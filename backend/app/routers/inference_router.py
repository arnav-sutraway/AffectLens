"""ML inference endpoint for real-time emotion detection."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.auth import get_current_user
from app.ml.emotion_detector import process_frame

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("/emotion")
def infer_emotion(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """Process a single frame and return emotion prediction."""
    if not file.content_type or "image" not in file.content_type:
        raise HTTPException(status_code=400, detail="Image file required (JPEG/PNG)")
    data = file.file.read()
    result = process_frame(data)
    if result is None:
        return {"emotion": "neutral", "probability": 0.0, "valence": 0.0, "arousal": 0.0, "face_detected": False}
    emotion, prob, valence, arousal = result
    return {
        "emotion": emotion,
        "probability": round(prob, 4),
        "valence": round(valence or 0, 4),
        "arousal": round(arousal or 0, 4),
        "face_detected": True,
    }
