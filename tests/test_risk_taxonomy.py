"""tests/test_risk_taxonomy.py"""
from __future__ import annotations

from src.storage.models import RiskTaxonomyScore


def test_taxonomy_model_has_columns():
    cols = {c.name for c in RiskTaxonomyScore.__table__.columns}
    assert "category_id" in cols
    assert "subcategory_key" in cols
    assert "score" in cols
    assert "baseline_score" in cols
    assert "data_source" in cols
    assert "psi_module" in cols
    assert "rationale" in cols
    assert "last_event" in cols
    assert "scored_at" in cols


from datetime import datetime
from src.storage.database import init_db, SessionLocal
from src.storage.persistence import PersistenceService


def test_upsert_taxonomy_score():
    init_db()
    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        svc.upsert_taxonomy_score(
            category_id=1,
            category_name="FOCI",
            subcategory_key="1a",
            subcategory_name="Theft of trade secrets",
            score=42.0,
            baseline_score=40.0,
            data_source="live",
            psi_module="Legal & Reputational Monitor",
            rationale="Test rationale",
        )
        row = session.query(RiskTaxonomyScore).filter_by(subcategory_key="1a").first()
        assert row is not None
        assert row.score == 42.0

        # Upsert should update, not duplicate
        svc.upsert_taxonomy_score(
            category_id=1,
            category_name="FOCI",
            subcategory_key="1a",
            subcategory_name="Theft of trade secrets",
            score=55.0,
            baseline_score=40.0,
            data_source="live",
        )
        rows = session.query(RiskTaxonomyScore).filter_by(subcategory_key="1a").all()
        assert len(rows) == 1
        assert rows[0].score == 55.0
    finally:
        session.close()


def test_seed_definitions_complete():
    from src.analysis.risk_taxonomy import TAXONOMY_DEFINITIONS
    assert len(TAXONOMY_DEFINITIONS) == 13
    total = sum(len(cat["subcategories"]) for cat in TAXONOMY_DEFINITIONS.values())
    assert total == 121
    for cat_id, cat in TAXONOMY_DEFINITIONS.items():
        assert "data_source" in cat, f"Category {cat_id} missing data_source"
        for sub in cat["subcategories"]:
            assert "key" in sub
            assert "name" in sub
            assert "baseline_score" in sub
            assert "data_source" in sub
            assert "psi_module" in sub
