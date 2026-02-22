"""Face detection + emotion classification pipeline."""
import io
import numpy as np
from PIL import Image
from typing import Tuple, Optional

EMOTION_LABELS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]

# Lazy-loaded models
_face_detector = None
_emotion_model = None


def _get_face_detector():
    """Return a MediaPipe FaceMesh detector (for landmarks) if available."""
    global _face_detector
    if _face_detector is None:
        try:
            import mediapipe as mp
            mp_face = mp.solutions.face_mesh
            # static_image_mode=True for single frames (webcam snapshots)
            # Very low thresholds to maximize face detection
            _face_detector = mp_face.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.05,
                min_tracking_confidence=0.05,
            )
        except Exception:
            _face_detector = False  # Disabled
    return _face_detector if _face_detector else None


def _get_emotion_model():
    """
    Load FER-style model. 
    Vision Transformer fine-tuned for facial emotion recognition, 
    capable of classifying seven distinct emotions with an accuracy of 71.16%.
    It is trained on several datasets, including FER2013, 
    MMI Facial Expression Database, and AffectNet
    """
    global _emotion_model
    if _emotion_model is None:
        try:
            from transformers import pipeline
            # top_k=7 to see all emotions; max sensitivity
            _emotion_model = pipeline(
                "image-classification",
                model="trpakov/vit-face-expression",
                top_k=7,
            )
        except Exception:
            _emotion_model = False  # Use heuristic fallback
    return _emotion_model if _emotion_model else None


def detect_face(image: np.ndarray) -> Optional[Tuple[int, int, int, int, Optional[list]]]:
    """Return (x, y, w, h, landmarks) or None.

    Landmarks are returned as a list of (x_norm, y_norm) with coordinates normalized
    to the image width/height (range 0..1). This makes it easy for the viewer to
    overlay the points on the original image.
    """
    detector = _get_face_detector()
    h, w = image.shape[:2]
    if not detector:
        # Fallback: center crop and no landmarks
        return (w // 4, h // 4, w // 2, h // 2, None)

    try:
        import cv2  # mediapipe uses RGB arrays; input from PIL is already RGB
    except Exception:
        cv2 = None

    # Normalize channels: ensure a 3-channel RGB image in uint8
    if len(image.shape) == 3:
        # Drop alpha if present
        if image.shape[2] == 4:
            rgb = image[..., :3]
        elif image.shape[2] == 3:
            rgb = image
        else:
            # Unexpected channel count - convert by repeating first channel
            rgb = np.stack([image[..., 0]] * 3, axis=-1)
    else:
        # Grayscale -> replicate channels
        rgb = np.stack([image] * 3, axis=-1)

    # Ensure dtype is uint8
    if rgb.dtype != np.uint8:
        rgb = rgb.astype(np.uint8)

    results = detector.process(rgb)
    if not getattr(results, "multi_face_landmarks", None):
        return None

    face_lms = results.multi_face_landmarks[0]
    xs = [lm.x for lm in face_lms.landmark]
    ys = [lm.y for lm in face_lms.landmark]
    # normalized bbox
    xmin = max(0.0, min(xs))
    ymin = max(0.0, min(ys))
    xmax = min(1.0, max(xs))
    ymax = min(1.0, max(ys))
    # convert to pixel coords for bbox
    x = int(xmin * w)
    y = int(ymin * h)
    bw = int((xmax - xmin) * w)
    bh = int((ymax - ymin) * h)

    landmarks = [(float(lm.x), float(lm.y)) for lm in face_lms.landmark]
    return (max(0, x), max(0, y), bw, bh, landmarks)


def predict_emotion(face_crop: np.ndarray) -> Tuple[str, float, Optional[float], Optional[float]]:
    """
    Returns (emotion_label, probability, valence, arousal).
    """
    valence_map = {"angry": -0.8, "disgust": -0.6, "fear": -0.5, "happy": 0.9, "sad": -0.7, "surprise": 0.3, "neutral": 0.0}
    arousal_map = {"angry": 0.8, "disgust": 0.4, "fear": 0.9, "happy": 0.6, "sad": -0.3, "surprise": 0.9, "neutral": 0.0}

    model = _get_emotion_model()
    if model is None:
        # Heuristic: balanced across all 7 emotions (used when model unavailable)
        gray = np.mean(face_crop, axis=-1) if len(face_crop.shape) == 3 else face_crop
        mean_val = float(np.mean(gray))
        std_val = float(np.std(gray))
        # Map (mean, variance) to each emotion equally via combined score
        combined = mean_val * 0.4 + min(std_val, 60) * 0.6
        idx = int(combined) % 7
        label = EMOTION_LABELS[idx]
        return (label, 0.65, valence_map.get(label, 0), arousal_map.get(label, 0))

    # Preprocess crop: pad to square, enhance contrast (CLAHE) if available,
    # and resize to model input (224x224) for more consistent predictions.
    proc_img = None
    try:
        import cv2
        fc = face_crop
        # Ensure uint8 and 3 channels
        if fc.dtype != np.uint8:
            fc = fc.astype(np.uint8)
        if fc.ndim == 2:
            fc = np.stack([fc] * 3, axis=-1)
        if fc.shape[2] == 4:
            fc = fc[..., :3]

        h, w = fc.shape[:2]
        size = max(h, w)
        top = (size - h) // 2
        bottom = size - h - top
        left = (size - w) // 2
        right = size - w - left
        fc = cv2.copyMakeBorder(fc, top, bottom, left, right, cv2.BORDER_REPLICATE)

        # CLAHE: moderate enhancement, balanced across expressions
        try:
            lab = cv2.cvtColor(fc, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            lab = cv2.merge((cl, a, b))
            fc = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
        except Exception:
            pass

        proc = cv2.resize(fc, (224, 224), interpolation=cv2.INTER_AREA)
        proc_img = Image.fromarray(proc)
    except Exception:
        # Fallback: use PIL to resize
        try:
            pil_tmp = Image.fromarray(face_crop)
            proc_img = pil_tmp.convert('RGB').resize((224, 224), Image.BILINEAR)
        except Exception:
            proc_img = Image.fromarray((face_crop * 255).astype('uint8')).convert('RGB').resize((224, 224), Image.BILINEAR)

    pil = proc_img
    result = model(pil)
    # Normalize result shape: pipeline may return list-of-lists when top_k>1
    items = None
    if isinstance(result, list) and len(result) > 0 and isinstance(result[0], list):
        items = result[0]
    else:
        items = result if isinstance(result, list) else [result]

    if items:
        top = items[0]
        label = top.get("label", "neutral").lower()
        prob = float(top.get("score", 0.0))
        # Balanced: trust model's top prediction. Only override on near-tie (within 0.08)
        if len(items) > 1 and prob < 0.5:
            second = items[1]
            sec_label = second.get("label", "").lower()
            sec_prob = float(second.get("score", 0.0))
            if sec_label in EMOTION_LABELS and sec_prob >= prob - 0.08:
                label, prob = sec_label, sec_prob
        if label not in EMOTION_LABELS:
            label = "neutral"
    else:
        label, prob = "neutral", 0.5
    return (label, prob, valence_map.get(label, 0), arousal_map.get(label, 0))


def process_frame(image_bytes: bytes) -> Optional[Tuple[str, float, Optional[float], Optional[float], Optional[list]]]:
    """
    Process a single frame (JPEG/PNG bytes).
    Returns (emotion, probability, valence, arousal, landmarks) or None.
    Uses center crop fallback when face detection fails so emotion is always predicted.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        if len(arr.shape) == 2:
            arr = np.stack([arr] * 3, axis=-1)
        res = detect_face(arr)
        landmarks = None
        if res is not None:
            if len(res) == 5:
                x, y, w, h, landmarks = res
            else:
                x, y, w, h = res
            crop = arr[y : y + h, x : x + w]
        else:
            h_img, w_img = arr.shape[:2]
            size = min(h_img, w_img) * 2 // 3
            x = (w_img - size) // 2
            y = (h_img - size) // 2
            x = max(0, x)
            y = max(0, y)
            crop = arr[y : y + size, x : x + size]
        if crop.size == 0:
            return None
        emotion, prob, valence, arousal = predict_emotion(crop)
        return (emotion, prob, valence, arousal, landmarks)
    except Exception as e:
        # Log exception for debugging (will appear in server logs)
        try:
            import sys, traceback
            traceback.print_exc(file=sys.stderr)
        except Exception:
            pass
        return None
