"""Emotion readings ingestion from viewer client."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Session as SessionModel, EmotionReading
from app.schemas import EmotionReadingBatch
from app.auth import require_viewer, get_current_user

router = APIRouter(prefix="/emotions", tags=["emotions"])


@router.post("/sessions/{session_id}/readings")
def submit_emotion_readings(
    session_id: int,
    data: EmotionReadingBatch,
    user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id, SessionModel.viewer_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    for r in data.readings:
        reading = EmotionReading(
            session_id=session_id,
            timestamp=r.timestamp,
            emotion_label=r.emotion_label,
            probability=r.probability,
            valence=r.valence,
            arousal=r.arousal,
        )
        db.add(reading)
    db.commit()
    return {"count": len(data.readings)}
