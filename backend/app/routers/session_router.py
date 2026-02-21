"""Session management for viewer watching flow."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Video, Session as SessionModel
from app.schemas import SessionCreate, SessionResponse
from app.auth import get_current_user, require_viewer

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
def create_session(
    data: SessionCreate,
    user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    session = SessionModel(video_id=data.video_id, viewer_id=user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.viewer_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return session


@router.post("/{session_id}/complete")
def complete_session(
    session_id: int,
    user: User = Depends(require_viewer),
    db: Session = Depends(get_db),
):
    from datetime import datetime
    session = db.query(SessionModel).filter(SessionModel.id == session_id, SessionModel.viewer_id == user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.completed_at = datetime.utcnow()
    db.commit()
    return {"status": "completed"}
