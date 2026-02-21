"""Post-viewing survey submission."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Session as SessionModel, SurveyResponse
from app.schemas import SurveySubmit, SurveyResponseSchema
from app.auth import require_viewer, get_current_user

router = APIRouter(prefix="/survey", tags=["survey"])


@router.post("/sessions/{session_id}", response_model=SurveyResponseSchema)
def submit_survey(
    session_id: int,
    data: SurveySubmit,
    user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    if data.intensity < 1 or data.intensity > 10:
        raise HTTPException(status_code=400, detail="Intensity must be 1-10")
    session = db.query(SessionModel).filter(SessionModel.id == session_id, SessionModel.viewer_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    existing = db.query(SurveyResponse).filter(SurveyResponse.session_id == session_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Survey already submitted")
    resp = SurveyResponse(
        session_id=session_id,
        reported_emotion=data.reported_emotion,
        intensity=data.intensity,
        feedback_text=data.feedback_text,
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)
    return resp
