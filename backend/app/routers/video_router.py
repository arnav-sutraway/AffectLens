"""Video upload and management endpoints."""
import os
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
    
    # Create director-specific upload directory
    director_dir = os.path.join(settings.upload_dir, str(user.id))
    Path(director_dir).mkdir(parents=True, exist_ok=True)
    
    # Save file with temporary name first
    temp_file_path = os.path.join(director_dir, f".temp_{file.filename}")
    with open(temp_file_path, "wb") as f:
        content = file.file.read()
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            raise HTTPException(status_code=400, detail=f"File too large (max {settings.max_upload_mb}MB)")
        f.write(content)
    
    # Create database entry (this generates the ID)
    video = Video(
        director_id=user.id,
        filename=file.filename,
        file_path="",  # Will be updated after we have the ID
        title=title,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    
    # Now rename file to use video ID as filename: uploads/{director_id}/{video_id}.mp4
    final_file_path = os.path.join(director_dir, f"{video.id}.mp4")
    os.rename(temp_file_path, final_file_path)
    
    # Update the file_path in database with the final path
    video.file_path = final_file_path
    db.commit()
    db.refresh(video)
    return video


@router.get("", response_model=list[VideoResponse])
def list_videos(
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    return db.query(Video).filter(Video.director_id == user.id).order_by(Video.upload_time.desc()).all()


@router.get("/available/list", response_model=list[VideoResponse])
def list_available_videos(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all available videos for viewers to watch."""
    return db.query(Video).order_by(Video.upload_time.desc()).all()


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
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        if not os.path.exists(video.file_path):
            raise HTTPException(status_code=404, detail="Video file not found")
        return FileResponse(video.file_path, media_type="video/mp4")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    try:
        video = db.query(Video).filter(Video.id == video_id, Video.director_id == user.id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Delete related sessions first (they will cascade delete emotion_readings and survey_responses)
        from app.models import Session as SessionModel
        sessions = db.query(SessionModel).filter(SessionModel.video_id == video_id).all()
        for session in sessions:
            db.delete(session)
        
        # Delete the file from disk (if it exists)
        try:
            if video.file_path and os.path.exists(video.file_path):
                os.remove(video.file_path)
        except Exception as e:
            # Log but continue - file might already be deleted or path might be invalid
            pass
        
        # Delete from database
        db.delete(video)
        db.commit()
        return {"message": "Video deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete video: {str(e)}")
