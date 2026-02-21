"""Pydantic schemas for API validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


# Auth
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "viewer"  # "director" | "viewer"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str


class UserResponse(BaseModel):
    id: int
    email: str
    role: str

    class Config:
        from_attributes = True


# Video
class VideoCreate(BaseModel):
    title: Optional[str] = "Untitled"


class VideoResponse(BaseModel):
    id: int
    director_id: int
    filename: str
    title: str
    upload_time: datetime

    class Config:
        from_attributes = True


class IntendedEmotionBeat(BaseModel):
    timestamp: float
    emotion: str


class VideoUpdateIntended(BaseModel):
    intended_emotion_curve: List[IntendedEmotionBeat]


# Session
class SessionCreate(BaseModel):
    video_id: int


class SessionResponse(BaseModel):
    id: int
    video_id: int
    viewer_id: int
    started_at: datetime

    class Config:
        from_attributes = True


# Emotion
class EmotionReadingCreate(BaseModel):
    timestamp: float
    emotion_label: str
    probability: float
    valence: Optional[float] = None
    arousal: Optional[float] = None


class EmotionReadingBatch(BaseModel):
    readings: List[EmotionReadingCreate]


# Survey
class SurveySubmit(BaseModel):
    reported_emotion: str
    intensity: int  # 1-10
    feedback_text: Optional[str] = None


class SurveyResponseSchema(BaseModel):
    id: int
    session_id: int
    reported_emotion: str
    intensity: int
    feedback_text: Optional[str] = None

    class Config:
        from_attributes = True


# Analytics
class EmotionCurvePoint(BaseModel):
    timestamp: float
    emotion: str
    value: float


class AnalyticsResponse(BaseModel):
    video_id: int
    avg_emotion_curve: List[dict]
    alignment_score: Optional[float]
    emotional_volatility: Optional[float]
    peak_engagement_timestamps: List[float]
    ai_summary: Optional[str]
    model_vs_survey_alignment: Optional[float]
