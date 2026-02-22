"""Director analytics dashboard endpoints."""
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import User, Video, Session as SessionModel, EmotionReading, SurveyResponse, AggregatedAnalytics
from app.auth import require_director
from app.schemas import AnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

EMOTIONS = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


def compute_alignment_score(model_curve: list, survey_curve: list, intended_curve: list | None) -> float:
    """Compute alignment between model predictions and survey/intended."""
    if not model_curve:
        return 0.0
    # Simple alignment: compare dominant emotions at key timestamps
    scores = []
    for mc in model_curve:
        ts = mc.get("timestamp", 0)
        pred_emotion = mc.get("emotion", "neutral")
        # Find closest survey point
        survey_match = next((s for s in survey_curve if abs(s.get("timestamp", 0) - ts) < 2), None)
        if survey_match and survey_match.get("emotion") == pred_emotion:
            scores.append(1.0)
        elif survey_match:
            scores.append(0.5)  # Partial match
        else:
            scores.append(0.7)  # No survey data, assume moderate
    return sum(scores) / len(scores) * 100 if scores else 0.0


def compute_volatility(readings: list) -> float:
    """Emotional volatility = variance in emotion changes."""
    if len(readings) < 2:
        return 0.0
    changes = []
    prev = readings[0].get("emotion", "neutral")
    for r in readings[1:]:
        curr = r.get("emotion", "neutral")
        changes.append(1.0 if curr != prev else 0.0)
        prev = curr
    return sum(changes) / len(changes) * 100 if changes else 0.0


@router.get("/video/{video_id}", response_model=AnalyticsResponse)
def get_video_analytics(
    video_id: int,
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    video = db.query(Video).filter(Video.id == video_id, Video.director_id == user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    sessions = db.query(SessionModel).filter(SessionModel.video_id == video_id).all()
    all_readings = []
    survey_curves = []

    for s in sessions:
        readings = db.query(EmotionReading).filter(EmotionReading.session_id == s.id).order_by(EmotionReading.timestamp).all()
        for r in readings:
            all_readings.append({"timestamp": r.timestamp, "emotion": r.emotion_label, "probability": r.probability})
        sr = db.query(SurveyResponse).filter(SurveyResponse.session_id == s.id).first()
        if sr:
            survey_curves.append({"timestamp": 0, "emotion": sr.reported_emotion, "intensity": sr.intensity})

    # Aggregate emotion curve by timestamp buckets (1s)
    bucket = defaultdict(list)
    for r in all_readings:
        t = int(r["timestamp"])
        bucket[t].append(r)

    avg_curve = []
    for t in sorted(bucket.keys()):
        items = bucket[t]
        emotion_probs = defaultdict(float)
        for i in items:
            emotion_probs[i["emotion"]] += i["probability"]
        n = len(items)
        for e, p in emotion_probs.items():
            emotion_probs[e] = p / n
        dominant = max(emotion_probs, key=emotion_probs.get)
        avg_curve.append({"timestamp": float(t), "emotion": dominant, "value": emotion_probs[dominant]})

    intended = []
    if video.intended_emotion_curve:
        try:
            intended = json.loads(video.intended_emotion_curve)
        except Exception:
            pass

    alignment = compute_alignment_score(avg_curve, survey_curves, intended)
    volatility = compute_volatility(avg_curve)

    # Peak engagement = timestamps with highest emotion intensity
    peak_ts = sorted(avg_curve, key=lambda x: x["value"], reverse=True)[:5]
    peak_timestamps = [p["timestamp"] for p in peak_ts]

    # AI summary placeholder (will use LLM in ml_service)
    ai_summary = _generate_ai_summary(avg_curve, intended, survey_curves)

    # Model vs survey alignment
    model_vs_survey = None
    if survey_curves and avg_curve:
        model_vs_survey = compute_alignment_score(avg_curve, survey_curves, None)

    return AnalyticsResponse(
        video_id=video_id,
        avg_emotion_curve=avg_curve,
        alignment_score=round(alignment, 2),
        emotional_volatility=round(volatility, 2),
        peak_engagement_timestamps=peak_timestamps,
        ai_summary=ai_summary,
        model_vs_survey_alignment=round(model_vs_survey, 2) if model_vs_survey else None,
    )


def _generate_ai_summary(avg_curve: list, intended: list, survey_curves: list) -> str:
    """Generate narrative AI summary of emotional analytics."""
    if not avg_curve:
        return "No audience emotion data collected yet."
    dominant_emotions = [c["emotion"] for c in avg_curve]
    top_emotion = max(set(dominant_emotions), key=dominant_emotions.count)
    peak = max(avg_curve, key=lambda x: x["value"]) if avg_curve else None
    lines = [
        f"Audience showed predominant {top_emotion} throughout the clip.",
        f"Peak emotional intensity at {peak['timestamp']:.1f}s ({peak['emotion']})." if peak else "",
    ]
    if survey_curves:
        reported = [s["emotion"] for s in survey_curves]
        common = max(set(reported), key=reported.count)
        lines.append(f"Self-reported emotions aligned with {common} as most common.")
    if intended:
        lines.append("Compare with director-intended emotional beats for alignment insights.")
    return " ".join(l for l in lines if l).strip()


@router.get("/video/{video_id}/export")
def export_analytics_pdf(
    video_id: int,
    user: User = Depends(require_director),
    db: Session = Depends(get_db),
):
    """Export analytics as PDF."""
    from fastapi.responses import Response
    analytics = get_video_analytics(video_id, user, db)
    pdf_bytes = _render_pdf(analytics)
    return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=analytics.pdf"})


def _render_pdf(analytics: AnalyticsResponse) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from io import BytesIO
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, f"AffectLens Analytics - Video #{analytics.video_id}")
    c.drawString(100, 730, f"Alignment Score: {analytics.alignment_score}%")
    c.drawString(100, 710, f"Emotional Volatility: {analytics.emotional_volatility}%")
    c.drawString(100, 680, "AI Summary:")
    # Wrap summary text to stay within page
    summary = analytics.ai_summary or "N/A"
    words = summary.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > 70:
            if current:
                lines.append(current)
            current = word
        else:
            current += (" " if current else "") + word
    if current:
        lines.append(current)
    y = 660
    for line in lines:
        c.drawString(100, y, line)
        y -= 15
    c.save()
    buf.seek(0)
    return buf.getvalue()
