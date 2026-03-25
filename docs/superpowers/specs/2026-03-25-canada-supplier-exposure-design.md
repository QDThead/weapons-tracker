# Canadian Defence Supply Base Exposure Module

**Date:** 2026-03-25
**Status:** Approved
**Goal:** Score Canadian defence suppliers by exposure risk so DND decision-makers can answer "How vulnerable is our supply base?"

## Context

The platform tracks Canada as a buyer (supplier concentration, NATO spending, Arctic security) but knows nothing about Canada as a manufacturer/supplier. DND needs visibility into which companies supply the CAF, who owns them, how concentrated each sector is, and where the vulnerabilities lie.

## Data Sources

### Primary: Open Canada Procurement Disclosure

**URL:** `https://search.open.canada.ca/contracts/`

The Government of Canada's procurement disclosure portal. Contains 331,000+ National Defence records. Filters by department, vendor, solicitation procedure, and date range. The portal is server-rendered but backed by a Solr search endpoint that returns JSON — the scraper will discover and use the underlying API.

Parse:
- Vendor name (normalized to canonical form)
- Contract value (CAD)
- Description (classified into sector by keyword matching)
- Award date, end date
- Solicitation procedure (sole-source detection: "non-competitive" flag)

**Backfill range:** 2021-01-01 to present (5 calendar years).
**Schedule:** Weekly refresh via APScheduler.
**Rate limiting:** 1 request/second with exponential backoff. Paginate at 100 records per request.

### Enrichment: Wikidata Corporate Graph

For each supplier, call a new method on `corporate_graph.py` (`fetch_company_ownership(company_name)`) that queries Wikidata SPARQL for:
- Parent company (P749)
- Country of origin (P17)
- Subsidiaries (P355)

Populates ownership chain and foreign-control status.

### Enrichment: SIPRI Top 100

Cross-reference against existing `sipri_companies.py` data to flag globally-ranked firms and their relative position.

## Data Model

**Naming note:** Uses "defence" (Canadian/British spelling) for new tables since this module is Canada-specific and targets DND. The existing `defense_companies` table retains American spelling for backwards compatibility.

All new Python files must include `from __future__ import annotations` per project convention.

### Table: `defence_suppliers`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer PK | Auto-increment | |
| name | String(200) | UniqueConstraint("uq_supplier_name") | Canonical display name (dedup key) |
| legal_name | String(300) | | Full legal entity name |
| headquarters_city | String(100) | | City |
| headquarters_province | String(50) | | Province/territory |
| parent_company | String(200) | Nullable | Parent entity name |
| parent_country | String(100) | Nullable | Parent country of origin |
| ownership_type | Enum | | canadian_private, canadian_public, foreign_subsidiary, crown_corp, joint_venture |
| sipri_rank | Integer | Nullable | Rank in SIPRI Top 100 |
| wikidata_id | String(20) | Nullable | Wikidata Q-identifier |
| sector | Enum | | See unified sector enum below |
| estimated_revenue_cad | Float | Nullable | Annual total company revenue estimate (from SEDAR/public data, used for customer concentration calculation) |
| dnd_contract_revenue_cad | Float | App-level computed | Sum of active DND contract values, populated by the weekly scoring cron job (not a DB-level generated column, since SQLite has limited support) |
| employee_count | Integer | Nullable | |
| risk_score_composite | Float | | 0-100, computed from dimension scores |
| created_at | DateTime | | Record creation |
| updated_at | DateTime | | Last update |

### Table: `supplier_contracts`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer PK | Auto-increment | |
| supplier_id | Integer FK | References defence_suppliers.id | |
| contract_number | String(100) | UniqueConstraint("uq_contract_number") | Government contract identifier (dedup key) |
| contract_value_cad | Float | | Total contract value in CAD |
| description | Text | | Contract description |
| department | String(50) | | Awarding department (DND, PSPC, CSA, etc.) |
| award_date | Date | | Contract award date |
| end_date | Date | Nullable | Expected/actual completion |
| status | Enum | | active, completed, terminated |
| sector | Enum | | Same unified sector enum as defence_suppliers |
| is_sole_source | Boolean | | True if solicitation_procedure = "non-competitive" |
| created_at | DateTime | | Record creation |

**Index:** `Index("ix_contract_supplier_date", "supplier_id", "award_date")` for scoring queries.

### Unified Sector Enum

Used on both `defence_suppliers.sector` and `supplier_contracts.sector`:

`shipbuilding, land_vehicles, aerospace, electronics, simulation, munitions, cyber, maintenance, services, other`

The supplier's sector is determined by their highest-value contract sector (mode by CAD value across all contracts).

### Table: `supplier_risk_scores`

| Column | Type | Description |
|--------|------|-------------|
| id | Integer PK | Auto-increment |
| supplier_id | Integer FK | References defence_suppliers.id |
| dimension | Enum | foreign_ownership, customer_concentration, single_source, contract_activity, sanctions_proximity, contract_performance |
| score | Float | 0-100, higher = more exposed |
| rationale | Text | Human-readable explanation |
| scored_at | DateTime | When this score was computed |

**Constraints:** `UniqueConstraint("supplier_id", "dimension", name="uq_score_supplier_dimension")` to support upsert.
**Index:** `Index("ix_risk_score_supplier", "supplier_id")` for profile lookups.

**Score persistence:** The weekly scoring cron job upserts scores (one row per supplier+dimension, replacing the previous score). The `scored_at` timestamp tracks when the latest computation ran. No historical scores are retained — this is consistent with how the platform computes risk on refresh rather than tracking trends over time. Endpoints read from this table.

## Ingestion Pipeline

### File: `src/ingestion/procurement_scraper.py`

Async connector using httpx. Steps:

1. Discover the Solr/search API endpoint behind search.open.canada.ca/contracts/
2. Query for National Defence contracts, paginating at 100 records per request, 1 req/sec
3. Normalize vendor names (strip "Inc.", "Ltd.", "Canada" suffixes; merge known aliases via alias table)
4. Classify each contract into a sector using keyword matching on the description (see heuristics below)
5. Upsert into `supplier_contracts` (dedup on `contract_number`)
6. Deduplicate: group contracts by normalized vendor, create/update `defence_suppliers` records (dedup on `name`)
7. Trigger enrichment pipeline

### Sector Classification Heuristics

Applied to each contract description to assign `supplier_contracts.sector`:

| Keywords | Sector |
|----------|--------|
| frigate, ship, vessel, naval, maritime | shipbuilding |
| LAV, vehicle, armoured, armored, tank | land_vehicles |
| aircraft, helicopter, jet, fighter, F-35, CF-18 | aerospace |
| radar, sensor, communications, radio, electronic | electronics |
| simulation, training, simulator | simulation |
| ammunition, munition, explosive, bomb, missile | munitions |
| cyber, software, IT, network, data | cyber |
| maintenance, repair, overhaul, MRO, sustainment | maintenance |
| consulting, advisory, professional, logistics | services |
| (no match) | other |

### Enrichment Pipeline

Runs after scraper completes:

1. **Wikidata enrichment** — For each supplier, call new `fetch_company_ownership(name)` method on `corporate_graph.py`. Populate `parent_company`, `parent_country`, `ownership_type`.
2. **SIPRI enrichment** — Match against `sipri_companies.py` data. Populate `sipri_rank`.
3. **Revenue estimation** — For publicly-traded suppliers, attempt to pull total revenue from Wikidata (P2139 = revenue). This provides the denominator for customer concentration scoring. If unavailable, leave null and use a conservative estimate (see Customer Concentration scoring below).

### Scheduler Integration

Add to `src/ingestion/scheduler.py`:
- `procurement_scraper`: weekly (Sunday 02:00)
- `supplier_enrichment`: weekly (Sunday 04:00, after scraper)
- `supplier_risk_scoring`: weekly (Sunday 05:00, after enrichment)

## Risk Scoring Engine

### File: `src/analysis/supplier_risk.py`

Computes 6 dimension scores per supplier. Each dimension produces a score from 0 (no risk) to 100 (critical risk) plus a text rationale. Scores are upserted into `supplier_risk_scores` (one row per supplier+dimension).

### Dimension Scoring Logic

**Foreign Ownership (weight: 20%)**
- 0: Canadian-owned (private or public), Crown corporation
- 30: Joint venture with allied nation
- 50: Subsidiary of allied-nation company (US, UK, EU, Australia, etc.)
- 75: Subsidiary of non-allied, non-adversary nation
- 90: Any ownership link to sanctioned or embargoed country
- Rationale includes parent company name and country.

**Customer Concentration (weight: 15%)**
- If `estimated_revenue_cad` is available: score = (`dnd_contract_revenue_cad` / `estimated_revenue_cad`) * 100
- If `estimated_revenue_cad` is null: score = 65 (conservative "unknown — likely concentrated" default, since most DND suppliers are defence-focused)
- >80% triggers "critical dependency on DND" rationale
- Rationale notes whether the score is based on actual revenue data or the conservative default.

**Single Source (weight: 25%)**
- For each sector, count how many suppliers have active DND contracts
- If this supplier is the only one in its sector: score 90
- If one of two: score 60
- If one of three+: score 20
- Rationale names the sector and competitor count.

**Contract Activity Trend (weight: 15%)**
- Measures DND engagement trajectory, not actual financial health (no balance sheet data available)
- Compare last 2 years of contract volume to prior 2 years
- Growing or stable: score 20
- Declining 10-30%: score 50
- Declining >30%: score 80
- No recent contracts (>2 years): score 90
- Rationale includes the trend direction and magnitude.

**Sanctions Proximity (weight: 10%)**
- Cross-reference `parent_country` against `sanctions.py` embargo list
- Cross-reference known material dependencies from PSI module
- 0: No sanctions exposure
- 40: Parent country has partial sanctions
- 70: Depends on materials from sanctioned sources
- 90: Parent country is fully embargoed
- Rationale names the sanctioned connection.

**Contract Performance (weight: 15%)**
- Calculate ratio: terminated contracts / total contracts
- 0 terminated: score 10
- <10% terminated: score 30
- 10-25% terminated: score 60
- >25% terminated: score 85
- Rationale includes count and ratio.

**Composite Score** = weighted average of all 6 dimensions, rounded to integer.

### Risk Thresholds

- **Green (0-39):** Low exposure. Monitor normally.
- **Amber (40-69):** Moderate exposure. Review annually.
- **Red (70-100):** High exposure. Requires mitigation plan.

## API Endpoints

### File: `src/api/supplier_routes.py` (new)

Dedicated route file following the pattern of `arctic_routes.py` and `psi_routes.py`. Keeps `dashboard_routes.py` from growing too large.

**Note:** The `/dashboard/suppliers/alerts` endpoint is specific to supplier dimension scores >70. The existing `/psi/alerts` endpoint covers material/supply-chain alerts. These are complementary — the Canada Intel tab calls the supplier alerts endpoint, the Supply Chain tab continues using PSI alerts.

### `GET /dashboard/suppliers`

Returns all Canadian defence suppliers with composite risk scores, sorted by risk descending.

```json
{
  "suppliers": [
    {
      "name": "Irving Shipbuilding",
      "sector": "shipbuilding",
      "ownership_type": "canadian_private",
      "parent_company": null,
      "contract_value_total_cad": 30000000000,
      "active_contracts": 12,
      "risk_score_composite": 72,
      "risk_level": "red",
      "top_risk_dimension": "single_source"
    }
  ],
  "total_suppliers": 28,
  "avg_risk_score": 48
}
```

### `GET /dashboard/suppliers/{name}/profile`

Single supplier detail with all contracts, all 6 risk dimension scores, and ownership chain.

### `GET /dashboard/suppliers/concentration`

Sector-level analysis:

```json
{
  "sectors": [
    {
      "sector": "shipbuilding",
      "supplier_count": 1,
      "is_sole_source": true,
      "sole_supplier": "Irving Shipbuilding",
      "total_contract_value_cad": 30000000000
    }
  ]
}
```

### `GET /dashboard/suppliers/risk-matrix`

All suppliers as scatter plot data: x = contract value, y = composite risk score.

### `GET /dashboard/suppliers/ownership`

Breakdown by ownership type with aggregate contract values.

### `GET /dashboard/suppliers/alerts`

Suppliers with any dimension score >70, sorted by highest score. Each alert includes supplier name, dimension, score, and rationale.

All endpoints cached 1 hour (matches existing dashboard pattern).

## UI: Canada Intel Tab Extension

### Placement

Added after the `<div class="grid grid-2">` that wraps Sections 5 (Supply Chain) and 6 (Shifting Alliances) in the Canada Intel tab — after line ~1474 in `index.html`. Full-width section, not inside a grid-2.

### Alerts Banner

At the top of the section. Uses existing `.insight-alert` card styling. Shows suppliers with any dimension score >70. Color-coded: `.threat` (red) for score >85, `.warning` (amber) for 70-85. Each alert shows supplier name, highest-risk dimension, and one-line rationale.

### Card 1 (full width): Supply Base Risk Overview

**Top row:** 4 KPI stat boxes using `.stat-box` class:
- Total Suppliers (count)
- Foreign-Controlled % (percentage of suppliers that are foreign_subsidiary)
- Sole-Source Sectors (count of sectors with only 1 supplier)
- Avg Risk Score (composite average, color-coded by threshold)

**Below:** Horizontal bar chart (Chart.js) showing all suppliers sorted by composite risk score. Bar color: green <40, amber 40-70, red >70. Clicking a bar shows an expanded area with the 6-dimension radar chart for that supplier (reusing the PSI radar pattern).

### Card 2 (half width): Sector Concentration

Inside a `<div class="grid grid-2">` with Card 3.

Grouped bar chart — one bar per sector showing supplier count. Sectors with 1 supplier highlighted in red with "SOLE SOURCE" text annotation. Below the chart: table listing sole-source suppliers with sector, contract value, and risk score.

### Card 3 (half width): Ownership Exposure

Donut chart (Chart.js): segments for Canadian-owned, allied-subsidiary, other. Below: list of foreign-owned suppliers showing flag emoji, parent company, parent country, and contract value. Suppliers with sanctioned parent countries get a `.threat-flag` badge.

### Design System Compliance

All new UI elements use the existing design tokens:
- Colors: `--accent` through `--accent5`, `--text-dim`, `--bg`, `--surface-glass`
- Typography: `--font-display` for headings, `--font-mono` for numbers, `--font-body` for text
- Components: `.card`, `.stat-box`, `.stat-num`, `.stat-label`, `.insight-alert`, `.btn-primary`
- Charts: Chart.js with `'IBM Plex Sans'` font family, new palette hex values

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/storage/models.py` | Modified | Add 3 new SQLAlchemy models with unique constraints and indexes |
| `src/ingestion/procurement_scraper.py` | New | Open Canada procurement disclosure scraper |
| `src/ingestion/corporate_graph.py` | Modified | Add `fetch_company_ownership(name)` method for per-company lookup |
| `src/storage/persistence.py` | Modified | Add upsert functions for new tables |
| `src/analysis/supplier_risk.py` | New | 6-dimension risk scoring engine |
| `src/api/supplier_routes.py` | New | 6 supplier endpoints (dedicated route file) |
| `src/ingestion/scheduler.py` | Modified | Add weekly procurement jobs |
| `src/static/index.html` | Modified | Add Defence Supply Base section to Canada Intel tab |
| `src/main.py` | Modified | Register new tables in DB init, mount supplier routes |

## Out of Scope

- Real-time supplier monitoring (future: financial news feed)
- Workforce/capacity scoring (can be added as dimension 7 later)
- Arctic-specific capability mapping (can extend sector enum later)
- PDF briefing export of supplier risk (planned in separate feature)
- User authentication / access control for sensitive procurement data
