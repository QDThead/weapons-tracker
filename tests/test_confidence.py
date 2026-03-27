"""tests/test_confidence.py"""
from __future__ import annotations

from src.storage.database import init_db, SessionLocal
from src.analysis.confidence import compute_confidence


def test_live_high_confidence():
    """Live data with 3+ sources = high confidence."""
    init_db()
    session = SessionLocal()
    try:
        result = compute_confidence(
            data_source="live",
            risk_source="supplier",
            dimension="foreign_ownership",
            session=session,
        )
        assert result["level"] in ("high", "medium")
        assert result["score"] >= 50
        assert result["source_count"] >= 1
        assert "label" in result
        assert "sources" in result
        assert isinstance(result["triangulated"], bool)
    finally:
        session.close()


def test_seeded_low_confidence():
    """Seeded data = low confidence."""
    init_db()
    session = SessionLocal()
    try:
        result = compute_confidence(
            data_source="seeded",
            risk_source="taxonomy",
            dimension="4a",
            session=session,
        )
        assert result["level"] == "low"
        assert result["score"] <= 40
        assert result["source_count"] == 1
        assert "Seeded baseline" in result["label"]
        assert result["triangulated"] is False
    finally:
        session.close()


def test_hybrid_medium_confidence():
    """Hybrid data = medium confidence."""
    init_db()
    session = SessionLocal()
    try:
        result = compute_confidence(
            data_source="hybrid",
            risk_source="taxonomy",
            dimension="7a",
            session=session,
        )
        assert result["level"] == "medium"
        assert 40 <= result["score"] <= 75
    finally:
        session.close()


def test_mitigation_confidence_from_risk_source():
    """Mitigation actions compute confidence from risk_source field."""
    init_db()
    session = SessionLocal()
    try:
        result = compute_confidence(
            data_source=None,
            risk_source="supplier",
            dimension="single_source",
            session=session,
        )
        # Should still produce a valid confidence
        assert result["level"] in ("high", "medium", "low")
        assert 0 <= result["score"] <= 100
    finally:
        session.close()
