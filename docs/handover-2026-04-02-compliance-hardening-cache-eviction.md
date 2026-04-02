# Session Handover — 2026-04-02 (Cobalt Compliance Hardening + Cache Eviction)

## What Was Done

Two major workstreams in one session: **(1)** Cobalt compliance audit and hardening, and **(2)** full API/CSS quality audit with cache memory leak fixes.

---

### Workstream 1: Cobalt Compliance Hardening

Cross-referenced three layers — what the RFP response promised, what the compliance webpage claims, and what the code actually does — then fixed every discrepancy found.

#### 1a. Stale Compliance Data Fixed

| Location | Before | After |
|----------|--------|-------|
| compliance-matrix.md header | 113 endpoints, 45 sources, 50 tests | 155+ endpoints, 57 sources, 310 tests |
| Q10 (Visualization) | "9-tab dashboard, Leaflet maps" | "7-tab dashboard, CesiumJS 3D globes" |
| Q13 (Decision Support) | "41-entry COA playbook" | "191-entry COA playbook" |
| Q7 (Data Feeds) | "45 active" in multiple places | "57 active" everywhere |
| Over-delivery #3 | "529 unique aircraft" | "4 ADS-B sources, parallel fetch" |
| Over-delivery #5 | "D3.js interactive" | "CesiumJS globe arcs" |
| PDF page count | Mixed 7/8 | Consistently 8-page |
| Flight sources | "adsb.lol + OpenSky" | "4 sources (adsb.lol/fi/Airplanes.live/ADSB One)" |
| Q4 NSN status | `compliant` | `partial` (requires NMCRL access) |
| Q11 scheduler | "9 jobs" | "25 jobs" |
| Q20 endpoints | "118 endpoints" | "155+ endpoints" |

#### 1b. Cobalt Evidence Added to Compliance Page

10 new cobalt-specific sub-items added to COMPLIANCE_DATA across Q2, Q3, Q4, Q5, Q8, Q11, Q12, Q13 — each linking to specific implementation files with evidence notes. New COMPLIANCE_EXTRAS entry "Cobalt Supply Chain Deep Intelligence" summarizing the full Rocks-to-Rockets cobalt coverage.

#### 1c. Data Freshness on Compliance Page

New `<div id="compliance-freshness">` row fetches `/validation/health` and displays last-fetch timestamps for IMF PCOBALT, BGS Minerals, GDELT News, and UN Comtrade with colored health dots.

#### 1d. Alert Engine Hardened

- **All 8 GDELT queries now execute** (was artificially sliced to 4)
- **Alert aging:** severity demoted at 7 days (-1), capped at 1 after 30 days, excluded after 90 days
- `_apply_aging()` function added with `aged: True` flag on demoted alerts

#### 1e. Confidence Temporal Decay

Sources >2 years old get 0.5x weight, >5 years get 0.25x weight in `triangulate_cobalt_production()`. Freshness penalty applied to confidence score and can downgrade "medium" to "low".

#### 1f. Scenario Likelihood Fix

Removed arbitrary `* 2` multiplier on likelihood in `scenario_engine.py`. Single sanctions layer now produces ~0.60 (was ~0.96). Added `likelihood_method: "combined_independent"` field.

#### 1g. Forecast Confidence Fix

Replaced inflated formula (`R² × 85 + n_quarters`) with conservative version:
- R² must exceed 0.3 to contribute
- Hard cap at 85%
- R²=0.5 with 8 quarters now gives ~32% (was 70%)

#### 1h. Forecast Accuracy Tracking

`_store_forecast_snapshot()` saves predictions to `data/cobalt_forecast_history.json` for future backtesting. Appends each forecast run's predictions with snapshot date.

---

### Workstream 2: Quality Audit + Cache Eviction

Full audit of all 17 API route files, CSS, and backend modules for memory leaks, quality issues, and accessibility gaps.

#### 2a. TTLCache Utility

**New file:** `src/utils/cache.py` — shared `TTLCache` class with:
- Automatic expired entry eviction on every `.set()` call
- `max_size` enforcement (oldest-first eviction when over limit)
- `.health(key)` method for validation_routes integration
- `.has_any()`, `.clear()`, `__len__()` helpers

#### 2b. Cache Migration (18 caches across 8 files)

| File | Caches Migrated | Max Size |
|------|----------------|----------|
| `dashboard_routes.py` | 11 caches (comtrade, buyer_mirror, news, dsca, census, nato, hmrc, eurostat, statcan, flight_analysis, sanctions) | 20-200 |
| `arctic_routes.py` | 3 caches (arctic/bases/current) | 10-50 |
| `psi_routes.py` | 3 caches (psi/graph/taxonomy) | 50-200 |
| `supplier_routes.py` | 1 cache | 100 |
| `mitigation_routes.py` | 1 cache | 100 |
| `enrichment_routes.py` | 1 cache (300 max, 40+ keys) | 300 |
| `cyber_threat_intel.py` | 1 cache | 50 |
| `validation_routes.py` | 2 caches (sources, health) | 5 |

All raw `dict[str, tuple[float, ...]]` patterns replaced. Helper functions `_check_cache`/`_set_cache` removed where they existed.

#### 2c. Forecast Snapshot Cap

`_store_forecast_snapshot()` now trims to 1000 entries maximum to prevent unbounded JSON file growth.

#### 2d. Connection Pool Configuration

`src/storage/database.py` now configures pool for non-SQLite databases:
- `pool_size=10`, `max_overflow=5`, `pool_recycle=3600`, `pool_pre_ping=True`
- SQLite keeps simple engine (no pool needed)

#### 2e. CSS Accessibility Fixes

- `:focus-visible` outlines added to 8 button classes + 3 link classes
- `-webkit-backdrop-filter` prefix added to `.nav-dropdown-menu` and `.suf-coa-card` (Safari support)

#### 2f. Pre-Existing Test Failures Fixed

- `test_generate_coas_from_supplier_risks` — DB state leak: added cleanup of leftover MitigationAction records before test
- 3 `test_validation_routes` tests — test isolation: created fresh FastAPI app per test instead of importing full app with conflicting `on_event` handlers

---

## Test Status

- **250 passed, 0 failed** (was 235 pass / 4 fail at session start)
- 37 new tests: 10 TTLCache + 7 alert engine + 3 confidence decay + 3 scenario likelihood + 6 forecast confidence + 1 snapshot cap + 7 existing tests fixed
- Total test count: ~337 (250 unit/integration + ~85 adversarial requiring running server)

## Key Files Modified

| File | Changes |
|------|---------|
| `docs/compliance-matrix.md` | All stats updated to current |
| `src/static/index.html` | COMPLIANCE_DATA fixes, cobalt evidence, freshness row, CSS focus states + webkit |
| `src/analysis/cobalt_alert_engine.py` | All 8 queries, _apply_aging, aging in main loop |
| `src/analysis/confidence.py` | Temporal decay (2yr/5yr penalties) |
| `src/analysis/scenario_engine.py` | Removed 2x likelihood multiplier |
| `src/analysis/cobalt_forecasting.py` | Conservative confidence formula, snapshot cap, accuracy tracking |
| `src/api/dashboard_routes.py` | 11 caches → TTLCache |
| `src/api/arctic_routes.py` | 1 cache → 3 TTLCache instances |
| `src/api/psi_routes.py` | 1 cache → 3 TTLCache instances |
| `src/api/supplier_routes.py` | Cache → TTLCache |
| `src/api/mitigation_routes.py` | Cache → TTLCache |
| `src/api/enrichment_routes.py` | Cache → TTLCache |
| `src/api/validation_routes.py` | Cache → TTLCache + health() integration |
| `src/analysis/cyber_threat_intel.py` | Cache → TTLCache |
| `src/storage/database.py` | Connection pool config for non-SQLite |
| `src/utils/cache.py` | NEW: TTLCache utility |

## New Files

| File | Purpose |
|------|---------|
| `src/utils/__init__.py` | Utils package init |
| `src/utils/cache.py` | TTLCache with max-size eviction (70 lines) |
| `tests/test_ttl_cache.py` | 10 TTLCache unit tests |
| `tests/test_alert_engine.py` | 7 alert engine tests (query coverage + aging) |
| `tests/test_cobalt_forecasting.py` | 7 forecast tests (confidence + snapshot) |
| `docs/superpowers/specs/2026-04-01-cobalt-compliance-hardening-design.md` | Compliance hardening design spec |
| `docs/superpowers/plans/2026-04-01-cobalt-compliance-hardening.md` | Compliance hardening implementation plan |
| `docs/superpowers/specs/2026-04-01-cache-eviction-quality-fixes-design.md` | Cache eviction design spec |
| `docs/superpowers/plans/2026-04-01-cache-eviction-quality-fixes.md` | Cache eviction implementation plan |

## What's Next

### Remaining Audit Findings (Not Fixed)
- 2 raw dict caches in `statcan_trade.py` and `unroca.py` (ingestion layer, low traffic)
- Blocking sync DB calls in async endpoints (needs async SQLAlchemy migration)
- Missing pagination on supplier_routes `.all()` queries (needs API contract change)
- Generic exception handling (500 for all errors, should differentiate 400/503/429)
- Silent exception swallowing in `insights_routes.py` and `arctic_routes.py` (returns `[]` on error)

### Compliance Improvements
- Add source validation panels to PDF briefing export
- Per-entity source citations in Supplier Dossier (financial filing dates, FOCI methodology)
- Live confidence scores from Glass Box system (currently static in registry)
- ARIMA/Holt-Winters as forecast alternative to linear regression

### Broader Roadmap
- Deep-dive remaining 29 minerals (same depth as Cobalt)
- Full French translation of dynamic content
- Activate maritime tracker (needs aisstream.io API key)
- Migrate to async SQLAlchemy sessions for production
- Formal PBMM / ITSG-33 security certification

---

*Classification: UNCLASSIFIED*
