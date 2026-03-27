# COA/Mitigation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add automated Course of Action recommendations with a lightweight action tracker, addressing DND Q13 (Decision Support & Mitigation) — the "Decide/Act" phases of the OODA loop.

**Architecture:** New `MitigationAction` model stores COA recommendations. A `MitigationPlaybook` engine maps ~40 risk patterns to deterministic actions with priority/timeline/responsible party. Three API endpoints serve actions, update status, and trigger generation. UI shows an Action Centre on Insights plus inline COAs on alert cards.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2.0, Chart.js, existing design system

**Spec:** `docs/superpowers/specs/2026-03-27-coa-mitigation-engine-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/storage/models.py` | Modify | Add `MitigationAction` model |
| `src/storage/persistence.py` | Modify | Add `upsert_mitigation_action` method |
| `src/analysis/mitigation_playbook.py` | Create | Playbook definitions (~40 COA mappings) + generation engine |
| `src/api/mitigation_routes.py` | Create | 3 endpoints (GET, PATCH, POST) |
| `src/ingestion/scheduler.py` | Modify | Call COA generation at tail of `score_taxonomy()` |
| `src/main.py` | Modify | Register mitigation_routes router |
| `src/static/index.html` | Modify | Action Centre on Insights + inline COAs |
| `tests/test_mitigation.py` | Create | Tests for model, playbook, endpoints |

---

### Task 1: Add MitigationAction Model + Persistence

**Files:**
- Modify: `src/storage/models.py` (append after RiskTaxonomyScore)
- Modify: `src/storage/persistence.py`
- Create: `tests/test_mitigation.py`

- [ ] **Step 1: Write tests**

```python
"""tests/test_mitigation.py"""
from __future__ import annotations

from src.storage.models import MitigationAction
from src.storage.database import init_db, SessionLocal
from src.storage.persistence import PersistenceService


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_mitigation.py -v`
Expected: ImportError

- [ ] **Step 3: Add model to models.py**

Append after `RiskTaxonomyScore` class (end of file):

```python
class MitigationAction(Base):
    """A Course of Action recommendation for a detected risk."""
    __tablename__ = "mitigation_actions"

    id = Column(Integer, primary_key=True)
    risk_source = Column(String(50), nullable=False)
    risk_entity = Column(String(500), nullable=False)
    risk_dimension = Column(String(100), nullable=False)
    risk_score = Column(Float, nullable=False)
    coa_action = Column(Text, nullable=False)
    coa_priority = Column(String(10), nullable=False)
    coa_timeline = Column(String(50))
    coa_responsible = Column(String(100))
    status = Column(String(15), nullable=False, default="open")
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_mitigation_status", "status"),
    )

    def __repr__(self):
        return f"<MitigationAction(entity='{self.risk_entity}', priority='{self.coa_priority}', status='{self.status}')>"
```

Note: No UniqueConstraint on the table itself — upsert logic in Python handles the "find existing open action for same risk triple" pattern, allowing resolved rows to coexist with new open ones.

- [ ] **Step 4: Add upsert to persistence.py**

Add `MitigationAction` to the imports at top. Add method:

```python
    def upsert_mitigation_action(self, risk_source: str, risk_entity: str, risk_dimension: str, **kwargs) -> MitigationAction:
        """Create or update a mitigation action. Skips resolved actions (creates new instead)."""
        existing = self.session.query(MitigationAction).filter_by(
            risk_source=risk_source,
            risk_entity=risk_entity,
            risk_dimension=risk_dimension,
        ).filter(MitigationAction.status != "resolved").first()

        if existing:
            for key, val in kwargs.items():
                if val is not None and hasattr(existing, key):
                    setattr(existing, key, val)
            existing.updated_at = datetime.utcnow()
        else:
            existing = MitigationAction(
                risk_source=risk_source,
                risk_entity=risk_entity,
                risk_dimension=risk_dimension,
                **kwargs,
            )
            self.session.add(existing)
        self.session.commit()
        return existing
```

- [ ] **Step 5: Run tests, verify all pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_mitigation.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add src/storage/models.py src/storage/persistence.py tests/test_mitigation.py
git commit -m "feat: add MitigationAction model and persistence upsert

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Build Playbook Engine

**Files:**
- Create: `src/analysis/mitigation_playbook.py`

- [ ] **Step 1: Add playbook tests to `tests/test_mitigation.py`**

```python
from src.analysis.mitigation_playbook import MitigationPlaybook, PLAYBOOK


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
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Create `src/analysis/mitigation_playbook.py`**

This file contains the full PLAYBOOK dict and the `MitigationPlaybook` class. Read the complete implementation from the plan below. Must start with `from __future__ import annotations`.

```python
"""Mitigation Playbook — Rule-based COA recommendations for detected risks.

Maps risk patterns to deterministic Course of Action recommendations.
Addresses DND Q13: Decision Support & Mitigation Capabilities.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from src.storage.models import (
    MitigationAction, SupplierRiskScore, RiskTaxonomyScore,
    SupplyChainAlert, DefenceSupplier, RiskDimension,
)

logger = logging.getLogger(__name__)

# Priority map for sorting
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# ── Playbook: (risk_source, dimension_pattern) → COA template ──
# Each entry: action text, timeline, responsible party
PLAYBOOK: dict[tuple[str, str], dict] = {
    # Supplier risks
    ("supplier", "foreign_ownership"): {
        "action": "Initiate National Security Review; suspend new PO issuance pending FOCI assessment",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("supplier", "customer_concentration"): {
        "action": "Engage supplier on revenue diversification plan; assess business continuity risk",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("supplier", "single_source"): {
        "action": "Qualify alternate supplier; estimated qualification time: 90 days. Initiate dual-source program",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("supplier", "contract_activity"): {
        "action": "Engage supplier for business continuity review; activate safety stock if available",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("supplier", "sanctions_proximity"): {
        "action": "Conduct sanctions compliance audit; review sub-tier material sourcing for restricted origins",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("supplier", "contract_performance"): {
        "action": "Issue corrective action request (CAR); increase inspection frequency; review contract terms",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    # Taxonomy — FOCI (category 1)
    ("taxonomy", "1a"): {"action": "Investigate IP litigation; assess trade secret exposure for DND programs", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "1b"): {"action": "Request supplier cyber posture assessment; brief CCCS on threat activity", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1c"): {"action": "Initiate UBO (Ultimate Beneficial Ownership) review; flag for FOCI assessment", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "1d"): {"action": "Monitor M&A activity; prepare FOCI impact assessment if acquisition proceeds", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1e"): {"action": "Investigate shell company structure; escalate to CI if confirmed", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1h"): {"action": "Trace material provenance to origin; verify no sanctioned-country sourcing", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "1k"): {"action": "Escalate to Canadian Intelligence Command; initiate enhanced screening", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Political (category 2)
    ("taxonomy", "2b"): {"action": "Assess impact on logistics corridors; identify alternate trade routes", "timeline": "30 days", "responsible": "DSCRO"},
    ("taxonomy", "2c"): {"action": "Activate conflict supply chain contingency; assess inventory buffer adequacy", "timeline": "Immediate", "responsible": "DSCRO"},
    ("taxonomy", "2d"): {"action": "Monitor tariff developments; model cost impact on active contracts", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "2e"): {"action": "Cross-reference updated sanctions list; flag affected suppliers and routes", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Manufacturing (category 3)
    ("taxonomy", "3a"): {"action": "Initiate dual-source qualification program; document sole-source justification", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3b"): {"action": "Purchase safety stock from secondary supplier; monitor commodity market", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "3d"): {"action": "Map geographic concentration; identify alternative regions for sourcing", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3f"): {"action": "Qualify alternate supplier; estimated qualification time: 90 days", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3j"): {"action": "Initiate DMSMS review; identify form-fit-function replacements", "timeline": "90 days", "responsible": "Program Office"},
    ("taxonomy", "3l"): {"action": "Review production schedules with supplier; assess impact on delivery milestones", "timeline": "30 days", "responsible": "Program Office"},
    ("taxonomy", "3p"): {"action": "Trace raw material sources; ensure no sanctioned-origin materials in supply chain", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "3s"): {"action": "Pre-order critical components; negotiate priority allocation with supplier", "timeline": "Immediate", "responsible": "Procurement"},
    # Taxonomy — Cyber (category 4)
    ("taxonomy", "4a"): {"action": "Request supplier network security assessment; review data handling procedures", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "4c"): {"action": "Brief CCCS on intrusion indicators; assess data exposure scope", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4e"): {"action": "Request incident report from supplier; assess DND data exposure; review contract terms", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4f"): {"action": "Activate cyber incident response plan; assess operational impact", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4j"): {"action": "Assess CVE applicability to DND systems; coordinate patch deployment", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Transport (category 7)
    ("taxonomy", "7a"): {"action": "Activate alternate shipping route; pre-position safety stock at secondary depot", "timeline": "Immediate", "responsible": "DSCRO"},
    ("taxonomy", "7c"): {"action": "Issue delivery performance improvement notice; escalate if no improvement in 30 days", "timeline": "30 days", "responsible": "Program Office"},
    # Taxonomy — Compliance (category 10)
    ("taxonomy", "10h"): {"action": "Initiate conflict mineral trace; verify 3TG (tin, tantalum, tungsten, gold) sourcing", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "10j"): {"action": "Review export control classification; ensure ITAR/EAR compliance", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Financial (category 12)
    ("taxonomy", "12b"): {"action": "Purchase safety stock from secondary supplier to cover 6-month gap; monitor Z-Score", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "12d"): {"action": "Assess supplier revenue concentration; develop business continuity plan", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "12e"): {"action": "Review cost baseline; negotiate revised contract terms if overrun exceeds 10%", "timeline": "30 days", "responsible": "Program Office"},
    # PSI alerts
    ("psi", "chokepoint_blocked"): {"action": "Divert shipments to alternate port; assess transit time impact", "timeline": "Immediate", "responsible": "DSCRO"},
    ("psi", "material_shortage"): {"action": "Purchase safety stock from secondary supplier to cover 6-month gap", "timeline": "30 days", "responsible": "Procurement"},
    ("psi", "sanctions_risk"): {"action": "Initiate supply chain re-sourcing; flag affected NSNs for review", "timeline": "Immediate", "responsible": "Security"},
    ("psi", "concentration_risk"): {"action": "Identify alternate sources across different geographies; begin qualification", "timeline": "90 days", "responsible": "Procurement"},
    ("psi", "supplier_disruption"): {"action": "Activate business continuity plan; contact secondary suppliers", "timeline": "Immediate", "responsible": "DSCRO"},
    ("psi", "demand_surge"): {"action": "Negotiate priority allocation with suppliers; assess production capacity", "timeline": "30 days", "responsible": "Procurement"},
}


def _compute_priority(score: float) -> str:
    if score >= 85: return "critical"
    if score >= 70: return "high"
    if score >= 50: return "medium"
    return "low"


class MitigationPlaybook:
    """Generates COA recommendations from risk scores using the playbook."""

    def __init__(self, session: Session):
        self.session = session

    def _upsert_action(self, risk_source: str, risk_entity: str, risk_dimension: str,
                        risk_score: float, coa: dict, priority: str) -> bool:
        """Upsert a single COA. Returns True if new/updated, False if skipped."""
        existing = self.session.query(MitigationAction).filter_by(
            risk_source=risk_source,
            risk_entity=risk_entity,
            risk_dimension=risk_dimension,
        ).filter(MitigationAction.status != "resolved").first()

        if existing:
            existing.risk_score = risk_score
            existing.coa_action = coa["action"]
            existing.coa_priority = priority
            existing.coa_timeline = coa.get("timeline")
            existing.coa_responsible = coa.get("responsible")
            existing.updated_at = datetime.utcnow()
            return True
        else:
            self.session.add(MitigationAction(
                risk_source=risk_source,
                risk_entity=risk_entity,
                risk_dimension=risk_dimension,
                risk_score=risk_score,
                coa_action=coa["action"],
                coa_priority=priority,
                coa_timeline=coa.get("timeline"),
                coa_responsible=coa.get("responsible"),
                status="open",
            ))
            return True

    def generate_all_coas(self) -> dict:
        """Generate COAs from all risk sources. Returns counts."""
        generated = 0
        updated = 0
        skipped = 0

        # 1. Supplier risk scores
        supplier_risks = self.session.query(SupplierRiskScore).filter(
            SupplierRiskScore.score > 50,
        ).all()
        for rs in supplier_risks:
            supplier = self.session.get(DefenceSupplier, rs.supplier_id)
            if not supplier:
                continue
            dim_value = rs.dimension.value  # Convert SQLEnum to string
            key = ("supplier", dim_value)
            coa = PLAYBOOK.get(key)
            if not coa and rs.score > 70:
                coa = {"action": f"Review {dim_value.replace('_', ' ')} risk for {supplier.name}; determine appropriate mitigation", "timeline": "30 days", "responsible": "DSCRO"}
            if coa:
                priority = _compute_priority(rs.score)
                is_new = self._upsert_action("supplier", supplier.name, dim_value, rs.score, coa, priority)
                if is_new:
                    generated += 1

        # 2. Taxonomy scores
        taxonomy_risks = self.session.query(RiskTaxonomyScore).filter(
            RiskTaxonomyScore.score > 50,
        ).all()
        for ts in taxonomy_risks:
            key = ("taxonomy", ts.subcategory_key)
            coa = PLAYBOOK.get(key)
            if not coa and ts.score > 70:
                coa = {"action": f"Review {ts.subcategory_name} risk; determine appropriate mitigation", "timeline": "30 days", "responsible": "DSCRO"}
            if coa:
                priority = _compute_priority(ts.score)
                entity = f"[{ts.subcategory_key}] {ts.subcategory_name}"
                is_new = self._upsert_action("taxonomy", entity, ts.subcategory_key, ts.score, coa, priority)
                if is_new:
                    generated += 1

        # 3. PSI alerts
        psi_alerts = self.session.query(SupplyChainAlert).filter(
            SupplyChainAlert.is_active == True,
        ).all()
        for alert in psi_alerts:
            alert_type = alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(alert.alert_type)
            key = ("psi", alert_type)
            coa = PLAYBOOK.get(key)
            if not coa:
                coa = {"action": f"Assess impact of {alert_type.replace('_', ' ')}; coordinate response", "timeline": "30 days", "responsible": "DSCRO"}
            severity_score = {"critical": 95, "high": 80, "medium": 60, "low": 40}.get(str(alert.severity), 60)
            priority = _compute_priority(severity_score)
            is_new = self._upsert_action("psi", alert.title or alert_type, alert_type, severity_score, coa, priority)
            if is_new:
                generated += 1

        self.session.commit()
        logger.info("COA generation: %d generated/updated, %d skipped", generated, skipped)
        return {"generated": generated, "updated": updated, "skipped_resolved": skipped}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_mitigation.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/mitigation_playbook.py tests/test_mitigation.py
git commit -m "feat: add COA playbook engine with ~40 risk-to-action mappings

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Add API Endpoints

**Files:**
- Create: `src/api/mitigation_routes.py`
- Modify: `src/main.py`

- [ ] **Step 1: Add endpoint tests to `tests/test_mitigation.py`**

```python
from fastapi.testclient import TestClient
from src.api.routes import app
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
```

- [ ] **Step 2: Run tests to verify they fail (404)**

- [ ] **Step 3: Create `src/api/mitigation_routes.py`**

```python
"""Mitigation Action Centre API endpoints.

Serves COA recommendations, tracks action status,
and triggers on-demand COA generation.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.storage.database import SessionLocal
from src.storage.models import MitigationAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mitigation", tags=["Mitigation"])

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 300  # 5 minutes

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _check_cache(key: str) -> dict | None:
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _TTL:
        return cached[1]
    return None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = (time.time(), data)


def _clear_cache():
    _cache.clear()


class StatusUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("/actions")
async def get_actions(
    status: str = Query(None, description="Filter: open, in_progress, resolved, or all"),
    priority: str = Query(None, description="Filter: critical, high, medium, low"),
    source: str = Query(None, description="Filter: supplier, taxonomy, psi"),
):
    """All mitigation actions with summary stats."""
    cache_key = f"actions:{status}:{priority}:{source}"
    cached = _check_cache(cache_key)
    if cached:
        return cached

    session = SessionLocal()
    try:
        # Always count ALL statuses for badges
        all_actions = session.query(MitigationAction).all()
        by_status = {"open": 0, "in_progress": 0, "resolved": 0}
        by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in all_actions:
            by_status[a.status] = by_status.get(a.status, 0) + 1
            if a.status != "resolved":
                by_priority[a.coa_priority] = by_priority.get(a.coa_priority, 0) + 1

        # Filter for the action list
        query = session.query(MitigationAction)
        if status and status != "all":
            query = query.filter(MitigationAction.status == status)
        elif not status:
            query = query.filter(MitigationAction.status.in_(["open", "in_progress"]))
        if priority:
            query = query.filter(MitigationAction.coa_priority == priority)
        if source:
            query = query.filter(MitigationAction.risk_source == source)

        actions = query.all()
        # Sort by priority in Python
        actions.sort(key=lambda a: PRIORITY_ORDER.get(a.coa_priority, 9))

        result = {
            "actions": [
                {
                    "id": a.id,
                    "risk_source": a.risk_source,
                    "risk_entity": a.risk_entity,
                    "risk_dimension": a.risk_dimension,
                    "risk_score": a.risk_score,
                    "coa_action": a.coa_action,
                    "coa_priority": a.coa_priority,
                    "coa_timeline": a.coa_timeline,
                    "coa_responsible": a.coa_responsible,
                    "status": a.status,
                    "notes": a.notes,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                }
                for a in actions
            ],
            "total": len(actions),
            "by_priority": by_priority,
            "by_status": by_status,
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_actions failed: %s", e)
        return {"actions": [], "total": 0, "by_priority": {}, "by_status": {}, "error": str(e)}
    finally:
        session.close()


@router.patch("/actions/{action_id}")
async def update_action(action_id: int, update: StatusUpdate):
    """Update action status and/or notes."""
    session = SessionLocal()
    try:
        action = session.get(MitigationAction, action_id)
        if not action:
            return {"error": f"Action {action_id} not found"}
        if update.status:
            action.status = update.status
        if update.notes is not None:
            action.notes = update.notes
        action.updated_at = __import__("datetime").datetime.utcnow()
        session.commit()
        _clear_cache()
        return {
            "id": action.id,
            "status": action.status,
            "notes": action.notes,
            "updated_at": action.updated_at.isoformat(),
        }
    except Exception as e:
        logger.error("update_action failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/generate")
async def generate_coas():
    """Trigger on-demand COA generation from current risk scores."""
    from src.analysis.mitigation_playbook import MitigationPlaybook
    session = SessionLocal()
    try:
        playbook = MitigationPlaybook(session)
        result = playbook.generate_all_coas()
        _clear_cache()
        return result
    except Exception as e:
        logger.error("generate_coas failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()
```

- [ ] **Step 4: Register in main.py**

Add import: `from src.api.mitigation_routes import router as mitigation_router`
Add: `app.include_router(mitigation_router)` after the supplier_router line.

- [ ] **Step 5: Run tests, verify all pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_mitigation.py -v`
Expected: All 8 PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/mitigation_routes.py src/main.py tests/test_mitigation.py
git commit -m "feat: add 3 mitigation API endpoints (GET, PATCH, POST)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add Scheduler Integration

**Files:**
- Modify: `src/ingestion/scheduler.py`

- [ ] **Step 1: Add COA generation to `score_taxonomy()` function**

In `src/ingestion/scheduler.py`, find the `score_taxonomy()` function. After `scorer.score_all()` (line ~218), add:

```python
            # Generate COA recommendations from updated scores
            from src.analysis.mitigation_playbook import MitigationPlaybook
            playbook = MitigationPlaybook(session)
            coa_result = playbook.generate_all_coas()
            logger.info("[scheduler] COA generation: %s", coa_result)
```

This goes INSIDE the existing try/session block, right after the taxonomy scoring line.

- [ ] **Step 2: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat: add COA generation to taxonomy scoring cycle

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Build Action Centre UI (Insights Tab)

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add HTML for Action Centre**

In the Insights page, find the taxonomy strip (`id="taxonomy-strip"`). Insert the Action Centre HTML AFTER the taxonomy strip, BEFORE Section 1 (Situation Report):

```html
    <!-- Action Centre -->
    <div id="action-centre" style="margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <h2 style="font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text);margin:0;">Action Centre</h2>
          <span class="stat-box" style="padding:2px 10px;background:rgba(239,68,68,0.15);border-color:var(--accent2);">
            <span class="stat-num" style="font-size:14px;color:var(--accent2);" id="ac-open-count">0</span>
            <span style="font-size:9px;color:var(--accent2);margin-left:4px;">OPEN</span>
          </span>
          <span class="stat-box" style="padding:2px 10px;background:rgba(245,158,11,0.15);border-color:var(--accent4);">
            <span class="stat-num" style="font-size:14px;color:var(--accent4);" id="ac-progress-count">0</span>
            <span style="font-size:9px;color:var(--accent4);margin-left:4px;">IN PROGRESS</span>
          </span>
          <span class="stat-box" style="padding:2px 10px;background:rgba(16,185,129,0.15);border-color:var(--accent3);">
            <span class="stat-num" style="font-size:14px;color:var(--accent3);" id="ac-resolved-count">0</span>
            <span style="font-size:9px;color:var(--accent3);margin-left:4px;">RESOLVED</span>
          </span>
        </div>
        <button class="btn-primary" style="padding:5px 14px;font-size:12px;" onclick="generateCOAs()">Generate COAs</button>
      </div>
      <div id="action-centre-list"></div>
    </div>
```

- [ ] **Step 2: Add JavaScript**

```javascript
// ═══════ ACTION CENTRE (Insights page) ═══════

let _mitigationCache = null;

async function loadActionCentre() {
  try {
    const data = await fetch('/mitigation/actions').then(r => r.json());
    _mitigationCache = data;

    document.getElementById('ac-open-count').textContent = data.by_status.open || 0;
    document.getElementById('ac-progress-count').textContent = data.by_status.in_progress || 0;
    document.getElementById('ac-resolved-count').textContent = data.by_status.resolved || 0;

    const priorityColors = {critical:'var(--accent2)',high:'var(--accent4)',medium:'#eab308',low:'var(--accent3)'};
    const el = document.getElementById('action-centre-list');

    if (!data.actions || data.actions.length === 0) {
      el.innerHTML = '<div style="color:var(--text-dim);font-size:13px;padding:12px;">No active actions. Click "Generate COAs" to analyze current risks.</div>';
      return;
    }

    el.innerHTML = data.actions.slice(0, 10).map(a => {
      const color = priorityColors[a.coa_priority] || 'var(--text-dim)';
      return `<div class="insight-alert" style="border-left-color:${color};padding:12px 16px;margin-bottom:6px;">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
              <span style="background:${color};color:#fff;padding:1px 8px;border-radius:4px;font-size:10px;font-weight:600;text-transform:uppercase;">${a.coa_priority}</span>
              <span style="font-weight:600;font-size:13px;">${esc(a.risk_entity)}</span>
              <span style="font-size:11px;color:var(--text-dim);">${a.risk_dimension.replace(/_/g,' ')}</span>
            </div>
            <div style="font-size:12px;color:var(--text);line-height:1.4;">${esc(a.coa_action)}</div>
            <div style="font-size:11px;color:var(--text-dim);margin-top:4px;">
              ${a.coa_responsible ? '<span style="background:rgba(0,212,255,0.1);color:var(--accent);padding:1px 6px;border-radius:3px;font-size:10px;">' + esc(a.coa_responsible) + '</span>' : ''}
              ${a.coa_timeline ? ' · ' + esc(a.coa_timeline) : ''}
            </div>
          </div>
          <select onchange="updateActionStatus(${a.id}, this.value)" style="background:var(--bg);border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;font-size:11px;font-family:var(--font-body);">
            <option value="open" ${a.status==='open'?'selected':''}>Open</option>
            <option value="in_progress" ${a.status==='in_progress'?'selected':''}>In Progress</option>
            <option value="resolved" ${a.status==='resolved'?'selected':''}>Resolved</option>
          </select>
        </div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error('Failed to load Action Centre:', e);
  }
}

async function updateActionStatus(id, newStatus) {
  try {
    await fetch('/mitigation/actions/' + id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: newStatus}),
    });
    loadActionCentre();
  } catch (e) {
    console.error('Failed to update action:', e);
  }
}

async function generateCOAs() {
  try {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = 'Generating...';
    const result = await fetch('/mitigation/generate', {method: 'POST'}).then(r => r.json());
    btn.textContent = 'Generate COAs';
    btn.disabled = false;
    loadActionCentre();
  } catch (e) {
    console.error('Failed to generate COAs:', e);
  }
}
```

- [ ] **Step 3: Hook into Insights load**

Add `loadActionCentre();` at the end of `loadInsights()` (alongside `loadTaxonomyStrip()`).

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add Action Centre to Insights tab with status tracking

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Add Inline COAs on Alert Cards

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add inline COA rendering to supplier alerts**

Find the `renderSupplierAlerts` function. After the alert HTML is built, add COA matching:

Modify the alert template to include a COA line. After the `alert-detail` div, add:

```javascript
// Inside renderSupplierAlerts, after building alert HTML
// Add COA lookup from _mitigationCache
function getInlineCOA(entity, source) {
  if (!_mitigationCache || !_mitigationCache.actions) return '';
  const match = _mitigationCache.actions.find(a => a.risk_entity === entity && a.risk_source === source);
  if (!match) return '';
  const color = {critical:'var(--accent2)',high:'var(--accent4)',medium:'#eab308',low:'var(--accent3)'}[match.coa_priority] || 'var(--text-dim)';
  return `<div style="margin-top:6px;padding:6px 10px;background:rgba(0,212,255,0.04);border-radius:4px;font-size:11px;border-left:2px solid ${color};">
    <span style="color:${color};font-weight:600;">⚡ Recommended:</span> ${esc(match.coa_action)}
    ${match.coa_timeline ? ' <span style="color:var(--text-dim);">· ' + esc(match.coa_timeline) + '</span>' : ''}
  </div>`;
}
```

Add `getInlineCOA` as a global function. Then in `renderSupplierAlerts`, append `${getInlineCOA(a.supplier, 'supplier')}` to each alert card.

Similarly in `renderPsiAlerts` (in the PSI Overview section), append `${getInlineCOA(a.title || a.alert_type, 'psi')}`.

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add inline COA recommendations on supplier and PSI alert cards

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Integration Test

- [ ] **Step 1: Run all tests**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/ -v`
Expected: All tests PASS (~45 tests)

- [ ] **Step 2: Trigger COA generation and verify**

```bash
curl -s -X POST http://localhost:8000/mitigation/generate | python3 -m json.tool
curl -s http://localhost:8000/mitigation/actions | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Actions: {d[\"total\"]}, Open: {d[\"by_status\"][\"open\"]}, Critical: {d[\"by_priority\"].get(\"critical\",0)}')"
```

- [ ] **Step 3: Test status update**

```bash
curl -s -X PATCH http://localhost:8000/mitigation/actions/1 -H "Content-Type: application/json" -d '{"status":"in_progress","notes":"Under review"}' | python3 -m json.tool
```

- [ ] **Step 4: Verify UI**

Open http://localhost:8000 — Insights tab should show Action Centre with COAs. Status dropdowns should work.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: COA/Mitigation Engine — complete OODA Decide/Act implementation

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
