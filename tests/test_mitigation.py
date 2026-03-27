"""tests/test_mitigation.py"""
from __future__ import annotations

from src.storage.models import MitigationAction
from src.storage.database import init_db, SessionLocal
from src.storage.persistence import PersistenceService
from src.analysis.mitigation_playbook import MitigationPlaybook, PLAYBOOK


def test_mitigation_model_has_columns():
    cols = {c.name for c in MitigationAction.__table__.columns}
    assert "risk_source" in cols
    assert "risk_entity" in cols
    assert "risk_dimension" in cols
    assert "coa_action" in cols
    assert "coa_priority" in cols
    assert "status" in cols
    assert "notes" in cols


def test_upsert_mitigation_action():
    init_db()
    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="Irving Shipbuilding",
            risk_dimension="single_source",
            risk_score=90.0,
            coa_action="Qualify alternate supplier; estimated qualification time: 90 days",
            coa_priority="critical",
            coa_timeline="90 days",
            coa_responsible="Procurement",
        )
        row = session.query(MitigationAction).filter_by(
            risk_entity="Irving Shipbuilding", risk_dimension="single_source"
        ).first()
        assert row is not None
        assert row.status == "open"
        assert row.coa_priority == "critical"

        # Upsert should update existing open action, not duplicate
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="Irving Shipbuilding",
            risk_dimension="single_source",
            risk_score=85.0,
            coa_action="Updated action",
            coa_priority="high",
        )
        rows = session.query(MitigationAction).filter_by(
            risk_entity="Irving Shipbuilding", risk_dimension="single_source", status="open"
        ).all()
        assert len(rows) == 1
        assert rows[0].coa_action == "Updated action"
    finally:
        session.close()


def test_resolved_action_not_reopened():
    init_db()
    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="TestCo",
            risk_dimension="contract_activity",
            risk_score=75.0,
            coa_action="Review",
            coa_priority="high",
        )
        # Mark it resolved
        row = session.query(MitigationAction).filter_by(risk_entity="TestCo").first()
        row.status = "resolved"
        session.commit()

        # Upsert should create a NEW open action, not touch the resolved one
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="TestCo",
            risk_dimension="contract_activity",
            risk_score=80.0,
            coa_action="New review",
            coa_priority="critical",
        )
        all_rows = session.query(MitigationAction).filter_by(risk_entity="TestCo").all()
        assert len(all_rows) == 2
        assert sum(1 for r in all_rows if r.status == "resolved") == 1
        assert sum(1 for r in all_rows if r.status == "open") == 1
    finally:
        session.close()


def test_playbook_has_entries():
    assert len(PLAYBOOK) >= 30


def test_generate_coas_from_supplier_risks():
    init_db()
    session = SessionLocal()
    try:
        # Seed a supplier with risk scores
        from src.storage.models import DefenceSupplier, SupplierRiskScore, SupplierSector, OwnershipType, RiskDimension
        svc = PersistenceService(session)
        sup = svc.upsert_supplier(name="TestSupplier", sector=SupplierSector.SHIPBUILDING, ownership_type=OwnershipType.CANADIAN_PRIVATE)
        svc.upsert_risk_score(sup.id, RiskDimension.SINGLE_SOURCE, 90.0, "Sole shipbuilder")

        playbook = MitigationPlaybook(session)
        result = playbook.generate_all_coas()
        assert result["generated"] > 0

        # Check COA was created
        actions = session.query(MitigationAction).filter_by(risk_entity="TestSupplier").all()
        assert len(actions) >= 1
        assert actions[0].coa_priority in ("critical", "high", "medium", "low")
        assert actions[0].status == "open"
    finally:
        session.close()


def test_generate_coas_from_taxonomy():
    init_db()
    session = SessionLocal()
    try:
        # Seed taxonomy scores (some above threshold)
        from src.analysis.risk_taxonomy import RiskTaxonomyScorer
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()

        playbook = MitigationPlaybook(session)
        result = playbook.generate_all_coas()
        assert result["generated"] > 0

        total = session.query(MitigationAction).count()
        assert total > 5  # Should generate multiple COAs from taxonomy
    finally:
        session.close()
