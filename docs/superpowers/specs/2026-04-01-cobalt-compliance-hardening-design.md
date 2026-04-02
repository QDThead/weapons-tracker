# Design Spec: Cobalt Compliance Hardening

**Date:** 2026-04-01
**Scope:** Fix stale compliance data, add cobalt-specific evidence, harden alert/confidence/scenario/forecast code
**Mineral focus:** Cobalt only

---

## Context

A full compliance audit was performed comparing three layers:
1. What the RFP response (qdt-rfi-response.md) promised
2. What the compliance webpage (COMPLIANCE_DATA in index.html + compliance-matrix.md) claims
3. What the code actually does

The audit found: stale stats in the compliance matrix, overstatements in compliance claims, missing cobalt-specific evidence, and code gaps in alerts, confidence, scenarios, and forecasting.

---

## Tier 1 — Fix Stale Compliance Data

### 1a. compliance-matrix.md Header Stats

Current (stale, dated March 27 2026):
```
113 API Endpoints | 45 Active Data Sources | 50 Automated Tests
```

Update to:
```
155+ API Endpoints | 57 Active Data Sources | 310 Automated Tests
```

### 1b. Q10 (Visualization) — Matrix Row

Current: "9-tab dashboard, Leaflet maps, D3.js knowledge graph"
Fix to: "7-tab dashboard, CesiumJS 3D globes (Arctic + Supply Chain), D3.js knowledge graph"

### 1c. Q13 (Decision Support) — COA Count

Current in matrix: "41-entry COA playbook"
Fix to: "191-entry COA playbook"

### 1d. Q7 (Data Feeds) — Feed Count

compliance-matrix.md says "45 active OSINT sources" in multiple places.
Fix all to "57 active OSINT feeds" to match COMPLIANCE_DATA.

### 1e. Over-Delivery Items — Stale References

| Item | Issue | Fix |
|------|-------|-----|
| #5 "Arms trade flow network visualization (D3.js interactive)" | D3 network graph removed during tab consolidation | Update to "Arms trade flow visualization (CesiumJS globe arcs)" |
| #3 "529 unique aircraft" | Hardcoded count, should be dynamic | Change to "Live worldwide military flight tracking (4 ADS-B sources)" |

### 1f. PDF Briefing Page Count

Harmonize all references to "8-page" (currently mixed 7/8):
- compliance-matrix.md over-delivery #6
- COMPLIANCE_EXTRAS entry for PDF briefing
- COMPLIANCE_DATA Q20 sub-item (if it says 7)

### 1g. Data Feed Table

compliance-matrix.md Section 2 row 32: "adsb.lol + OpenSky Network (Arctic)"
Fix to: "adsb.lol + adsb.fi + Airplanes.live + ADSB One (4 sources, parallel fetch)"

---

## Tier 2 — Cobalt Evidence in Compliance Page

### 2a. Cobalt Deep Dive Section in COMPLIANCE_EXTRAS

Add a new entry to COMPLIANCE_EXTRAS showing cobalt-specific compliance evidence. This appears in the "Beyond Contract" grid on the Compliance tab.

```javascript
{
  name: 'Cobalt Supply Chain Deep Intelligence',
  desc: 'Full Rocks-to-Rockets cobalt coverage: 9 named mines with FOCI/Z-score dossiers, ' +
        '9 refineries, 8 defence alloys (Waspaloy/CMSX-4/Stellite), 6 shipping corridors, ' +
        'live IMF PCOBALT forecasting with R² and prediction intervals, ' +
        'GDELT + rule-based alert engine, active BGS/USGS/NRCan triangulation, ' +
        '10 bilateral Comtrade corridors (4 HS codes), ' +
        'DND 13-category risk taxonomy per entity. ' +
        'Demonstrates full DMPP 11 compliance at the individual mineral level.',
  component: 'mineral_supply_chains.py, cobalt_forecasting.py, cobalt_alert_engine.py, confidence.py',
  tab: 'supply-chain'
}
```

### 2b. Per-Q Cobalt Evidence Sub-Items

Add cobalt-specific sub-items to relevant COMPLIANCE_DATA questions. These appear when expanding a compliance card:

| Q | New Sub-Item | Status | Component | Note |
|---|-------------|--------|-----------|------|
| Q2 | Cobalt: Mine-to-platform network mapping | compliant | mineral_supply_chains.py | 9 mines → 9 refineries → 8 alloys → 7 CAF platforms, ownership chains traced |
| Q3 | Cobalt: Per-tier confidence scoring | compliant | confidence.py | Mining=HIGH (4 sources), Processing=HIGH (3), Alloy=HIGH (specs), Platform=MEDIUM (derived) |
| Q4 | Cobalt: 4 HS codes tracked (2605, 810520, 810590, 282200) | compliant | comtrade.py | Bilateral flows for 10 corridors, buyer-side mirror for DRC |
| Q4 | NSN: Illustrative only (structural gap) | partial | models.py | Architecture ready (13-digit indexed column); requires NMCRL access at DND deployment |
| Q5 | Cobalt: 13-cat taxonomy scored per entity | compliant | mineral_supply_chains.py | All 18 mines+refineries have entity-level taxonomy scores with KPIs |
| Q8 | Cobalt: Active triangulation (BGS vs USGS vs NRCan vs Comtrade) | compliant | confidence.py | Pairwise cross-check, >25% = warning, >50% = critical, live HHI computation |
| Q11 | Cobalt: GDELT + rule-based alert engine | compliant | cobalt_alert_engine.py | 8 keyword queries + 4 rule triggers (HHI, China refining, paused ops, discrepancies) |
| Q12 | Cobalt: IMF PCOBALT price forecasting | compliant | cobalt_forecasting.py | Linear regression, R², 90% prediction intervals, fan chart, 4-quarter horizon |
| Q12 | Cobalt: Scenario sandbox with cascade propagation | compliant | scenario_engine.py | 5 layer types, 4-tier Sankey, Likelihood x Impact, 5 preset scenarios |
| Q13 | Cobalt: 10 risk register entries with COA links | compliant | mineral_supply_chains.py | Status lifecycle (Open→In Progress→Mitigated→Closed), DB-persisted |

### 2c. Data Freshness in Compliance Rendering

Add a small "Data Freshness" row to the compliance stats summary (rendered by `renderCompliance()`). This fetches `/validation/health` and shows key cobalt source timestamps:

```
Cobalt Data Freshness: IMF PCOBALT (2026-03-28) | BGS Minerals (2026-03-15) | GDELT (live, 30min) | Comtrade (2026-04-01)
```

Implementation: In `renderCompliance()`, after the stats summary, add a fetch to `/validation/health` and render a `.compliance-freshness` row showing the 4 key cobalt sources with their last-fetch timestamps.

### 2d. NSN Gap Documentation

In COMPLIANCE_DATA Q4, the existing NSN sub-item says `status:'compliant'`. Change to `status:'partial'` and update the note:

```
note: 'NSN column (String 13-digit, indexed) on SupplyChainNode. Currently illustrative — real NSNs require NMCRL access at DND deployment. Architecture ready, demo shows 6 sample NSNs with red demo indicator.'
```

---

## Tier 3 — Code Fixes for Actual Compliance

### 3a. Alert Engine: Full GDELT Coverage

**File:** `src/analysis/cobalt_alert_engine.py`

**Problem:** Only 4 of 8 GDELT queries execute in the loop.

**Fix:** Change the query loop to iterate over all 8 queries instead of slicing to 4. All 8 queries are already defined — the loop limit is artificial.

### 3b. Alert Engine: Alert Aging/Expiry

**File:** `src/analysis/cobalt_alert_engine.py`

**Problem:** Alerts never expire. A 6-month-old GDELT article stays "active."

**Fix:** Add `generated_at` timestamp to each alert. In the alert aggregation step, down-weight severity for alerts older than 7 days and auto-demote to severity 1 ("info") for alerts older than 30 days. Alerts older than 90 days are excluded from results entirely.

```python
age_days = (now - alert["generated_at"]).days
if age_days > 90:
    continue  # exclude
elif age_days > 30:
    alert["severity"] = min(alert["severity"], 1)
    alert["aged"] = True
elif age_days > 7:
    alert["severity"] = max(1, alert["severity"] - 1)
    alert["aged"] = True
```

### 3c. Confidence: Temporal Decay

**File:** `src/analysis/confidence.py`

**Problem:** Sources from 2020 and 2026 both count equally for triangulation.

**Fix:** In `triangulate_cobalt_production()`, add a `year` field check on each `SourceDataPoint`. Sources older than current_year - 2 get a 0.5 weight multiplier. Sources older than current_year - 5 get 0.25 weight. The "best estimate" computation uses weighted median instead of simple median.

In `compute_confidence()`, add a `freshness_penalty` when the most recent source is >1 year old: reduce score by 10 points. When >2 years old: reduce by 20 points.

### 3d. Scenario Engine: Fix Likelihood Scaling

**File:** `src/analysis/scenario_engine.py`

**Problem:** `likelihood = min(raw_likelihood * 2, 1.0)` — arbitrary 2x multiplier makes single-layer scenarios unrealistically high (0.60 base → 96%).

**Fix:** Remove the 2x multiplier. Use raw combined probability directly:
```python
not_happening = product(1 - layer.probability for layer in layers)
likelihood = 1 - not_happening
# No scaling — let the probability speak for itself
```

Add a `likelihood_method` field to the response: `"combined_independent"` so the UI can display methodology.

### 3e. Forecasting: Conservative Confidence Formula

**File:** `src/analysis/cobalt_forecasting.py`

**Problem:** `confidence_pct = min(90, r_squared * 85 + n_quarters)` inflates scores — R²=0.5 with 8 quarters gives 70%.

**Fix:** Use a more conservative formula that penalizes low R² harder:
```python
# R² must be >0.3 to contribute meaningfully
r2_component = max(0, (r_squared - 0.3)) * 100  # 0-70 range
data_component = min(15, n_quarters * 1.5)       # 0-15 range
confidence_pct = min(85, r2_component + data_component)
```

This gives: R²=0.5 with 8 quarters → 32% (was 70%). R²=0.8 with 12 quarters → 68% (was 80%). Much more honest.

### 3f. Forecasting: Accuracy Tracking Stub

**File:** `src/analysis/cobalt_forecasting.py`

Add a `_store_forecast_snapshot()` function that saves the current forecast (date, predicted prices for next 4 quarters, R², confidence) to a JSON file at `data/cobalt_forecast_history.json`. Called each time `_compute_price_forecast()` runs successfully.

This creates the data foundation for future backtesting (compare predicted vs actual when actuals arrive). Does not add backtesting logic yet — just the data capture.

---

## Tier 4 — Stretch Goals

### 4a. Analyst Feedback Loop for Alert Rules

**File:** `src/analysis/cobalt_alert_engine.py`

When an analyst marks an alert as "False Positive" via `/psi/alerts/cobalt/action`, track the rule that generated it. If a rule accumulates >30% false positive rate over 20+ actions, auto-raise its severity threshold by 1.

Implementation: Add a `_load_rule_stats()` function that reads from the MitigationAction table, groups by rule_id, computes FP rate, and adjusts thresholds.

### 4b. Live Altman Z-Score for Public Cobalt Players

**File:** `src/analysis/financial_scoring.py`

For the 15 publicly-traded cobalt players (already tracked via `cobalt_players.py`), attempt to compute Altman Z-Score from Yahoo Finance balance sheet data (yfinance library already in requirements). Cache results for 24 hours. Fall back to seeded dossier values if fetch fails.

Update globe entity popups and Supplier Dossier to show "Live Z-Score" vs "Seeded Z-Score" badge.

---

## Test Plan

| Area | Tests |
|------|-------|
| Alert engine: all 8 queries | Verify loop iterates 8 times, not 4 |
| Alert aging | Verify severity demotion at 7/30/90 day thresholds |
| Confidence temporal decay | Verify old sources get lower weight |
| Scenario likelihood | Verify no 2x scaling, single 0.6 layer → 0.6 likelihood |
| Forecast confidence | Verify R²=0.5/n=8 → ~32%, not 70% |
| Forecast snapshot | Verify JSON file written with correct structure |
| Compliance data | Verify COMPLIANCE_DATA has cobalt sub-items |
| Compliance matrix | Verify updated stats match current codebase |

---

## Out of Scope

- ARIMA/Holt-Winters forecasting models (separate session)
- Live FOCI from Wikidata (needs corporate_graph.py redesign)
- Full French translation of dynamic content
- Deep-dive of remaining 29 minerals
- NSN resolution (requires NMCRL access)
