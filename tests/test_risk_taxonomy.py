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
