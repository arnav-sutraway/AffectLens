const API = ''; // Same origin - backend serves this

// ===== UI SESSION STATE =====
const UIState = {
  IDLE: 'idle',
  LOADING_VIDEO: 'loading_video',
  WAITING_CONSENT: 'waiting_consent',
  DETECTING: 'detecting',
  PAUSED: 'paused',
  FINISHED: 'finished',
  ERROR: 'error'
};

let uiState = UIState.IDLE;

function setUIState(state) {
  uiState = state;
  document.body.dataset.state = state;
  updateStatusText();
}

function updateStatusText() {
  const el = document.getElementById('statusText');
  if (!el) return;

  const messages = {
    idle: '',
    loading_video: 'Loading video…',
    waiting_consent: 'Waiting for camera access…',
    detecting: 'Detecting facial expressions',
    paused: 'Detection paused',
    finished: 'Session complete',
    error: 'Something went wrong'
  };

  el.textContent = messages[uiState] || '';
}

function getToken() { return localStorage.getItem('token'); }
function setToken(t) { localStorage.setItem('token', t); }
function setUser(u) { localStorage.setItem('user', JSON.stringify(u)); }
function getUser() {
  try { return JSON.parse(localStorage.getItem('user') || 'null'); } catch { return null; }
}
function clearAuth() { localStorage.removeItem('token'); localStorage.removeItem('user'); }

async function api(path, opts = {}) {
  const headers = { ...opts.headers };
  if (!headers['Content-Type'] && typeof opts.body === 'string') headers['Content-Type'] = 'application/json';
  const token = getToken();
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const res = await fetch(API + path, { ...opts, headers });
  if (res.status === 401 && path !== '/auth/login') { clearAuth(); window.location.reload(); return; }
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }
  if (!res.ok) throw { status: res.status, data, message: data?.detail || res.statusText };
  return data;
}

function showView(id) {
  document.querySelectorAll('.view').forEach(v => v.style.display = 'none');
  const el = document.getElementById(id);
  if (el) el.style.display = 'block';
  // Load available videos when switching to watchView
  if (id === 'watchView') loadAvailableVideos();
}

function updateNav() {
  const user = getUser();
  const el = document.getElementById('navUser');
  if (!user) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <span>${user.email}</span>
    <span class="role">${user.role}</span>
    ${user.role === 'director' ? '<a href="#" data-view="dashboardView">Dashboard</a>' : '<a href="#" data-view="watchView">Watch</a>'}
    <a href="#" id="logout">Logout</a>
  `;
  el.querySelector('#logout').onclick = (e) => { e.preventDefault(); clearAuth(); window.location.reload(); };
  el.querySelectorAll('[data-view]').forEach(a => {
    a.onclick = (e) => { e.preventDefault(); showView(a.dataset.view); };
  });
}

// Login
document.getElementById('showRegister').onclick = (e) => { e.preventDefault(); showView('registerView'); document.getElementById('registerError').textContent = ''; };
document.getElementById('showLogin').onclick = (e) => { e.preventDefault(); showView('loginView'); document.getElementById('loginError').textContent = ''; };

document.getElementById('loginForm').onsubmit = async (e) => {
  e.preventDefault();
  const err = document.getElementById('loginError');
  err.textContent = '';
  try {
    const data = await api('/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('loginEmail').value.trim(),
        password: document.getElementById('loginPassword').value
      })
    });
    setToken(data.access_token);
    setUser({ id: data.user_id, email: document.getElementById('loginEmail').value.trim(), role: data.role });
    updateNav();
    showView(data.role === 'director' ? 'dashboardView' : 'watchView');
    if (data.role === 'director') loadVideos();
  } catch (ex) {
    if (ex.status === 401 || (ex.data?.detail && String(ex.data.detail).toLowerCase().includes('invalid'))) {
      err.textContent = 'Your entered details were invalid. Please try again.';
    } else {
      const d = ex.data?.detail ?? ex.data;
      err.textContent = (Array.isArray(d) ? d.map(x => x.msg).join(', ') : (typeof d === 'string' ? d : ex.data?.detail || ex.message)) || 'Login failed';
    }
  }
};

document.getElementById('registerForm').onsubmit = async (e) => {
  e.preventDefault();
  const err = document.getElementById('registerError');
  err.textContent = '';
  const email = document.getElementById('regEmail').value.trim();
  const password = document.getElementById('regPassword').value;
  const role = document.getElementById('regRole').value;
  if (!email || !password) { err.textContent = 'Email and password required'; return; }
  try {
    const data = await api('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, role })
    });
    setToken(data.access_token);
    setUser({ id: data.user_id, email, role: data.role });
    updateNav();
    showView(data.role === 'director' ? 'dashboardView' : 'watchView');
    if (data.role === 'director') loadVideos();
  } catch (ex) {
    const d = ex.data?.detail ?? ex.data;
    const msg = Array.isArray(d) ? d.map(x => (x.loc ? x.loc.slice(1).join('.') + ': ' : '') + (x.msg || '')).join('; ') : (typeof d === 'string' ? d : ex.data?.detail || ex.message);
    err.textContent = msg || 'Registration failed';
  }
};

// Director
let selectedVideoId = null;
async function loadVideos() {
  try {
    const list = await api('/videos');
    const el = document.getElementById('videoList');
    el.innerHTML = list.length ? list.map(v => `
      <div class="video-item" data-id="${v.id}">
        <button type="button" class="${v.id === selectedVideoId ? 'active' : ''}" data-id="${v.id}">
          <div>${v.title || v.filename}</div>
          <div class="filename">${v.filename}</div>
        </button>
        <button type="button" class="delete-btn" data-id="${v.id}" aria-label="Delete video">🗑️</button>
      </div>
    `).join('') : '<p style="color:var(--text-muted)">No videos yet</p>';
    el.querySelectorAll('.video-item > button:not(.delete-btn)').forEach(b => {
      b.onclick = () => { selectedVideoId = parseInt(b.dataset.id); loadVideos(); loadAnalytics(selectedVideoId); };
    });
    el.querySelectorAll('.delete-btn').forEach(btn => {
      btn.onclick = async (e) => {
        e.stopPropagation();
        const videoId = parseInt(btn.dataset.id, 10);
        if (confirm('Are you sure you want to delete this video?')) {
          try {
            await api('/videos/' + videoId, { method: 'DELETE' });
            if (selectedVideoId === videoId) {
              selectedVideoId = null;
              document.getElementById('analyticsPlaceholder').style.display = 'block';
              document.getElementById('analyticsContent').style.display = 'none';
            }
            loadVideos();
          } catch (ex) {
            alert((ex.data?.detail || ex.message) || 'Failed to delete video');
          }
        }
      };
    });
  } catch (e) { console.error(e); }
}

async function loadAnalytics(videoId) {
  const ph = document.getElementById('analyticsPlaceholder');
  const content = document.getElementById('analyticsContent');
  try {
    const a = await api('/analytics/video/' + videoId);
    ph.style.display = 'none';
    content.style.display = 'block';
    document.getElementById('statsRow').innerHTML = `
      <div class="stat-box"><div class="label">Alignment</div><div class="value" style="color:var(--accent)">${a.alignment_score ?? 0}%</div></div>
      <div class="stat-box"><div class="label">Volatility</div><div class="value" style="color:#f59e0b">${a.emotional_volatility ?? 0}%</div></div>
      <div class="stat-box"><div class="label">Model vs Survey</div><div class="value" style="color:#22c55e">${a.model_vs_survey_alignment ?? '-'}%</div></div>
      <div class="stat-box stat-box-download">
        <div class="label">Download Report</div>
        <div class="download-symbol" id="exportPdf" aria-label="Download PDF">⬇</div>
      </div>
    `;
    document.getElementById('exportPdf').onclick = async (e) => {
      e.preventDefault();
      const res = await fetch(API + '/analytics/video/' + videoId + '/export', { headers: { Authorization: 'Bearer ' + getToken() } });
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'analytics.pdf'; a.click();
      URL.revokeObjectURL(url);
    };
    document.getElementById('aiSummary').textContent = a.ai_summary || 'No summary available.';
    const curve = a.avg_emotion_curve || [];
    document.getElementById('chartArea').innerHTML = curve.length ? '<p style="color:var(--text-muted)">' + curve.map(c => c.timestamp + 's: ' + c.emotion).join(', ') + '</p>' : '<p style="color:var(--text-muted)">No data</p>';
    const emotionColors = { happy: '#ec4899', sad: '#3b82f6', angry: '#ef4444', neutral: '#6b7280', surprise: '#eab308', surprised: '#eab308', fear: '#1f2937', disgust: '#166534' };
    const tubeEl = document.getElementById('emotionTube');
    if (curve.length) {
      const total = Math.max(1, curve[curve.length - 1].timestamp - curve[0].timestamp + 1);
      tubeEl.innerHTML = curve.map((c, i) => {
        const nextTs = i < curve.length - 1 ? curve[i + 1].timestamp : c.timestamp + 1;
        const width = ((nextTs - c.timestamp) / total) * 100;
        const color = emotionColors[c.emotion?.toLowerCase()] || emotionColors.neutral;
        return `<span class="emotion-tube-segment" style="width:${width}%;background:${color}" title="${c.timestamp}s: ${c.emotion}"></span>`;
      }).join('');
    } else {
      tubeEl.innerHTML = '';
    }
  } catch (e) { ph.style.display = 'block'; content.style.display = 'none'; ph.textContent = 'Failed to load analytics'; }
}

document.getElementById('videoFile').onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const title = document.getElementById('videoTitle').value || file.name;
  const fd = new FormData();
  fd.append('file', file);
  fd.append('title', title);
  try {
    await api('/videos/upload', { method: 'POST', body: fd });
    document.getElementById('videoTitle').value = '';
    e.target.value = '';
    loadVideos();
  } catch (ex) { alert((ex.data?.detail || ex.message) || 'Upload failed'); }
};

// Viewer
async function loadAvailableVideos() {
  try {
    const videos = await api('/videos/available/list');
    const container = document.getElementById('availableVideosList');
    if (!videos || videos.length === 0) {
      container.innerHTML = '<p>No videos available at this time.</p>';
      return;
    }
    container.innerHTML = videos.map(v => `
      <div class="video-item card" style="cursor: pointer; margin-bottom: 1rem;" onclick="startWatching(${v.id})">
        <h3>${v.title || 'Untitled'}</h3>
        <p>ID: ${v.id} • Uploaded: ${new Date(v.upload_time).toLocaleDateString()}</p>
      </div>
    `).join('');
  } catch (ex) {
    console.error('Failed to load videos:', ex);
    document.getElementById('availableVideosList').innerHTML = '<p>Failed to load videos.</p>';
  }
}

let currentSessionId = null;
let streamRef = null;
let videoBlobUrl = null;

async function startWatching(videoId) {
  try {
    setUIState(UIState.LOADING_VIDEO);
    const sess = await api('/sessions', { method: 'POST', body: JSON.stringify({ video_id: videoId }) });
    currentSessionId = sess.id;
    const res = await fetch(API + '/videos/' + videoId + '/stream', { headers: { Authorization: 'Bearer ' + getToken() } });
    if (!res.ok) throw new Error('Could not load video');
    videoBlobUrl = URL.createObjectURL(await res.blob());
    setUIState(UIState.WAITING_CONSENT);
    const consent = confirm('To capture your emotional reactions, we need webcam access. We only store emotion data—no face images. Click OK to enable, or Cancel to skip.');
    if (consent) {
      try { streamRef = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } }); } catch (e) { console.warn('Webcam denied'); }
    }
    showView('watchingView');
    const video = document.getElementById('mainVideo');
    video.src = videoBlobUrl;
    video.onended = () => {
      setUIState(UIState.FINISHED);
      finishWatching();
    };
    video.onplay = () => {
      setUIState(UIState.DETECTING);
      startCapture();
    };
    video.onpause = () => {
      setUIState(UIState.PAUSED);
      stopCapture();
    };
  } catch (ex) {
  setUIState(UIState.ERROR);
  alert((ex.data?.detail || ex.message) || 'Failed to start');
  }
}

let captureInterval = null;
function startCapture() {
  if (!streamRef || !currentSessionId) {
    setUIState(UIState.ERROR);
    return;
  }
  // Attach stream to visible webcam element if present
  const webcamPreview = document.getElementById('webcamPreview');
  const webcamVideo = document.getElementById('webcamVideo');
  if (webcamVideo && streamRef) {
    try { webcamVideo.srcObject = streamRef; webcamVideo.play().catch(()=>{}); webcamPreview.style.display = 'block'; } catch(e){}
  }
  captureInterval = setInterval(captureFrame, 500);
}
function stopCapture() { clearInterval(captureInterval); captureInterval = null; _hideWebcamPreview(); }

function _hideWebcamPreview() {
  const webcamPreview = document.getElementById('webcamPreview');
  const webcamVideo = document.getElementById('webcamVideo');
  const overlay = document.getElementById('overlayCanvas');
  if (webcamVideo && webcamVideo.srcObject) { try { webcamVideo.pause(); webcamVideo.srcObject = null; } catch(e){} }
  if (webcamPreview) webcamPreview.style.display = 'none';
  if (overlay && overlay.getContext) { const octx = overlay.getContext('2d'); octx && octx.clearRect(0,0,overlay.width||0, overlay.height||0); }
}

async function captureFrame() {
  if (!streamRef || !currentSessionId) return;
  const webcamVideo = document.getElementById('webcamVideo');
  if (!webcamVideo || webcamVideo.readyState < 2) return;
  // Reuse a hidden capture canvas
  if (!window._captureCanvas) {
    window._captureCanvas = document.createElement('canvas');
    window._captureCanvas.width = webcamVideo.videoWidth || 640;
    window._captureCanvas.height = webcamVideo.videoHeight || 480;
  }
  const canvas = window._captureCanvas;
  canvas.width = webcamVideo.videoWidth || 640;
  canvas.height = webcamVideo.videoHeight || 480;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.drawImage(webcamVideo, 0, 0, canvas.width, canvas.height);
  canvas.toBlob(async (blob) => {
    if (!blob) return;
    const mainVideo = document.getElementById('mainVideo');
    const ts = mainVideo ? mainVideo.currentTime : 0;
    try {
      const fd = new FormData();
      fd.append('file', blob, 'frame.jpg');
      const resp = await fetch(API + '/inference/emotion', { method: 'POST', headers: { Authorization: 'Bearer ' + getToken() }, body: fd });
      const data = await resp.json();
      // update badge
      if (data.face_detected) {
        document.getElementById('currentEmotion').textContent = data.emotion;
        // persist reading
        api('/emotions/sessions/' + currentSessionId + '/readings', {
          method: 'POST',
          body: JSON.stringify({ readings: [{ timestamp: ts, emotion_label: data.emotion, probability: data.probability, valence: data.valence, arousal: data.arousal }] })
        }).catch(()=>{});
      }
      // draw landmarks on overlay
      const overlay = document.getElementById('overlayCanvas');
      if (overlay) {
        overlay.width = overlay.clientWidth;
        overlay.height = overlay.clientHeight;
        const octx = overlay.getContext('2d');
        octx.clearRect(0,0,overlay.width, overlay.height);
        if (data.landmarks && Array.isArray(data.landmarks) && data.landmarks.length) {
          octx.fillStyle = 'rgba(0,255,128,0.95)';
          const vw = overlay.width, vh = overlay.height;
          // landmarks are normalized to image size used on server; map using capture canvas aspect ratio
          for (const lm of data.landmarks) {
            const x = lm.x * vw;
            const y = lm.y * vh;
            octx.beginPath(); octx.arc(x, y, 2.2, 0, Math.PI*2); octx.fill();
          }
        }
      }
    } catch (e) { /* ignore */ }
  }, 'image/jpeg');
}

async function finishWatching() {
  setUIState(UIState.FINISHED);
  stopCapture();
  if (streamRef) { streamRef.getTracks().forEach(t => t.stop()); streamRef = null; }
  _hideWebcamPreview();
  if (videoBlobUrl) { URL.revokeObjectURL(videoBlobUrl); videoBlobUrl = null; }
  if (currentSessionId) await api('/sessions/' + currentSessionId + '/complete', { method: 'POST' });
  showView('surveyView');
}

document.getElementById('surveyForm').onsubmit = async (e) => {
  e.preventDefault();
  if (!currentSessionId) return;
  try {
    await api('/survey/sessions/' + currentSessionId, {
      method: 'POST',
      body: JSON.stringify({
        reported_emotion: document.getElementById('reportedEmotion').value,
        intensity: parseInt(document.getElementById('intensity').value, 10),
        feedback_text: document.getElementById('feedbackText').value || undefined
      })
    });
    showView('thankYouView');
  } catch (ex) { alert((ex.data?.detail || ex.message) || 'Submit failed'); }
};

document.getElementById('intensity').oninput = () => { document.getElementById('intensityVal').textContent = document.getElementById('intensity').value; };
document.getElementById('watchAnother').onclick = (e) => { e.preventDefault(); currentSessionId = null; showView('watchView'); };

// Init
(function() {
  const user = getUser();
  if (user && getToken()) {
    updateNav();
    showView(user.role === 'director' ? 'dashboardView' : 'watchView');
    if (user.role === 'director') loadVideos();
  } else {
    showView('loginView');
  }
})();
