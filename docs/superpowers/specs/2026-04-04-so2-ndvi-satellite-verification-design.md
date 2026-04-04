# Design Spec: SO2 + NDVI Satellite Verification (Phase 1)

**Date:** 2026-04-04
**Status:** Approved
**Goal:** Add two new satellite signals — Sentinel-5P SO2 (smelting tracer for refineries) and Sentinel-2 NDVI/bare soil (mining activity for mines) — with tier-specific combined verdicts.

## Problem

Current satellite verification uses 2 signals (FIRMS thermal + Sentinel-5P NO2). FIRMS misses enclosed refineries, and NO2 is noisy in dense industrial zones. We need more independent confirmation channels, applied intelligently per facility type.

## Architecture

**No new Python files.** Both signals extend the existing `sentinel_no2.py` connector — same Copernicus OAuth, same Processing API endpoint, same cache/history pattern.

### Signal Summary

| Signal | Sensor | Resolution | Cadence | Best For | Status Categories |
|--------|--------|-----------|---------|----------|-------------------|
| Thermal | FIRMS VIIRS | 375m | 6hr | Mines (open pit) | ACTIVE / IDLE / UNKNOWN |
| NO2 | S5P TROPOMI | 5.5km | Daily | Both (isolated) | EMITTING / LOW_EMISSION / UNKNOWN |
| **SO2** | **S5P TROPOMI** | **5.5x3.5km** | **Daily** | **Refineries (smelting)** | **SMELTING / LOW_SO2 / UNKNOWN** |
| **NDVI** | **Sentinel-2 L2A** | **10m** | **Weekly** | **Mines (land change)** | **ACTIVE_MINING / MODERATE / VEGETATED / UNKNOWN** |

## SO2 Implementation

### Evalscript

```javascript
//VERSION=3
function setup(){
  return {
    input: ["SO2", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  // SO2 units: mol/m² — scale to 0-255 range
  // Typical industrial SO2: 0.0001-0.001 mol/m²
  var v = s.SO2 / 0.001 * 255;
  v = Math.min(255, Math.max(0, v));
  return [v, v, v, 255];
}
```

### Processing API Payload

Same as NO2 query but with `"s5pType": "SO2"` in data filter. Same 8x8 pixel output, same OFFL 5-day lag offset, same minQa: 50.

### Status Classification

```python
def compute_so2_status(facility_so2, background_so2):
    # Ratio >= 1.5 → SMELTING
    # Ratio < 1.5 → LOW_SO2
    # None → UNKNOWN
```

Threshold: 1.5x background (same as NO2). SO2 is a more specific industrial tracer than NO2 for pyrometallurgical processing — copper-cobalt smelters are significant SO2 sources.

### Methods

- `_query_bbox_so2(bbox, days)` — returns `{so2: float, cloud_free_pct: int}`
- `fetch_facility_so2(name, lat, lon, radius_deg, days)` — single facility
- `fetch_all_facilities_so2()` — all 18, with cache + history
- `_fallback_so2_data()` — seed data when no credentials

### History

- File: `data/sentinel_so2_history.json`
- Same 90-day cap, same snapshot pattern as NO2
- Backfill: `backfill_so2_history(days=30)`

## NDVI / Bare Soil Implementation

### Evalscript

```javascript
//VERSION=3
function setup(){
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-10);
  // NDVI: -1 to 1 → scale to 0-255 (128 = 0.0)
  var ndvi_scaled = Math.round((ndvi + 1) / 2 * 255);
  // SCL class 5 = bare soil → 255, else 0
  var bare = (s.SCL == 5) ? 255 : 0;
  return [ndvi_scaled, bare, 255, 255];
}
```

### Processing API Payload

- Data type: `sentinel-2-l2a`
- Time range: last 30 days (cloud-free composite)
- Max cloud coverage: 30%
- Output: 32x32 pixels (higher res needed for 10m NDVI accuracy)
- Bbox: use FIRMS facility radius (2-8km adaptive)

### Status Classification

```python
def compute_ndvi_status(bare_soil_pct, mean_ndvi):
    # bare_soil_pct > 60% → ACTIVE_MINING
    # bare_soil_pct 30-60% → MODERATE
    # bare_soil_pct < 30% → VEGETATED
    # None → UNKNOWN
```

No historical baseline needed — current bare soil percentage is the signal. Open-pit cobalt mines have distinctive bare-soil footprints (exposed laterite/sulfide ore, tailings, haul roads) that contrast sharply with surrounding vegetation.

### Methods

- `_query_bbox_ndvi(bbox, days)` — returns `{bare_soil_pct: float, mean_ndvi: float, cloud_free_pct: int}`
- `fetch_facility_ndvi(name, lat, lon, radius_deg, days)` — single facility
- `fetch_all_facilities_ndvi()` — mines only (skip refineries), with cache + history
- `_fallback_ndvi_data()` — seed data for 9 mines

### History

- File: `data/sentinel_ndvi_history.json`
- Same 90-day cap, same snapshot pattern
- Backfill: `backfill_ndvi_history(days=30)`

## Tier-Specific Combined Verdict

### New Signature

```python
def compute_combined_verdict(
    thermal_status: str,
    no2_status: str,
    so2_status: str = "UNKNOWN",
    ndvi_status: str = "UNKNOWN",
    facility_type: str = "mine",
) -> dict:
```

### Verdict Matrix

**Mines** — count confirming signals from: thermal, NO2, NDVI

| Confirming Signals | Verdict | Confidence |
|-------------------|---------|------------|
| 3/3 | CONFIRMED ACTIVE | high |
| 2/3 | ACTIVE | medium-high |
| 1/3 | LIKELY ACTIVE | medium |
| 0/3 | IDLE | low |

Active definitions for mines:
- Thermal: ACTIVE
- NO2: EMITTING
- NDVI: ACTIVE_MINING

**Refineries** — count confirming signals from: thermal, NO2, SO2

| Confirming Signals | Verdict | Confidence |
|-------------------|---------|------------|
| 3/3 | CONFIRMED ACTIVE | high |
| 2/3 | ACTIVE | medium-high |
| 1/3 | LIKELY ACTIVE | medium |
| 0/3 | IDLE | low |

Active definitions for refineries:
- Thermal: ACTIVE
- NO2: EMITTING
- SO2: SMELTING

### Sources List

The `sources` field in the verdict dict lists which signals confirmed activity (e.g., `["FIRMS VIIRS thermal", "Sentinel-5P NO2", "Sentinel-2 NDVI"]`).

### Backward Compatibility

When SO2/NDVI data is UNKNOWN (not yet fetched, or credentials missing), the verdict degrades gracefully to the current 2-signal logic. UNKNOWN signals are not counted as confirming OR denying.

## Globe Routes Changes

In `globe_routes.py` cobalt enrichment section, add two new blocks after NO2 enrichment:

1. **SO2 enrichment** — call `fetch_all_facilities_so2()`, attach `so2` dict to each facility
2. **NDVI enrichment** — call `fetch_all_facilities_ndvi()`, attach `ndvi` dict to mines only

Update verdict computation to pass all 4 signals + facility type:

```python
for mine in mineral.get("mines", []):
    mine["operational_verdict"] = compute_combined_verdict(
        thermal, no2, so2="UNKNOWN", ndvi=mine["ndvi"]["status"],
        facility_type="mine"
    )
for ref in mineral.get("refineries", []):
    ref["operational_verdict"] = compute_combined_verdict(
        thermal, no2, so2=ref["so2"]["status"], ndvi="UNKNOWN",
        facility_type="refinery"
    )
```

## Frontend Changes

### Verification Tab

- **Overlay chart:** Add SO2 bars (yellow, `#e6c619`) for refineries alongside thermal (red) and NO2 (purple). Add NDVI bare soil bars (green, `#6b9080`) for mines.
- **Verification score:** Update `computeVerificationScore()` to count 3 relevant signals instead of 2, based on facility type (detect from mine vs refinery array membership).
- **Signal badges:** Show which signals are active per card — e.g., "THERMAL + NO2 + SO2" for refineries.

### Alerts & Sensing Satellite Card

- Add SO2 and NDVI to KPI row (SO2 Smelting count, NDVI Active Mining count)
- Anomaly detection: add "VEGETATED_BUT_OPERATING" for mines with NDVI < 30% bare soil but reporting production
- Source badges: add "Sentinel-5P SO2" and "Sentinel-2 NDVI (10m)"

### Globe Layers

- **SO2 plumes:** Yellow ellipses (same 3-concentric pattern as NO2 purple) for SMELTING refineries. Toggleable "SO2 Emissions (S5P)" layer.
- **NDVI bare soil:** Orange-tinted ground overlay circles for ACTIVE_MINING mines. Toggleable "Mine Activity (NDVI)" layer.

### Dossier Popup

- New "SO2 Emissions" section for refineries (ratio, status, 30-day sparkline in yellow)
- New "Land Activity (NDVI)" section for mines (bare soil %, mean NDVI, 30-day sparkline in green)

## Scheduler

- **Job #29:** `poll_sentinel_so2` — daily 03:30 UTC, 300s timeout, backfills on first run
- **Job #30:** `poll_sentinel_ndvi` — weekly Sunday 04:00 UTC, 300s timeout (vegetation changes slowly)

## Tests

Extend `tests/test_sentinel_no2.py`:

- `test_so2_status_smelting()` — ratio >= 1.5 → SMELTING
- `test_so2_status_low()` — ratio < 1.5 → LOW_SO2
- `test_so2_status_unknown()` — None → UNKNOWN
- `test_ndvi_status_active_mining()` — bare soil > 60% → ACTIVE_MINING
- `test_ndvi_status_moderate()` — bare soil 30-60% → MODERATE
- `test_ndvi_status_vegetated()` — bare soil < 30% → VEGETATED
- `test_ndvi_status_unknown()` — None → UNKNOWN
- `test_combined_verdict_mine_3_signals()` — all 3 mine signals active → CONFIRMED ACTIVE
- `test_combined_verdict_mine_2_signals()` — 2/3 → ACTIVE
- `test_combined_verdict_refinery_3_signals()` — all 3 refinery signals → CONFIRMED ACTIVE
- `test_combined_verdict_refinery_so2_only()` — only SO2 → LIKELY ACTIVE
- `test_combined_verdict_backward_compat()` — UNKNOWN SO2/NDVI → degrades to 2-signal logic
- `test_fallback_so2_data()` — seed data loads
- `test_fallback_ndvi_data()` — seed data loads

## CDSE Budget Impact

Current usage: ~500-1000 PU/month (NO2 + thumbnails for 18 facilities).
Adding SO2 (18 facilities daily) + NDVI (9 mines weekly): ~300-500 PU/month additional.
Total: ~800-1500 PU/month — well within 10,000 PU/month free tier.
