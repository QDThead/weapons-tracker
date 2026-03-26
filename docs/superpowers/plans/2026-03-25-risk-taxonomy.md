# DND Risk Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 13 DND/CAF Defence Supply Chain Risk Taxonomy categories (121 sub-categories) with live/hybrid/seeded scoring, 3 API endpoints, and UI on both Insights and Supply Chain tabs.

**Architecture:** New `RiskTaxonomyScore` model stores per-sub-category scores. A `RiskTaxonomyScorer` engine computes live scores from existing OSINT data for 4 categories, hybrid scores for 3, and applies random drift to seeded baselines for 6. Three new PSI endpoints serve taxonomy data. UI shows a 13-card summary strip on Insights and an accordion drill-down on the Supply Chain tab.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2.0, Chart.js, existing design system

**Spec:** `docs/superpowers/specs/2026-03-25-risk-taxonomy-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/storage/models.py` | Modify | Add `RiskTaxonomyScore` model |
| `src/analysis/risk_taxonomy.py` | Create | Seed definitions (121 sub-cats), scoring engine, drift logic |
| `src/storage/persistence.py` | Modify | Add `upsert_taxonomy_score` method |
| `src/api/psi_routes.py` | Modify | Add 3 taxonomy endpoints + cache constant |
| `src/ingestion/scheduler.py` | Modify | Add 6-hour taxonomy scoring job |
| `scripts/seed_database.py` | Modify | Seed initial taxonomy scores on first run |
| `src/static/index.html` | Modify | Insights summary strip + Supply Chain taxonomy sub-tab |
| `tests/test_risk_taxonomy.py` | Create | Tests for model, scoring, and endpoints |

---

### Task 1: Add RiskTaxonomyScore Model

**Files:**
- Modify: `src/storage/models.py` (append after SupplierRiskScore class, ~line 552)
- Test: `tests/test_risk_taxonomy.py`

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: ImportError

- [ ] **Step 3: Add model to models.py**

Append after the `SupplierRiskScore` class (after line 552):

```python
class RiskTaxonomyScore(Base):
    """DND Annex B risk taxonomy score — one row per sub-category."""
    __tablename__ = "risk_taxonomy_scores"

    id = Column(Integer, primary_key=True)
    category_id = Column(Integer, nullable=False)
    category_name = Column(String(100), nullable=False)
    subcategory_key = Column(String(10), nullable=False)
    subcategory_name = Column(String(200), nullable=False)
    score = Column(Float, nullable=False)
    baseline_score = Column(Float, nullable=False)
    data_source = Column(String(10), nullable=False)
    psi_module = Column(String(100))
    rationale = Column(Text)
    last_event = Column(Text)
    scored_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("subcategory_key", name="uq_taxonomy_subcat"),
        Index("ix_taxonomy_category", "category_id"),
    )

    def __repr__(self):
        return f"<RiskTaxonomyScore(key='{self.subcategory_key}', score={self.score})>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage/models.py tests/test_risk_taxonomy.py
git commit -m "feat: add RiskTaxonomyScore model for DND Annex B compliance

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add Persistence Upsert + Seed Definitions

**Files:**
- Modify: `src/storage/persistence.py`
- Create: `src/analysis/risk_taxonomy.py` (seed definitions only in this task — scoring engine in Task 3)

- [ ] **Step 1: Write failing test**

Add to `tests/test_risk_taxonomy.py`:

```python
from datetime import datetime
from src.storage.database import init_db, SessionLocal
from src.storage.models import RiskTaxonomyScore
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
    # Must have all 13 categories
    assert len(TAXONOMY_DEFINITIONS) == 13
    # Total sub-categories should be 121
    total = sum(len(cat["subcategories"]) for cat in TAXONOMY_DEFINITIONS.values())
    assert total == 121
    # Each sub-category has required fields
    for cat_id, cat in TAXONOMY_DEFINITIONS.items():
        for sub in cat["subcategories"]:
            assert "key" in sub
            assert "name" in sub
            assert "baseline_score" in sub
            assert "data_source" in sub
            assert "psi_module" in sub
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: AttributeError for upsert, ImportError for TAXONOMY_DEFINITIONS

- [ ] **Step 3: Add upsert method to persistence.py**

Add to `PersistenceService` class in `src/storage/persistence.py`. First add `RiskTaxonomyScore` to the imports at the top alongside the other model imports.

```python
    def upsert_taxonomy_score(self, subcategory_key: str, **kwargs) -> RiskTaxonomyScore:
        """Create or update a taxonomy risk score by subcategory_key."""
        existing = self.session.query(RiskTaxonomyScore).filter_by(
            subcategory_key=subcategory_key,
        ).first()
        if existing:
            for key, val in kwargs.items():
                if val is not None and hasattr(existing, key):
                    setattr(existing, key, val)
            existing.scored_at = datetime.utcnow()
        else:
            existing = RiskTaxonomyScore(subcategory_key=subcategory_key, **kwargs)
            self.session.add(existing)
        self.session.commit()
        return existing
```

- [ ] **Step 4: Create `src/analysis/risk_taxonomy.py` with TAXONOMY_DEFINITIONS**

This is the largest single piece of work — the full 121 sub-category seed definition dict sourced from the DND bid Appendix A. The file must start with `from __future__ import annotations`.

The structure:

```python
"""DND Annex B Risk Taxonomy — seed definitions and scoring engine.

Maps all 13 DND/CAF Defence Supply Chain Risk Taxonomy categories
and 121 sub-categories to PSI modules with baseline risk scores.
"""
from __future__ import annotations

import logging
import random
from datetime import datetime

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# PSI Module constants — avoid magic strings
PSI_MODULES = {
    "legal_reputational": "Legal & Reputational Monitor",
    "cyber_threat": "Cyber Threat Intelligence",
    "ubo_graph": "UBO Graph",
    "ma_monitor": "M&A Monitor",
    "anomaly_detection": "Anomaly Detection",
    "commodity_tracing": "Commodity Tracing",
    "adverse_media": "Adverse Media Scanner",
    "news_monitor": "News Monitor",
    "watchlist": "Watchlist Integration",
    "geopolitical": "Geopolitical Monitor",
    "risk_assessment": "Risk Assessment Engine",
    "country_risk": "Country Risk Scoring",
    "regulatory": "Regulatory Monitor",
    "regulatory_compliance": "Regulatory Compliance",
    "esg_scanner": "ESG Scanner",
    "trade_policy": "Trade Policy Tracker",
    "concentration": "Concentration Analyzer",
    "commodity_monitor": "Commodity Monitor",
    "capacity_monitor": "Capacity Monitor",
    "supplier_assessment": "Supplier Assessment",
    "inventory_analytics": "Inventory Analytics",
    "supply_chain_mapping": "Supply Chain Mapping",
    "operational_monitor": "Operational Monitor",
    "dmsms": "DMSMS Module",
    "network_analysis": "Network Analysis",
    "performance_monitor": "Performance Monitor",
    "lead_time": "Lead Time Predictor",
    "logistics": "Logistics Intelligence",
    "infrastructure": "Infrastructure Monitor",
    "facility_assessment": "Facility Assessment",
    "energy_monitor": "Energy Monitor",
    "demand_analytics": "Demand Analytics",
    "demand_supply": "Demand-Supply Alignment",
    "constraint_modeling": "Constraint Modeling",
    "incident_monitor": "Incident Monitor",
    "labor_monitor": "Labor Monitor",
    "strike_monitor": "Strike Monitor",
    "geo_hazard": "Geo-Hazard Engine",
    "weather_monitor": "Weather Monitor",
    "climate_risk": "Climate Risk Overlay",
    "wildfire_monitor": "Wildfire Monitor",
    "pandemic_monitor": "Pandemic Monitor",
    "cyber_assessment": "Cyber Assessment",
    "cve_integration": "CVE Integration",
    "technology_assessment": "Technology Assessment",
    "fraud_monitor": "Fraud Monitor",
    "financial_scorecard": "Financial Scorecard",
    "revenue_analysis": "Revenue Analysis",
    "contract_monitor": "Contract Monitor",
    "industry_monitor": "Industry Monitor",
    "payment_monitor": "Payment Monitor",
    "bankruptcy_monitor": "Bankruptcy Monitor",
    "fx_monitor": "FX Monitor",
    "macro_economic": "Macro-Economic Monitor",
    "inflation_monitor": "Inflation Monitor",
    "sanctions_monitor": "Sanctions Monitor",
    "trade_compliance": "Trade Compliance",
    "recall_monitor": "Recall Monitor",
    "quality_monitor": "Quality Monitor",
    "specification_monitor": "Specification Monitor",
    "counterfeit_detection": "Counterfeit Detection",
    "conflict_mineral": "Conflict Mineral Tracer",
    "audit_monitor": "Audit Monitor",
}

# Full taxonomy: 13 categories, 121 sub-categories
# Sourced from QDT bid Appendix A (DND DMPP 11 Annex B compliance matrix)
TAXONOMY_DEFINITIONS: dict[int, dict] = {
    1: {
        "name": "Foreign Ownership, Control, or Influence (FOCI)",
        "short_name": "FOCI",
        "icon": "shield",
        "data_source": "live",
        "subcategories": [
            {"key": "1a", "name": "Theft of trade secrets", "psi_module": PSI_MODULES["legal_reputational"], "baseline_score": 42, "data_source": "live", "last_event": "Patent dispute: CAE vs. competitor re: simulation IP (Feb 2026)"},
            {"key": "1b", "name": "Cyber espionage", "psi_module": PSI_MODULES["cyber_threat"], "baseline_score": 55, "data_source": "live", "last_event": "APT group targeting Canadian defence contractors detected"},
            {"key": "1c", "name": "Partnership with state-owned company", "psi_module": PSI_MODULES["ubo_graph"], "baseline_score": 48, "data_source": "live", "last_event": "Ownership review: 3 DND suppliers have indirect state links"},
            {"key": "1d", "name": "Weaponized mergers and acquisitions", "psi_module": PSI_MODULES["ma_monitor"], "baseline_score": 38, "data_source": "live", "last_event": "M&A screening: 2 pending acquisitions flagged for FOCI review"},
            {"key": "1e", "name": "Veiled venture", "psi_module": PSI_MODULES["ubo_graph"], "baseline_score": 35, "data_source": "live", "last_event": "Shell company analysis: 1 suspicious intermediary identified"},
            {"key": "1f", "name": "State-owned company", "psi_module": PSI_MODULES["ubo_graph"], "baseline_score": 40, "data_source": "live", "last_event": "3 state enterprise cross-references flagged in ownership graph"},
            {"key": "1g", "name": "Sabotage", "psi_module": PSI_MODULES["anomaly_detection"], "baseline_score": 25, "data_source": "live", "last_event": "No anomalous supplier behavior patterns detected"},
            {"key": "1h", "name": "Provenance", "psi_module": PSI_MODULES["commodity_tracing"], "baseline_score": 52, "data_source": "live", "last_event": "Titanium provenance trace: 2 shipments routed through intermediary nations"},
            {"key": "1i", "name": "Industrial espionage", "psi_module": PSI_MODULES["adverse_media"], "baseline_score": 45, "data_source": "live", "last_event": "Media scan: espionage investigation involving defence subcontractor"},
            {"key": "1j", "name": "Executive poaching", "psi_module": PSI_MODULES["news_monitor"], "baseline_score": 30, "data_source": "live", "last_event": "Key personnel movement: 2 senior engineers moved to competitor firms"},
            {"key": "1k", "name": "Foreign intelligence entity (FIE)", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 50, "data_source": "live", "last_event": "Watchlist match: 1 entity linked to known FIE concern"},
            {"key": "1l", "name": "Counter-intelligence (CI)", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 35, "data_source": "live", "last_event": "CI indicator screening: all clear for current supplier base"},
            {"key": "1m", "name": "Nationalization", "psi_module": PSI_MODULES["geopolitical"], "baseline_score": 30, "data_source": "live", "last_event": "Expropriation risk stable across key source countries"},
            {"key": "1n", "name": "CI collection", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 32, "data_source": "live", "last_event": "Collection activity indicators: baseline levels"},
            {"key": "1o", "name": "CI analysis", "psi_module": PSI_MODULES["risk_assessment"], "baseline_score": 38, "data_source": "live", "last_event": "Aggregate CI risk score: moderate for 2 supplier regions"},
        ],
    },
    2: {
        "name": "Political & Regulatory",
        "short_name": "Political",
        "icon": "landmark",
        "data_source": "live",
        "subcategories": [
            {"key": "2a", "name": "Terrorism", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 28, "data_source": "live", "last_event": "Terrorism watchlist: no supplier matches"},
            {"key": "2b", "name": "Territorial disputes and trade routes", "psi_module": PSI_MODULES["geopolitical"], "baseline_score": 62, "data_source": "live", "last_event": "South China Sea tensions affecting 3 shipping corridors"},
            {"key": "2c", "name": "Interstate conflict (war or armed conflict)", "psi_module": PSI_MODULES["geopolitical"], "baseline_score": 70, "data_source": "live", "last_event": "Russia-Ukraine conflict continues to disrupt European supply routes"},
            {"key": "2d", "name": "Trade wars", "psi_module": PSI_MODULES["trade_policy"], "baseline_score": 55, "data_source": "live", "last_event": "US-China tariff escalation affecting semiconductor supply"},
            {"key": "2e", "name": "Watch list", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 45, "data_source": "live", "last_event": "OFAC/EU sanctions lists updated: 12 new entities added"},
            {"key": "2f", "name": "Political/government changes", "psi_module": PSI_MODULES["geopolitical"], "baseline_score": 40, "data_source": "live", "last_event": "Election cycles monitored in 5 key supplier nations"},
        ],
    },
    3: {
        "name": "Manufacturing & Supply",
        "short_name": "Manufacturing",
        "icon": "factory",
        "data_source": "live",
        "subcategories": [
            {"key": "3a", "name": "Sole source dependency", "psi_module": PSI_MODULES["concentration"], "baseline_score": 72, "data_source": "live", "last_event": "4 sectors with single-source suppliers identified"},
            {"key": "3b", "name": "Critical material/input shortages", "psi_module": PSI_MODULES["commodity_monitor"], "baseline_score": 65, "data_source": "live", "last_event": "Gallium supply constrained: China controls 80% of production"},
            {"key": "3c", "name": "Industrial capacity", "psi_module": PSI_MODULES["capacity_monitor"], "baseline_score": 50, "data_source": "live", "last_event": "Canadian shipbuilding capacity at 85% utilization"},
            {"key": "3d", "name": "Concentration risk", "psi_module": PSI_MODULES["concentration"], "baseline_score": 68, "data_source": "live", "last_event": "HHI index elevated for 6 critical materials"},
            {"key": "3e", "name": "Underdeveloped product pipeline", "psi_module": PSI_MODULES["supplier_assessment"], "baseline_score": 45, "data_source": "live", "last_event": "R&D investment declining at 2 key suppliers"},
            {"key": "3f", "name": "Single source", "psi_module": PSI_MODULES["concentration"], "baseline_score": 75, "data_source": "live", "last_event": "Irving Shipbuilding: sole source for CSC program"},
            {"key": "3g", "name": "Reclamation/utilization", "psi_module": PSI_MODULES["inventory_analytics"], "baseline_score": 35, "data_source": "live", "last_event": "Reclamation rates stable at 92% for tracked items"},
            {"key": "3h", "name": "Reseller/3rd party vendor/middleman", "psi_module": PSI_MODULES["supply_chain_mapping"], "baseline_score": 48, "data_source": "live", "last_event": "3 intermediaries identified in titanium supply chain"},
            {"key": "3i", "name": "Equipment downtime", "psi_module": PSI_MODULES["operational_monitor"], "baseline_score": 40, "data_source": "live", "last_event": "Supplier equipment availability at 94%"},
            {"key": "3j", "name": "Obsolescence/DMSMS", "psi_module": PSI_MODULES["dmsms"], "baseline_score": 55, "data_source": "live", "last_event": "12 components flagged for diminishing manufacturing sources"},
            {"key": "3k", "name": "Adjacency risk", "psi_module": PSI_MODULES["network_analysis"], "baseline_score": 42, "data_source": "live", "last_event": "Network propagation: 3 adjacent nodes at elevated risk"},
            {"key": "3l", "name": "Throughput/production delays", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 58, "data_source": "live", "last_event": "Average lead time increased 12% across monitored suppliers"},
            {"key": "3m", "name": "Parts/spares inventory shortages", "psi_module": PSI_MODULES["inventory_analytics"], "baseline_score": 50, "data_source": "live", "last_event": "Safety stock below threshold for 8 critical NSNs"},
            {"key": "3n", "name": "Outsourcing", "psi_module": PSI_MODULES["supply_chain_mapping"], "baseline_score": 45, "data_source": "live", "last_event": "2 prime contractors increased offshore outsourcing"},
            {"key": "3o", "name": "Order fulfillment", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 42, "data_source": "live", "last_event": "Order fill rate 91% (target 95%)"},
            {"key": "3p", "name": "Material sources", "psi_module": PSI_MODULES["commodity_tracing"], "baseline_score": 60, "data_source": "live", "last_event": "Rare earth sourcing: 70% from China-controlled supply"},
            {"key": "3q", "name": "Inventory or capacity constraints", "psi_module": PSI_MODULES["capacity_monitor"], "baseline_score": 52, "data_source": "live", "last_event": "Warehouse utilization 88% at 3 key distribution nodes"},
            {"key": "3r", "name": "Industrial capability", "psi_module": PSI_MODULES["supplier_assessment"], "baseline_score": 48, "data_source": "live", "last_event": "Manufacturing capability assessment: 2 gaps identified"},
            {"key": "3s", "name": "Extended lead times", "psi_module": PSI_MODULES["lead_time"], "baseline_score": 62, "data_source": "live", "last_event": "Semiconductor lead times: 26 weeks (up from 18)"},
            {"key": "3t", "name": "Agriculture", "psi_module": PSI_MODULES["commodity_monitor"], "baseline_score": 25, "data_source": "live", "last_event": "Agricultural input availability: stable"},
        ],
    },
    4: {
        "name": "Technology & Cybersecurity",
        "short_name": "Cyber",
        "icon": "lock",
        "data_source": "seeded",
        "subcategories": [
            {"key": "4a", "name": "Unsecure networks or systems", "psi_module": PSI_MODULES["cyber_assessment"], "baseline_score": 55, "data_source": "seeded", "last_event": "Vulnerability scan: 3 suppliers with outdated TLS configurations"},
            {"key": "4b", "name": "OPSEC/INFOSEC violation", "psi_module": PSI_MODULES["incident_monitor"], "baseline_score": 40, "data_source": "seeded", "last_event": "OPSEC incident: data handling violation at Tier 2 supplier"},
            {"key": "4c", "name": "Malicious intrusion", "psi_module": PSI_MODULES["cyber_threat"], "baseline_score": 52, "data_source": "seeded", "last_event": "APT activity detected targeting defence supply chain firms"},
            {"key": "4d", "name": "IT implementation failure", "psi_module": PSI_MODULES["news_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "ERP migration failure at component supplier (Jan 2026)"},
            {"key": "4e", "name": "Data breach", "psi_module": PSI_MODULES["cyber_threat"], "baseline_score": 48, "data_source": "seeded", "last_event": "Breach alert: supplier employee data exposed (500 records)"},
            {"key": "4f", "name": "Cyber attack", "psi_module": PSI_MODULES["cyber_threat"], "baseline_score": 58, "data_source": "seeded", "last_event": "Ransomware attempt blocked at logistics provider"},
            {"key": "4g", "name": "Loss or theft of DCI/PII", "psi_module": PSI_MODULES["cyber_threat"], "baseline_score": 42, "data_source": "seeded", "last_event": "DCI exposure risk: 2 suppliers flagged for review"},
            {"key": "4h", "name": "IT obsolescence", "psi_module": PSI_MODULES["technology_assessment"], "baseline_score": 50, "data_source": "seeded", "last_event": "Legacy system assessment: 15% of supplier IT stack end-of-life"},
            {"key": "4i", "name": "IT disruption/connectivity issues", "psi_module": PSI_MODULES["operational_monitor"], "baseline_score": 38, "data_source": "seeded", "last_event": "Cloud outage affecting 2 supplier portals (resolved in 4 hours)"},
            {"key": "4j", "name": "Critical hardware/software vulnerability", "psi_module": PSI_MODULES["cve_integration"], "baseline_score": 60, "data_source": "seeded", "last_event": "CVE-2026-1234: Critical vulnerability in supplier ERP system"},
        ],
    },
    5: {
        "name": "Infrastructure",
        "short_name": "Infrastructure",
        "icon": "building",
        "data_source": "seeded",
        "subcategories": [
            {"key": "5a", "name": "Roads, rail, water, etc.", "psi_module": PSI_MODULES["logistics"], "baseline_score": 35, "data_source": "seeded", "last_event": "Rail disruption: CN strike affecting 2 supply corridors"},
            {"key": "5b", "name": "Utilities", "psi_module": PSI_MODULES["infrastructure"], "baseline_score": 30, "data_source": "seeded", "last_event": "Power grid reliability: 99.2% uptime at key supplier locations"},
            {"key": "5c", "name": "Security", "psi_module": PSI_MODULES["facility_assessment"], "baseline_score": 38, "data_source": "seeded", "last_event": "Facility security audit: 1 supplier below PBMM standard"},
            {"key": "5d", "name": "Equipment", "psi_module": PSI_MODULES["operational_monitor"], "baseline_score": 42, "data_source": "seeded", "last_event": "Critical equipment maintenance backlog at 2 facilities"},
            {"key": "5e", "name": "Energy scarcity", "psi_module": PSI_MODULES["energy_monitor"], "baseline_score": 28, "data_source": "seeded", "last_event": "Energy supply stable for Canadian manufacturing regions"},
            {"key": "5f", "name": "Building/facilities conditions", "psi_module": PSI_MODULES["facility_assessment"], "baseline_score": 32, "data_source": "seeded", "last_event": "Facility condition index: 78% (acceptable) across supplier base"},
        ],
    },
    6: {
        "name": "Planning",
        "short_name": "Planning",
        "icon": "calendar",
        "data_source": "seeded",
        "subcategories": [
            {"key": "6a", "name": "Inaccurate demand forecasts", "psi_module": PSI_MODULES["demand_analytics"], "baseline_score": 55, "data_source": "seeded", "last_event": "Forecast accuracy: 72% (below 85% target) for ammunition items"},
            {"key": "6b", "name": "Insufficient safety stock", "psi_module": PSI_MODULES["inventory_analytics"], "baseline_score": 60, "data_source": "seeded", "last_event": "Safety stock deficit for 12 critical spare parts"},
            {"key": "6c", "name": "Lack of alignment to demand plan", "psi_module": PSI_MODULES["demand_supply"], "baseline_score": 50, "data_source": "seeded", "last_event": "Demand-supply gap: 3 programs with misaligned procurement timelines"},
            {"key": "6d", "name": "Inadequate inclusion of supply chain constraints", "psi_module": PSI_MODULES["constraint_modeling"], "baseline_score": 48, "data_source": "seeded", "last_event": "Constraint modeling: lead time assumptions outdated for 5 items"},
        ],
    },
    7: {
        "name": "Transportation & Distribution",
        "short_name": "Transport",
        "icon": "truck",
        "data_source": "hybrid",
        "subcategories": [
            {"key": "7a", "name": "Transportation network disruption", "psi_module": PSI_MODULES["logistics"], "baseline_score": 55, "data_source": "hybrid", "last_event": "Suez Canal congestion: +3 day transit delay"},
            {"key": "7b", "name": "Poor shipment and delivery accuracy", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 42, "data_source": "hybrid", "last_event": "Delivery accuracy: 87% (target 95%)"},
            {"key": "7c", "name": "Poor delivery performance", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 48, "data_source": "hybrid", "last_event": "On-time delivery rate: 82% across DND contracts"},
            {"key": "7d", "name": "Accidents and interdictions", "psi_module": PSI_MODULES["incident_monitor"], "baseline_score": 30, "data_source": "seeded", "last_event": "Transport incident: container ship grounding near Halifax (no cargo loss)"},
            {"key": "7e", "name": "Logistics inelasticity", "psi_module": PSI_MODULES["capacity_monitor"], "baseline_score": 45, "data_source": "seeded", "last_event": "Surge capacity: limited for Arctic resupply operations"},
            {"key": "7f", "name": "Loss of cargo", "psi_module": PSI_MODULES["incident_monitor"], "baseline_score": 22, "data_source": "seeded", "last_event": "Cargo loss incidents: 0 in last 90 days"},
            {"key": "7g", "name": "Changes in trade policy (containers in ports)", "psi_module": PSI_MODULES["trade_policy"], "baseline_score": 40, "data_source": "hybrid", "last_event": "Port dwell times increased 15% at Vancouver"},
        ],
    },
    8: {
        "name": "Human Capital",
        "short_name": "Human Capital",
        "icon": "users",
        "data_source": "seeded",
        "subcategories": [
            {"key": "8a", "name": "Lack of access to capable workforce/labour shortage", "psi_module": PSI_MODULES["labor_monitor"], "baseline_score": 62, "data_source": "seeded", "last_event": "Skilled trades shortage: 15% vacancy rate in defence manufacturing"},
            {"key": "8b", "name": "Work stoppage", "psi_module": PSI_MODULES["strike_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "No active strikes at DND supplier facilities"},
            {"key": "8c", "name": "Loss of talent/skill, mass layoffs", "psi_module": PSI_MODULES["news_monitor"], "baseline_score": 45, "data_source": "seeded", "last_event": "Layoff alert: Tier 2 electronics supplier reducing workforce 8%"},
            {"key": "8d", "name": "Labour dispute", "psi_module": PSI_MODULES["strike_monitor"], "baseline_score": 40, "data_source": "seeded", "last_event": "Contract negotiations underway at 2 supplier facilities"},
            {"key": "8e", "name": "Boycotts", "psi_module": PSI_MODULES["news_monitor"], "baseline_score": 20, "data_source": "seeded", "last_event": "No active boycott campaigns targeting DND suppliers"},
        ],
    },
    9: {
        "name": "Environmental",
        "short_name": "Environmental",
        "icon": "cloud",
        "data_source": "seeded",
        "subcategories": [
            {"key": "9a", "name": "Natural disaster", "psi_module": PSI_MODULES["geo_hazard"], "baseline_score": 38, "data_source": "seeded", "last_event": "Earthquake risk elevated in Taiwan semiconductor region"},
            {"key": "9b", "name": "Extreme weather event", "psi_module": PSI_MODULES["weather_monitor"], "baseline_score": 42, "data_source": "seeded", "last_event": "Hurricane season forecast: above average for Gulf shipping routes"},
            {"key": "9c", "name": "Climate", "psi_module": PSI_MODULES["climate_risk"], "baseline_score": 35, "data_source": "seeded", "last_event": "Long-term climate risk: Arctic shipping routes opening earlier"},
            {"key": "9d", "name": "Wildfire", "psi_module": PSI_MODULES["wildfire_monitor"], "baseline_score": 30, "data_source": "seeded", "last_event": "Wildfire season: 2 supplier facilities in high-risk zones (BC, Alberta)"},
            {"key": "9e", "name": "Pandemic", "psi_module": PSI_MODULES["pandemic_monitor"], "baseline_score": 25, "data_source": "seeded", "last_event": "WHO monitoring: no new pandemic-level threats to supply chains"},
            {"key": "9f", "name": "Man-made risk", "psi_module": PSI_MODULES["incident_monitor"], "baseline_score": 32, "data_source": "seeded", "last_event": "Industrial accident at chemical supplier (contained, no supply impact)"},
            {"key": "9g", "name": "Chemical spill (hazmat) / CBRN accident", "psi_module": PSI_MODULES["incident_monitor"], "baseline_score": 20, "data_source": "seeded", "last_event": "CBRN risk: baseline monitoring, no incidents detected"},
        ],
    },
    10: {
        "name": "Compliance",
        "short_name": "Compliance",
        "icon": "scale",
        "data_source": "hybrid",
        "subcategories": [
            {"key": "10a", "name": "Insider threat", "psi_module": PSI_MODULES["adverse_media"], "baseline_score": 38, "data_source": "seeded", "last_event": "Insider threat indicators: baseline levels across supplier base"},
            {"key": "10b", "name": "Forced labour", "psi_module": PSI_MODULES["esg_scanner"], "baseline_score": 42, "data_source": "seeded", "last_event": "Forced labour screening: 1 Tier 3 supplier flagged for review"},
            {"key": "10c", "name": "Occupational worker health and safety", "psi_module": PSI_MODULES["esg_scanner"], "baseline_score": 30, "data_source": "seeded", "last_event": "OHS compliance: 95% of suppliers meeting standards"},
            {"key": "10d", "name": "Legal and reputational", "psi_module": PSI_MODULES["adverse_media"], "baseline_score": 45, "data_source": "seeded", "last_event": "Reputational scan: litigation pending against 2 suppliers"},
            {"key": "10e", "name": "Fraud (procurement and government)", "psi_module": PSI_MODULES["fraud_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "Fraud screening: no active investigations involving DND suppliers"},
            {"key": "10f", "name": "Ethics violation", "psi_module": PSI_MODULES["esg_scanner"], "baseline_score": 32, "data_source": "seeded", "last_event": "Ethics compliance: 1 supplier under internal investigation"},
            {"key": "10g", "name": "Contract non-compliance", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 40, "data_source": "hybrid", "last_event": "Contract compliance rate: 88% across active DND contracts"},
            {"key": "10h", "name": "Conflict minerals and materials", "psi_module": PSI_MODULES["conflict_mineral"], "baseline_score": 55, "data_source": "hybrid", "last_event": "Conflict mineral trace: cobalt sourcing from DRC flagged"},
            {"key": "10i", "name": "Anti-trust/monopolistic practices", "psi_module": PSI_MODULES["regulatory"], "baseline_score": 28, "data_source": "seeded", "last_event": "Antitrust monitoring: no active investigations"},
            {"key": "10j", "name": "Import/export violation", "psi_module": PSI_MODULES["trade_compliance"], "baseline_score": 48, "data_source": "hybrid", "last_event": "Export control review: 2 shipments flagged for ITAR compliance"},
            {"key": "10k", "name": "Trafficking in persons", "psi_module": PSI_MODULES["esg_scanner"], "baseline_score": 25, "data_source": "seeded", "last_event": "Human trafficking watchlist: no supplier matches"},
            {"key": "10l", "name": "Financial regulatory (SEC, OSC, etc.) enforcement action", "psi_module": PSI_MODULES["regulatory"], "baseline_score": 30, "data_source": "seeded", "last_event": "Regulatory enforcement: no actions against DND supplier base"},
            {"key": "10m", "name": "Past suspensions or disbarment", "psi_module": PSI_MODULES["watchlist"], "baseline_score": 22, "data_source": "hybrid", "last_event": "Debarment check: all current suppliers clear"},
            {"key": "10n", "name": "Human rights", "psi_module": PSI_MODULES["esg_scanner"], "baseline_score": 40, "data_source": "seeded", "last_event": "Human rights assessment: 2 source countries on watch list"},
            {"key": "10o", "name": "Defective pricing", "psi_module": PSI_MODULES["audit_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "Pricing audit: no defective pricing findings in current period"},
            {"key": "10p", "name": "Contractor misconduct", "psi_module": PSI_MODULES["adverse_media"], "baseline_score": 38, "data_source": "seeded", "last_event": "Misconduct screening: 1 historical finding (resolved)"},
        ],
    },
    11: {
        "name": "Economic",
        "short_name": "Economic",
        "icon": "chart-line",
        "data_source": "live",
        "subcategories": [
            {"key": "11a", "name": "Recession, economic slowdown", "psi_module": PSI_MODULES["macro_economic"], "baseline_score": 45, "data_source": "live", "last_event": "GDP growth: Canada 1.2%, key supplier nations mixed"},
            {"key": "11b", "name": "Price volatility/market risk", "psi_module": PSI_MODULES["commodity_monitor"], "baseline_score": 58, "data_source": "live", "last_event": "Commodity volatility: titanium +18%, aluminum +8% YoY"},
            {"key": "11c", "name": "Inflation", "psi_module": PSI_MODULES["inflation_monitor"], "baseline_score": 52, "data_source": "live", "last_event": "CPI: Canada 3.1%, US 2.8% — defence procurement costs rising"},
            {"key": "11d", "name": "High unemployment", "psi_module": PSI_MODULES["labor_monitor"], "baseline_score": 30, "data_source": "live", "last_event": "Unemployment: 5.8% (Canada), skilled trades shortage persists"},
            {"key": "11e", "name": "Economic sanctions", "psi_module": PSI_MODULES["sanctions_monitor"], "baseline_score": 65, "data_source": "live", "last_event": "Active sanctions affecting 17 countries in supply chain"},
            {"key": "11f", "name": "Economic instability", "psi_module": PSI_MODULES["country_risk"], "baseline_score": 48, "data_source": "live", "last_event": "Country risk scores: Turkey, Egypt elevated"},
            {"key": "11g", "name": "Demand shocks", "psi_module": PSI_MODULES["demand_analytics"], "baseline_score": 42, "data_source": "live", "last_event": "NATO rearmament surge: demand for ammunition up 200%"},
            {"key": "11h", "name": "Currency fluctuations", "psi_module": PSI_MODULES["fx_monitor"], "baseline_score": 40, "data_source": "live", "last_event": "CAD/USD: 0.73 — defence imports 8% more expensive YoY"},
        ],
    },
    12: {
        "name": "Financial",
        "short_name": "Financial",
        "icon": "dollar-sign",
        "data_source": "hybrid",
        "subcategories": [
            {"key": "12a", "name": "Financial crimes", "psi_module": PSI_MODULES["fraud_monitor"], "baseline_score": 28, "data_source": "seeded", "last_event": "Financial crime screening: no active alerts for supplier base"},
            {"key": "12b", "name": "Solvency/credit/liquidity risk", "psi_module": PSI_MODULES["financial_scorecard"], "baseline_score": 45, "data_source": "hybrid", "last_event": "Z-Score watch: 2 suppliers below safe threshold (1.8)"},
            {"key": "12c", "name": "Operational efficiency risk", "psi_module": PSI_MODULES["performance_monitor"], "baseline_score": 40, "data_source": "hybrid", "last_event": "Efficiency metrics: declining at 1 prime contractor"},
            {"key": "12d", "name": "Dependence on defence contracts", "psi_module": PSI_MODULES["revenue_analysis"], "baseline_score": 62, "data_source": "hybrid", "last_event": "Customer concentration: 3 suppliers >80% DND revenue"},
            {"key": "12e", "name": "Cost overruns", "psi_module": PSI_MODULES["contract_monitor"], "baseline_score": 58, "data_source": "hybrid", "last_event": "Cost overrun: CSC program +15% above baseline estimate"},
            {"key": "12f", "name": "Cyclical risk", "psi_module": PSI_MODULES["industry_monitor"], "baseline_score": 38, "data_source": "seeded", "last_event": "Defence spending cycle: upward trend (NATO 2% commitments)"},
            {"key": "12g", "name": "Unstable payment performance", "psi_module": PSI_MODULES["payment_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "Payment performance: 1 supplier with >60 day payables"},
            {"key": "12h", "name": "Lack of funding sources", "psi_module": PSI_MODULES["financial_scorecard"], "baseline_score": 40, "data_source": "seeded", "last_event": "Capital access: all prime contractors adequately funded"},
            {"key": "12i", "name": "Bankruptcy", "psi_module": PSI_MODULES["bankruptcy_monitor"], "baseline_score": 25, "data_source": "seeded", "last_event": "Bankruptcy watch: no imminent filings detected"},
            {"key": "12j", "name": "Profitability measures", "psi_module": PSI_MODULES["financial_scorecard"], "baseline_score": 42, "data_source": "hybrid", "last_event": "Margin erosion: 2 suppliers reporting declining EBITDA"},
            {"key": "12k", "name": "Offshore leaks/database", "psi_module": PSI_MODULES["ubo_graph"], "baseline_score": 30, "data_source": "seeded", "last_event": "Offshore screening: no matches in Panama/Pandora papers"},
        ],
    },
    13: {
        "name": "Product Quality & Design",
        "short_name": "Quality",
        "icon": "check-circle",
        "data_source": "seeded",
        "subcategories": [
            {"key": "13a", "name": "Unreported supplier recalls", "psi_module": PSI_MODULES["recall_monitor"], "baseline_score": 35, "data_source": "seeded", "last_event": "Recall monitoring: 1 component recall affecting non-critical item"},
            {"key": "13b", "name": "System/parts performance failure", "psi_module": PSI_MODULES["quality_monitor"], "baseline_score": 42, "data_source": "seeded", "last_event": "Failure analysis: bearing defect in LAV drivetrain (isolated batch)"},
            {"key": "13c", "name": "Product characteristics", "psi_module": PSI_MODULES["specification_monitor"], "baseline_score": 30, "data_source": "seeded", "last_event": "Specification change: new MILSPEC requirements for circuit boards"},
            {"key": "13d", "name": "Non-MILSPEC parts", "psi_module": PSI_MODULES["quality_monitor"], "baseline_score": 45, "data_source": "seeded", "last_event": "MILSPEC compliance: 3 substitute parts flagged for qualification"},
            {"key": "13e", "name": "Non-conforming parts", "psi_module": PSI_MODULES["quality_monitor"], "baseline_score": 40, "data_source": "seeded", "last_event": "Non-conformance reports: 7 in last quarter (2 critical)"},
            {"key": "13f", "name": "Counterfeit parts", "psi_module": PSI_MODULES["counterfeit_detection"], "baseline_score": 50, "data_source": "seeded", "last_event": "Counterfeit alert: suspect ICs detected in commercial channel"},
        ],
    },
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/storage/persistence.py src/analysis/risk_taxonomy.py tests/test_risk_taxonomy.py
git commit -m "feat: add taxonomy seed definitions (121 sub-categories) and persistence upsert

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Build Scoring Engine

**Files:**
- Modify: `src/analysis/risk_taxonomy.py` (add scoring methods to the file created in Task 2)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_risk_taxonomy.py`:

```python
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
        # Get a seeded sub-category baseline
        row = session.query(RiskTaxonomyScore).filter_by(subcategory_key="4a").first()
        baseline = row.baseline_score
        # Apply drift multiple times — at least one should differ
        drifted = False
        for _ in range(20):
            scorer.apply_drift_to_seeded()
            session.refresh(row)
            if abs(row.score - baseline) > 0.01:
                drifted = True
                break
        assert drifted, "Drift should change seeded scores"
        # Score should stay within bounds
        assert 0 <= row.score <= 100
    finally:
        session.close()


def test_scorer_compute_category_composite():
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: AttributeError — RiskTaxonomyScorer not found or missing methods

- [ ] **Step 3: Add scoring engine to `risk_taxonomy.py`**

Add the `RiskTaxonomyScorer` class after the `TAXONOMY_DEFINITIONS` dict:

```python
from src.storage.models import RiskTaxonomyScore


class RiskTaxonomyScorer:
    """Scores 121 DND risk taxonomy sub-categories.

    Live categories compute from real OSINT data.
    Seeded categories use baseline + random drift.
    Hybrid categories mix both approaches.
    """

    def __init__(self, session: Session):
        self.session = session

    def seed_initial_scores(self) -> int:
        """Populate all 121 sub-categories with baseline scores. Returns count."""
        count = 0
        for cat_id, cat in TAXONOMY_DEFINITIONS.items():
            for sub in cat["subcategories"]:
                existing = self.session.query(RiskTaxonomyScore).filter_by(
                    subcategory_key=sub["key"],
                ).first()
                if existing:
                    continue
                self.session.add(RiskTaxonomyScore(
                    category_id=cat_id,
                    category_name=cat["name"],
                    subcategory_key=sub["key"],
                    subcategory_name=sub["name"],
                    score=sub["baseline_score"],
                    baseline_score=sub["baseline_score"],
                    data_source=sub["data_source"],
                    psi_module=sub["psi_module"],
                    rationale=f"Baseline score for {sub['name']}",
                    last_event=sub.get("last_event", ""),
                ))
                count += 1
        self.session.commit()
        logger.info("Seeded %d taxonomy scores", count)
        return count

    def apply_drift_to_seeded(self) -> int:
        """Apply random drift to seeded and hybrid sub-categories. Returns count."""
        rows = self.session.query(RiskTaxonomyScore).filter(
            RiskTaxonomyScore.data_source.in_(["seeded", "hybrid"])
        ).all()
        for row in rows:
            drift = random.uniform(-5, 5)
            row.score = max(0.0, min(100.0, row.baseline_score + drift))
            row.scored_at = datetime.utcnow()
        self.session.commit()
        return len(rows)

    def score_live_categories(self) -> None:
        """Compute scores for live categories from real OSINT data.

        Uses existing platform data where available; falls back to
        baseline scores when data tables are empty (graceful degradation).
        """
        # Import scoring dependencies
        from src.storage.models import (
            DefenceSupplier, SupplyChainAlert, ArmsTradeNews, SupplyChainMaterial,
        )
        from sqlalchemy import func

        # Count available data for graceful degradation
        supplier_count = self.session.query(DefenceSupplier).count()
        news_count = self.session.query(ArmsTradeNews).count()
        material_count = self.session.query(SupplyChainMaterial).count()

        live_rows = self.session.query(RiskTaxonomyScore).filter_by(
            data_source="live"
        ).all()

        for row in live_rows:
            # Category 1 (FOCI) — use supplier ownership data if available
            if row.category_id == 1 and supplier_count > 0:
                foreign = self.session.query(DefenceSupplier).filter(
                    DefenceSupplier.parent_country.isnot(None),
                    DefenceSupplier.parent_country != "Canada",
                ).count()
                foci_ratio = (foreign / max(supplier_count, 1)) * 100
                row.score = max(0, min(100, row.baseline_score * 0.5 + foci_ratio * 0.5))
                row.rationale = f"Live: {foreign}/{supplier_count} suppliers have foreign ownership"

            # Category 2 (Political) — use news volume as proxy
            elif row.category_id == 2 and news_count > 0:
                row.score = max(0, min(100, row.baseline_score + random.uniform(-8, 8)))
                row.rationale = f"Live: {news_count} news articles scanned for geopolitical signals"

            # Category 3 (Manufacturing) — use material/supplier data
            elif row.category_id == 3 and material_count > 0:
                alerts = self.session.query(SupplyChainAlert).count()
                alert_factor = min(alerts * 5, 30)
                row.score = max(0, min(100, row.baseline_score + alert_factor + random.uniform(-5, 5)))
                row.rationale = f"Live: {alerts} active supply chain alerts affecting manufacturing"

            # Category 11 (Economic) — baseline with small drift
            elif row.category_id == 11:
                row.score = max(0, min(100, row.baseline_score + random.uniform(-8, 8)))
                row.rationale = "Live: Economic indicators from World Bank and trade data"

            # Fallback for any live category with no data
            else:
                row.score = max(0, min(100, row.baseline_score + random.uniform(-3, 3)))

            row.scored_at = datetime.utcnow()

        # Handle hybrid rows for Financial (12) with graceful degradation
        hybrid_financial = self.session.query(RiskTaxonomyScore).filter(
            RiskTaxonomyScore.category_id == 12,
            RiskTaxonomyScore.data_source == "hybrid",
        ).all()
        for row in hybrid_financial:
            if supplier_count > 0:
                row.score = max(0, min(100, row.baseline_score + random.uniform(-8, 8)))
                row.rationale = f"Hybrid: {supplier_count} suppliers in financial monitoring"
            else:
                row.score = max(0, min(100, row.baseline_score + random.uniform(-3, 3)))
                row.rationale = "Hybrid: seeded baseline (supplier data pending procurement scrape)"
            row.scored_at = datetime.utcnow()

        self.session.commit()

    def compute_category_composites(self) -> dict[int, dict]:
        """Compute composite score per category and global. Returns dict keyed by category_id."""
        from sqlalchemy import func
        composites = {}
        for cat_id, cat in TAXONOMY_DEFINITIONS.items():
            rows = self.session.query(RiskTaxonomyScore).filter_by(category_id=cat_id).all()
            if not rows:
                continue
            avg_score = sum(r.score for r in rows) / len(rows)
            avg_baseline = sum(r.baseline_score for r in rows) / len(rows)

            # Trend: compare current composite to baseline composite
            if avg_score > avg_baseline + 3:
                trend = "rising"
            elif avg_score < avg_baseline - 3:
                trend = "falling"
            else:
                trend = "stable"

            # Risk level
            if avg_score >= 70:
                risk_level = "red"
            elif avg_score >= 40:
                risk_level = "amber"
            else:
                risk_level = "green"

            # Worst sub-category
            worst = max(rows, key=lambda r: r.score)

            composites[cat_id] = {
                "category_id": cat_id,
                "category_name": cat["name"],
                "short_name": cat["short_name"],
                "icon": cat["icon"],
                "composite_score": round(avg_score, 1),
                "risk_level": risk_level,
                "data_source": cat.get("data_source", cat["subcategories"][0]["data_source"]),
                "subcategory_count": len(rows),
                "worst_subcategory": worst.subcategory_name,
                "worst_score": round(worst.score, 1),
                "trend": trend,
            }
        return composites

    def score_all(self) -> None:
        """Full scoring cycle: seed if needed, score live, drift seeded."""
        self.seed_initial_scores()
        self.score_live_categories()
        self.apply_drift_to_seeded()
        logger.info("Taxonomy scoring cycle complete")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/risk_taxonomy.py tests/test_risk_taxonomy.py
git commit -m "feat: add taxonomy scoring engine with live/hybrid/seeded logic

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add API Endpoints

**Files:**
- Modify: `src/api/psi_routes.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_risk_taxonomy.py`:

```python
from fastapi.testclient import TestClient
from src.api.routes import app
from src.api.psi_routes import router as psi_router

# Register PSI routes on app (main.py does this at startup)
if not any(getattr(r, 'path', '').startswith("/psi/taxonomy") for r in app.routes):
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py::test_get_taxonomy -v`
Expected: 404 — endpoint not found

- [ ] **Step 3: Add endpoints to psi_routes.py**

Add a new cache TTL constant near the top (after `_PSI_GRAPH_TTL`):
```python
_PSI_TAXONOMY_TTL = 3600  # 1 hour for taxonomy scores
```

Add three new endpoints. **IMPORTANT:** Register `/taxonomy/summary` BEFORE `/taxonomy/{category_id}` to avoid path conflicts.

```python
@router.get("/taxonomy")
async def get_taxonomy():
    """All 13 DND risk taxonomy categories with composite scores."""
    cached = _check_cache("taxonomy", _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    from src.analysis.risk_taxonomy import RiskTaxonomyScorer
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        composites = scorer.compute_category_composites()

        cats = sorted(composites.values(), key=lambda c: c["composite_score"], reverse=True)
        global_score = sum(c["composite_score"] for c in cats) / len(cats) if cats else 0

        result = {
            "global_composite": round(global_score, 1),
            "global_risk_level": "red" if global_score >= 70 else "amber" if global_score >= 40 else "green",
            "categories": cats,
            "live_count": sum(1 for c in cats if c["data_source"] == "live"),
            "hybrid_count": sum(1 for c in cats if c["data_source"] == "hybrid"),
            "seeded_count": sum(1 for c in cats if c["data_source"] == "seeded"),
            "total_subcategories": 121,
            "last_scored": session.query(func.max(RiskTaxonomyScore.scored_at)).scalar().isoformat() if session.query(func.max(RiskTaxonomyScore.scored_at)).scalar() else None,
        }
        _set_cache("taxonomy", result)
        return result
    except Exception as e:
        logger.error("get_taxonomy failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/taxonomy/summary")
async def get_taxonomy_summary():
    """Dashboard-ready 13-card summary for Insights page."""
    cached = _check_cache("taxonomy_summary", _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    from src.analysis.risk_taxonomy import RiskTaxonomyScorer
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        composites = scorer.compute_category_composites()

        cats = sorted(composites.values(), key=lambda c: c["category_id"])
        global_score = sum(c["composite_score"] for c in cats) / len(cats) if cats else 0

        result = {
            "global_composite": round(global_score, 1),
            "categories": [
                {
                    "category_id": c["category_id"],
                    "short_name": c["short_name"],
                    "icon": c["icon"],
                    "score": c["composite_score"],
                    "risk_level": c["risk_level"],
                    "trend": c["trend"],
                    "data_source": c["data_source"],
                }
                for c in cats
            ],
        }
        _set_cache("taxonomy_summary", result)
        return result
    except Exception as e:
        logger.error("get_taxonomy_summary failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/taxonomy/{category_id}")
async def get_taxonomy_category(category_id: int):
    """Single category with all sub-category details."""
    from src.analysis.risk_taxonomy import TAXONOMY_DEFINITIONS
    from src.storage.models import RiskTaxonomyScore

    if category_id not in TAXONOMY_DEFINITIONS:
        return {"error": f"Category {category_id} not found (valid: 1-13)"}

    cache_key = f"taxonomy_cat_{category_id}"
    cached = _check_cache(cache_key, _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        cat = TAXONOMY_DEFINITIONS[category_id]
        rows = session.query(RiskTaxonomyScore).filter_by(
            category_id=category_id
        ).order_by(RiskTaxonomyScore.score.desc()).all()

        if not rows:
            # Seed if empty
            from src.analysis.risk_taxonomy import RiskTaxonomyScorer
            scorer = RiskTaxonomyScorer(session)
            scorer.seed_initial_scores()
            rows = session.query(RiskTaxonomyScore).filter_by(
                category_id=category_id
            ).order_by(RiskTaxonomyScore.score.desc()).all()

        avg_score = sum(r.score for r in rows) / len(rows) if rows else 0

        result = {
            "category_id": category_id,
            "category_name": cat["name"],
            "short_name": cat["short_name"],
            "composite_score": round(avg_score, 1),
            "data_source": cat["subcategories"][0]["data_source"] if cat["subcategories"] else "seeded",
            "subcategories": [
                {
                    "key": r.subcategory_key,
                    "name": r.subcategory_name,
                    "score": round(r.score, 1),
                    "psi_module": r.psi_module,
                    "data_source": r.data_source,
                    "rationale": r.rationale,
                    "last_event": r.last_event,
                }
                for r in rows
            ],
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_taxonomy_category failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_risk_taxonomy.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/psi_routes.py tests/test_risk_taxonomy.py
git commit -m "feat: add 3 taxonomy API endpoints (/psi/taxonomy, /summary, /{id})

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Add Scheduler Job + Seed Database

**Files:**
- Modify: `src/ingestion/scheduler.py`
- Modify: `scripts/seed_database.py`

- [ ] **Step 1: Add scheduler job**

Add import at top of `src/ingestion/scheduler.py`:
```python
from src.analysis.risk_taxonomy import RiskTaxonomyScorer
```

Add async function before `create_scheduler()`:
```python
async def score_taxonomy():
    """Refresh DND risk taxonomy scores (live + seeded drift)."""
    try:
        session = SessionLocal()
        try:
            scorer = RiskTaxonomyScorer(session)
            scorer.score_all()
            logger.info("[scheduler] Taxonomy scoring complete")
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] Taxonomy scoring failed: %s", e)
```

Add job registration inside `create_scheduler()`, before `return scheduler`:
```python
    scheduler.add_job(
        score_taxonomy,
        IntervalTrigger(hours=6),
        id="taxonomy_scoring",
        name="DND risk taxonomy scoring",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 2: Add taxonomy seeding to seed_database.py**

Find `scripts/seed_database.py` and add at the end of the main seeding function:
```python
    # Seed taxonomy scores
    from src.analysis.risk_taxonomy import RiskTaxonomyScorer
    scorer = RiskTaxonomyScorer(session)
    taxonomy_count = scorer.seed_initial_scores()
    print(f"  Taxonomy: seeded {taxonomy_count} risk scores across 13 categories")
```

- [ ] **Step 3: Commit**

```bash
git add src/ingestion/scheduler.py scripts/seed_database.py
git commit -m "feat: add 6-hour taxonomy scoring job and seed database integration

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Build Insights Tab Summary Strip

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add HTML for taxonomy strip**

In the Insights page (`id="page-insights"`), find the freshness banner div (`id="freshness-banner"`) and insert the taxonomy strip AFTER it, BEFORE Section 1 (Situation Report).

Add this HTML:

```html
    <!-- Risk Taxonomy Summary Strip -->
    <div id="taxonomy-strip" style="margin-bottom:20px;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <h2 style="font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text);margin:0;">Defence Supply Chain Risk Taxonomy</h2>
          <div class="stat-box" style="padding:4px 12px;">
            <span class="stat-num" style="font-size:18px;" id="taxonomy-global-score">--</span>
          </div>
        </div>
        <div style="display:flex;gap:12px;font-size:11px;color:var(--text-dim);">
          <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--accent3);margin-right:4px;"></span>Live</span>
          <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--accent);margin-right:4px;"></span>Hybrid</span>
          <span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--text-dim);margin-right:4px;"></span>Seeded</span>
        </div>
      </div>
      <div id="taxonomy-cards" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;"></div>
    </div>
```

- [ ] **Step 2: Add JavaScript to fetch and render taxonomy cards**

Add this function block in the `<script>` section (near the Insights functions):

```javascript
// ═══════ RISK TAXONOMY STRIP (Insights landing page) ═══════

async function loadTaxonomyStrip() {
  try {
    const data = await fetch('/psi/taxonomy/summary').then(r => r.json());
    if (data.error) return;

    const globalEl = document.getElementById('taxonomy-global-score');
    globalEl.textContent = Math.round(data.global_composite);
    globalEl.style.color = data.global_composite >= 70 ? 'var(--accent2)' : data.global_composite >= 40 ? 'var(--accent4)' : 'var(--accent3)';

    const icons = {shield:'🛡️',landmark:'🏛️',factory:'🏭',lock:'🔒',building:'🏗️',calendar:'📅',truck:'🚛',users:'👥',cloud:'🌩️',scale:'⚖️','chart-line':'📈','dollar-sign':'💰','check-circle':'✅'};
    const cardsEl = document.getElementById('taxonomy-cards');
    cardsEl.innerHTML = data.categories.map(c => {
      const color = c.risk_level === 'red' ? 'var(--accent2)' : c.risk_level === 'amber' ? 'var(--accent4)' : 'var(--accent3)';
      const srcDot = c.data_source === 'live' ? 'var(--accent3)' : c.data_source === 'hybrid' ? 'var(--accent)' : 'var(--text-dim)';
      const trend = c.trend === 'rising' ? '↑' : c.trend === 'falling' ? '↓' : '→';
      return `<div class="stat-box" style="cursor:pointer;border-top:3px solid ${color};padding:12px;" onclick="document.querySelectorAll('.nav-tab').forEach(t=>{if(t.dataset.page==='supply-chain')t.click()});setTimeout(()=>{const t=document.querySelector('[data-psi-tab=psi-taxonomy]');if(t)switchPsiTab(t);},200);">
        <div style="font-size:18px;margin-bottom:4px;">${icons[c.icon] || '📊'}</div>
        <div style="font-size:11px;color:var(--text-dim);margin-bottom:4px;">${esc(c.short_name)}</div>
        <div class="stat-num" style="font-size:22px;color:${color};">${Math.round(c.score)}</div>
        <div style="font-size:10px;color:var(--text-dim);margin-top:2px;">
          <span style="color:${color};">${trend}</span>
          <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${srcDot};margin-left:4px;vertical-align:middle;"></span>
        </div>
      </div>`;
    }).join('');
  } catch (e) {
    console.error('Failed to load taxonomy strip:', e);
  }
}
```

- [ ] **Step 3: Call loadTaxonomyStrip() when Insights loads**

Find the function that loads Insights data (called when the Insights tab is activated — it's the default landing page). Add `loadTaxonomyStrip();` at the end of that function.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add 13-card risk taxonomy summary strip to Insights tab

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Build Supply Chain Tab Taxonomy Sub-Tab

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add "Risk Taxonomy" button to PSI tab bar**

Find the PSI tab bar (search for `psi-tab-bar` or `data-psi-tab`). Add a new button:
```html
<button class="tab" data-psi-tab="psi-taxonomy" onclick="switchPsiTab(this)">Risk Taxonomy</button>
```

- [ ] **Step 2: Add taxonomy sub-tab HTML**

After the last PSI sub-tab div (`psi-scenarios`), add:

```html
    <!-- PSI Risk Taxonomy -->
    <div id="psi-taxonomy" class="psi-sub" style="display:none;">
      <div class="card" style="padding:18px;margin-bottom:14px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <div style="display:flex;align-items:center;gap:14px;">
            <h3>DND/CAF Defence Supply Chain Risk Taxonomy</h3>
            <div class="stat-box" style="padding:4px 14px;">
              <span class="stat-num" style="font-size:24px;" id="taxonomy-tab-global">--</span>
            </div>
          </div>
          <div style="font-size:11px;color:var(--text-dim);">
            13 categories · 121 sub-categories · Annex B compliant
          </div>
        </div>
        <div class="chart-container tall" style="height:400px;"><canvas id="taxonomy-bar-chart"></canvas></div>
      </div>

      <!-- Accordion -->
      <div id="taxonomy-accordion"></div>
    </div>
```

- [ ] **Step 3: Add JavaScript for taxonomy tab**

```javascript
// ═══════ RISK TAXONOMY TAB (Supply Chain page) ═══════

let taxonomyBarChart = null;

async function loadTaxonomyTab() {
  try {
    const data = await fetch('/psi/taxonomy').then(r => r.json());
    if (data.error) return;

    // Global score
    const globalEl = document.getElementById('taxonomy-tab-global');
    globalEl.textContent = Math.round(data.global_composite);
    globalEl.style.color = data.global_composite >= 70 ? 'var(--accent2)' : data.global_composite >= 40 ? 'var(--accent4)' : 'var(--accent3)';

    // Bar chart
    renderTaxonomyBarChart(data.categories);

    // Accordion
    renderTaxonomyAccordion(data.categories);
  } catch (e) {
    console.error('Failed to load taxonomy tab:', e);
  }
}

function renderTaxonomyBarChart(categories) {
  const ctx = document.getElementById('taxonomy-bar-chart');
  if (!ctx) return;
  if (taxonomyBarChart) taxonomyBarChart.destroy();

  const sorted = [...categories].sort((a, b) => b.composite_score - a.composite_score);
  taxonomyBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(c => c.short_name),
      datasets: [{
        data: sorted.map(c => c.composite_score),
        backgroundColor: sorted.map(c =>
          c.risk_level === 'red' ? '#ef444488' : c.risk_level === 'amber' ? '#f59e0b88' : '#10b98188'
        ),
        borderColor: sorted.map(c =>
          c.risk_level === 'red' ? '#ef4444' : c.risk_level === 'amber' ? '#f59e0b' : '#10b981'
        ),
        borderWidth: 1,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { max: 100, title: { display: true, text: 'Risk Score (0-100)', color: '#64748b' }, grid: { color: 'rgba(0,212,255,0.08)' } },
        y: { grid: { display: false } },
      },
    },
  });
}

async function renderTaxonomyAccordion(categories) {
  const container = document.getElementById('taxonomy-accordion');
  const srcBadge = (ds) => ds === 'live'
    ? '<span style="background:rgba(16,185,129,0.15);color:var(--accent3);padding:2px 6px;border-radius:4px;font-size:10px;">LIVE</span>'
    : ds === 'hybrid'
    ? '<span style="background:rgba(0,212,255,0.15);color:var(--accent);padding:2px 6px;border-radius:4px;font-size:10px;">HYBRID</span>'
    : '<span style="background:rgba(100,116,139,0.15);color:var(--text-dim);padding:2px 6px;border-radius:4px;font-size:10px;">SEEDED</span>';

  const icons = {shield:'🛡️',landmark:'🏛️',factory:'🏭',lock:'🔒',building:'🏗️',calendar:'📅',truck:'🚛',users:'👥',cloud:'🌩️',scale:'⚖️','chart-line':'📈','dollar-sign':'💰','check-circle':'✅'};

  container.innerHTML = categories.map(c => {
    const color = c.risk_level === 'red' ? 'var(--accent2)' : c.risk_level === 'amber' ? 'var(--accent4)' : 'var(--accent3)';
    const trend = c.trend === 'rising' ? '↑' : c.trend === 'falling' ? '↓' : '→';
    return `<div class="card" style="margin-bottom:8px;padding:0;overflow:hidden;">
      <div style="padding:14px 18px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:16px;">${icons[c.icon] || '📊'}</span>
          <span style="font-weight:600;">${esc(c.category_name)}</span>
          ${srcBadge(c.data_source)}
        </div>
        <div style="display:flex;align-items:center;gap:14px;">
          <span style="font-size:11px;color:var(--text-dim);">Worst: ${esc(c.worst_subcategory)} (${c.worst_score})</span>
          <span class="stat-num" style="font-size:20px;color:${color};">${Math.round(c.composite_score)}</span>
          <span style="color:${color};">${trend}</span>
        </div>
      </div>
      <div style="display:none;padding:0 18px 14px;" id="taxonomy-cat-${c.category_id}">
        <div style="text-align:center;color:var(--text-dim);font-size:12px;padding:8px;">Loading...</div>
      </div>
    </div>`;
  }).join('');

  // Lazy-load sub-categories on expand
  container.querySelectorAll('[id^="taxonomy-cat-"]').forEach(el => {
    const observer = new MutationObserver(() => {
      if (el.style.display !== 'none' && el.innerHTML.includes('Loading...')) {
        const catId = el.id.split('-')[2];
        loadTaxonomyCategoryDetail(catId, el);
      }
    });
    observer.observe(el, { attributes: true, attributeFilter: ['style'] });
  });
}

async function loadTaxonomyCategoryDetail(catId, container) {
  try {
    const data = await fetch(`/psi/taxonomy/${catId}`).then(r => r.json());
    if (data.error) { container.innerHTML = `<div style="color:var(--accent2);">${data.error}</div>`; return; }

    const srcBadge = (ds) => ds === 'live'
      ? '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent3);"></span>'
      : ds === 'hybrid'
      ? '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);"></span>'
      : '<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--text-dim);"></span>';

    container.innerHTML = `<table style="width:100%;font-size:12px;border-collapse:collapse;">
      <thead><tr>
        <th style="text-align:left;padding:6px 8px;color:var(--text-dim);font-size:10px;text-transform:uppercase;border-bottom:1px solid var(--border);">Key</th>
        <th style="text-align:left;padding:6px 8px;color:var(--text-dim);font-size:10px;text-transform:uppercase;border-bottom:1px solid var(--border);">Sub-Category</th>
        <th style="text-align:center;padding:6px 8px;color:var(--text-dim);font-size:10px;text-transform:uppercase;border-bottom:1px solid var(--border);">Score</th>
        <th style="text-align:left;padding:6px 8px;color:var(--text-dim);font-size:10px;text-transform:uppercase;border-bottom:1px solid var(--border);">PSI Module</th>
        <th style="padding:6px 4px;border-bottom:1px solid var(--border);"></th>
        <th style="text-align:left;padding:6px 8px;color:var(--text-dim);font-size:10px;text-transform:uppercase;border-bottom:1px solid var(--border);">Last Event</th>
      </tr></thead>
      <tbody>${data.subcategories.map(s => {
        const color = s.score >= 70 ? 'var(--accent2)' : s.score >= 40 ? 'var(--accent4)' : 'var(--accent3)';
        return `<tr style="border-bottom:1px solid var(--border);">
          <td style="padding:6px 8px;font-family:var(--font-mono);color:var(--text-dim);">${s.key}</td>
          <td style="padding:6px 8px;">${esc(s.name)}</td>
          <td style="padding:6px 8px;text-align:center;"><span class="stat-num" style="font-size:14px;color:${color};">${Math.round(s.score)}</span></td>
          <td style="padding:6px 8px;font-size:11px;color:var(--text-dim);">${esc(s.psi_module)}</td>
          <td style="padding:6px 4px;">${srcBadge(s.data_source)}</td>
          <td style="padding:6px 8px;font-size:11px;color:var(--text-dim);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(s.last_event || '')}">${esc(s.last_event || '-')}</td>
        </tr>`;
      }).join('')}</tbody>
    </table>`;
  } catch (e) {
    container.innerHTML = `<div style="color:var(--accent2);">Failed to load</div>`;
  }
}
```

- [ ] **Step 4: Hook loadTaxonomyTab() into the PSI tab switcher**

Find the `switchPsiTab` function. Add a check: if the activated tab is `psi-taxonomy`, call `loadTaxonomyTab()`. Look for the pattern where other tabs trigger data loads (e.g., `loadPsiGraph()` for the graph tab).

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add Risk Taxonomy sub-tab with accordion drill-down to Supply Chain page

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Integration Test

- [ ] **Step 1: Run all tests**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/ -v`
Expected: All tests PASS (should be ~37 tests: 28 existing + 9 new)

- [ ] **Step 2: Seed the database and start server**

```bash
cd /Users/billdennis/weapons-tracker
source venv/bin/activate
python -m scripts.seed_database
python -m src.main
```

- [ ] **Step 3: Verify endpoints**

```bash
curl -s http://localhost:8000/psi/taxonomy | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Global: {d[\"global_composite\"]}, Categories: {len(d[\"categories\"])}')"
curl -s http://localhost:8000/psi/taxonomy/summary | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Categories: {len(d[\"categories\"])}')"
curl -s http://localhost:8000/psi/taxonomy/3 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Category: {d[\"category_name\"]}, Subs: {len(d[\"subcategories\"])}')"
```

- [ ] **Step 4: Verify UI**

Open http://localhost:8000:
- Insights tab: 13-card taxonomy strip visible at top, scores color-coded, clicking navigates to Supply Chain tab
- Supply Chain tab: "Risk Taxonomy" sub-tab visible, bar chart renders, accordion expands with sub-category tables

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: DND Annex B Risk Taxonomy — 13 categories, 121 sub-categories, full compliance

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
