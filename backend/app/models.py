"""SQLAlchemy models for AffectLens."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class UserRole(str, enum.Enum):
    director = "director"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    videos = relationship("Video", back_populates="director", foreign_keys="Video.director_id")
    sessions = relationship("Session", back_populates="viewer")


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    director_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(512), nullable=False)
    file_path = Column(String(1024), nullable=False)
    title = Column(String(256), default="Untitled")
    intended_emotion_curve = Column(Text, nullable=True)  # JSON: [{timestamp, emotion}]
    upload_time = Column(DateTime, default=datetime.utcnow)

    director = relationship("User", back_populates="videos", foreign_keys=[director_id])
    sessions = relationship("Session", back_populates="video")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False)
    viewer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    video = relationship("Video", back_populates="sessions")
    viewer = relationship("User", back_populates="sessions")
    emotion_readings = relationship("EmotionReading", back_populates="session", cascade="all, delete-orphan")
    survey_response = relationship("SurveyResponse", back_populates="session", uselist=False, cascade="all, delete-orphan")


class EmotionReading(Base):
    __tablename__ = "emotion_readings"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    timestamp = Column(Float, nullable=False)  # seconds into video
    emotion_label = Column(String(64), nullable=False)
    probability = Column(Float, nullable=False)
    valence = Column(Float, nullable=True)
    arousal = Column(Float, nullable=True)

    session = relationship("Session", back_populates="emotion_readings")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)
    reported_emotion = Column(String(64), nullable=False)
    intensity = Column(Integer, nullable=False)  # 1-10
    feedback_text = Column(Text, nullable=True)

    session = relationship("Session", back_populates="survey_response")


class AggregatedAnalytics(Base):
    __tablename__ = "aggregated_analytics"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=False, unique=True)
    avg_emotion_curve = Column(Text, nullable=True)  # JSON
    alignment_score = Column(Float, nullable=True)
    emotional_volatility = Column(Float, nullable=True)
    peak_engagement_timestamps = Column(Text, nullable=True)  # JSON array
    ai_summary = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
