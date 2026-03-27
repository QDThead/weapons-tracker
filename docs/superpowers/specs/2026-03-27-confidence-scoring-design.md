# Confidence Scoring — "Glass Box" Data Integrity

**Date:** 2026-03-27
**Status:** Approved
**Goal:** Add confidence levels, source counts, and triangulation indicators to every risk assessment, addressing DND Q8 (Data Integrity & Confidence Testing) — the "Glass Box" philosophy.

## Context

The bid promises a "Zero Trust / Glass Box" data approach where every insight is accompanied by a confidence score, source count, and data lineage. DND evaluators need to trust the platform's outputs. Currently, scores are displayed without any indication of how reliable they are. This enhancement adds transparency without changing any underlying scoring logic.

## Approach

A shared utility function `compute_confidence()` dynamically calculates confidence for any risk score based on its data source type and the number of independent sources that contributed. No new tables or columns — confidence is computed on the fly from existing data. The result is added to existing API responses as an additive `confidence` field. UI renders a compact badge everywhere scores appear.

## Confidence Computation Engine

### File: `src/analysis/confidence.py`

Must include `from __future__ import annotations`.

### Core Function

`compute_confidence(data_source: str, risk_source: str, dimension: str, session: Session) -> dict`

Returns:
```python
{
    "level": "high",          # high / medium / low
    "score": 85,              # 0-100 numeric confidence
    "source_count": 3,        # independent sources
    "sources": ["SIPRI transfers", "Wikidata ownership", "OFAC sanctions"],
    "triangulated": True,     # 3+ sources
    "label": "Triangulated (3 sources)"
}
```

### Confidence Level Matrix

| Data Source Type | Source Count | Level | Score Range |
|---|---|---|---|
| live + 3+ sources | >= 3 | **high** | 80-95 |
| live + 1-2 sources | 1-2 | **medium** | 60-75 |
| hybrid + any | any | **medium** | 50-70 |
| seeded | 1 | **low** | 20-35 |

### Source Counting Logic

The function counts independent data sources that could corroborate each score. Counts are determined by `(risk_source, dimension)` pattern:

**Supplier risk dimensions:**

| Dimension | Possible Sources | Max Count |
|---|---|---|
| foreign_ownership | Wikidata ownership graph, OFAC/EU sanctions lists, SIPRI Top 100 company data | 3 |
| customer_concentration | Open Canada procurement contracts, estimated revenue data | 2 |
| single_source | Procurement contracts, SIPRI arms transfers | 2 |
| contract_activity | Procurement contracts | 1 |
| sanctions_proximity | OFAC SDN list, EU sanctions list, PSI material dependencies | 3 |
| contract_performance | Procurement contracts | 1 |

Source count adjusts based on what data is actually present in the DB. Concrete presence checks:
- **Wikidata source present:** `DefenceSupplier.parent_company IS NOT NULL` for the specific supplier
- **SIPRI source present:** `DefenceSupplier.sipri_rank IS NOT NULL` for the specific supplier
- **Sanctions source present:** `SupplierRiskScore` row exists for `sanctions_proximity` dimension
- **Procurement source present:** `SupplierContract` count > 0 for the supplier
This prevents overcounting when data isn't loaded.

**Taxonomy sub-categories:**

| Category Data Source | Sources | Count |
|---|---|---|
| live (FOCI, Political, Manufacturing, Economic) | Multiple OSINT feeds (news, sanctions, transfers, indicators) | 2-4 depending on category |
| hybrid (Transport, Compliance, Financial) | Partial OSINT + seeded baseline | 1-2 |
| seeded (Cyber, Infrastructure, Planning, Human Capital, Environmental, Quality) | Seeded baseline only | 1 |

**PSI alerts:** Count based on alert type — `material_shortage` backed by PSI material data + Comtrade = 2; `chokepoint_blocked` backed by chokepoint registry + AIS data = 2; etc.

**Mitigation actions:** Inherit confidence from the underlying risk score. The function looks up the source risk and delegates.

### Label Generation

| Triangulated | Source Count | Label |
|---|---|---|
| true | 3+ | "Triangulated (N sources)" |
| false | 2 | "Corroborated (2 sources)" |
| false | 1, live | "Single source (live OSINT)" |
| false | 1, seeded | "Seeded baseline — limited corroboration" |

## API Response Enhancement

No new endpoints. Add an additive `confidence` field to responses from 5 existing endpoints. Existing consumers that don't read this field are unaffected.

### Modified Endpoints

**1. `GET /psi/taxonomy`** — Each category in `categories` array gets `confidence` dict. Add `confidence_summary` to top level. The `confidence_summary.triangulated_pct` = `(count of categories where triangulated==true / 13) * 100`, rounded to integer.
```json
{
  "confidence_summary": {
    "high_count": 4,
    "medium_count": 3,
    "low_count": 6,
    "avg_confidence": 58,
    "triangulated_pct": 31
  }
}
```
**Also add confidence to `GET /psi/taxonomy/summary`** — each card object gets `confidence` dict. The summary endpoint must expose `data_source` in its response (it already has it in the category data from `compute_category_composites`).

**2. `GET /psi/taxonomy/{category_id}`** — Each sub-category in `subcategories` array gets `confidence` dict.

**3. `GET /dashboard/suppliers`** — Each supplier in `suppliers` array gets `confidence` dict (computed from their highest-risk dimension's confidence).

**4. `GET /dashboard/suppliers/{name}/profile`** — Each entry in `risk_scores` array (note: the field is named `risk_scores` in the response, not `risk_dimensions`) gets `confidence` dict.

**5. `GET /mitigation/actions`** — Each action in `actions` array gets `confidence` dict. Since `MitigationAction` has no FK back to the originating risk record, confidence is computed from the stored `risk_score` and `risk_source` fields directly: use `risk_source` to determine data source type (supplier=live, taxonomy=varies by dimension prefix, psi=live), and `risk_score` to infer source count heuristically. This avoids a complex join.

### Implementation Pattern

Each endpoint imports `compute_confidence` and calls it while building the response dict. **Important: pass the endpoint's existing session — do not open a new SessionLocal() inside `compute_confidence`.** This prevents session leaks inside cached response paths.

```python
from src.analysis.confidence import compute_confidence

# Inside endpoint, for each supplier (using the endpoint's existing session):
conf = compute_confidence(
    data_source="live",
    risk_source="supplier",
    dimension=top_risk.dimension.value if top_risk else "unknown",
    session=session,  # <-- reuse the endpoint's session
)
supplier_dict["confidence"] = conf
```

### Caching

Confidence computation is lightweight (a few DB count queries). The existing endpoint-level caching (5 min - 1 hour TTL) already handles this — confidence is computed once per cache cycle, not per request.

## UI: Confidence Badges

### Shared Function

`renderConfidenceBadge(confidence)` — global JS function returning HTML:

```javascript
function renderConfidenceBadge(conf) {
  if (!conf) return '';
  const colors = {high:'var(--accent3)',medium:'var(--accent4)',low:'var(--text-dim)'};
  const color = colors[conf.level] || 'var(--text-dim)';
  return `<span style="display:inline-flex;align-items:center;gap:3px;font-size:9px;color:${color};"
    title="Sources: ${(conf.sources||[]).join(', ')}">
    <span style="width:5px;height:5px;border-radius:50%;background:${color};"></span>
    ${conf.level.toUpperCase()} (${conf.source_count})
  </span>`;
}
```

### Where It Renders

1. **Taxonomy summary strip (Insights)** — Bottom-right of each card, after the trend arrow
2. **Taxonomy accordion (Supply Chain)** — New column in sub-category table between Score and PSI Module
3. **Supplier risk ranking chart (Canada Intel)** — Below each supplier name in the bar chart labels area
4. **Supplier profile risk dimensions** — Inline after each dimension score
5. **Action Centre (Insights)** — After the priority badge on each COA row
6. **PDF Briefing** — Add "Conf." column to taxonomy and supplier tables in the PDF

### Design System

- High: `--accent3` (green) dot + "HIGH"
- Medium: `--accent4` (amber) dot + "MED"
- Low: `--text-dim` (gray) dot + "LOW"
- Font: 9px, `--font-mono`
- Tooltip: native `title` attribute showing source list

## PDF Briefing Update

Add a "Conf." column (narrow, 10mm width) to:
- Risk Taxonomy table (Section 2) — shows H/M/L per category. Shrink "Worst Sub-Category" column from 70mm to 60mm to make room.
- Supplier Exposure table (Section 4) — shows H/M/L per supplier. Shrink "Supplier" column from 34mm to 28mm.
- Priority Actions table (Section 3) — shows H/M/L per COA. Shrink "Recommended Action" column from 60mm to 50mm.

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/analysis/confidence.py` | New | Shared confidence computation utility. Must include `from __future__ import annotations` |
| `src/api/psi_routes.py` | Modified | Add confidence to taxonomy endpoints |
| `src/api/supplier_routes.py` | Modified | Add confidence to supplier endpoints |
| `src/api/mitigation_routes.py` | Modified | Add confidence to actions endpoint |
| `src/analysis/briefing_generator.py` | Modified | Add Conf. column to PDF tables |
| `src/static/index.html` | Modified | Add renderConfidenceBadge + badges on all score displays |
| `tests/test_confidence.py` | New | Tests for confidence computation |

## Out of Scope

- Full evidence chain / "Evidence Locker" (per-record data lineage)
- User-configurable confidence thresholds
- Confidence-based alert suppression (hide low-confidence alerts)
- Historical confidence tracking (confidence trends over time)
- Confidence in the PDF cover page summary
