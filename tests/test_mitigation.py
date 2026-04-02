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
            risk_entity="UpsertTestCorp",
            risk_dimension="single_source_upsert_test",
            risk_score=90.0,
            coa_action="Qualify alternate supplier; estimated qualification time: 90 days",
            coa_priority="critical",
            coa_timeline="90 days",
            coa_responsible="Procurement",
        )
        row = session.query(MitigationAction).filter_by(
            risk_entity="UpsertTestCorp", risk_dimension="single_source_upsert_test"
        ).first()
        assert row is not None
        assert row.status == "open"
        assert row.coa_priority == "critical"

        # Upsert should update existing open action, not duplicate
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="UpsertTestCorp",
            risk_dimension="single_source_upsert_test",
            risk_score=85.0,
            coa_action="Updated action",
            coa_priority="high",
        )
        rows = session.query(MitigationAction).filter_by(
            risk_entity="UpsertTestCorp", risk_dimension="single_source_upsert_test", status="open"
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
            risk_entity="ResolvedTestCo",
            risk_dimension="contract_activity_test",
            risk_score=75.0,
            coa_action="Review",
            coa_priority="high",
        )
        # Mark it resolved
        row = session.query(MitigationAction).filter_by(risk_entity="ResolvedTestCo").first()
        row.status = "resolved"
        session.commit()

        # Upsert should create a NEW open action, not touch the resolved one
        svc.upsert_mitigation_action(
            risk_source="supplier",
            risk_entity="ResolvedTestCo",
            risk_dimension="contract_activity_test",
            risk_score=80.0,
            coa_action="New review",
            coa_priority="critical",
        )
        all_rows = session.query(MitigationAction).filter_by(risk_entity="ResolvedTestCo").all()
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
        # Clean up any leftover actions from prior runs (DB state leak)
        session.query(MitigationAction).filter_by(risk_entity="TestSupplier").delete()
        session.commit()

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


from fastapi.testclient import TestClient
from src.main import app
from src.api.mitigation_routes import router as mitigation_router

if not any(getattr(r, 'path', '').startswith("/mitigation") for r in app.routes):
    app.include_router(mitigation_router)

client = TestClient(app)


def _seed_and_generate():
    init_db()
    session = SessionLocal()
    try:
        from src.storage.models import DefenceSupplier, SupplierSector, OwnershipType, RiskDimension
        svc = PersistenceService(session)
        sup = svc.upsert_supplier(name="TestCorp", sector=SupplierSector.AEROSPACE, ownership_type=OwnershipType.FOREIGN_SUBSIDIARY, parent_country="United States")
        svc.upsert_risk_score(sup.id, RiskDimension.SINGLE_SOURCE, 90.0, "Sole source")
        svc.upsert_risk_score(sup.id, RiskDimension.FOREIGN_OWNERSHIP, 50.0, "US subsidiary")
        from src.analysis.mitigation_playbook import MitigationPlaybook
        pb = MitigationPlaybook(session)
        pb.generate_all_coas()
    finally:
        session.close()


def test_get_actions():
    _seed_and_generate()
    resp = client.get("/mitigation/actions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert "by_priority" in data
    assert "by_status" in data
    # by_status should count ALL statuses
    assert "resolved" in data["by_status"]


def test_patch_action_status():
    _seed_and_generate()
    # Get an action
    resp = client.get("/mitigation/actions")
    actions = resp.json()["actions"]
    assert len(actions) >= 1
    action_id = actions[0]["id"]

    # Update status
    resp = client.patch(f"/mitigation/actions/{action_id}", json={"status": "in_progress", "notes": "Under review"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["notes"] == "Under review"


def test_post_generate():
    _seed_and_generate()
    resp = client.post("/mitigation/generate")
    assert resp.status_code == 200
    assert "generated" in resp.json()
