# DND Annex B Risk Taxonomy — Full 13-Category Compliance

**Date:** 2026-03-25
**Status:** Approved
**Goal:** Implement all 13 DND/CAF Defence Supply Chain Risk Taxonomy categories (117 sub-categories) with live OSINT scoring where available and realistic seeded data with time-based drift for the remainder, displayed on both the Insights landing page and the Supply Chain tab.

## Context

The DND DMPP 11 RFI (Annex B) defines 13 risk categories with 117 sub-categories as the evaluation rubric for a Defence Supply Chain Control Tower. QDT's bid (Appendix A) maps each sub-category to a PSI module. The weapons-tracker demo must show compliance with all 13 categories. Currently ~4 are covered by existing features. This spec closes the gap.

## Data Source Strategy

Categories are classified by data backing:

| Type | Categories | Approach |
|------|-----------|----------|
| **Live** | 1-FOCI, 2-Political/Regulatory, 3-Manufacturing/Supply, 11-Economic | Computed from existing OSINT data (sanctions, suppliers, Comtrade, World Bank, GDELT) |
| **Hybrid** | 7-Transportation, 10-Compliance, 12-Financial | Partial real data (chokepoints, sanctions, supplier contracts) + seeded baselines |
| **Seeded** | 4-Cyber, 5-Infrastructure, 6-Planning, 8-Human Capital, 9-Environmental, 13-Product Quality | Realistic hand-tuned baselines with +/- 5 point random drift per scoring cycle |

## Data Model

### Table: `risk_taxonomy_scores`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer PK | Auto-increment | |
| category_id | Integer | Not null | 1-13, maps to DND risk categories |
| category_name | String(100) | Not null | e.g., "Foreign Ownership, Control, or Influence (FOCI)" |
| subcategory_key | String(10) | Not null | e.g., "1a", "3f", "12k" |
| subcategory_name | String(200) | Not null | e.g., "Theft of trade secrets", "Single source" |
| score | Float | Not null | Current risk score 0-100 |
| baseline_score | Float | Not null | Seed baseline for drift calculation |
| data_source | String(10) | Not null | "live", "seeded", or "hybrid" |
| psi_module | String(100) | | PSI module name from bid Appendix A |
| rationale | Text | | Human-readable explanation of current score |
| last_event | Text | | Most recent event/alert text for this sub-category |
| scored_at | DateTime | default=datetime.utcnow | When this score was last computed |

**Constraints:** `UniqueConstraint("subcategory_key", name="uq_taxonomy_subcat")`
**Index:** `Index("ix_taxonomy_category", "category_id")`

**Persistence:** The `upsert_taxonomy_score` method queries by `subcategory_key` to find existing rows before updating. This matches the uniqueness constraint.

## 13 Categories and Sub-Category Counts

Sourced directly from bid Appendix A:

| ID | Category | Sub-categories | Data Source |
|----|----------|---------------|-------------|
| 1 | FOCI | 15 (a-o) | Live |
| 2 | Political & Regulatory | 6 (a-f) | Live |
| 3 | Manufacturing & Supply | 20 (a-t) | Live |
| 4 | Technology & Cybersecurity | 10 (a-j) | Seeded |
| 5 | Infrastructure | 6 (a-f) | Seeded |
| 6 | Planning | 4 (a-d) | Seeded |
| 7 | Transportation & Distribution | 7 (a-g) | Hybrid |
| 8 | Human Capital | 5 (a-e) | Seeded |
| 9 | Environmental | 7 (a-g) | Seeded |
| 10 | Compliance | 16 (a-p) | Hybrid |
| 11 | Economic | 8 (a-h) | Live |
| 12 | Financial | 11 (a-k) | Hybrid |
| 13 | Product Quality & Design | 6 (a-f) | Seeded |

**Total: 121 sub-categories.** The bid executive summary references 117; the full Appendix A count is 121. The demo implements all 121 from Appendix A (the authoritative source). The 4-count difference is likely due to sub-categories added during bid finalization.

## Scoring Engine

### File: `src/analysis/risk_taxonomy.py`

A `RiskTaxonomyScorer` class with:

**Seed definitions:** A hardcoded `TAXONOMY_DEFINITIONS` dict defining all 13 categories and their 121 sub-categories, matching the bid's Appendix A exactly. PSI module names are defined as a `PSI_MODULES` constant dict (e.g., `PSI_MODULES = {"ubo_graph": "UBO Graph", "cyber_threat": "Cyber Threat Intelligence", ...}`) to avoid magic strings. Each sub-category entry has:
- `subcategory_key`, `subcategory_name`, `psi_module` (reference to PSI_MODULES key)
- `baseline_score` (hand-tuned realistic default, 0-100)
- `data_source` ("live", "hybrid", "seeded")
- `last_event` (static example event text for seeded categories)

**Live scoring methods** — for categories 1, 2, 3, 11:
- **FOCI (1):** Imports and calls `SupplierRiskScorer` from `src/analysis/supplier_risk.py` (reuse, don't duplicate) for foreign ownership and sanctions proximity scores. Sub-categories like "Theft of trade secrets" (1a) pull from news data, "Partnership with state-owned company" (1c) from Wikidata ownership, "Weaponized M&A" (1d) from corporate graph changes. **Graceful degradation:** If `defence_suppliers` table is empty, falls back to seeded baseline values rather than returning 0.
- **Political/Regulatory (2):** Queries sanctions embargo counts, GDELT geopolitical news volume, arms trade policy changes from existing data.
- **Manufacturing/Supply (3):** Queries PSI `SupplyChainAnalyzer` from `src/analysis/supply_chain.py` for concentration scores, supplier single-source counts from `supplier_risk.py`, material scarcity from `SupplyChainMaterial`.
- **Economic (11):** Queries World Bank indicators (GDP, military spending), commodity price trends from Comtrade data.

**Hybrid scoring** — for categories 7, 10, 12:

- **Transportation (7):** Chokepoint status from PSI (real) + seeded baselines for sub-categories like "logistics inelasticity" and "loss of cargo".
- **Compliance (10):** Sanctions watchlist data (real) for sub-categories like "import/export violation" + seeded baselines for "forced labour", "conflict minerals", etc.
- **Financial (12):** Queries supplier contract activity and customer concentration from `supplier_risk.py` when `supplier_contracts` table has data. **Graceful degradation:** Falls back to seeded baselines when contract data is empty (common in fresh demo environments).

**Seeded scoring with drift** — for categories 4, 5, 6, 8, 9, 13:
- `score = clamp(baseline_score + random.uniform(-5, +5), 0, 100)`
- Drift applied per scoring cycle (every 6 hours)
- `last_event` is static text set at seed time (e.g., "CVE-2026-1234 reported in supplier ERP system")

**Composite calculations:**
- Category composite = mean of sub-category scores within that category
- Global composite = weighted mean of 13 category composites (equal weights for demo, configurable)

**Risk thresholds:**
- Green (0-39): Low risk
- Amber (40-69): Moderate risk
- Red (70-100): High risk

**Trend computation:** Trend is derived by comparing `score` to `baseline_score` (no history table needed):
- `score > baseline + 3` → "rising" (risk increasing)
- `score < baseline - 3` → "falling" (risk decreasing)
- Otherwise → "stable"

### Scheduler Integration

Add to `src/ingestion/scheduler.py`:
- `taxonomy_scoring`: every 6 hours (`IntervalTrigger(hours=6)`), `replace_existing=True`, `max_instances=1`
- Runs `RiskTaxonomyScorer.score_all()` which refreshes live categories from real data and applies drift to seeded categories

## API Endpoints

Added to `src/api/psi_routes.py` (3 new endpoints):

### `GET /psi/taxonomy`

All 13 categories with composites:

```json
{
  "global_composite": 52,
  "global_risk_level": "amber",
  "categories": [
    {
      "category_id": 1,
      "category_name": "Foreign Ownership, Control, or Influence (FOCI)",
      "short_name": "FOCI",
      "composite_score": 58,
      "risk_level": "amber",
      "data_source": "live",
      "subcategory_count": 15,
      "worst_subcategory": "Partnership with state-owned company",
      "worst_score": 78,
      "trend": "rising"
    }
  ],
  "live_count": 4,
  "hybrid_count": 3,
  "seeded_count": 6,
  "last_scored": "2026-03-25T15:00:00Z"
}
```

### `GET /psi/taxonomy/{category_id}`

**Route ordering:** This endpoint MUST be registered AFTER `/psi/taxonomy/summary` to avoid FastAPI matching "summary" as a `category_id`. The `category_id` parameter is typed as `int` to further disambiguate.

Single category with all sub-categories:

```json
{
  "category_id": 1,
  "category_name": "Foreign Ownership, Control, or Influence (FOCI)",
  "composite_score": 58,
  "data_source": "live",
  "subcategories": [
    {
      "key": "1a",
      "name": "Theft of trade secrets",
      "score": 42,
      "psi_module": "Legal & Reputational Monitor",
      "data_source": "live",
      "rationale": "2 IP litigation cases detected involving DND suppliers in last 90 days",
      "last_event": "Patent dispute: CAE vs. competitor re: simulation IP (Feb 2026)"
    }
  ]
}
```

### `GET /psi/taxonomy/summary`

Dashboard-ready summary for Insights page cards:

```json
{
  "global_composite": 52,
  "categories": [
    {
      "category_id": 1,
      "short_name": "FOCI",
      "icon": "shield",
      "score": 58,
      "risk_level": "amber",
      "trend": "stable",
      "data_source": "live"
    }
  ]
}
```

All endpoints cached 1 hour (`_PSI_TAXONOMY_TTL = 3600`), matching the PSI graph cache TTL. Since seeded data only drifts every 6 hours, a shorter TTL wastes cache invalidations.

## UI: Two Locations

### 1. Insights Tab — Summary Strip (Section 0)

Inserted in the Insights page DOM between `#freshness-banner` and Section 1 (Situation Report). The freshness banner remains above (it's conditionally shown and collapses when hidden).

**Header:** "Defence Supply Chain Risk Taxonomy" with a global composite score badge and a small legend: green dot "Live Data" / gray dot "Seeded"

**Layout:** A grid of 13 compact cards (either 1 scrollable row on wide screens, or `grid-template-columns: repeat(auto-fill, minmax(140px, 1fr))` for responsive wrapping). Each card shows:
- Icon (small SVG or emoji per category)
- Short category name (e.g., "FOCI", "Cyber", "Manufacturing")
- Composite score (large number, font-mono)
- Color stripe: green <40, amber 40-70, red >70
- Small "LIVE" or "SEEDED" badge
- Click navigates to Supply Chain tab taxonomy view

### 2. Supply Chain Tab — Risk Taxonomy Sub-Tab

New sub-tab "Risk Taxonomy" added to the PSI tab bar alongside Overview, Knowledge Graph, Risk Matrix, Scenario Sandbox.

**Top section:**
- Global composite score (large stat-num, color-coded)
- Horizontal bar chart (Chart.js): 13 categories sorted by risk score, color-coded green/amber/red
- Legend: "LIVE" green dot, "HYBRID" blue dot, "SEEDED" gray dot

**Below: Expandable accordion**
- One collapsible section per category
- Header shows: category name, composite score, data source badge, worst sub-category preview
- Expanded view: table of all sub-categories with columns:
  - Key | Name | Score | PSI Module | Source (live/seeded badge) | Last Event | Rationale
- Rows color-coded by score threshold

### Design System Compliance

All new UI elements use existing tokens:
- Colors: `--accent` through `--accent5`, risk thresholds (green/amber/red)
- Typography: `--font-display` for headings, `--font-mono` for scores
- Components: `.card`, `.stat-box`, `.stat-num`, `.insight-alert`
- Charts: Chart.js with IBM Plex Sans, new palette colors

### Category Icons

| ID | Short Name | Icon |
|----|-----------|------|
| 1 | FOCI | shield |
| 2 | Political | landmark |
| 3 | Manufacturing | factory |
| 4 | Cyber | lock |
| 5 | Infrastructure | building |
| 6 | Planning | calendar |
| 7 | Transportation | truck |
| 8 | Human Capital | users |
| 9 | Environmental | cloud |
| 10 | Compliance | scale |
| 11 | Economic | chart-line |
| 12 | Financial | dollar-sign |
| 13 | Quality | check-circle |

Icons rendered as small inline SVGs (no external icon library dependency).

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/storage/models.py` | Modified | Add `RiskTaxonomyScore` model |
| `src/analysis/risk_taxonomy.py` | New | Scorer with seed definitions, live scoring, drift logic |
| `src/storage/persistence.py` | Modified | Add upsert for taxonomy scores |
| `src/api/psi_routes.py` | Modified | Add 3 taxonomy endpoints |
| `src/ingestion/scheduler.py` | Modified | Add 6-hour taxonomy scoring job |
| `src/static/index.html` | Modified | Add Insights summary strip + Supply Chain taxonomy sub-tab |
| `scripts/seed_database.py` | Modified | Seed initial taxonomy scores on first run |

## Out of Scope

- DND internal data integration (ERP/SAP/DRMIS connectors)
- Real cyber threat intelligence feeds (CVE, breach databases)
- Real weather/environmental monitoring feeds
- Real labor statistics feeds
- French language UI support
- User-configurable category weights
