# AffectLens — Real-Time Audience Emotion Intelligence

**Data-driven storytelling optimization.** A platform where directors upload short video clips and receive timestamped emotional analytics, aggregated audience reaction curves, sentiment alignment, and AI-generated narrative feedback.

## Features

### Director Flow
- Upload MP4 clips
- Tag intended emotional beats
- View analytics dashboard (alignment score, emotional volatility, model vs survey)
- Export PDF reports
- Download analytics reports

### Viewer Flow
- Watch assigned clips with real-time webcam emotion tracking
- **Post-viewing survey** appears immediately when the video ends (no delay)
- Explicit consent for webcam access; only emotion data stored—no raw face images

### ML Pipeline — Emotion Detection
- **Face detection**: MediaPipe FaceMesh (`static_image_mode=True` for single frames, low confidence thresholds for maximum sensitivity)
- **Center-crop fallback**: When face detection fails (e.g., lighting, angle), uses a center crop so emotion is always predicted
- **Emotion model**: Vision Transformer (`trpakov/vit-face-expression`), 7 classes—angry, disgust, fear, happy, sad, surprise, neutral
- **Balanced detection**: All facial expressions are equally detectable; no bias toward any emotion
- **Heuristic fallback**: When the model is unavailable, uses a balanced intensity/variance heuristic across all 7 emotions
- **CLAHE** contrast enhancement for consistent predictions across lighting conditions

### Analytics
- Emotion-over-time curves
- Alignment score (model predictions vs intended beats)
- Emotional volatility
- Model vs survey alignment
- AI-generated narrative summary

### Ethics
- Explicit webcam consent
- No raw face storage
- Transparency statement

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, JWT, PyTorch, MediaPipe, OpenCV, Transformers (Hugging Face)
- **Frontend**: Plain HTML, CSS, JavaScript (served by backend)

## Quick Start

### Prerequisites

- Python 3.12+

### 1. Backend (serves API + frontend)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Open the app

Go to **http://localhost:8000**. The frontend is served by the backend.

## Database Configuration

**Default (SQLite)**: No setup required. The database file `affectlens.db` is created automatically in the `backend/` folder when you first run the server.

**PostgreSQL** (optional, for production):

1. Create a database:
   ```bash
   docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=affectlens postgres:16-alpine
   ```
2. Create `backend/.env` with:
   ```
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/affectlens
   ```

Tables are created automatically on first run.

## Docker (optional)

```bash
docker-compose up -d
# Backend: http://localhost:8000
```

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Register (director or viewer) |
| `POST` | `/auth/login` | Login |
| `POST` | `/videos/upload` | Upload MP4 (director) |
| `GET` | `/videos` | List videos (director) |
| `POST` | `/sessions` | Start viewing session (viewer) |
| `GET` | `/videos/{id}/stream` | Stream video |
| `POST` | `/inference/emotion` | Emotion inference from frame (viewer) |
| `POST` | `/emotions/sessions/{id}/readings` | Batch emotion readings |
| `POST` | `/sessions/{id}/complete` | Mark session complete |
| `POST` | `/survey/sessions/{id}` | Submit post-viewing survey (viewer) |
| `GET` | `/analytics/video/{id}` | Get analytics (director) |
| `GET` | `/analytics/video/{id}/export` | Export PDF report (director) |

## Project Structure

```
AffectLens/
├── backend/
│   ├── app/
│   │   ├── routers/        # API routes (auth, video, session, emotion, survey, analytics, inference)
│   │   ├── ml/             # Emotion detection pipeline
│   │   │   └── emotion_detector.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── main.py
│   ├── static/             # HTML, CSS, JS frontend
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   ├── alembic/
│   └── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

## Emotion Detection Details

- **Capture rate**: 100ms per frame for responsive real-time updates
- **Aggregator**: 4-frame rolling buffer with equal weighting for all emotions
- **Model**: ViT fine-tuned on FER2013, MMI, AffectNet (~71% accuracy)
- **Fallbacks**: Center crop when no face detected; heuristic when model fails to load

## Datasets for Fine-Tuning

- **FER2013**: 35k grayscale faces, 7 emotions
- **AffectNet**: 1M+ images, valence-arousal
- **RAVDESS**: Emotional speech (multimodal)

## License

MIT
