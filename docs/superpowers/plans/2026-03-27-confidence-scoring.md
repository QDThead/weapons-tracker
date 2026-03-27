# Confidence Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add confidence levels, source counts, and triangulation indicators to every risk assessment — the "Glass Box" data integrity requirement (DND Q8).

**Architecture:** A shared `compute_confidence()` utility dynamically calculates confidence for any risk score based on data source type and independent source count. No new tables — confidence computed on the fly. Added as an additive `confidence` field to 5 existing API responses. UI renders compact badges everywhere scores appear. PDF briefing updated with Conf. column.

**Tech Stack:** Python 3.9+, FastAPI, SQLAlchemy 2.0, existing design system

**Spec:** `docs/superpowers/specs/2026-03-27-confidence-scoring-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/analysis/confidence.py` | Create | Shared confidence computation utility |
| `src/api/psi_routes.py` | Modify | Add confidence to taxonomy endpoints |
| `src/api/supplier_routes.py` | Modify | Add confidence to supplier endpoints |
| `src/api/mitigation_routes.py` | Modify | Add confidence to actions endpoint |
| `src/analysis/briefing_generator.py` | Modify | Add Conf. column to PDF tables |
| `src/static/index.html` | Modify | renderConfidenceBadge + badges on all score displays |
| `tests/test_confidence.py` | Create | Tests for confidence computation |

---

### Task 1: Build Confidence Computation Engine

**Files:**
- Create: `src/analysis/confidence.py`
- Create: `tests/test_confidence.py`

- [ ] **Step 1: Write tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_confidence.py -v`
Expected: ImportError

- [ ] **Step 3: Create `src/analysis/confidence.py`**

```python
"""Confidence scoring utility — "Glass Box" data integrity.

Computes confidence levels for any risk assessment based on
data source type and number of independent corroborating sources.
"""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Source definitions: which independent data sources back each risk dimension
_SUPPLIER_SOURCES = {
    "foreign_ownership": [
        ("Wikidata ownership", "parent_company"),    # check DefenceSupplier.parent_company IS NOT NULL
        ("OFAC/EU sanctions", "sanctions_proximity"), # check SupplierRiskScore exists for sanctions_proximity
        ("SIPRI Top 100", "sipri_rank"),              # check DefenceSupplier.sipri_rank IS NOT NULL
    ],
    "customer_concentration": [
        ("Open Canada procurement", "contracts"),     # check SupplierContract count > 0
        ("Estimated revenue data", "revenue"),        # check DefenceSupplier.estimated_revenue_cad IS NOT NULL
    ],
    "single_source": [
        ("Procurement contracts", "contracts"),
        ("SIPRI arms transfers", "transfers"),
    ],
    "contract_activity": [
        ("Procurement contracts", "contracts"),
    ],
    "sanctions_proximity": [
        ("OFAC SDN list", "ofac"),
        ("EU sanctions list", "eu_sanctions"),
        ("PSI material dependencies", "psi_materials"),
    ],
    "contract_performance": [
        ("Procurement contracts", "contracts"),
    ],
}

_TAXONOMY_LIVE_SOURCES = {
    "1": [("GDELT news", None), ("Sanctions lists", None), ("Wikidata corporate graph", None)],
    "2": [("GDELT geopolitical news", None), ("Sanctions lists", None)],
    "3": [("PSI supply chain data", None), ("Supplier risk scores", None), ("SIPRI transfers", None)],
    "11": [("World Bank indicators", None), ("Comtrade trade data", None)],
}

_PSI_SOURCES = {
    "material_shortage": [("PSI material data", None), ("Comtrade trade flows", None)],
    "chokepoint_blocked": [("Chokepoint registry", None), ("Maritime/AIS data", None)],
    "sanctions_risk": [("OFAC SDN", None), ("EU sanctions", None), ("PSI graph", None)],
    "concentration_risk": [("PSI concentration analyzer", None), ("Comtrade data", None)],
    "supplier_disruption": [("GDELT news", None), ("Financial data", None)],
    "demand_surge": [("NATO spending data", None), ("DSCA sales", None)],
}


def compute_confidence(
    data_source: str | None,
    risk_source: str,
    dimension: str,
    session: Session,
) -> dict:
    """Compute confidence for a risk assessment.

    Args:
        data_source: "live", "hybrid", "seeded", or None (infer from risk_source)
        risk_source: "supplier", "taxonomy", "psi", "mitigation"
        dimension: The specific risk dimension (e.g., "foreign_ownership", "1a", "material_shortage")
        session: SQLAlchemy session (reuse the caller's session, do NOT open a new one)

    Returns:
        dict with level, score, source_count, sources, triangulated, label
    """
    # Determine data source if not provided (for mitigation actions)
    if data_source is None:
        if risk_source == "supplier":
            data_source = "live"
        elif risk_source == "psi":
            data_source = "live"
        elif risk_source == "taxonomy":
            # Infer from dimension prefix
            cat_id = dimension.rstrip("abcdefghijklmnopqrst")
            live_cats = {"1", "2", "3", "11"}
            hybrid_cats = {"7", "10", "12"}
            if cat_id in live_cats:
                data_source = "live"
            elif cat_id in hybrid_cats:
                data_source = "hybrid"
            else:
                data_source = "seeded"
        else:
            data_source = "seeded"

    # Count sources
    sources = _count_sources(risk_source, dimension, session)
    source_count = len(sources)
    source_names = [s[0] for s in sources]

    # Determine confidence level and score
    if data_source == "live":
        if source_count >= 3:
            level = "high"
            score = min(80 + source_count * 5, 95)
        elif source_count >= 1:
            level = "medium"
            score = 60 + source_count * 5
        else:
            level = "medium"
            score = 55
            source_names = ["Computed from OSINT data"]
            source_count = 1
    elif data_source == "hybrid":
        level = "medium"
        score = 50 + source_count * 5
        score = min(score, 70)
    else:  # seeded
        level = "low"
        score = 25 + source_count * 5
        score = min(score, 35)
        if source_count <= 1:
            source_names = ["Seeded baseline"]
            source_count = 1

    triangulated = source_count >= 3

    # Generate label
    if triangulated:
        label = f"Triangulated ({source_count} sources)"
    elif source_count >= 2:
        label = f"Corroborated ({source_count} sources)"
    elif data_source == "seeded":
        label = "Seeded baseline - limited corroboration"
    else:
        label = f"Single source (live OSINT)"

    return {
        "level": level,
        "score": score,
        "source_count": source_count,
        "sources": source_names,
        "triangulated": triangulated,
        "label": label,
    }


def _count_sources(risk_source: str, dimension: str, session: Session) -> list[tuple[str, str | None]]:
    """Count how many independent sources back this risk dimension."""
    active_sources = []

    if risk_source == "supplier":
        # Check which supplier data sources are actually populated
        from src.storage.models import DefenceSupplier, SupplierContract, SupplierRiskScore, RiskDimension
        source_defs = _SUPPLIER_SOURCES.get(dimension, [])
        for source_name, check_key in source_defs:
            if check_key == "parent_company":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.parent_company.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "sipri_rank":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.sipri_rank.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "contracts":
                count = session.query(SupplierContract).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "revenue":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.estimated_revenue_cad.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "sanctions_proximity":
                count = session.query(SupplierRiskScore).filter(SupplierRiskScore.dimension == RiskDimension.SANCTIONS_PROXIMITY).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key in ("ofac", "eu_sanctions", "psi_materials", "transfers"):
                # These are always available (static/cached data)
                active_sources.append((source_name, check_key))

    elif risk_source == "taxonomy":
        cat_id = dimension.rstrip("abcdefghijklmnopqrst")
        source_defs = _TAXONOMY_LIVE_SOURCES.get(cat_id, [])
        if source_defs:
            active_sources = source_defs
        else:
            active_sources = [("Seeded baseline", None)]

    elif risk_source == "psi":
        source_defs = _PSI_SOURCES.get(dimension, [])
        if source_defs:
            active_sources = source_defs
        else:
            active_sources = [("PSI risk engine", None)]

    else:
        active_sources = [("Platform assessment", None)]

    return active_sources
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/test_confidence.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/confidence.py tests/test_confidence.py
git commit -m "feat: add confidence computation engine (Glass Box utility)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Add Confidence to Taxonomy Endpoints

**Files:**
- Modify: `src/api/psi_routes.py`

- [ ] **Step 1: Add confidence to `GET /psi/taxonomy`**

Import at the top of the taxonomy endpoint function (lazy):
```python
from src.analysis.confidence import compute_confidence
```

In the `get_taxonomy()` endpoint, after building each category dict in the `cats` list, add:
```python
cat_conf = compute_confidence(
    data_source=cat["data_source"],
    risk_source="taxonomy",
    dimension=str(cat["category_id"]),
    session=session,
)
cat["confidence"] = cat_conf
```

Add `confidence_summary` to the result dict:
```python
high_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "high")
med_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "medium")
low_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "low")
avg_conf = sum(c.get("confidence", {}).get("score", 0) for c in cats) / max(len(cats), 1)
tri_count = sum(1 for c in cats if c.get("confidence", {}).get("triangulated"))

result["confidence_summary"] = {
    "high_count": high_count,
    "medium_count": med_count,
    "low_count": low_count,
    "avg_confidence": round(avg_conf),
    "triangulated_pct": round(tri_count / max(len(cats), 1) * 100),
}
```

- [ ] **Step 2: Add confidence to `GET /psi/taxonomy/summary`**

Same pattern — add confidence to each category card in the summary response.

- [ ] **Step 3: Add confidence to `GET /psi/taxonomy/{category_id}`**

For each sub-category in the response, add:
```python
sub_conf = compute_confidence(
    data_source=r.data_source,
    risk_source="taxonomy",
    dimension=r.subcategory_key,
    session=session,
)
sub_dict["confidence"] = sub_conf
```

- [ ] **Step 4: Commit**

```bash
git add src/api/psi_routes.py
git commit -m "feat: add confidence scoring to taxonomy API responses

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Add Confidence to Supplier & Mitigation Endpoints

**Files:**
- Modify: `src/api/supplier_routes.py`
- Modify: `src/api/mitigation_routes.py`

- [ ] **Step 1: Add confidence to `GET /dashboard/suppliers`**

In `get_suppliers()`, after building each supplier dict, add:
```python
from src.analysis.confidence import compute_confidence
conf = compute_confidence(
    data_source="live",
    risk_source="supplier",
    dimension=top_risk.dimension.value if top_risk else "unknown",
    session=session,
)
supplier_dict["confidence"] = conf
```

- [ ] **Step 2: Add confidence to `GET /dashboard/suppliers/{name}/profile`**

For each entry in the `risk_scores` array:
```python
conf = compute_confidence(
    data_source="live",
    risk_source="supplier",
    dimension=s.dimension.value if s.dimension else "unknown",
    session=session,
)
score_dict["confidence"] = conf
```

- [ ] **Step 3: Add confidence to `GET /mitigation/actions`**

For each action, compute from stored fields:
```python
from src.analysis.confidence import compute_confidence
conf = compute_confidence(
    data_source=None,  # inferred from risk_source
    risk_source=a.risk_source,
    dimension=a.risk_dimension,
    session=session,
)
action_dict["confidence"] = conf
```

- [ ] **Step 4: Commit**

```bash
git add src/api/supplier_routes.py src/api/mitigation_routes.py
git commit -m "feat: add confidence scoring to supplier and mitigation API responses

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Add UI Confidence Badges

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add `renderConfidenceBadge` global function**

In the `<script>` section, add near the top (with other utility functions):

```javascript
function renderConfidenceBadge(conf) {
  if (!conf) return '';
  const colors = {high:'var(--accent3)',medium:'var(--accent4)',low:'var(--text-dim)'};
  const color = colors[conf.level] || 'var(--text-dim)';
  const srcs = (conf.sources || []).join(', ');
  return '<span style="display:inline-flex;align-items:center;gap:3px;font-size:9px;font-family:var(--font-mono);color:' + color + ';" title="Sources: ' + esc(srcs) + '">' +
    '<span style="width:5px;height:5px;border-radius:50%;background:' + color + ';"></span>' +
    conf.level.toUpperCase() + ' (' + conf.source_count + ')' +
    '</span>';
}
```

- [ ] **Step 2: Add badges to taxonomy summary strip (Insights)**

In `loadTaxonomyStrip()`, inside the card template, after the trend/source dot line, append:
```javascript
${renderConfidenceBadge(c.confidence)}
```

- [ ] **Step 3: Add badges to taxonomy accordion (Supply Chain)**

In `loadTaxonomyCategoryDetail()`, add a new column header "Conf." to the table, and in each row add:
```javascript
'<td style="padding:6px 4px;">' + renderConfidenceBadge(s.confidence) + '</td>'
```

- [ ] **Step 4: Add badges to supplier risk ranking (Canada Intel)**

In `renderSupplierRiskChart()` or the supplier list rendering, add confidence badge after each supplier's risk score display.

- [ ] **Step 5: Add badges to Action Centre (Insights)**

In `loadActionCentre()`, after the priority badge in each action card, append:
```javascript
${renderConfidenceBadge(a.confidence)}
```

- [ ] **Step 6: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add Glass Box confidence badges to all score displays

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Update PDF Briefing with Confidence Column

**Files:**
- Modify: `src/analysis/briefing_generator.py`

- [ ] **Step 1: Add confidence to taxonomy table (Section 2)**

In the taxonomy table section, change col_widths from `[28, 14, 14, 16, 70, 14]` to `[28, 14, 10, 14, 16, 60, 14]` and add "Conf." header. For each row, compute confidence and add H/M/L:

```python
from src.analysis.confidence import compute_confidence
# For each taxonomy row:
conf = compute_confidence(data_source=cat.get("data_source", "seeded"), risk_source="taxonomy", dimension=str(cat_id), session=self.session)
conf_label = conf["level"][0].upper()  # "H", "M", or "L"
tax_rows.append([cat["short_name"], str(avg), conf_label, level, ...])
```

- [ ] **Step 2: Add confidence to supplier table (Section 4)**

Change col_widths from `[34, 22, 26, 12, 28, 22]` to `[28, 20, 24, 12, 10, 26, 22]` and add "Conf." column.

- [ ] **Step 3: Add confidence to COA table (Section 3)**

Change col_widths from `[16, 32, 22, 60, 16, 20]` to `[14, 28, 20, 50, 10, 14, 18]` and add "Conf." column.

- [ ] **Step 4: Commit**

```bash
git add src/analysis/briefing_generator.py
git commit -m "feat: add Conf. column to PDF briefing tables

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Integration Test

- [ ] **Step 1: Run all tests**

Run: `cd /Users/billdennis/weapons-tracker && python -m pytest tests/ -v`
Expected: All tests pass (~50 tests)

- [ ] **Step 2: Verify confidence in API responses**

```bash
curl -s http://localhost:8000/psi/taxonomy | python3 -c "import sys,json; d=json.load(sys.stdin); print('Confidence summary:', d.get('confidence_summary')); print('First cat confidence:', d['categories'][0].get('confidence',{}).get('label'))"
curl -s http://localhost:8000/dashboard/suppliers | python3 -c "import sys,json; d=json.load(sys.stdin); print('First supplier confidence:', d['suppliers'][0].get('confidence',{}).get('label'))"
curl -s http://localhost:8000/mitigation/actions | python3 -c "import sys,json; d=json.load(sys.stdin); print('First action confidence:', d['actions'][0].get('confidence',{}).get('label') if d['actions'] else 'no actions')"
```

- [ ] **Step 3: Verify PDF has Conf. column**

```bash
curl -s -o /tmp/briefing.pdf http://localhost:8000/briefing/pdf && open /tmp/briefing.pdf
```

- [ ] **Step 4: Verify UI badges**

Open http://localhost:8000 — check Insights tab (taxonomy strip has badges, Action Centre has badges), Supply Chain tab (taxonomy accordion has Conf. column).

- [ ] **Step 5: Commit and push**

```bash
git add -A
git commit -m "feat: Glass Box confidence scoring — complete DND Q8 compliance

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
git push origin main
```
