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
    global _face_detector
    if _face_detector is None:
        try:
            import mediapipe as mp
            mp_face = mp.solutions.face_detection
            _face_detector = mp_face.FaceDetection(min_detection_confidence=0.5)
        except Exception:
            _face_detector = False  # Disabled
    return _face_detector if _face_detector else None


def _get_emotion_model():
    """Load FER-style model. Uses heuristic fallback if unavailable."""
    global _emotion_model
    if _emotion_model is None:
        try:
            from transformers import pipeline
            _emotion_model = pipeline(
                "image-classification",
                model="trpakov/vit-face-expression",
                top_k=1,
            )
        except Exception:
            _emotion_model = False  # Use heuristic fallback
    return _emotion_model if _emotion_model else None


def detect_face(image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Return (x, y, w, h) face bbox or None."""
    detector = _get_face_detector()
    if not detector:
        h, w = image.shape[:2]
        return (w // 4, h // 4, w // 2, h // 2)  # Fallback: center crop

    import cv2
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else image
    if len(rgb.shape) == 2:
        rgb = np.stack([rgb] * 3, axis=-1)
    results = detector.process(rgb)
    if not results.detections:
        return None
    d = results.detections[0]
    bbox = d.location_data.relative_bounding_box
    h, w = image.shape[:2]
    x = int(bbox.xmin * w)
    y = int(bbox.ymin * h)
    bw = int(bbox.width * w)
    bh = int(bbox.height * h)
    return (max(0, x), max(0, y), bw, bh)


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
    if result:
        label = result[0]["label"].lower()
        prob = float(result[0]["score"])
        # Map model labels to our 7 classes if needed
        if label not in EMOTION_LABELS:
            label = "neutral"
    else:
        label, prob = "neutral", 0.5
    return (label, prob, valence_map.get(label, 0), arousal_map.get(label, 0))


def process_frame(image_bytes: bytes) -> Optional[Tuple[str, float, Optional[float], Optional[float]]]:
    """
    Process a single frame (JPEG/PNG bytes).
    Returns (emotion, probability, valence, arousal) or None if no face.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        arr = np.array(img)
        if len(arr.shape) == 2:
            arr = np.stack([arr] * 3, axis=-1)
        bbox = detect_face(arr)
        if bbox is None:
            return None
        x, y, w, h = bbox
        crop = arr[y : y + h, x : x + w]
        if crop.size == 0:
            return None
        return predict_emotion(crop)
    except Exception:
        return None
