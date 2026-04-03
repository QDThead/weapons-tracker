# NASA FIRMS Facility Thermal Monitoring — Design Spec

**Date:** 2026-04-03
**Purpose:** Detect operational status (active/idle/shutdown) of all 18 cobalt mines and refineries using NASA FIRMS satellite thermal anomaly data. Enables fraud detection by cross-referencing reported production against satellite-observable thermal signatures.

## Problem

Cobalt supply chain data relies on self-reported production figures from mine operators and refineries. There is significant fraud risk — facilities may claim production while idle, or underreport to evade export quotas. We need an independent, satellite-based verification layer.

## Solution

Query NASA FIRMS (Fire Information for Resource Management System) every 6 hours for thermal anomaly detections around each of the 18 geolocated cobalt facilities. VIIRS 375m resolution detects the heat signatures of active smelters (1,200-1,500C) and large mining operations. Display results as pin badges on the 3D globe and evidence panels in facility dossiers.

## Data Source

- **API:** NASA FIRMS Area API v4
- **URL pattern:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{days}`
- **Sensor:** VIIRS NOAA-20 NRT (375m resolution, near-real-time within 3hrs of overpass)
- **Auth:** Free MAP_KEY (request at https://firms.modaps.eosdis.nasa.gov/api/map_key/)
- **Rate limit:** 5,000 requests per 10 minutes
- **Response format:** CSV (not JSON)
- **Our usage:** ~72 requests/day (18 facilities x 4 polls) — trivial against rate limit

## Architecture

```
NASA FIRMS API (CSV)
  -> src/ingestion/firms_thermal.py (FIRMSThermalClient)
    -> 6hr in-memory TTL cache
      -> src/api/globe_routes.py (enriches /globe/minerals/Cobalt)
        -> index.html (pin badge + dossier popup)
```

No new database table. Thermal detections are transient satellite data cached in-memory, same pattern as flight tracking.

## New File: `src/ingestion/firms_thermal.py`

### FIRMSThermalClient

```python
class FIRMSThermalClient:
    """NASA FIRMS thermal anomaly detector for cobalt facility monitoring."""
    
    _cache: dict = {}  # 6hr TTL
    
    def __init__(self, map_key: str = "", timeout: float = 30.0):
        self.map_key = map_key or os.getenv("NASA_FIRMS_MAP_KEY", "")
        self.timeout = timeout
    
    async def fetch_facility_thermal(self, lat, lon, radius_deg, days=2, source="VIIRS_NOAA20_NRT") -> list[dict]:
        """Query FIRMS Area API for thermal detections in bounding box around facility."""
    
    async def fetch_all_facilities(self) -> dict[str, dict]:
        """Iterate all 18 facilities, return dict keyed by name with detections + status."""
    
    def _compute_status(self, detections: list[dict]) -> dict:
        """Derive operational status from detection list."""
    
    def _fallback_data(self) -> dict[str, dict]:
        """Seed data for all 18 facilities when API unavailable."""
```

### Facility Bounding Box Config

Each facility gets a detection radius based on its type and setting:

| Facility | Type | Radius | Rationale |
|----------|------|--------|-----------|
| Tenke Fungurume | Open-pit mine | 0.08 deg (~8km) | 1,400 km2 concession |
| Kisanfu | Open-pit mine | 0.08 deg | Large concession area |
| Kamoto (KCC) | Underground + open-pit | 0.08 deg | Multi-pit complex |
| Mutanda | Open-pit mine | 0.08 deg | Large open-pit |
| Murrin Murrin | Open-pit + HPAL | 0.05 deg (~5km) | Remote, large HPAL plant |
| Moa JV | Open-pit + processing | 0.05 deg | Remote laterite operation |
| Voisey's Bay | Underground mine | 0.05 deg | Remote Labrador |
| Sudbury Basin | Underground complex | 0.05 deg | Large basin, multiple sites |
| Raglan Mine | Underground mine | 0.05 deg | Remote Nunavik |
| Huayou Cobalt | Refinery | 0.03 deg (~3km) | Industrial zone, Tongxiang |
| GEM Co. | Refinery | 0.03 deg | Industrial zone, Taixing |
| Jinchuan Group | Refinery/smelter | 0.03 deg | Industrial complex, Jinchang |
| Umicore Kokkola | Refinery | 0.02 deg (~2km) | Industrial park, urban |
| Umicore Hoboken | Refinery | 0.02 deg | Suburban Antwerp |
| Fort Saskatchewan | Refinery | 0.02 deg | Urban Alberta |
| Long Harbour NPP | Hydromet plant | 0.02 deg | Small coastal facility |
| Niihama | Refinery | 0.02 deg | Urban Japan |
| Harjavalta | Refinery | 0.02 deg | Small Finnish town |

### Status Logic

| Condition | Status | Color | Badge |
|-----------|--------|-------|-------|
| 1+ high/nominal confidence detection in last 48hrs | `ACTIVE` | Green (#6b9080) | Green dot on pin |
| 0 detections in last 48hrs | `IDLE` | Amber (#a89060) | Amber dot on pin |
| API failure or no MAP_KEY configured | `UNKNOWN` | Grey (#4B5567) | Grey dot on pin |

### Thermal Object (per facility)

```json
{
  "status": "ACTIVE",
  "detection_count": 7,
  "latest_detection": "2026-04-02",
  "max_brightness_k": 342.5,
  "avg_frp_mw": 12.3,
  "source": "NASA FIRMS VIIRS NOAA-20",
  "detections": [
    {
      "lat": -10.57,
      "lon": 26.19,
      "bright_ti4": 340.2,
      "frp": 11.5,
      "acq_date": "2026-04-02",
      "acq_time": "1342",
      "confidence": "high",
      "daynight": "D"
    }
  ]
}
```

### Fallback Seed Data

When no MAP_KEY is configured or API is unreachable, return realistic seed data:
- DRC mines (TFM, KCC, Mutanda): ACTIVE with 3-8 detections
- Kisanfu: ACTIVE with 1-2 detections (newer, smaller operation)
- Moa JV: IDLE with 0 detections (paused Feb 2026 per existing intel)
- Canadian mines (Voisey's Bay, Sudbury, Raglan): ACTIVE with 1-3 detections
- Chinese refineries (Huayou, GEM, Jinchuan): ACTIVE with 4-10 detections
- Western refineries: ACTIVE with 1-3 detections
- Harjavalta: ACTIVE with 1-2 (Nornickel, monitoring for ownership change)

## Modified File: `src/api/globe_routes.py`

In the existing cobalt enrichment block (where BGS HHI and forecast are added), add:

```python
from src.ingestion.firms_thermal import FIRMSThermalClient
firms = FIRMSThermalClient()
thermal_data = await firms.fetch_all_facilities()
for mine in mineral["mines"]:
    mine["thermal"] = thermal_data.get(mine["name"], {"status": "UNKNOWN", "detection_count": 0, "source": "NASA FIRMS (unavailable)"})
for ref in mineral["refineries"]:
    ref["thermal"] = thermal_data.get(ref["name"], {"status": "UNKNOWN", "detection_count": 0, "source": "NASA FIRMS (unavailable)"})
```

## Modified File: `src/static/index.html`

### Globe Pin Badge

In `renderGlobeEntities()`, after creating each mine/refinery pin head entity, read the `thermal.status` property and set outline color:

- Parse `thermal` from the entity properties
- Set pin head outline: green for ACTIVE, amber for IDLE, grey for UNKNOWN
- Append status dot character to label text: `"TFM\n32,000t \u25CF"` colored by status

### Dossier Popup — Satellite Verification Section

In the entity click handler (type === 'mine' or 'refinery'), append after existing risk/flag sections:

```
── SATELLITE VERIFICATION ──
Status: ACTIVE (7 thermal detections, last 48hrs)
Latest: 2026-04-02 13:42 UTC | 342.5K | 12.3 MW FRP
Source: NASA FIRMS VIIRS NOAA-20 (375m resolution)
[Detection list: date, time, brightness, FRP, confidence]
```

For IDLE facilities, show warning styling:
```
Status: IDLE (0 thermal detections in 48hrs)
Last known activity: 2026-03-28
WARNING: Facility reports active production but no satellite thermal signature detected
```

## Modified File: `src/ingestion/scheduler.py`

Add 6-hour interval job:

```python
async def refresh_firms_thermal():
    """Pre-warm FIRMS thermal cache for all 18 cobalt facilities."""
    from src.ingestion.firms_thermal import FIRMSThermalClient
    client = FIRMSThermalClient()
    data = await client.fetch_all_facilities()
    active = sum(1 for v in data.values() if v["status"] == "ACTIVE")
    logger.info("[firms_thermal] %d/%d facilities ACTIVE", active, len(data))

scheduler.add_job(
    resilient_job("firms_thermal", timeout_s=120)(refresh_firms_thermal),
    trigger=IntervalTrigger(hours=6),
    id="firms_thermal",
    name="NASA FIRMS facility thermal monitoring (18 facilities)",
    max_instances=1,
)
```

## Environment Variable

```
NASA_FIRMS_MAP_KEY=your_32_character_key_here
```

Add to `config/.env.example`. Free key from https://firms.modaps.eosdis.nasa.gov/api/map_key/

## Testing

New test file `tests/test_firms_thermal.py`:

- `test_facility_config_has_all_18` — verify all mines + refineries have bounding box config
- `test_facility_coords_match_mineral_data` — verify lat/lon in config matches mineral_supply_chains.py
- `test_compute_status_active` — detections present -> ACTIVE
- `test_compute_status_idle` — no detections -> IDLE
- `test_compute_status_unknown` — API failure -> UNKNOWN
- `test_fallback_data_has_all_facilities` — fallback covers all 18
- `test_fallback_moa_is_idle` — Moa JV seed data reflects known pause
- `test_bounding_box_computation` — verify lat/lon + radius -> correct west,south,east,north
- `test_csv_parsing` — verify VIIRS CSV columns are correctly mapped
- `test_frp_and_brightness_extracted` — key thermal fields present in parsed output

## Files Changed

| File | Change |
|------|--------|
| `src/ingestion/firms_thermal.py` | NEW — FIRMSThermalClient connector |
| `src/api/globe_routes.py` | MODIFIED — enrich cobalt mines/refineries with thermal data |
| `src/static/index.html` | MODIFIED — pin badge colors + dossier satellite verification section |
| `src/ingestion/scheduler.py` | MODIFIED — add 6hr FIRMS polling job |
| `config/.env.example` | MODIFIED — add NASA_FIRMS_MAP_KEY |
| `tests/test_firms_thermal.py` | NEW — 10 tests |
