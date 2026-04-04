# Design Spec: Sentinel-5P TROPOMI NO2 Industrial Emissions Layer

**Date:** 2026-04-03
**Status:** Draft
**Depends on:** FIRMS thermal monitoring (completed Session B/C 2026-04-03)

## Problem

VIIRS thermal detection (375m) works well for open-pit mines but fails for enclosed refineries — most show 0 detections. 15 of 18 cobalt facilities have intermittent or no thermal signature. We need a complementary satellite data source that detects industrial activity even when heat isn't visible.

Sentinel-5P TROPOMI measures tropospheric NO2 column density at ~5.5km resolution with daily global revisit. Smelters and refineries emit NO2 as a byproduct of high-temperature metal processing. This fills the gap: facilities invisible to thermal IR are visible via their NO2 plumes.

## Goals

1. Poll all 18 cobalt facilities daily for tropospheric NO2 column density
2. Derive a background-relative emissions ratio per facility (e.g., "3.2x background")
3. Merge NO2 + thermal into a single combined operational verdict per facility
4. Render purple plume ellipses on the 3D supply chain globe
5. Display NO2 data and combined verdict in facility dossier popups
6. Track 90-day NO2 history with sparkline visualization

## Non-Goals

- Global NO2 WMTS tile overlay (could add later, not in this scope)
- Monitoring non-cobalt mineral facilities (extend when those minerals get deep-dive treatment)
- Real-time alerting on NO2 changes (daily cadence is sufficient)

## Data Source

**Copernicus Data Space Ecosystem (CDSE) Sentinel Hub Processing API**

- **Satellite:** Sentinel-5P (TROPOMI spectrometer)
- **Product:** L2 NO2, OFFL (offline reprocessed, 2-5 day latency)
- **Resolution:** ~5.5km x 3.5km at nadir
- **Revisit:** Daily global coverage
- **Auth:** OAuth2 client credentials flow
  - Token endpoint: `https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token`
  - Processing API: `https://sh.dataspace.copernicus.eu/api/v1/process`
- **Env vars:** `SENTINEL_CLIENT_ID`, `SENTINEL_CLIENT_SECRET`
- **Free quota:** 50,000 requests/month, 300 requests/minute
- **Verified:** Credentials tested successfully 2026-04-03. Jinchuan Group returned 0.000042 mol/m2 peak (elevated, consistent with active smelting).

## Architecture

### New File: `src/ingestion/sentinel_no2.py`

Follows the same pattern as `firms_thermal.py`:

```
SentinelNO2Client
├── __init__(client_id, client_secret, timeout)
├── _get_token() -> str                    # OAuth2 token with expiry caching
├── fetch_facility_no2(name, lat, lon, radius_deg, days) -> dict
│   ├── Query Processing API with facility bbox
│   ├── Query wider regional bbox for background
│   └── Return {no2_mol_m2, background_mol_m2, ratio, valid_pixels, date}
├── fetch_all_facilities() -> dict[str, dict]
│   ├── Poll all 18 facilities
│   ├── Snapshot to history
│   └── Return enriched results with history
├── _compute_status(facility_data) -> dict
│   └── Derive EMITTING / LOW_EMISSION / UNKNOWN
├── _fallback_data() -> dict[str, dict]    # Seed data when no credentials
├── load_history() / save_history()         # JSON persistence (90-day cap)
├── snapshot_to_history(all_data)           # Daily snapshot
└── backfill_history(days=30)              # Initial 30-day backfill
```

### Facility Bounding Boxes

Reuse the same 18 facilities and coordinates from `firms_thermal.FACILITY_CONFIG`. Two bbox sizes per facility:

- **Facility bbox:** `radius_deg` from FIRMS config (2-8km) — measures NO2 at the facility
- **Background bbox:** 5x the facility radius (10-40km) — measures regional baseline for ratio computation

### Processing API Request

Each facility query sends a POST to the Processing API with:

```json
{
  "input": {
    "bounds": {"bbox": [west, south, east, north]},
    "data": [{
      "type": "sentinel-5p-l2",
      "dataFilter": {
        "timeRange": {"from": "7 days ago", "to": "now"},
        "s5pType": "NO2"
      },
      "processing": {"minQa": 50}
    }]
  },
  "output": {
    "width": 4, "height": 4,
    "responses": [{"format": {"type": "image/png"}}]
  },
  "evalscript": "// Convert NO2 to 0-255 grayscale scaled to 0-0.0001 mol/m2"
}
```

Response is a small PNG (4x4 or 8x8 pixels). Parse with PIL to extract mean/max NO2 values. PNG format chosen over TIFF because PIL is already a dependency and parsing is simpler.

### NO2 Status Derivation

```python
def _compute_status(facility_no2: float, background_no2: float) -> dict:
    if facility_no2 is None or background_no2 is None:
        return {"status": "UNKNOWN", "ratio": 0}
    
    ratio = facility_no2 / max(background_no2, 1e-8)
    
    if ratio >= 2.0:
        status = "EMITTING"      # 2x+ background = active industrial emissions
    else:
        status = "LOW_EMISSION"  # At or below background
    
    return {"status": status, "ratio": round(ratio, 1)}
```

Thresholds:
- `ratio >= 2.0` → EMITTING (facility NO2 is at least double the regional background)
- `ratio < 2.0` → LOW_EMISSION (indistinguishable from background)
- No data / cloud cover / API failure → UNKNOWN

### Combined Operational Verdict

Computed in `globe_routes.py` when enriching cobalt data. Merges FIRMS thermal + Sentinel NO2:

| Thermal Status | NO2 Status | Combined Verdict | Badge Color |
|---------------|------------|-------------------|-------------|
| ACTIVE | EMITTING | **CONFIRMED ACTIVE** | Green |
| ACTIVE | LOW_EMISSION | **ACTIVE** | Green |
| ACTIVE | UNKNOWN | **ACTIVE** | Green |
| IDLE | EMITTING | **LIKELY ACTIVE** | Amber/Ochre |
| IDLE | LOW_EMISSION | **IDLE** | Grey |
| IDLE | UNKNOWN | **IDLE** | Grey |
| UNKNOWN | EMITTING | **LIKELY ACTIVE** | Amber/Ochre |
| UNKNOWN | LOW_EMISSION | **UNKNOWN** | Grey |
| UNKNOWN | UNKNOWN | **UNKNOWN** | Grey |

The key intelligence value is row 4: **IDLE thermal + EMITTING NO2 = LIKELY ACTIVE**. This catches enclosed refineries that VIIRS can't see.

### Token Caching

OAuth tokens from CDSE expire after 1800s (30 min). Cache the token in-memory with expiry timestamp. Request a new token only when the cached one has <60s remaining.

```python
_token_cache = {"token": None, "expires_at": 0}

async def _get_token(self) -> str:
    if time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]
    # POST to token endpoint, cache result
```

### Response Caching

- In-memory cache with 24-hour TTL (daily polling, no point re-fetching within the day)
- Same `_cache_get` / `_cache_set` pattern as FIRMS

## Globe Rendering

### Purple Plume Ellipses

Same technique as FIRMS thermal red blooms but purple to visually distinguish:

- 3 concentric ground-hugging ellipses per facility with EMITTING status
- Outer glow: `rgba(160, 80, 220, 0.15)` — 6x facility footprint
- Mid bloom: `rgba(180, 100, 240, 0.25)` — 3x footprint
- Inner core: `rgba(200, 120, 255, 0.4)` — 1.5x footprint
- Ellipse size scales with NO2 ratio: base radius at 2x, grows to 2x radius at 5x+
- `classificationType: BOTH`, `height: 0` (ground-hugging, same as thermal)
- Small center label showing ratio (e.g., "3.2x") visible at all zoom levels

### Layer Toggle

New entry in `GLOBE_LAYERS` config array:
```javascript
{id: 'no2-emissions', label: 'NO2 Emissions (S5P)', icon: '☁', default: true}
```

All NO2 ellipses and labels tagged with `layerId: 'no2-emissions'` for toggle control.

### Legend

Add to "Satellite Verification" legend section:
- Purple swatch: "NO2 Emissions (Sentinel-5P)"
- Scale: "2x bg = small, 5x+ bg = large"

## Dossier Popup

### Emissions Verification Section

Added below the existing "Satellite Verification" (thermal) section in mine/refinery click popups:

```
┌─────────────────────────────────────┐
│ 📡 Emissions Verification           │
│ Status: EMITTING  [purple badge]    │
│ NO2: 0.000042 mol/m² (3.2× bg)     │
│ Background: 0.000013 mol/m²         │
│ Source: Sentinel-5P TROPOMI (OFFL)  │
│ Last overpass: 2026-04-01           │
│ [===== NO2 sparkline 30d ======]    │
└─────────────────────────────────────┘
```

- Sparkline: 30-day bar chart of daily NO2 ratio values (purple bars)
- Same Chart.js mini-chart pattern as FIRMS FRP sparklines

### Combined Verdict Badge

At the top of the dossier popup, replace the current thermal-only status with:

```
CONFIRMED ACTIVE  [green badge]   ← thermal + NO2 both confirm
  Thermal: ACTIVE (4 detections, 346.5K)
  Emissions: EMITTING (3.2× background)
```

Or for the key gap-filling case:
```
LIKELY ACTIVE  [ochre badge]      ← NO2 detected but no thermal
  Thermal: IDLE (0 detections)
  Emissions: EMITTING (2.8× background)
```

## Scheduler

**Job #28** in `src/ingestion/scheduler.py`:

```python
scheduler.add_job(
    poll_sentinel_no2,
    trigger="cron",
    hour=3, minute=0,          # 03:00 UTC daily
    id="sentinel_no2_poll",
    name="Sentinel-5P NO2 facility emissions (18 facilities)",
    replace_existing=True,
)
```

- Runs daily at 03:00 UTC (offset from FIRMS at 0/6/12/18)
- First run triggers 30-day backfill if `data/sentinel_no2_history.json` doesn't exist
- Logs: "Sentinel NO2: X/18 facilities EMITTING"

## History & Persistence

### File: `data/sentinel_no2_history.json`

Same structure as FIRMS thermal history:

```json
{
  "Jinchuan Group": [
    {
      "date": "2026-04-01",
      "no2_mol_m2": 0.000042,
      "background_mol_m2": 0.000013,
      "ratio": 3.2,
      "valid_pixels": 12,
      "status": "EMITTING"
    }
  ]
}
```

- Capped at 90 days per facility
- Daily snapshots appended by `snapshot_to_history()`
- 30-day backfill queries 7-day windows (5 API calls per facility = 90 total)

## Environment Variables

| Variable | Required | Source |
|----------|----------|--------|
| `SENTINEL_CLIENT_ID` | No (fallback data without) | CDSE Dashboard → OAuth clients |
| `SENTINEL_CLIENT_SECRET` | No (fallback data without) | CDSE Dashboard → OAuth clients |

Already present in `config/.env.example` and `config/.env`.

## Fallback Data

When no credentials are configured, return seed data for all 18 facilities with realistic NO2 values:

- DRC mines: elevated (open-pit dust + nearby smelting)
- Chinese refineries: highest (heavy industrial zones, urban NO2 contribution)
- European/Canadian refineries: moderate (enclosed, lower emissions)
- Moa JV (Cuba): low (reported pause aligns with low NO2)

Seed data allows the globe visualization and dossier popups to render correctly during development and demos without API credentials.

## Tests: `tests/test_sentinel_no2.py`

| Test | What It Covers |
|------|---------------|
| `test_facility_config_matches_firms` | All 18 FIRMS facilities have NO2 config |
| `test_token_caching` | OAuth token reused within expiry window |
| `test_status_emitting` | ratio >= 2.0 → EMITTING |
| `test_status_low` | ratio < 2.0 → LOW_EMISSION |
| `test_status_unknown` | None values → UNKNOWN |
| `test_combined_verdict_confirmed` | ACTIVE + EMITTING → CONFIRMED ACTIVE |
| `test_combined_verdict_likely` | IDLE + EMITTING → LIKELY ACTIVE |
| `test_combined_verdict_idle` | IDLE + LOW → IDLE |
| `test_fallback_data` | Returns 18 facilities when no credentials |
| `test_background_ratio` | Wider bbox returns lower NO2 than facility bbox |
| `test_history_cap` | History capped at 90 days |
| `test_backfill` | 30-day backfill produces correct date range |

## API Changes

### Modified: `GET /globe/minerals/Cobalt`

Each mine/refinery gains new fields:

```json
{
  "name": "Jinchuan Group",
  "thermal": { "status": "ACTIVE", "..." },
  "no2": {
    "status": "EMITTING",
    "no2_mol_m2": 0.000042,
    "background_mol_m2": 0.000013,
    "ratio": 3.2,
    "last_overpass": "2026-04-01",
    "source": "Sentinel-5P TROPOMI (live)",
    "history": [{"date": "...", "ratio": 3.1}, ...]
  },
  "operational_verdict": {
    "status": "CONFIRMED ACTIVE",
    "confidence": "high",
    "sources": ["FIRMS VIIRS thermal", "Sentinel-5P NO2"]
  }
}
```

### No new endpoints

NO2 data is enriched into the existing `/globe/minerals/Cobalt` response alongside thermal data. No separate NO2 API endpoint needed.

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/ingestion/sentinel_no2.py` | NEW | Sentinel-5P NO2 connector (~250 lines) |
| `tests/test_sentinel_no2.py` | NEW | 12 tests (~120 lines) |
| `src/api/globe_routes.py` | MODIFY | Add NO2 enrichment + combined verdict |
| `src/ingestion/scheduler.py` | MODIFY | Add job #28 (daily 03:00 UTC) |
| `src/static/index.html` | MODIFY | Purple ellipses, layer toggle, dossier section, legend, sparkline |
| `config/.env.example` | NO CHANGE | Already has SENTINEL_CLIENT_ID/SECRET |
| `CLAUDE.md` | MODIFY | Update feature list, data source table |

## Dependencies

No new Python packages. Uses:
- `httpx` (already installed) — async HTTP for API calls
- `PIL` / `Pillow` (already installed) — PNG pixel extraction
- `json`, `time`, `os`, `io` — stdlib
