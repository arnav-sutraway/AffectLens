"""Video upload and management endpoints."""
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Video
from app.schemas import VideoResponse, VideoUpdateIntended
from app.auth import require_director, get_current_user
from app.config import settings

router = APIRouter(prefix="/videos", tags=["videos"])

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=VideoResponse)
def upload_video(
    file: UploadFile = File(...),
    title: str = Form("Untitled"),
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Only MP4 files allowed")
    ext = Path(file.filename).suffix
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, unique_name)
    with open(file_path, "wb") as f:
        content = file.file.read()
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File too large (max {settings.max_upload_mb}MB)")
        f.write(content)
    video = Video(
        director_id=user.id,
        filename=file.filename,
        file_path=file_path,
        title=title,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


@router.get("", response_model=list[VideoResponse])
def list_videos(
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    return db.query(Video).filter(Video.director_id == user.id).order_by(Video.upload_time.desc()).all()


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if user.role.value == "director" and video.director_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return video


@router.patch("/{video_id}/intended", response_model=VideoResponse)
def update_intended_emotion(
    video_id: int,
    data: VideoUpdateIntended,
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == video_id, Video.director_id == user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    import json
    video.intended_emotion_curve = json.dumps([b.model_dump() for b in data.intended_emotion_curve])
    db.commit()
    db.refresh(video)
    return video


@router.get("/{video_id}/stream")
def stream_video(
    video_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from fastapi.responses import FileResponse
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video.file_path, media_type="video/mp4")


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == video_id, Video.director_id == user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete the file from disk
    if os.path.exists(video.file_path):
        try:
            os.remove(video.file_path)
        except Exception as e:
            pass  # Continue even if file deletion fails
    
    # Delete from database
    db.delete(video)
    db.commit()
    return {"message": "Video deleted successfully"}
