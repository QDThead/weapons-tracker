# Canadian Defence Supply Base Exposure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6-dimension risk scoring of Canadian defence suppliers to the Canada Intel tab, sourced from Open Canada procurement disclosure data enriched with Wikidata ownership and SIPRI rankings.

**Architecture:** New SQLAlchemy models for suppliers, contracts, and risk scores. Async procurement scraper fetches from search.open.canada.ca/contracts/. Risk scoring engine computes 6 dimensions per supplier. New FastAPI route file serves 6 endpoints. Canada Intel tab gets a new Defence Supply Base section with risk overview, sector concentration, and ownership exposure charts.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2.0, httpx (async), Chart.js, existing design system

**Spec:** `docs/superpowers/specs/2026-03-25-canada-supplier-exposure-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/storage/models.py` | Modify | Add 3 enums + 3 models (DefenceSupplier, SupplierContract, SupplierRiskScore) |
| `src/storage/persistence.py` | Modify | Add upsert functions for suppliers, contracts, risk scores |
| `src/ingestion/procurement_scraper.py` | Create | Async scraper for Open Canada procurement portal |
| `src/ingestion/corporate_graph.py` | Modify | Add `fetch_company_ownership(name)` method |
| `src/analysis/supplier_risk.py` | Create | 6-dimension risk scoring engine |
| `src/api/supplier_routes.py` | Create | 6 API endpoints for supplier data |
| `src/ingestion/scheduler.py` | Modify | Add 3 weekly cron jobs |
| `src/main.py` | Modify | Register supplier_routes router |
| `src/static/index.html` | Modify | Add Defence Supply Base UI section to Canada Intel tab |
| `tests/test_models_supplier.py` | Create | Tests for new SQLAlchemy models |
| `tests/test_persistence_supplier.py` | Create | Tests for upsert functions |
| `tests/test_procurement_scraper.py` | Create | Tests for scraper pure functions |
| `tests/test_supplier_risk.py` | Create | Tests for risk scoring engine |
| `tests/test_supplier_routes.py` | Create | Tests for all 6 API endpoints |

---

## Task 1: Add SQLAlchemy Models

**Files:**
- Modify: `src/storage/models.py`
- Test: `tests/test_models_supplier.py`

- [ ] **Step 1: Write test that imports new models**

```python
"""tests/test_models_supplier.py"""
from __future__ import annotations

from src.storage.models import (
    SupplierSector, OwnershipType, ContractStatus,
    RiskDimension, DefenceSupplier, SupplierContract, SupplierRiskScore,
)


def test_enums_exist():
    assert SupplierSector.SHIPBUILDING == "shipbuilding"
    assert OwnershipType.FOREIGN_SUBSIDIARY == "foreign_subsidiary"
    assert ContractStatus.ACTIVE == "active"
    assert RiskDimension.FOREIGN_OWNERSHIP == "foreign_ownership"


def test_supplier_model_has_columns():
    cols = {c.name for c in DefenceSupplier.__table__.columns}
    assert "name" in cols
    assert "parent_company" in cols
    assert "risk_score_composite" in cols
    assert "sector" in cols


def test_contract_model_has_columns():
    cols = {c.name for c in SupplierContract.__table__.columns}
    assert "contract_number" in cols
    assert "supplier_id" in cols
    assert "is_sole_source" in cols


def test_risk_score_model_has_columns():
    cols = {c.name for c in SupplierRiskScore.__table__.columns}
    assert "dimension" in cols
    assert "score" in cols
    assert "rationale" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_models_supplier.py -v`
Expected: ImportError — SupplierSector not found

- [ ] **Step 3: Add enums and models to models.py**

Add after the existing PSI models section (after the `SupplyChainAlert` class, near end of file). Follow the existing pattern with `str, Enum` bases, `SQLEnum` columns, `UniqueConstraint`, and `Index`.

```python
# ---------------------------------------------------------------------------
# Defence Supplier Exposure models — Canadian supply base risk scoring
# ---------------------------------------------------------------------------

class SupplierSector(str, Enum):
    """Defence industry sectors for Canadian suppliers."""
    SHIPBUILDING = "shipbuilding"
    LAND_VEHICLES = "land_vehicles"
    AEROSPACE = "aerospace"
    ELECTRONICS = "electronics"
    SIMULATION = "simulation"
    MUNITIONS = "munitions"
    CYBER = "cyber"
    MAINTENANCE = "maintenance"
    SERVICES = "services"
    OTHER = "other"


class OwnershipType(str, Enum):
    """Ownership classification for defence suppliers."""
    CANADIAN_PRIVATE = "canadian_private"
    CANADIAN_PUBLIC = "canadian_public"
    FOREIGN_SUBSIDIARY = "foreign_subsidiary"
    CROWN_CORP = "crown_corp"
    JOINT_VENTURE = "joint_venture"


class ContractStatus(str, Enum):
    """Status of a procurement contract."""
    ACTIVE = "active"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class RiskDimension(str, Enum):
    """Risk scoring dimensions for supplier exposure."""
    FOREIGN_OWNERSHIP = "foreign_ownership"
    CUSTOMER_CONCENTRATION = "customer_concentration"
    SINGLE_SOURCE = "single_source"
    CONTRACT_ACTIVITY = "contract_activity"
    SANCTIONS_PROXIMITY = "sanctions_proximity"
    CONTRACT_PERFORMANCE = "contract_performance"


class DefenceSupplier(Base):
    """A Canadian defence industry supplier."""
    __tablename__ = "defence_suppliers"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    legal_name = Column(String(300))
    headquarters_city = Column(String(100))
    headquarters_province = Column(String(50))
    parent_company = Column(String(200))
    parent_country = Column(String(100))
    ownership_type = Column(SQLEnum(OwnershipType))
    sipri_rank = Column(Integer)
    wikidata_id = Column(String(20))
    sector = Column(SQLEnum(SupplierSector))
    estimated_revenue_cad = Column(Float)
    dnd_contract_revenue_cad = Column(Float)
    employee_count = Column(Integer)
    risk_score_composite = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    contracts = relationship("SupplierContract", back_populates="supplier")
    risk_scores = relationship("SupplierRiskScore", back_populates="supplier")

    __table_args__ = (
        UniqueConstraint("name", name="uq_supplier_name"),
    )

    def __repr__(self):
        return f"<DefenceSupplier(name='{self.name}', sector='{self.sector}')>"


class SupplierContract(Base):
    """A DND/PSPC procurement contract."""
    __tablename__ = "supplier_contracts"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("defence_suppliers.id"), nullable=False)
    contract_number = Column(String(100), nullable=False)
    contract_value_cad = Column(Float)
    description = Column(Text)
    department = Column(String(50))
    award_date = Column(Date)
    end_date = Column(Date)
    status = Column(SQLEnum(ContractStatus))
    sector = Column(SQLEnum(SupplierSector))
    is_sole_source = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("DefenceSupplier", back_populates="contracts")

    __table_args__ = (
        UniqueConstraint("contract_number", name="uq_contract_number"),
        Index("ix_contract_supplier_date", "supplier_id", "award_date"),
    )

    def __repr__(self):
        return f"<SupplierContract(number='{self.contract_number}', supplier={self.supplier_id})>"


class SupplierRiskScore(Base):
    """Per-supplier, per-dimension risk score."""
    __tablename__ = "supplier_risk_scores"

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey("defence_suppliers.id"), nullable=False)
    dimension = Column(SQLEnum(RiskDimension), nullable=False)
    score = Column(Float, nullable=False)
    rationale = Column(Text)
    scored_at = Column(DateTime, default=datetime.utcnow)

    supplier = relationship("DefenceSupplier", back_populates="risk_scores")

    __table_args__ = (
        UniqueConstraint("supplier_id", "dimension", name="uq_score_supplier_dimension"),
        Index("ix_risk_score_supplier", "supplier_id"),
    )

    def __repr__(self):
        return f"<SupplierRiskScore(supplier={self.supplier_id}, dim='{self.dimension}', score={self.score})>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_models_supplier.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/models.py tests/test_models_supplier.py
git commit -m "feat: add DefenceSupplier, SupplierContract, SupplierRiskScore models"
```

---

## Task 2: Add Persistence Upsert Functions

**Files:**
- Modify: `src/storage/persistence.py`
- Test: `tests/test_persistence_supplier.py`

- [ ] **Step 1: Write tests for upsert functions**

```python
"""tests/test_persistence_supplier.py"""
from __future__ import annotations

from datetime import date, datetime

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService


def _fresh_session():
    init_db()
    return SessionLocal()


def test_upsert_supplier_creates_new():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(
            name="Irving Shipbuilding",
            sector=SupplierSector.SHIPBUILDING,
            ownership_type=OwnershipType.CANADIAN_PRIVATE,
        )
        result = session.query(DefenceSupplier).filter_by(name="Irving Shipbuilding").first()
        assert result is not None
        assert result.sector == SupplierSector.SHIPBUILDING
    finally:
        session.close()


def test_upsert_supplier_updates_existing():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="CAE", sector=SupplierSector.SIMULATION)
        svc.upsert_supplier(name="CAE", sector=SupplierSector.SIMULATION, parent_company="Test Parent")
        results = session.query(DefenceSupplier).filter_by(name="CAE").all()
        assert len(results) == 1
        assert results[0].parent_company == "Test Parent"
    finally:
        session.close()


def test_upsert_contract():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="GD Canada", sector=SupplierSector.LAND_VEHICLES)
        supplier = session.query(DefenceSupplier).filter_by(name="GD Canada").first()
        svc.upsert_contract(
            supplier_id=supplier.id,
            contract_number="W8486-12345",
            contract_value_cad=500000000.0,
            department="DND",
            award_date=date(2023, 6, 15),
            sector=SupplierSector.LAND_VEHICLES,
        )
        contract = session.query(SupplierContract).filter_by(contract_number="W8486-12345").first()
        assert contract is not None
        assert contract.contract_value_cad == 500000000.0
    finally:
        session.close()


def test_upsert_risk_score():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="Test Corp", sector=SupplierSector.AEROSPACE)
        supplier = session.query(DefenceSupplier).filter_by(name="Test Corp").first()
        svc.upsert_risk_score(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
            score=50.0,
            rationale="Subsidiary of US company",
        )
        score = session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
        ).first()
        assert score is not None
        assert score.score == 50.0

        # Upsert should update, not duplicate
        svc.upsert_risk_score(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
            score=60.0,
            rationale="Updated",
        )
        scores = session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
        ).all()
        assert len(scores) == 1
        assert scores[0].score == 60.0
    finally:
        session.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_persistence_supplier.py -v`
Expected: AttributeError — PersistenceService has no method `upsert_supplier`

- [ ] **Step 3: Add upsert methods to PersistenceService**

Add to `src/storage/persistence.py`. Import the new models at the top alongside existing imports. Add three new methods to the `PersistenceService` class:

```python
# Add to imports at top of file:
from src.storage.models import (
    # ... existing imports ...
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)

# Add these methods to PersistenceService class:

    def upsert_supplier(self, name: str, sector: SupplierSector | None = None, **kwargs) -> DefenceSupplier:
        """Create or update a defence supplier by name."""
        existing = self.session.query(DefenceSupplier).filter_by(name=name).first()
        if existing:
            if sector:
                existing.sector = sector
            for key, val in kwargs.items():
                if val is not None and hasattr(existing, key):
                    setattr(existing, key, val)
            existing.updated_at = datetime.utcnow()
        else:
            existing = DefenceSupplier(name=name, sector=sector, **kwargs)
            self.session.add(existing)
        self.session.commit()
        return existing

    def upsert_contract(self, supplier_id: int, contract_number: str, **kwargs) -> SupplierContract:
        """Create or update a procurement contract by contract number."""
        existing = self.session.query(SupplierContract).filter_by(contract_number=contract_number).first()
        if existing:
            for key, val in kwargs.items():
                if val is not None and hasattr(existing, key):
                    setattr(existing, key, val)
        else:
            existing = SupplierContract(supplier_id=supplier_id, contract_number=contract_number, **kwargs)
            self.session.add(existing)
        self.session.commit()
        return existing

    def upsert_risk_score(self, supplier_id: int, dimension: RiskDimension, score: float, rationale: str) -> SupplierRiskScore:
        """Create or update a risk score for a supplier+dimension."""
        existing = self.session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier_id, dimension=dimension,
        ).first()
        if existing:
            existing.score = score
            existing.rationale = rationale
            existing.scored_at = datetime.utcnow()
        else:
            existing = SupplierRiskScore(
                supplier_id=supplier_id, dimension=dimension,
                score=score, rationale=rationale,
            )
            self.session.add(existing)
        self.session.commit()
        return existing
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_persistence_supplier.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/persistence.py tests/test_persistence_supplier.py
git commit -m "feat: add upsert functions for suppliers, contracts, and risk scores"
```

---

## Task 3: Build Risk Scoring Engine

**Files:**
- Create: `src/analysis/supplier_risk.py`
- Test: `tests/test_supplier_risk.py`

- [ ] **Step 1: Write tests for each scoring dimension**

```python
"""tests/test_supplier_risk.py"""
from __future__ import annotations

from datetime import date, datetime

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService
from src.analysis.supplier_risk import SupplierRiskScorer


def _setup():
    init_db()
    session = SessionLocal()
    svc = PersistenceService(session)
    return session, svc


def test_foreign_ownership_canadian():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="Irving", sector=SupplierSector.SHIPBUILDING,
            ownership_type=OwnershipType.CANADIAN_PRIVATE,
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_foreign_ownership(supplier)
        assert score == 0
    finally:
        session.close()


def test_foreign_ownership_allied_subsidiary():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="GD Canada", sector=SupplierSector.LAND_VEHICLES,
            ownership_type=OwnershipType.FOREIGN_SUBSIDIARY,
            parent_country="United States",
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_foreign_ownership(supplier)
        assert score == 50
        assert "United States" in rationale
    finally:
        session.close()


def test_single_source_sole_supplier():
    session, svc = _setup()
    try:
        svc.upsert_supplier(name="Irving Solo", sector=SupplierSector.SHIPBUILDING)
        supplier = session.query(DefenceSupplier).filter_by(name="Irving Solo").first()
        # Add an active contract
        svc.upsert_contract(
            supplier_id=supplier.id, contract_number="SOLE-001",
            contract_value_cad=1e9, sector=SupplierSector.SHIPBUILDING,
            status=ContractStatus.ACTIVE, award_date=date(2024, 1, 1),
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_single_source(supplier)
        assert score == 90
        assert "shipbuilding" in rationale.lower()
    finally:
        session.close()


def test_composite_score():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="Test Composite", sector=SupplierSector.AEROSPACE,
            ownership_type=OwnershipType.CANADIAN_PUBLIC,
        )
        svc.upsert_contract(
            supplier_id=supplier.id, contract_number="COMP-001",
            contract_value_cad=5e8, sector=SupplierSector.AEROSPACE,
            status=ContractStatus.ACTIVE, award_date=date(2024, 1, 1),
        )
        scorer = SupplierRiskScorer(session)
        composite = scorer.score_supplier(supplier)
        assert 0 <= composite <= 100
        # Verify scores were persisted
        scores = session.query(SupplierRiskScore).filter_by(supplier_id=supplier.id).all()
        assert len(scores) == 6
    finally:
        session.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_supplier_risk.py -v`
Expected: ModuleNotFoundError — src.analysis.supplier_risk

- [ ] **Step 3: Implement the scoring engine**

Create `src/analysis/supplier_risk.py`:

```python
"""Defence supplier risk scoring engine.

Computes 6-dimension exposure scores for Canadian defence suppliers.
See docs/superpowers/specs/2026-03-25-canada-supplier-exposure-design.md
"""
from __future__ import annotations

import logging
from datetime import datetime, date

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)

logger = logging.getLogger(__name__)

# Countries considered allied for ownership scoring
ALLIED_COUNTRIES = {
    "United States", "United Kingdom", "France", "Germany", "Italy",
    "Australia", "New Zealand", "Japan", "South Korea", "Netherlands",
    "Belgium", "Norway", "Denmark", "Sweden", "Finland", "Poland",
    "Spain", "Portugal", "Czech Republic", "Romania", "Turkey",
}

# Embargoed countries from sanctions.py
EMBARGOED_COUNTRIES = {
    "Russia", "Belarus", "Iran", "North Korea", "Syria", "Myanmar",
    "China", "Venezuela", "Cuba", "Sudan", "South Sudan",
    "Central African Republic", "Democratic Republic of the Congo",
    "Libya", "Somalia", "Yemen", "Iraq",
}

# Dimension weights (must sum to 1.0)
WEIGHTS = {
    RiskDimension.FOREIGN_OWNERSHIP: 0.20,
    RiskDimension.CUSTOMER_CONCENTRATION: 0.15,
    RiskDimension.SINGLE_SOURCE: 0.25,
    RiskDimension.CONTRACT_ACTIVITY: 0.15,
    RiskDimension.SANCTIONS_PROXIMITY: 0.10,
    RiskDimension.CONTRACT_PERFORMANCE: 0.15,
}


class SupplierRiskScorer:
    """Scores Canadian defence suppliers across 6 risk dimensions."""

    def __init__(self, session: Session):
        self.session = session

    def score_foreign_ownership(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on who owns the company and where they are based."""
        otype = supplier.ownership_type
        parent = supplier.parent_company or "unknown"
        country = supplier.parent_country or "unknown"

        if otype in (OwnershipType.CANADIAN_PRIVATE, OwnershipType.CANADIAN_PUBLIC, OwnershipType.CROWN_CORP):
            return 0.0, f"Canadian-owned ({otype.value})"
        if otype == OwnershipType.JOINT_VENTURE:
            if country in ALLIED_COUNTRIES:
                return 30.0, f"Joint venture with {parent} ({country})"
            return 50.0, f"Joint venture with {parent} ({country})"
        if otype == OwnershipType.FOREIGN_SUBSIDIARY:
            if country in EMBARGOED_COUNTRIES:
                return 90.0, f"Subsidiary of {parent} ({country}) — embargoed country"
            if country in ALLIED_COUNTRIES:
                return 50.0, f"Subsidiary of {parent} ({country}) — allied nation"
            return 75.0, f"Subsidiary of {parent} ({country}) — non-allied nation"
        return 65.0, f"Ownership type unknown for {supplier.name}"

    def score_customer_concentration(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on dependency on DND as sole customer."""
        dnd_rev = supplier.dnd_contract_revenue_cad or 0
        total_rev = supplier.estimated_revenue_cad

        if total_rev and total_rev > 0:
            pct = min((dnd_rev / total_rev) * 100, 100)
            level = "critical" if pct > 80 else "moderate" if pct > 50 else "diversified"
            return pct, f"DND revenue is {pct:.0f}% of total ({level} dependency). Based on reported revenue."
        return 65.0, "Revenue data unavailable — conservative estimate. Most DND suppliers are defence-focused."

    def score_single_source(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on whether this is the only supplier in its sector."""
        sector = supplier.sector
        if not sector:
            return 50.0, "Sector unknown — cannot assess competition"

        competitor_count = self.session.query(DefenceSupplier).join(
            SupplierContract
        ).filter(
            DefenceSupplier.sector == sector,
            SupplierContract.status == ContractStatus.ACTIVE,
            DefenceSupplier.id != supplier.id,
        ).distinct().count()

        total = competitor_count + 1
        if total == 1:
            return 90.0, f"Sole supplier in {sector.value} — no alternatives with active DND contracts"
        if total == 2:
            return 60.0, f"One of 2 suppliers in {sector.value} — limited alternatives"
        return 20.0, f"One of {total} suppliers in {sector.value} — adequate competition"

    def score_contract_activity(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on DND contract volume trend (not actual financial health)."""
        now = date.today()
        recent_cutoff = date(now.year - 2, now.month, now.day)
        prior_cutoff = date(now.year - 4, now.month, now.day)

        recent = self.session.query(func.sum(SupplierContract.contract_value_cad)).filter(
            SupplierContract.supplier_id == supplier.id,
            SupplierContract.award_date >= recent_cutoff,
        ).scalar() or 0

        prior = self.session.query(func.sum(SupplierContract.contract_value_cad)).filter(
            SupplierContract.supplier_id == supplier.id,
            SupplierContract.award_date >= prior_cutoff,
            SupplierContract.award_date < recent_cutoff,
        ).scalar() or 0

        if prior == 0 and recent == 0:
            return 90.0, "No contracts in last 4 years — supplier may be inactive"
        if prior == 0:
            return 20.0, f"New supplier — ${recent:,.0f} in recent contracts, no prior baseline"
        change = ((recent - prior) / prior) * 100
        if change >= -10:
            return 20.0, f"Contract activity stable/growing ({change:+.0f}%)"
        if change >= -30:
            return 50.0, f"Contract activity declining ({change:+.0f}%)"
        return 80.0, f"Contract activity sharply declining ({change:+.0f}%)"

    def score_sanctions_proximity(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on ownership ties to sanctioned countries and material dependencies."""
        country = supplier.parent_country

        # Check PSI material dependencies from sanctioned sources
        from src.storage.models import SupplyChainNode, SupplyChainEdge, SupplyChainMaterial
        material_risk = False
        try:
            sanctioned_materials = self.session.query(SupplyChainMaterial).filter(
                SupplyChainMaterial.top_producers.ilike('%Russia%') |
                SupplyChainMaterial.top_producers.ilike('%China%') |
                SupplyChainMaterial.top_producers.ilike('%Iran%')
            ).count()
            if sanctioned_materials > 0:
                material_risk = True
        except Exception:
            pass

        if country and country in EMBARGOED_COUNTRIES:
            return 90.0, f"Parent country {country} is fully embargoed"

        PARTIAL_SANCTIONS = {"China", "Turkey", "India"}
        if country and country in PARTIAL_SANCTIONS:
            return 40.0, f"Parent country {country} has partial sanctions/restrictions"

        if material_risk:
            return 70.0, "Depends on materials sourced from sanctioned countries (PSI cross-reference)"

        if not country:
            return 0.0, "No foreign ownership — no sanctions exposure"
        return 0.0, f"Parent country {country} is not sanctioned"

    def score_contract_performance(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on ratio of terminated contracts."""
        total = self.session.query(SupplierContract).filter_by(supplier_id=supplier.id).count()
        if total == 0:
            return 50.0, "No contract history available"
        terminated = self.session.query(SupplierContract).filter_by(
            supplier_id=supplier.id, status=ContractStatus.TERMINATED,
        ).count()
        ratio = (terminated / total) * 100
        if terminated == 0:
            return 10.0, f"0 terminated out of {total} contracts — clean record"
        if ratio < 10:
            return 30.0, f"{terminated} terminated out of {total} ({ratio:.0f}%) — minor issues"
        if ratio < 25:
            return 60.0, f"{terminated} terminated out of {total} ({ratio:.0f}%) — moderate concerns"
        return 85.0, f"{terminated} terminated out of {total} ({ratio:.0f}%) — serious performance issues"

    def score_supplier(self, supplier: DefenceSupplier) -> float:
        """Compute all 6 dimensions, persist scores, return composite."""
        scorers = {
            RiskDimension.FOREIGN_OWNERSHIP: self.score_foreign_ownership,
            RiskDimension.CUSTOMER_CONCENTRATION: self.score_customer_concentration,
            RiskDimension.SINGLE_SOURCE: self.score_single_source,
            RiskDimension.CONTRACT_ACTIVITY: self.score_contract_activity,
            RiskDimension.SANCTIONS_PROXIMITY: self.score_sanctions_proximity,
            RiskDimension.CONTRACT_PERFORMANCE: self.score_contract_performance,
        }
        composite = 0.0
        for dim, scorer_fn in scorers.items():
            score, rationale = scorer_fn(supplier)
            # Persist
            existing = self.session.query(SupplierRiskScore).filter_by(
                supplier_id=supplier.id, dimension=dim,
            ).first()
            if existing:
                existing.score = score
                existing.rationale = rationale
                existing.scored_at = datetime.utcnow()
            else:
                self.session.add(SupplierRiskScore(
                    supplier_id=supplier.id, dimension=dim,
                    score=score, rationale=rationale,
                ))
            composite += score * WEIGHTS[dim]

        supplier.risk_score_composite = round(composite)
        self.session.commit()
        logger.info("Scored %s: composite=%d", supplier.name, supplier.risk_score_composite)
        return supplier.risk_score_composite

    def score_all_suppliers(self) -> int:
        """Score every supplier in the database. Returns count scored."""
        suppliers = self.session.query(DefenceSupplier).all()
        for s in suppliers:
            self.score_supplier(s)
        return len(suppliers)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_supplier_risk.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/supplier_risk.py tests/test_supplier_risk.py
git commit -m "feat: add 6-dimension supplier risk scoring engine"
```

---

## Task 4: Build Procurement Scraper

**Files:**
- Create: `src/ingestion/procurement_scraper.py`
- Modify: `src/ingestion/corporate_graph.py`

- [ ] **Step 1: Write tests for scraper pure functions**

```python
"""tests/test_procurement_scraper.py"""
from __future__ import annotations

from src.ingestion.procurement_scraper import normalize_vendor_name, classify_sector
from src.storage.models import SupplierSector


def test_normalize_strips_inc():
    assert normalize_vendor_name("Irving Shipbuilding Inc.") == "Irving Shipbuilding"


def test_normalize_strips_ltd():
    assert normalize_vendor_name("CAE Ltd") == "CAE"


def test_normalize_strips_corporation():
    assert normalize_vendor_name("General Dynamics Corporation") == "General Dynamics"


def test_normalize_trims_whitespace():
    assert normalize_vendor_name("  Some Company  Inc  ") == "Some Company"


def test_classify_frigate():
    assert classify_sector("Halifax-class frigate modernization") == SupplierSector.SHIPBUILDING


def test_classify_lav():
    assert classify_sector("LAV 6.0 upgrade package") == SupplierSector.LAND_VEHICLES


def test_classify_aircraft():
    assert classify_sector("CF-18 fighter jet maintenance") == SupplierSector.AEROSPACE


def test_classify_simulation():
    assert classify_sector("Flight simulation training system") == SupplierSector.SIMULATION


def test_classify_unknown():
    assert classify_sector("Office supplies and furniture") == SupplierSector.OTHER
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_procurement_scraper.py -v`
Expected: ModuleNotFoundError — src.ingestion.procurement_scraper

- [ ] **Step 3: Create the procurement scraper**

Create `src/ingestion/procurement_scraper.py`:

```python
"""Open Canada procurement disclosure scraper.

Fetches DND/CAF contracts from search.open.canada.ca/contracts/
and normalizes vendor names for supplier deduplication.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx

from src.storage.models import SupplierSector

logger = logging.getLogger(__name__)

OPEN_CANADA_URL = "https://search.open.canada.ca/opendata/search/contracts"

# Vendor name normalization: strip common suffixes
_STRIP_SUFFIXES = re.compile(
    r"\s*(inc\.?|ltd\.?|ltée?\.?|corp\.?|corporation|company|co\.|"
    r"limited|llc|lp|s\.a\.|gmbh|plc)\s*$",
    re.IGNORECASE,
)
_EXTRA_WHITESPACE = re.compile(r"\s+")

# Sector classification keywords
_SECTOR_KEYWORDS: dict[SupplierSector, list[str]] = {
    SupplierSector.SHIPBUILDING: ["frigate", "ship", "vessel", "naval", "maritime"],
    SupplierSector.LAND_VEHICLES: ["lav", "vehicle", "armoured", "armored", "tank"],
    SupplierSector.AEROSPACE: ["aircraft", "helicopter", "jet", "fighter", "f-35", "cf-18"],
    SupplierSector.ELECTRONICS: ["radar", "sensor", "communications", "radio", "electronic"],
    SupplierSector.SIMULATION: ["simulation", "training", "simulator"],
    SupplierSector.MUNITIONS: ["ammunition", "munition", "explosive", "bomb", "missile"],
    SupplierSector.CYBER: ["cyber", "software", "it ", "network", "data"],
    SupplierSector.MAINTENANCE: ["maintenance", "repair", "overhaul", "mro", "sustainment"],
    SupplierSector.SERVICES: ["consulting", "advisory", "professional", "logistics"],
}


@dataclass
class ProcurementRecord:
    """A parsed procurement contract record."""
    vendor_name: str
    vendor_name_normalized: str
    contract_number: str
    contract_value_cad: float
    description: str
    department: str
    award_date: date | None
    end_date: date | None
    is_sole_source: bool
    sector: SupplierSector


def normalize_vendor_name(name: str) -> str:
    """Normalize a vendor name for deduplication."""
    name = name.strip()
    name = _STRIP_SUFFIXES.sub("", name).strip()
    name = _EXTRA_WHITESPACE.sub(" ", name)
    return name


def classify_sector(description: str) -> SupplierSector:
    """Classify a contract description into a sector."""
    desc_lower = description.lower()
    for sector, keywords in _SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                return sector
    return SupplierSector.OTHER


def _parse_date(s: str | None) -> date | None:
    """Parse a date string from the API."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


class ProcurementScraperClient:
    """Async client for Open Canada procurement disclosure."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_dnd_contracts(
        self,
        start_date: str = "2021-01-01",
        max_records: int = 10000,
    ) -> list[ProcurementRecord]:
        """Fetch National Defence contracts from Open Canada."""
        records: list[ProcurementRecord] = []
        offset = 0
        page_size = 100

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while offset < max_records:
                params = {
                    "search_text": "",
                    "owner_org": "dnd-mdn",
                    "start_row": str(offset),
                    "rows": str(page_size),
                }
                try:
                    resp = await client.get(OPEN_CANADA_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.error("Procurement API error at offset %d: %s", offset, e)
                    break

                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    vendor = item.get("vendor_name", "") or ""
                    if not vendor:
                        continue
                    contract_num = item.get("contract_number", "") or item.get("reference_number", "")
                    if not contract_num:
                        continue

                    description = item.get("description", "") or ""
                    value_str = item.get("contract_value", "0") or "0"
                    try:
                        value = float(str(value_str).replace(",", "").replace("$", ""))
                    except (ValueError, TypeError):
                        value = 0.0

                    solicitation = (item.get("solicitation_procedure", "") or "").lower()
                    is_sole_source = "non-competitive" in solicitation

                    records.append(ProcurementRecord(
                        vendor_name=vendor,
                        vendor_name_normalized=normalize_vendor_name(vendor),
                        contract_number=contract_num,
                        contract_value_cad=value,
                        description=description,
                        department=item.get("owner_org", "DND"),
                        award_date=_parse_date(item.get("contract_date")),
                        end_date=_parse_date(item.get("delivery_date")),
                        is_sole_source=is_sole_source,
                        sector=classify_sector(description),
                    ))

                offset += page_size
                logger.info("Fetched %d contracts so far (offset %d)", len(records), offset)

                # Rate limiting: 1 req/sec
                await asyncio.sleep(1.0)

        logger.info("Total procurement records fetched: %d", len(records))
        return records
```

- [ ] **Step 2: Add `fetch_company_ownership` to corporate_graph.py**

Add this method to the `CorporateGraphClient` class in `src/ingestion/corporate_graph.py`:

```python
    async def fetch_company_ownership(self, company_name: str) -> CorporateEntity | None:
        """Look up a specific company's ownership chain from Wikidata."""
        sparql = f"""
        SELECT ?company ?companyLabel ?parent ?parentLabel ?country ?countryLabel
        WHERE {{
          ?company rdfs:label "{company_name}"@en .
          OPTIONAL {{ ?company wdt:P749 ?parent . }}
          OPTIONAL {{ ?company wdt:P17 ?country . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 1
        """
        headers = {"Accept": "application/sparql-results+json"}
        params = {"query": sparql}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(WIKIDATA_SPARQL_URL, params=params, headers=headers)
                resp.raise_for_status()

            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            if not bindings:
                return None

            b = bindings[0]
            return CorporateEntity(
                name=b.get("companyLabel", {}).get("value", company_name),
                country=b.get("countryLabel", {}).get("value", ""),
                parent_name=b.get("parentLabel", {}).get("value"),
                source="wikidata",
            )
        except Exception as e:
            logger.warning("Wikidata lookup failed for %s: %s", company_name, e)
            return None
```

- [ ] **Step 5: Run scraper tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_procurement_scraper.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/procurement_scraper.py src/ingestion/corporate_graph.py tests/test_procurement_scraper.py
git commit -m "feat: add Open Canada procurement scraper and Wikidata ownership lookup"
```

---

## Task 5: Build API Endpoints

**Files:**
- Create: `src/api/supplier_routes.py`
- Modify: `src/main.py`
- Test: `tests/test_supplier_routes.py`

- [ ] **Step 1: Write route tests**

```python
"""tests/test_supplier_routes.py"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService
from src.api.routes import app
from src.api.supplier_routes import router as supplier_router

# Register supplier routes on app (main.py does this at startup)
app.include_router(supplier_router)


def _seed():
    init_db()
    session = SessionLocal()
    svc = PersistenceService(session)
    s1 = svc.upsert_supplier(
        name="Irving Shipbuilding", sector=SupplierSector.SHIPBUILDING,
        ownership_type=OwnershipType.CANADIAN_PRIVATE,
    )
    s1.risk_score_composite = 72.0
    s2 = svc.upsert_supplier(
        name="GD Land Systems Canada", sector=SupplierSector.LAND_VEHICLES,
        ownership_type=OwnershipType.FOREIGN_SUBSIDIARY,
        parent_company="General Dynamics", parent_country="United States",
    )
    s2.risk_score_composite = 55.0
    svc.upsert_contract(
        supplier_id=s1.id, contract_number="CSC-001",
        contract_value_cad=30e9, sector=SupplierSector.SHIPBUILDING,
        status=ContractStatus.ACTIVE, award_date=date(2023, 1, 1),
    )
    svc.upsert_contract(
        supplier_id=s2.id, contract_number="LAV-001",
        contract_value_cad=5e9, sector=SupplierSector.LAND_VEHICLES,
        status=ContractStatus.ACTIVE, award_date=date(2023, 6, 1),
    )
    svc.upsert_risk_score(s1.id, RiskDimension.SINGLE_SOURCE, 90.0, "Sole shipbuilder")
    svc.upsert_risk_score(s2.id, RiskDimension.FOREIGN_OWNERSHIP, 50.0, "US subsidiary")
    session.commit()
    session.close()


client = TestClient(app)


def test_get_suppliers():
    _seed()
    resp = client.get("/dashboard/suppliers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_suppliers"] >= 2
    names = [s["name"] for s in data["suppliers"]]
    assert "Irving Shipbuilding" in names


def test_get_supplier_profile():
    _seed()
    resp = client.get("/dashboard/suppliers/Irving Shipbuilding/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Irving Shipbuilding"
    assert data["sector"] == "shipbuilding"
    assert len(data["contracts"]) >= 1


def test_get_supplier_profile_not_found():
    _seed()
    resp = client.get("/dashboard/suppliers/NonexistentCorp/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert "error" in data


def test_get_concentration():
    _seed()
    resp = client.get("/dashboard/suppliers/concentration")
    assert resp.status_code == 200
    data = resp.json()
    sectors = {s["sector"] for s in data["sectors"]}
    assert "shipbuilding" in sectors


def test_get_risk_matrix():
    _seed()
    resp = client.get("/dashboard/suppliers/risk-matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) >= 2
    assert all("x" in p and "y" in p for p in data["points"])


def test_get_ownership():
    _seed()
    resp = client.get("/dashboard/suppliers/ownership")
    assert resp.status_code == 200
    data = resp.json()
    assert "breakdown" in data
    assert len(data["foreign_suppliers"]) >= 1
    assert data["foreign_suppliers"][0]["parent_country"] == "United States"


def test_get_alerts():
    _seed()
    resp = client.get("/dashboard/suppliers/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["alerts"]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_supplier_routes.py -v`
Expected: 404 or ImportError — supplier_routes not found

- [ ] **Step 3: Create supplier_routes.py**

Create `src/api/supplier_routes.py`:

```python
"""Canadian Defence Supply Base API endpoints.

Serves supplier risk data, concentration analysis, ownership breakdown,
and exposure alerts for the Canada Intel tab.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter

from src.storage.database import SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, ContractStatus, RiskDimension,
)
from sqlalchemy import func

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Suppliers"])

_cache: dict[str, tuple[float, dict | list]] = {}
_TTL = 3600  # 1 hour


def _check_cache(key: str) -> dict | list | None:
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _TTL:
        return cached[1]
    return None


def _set_cache(key: str, data: dict | list) -> None:
    _cache[key] = (time.time(), data)


def _risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "red"
    if score >= 40:
        return "amber"
    return "green"


@router.get("/suppliers")
async def get_suppliers():
    cached = _check_cache("suppliers")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.query(DefenceSupplier).all()
        suppliers.sort(key=lambda s: s.risk_score_composite or 0, reverse=True)

        result = {
            "suppliers": [],
            "total_suppliers": len(suppliers),
            "avg_risk_score": 0,
        }
        total_score = 0
        scored_count = 0

        for s in suppliers:
            # Get top risk dimension
            top_risk = session.query(SupplierRiskScore).filter_by(
                supplier_id=s.id
            ).order_by(SupplierRiskScore.score.desc()).first()

            active_contracts = session.query(SupplierContract).filter_by(
                supplier_id=s.id, status=ContractStatus.ACTIVE,
            ).count()

            total_value = session.query(func.sum(SupplierContract.contract_value_cad)).filter_by(
                supplier_id=s.id,
            ).scalar() or 0

            result["suppliers"].append({
                "name": s.name,
                "sector": s.sector.value if s.sector else "other",
                "ownership_type": s.ownership_type.value if s.ownership_type else "unknown",
                "parent_company": s.parent_company,
                "parent_country": s.parent_country,
                "contract_value_total_cad": total_value,
                "active_contracts": active_contracts,
                "risk_score_composite": s.risk_score_composite,
                "risk_level": _risk_level(s.risk_score_composite),
                "top_risk_dimension": top_risk.dimension.value if top_risk else None,
            })

            if s.risk_score_composite is not None:
                total_score += s.risk_score_composite
                scored_count += 1

        result["avg_risk_score"] = round(total_score / scored_count) if scored_count else 0
        _set_cache("suppliers", result)
        return result
    finally:
        session.close()


@router.get("/suppliers/concentration")
async def get_concentration():
    cached = _check_cache("suppliers_concentration")
    if cached:
        return cached

    session = SessionLocal()
    try:
        sectors = []
        for sector in SupplierSector:
            suppliers_in_sector = session.query(DefenceSupplier).join(
                SupplierContract
            ).filter(
                DefenceSupplier.sector == sector,
                SupplierContract.status == ContractStatus.ACTIVE,
            ).distinct().all()

            if not suppliers_in_sector:
                continue

            total_value = session.query(func.sum(SupplierContract.contract_value_cad)).join(
                DefenceSupplier
            ).filter(
                DefenceSupplier.sector == sector,
            ).scalar() or 0

            sole_supplier = suppliers_in_sector[0].name if len(suppliers_in_sector) == 1 else None

            sectors.append({
                "sector": sector.value,
                "supplier_count": len(suppliers_in_sector),
                "is_sole_source": len(suppliers_in_sector) == 1,
                "sole_supplier": sole_supplier,
                "total_contract_value_cad": total_value,
                "suppliers": [s.name for s in suppliers_in_sector],
            })

        result = {"sectors": sorted(sectors, key=lambda x: x["supplier_count"])}
        _set_cache("suppliers_concentration", result)
        return result
    finally:
        session.close()


@router.get("/suppliers/risk-matrix")
async def get_risk_matrix():
    cached = _check_cache("suppliers_risk_matrix")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.query(DefenceSupplier).all()
        points = []
        for s in suppliers:
            total_value = session.query(func.sum(SupplierContract.contract_value_cad)).filter_by(
                supplier_id=s.id,
            ).scalar() or 0
            points.append({
                "name": s.name,
                "x": total_value,
                "y": s.risk_score_composite or 0,
                "sector": s.sector.value if s.sector else "other",
                "risk_level": _risk_level(s.risk_score_composite),
            })
        result = {"points": points}
        _set_cache("suppliers_risk_matrix", result)
        return result
    finally:
        session.close()


@router.get("/suppliers/ownership")
async def get_ownership():
    cached = _check_cache("suppliers_ownership")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.query(DefenceSupplier).all()
        breakdown = {}
        foreign_list = []

        for s in suppliers:
            otype = s.ownership_type.value if s.ownership_type else "unknown"
            if otype not in breakdown:
                breakdown[otype] = {"count": 0, "total_contract_value_cad": 0}
            breakdown[otype]["count"] += 1
            total_value = session.query(func.sum(SupplierContract.contract_value_cad)).filter_by(
                supplier_id=s.id,
            ).scalar() or 0
            breakdown[otype]["total_contract_value_cad"] += total_value

            if s.ownership_type and s.ownership_type.value == "foreign_subsidiary":
                foreign_list.append({
                    "name": s.name,
                    "parent_company": s.parent_company,
                    "parent_country": s.parent_country,
                    "contract_value_cad": total_value,
                })

        result = {"breakdown": breakdown, "foreign_suppliers": foreign_list}
        _set_cache("suppliers_ownership", result)
        return result
    finally:
        session.close()


@router.get("/suppliers/alerts")
async def get_alerts():
    cached = _check_cache("suppliers_alerts")
    if cached:
        return cached

    session = SessionLocal()
    try:
        high_scores = session.query(SupplierRiskScore).filter(
            SupplierRiskScore.score > 70,
        ).order_by(SupplierRiskScore.score.desc()).all()

        alerts = []
        for rs in high_scores:
            supplier = session.get(DefenceSupplier, rs.supplier_id)
            alerts.append({
                "supplier": supplier.name if supplier else "Unknown",
                "dimension": rs.dimension.value,
                "score": rs.score,
                "rationale": rs.rationale,
                "severity": "critical" if rs.score > 85 else "warning",
            })

        result = {"alerts": alerts, "total": len(alerts)}
        _set_cache("suppliers_alerts", result)
        return result
    finally:
        session.close()


@router.get("/suppliers/{name}/profile")
async def get_supplier_profile(name: str):
    session = SessionLocal()
    try:
        supplier = session.query(DefenceSupplier).filter_by(name=name).first()
        if not supplier:
            return {"error": f"Supplier '{name}' not found"}

        contracts = session.query(SupplierContract).filter_by(
            supplier_id=supplier.id,
        ).order_by(SupplierContract.award_date.desc()).all()

        scores = session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier.id,
        ).all()

        return {
            "name": supplier.name,
            "legal_name": supplier.legal_name,
            "sector": supplier.sector.value if supplier.sector else None,
            "ownership_type": supplier.ownership_type.value if supplier.ownership_type else None,
            "parent_company": supplier.parent_company,
            "parent_country": supplier.parent_country,
            "sipri_rank": supplier.sipri_rank,
            "estimated_revenue_cad": supplier.estimated_revenue_cad,
            "dnd_contract_revenue_cad": supplier.dnd_contract_revenue_cad,
            "risk_score_composite": supplier.risk_score_composite,
            "risk_level": _risk_level(supplier.risk_score_composite),
            "risk_dimensions": [
                {"dimension": s.dimension.value, "score": s.score, "rationale": s.rationale}
                for s in scores
            ],
            "contracts": [
                {
                    "contract_number": c.contract_number,
                    "value_cad": c.contract_value_cad,
                    "description": c.description,
                    "department": c.department,
                    "award_date": c.award_date.isoformat() if c.award_date else None,
                    "status": c.status.value if c.status else None,
                    "sector": c.sector.value if c.sector else None,
                    "is_sole_source": c.is_sole_source,
                }
                for c in contracts
            ],
            "total_contracts": len(contracts),
        }
    finally:
        session.close()
```

- [ ] **Step 4: Register routes in main.py**

Add to `src/main.py` imports:

```python
from src.api.supplier_routes import router as supplier_router
```

Add after the existing `app.include_router(psi_router)` line:

```python
app.include_router(supplier_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_supplier_routes.py -v`
Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/supplier_routes.py src/main.py tests/test_supplier_routes.py
git commit -m "feat: add 6 supplier API endpoints and register routes"
```

---

## Task 6: Add Scheduler Jobs

**Files:**
- Modify: `src/ingestion/scheduler.py`

- [ ] **Step 1: Add procurement ingestion job**

Add imports at top of `src/ingestion/scheduler.py`:

```python
from src.analysis.supplier_risk import SupplierRiskScorer
```

Add three new async functions (following the existing pattern of `ingest_gdelt_news`, `ingest_military_flights`):

```python
async def ingest_procurement():
    """Fetch and store DND procurement contracts from Open Canada."""
    try:
        from src.ingestion.procurement_scraper import ProcurementScraperClient
        client = ProcurementScraperClient()
        records = await client.fetch_dnd_contracts()

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            for rec in records:
                supplier = svc.upsert_supplier(
                    name=rec.vendor_name_normalized,
                    sector=rec.sector,
                )
                svc.upsert_contract(
                    supplier_id=supplier.id,
                    contract_number=rec.contract_number,
                    contract_value_cad=rec.contract_value_cad,
                    description=rec.description,
                    department=rec.department,
                    award_date=rec.award_date,
                    end_date=rec.end_date,
                    is_sole_source=rec.is_sole_source,
                    sector=rec.sector,
                    status=ContractStatus.ACTIVE if not rec.end_date or rec.end_date >= date.today() else ContractStatus.COMPLETED,
                )
            logger.info("[scheduler] Procurement: stored %d contracts", len(records))
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] Procurement ingestion failed: %s", e)


async def enrich_suppliers():
    """Enrich supplier records with Wikidata ownership data."""
    try:
        from src.ingestion.corporate_graph import CorporateGraphClient
        corp_client = CorporateGraphClient()

        session = SessionLocal()
        try:
            suppliers = session.query(DefenceSupplier).filter(
                DefenceSupplier.parent_company.is_(None)
            ).all()
            enriched = 0
            for s in suppliers:
                entity = await corp_client.fetch_company_ownership(s.name)
                if entity and entity.parent_name:
                    s.parent_company = entity.parent_name
                    s.parent_country = entity.country
                    s.ownership_type = OwnershipType.FOREIGN_SUBSIDIARY if entity.country and entity.country != "Canada" else s.ownership_type
                    enriched += 1
            session.commit()
            logger.info("[scheduler] Enriched %d suppliers with ownership data", enriched)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] Supplier enrichment failed: %s", e)


async def score_suppliers():
    """Compute risk scores for all defence suppliers."""
    try:
        session = SessionLocal()
        try:
            scorer = SupplierRiskScorer(session)
            count = scorer.score_all_suppliers()
            logger.info("[scheduler] Scored %d suppliers", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] Supplier scoring failed: %s", e)
```

Add the additional imports needed at top:

```python
from datetime import date
from src.storage.models import DefenceSupplier, OwnershipType, ContractStatus
```

- [ ] **Step 2: Register jobs in `create_scheduler()`**

Add these three jobs inside the existing `create_scheduler()` function, after the existing PSI job:

```python
    scheduler.add_job(
        ingest_procurement,
        CronTrigger(day_of_week="sun", hour=2),
        id="procurement_scraper",
        name="DND procurement scraper",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        enrich_suppliers,
        CronTrigger(day_of_week="sun", hour=3),
        id="supplier_enrichment",
        name="Supplier ownership enrichment",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        score_suppliers,
        CronTrigger(day_of_week="sun", hour=5),
        id="supplier_scoring",
        name="Supplier risk scoring",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 3: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat: add weekly procurement scraper, enrichment, and scoring jobs"
```

---

## Task 7: Build Dashboard UI — Defence Supply Base Section

**Files:**
- Modify: `src/static/index.html`

This is the largest task. Add the Defence Supply Base section to the Canada Intel tab.

- [ ] **Step 1: Add HTML structure after Sections 5/6 grid**

Find the closing `</div>` of the grid-2 that wraps Sections 5 and 6 in the Canada Intel tab (the `<div class="grid grid-2">` containing "Canada's Supply Chain" and "Shifting Alliances"). Add the new section right after that closing `</div>`, before the closing `</div>` of `page-canada-intel`.

Add the following HTML:

```html
    <!-- Section 7: Defence Supply Base -->
    <div style="margin-top:20px;">
      <h2 style="font-family:var(--font-display);font-size:18px;font-weight:600;margin-bottom:16px;color:var(--text);">
        Defence Supply Base Exposure
      </h2>

      <!-- Alerts -->
      <div id="ca-supplier-alerts" style="margin-bottom:16px;"></div>

      <!-- KPI row -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;" id="ca-supplier-kpis">
        <div class="stat-box">
          <div class="stat-label">Total Suppliers</div>
          <div class="stat-num" style="font-size:28px;color:var(--accent);" id="ca-sup-total">-</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Foreign-Controlled</div>
          <div class="stat-num" style="font-size:28px;color:var(--accent4);" id="ca-sup-foreign-pct">-</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Sole-Source Sectors</div>
          <div class="stat-num" style="font-size:28px;color:var(--accent2);" id="ca-sup-sole">-</div>
        </div>
        <div class="stat-box">
          <div class="stat-label">Avg Risk Score</div>
          <div class="stat-num" style="font-size:28px;" id="ca-sup-avg-risk">-</div>
        </div>
      </div>

      <!-- Risk overview chart -->
      <div class="card" style="margin-bottom:20px;">
        <h2>Supplier Risk Ranking</h2>
        <div class="chart-container tall" style="height:400px;"><canvas id="ca-supplier-risk-chart"></canvas></div>
      </div>

      <!-- Sector + Ownership side by side -->
      <div class="grid grid-2">
        <div class="card">
          <h2>Sector Concentration</h2>
          <div class="chart-container tall"><canvas id="ca-sector-chart"></canvas></div>
          <div id="ca-sole-source-list" style="margin-top:12px;"></div>
        </div>
        <div class="card">
          <h2>Ownership Exposure</h2>
          <div class="chart-container" style="height:250px;"><canvas id="ca-ownership-chart"></canvas></div>
          <div id="ca-foreign-list" style="margin-top:12px;max-height:200px;overflow-y:auto;"></div>
        </div>
      </div>
    </div>
```

- [ ] **Step 2: Add JavaScript to load and render supplier data**

Add a new function block in the `<script>` section (before the closing `</script>` tag), after the existing Canada Intel functions:

```javascript
// ═══════ DEFENCE SUPPLY BASE (Canada Intel Section 7) ═══════

let supplierRiskChart = null, sectorChart = null, ownershipChart = null;

async function loadSupplierData() {
  try {
    const [supRes, concRes, ownRes, alertRes] = await Promise.all([
      fetch('/dashboard/suppliers').then(r => r.json()),
      fetch('/dashboard/suppliers/concentration').then(r => r.json()),
      fetch('/dashboard/suppliers/ownership').then(r => r.json()),
      fetch('/dashboard/suppliers/alerts').then(r => r.json()),
    ]);
    renderSupplierKPIs(supRes, concRes);
    renderSupplierAlerts(alertRes);
    renderSupplierRiskChart(supRes);
    renderSectorChart(concRes);
    renderOwnershipChart(ownRes);
  } catch (e) {
    console.error('Failed to load supplier data:', e);
  }
}

function renderSupplierKPIs(data, concentration) {
  document.getElementById('ca-sup-total').textContent = data.total_suppliers;
  const foreign = data.suppliers.filter(s => s.ownership_type === 'foreign_subsidiary').length;
  const pct = data.total_suppliers > 0 ? Math.round((foreign / data.total_suppliers) * 100) : 0;
  document.getElementById('ca-sup-foreign-pct').textContent = pct + '%';
  const soleCount = concentration.sectors.filter(s => s.is_sole_source).length;
  document.getElementById('ca-sup-sole').textContent = soleCount;
  const avgEl = document.getElementById('ca-sup-avg-risk');
  avgEl.textContent = data.avg_risk_score;
  avgEl.style.color = data.avg_risk_score >= 70 ? 'var(--accent2)' : data.avg_risk_score >= 40 ? 'var(--accent4)' : 'var(--accent3)';
}

function renderSupplierAlerts(data) {
  const el = document.getElementById('ca-supplier-alerts');
  if (!data.alerts || data.alerts.length === 0) { el.innerHTML = ''; return; }
  el.innerHTML = data.alerts.slice(0, 5).map(a => `
    <div class="insight-alert ${a.severity === 'critical' ? 'threat' : 'warning'}">
      <div class="alert-title">${esc(a.supplier)} — ${a.dimension.replace(/_/g, ' ')}</div>
      <div class="alert-detail">${esc(a.rationale)} (score: ${a.score})</div>
    </div>
  `).join('');
}

function renderSupplierRiskChart(data) {
  const ctx = document.getElementById('ca-supplier-risk-chart');
  if (!ctx) return;
  if (supplierRiskChart) supplierRiskChart.destroy();
  const sorted = [...data.suppliers].sort((a, b) => (b.risk_score_composite || 0) - (a.risk_score_composite || 0));
  supplierRiskChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(s => s.name),
      datasets: [{
        data: sorted.map(s => s.risk_score_composite || 0),
        backgroundColor: sorted.map(s => {
          const sc = s.risk_score_composite || 0;
          return sc >= 70 ? '#ef444488' : sc >= 40 ? '#f59e0b88' : '#10b98188';
        }),
        borderColor: sorted.map(s => {
          const sc = s.risk_score_composite || 0;
          return sc >= 70 ? '#ef4444' : sc >= 40 ? '#f59e0b' : '#10b981';
        }),
        borderWidth: 1,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { max: 100, title: { display: true, text: 'Risk Score', color: '#64748b' }, grid: { color: 'rgba(0,212,255,0.08)' } },
        y: { grid: { display: false } },
      },
    },
  });
}

function renderSectorChart(data) {
  const ctx = document.getElementById('ca-sector-chart');
  if (!ctx) return;
  if (sectorChart) sectorChart.destroy();
  const sectors = data.sectors;
  sectorChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sectors.map(s => s.sector),
      datasets: [{
        label: 'Suppliers',
        data: sectors.map(s => s.supplier_count),
        backgroundColor: sectors.map(s => s.is_sole_source ? '#ef444488' : '#00d4ff88'),
        borderColor: sectors.map(s => s.is_sole_source ? '#ef4444' : '#00d4ff'),
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        annotation: {
          annotations: Object.fromEntries(
            sectors.filter(s => s.is_sole_source).map((s, i) => [
              `sole${i}`, { type: 'label', xValue: s.sector, yValue: s.supplier_count + 0.3,
                content: 'SOLE SOURCE', color: '#ef4444', font: { size: 9, weight: 'bold' } }
            ])
          ),
        },
      },
      scales: {
        y: { beginAtZero: true, ticks: { stepSize: 1 }, grid: { color: 'rgba(0,212,255,0.08)' } },
        x: { grid: { display: false } },
      },
    },
  });

  // Sole source list
  const listEl = document.getElementById('ca-sole-source-list');
  const soles = sectors.filter(s => s.is_sole_source);
  if (soles.length > 0) {
    listEl.innerHTML = '<div style="font-size:12px;color:var(--text-dim);margin-bottom:6px;">Sole-source suppliers:</div>' +
      soles.map(s => `<div class="ins-card-item" style="display:flex;justify-content:space-between;">
        <span style="font-weight:600;color:var(--accent2);">${esc(s.sole_supplier)}</span>
        <span class="tiv">$${(s.total_contract_value_cad / 1e9).toFixed(1)}B</span>
      </div>`).join('');
  }
}

function renderOwnershipChart(data) {
  const ctx = document.getElementById('ca-ownership-chart');
  if (!ctx) return;
  if (ownershipChart) ownershipChart.destroy();
  const labels = Object.keys(data.breakdown).map(k => k.replace(/_/g, ' '));
  const values = Object.values(data.breakdown).map(v => v.count);
  const colors = ['#00d4ff', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'];
  ownershipChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels, datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length), borderWidth: 0 }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: 'right', labels: { color: '#e2e8f0', font: { family: "'IBM Plex Sans'" } } } },
    },
  });

  // Foreign supplier list
  const listEl = document.getElementById('ca-foreign-list');
  if (data.foreign_suppliers.length > 0) {
    listEl.innerHTML = data.foreign_suppliers.map(f => `
      <div class="ins-card-item" style="display:flex;justify-content:space-between;">
        <div><span style="font-weight:600;">${esc(f.name)}</span>
          <span style="font-size:11px;color:var(--text-dim);"> — ${esc(f.parent_company || '')} (${esc(f.parent_country || '')})</span></div>
        <span class="tiv">$${(f.contract_value_cad / 1e6).toFixed(0)}M</span>
      </div>
    `).join('');
  }
}
```

- [ ] **Step 3: Call `loadSupplierData()` when Canada Intel tab loads**

Find the existing function that loads Canada Intel data (search for `loadCanadaIntel` or the nav tab click handler that activates `page-canada-intel`). Add `loadSupplierData();` at the end of that function so it loads alongside the existing Canada Intel data.

- [ ] **Step 4: Verify in browser**

Run: Open http://localhost:8000, navigate to the Canada Intel tab, scroll to bottom.
Expected: Defence Supply Base section visible with KPI boxes, charts, and alerts (data may be empty until procurement scraper runs).

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add Defence Supply Base UI section to Canada Intel tab"
```

---

## Task 8: Integration Test — End to End

- [ ] **Step 1: Run all tests**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Start server and verify**

Run: `cd /Users/billdennis/weapons-tracker && source venv/bin/activate && python -m src.main`

Verify:
- http://localhost:8000/docs shows new `/dashboard/suppliers*` endpoints
- http://localhost:8000/dashboard/suppliers returns JSON (may be empty)
- Canada Intel tab has Defence Supply Base section at bottom

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: Canadian Defence Supply Base Exposure module — complete"
```
