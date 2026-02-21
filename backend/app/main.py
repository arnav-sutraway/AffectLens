"""AffectLens API - Real-Time Audience Emotion Intelligence."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import engine, Base
from app.routers import auth_router, video_router, session_router, emotion_router, survey_router, analytics_router, inference_router

STATIC_DIR = Path(__file__).parent.parent / "static"

app = FastAPI(
    title="AffectLens",
    description="Real-Time Audience Emotion Intelligence for Data-Driven Storytelling Optimization",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables
Base.metadata.create_all(bind=engine)

app.include_router(auth_router.router)
app.include_router(video_router.router)
app.include_router(session_router.router)
app.include_router(emotion_router.router)
app.include_router(survey_router.router)
app.include_router(analytics_router.router)
app.include_router(inference_router.router)


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}
