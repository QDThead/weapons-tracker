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


from fastapi.testclient import TestClient
from src.main import app
from src.api.psi_routes import router as psi_router

# Register PSI routes on app (main.py does this at startup)
if not any(getattr(r, "path", "").startswith("/psi/taxonomy") for r in app.routes):
    app.include_router(psi_router)

client = TestClient(app)


def _seed_taxonomy():
    init_db()
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
    finally:
        session.close()


def test_get_taxonomy():
    _seed_taxonomy()
    resp = client.get("/psi/taxonomy")
    assert resp.status_code == 200
    data = resp.json()
    assert "global_composite" in data
    assert len(data["categories"]) == 13


def test_get_taxonomy_summary():
    _seed_taxonomy()
    resp = client.get("/psi/taxonomy/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["categories"]) == 13
    assert all("icon" in c for c in data["categories"])


def test_get_taxonomy_category():
    _seed_taxonomy()
    resp = client.get("/psi/taxonomy/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["category_id"] == 1
    assert len(data["subcategories"]) == 15


from src.analysis.risk_taxonomy import RiskTaxonomyScorer, TAXONOMY_DEFINITIONS


def test_scorer_seeds_all_subcategories():
    init_db()
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        count = session.query(RiskTaxonomyScore).count()
        assert count == 121
    finally:
        session.close()


def test_scorer_drift_changes_seeded_scores():
    init_db()
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        row = session.query(RiskTaxonomyScore).filter_by(subcategory_key="4a").first()
        baseline = row.baseline_score
        drifted = False
        for _ in range(20):
            scorer.apply_drift_to_seeded()
            session.refresh(row)
            if abs(row.score - baseline) > 0.01:
                drifted = True
                break
        assert drifted, "Drift should change seeded scores"
        assert 0 <= row.score <= 100
    finally:
        session.close()


def test_scorer_compute_category_composites():
    init_db()
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        composites = scorer.compute_category_composites()
        assert len(composites) == 13
        for cat_id, data in composites.items():
            assert 0 <= data["composite_score"] <= 100
            assert data["risk_level"] in ("green", "amber", "red")
            assert data["trend"] in ("rising", "falling", "stable")
    finally:
        session.close()
