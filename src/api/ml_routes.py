"""AI/ML API endpoints — anomaly detection, feedback, capabilities.

Addresses DND Q16: AI/ML Trainability.
"""
from __future__ import annotations

import logging
from typing import Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ml", tags=["AI/ML"])

# In-memory storage for user-defined threshold overrides
_custom_thresholds: Dict[str, float] = {}


class FeedbackRequest(BaseModel):
    entity: str
    assessment_type: str
    verdict: str
    notes: str = ""


class ThresholdOverride(BaseModel):
    z_score_threshold: float | None = None


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
        raise HTTPException(status_code=500, detail="Internal server error")
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
        raise HTTPException(status_code=500, detail="Internal server error")
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
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/capabilities")
async def get_ml_capabilities():
    """Describe the platform's AI/ML capabilities and integration options."""
    from src.analysis.ml_engine import MLCapability
    return MLCapability.get_capabilities()


@router.get("/thresholds")
async def get_thresholds():
    """Return current anomaly detection threshold configuration."""
    from src.analysis.ml_engine import FeedbackEngine

    default_threshold = 1.5
    session = SessionLocal()
    try:
        engine = FeedbackEngine(session)
        stats = engine.get_feedback_stats()

        total = stats.get("total_feedback", 0)
        false_positives = stats.get("false_positives", 0)
        verified = stats.get("verified", 0)
        fp_rate = false_positives / max(false_positives + verified, 1)

        # Adjust threshold upward if false-positive rate is high
        adjusted = default_threshold + (fp_rate * 0.5) if total > 0 else default_threshold

        return {
            "z_score_threshold": _custom_thresholds.get("z_score_threshold", default_threshold),
            "adjusted_threshold": round(adjusted, 3),
            "feedback_count": total,
            "false_positive_rate": round(fp_rate, 3),
            "custom_overrides": dict(_custom_thresholds),
        }
    except Exception as e:
        logger.error("Threshold retrieval failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.post("/thresholds")
async def set_thresholds(override: ThresholdOverride):
    """Set custom threshold overrides for anomaly detection."""
    if override.z_score_threshold is not None:
        _custom_thresholds["z_score_threshold"] = override.z_score_threshold

    return {
        "status": "updated",
        "custom_overrides": dict(_custom_thresholds),
    }
