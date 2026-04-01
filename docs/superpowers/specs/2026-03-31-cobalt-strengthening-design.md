# Cobalt Strengthening Design Spec

**Date**: 2026-03-31
**Goal**: Replace all fabricated/placeholder data with real OSINT sources, wire up existing dormant connectors, add new cobalt-specific data feeds, and enhance each of the 12 Supply Chain sub-tabs for analytical depth and data freshness.
**Scope**: Cobalt only. Changes span `mineral_supply_chains.py`, `cobalt_forecasting.py`, `cobalt_alert_engine.py`, `osint_feeds.py`, `export_routes.py`, `globe_routes.py`, `psi_routes.py`, `index.html`, and new connector files.

---

## Layer 1: Data Integrity Fixes

### L1.1 — Static Price History Correction

**File**: `src/analysis/mineral_supply_chains.py` (forecasting.price_history block, ~line 1371)

Replace fabricated prices with real IMF/LME-derived quarterly averages:

| Quarter | Current (wrong) | Real (IMF PCOBALT) |
|---|---|---|
| Q1 2025 | $10.90/lb | $9.75/lb |
| Q2 2025 | $11.20/lb | $16.00/lb |
| Q3 2025 | $10.50/lb | $16.80/lb |
| Q4 2025 | $11.80/lb | $21.00/lb |
| Q1 2026 | $12.40/lb | $25.00/lb |
| Q2 2026 | $12.90/lb | Remove (not yet concluded) |

Mark all as `"type": "actual"` and add `"source": "IMF PCOBALT / LME settlement"`.

### L1.2 — Remove Fabricated Items

| Item | Action | File |
|---|---|---|
| "CISA Alert AA26-081A" (COA-004) | Replace with real alert: "CISA adds Ivanti VPN vulnerability to KEV catalog — used by mining sector OT systems (CVE-2024-21887)" | `mineral_supply_chains.py` watchtower_alerts |
| DND contract IDs (DND-CO-TFM-001 etc.) | Remove fake contracts. Dossier shows: "No direct DND cobalt procurement contracts identified in Open Canada disclosure data" | `mineral_supply_chains.py` dossier.contracts |
| Sherritt CCC- S&P downgrade (COA-003 alert) | Replace with: "Sherritt International (TSX:S) trading at $0.18, market cap ~$56M, significant debt covenant pressure — Fort Saskatchewan operations funded through Q2 2026 feed inventory" | `mineral_supply_chains.py` watchtower_alerts |
| Kisanfu ownership 75/25 | Correct to CMOC 71.25% / CATL 23.75% / DRC govt 5% | `mineral_supply_chains.py` mines[1] |
| Mutanda acid mine drainage alert (COA-005) | Replace with real event: "Glencore Mutanda restart at reduced capacity — environmental remediation ongoing since 2022 suspension" sourced from Glencore 2025 production report | `mineral_supply_chains.py` watchtower_alerts |
| Gecamines 5%→10% royalty renegotiation | Replace with: "DRC government reviewing mining code fiscal terms — 2018 code revision increased royalties from 2% to 3.5% for cobalt, further increases under discussion" (real, sourced from DRC mining code) | `mineral_supply_chains.py` dossier.recent_intel |
| Kisanfu $200M capex overrun | Replace with: "Kisanfu Phase 2 ramp-up underway — CMOC targets full 30kt capacity by 2027" (real, from CMOC IR) | `mineral_supply_chains.py` dossier.recent_intel |
| Harjavalta LME status | Update to: "LME permanent delisting of Harjavalta nickel brands effective June 2026 — Nornickel exploring direct sales to battery manufacturers" | `mineral_supply_chains.py` refineries[8] |
| CF-188 fleet size | Correct 76 → 88 aircraft | `mineral_supply_chains.py` sufficiency.demand |
| Analyst personas (Tremblay, Singh, Okafor) | Replace names with "Analyst 1", "Analyst 2", etc. Add note: "Pending live analyst integration" | `mineral_supply_chains.py` analyst_feedback |
| ML accuracy 87% / FP rate 18% | Keep numbers but add `"baseline": true` flag. UI renders "BASELINE — no live model trained" | `mineral_supply_chains.py` analyst_feedback |
| Houthi 300% insurance premium (COA-006) | Keep the Houthi Red Sea risk (real) but change "300%" to "significant increase" and source to Lloyd's List / Freightos Baltic Index reporting | `mineral_supply_chains.py` watchtower_alerts |

### L1.3 — Production Figure Typing

Add `figure_type` field to every mine and refinery entry:

```python
"figure_type": "design_capacity",  # or "actual_2025", "quota_2026"
"figure_source": "USGS MCS 2025",  # or "Glencore FY 2025 Report", "CMOC Q3 2025"
"figure_year": 2025,
```

The UI displays: "32,000 t/yr (design capacity — USGS 2025)" instead of bare numbers.

### L1.4 — Correct Minor Factual Errors

- **GEM Co. coordinates**: Change from Shenzhen HQ (22.5, 114.1) to Taixing refinery (32.2, 120.0) where the actual cobalt refining occurs
- **Voisey's Bay production_t**: Add note: "Design capacity 2,500 t/yr — actual 2024 output ~840 t due to ramp-up delays (Vale Base Metals IR)"
- **Cobalt/nickel ratio**: Update commentary from "1.8-2.2x" to "historically 1.8-2.5x, elevated to ~3.0x in early 2026 due to cobalt rally" since the ratio has diverged

---

## Layer 2A: Wire Up Existing Connectors

### L2A.1 — IMF Cobalt Prices → Forecasting Engine

**Priority**: HIGHEST. Single biggest improvement.

**Current state**: `cobalt_forecasting.py` fetches FRED PNICKUSDM (nickel) and multiplies by 2.0.
**Target state**: Fetch IMF PCOBALT directly. Fall back to FRED nickel × ratio only if IMF is down.

**Changes**:

`src/analysis/cobalt_forecasting.py`:
- New function `fetch_cobalt_prices()` that calls IMF SDMX endpoint: `http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/PCPS/M.W00.PCOBALT`
- Parse SDMX JSON response → extract monthly USD/metric-ton values → convert to USD/lb (÷ 2204.62)
- Replace `fetch_nickel_prices()` call in `compute_cobalt_forecast()` with `fetch_cobalt_prices()`
- Keep `fetch_nickel_prices()` as fallback with logged warning: "IMF cobalt unavailable, using nickel proxy"
- Update `price_source` field in response from "FRED Nickel proxy × 2.0" to "IMF Primary Commodity Prices (PCOBALT)"
- Update regression to use real cobalt quarterly data instead of nickel-derived estimates

**Validation**: Compare first live IMF-based forecast against the current nickel proxy output. Log both for one release cycle.

### L2A.2 — Fix USGS CSV Download

**Current state**: `USGSCobaltDataClient` in `osint_feeds.py` hits catalog metadata URL, always falls to seed.
**Target state**: Download actual CSV from USGS data release.

**Changes**:

`src/ingestion/osint_feeds.py` (`USGSCobaltDataClient`):
- Change URL to the actual CSV download: the data release page at `https://data.usgs.gov/datacatalog/data/USGS:6797fb00d34ea8c18376e159` links to two CSVs (US salient stats + world production by country)
- Parse the world production CSV for country-level cobalt production tonnes
- Return structured data: `[{country: "DRC", production_t: 170000, year: 2024}, ...]`
- Compare against existing `mining[]` percentages and flag discrepancies
- Schedule: check monthly (data updates annually but we want to catch new releases)

### L2A.3 — Activate Comtrade Cobalt HS Queries

**Current state**: Cobalt HS codes defined in `comtrade.py` `HS_DEFENSE_MATERIALS` but not queried for bilateral flows.
**Target state**: Query bilateral cobalt trade values for key corridors.

**Changes**:

`src/ingestion/comtrade.py`:
- New function `fetch_cobalt_trade_flows()` that queries Comtrade Plus API for:
  - Reporter: DRC, China, Finland, Belgium, Cuba, Canada, Australia
  - Partner: China, Canada, USA, Finland, Belgium, Japan
  - HS codes: 2605, 810520, 810590, 282200
  - Period: latest available year
- Returns: `[{reporter: "DRC", partner: "China", hs_code: "2605", value_usd: 2400000000, year: 2023}, ...]`
- Store in `supply_chain_routes` table (new columns: `trade_value_usd`, `trade_year`, `hs_code`)
- Schedule: monthly (Comtrade updates with ~6 month lag)

`src/api/globe_routes.py`:
- Enrich `/globe/minerals/cobalt` response with trade flow data on shipping routes

### L2A.4 — SEC EDGAR XBRL → Real Z-Scores

**Current state**: Fabricated Z-scores in dossier data.
**Target state**: Computed from real financial filings.

**Changes**:

New file `src/analysis/financial_scoring.py`:
- `compute_altman_z(ticker, source)` function
- For Sherritt: parse quarterly PDF from `https://sherritt.com/wp-content/uploads/{year}/{month}/Q{q}-{year}-Interim-Report.pdf`
  - Extract: total assets, total liabilities, working capital, retained earnings, EBIT, revenue
  - Market cap from Yahoo Finance free API (or hardcode shares outstanding × TSX price)
  - Z = 1.2×(WC/TA) + 1.4×(RE/TA) + 3.3×(EBIT/TA) + 0.6×(MVE/TL) + 1.0×(S/TA)
- For US-listed companies (RTX, GE Aerospace): use SEC EDGAR XBRL API at `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`
- Cache results (quarterly refresh)
- Return: `{z_score: 1.42, zone: "distress", computed_from: "Sherritt Q3 2025 TSX filing", computed_at: "2026-03-31"}`

`src/analysis/mineral_supply_chains.py`:
- Replace hardcoded `z_score` values in dossier with calls to `compute_altman_z()` at data load time
- Fallback to static value if computation fails, with `"z_source": "estimated"` flag

---

## Layer 2B: New Connectors

### L2B.1 — BGS World Mineral Statistics

**File**: `src/ingestion/bgs_minerals.py` (new)

**Endpoint**: `https://ogcapi.bgs.ac.uk/collections/world-mineral-statistics/items`
**Query params**: `?commodity=Cobalt&limit=500&f=json`
**Auth**: None
**Format**: OGC API Features (GeoJSON)

**Returns**: Country-level cobalt production by year (1970-2022):
```json
{"country": "Congo (Kinshasa)", "year": 2022, "quantity": 130000, "unit": "tonnes", "statistic_type": "Mine production"}
```

**Integration**:
- Cross-reference with USGS data in `confidence.py` — when both agree, confidence = "triangulated (USGS + BGS)"
- Update `mining[]` array percentages if BGS and USGS data both confirm different shares
- Feed into Glass Box confidence scoring for taxonomy entries

**Schedule**: Weekly check, annual update expected

### L2B.2 — NRCan Canadian Cobalt Facts

**File**: `src/ingestion/nrcan_cobalt.py` (new)

**Source**: `https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis/minerals-metals-facts/cobalt-facts`
**Method**: HTML scrape (BeautifulSoup) — parse key stats tables
**Auth**: None

**Data extracted**:
- Canadian cobalt production by province (tonnes)
- Canadian cobalt exports (value CAD)
- Canadian cobalt imports (value CAD)
- Top trading partners
- Domestic consumption

**Integration**:
- Feed `canada.domestic` field in mineral_supply_chains.py with real production figure
- Feed `canada.import_pct` with computed value: (imports - domestic production) / total consumption × 100
- Display on Overview Canada Dependency card: "Canada produced 3,351t in 2024 (NRCan)"
- Cross-reference with Voisey's Bay, Sudbury, Raglan production claims

**Schedule**: Monthly check, data updates annually

### L2B.3 — Sherritt International Connector

**File**: `src/ingestion/sherritt_cobalt.py` (new)

**Sources**:
- Quarterly report PDFs: `https://sherritt.com/wp-content/uploads/{year}/{month}/Q{q}-{year}-Interim-Report.pdf`
- Press releases: `https://sherritt.com/news/` (RSS/HTML scrape)
- TSX stock price: free Yahoo Finance API for market cap computation

**Data extracted**:
- Fort Saskatchewan cobalt production (tonnes/quarter)
- Moa JV operational status (operating/paused/suspended)
- Financial metrics for Z-score (total assets, liabilities, WC, EBIT, revenue)
- Stock price + shares outstanding → market cap

**Integration**:
- Update Fort Saskatchewan refinery `capacity_t` and `actual_production_t`
- Update Moa JV mine operational status and flags
- Feed real Z-score into dossier
- Generate alert when operational status changes (pause/restart)

**Schedule**: Quarterly after earnings (+ press release RSS daily check)

### L2B.4 — Glencore + CMOC Production Report Parsers

**Enhancement to existing connectors** in `src/ingestion/osint_feeds.py`

**Glencore** (`GlencoreProductionClient`):
- Download quarterly PDF from known URL pattern
- Extract cobalt production table using `pdfplumber` or `tabula-py`
- Update mine-level production_t for Kamoto, Mutanda, Murrin Murrin, Raglan
- Source: `https://www.glencore.com/publications` → Production Reports

**CMOC** (`CMOCProductionClient`):
- Download from `https://en.cmoc.com/html/InvestorMedia/Performance/`
- Extract DRC cobalt production figures
- Update TFM and Kisanfu production_t
- Source: CMOC quarterly results announcements

Both should set `figure_type: "actual_{year}"` and `figure_source: "{company} Q{q} {year} Report"`.

### L2B.5 — IPIS DRC Cobalt Filter

**Enhancement to existing** `IPISDRCMinesClient` in `osint_feeds.py`

**Current**: Returns all 2,800+ ASM sites unfiltered.
**Enhancement**: Add cobalt filter to WFS query:
```
&CQL_FILTER=mineral1='cobalt' OR mineral2='cobalt'
```

**Integration**:
- New globe layer: "DRC Artisanal Cobalt Mines" (orange dots, toggleable)
- Each site carries: coordinates, armed_group_presence, child_labor_flag, worker_count, last_visit_date
- Feed into taxonomy scoring: `human_capital` and `compliance` categories get real IPIS field data instead of estimated scores
- Count of active ASM cobalt sites becomes a real KPI on the Overview

### L2B.6 — Cobalt Institute Market Report Parser

**Enhancement to existing** `CobaltInstituteClient` in `osint_feeds.py`

**Current**: HEAD check only, returns seed data.
**Enhancement**: Download annual market report PDF, extract:
- Global cobalt supply (tonnes)
- Global cobalt demand (tonnes) by end-use (batteries, superalloys, catalysts, other)
- Supply/demand balance (surplus or deficit)
- Recycled cobalt supply (tonnes)
- Price outlook commentary

**Integration**:
- Overview: new "Market Balance" stat card (surplus/deficit)
- Forecasting: additional structural context alongside price regression
- Knowledge Graph: recycling pathway as secondary supply source
- BOM Explorer: end-use breakdown percentages

---

## Layer 2C: Per-Sub-Tab UI Enhancements

### 4.1 Overview
- Add data freshness indicator row at top (per-feed last-updated timestamps)
- Live-computed HHI from USGS+BGS data (replace static 5900)
- Supply/demand balance card from Cobalt Institute
- NRCan-sourced Canada production stat on dependency card
- Price trend sparkline (last 12 months IMF PCOBALT) beside risk badge

### 4.2 3D Supply Map
- IPIS ASM cobalt sites as toggleable globe layer (orange dots)
- Comtrade trade flow arcs with real USD values (arc thickness = value)
- Lobito Corridor as distinct shipping lane
- Production figure source + date on entity popups

### 4.3 Knowledge Graph
- Complete dynamic percentage replacement in flow arrows (remove last hardcoded strings)
- Lobito Corridor as second Tier 1→2 pathway
- Recycling pathway as Tier 0 input (GEM Co., Umicore Hoboken secondary supply)

### 4.4 Risk Matrix
- Bubble positions grounded in live taxonomy + real production_t
- Time comparison toggle (Q4 vs Q1 snapshot)
- DRC export quota overlay (dashed ring showing constrained output)

### 4.5 Scenario Sandbox
- Real IMF cobalt price in value-at-risk calculations
- New preset: "Lobito Corridor Activation" (what if DRC→Lobito replaces DRC→China→Canada?)
- Real Comtrade values in dollar calculations

### 4.6 Risk Taxonomy
- Source attribution badges per category bar ("USGS + BGS", "IPIS", "GDELT")
- IPIS-sourced real armed-group/child-labor data for ESG categories
- Confidence gradient on bars (solid = 3+ sources, translucent = 1 source)

### 4.7 Forecasting
- IMF PCOBALT replaces nickel proxy (primary change)
- Price source toggle: "IMF Cobalt | FRED Nickel proxy"
- Real Sherritt Z-score from TSX filings in insolvency watch
- Cobalt Institute supply/demand forecast as second track
- Lobito Corridor in lead time calculation

### 4.8 BOM Explorer
- Prominent "Illustrative — not from NMCRL" label on NSN entries
- Real Comtrade USD values next to HS codes
- Alloy→platform cross-links to Scenario Sandbox

### 4.9 Supplier Dossier
- Fill dossiers for 3 Canadian entities (Voisey's Bay, Sudbury, Fort Saskatchewan) from NRCan + Sherritt IR
- Fill dossiers for Umicore Kokkola + Hoboken from Euronext filings
- Real Z-scores for Sherritt and Umicore from financial computations
- Real UBO chains for Sumitomo (Niihama) and Nornickel (Harjavalta)
- Chinese refineries: populate from SZSE/SSE where available, mark "Limited disclosure" where not

### 4.10 Alerts & Sensing
- Replace fabricated alerts with real events (see L1.2 table)
- IPIS alert integration: armed-group activity at cobalt mines → auto-alert
- IMF price alert: >10% monthly move → price volatility alert
- Sherritt operational status monitoring → pause/restart alert
- Source quality scoring on GDELT news (Reuters/Bloomberg > unknown domains)

### 4.11 Risk Register
- Remove fabricated owners/due dates → "Unassigned" default
- Evidence links to real sources (IMF price chart for CO-006, USGS for CO-001)
- "Last verified" date per risk
- Wire CO-001 severity to live USGS production percentage (auto-update)

### 4.12 Analyst Feedback
- Label seeded stats as "BASELINE — awaiting live analyst input"
- Remove fabricated analyst names
- Keep only confirmed-real pending adjudication items
- Add "Data quality feedback" mode: flag any data point as Incorrect/Outdated/Confirmed

---

## New Files

| File | Purpose |
|---|---|
| `src/ingestion/bgs_minerals.py` | BGS OGC API connector for world mineral statistics |
| `src/ingestion/nrcan_cobalt.py` | NRCan cobalt facts HTML scraper |
| `src/ingestion/sherritt_cobalt.py` | Sherritt International quarterly report parser + TSX data |
| `src/analysis/financial_scoring.py` | Real Altman Z-score computation from financial filings |

## Modified Files

| File | Changes |
|---|---|
| `src/analysis/mineral_supply_chains.py` | Fix all fabricated data (L1.1-L1.4), add figure_type/source fields |
| `src/analysis/cobalt_forecasting.py` | Replace FRED nickel with IMF PCOBALT (L2A.1) |
| `src/analysis/cobalt_alert_engine.py` | Add IPIS + IMF price + Sherritt status alert sources |
| `src/ingestion/osint_feeds.py` | Fix USGS CSV (L2A.2), enhance CMOC/Glencore/IPIS/CobaltInstitute connectors |
| `src/ingestion/comtrade.py` | Activate cobalt HS bilateral queries (L2A.3) |
| `src/ingestion/scheduler.py` | Add schedules for new connectors |
| `src/api/globe_routes.py` | Enrich cobalt response with trade flow data, figure_type |
| `src/api/psi_routes.py` | Feed real data into taxonomy scores, trade values into scenarios |
| `src/static/index.html` | All 12 sub-tab UI enhancements (Layer 2C) |
| `src/analysis/confidence.py` | Update triangulation logic for BGS + USGS multi-source |

## Implementation Priority

| Phase | Items | Impact |
|---|---|---|
| **Phase 1** | L1 (all data fixes) + L2A.1 (IMF cobalt prices) | Fixes all fabricated data, enables real cobalt pricing |
| **Phase 2** | L2A.2-L2A.4 (USGS, Comtrade, Z-scores) + L2B.1-L2B.3 (BGS, NRCan, Sherritt) | Adds independent data sources, Canadian context |
| **Phase 3** | L2B.4-L2B.6 (Glencore/CMOC parsers, IPIS filter, Cobalt Institute) | Deepens entity-level data |
| **Phase 4** | L2C (all 12 sub-tab UI enhancements) | Surfaces new data in the dashboard |

## Test Plan

- Existing 146 cobalt tests must continue to pass
- New tests for each connector: mock HTTP responses, verify parsing
- Integration test: start server, hit `/globe/minerals/cobalt/forecast`, verify response contains IMF-sourced prices (not nickel proxy)
- Integration test: hit `/globe/minerals/cobalt`, verify `figure_type` and `figure_source` present on all entities
- Verify no fabricated CISA alert numbers, contract IDs, or analyst names appear in any API response
- Verify Z-scores have `z_source` field indicating "computed" vs "estimated"
- CSV export tests: verify new columns (figure_type, source) appear in exports
