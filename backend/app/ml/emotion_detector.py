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
            # More sensitive defaults (lower confidence) to detect faces more often
            _face_detector = mp_face.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.3, min_tracking_confidence=0.3)
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
            # Request top_k=3 so we can disambiguate 'neutral' predictions
            _emotion_model = pipeline(
                "image-classification",
                model="trpakov/vit-face-expression",
                top_k=3,
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

    import cv2
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image
    if len(rgb.shape) == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
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
        # Fallback: heuristic based on face region intensity (demo mode)
        gray = np.mean(face_crop, axis=-1) if len(face_crop.shape) == 3 else face_crop
        mean_val = np.mean(gray)
        if mean_val < 80:
            return ("sad", 0.7, -0.3, 0.2)
        if mean_val > 180:
            return ("happy", 0.7, 0.5, 0.4)
        return ("neutral", 0.8, 0.0, 0.2)

    pil = Image.fromarray(face_crop)
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
        # If the top label is neutral but a close second exists, prefer it
        if label == "neutral" and len(items) > 1:
            second = items[1]
            sec_label = second.get("label", "neutral").lower()
            sec_prob = float(second.get("score", 0.0))
            # If the second non-neutral is within 0.15 of top, prefer it
            if sec_label != "neutral" and sec_prob >= prob - 0.15:
                label, prob = sec_label, sec_prob
        if label not in EMOTION_LABELS:
            label = "neutral"
    else:
        label, prob = "neutral", 0.5
    return (label, prob, valence_map.get(label, 0), arousal_map.get(label, 0))


def process_frame(image_bytes: bytes) -> Optional[Tuple[str, float, Optional[float], Optional[float], Optional[list]]]:
    """
    Process a single frame (JPEG/PNG bytes).
    Returns (emotion, probability, valence, arousal, landmarks) or None if no face.
    Landmarks are a list of (x_norm, y_norm) pairs normalized to the input image size.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        if len(arr.shape) == 2:
            arr = np.stack([arr] * 3, axis=-1)
        res = detect_face(arr)
        if res is None:
            return None
        # detect_face now returns (x, y, w, h, landmarks)
        if len(res) == 5:
            x, y, w, h, landmarks = res
        else:
            x, y, w, h = res
            landmarks = None
        crop = arr[y : y + h, x : x + w]
        if crop.size == 0:
            return None
        emotion, prob, valence, arousal = predict_emotion(crop)
        return (emotion, prob, valence, arousal, landmarks)
    except Exception:
        return None
