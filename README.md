# AffectLens — Real-Time Audience Emotion Intelligence

**Data-driven storytelling optimization.** A platform where directors upload short video clips and receive timestamped emotional analytics, aggregated audience reaction curves, sentiment alignment, and AI-generated narrative feedback.

## Features

- **Director Flow**: Upload MP4 clips, tag intended emotional beats, view analytics dashboard, export PDF reports
- **Viewer Flow**: Watch assigned clips with optional webcam emotion tracking, complete post-viewing survey
- **ML Pipeline**: Face detection (MediaPipe) + emotion classification (7 classes: angry, disgust, fear, happy, sad, surprise, neutral)
- **Analytics**: Emotion-over-time curves, alignment score, emotional volatility, peak engagement, AI summary
- **Ethics**: Explicit consent, no raw face storage, transparency statement

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, JWT, PyTorch, MediaPipe
- **Frontend**: Plain HTML, CSS, JavaScript (served by backend)

## Quick Start

### Prerequisites

- Python 3.12+

### 1. Backend (serves API + frontend)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS/Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Open the app

Go to **http://localhost:8000** — the frontend is served by the backend.

## Database Configuration

**Default (SQLite)**: No setup required. The database file `affectlens.db` is created automatically in the `backend/` folder when you first run the server.

**PostgreSQL** (optional, for production):

1. Create a database: `docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=affectlens postgres:16-alpine`
2. Create `backend/.env` with:
   ```
   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/affectlens
   ```

Tables are created automatically on first run.

### 4. Docker (optional)

```bash
docker-compose up -d
# Backend: http://localhost:8000
# Run frontend separately: cd frontend && npm run dev
```

## API

- `POST /auth/register` — Register (director or viewer)
- `POST /auth/login` — Login
- `POST /videos/upload` — Upload MP4 (director)
- `GET /videos` — List videos (director)
- `POST /sessions` — Start viewing session (viewer)
- `GET /videos/{id}/stream` — Stream video
- `POST /inference/emotion` — Emotion inference from frame (viewer)
- `POST /emotions/sessions/{id}/readings` — Batch emotion readings
- `POST /survey/sessions/{id}` — Submit survey (viewer)
- `GET /analytics/video/{id}` — Get analytics (director)
- `GET /analytics/video/{id}/export` — Export PDF (director)

## Project Structure

```
Hackathon/
├── backend/
│   ├── app/
│   │   ├── routers/     # API routes
│   │   ├── ml/          # Emotion detection pipeline
│   │   ├── models.py
│   │   ├── schemas.py
│   │   └── main.py
│   ├── static/          # HTML, CSS, JS frontend
│   │   ├── index.html
│   │   ├── styles.css
│   │   └── app.js
│   ├── alembic/
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

## Datasets for Fine-Tuning

- **FER2013**: 35k grayscale faces, 7 emotions
- **AffectNet**: 1M+ images, valence-arousal
- **RAVDESS**: Emotional speech (multimodal)

## License

MIT
