"""AI/ML API endpoints — anomaly detection, feedback, capabilities.

Addresses DND Q16: AI/ML Trainability.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["AI/ML"])


class FeedbackRequest(BaseModel):
    entity: str
    assessment_type: str
    verdict: str
    notes: str = ""


@router.get("/anomalies")
async def detect_anomalies():
    """Run anomaly detection on supplier behavior."""
    from src.analysis.ml_engine import AnomalyDetector
    session = SessionLocal()
    try:
        detector = AnomalyDetector(session)
        anomalies = detector.detect_all()
        return {
            "anomalies": anomalies,
            "total": len(anomalies),
            "method": "Statistical z-score analysis on risk score distributions",
        }
    except Exception as e:
        logger.error("Anomaly detection failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """Submit analyst feedback on a risk assessment (RLHF)."""
    from src.analysis.ml_engine import FeedbackEngine
    session = SessionLocal()
    try:
        engine = FeedbackEngine(session)
        result = engine.record_feedback(req.entity, req.assessment_type, req.verdict, req.notes)
        return result
    except Exception as e:
        logger.error("Feedback submission failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/feedback/stats")
async def get_feedback_stats():
    """Get feedback summary for model tuning metrics."""
    from src.analysis.ml_engine import FeedbackEngine
    session = SessionLocal()
    try:
        engine = FeedbackEngine(session)
        return engine.get_feedback_stats()
    except Exception as e:
        logger.error("Feedback stats failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/capabilities")
async def get_ml_capabilities():
    """Describe the platform's AI/ML capabilities and integration options."""
    from src.analysis.ml_engine import MLCapability
    return MLCapability.get_capabilities()
