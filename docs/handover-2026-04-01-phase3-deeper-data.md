# Session Handover — 2026-04-01 (Phase 3: Deeper Data Integration)

## What Was Done

This session implemented Phase 3 of the Cobalt Strengthening design spec — Deeper Data Integration. Three workstreams completed across 11 commits.

### 1. Comtrade Cobalt Bilateral Trade Queries
- Added 8 M49 country codes (DRC, Belgium, Finland, Cuba, Morocco, Zambia, Madagascar, South Africa)
- Expanded cobalt source countries from 5 to 10
- Defined 10 bilateral corridors using **buyer-side mirror** for DRC (DRC severely under-reports exports)
- 4 HS codes queried: 2605 (ore), 810520 (unwrought/powder), 810590 (wrought), 282200 (oxides/hydroxides)
- `fetch_cobalt_bilateral_flows()` method on `ComtradeMaterialsClient`
- Monthly scheduler job (1st of month, 6 AM)
- API key stored in `config/.env` (gitignored)

### 2. Supplier Dossiers — All 18 Entities Complete

Every cobalt mine (9) and refinery (9) now has a real dossier with sourced OSINT data:

| Entity | Type | FOCI Score | Z-Score | Key Finding |
|--------|------|-----------|---------|-------------|
| Tenke Fungurume | Mine | — | 2.8 | CMOC/State Council PRC control |
| Kisanfu | Mine | — | 2.5 | CMOC 71.25% + CATL 23.75% vertical integration |
| Kamoto (KCC) | Mine | — | 3.1 | Orion CMC $9B deal pending |
| Mutanda | Mine | — | — | DRC export quota: 6.7kt 2026 |
| Murrin Murrin | Mine | — | — | Declining production (3,400t→2,100t) |
| **Moa JV** | Mine | **92 CRITICAL** | 0.87 | **PAUSED Feb 2026** — Cuba fuel crisis |
| **Voisey's Bay** | Mine | 25 LOW-MOD | 3.2 | Ramping to 2,600t/yr by H2 2026 |
| **Sudbury Basin** | Mine | 15 LOW | 3.5 | Falconbridge smelter incidents 2025 |
| **Raglan Mine** | Mine | 15 LOW | 3.5 | All cobalt exported to Norway |
| Huayou Cobalt | Refinery | **92 CRITICAL** | 2.6 | CDM toxic dam failure Nov 2025 |
| GEM Co. | Refinery | **88 CRITICAL** | 1.9 | Glencore offtake 14,400t/yr through 2029 |
| Jinchuan Group | Refinery | **98 CRITICAL** | N/A (SOE) | Direct PRC state ownership 66% Gansu SASAC |
| **Umicore Kokkola** | Refinery | 10 LOW | 2.9 | Largest Western cobalt refinery (15-16kt/yr) |
| **Umicore Hoboken** | Refinery | 10 LOW | 2.9 | Battery recycling mega-plant delayed to 2032 |
| **Fort Saskatchewan** | Refinery | **82 CRITICAL** | 0.87 | **Feedstock PAUSED** — only non-Chinese pipeline |
| **Long Harbour NPP** | Refinery | 25 LOW-MOD | 3.2 | World's first hydromet for hard rock sulphide |
| **Niihama** | Refinery | 8 LOW | 3.1 | Japan's only cobalt refinery; FY2024 -72% profit |
| **Harjavalta** | Refinery | **95 CRITICAL** | 2.4 | Russian-owned in NATO Finland; Potanin sanctioned |

**Bold** = entities whose dossiers were added this session (10 total). Others were added by the prior Chinese entities research agent.

### 3. Active Confidence Triangulation
- `SourceDataPoint` class for typed production data
- `triangulate_cobalt_production()` — pairwise cross-check with tolerance thresholds (≤10% OK, 25-50% WARNING, >50% CRITICAL)
- `compute_cobalt_hhi()` — live Herfindahl-Hirschman Index from BGS country data
- Discrepancy alert Rule 4 in `cobalt_alert_engine.py` — BGS vs USGS DRC production cross-check
- Globe `/minerals/cobalt` endpoint enriched with `hhi_live` and `hhi_source`

### 4. UI Surfacing
- Globe entity popups: FOCI assessment + Z-score badges (color-coded)
- Taxonomy bars: opacity reflects source count (3+ = solid, 2 = 0.85, 1 = 0.6)
- Overview: HHI prefers live BGS-computed value
- BOM Explorer: HS code badges show trade values when available
- Supplier Dossier: FOCI assessment badge with numeric score (X/100)

## Test Status
- **283 tests total** (was 219)
- **64 new tests**: 12 Comtrade cobalt, 11 confidence triangulation, 41 dossier completeness
- 1 pre-existing failure: `test_generate_coas_from_supplier_risks` (status mismatch, unrelated)
- Server-dependent adversarial tests pass when server is running

## Key Files Modified

| File | Changes |
|------|---------|
| `src/ingestion/comtrade.py` | +8 M49 codes, +5 cobalt source countries, COBALT_BILATERAL_CORRIDORS, COBALT_HS_CODES, `fetch_cobalt_bilateral_flows()` |
| `src/analysis/mineral_supply_chains.py` | 10 new dossier blocks (4 mines + 6 refineries), FOCI fields added to 3 Chinese entities |
| `src/analysis/confidence.py` | `SourceDataPoint`, `triangulate_cobalt_production()`, `compute_cobalt_hhi()` |
| `src/analysis/cobalt_alert_engine.py` | Rule 4: data discrepancy detection |
| `src/ingestion/scheduler.py` | Monthly `comtrade_cobalt` job (1st of month, 6 AM) |
| `src/api/globe_routes.py` | Cobalt response enriched with live HHI |
| `src/static/index.html` | FOCI badges, Z-score badges, taxonomy opacity, live HHI, trade values |
| `tests/test_comtrade_cobalt.py` | 12 tests (M49 codes, corridors, bilateral query) |
| `tests/test_confidence_triangulation.py` | 11 tests (triangulation, HHI, discrepancies) |
| `tests/test_dossier_completeness.py` | 41 tests (all 18 entities, required fields, FOCI ranges) |

## What's Next (Not Yet Done)

### Phase 4 — UI Enhancements (from design spec)
- Data freshness indicator row on Overview
- IPIS ASM cobalt sites as toggleable globe layer
- Comtrade trade flow arcs on 3D globe (arc thickness = value)
- Lobito Corridor as distinct shipping lane
- Source attribution badges on Risk Taxonomy bars
- "Data quality feedback" mode on Analyst Feedback
- Price source toggle on Forecasting (IMF vs nickel proxy)
- Time comparison toggle on Risk Matrix

### Deferred from Phase 3
- Parse Glencore/CMOC quarterly PDFs (tabula-py) — deferred as existing data is already real (from FY 2025 reports)
- IPIS DRC cobalt filter (WFS query) — useful for ASM globe layer
- Cobalt Institute market report parser — useful for supply/demand balance

### Known Gaps
- Comtrade trade values not yet stored in DB (in-memory only from API queries)
- Triangulation runs on fallback data — needs live BGS/USGS queries to compare fresh data
- Taxonomy scores still authored estimates — not yet grounded in multi-source live computation
- NSN numbers remain illustrative (not from NMCRL)
- Cuba→Canada MSP trade invisible in standard HS codes (classified as nickel intermediates)

## Design Docs
- `docs/superpowers/specs/2026-04-01-phase3-deeper-data-integration-design.md` — Full design spec
- `docs/superpowers/plans/2026-04-01-phase3-deeper-data-integration.md` — Implementation plan (8 tasks)
