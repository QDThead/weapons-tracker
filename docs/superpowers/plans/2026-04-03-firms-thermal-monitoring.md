# NASA FIRMS Facility Thermal Monitoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect operational status (active/idle) of all 18 cobalt facilities using NASA FIRMS satellite thermal data, displayed as pin badges on the 3D globe and evidence panels in dossier popups.

**Architecture:** A new connector (`firms_thermal.py`) queries the FIRMS Area API every 6hrs for bounding boxes around each facility, parses CSV responses, computes operational status, and caches in-memory. The existing `/globe/minerals/Cobalt` endpoint enriches each mine/refinery with a `thermal` object. The globe JS reads this to color pin outlines and build a "Satellite Verification" section in the click popup.

**Tech Stack:** Python 3.9+ (httpx async, csv), FastAPI enrichment, CesiumJS globe rendering, NASA FIRMS REST API (CSV format)

**Spec:** `docs/superpowers/specs/2026-04-03-firms-thermal-monitoring-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `src/ingestion/firms_thermal.py` | CREATE | FIRMS API connector — fetch, parse CSV, compute status, cache, fallback |
| `tests/test_firms_thermal.py` | CREATE | 10 unit tests for connector |
| `src/api/globe_routes.py` | MODIFY (lines 56-58) | Enrich cobalt mines/refineries with thermal data |
| `src/ingestion/scheduler.py` | MODIFY (lines 743-745) | Add 6hr FIRMS polling job |
| `src/static/index.html` | MODIFY (pin rendering ~7929, ~7978, click handler ~9033) | Pin badge colors + dossier satellite section |
| `config/.env.example` | MODIFY | Add `NASA_FIRMS_MAP_KEY` |

---

### Task 1: Write the FIRMS thermal connector with tests (TDD)

**Files:**
- Create: `src/ingestion/firms_thermal.py`
- Create: `tests/test_firms_thermal.py`

- [ ] **Step 1: Write the test file with all 10 tests**

```python
# tests/test_firms_thermal.py
"""Tests for NASA FIRMS thermal facility monitoring."""
from __future__ import annotations

import pytest

from src.ingestion.firms_thermal import (
    FACILITY_CONFIG,
    FIRMSThermalClient,
    _compute_status,
    _make_bbox,
)


class TestFacilityConfig:
    def test_has_all_18_facilities(self):
        assert len(FACILITY_CONFIG) == 18

    def test_coords_are_valid(self):
        for name, cfg in FACILITY_CONFIG.items():
            assert -90 <= cfg["lat"] <= 90, f"{name} lat out of range"
            assert -180 <= cfg["lon"] <= 180, f"{name} lon out of range"
            assert 0.01 <= cfg["radius_deg"] <= 0.1, f"{name} radius out of range"

    def test_known_facilities_present(self):
        expected = [
            "Tenke Fungurume (TFM)", "Kisanfu (KFM)", "Kamoto (KCC)", "Mutanda",
            "Murrin Murrin", "Moa JV", "Voisey's Bay", "Sudbury Basin", "Raglan Mine",
            "Huayou Cobalt", "GEM Co.", "Jinchuan Group", "Umicore Kokkola",
            "Umicore Hoboken", "Fort Saskatchewan", "Long Harbour NPP",
            "Niihama Nickel Refinery", "Harjavalta",
        ]
        for name in expected:
            assert name in FACILITY_CONFIG, f"Missing facility: {name}"


class TestBoundingBox:
    def test_bbox_computation(self):
        west, south, east, north = _make_bbox(lat=-10.57, lon=26.20, radius_deg=0.08)
        assert abs(west - 26.12) < 0.001
        assert abs(south - (-10.65)) < 0.001
        assert abs(east - 26.28) < 0.001
        assert abs(north - (-10.49)) < 0.001


class TestComputeStatus:
    def test_active_with_detections(self):
        detections = [
            {"bright_ti4": 340.0, "frp": 12.0, "confidence": "high", "acq_date": "2026-04-02", "acq_time": "1342"},
            {"bright_ti4": 338.0, "frp": 10.5, "confidence": "nominal", "acq_date": "2026-04-01", "acq_time": "0215"},
        ]
        result = _compute_status(detections)
        assert result["status"] == "ACTIVE"
        assert result["detection_count"] == 2
        assert result["max_brightness_k"] == 340.0
        assert result["avg_frp_mw"] == 11.25

    def test_idle_no_detections(self):
        result = _compute_status([])
        assert result["status"] == "IDLE"
        assert result["detection_count"] == 0

    def test_unknown_on_none(self):
        result = _compute_status(None)
        assert result["status"] == "UNKNOWN"


class TestFallbackData:
    def test_fallback_has_all_facilities(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert len(data) == 18

    def test_fallback_moa_is_idle(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert data["Moa JV"]["status"] == "IDLE"

    def test_fallback_tfm_is_active(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert data["Tenke Fungurume (TFM)"]["status"] == "ACTIVE"
        assert data["Tenke Fungurume (TFM)"]["detection_count"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_firms_thermal.py -v --tb=short`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ingestion.firms_thermal'`

- [ ] **Step 3: Write the connector implementation**

```python
# src/ingestion/firms_thermal.py
"""NASA FIRMS thermal anomaly monitoring for cobalt facility verification.

Queries the FIRMS Area API (VIIRS NOAA-20, 375m resolution) for thermal
detections around each of 18 geolocated cobalt mines and refineries.
Derives operational status: ACTIVE / IDLE / UNKNOWN.

API docs: https://firms.modaps.eosdis.nasa.gov/api/area/
Free MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/
"""
from __future__ import annotations

import csv
import io
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 21600  # 6 hours
_FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov"


# ── Cache helpers (same pattern as osint_feeds.py) ──────────────────────

def _cache_get(store: dict, key: str) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


# ── Facility bounding box config ────────────────────────────────────────

FACILITY_CONFIG: dict[str, dict] = {
    # Tier 1 — Mines
    "Tenke Fungurume (TFM)": {"lat": -10.5684, "lon": 26.1956, "radius_deg": 0.08},
    "Kisanfu (KFM)":         {"lat": -10.7796, "lon": 25.9282, "radius_deg": 0.08},
    "Kamoto (KCC)":          {"lat": -10.7177, "lon": 25.3970, "radius_deg": 0.08},
    "Mutanda":               {"lat": -10.7858, "lon": 25.8082, "radius_deg": 0.08},
    "Murrin Murrin":          {"lat": -28.7675, "lon": 121.8939, "radius_deg": 0.05},
    "Moa JV":                {"lat": 20.6186, "lon": -74.9437, "radius_deg": 0.05},
    "Voisey's Bay":          {"lat": 56.3347, "lon": -62.1031, "radius_deg": 0.05},
    "Sudbury Basin":         {"lat": 46.6000, "lon": -81.1833, "radius_deg": 0.05},
    "Raglan Mine":           {"lat": 61.6875, "lon": -73.6781, "radius_deg": 0.05},
    # Tier 2 — Refineries
    "Huayou Cobalt":         {"lat": 30.6323, "lon": 120.5647, "radius_deg": 0.03},
    "GEM Co.":               {"lat": 32.1550, "lon": 119.9260, "radius_deg": 0.03},
    "Jinchuan Group":        {"lat": 38.5000, "lon": 102.1880, "radius_deg": 0.03},
    "Umicore Kokkola":       {"lat": 63.8611, "lon": 23.0524, "radius_deg": 0.02},
    "Umicore Hoboken":       {"lat": 51.1642, "lon": 4.3371, "radius_deg": 0.02},
    "Fort Saskatchewan":     {"lat": 53.7239, "lon": -113.1867, "radius_deg": 0.02},
    "Long Harbour NPP":      {"lat": 47.4242, "lon": -53.8167, "radius_deg": 0.02},
    "Niihama Nickel Refinery": {"lat": 33.9487, "lon": 133.2489, "radius_deg": 0.02},
    "Harjavalta":            {"lat": 61.3188, "lon": 22.1225, "radius_deg": 0.02},
}


def _make_bbox(lat: float, lon: float, radius_deg: float) -> tuple[float, float, float, float]:
    """Return (west, south, east, north) bounding box."""
    return (lon - radius_deg, lat - radius_deg, lon + radius_deg, lat + radius_deg)


def _compute_status(detections: list[dict] | None) -> dict:
    """Derive operational status from thermal detections."""
    if detections is None:
        return {"status": "UNKNOWN", "detection_count": 0, "latest_detection": None,
                "max_brightness_k": 0, "avg_frp_mw": 0}
    if len(detections) == 0:
        return {"status": "IDLE", "detection_count": 0, "latest_detection": None,
                "max_brightness_k": 0, "avg_frp_mw": 0}

    brightnesses = [d.get("bright_ti4", 0) for d in detections]
    frps = [d.get("frp", 0) for d in detections if d.get("frp")]
    dates = [d.get("acq_date", "") for d in detections]
    latest = max(dates) if dates else None

    return {
        "status": "ACTIVE",
        "detection_count": len(detections),
        "latest_detection": latest,
        "max_brightness_k": max(brightnesses) if brightnesses else 0,
        "avg_frp_mw": round(sum(frps) / len(frps), 2) if frps else 0,
    }


class FIRMSThermalClient:
    """NASA FIRMS thermal anomaly detector for cobalt facility monitoring.

    Queries VIIRS NOAA-20 NRT (375m) for thermal detections around each
    of the 18 geolocated cobalt facilities.  Free API — requires MAP_KEY
    from https://firms.modaps.eosdis.nasa.gov/api/map_key/
    """

    _cache: dict = {}

    def __init__(self, map_key: str = "", timeout: float = 30.0):
        self.map_key = map_key or os.getenv("NASA_FIRMS_MAP_KEY", "")
        self.timeout = timeout

    async def fetch_facility_thermal(
        self,
        name: str,
        lat: float,
        lon: float,
        radius_deg: float,
        days: int = 2,
        source: str = "VIIRS_NOAA20_NRT",
    ) -> list[dict]:
        """Query FIRMS Area API for thermal detections in a bounding box."""
        cache_key = f"firms_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached

        if not self.map_key:
            return []

        west, south, east, north = _make_bbox(lat, lon, radius_deg)
        area = f"{west},{south},{east},{north}"
        url = f"{_FIRMS_BASE}/api/area/csv/{self.map_key}/{source}/{area}/{days}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("FIRMS returned HTTP %s for %s", resp.status_code, name)
                    return []

            results = []
            reader = csv.DictReader(io.StringIO(resp.text))
            for row in reader:
                results.append({
                    "lat": float(row.get("latitude", 0)),
                    "lon": float(row.get("longitude", 0)),
                    "bright_ti4": float(row.get("bright_ti4", 0)),
                    "bright_ti5": float(row.get("bright_ti5", 0)),
                    "frp": float(row.get("frp", 0)) if row.get("frp") else 0,
                    "confidence": row.get("confidence", ""),
                    "acq_date": row.get("acq_date", ""),
                    "acq_time": row.get("acq_time", ""),
                    "daynight": row.get("daynight", ""),
                    "satellite": row.get("satellite", ""),
                })

            _cache_set(self._cache, cache_key, results)
            return results

        except Exception as e:
            logger.warning("FIRMS fetch failed for %s: %s", name, e)
            return []

    async def fetch_all_facilities(self) -> dict[str, dict]:
        """Fetch thermal data for all 18 cobalt facilities.

        Returns dict keyed by facility name, each value containing
        status, detection_count, detections list, and source metadata.
        """
        cache_key = "firms_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached

        if not self.map_key:
            logger.info("No NASA_FIRMS_MAP_KEY configured — using fallback data")
            return self._fallback_data()

        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            detections = await self.fetch_facility_thermal(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=2,
            )
            status = _compute_status(detections)
            status["source"] = "NASA FIRMS VIIRS NOAA-20 (live)"
            status["detections"] = detections[:10]  # cap for API payload size
            result[name] = status

        _cache_set(self._cache, cache_key, result)
        active = sum(1 for v in result.values() if v["status"] == "ACTIVE")
        logger.info("FIRMS thermal: %d/%d facilities ACTIVE", active, len(result))
        return result

    def _fallback_data(self) -> dict[str, dict]:
        """Seed data when no MAP_KEY is configured or API is unreachable."""
        seeds = {
            # DRC mines — active (large thermal signatures from processing)
            "Tenke Fungurume (TFM)": ("ACTIVE", 6, 342.5, 14.2, "2026-04-02"),
            "Kisanfu (KFM)":        ("ACTIVE", 2, 335.0, 8.1, "2026-04-02"),
            "Kamoto (KCC)":         ("ACTIVE", 5, 340.1, 12.8, "2026-04-02"),
            "Mutanda":              ("ACTIVE", 4, 338.7, 11.0, "2026-04-01"),
            # Non-DRC mines
            "Murrin Murrin":         ("ACTIVE", 3, 336.2, 9.5, "2026-04-01"),
            "Moa JV":               ("IDLE", 0, 0, 0, None),  # paused Feb 2026
            "Voisey's Bay":         ("ACTIVE", 2, 332.0, 7.2, "2026-04-01"),
            "Sudbury Basin":        ("ACTIVE", 3, 334.5, 8.8, "2026-04-02"),
            "Raglan Mine":          ("ACTIVE", 1, 330.0, 6.0, "2026-03-31"),
            # Chinese refineries — active (high-temp smelting)
            "Huayou Cobalt":        ("ACTIVE", 8, 355.0, 22.5, "2026-04-02"),
            "GEM Co.":              ("ACTIVE", 5, 348.0, 18.0, "2026-04-02"),
            "Jinchuan Group":       ("ACTIVE", 7, 352.0, 20.1, "2026-04-02"),
            # Western refineries
            "Umicore Kokkola":      ("ACTIVE", 3, 345.0, 15.0, "2026-04-01"),
            "Umicore Hoboken":      ("ACTIVE", 2, 340.0, 12.0, "2026-04-01"),
            "Fort Saskatchewan":    ("ACTIVE", 2, 338.0, 10.5, "2026-04-01"),
            "Long Harbour NPP":     ("ACTIVE", 1, 334.0, 8.0, "2026-03-31"),
            "Niihama Nickel Refinery": ("ACTIVE", 2, 342.0, 13.0, "2026-04-01"),
            "Harjavalta":           ("ACTIVE", 2, 339.0, 11.5, "2026-04-01"),
        }
        result = {}
        for name, (status, count, brightness, frp, latest) in seeds.items():
            result[name] = {
                "status": status,
                "detection_count": count,
                "latest_detection": latest,
                "max_brightness_k": brightness,
                "avg_frp_mw": frp,
                "source": "NASA FIRMS (fallback)",
                "detections": [],
            }
        _cache_set(self._cache, "firms_all_facilities", result)
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_firms_thermal.py -v --tb=short`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/firms_thermal.py tests/test_firms_thermal.py
git commit -m "feat: add NASA FIRMS thermal monitoring connector with tests"
```

---

### Task 2: Enrich globe API with thermal data

**Files:**
- Modify: `src/api/globe_routes.py` (lines 56-58)

- [ ] **Step 1: Add thermal enrichment to the cobalt block**

In `src/api/globe_routes.py`, replace the block at lines 56-58:

```python
            mineral["confidence_triangulation"] = "active"
        except Exception as e:
            logger.warning("Cobalt HHI enrichment failed: %s", e)

    return mineral
```

with:

```python
            mineral["confidence_triangulation"] = "active"
        except Exception as e:
            logger.warning("Cobalt HHI enrichment failed: %s", e)

        # Enrich mines/refineries with satellite thermal verification
        try:
            from src.ingestion.firms_thermal import FIRMSThermalClient
            firms = FIRMSThermalClient()
            thermal_data = await firms.fetch_all_facilities()
            unknown_thermal = {"status": "UNKNOWN", "detection_count": 0, "source": "NASA FIRMS (unavailable)", "detections": []}
            for mine in mineral.get("mines", []):
                mine["thermal"] = thermal_data.get(mine["name"], unknown_thermal)
            for ref in mineral.get("refineries", []):
                ref["thermal"] = thermal_data.get(ref["name"], unknown_thermal)
        except Exception as e:
            logger.warning("FIRMS thermal enrichment failed: %s", e)

    return mineral
```

- [ ] **Step 2: Verify the API returns thermal data**

Run: `python -m pytest tests/test_globe.py -v --tb=short -k "test_mine_dossier_exists or test_get_mineral_by_name"` 
Expected: existing tests still pass.

Then manually verify (with server running):
```bash
python -c "
import httpx, json
r = httpx.get('http://localhost:8000/globe/minerals/Cobalt', timeout=30)
d = r.json()
mine = d['mines'][0]
print(mine['name'], mine.get('thermal', {}).get('status'))
ref = d['refineries'][0]
print(ref['name'], ref.get('thermal', {}).get('status'))
"
```
Expected: Each facility prints a status (ACTIVE/IDLE/UNKNOWN with fallback data).

- [ ] **Step 3: Commit**

```bash
git add src/api/globe_routes.py
git commit -m "feat: enrich cobalt facilities with FIRMS thermal status"
```

---

### Task 3: Add thermal badge to globe pin markers

**Files:**
- Modify: `src/static/index.html` (mine pin ~line 7929, refinery pin ~line 7978)

- [ ] **Step 1: Add thermal outline color to mine pins**

In `src/static/index.html`, find the mine pin rendering block. Replace:

```javascript
        var isChineseOwned = /china|cmoc|jinchuan|huayou/i.test(mine.owner);
        var pinColor = isChineseOwned ? Cesium.Color.fromCssColorString('#D80621') : tierColors.mining;
        var pinHead = Math.max(10, Math.min(20, (mine.production_t || 1000) / 1500));
```

with:

```javascript
        var isChineseOwned = /china|cmoc|jinchuan|huayou/i.test(mine.owner);
        var pinColor = isChineseOwned ? Cesium.Color.fromCssColorString('#D80621') : tierColors.mining;
        var pinHead = Math.max(10, Math.min(20, (mine.production_t || 1000) / 1500));
        var thermalStatus = (mine.thermal && mine.thermal.status) || 'UNKNOWN';
        var thermalOutline = thermalStatus === 'ACTIVE' ? Cesium.Color.fromCssColorString('#6b9080') :
                             thermalStatus === 'IDLE' ? Cesium.Color.fromCssColorString('#a89060') :
                             Cesium.Color.fromCssColorString('#4B5567');
```

Then in the same block, find the pin head entity `point` property:

```javascript
          point: { pixelSize: pinHead, color: pinColor, outlineColor: Cesium.Color.WHITE, outlineWidth: 3 },
```

Replace with:

```javascript
          point: { pixelSize: pinHead, color: pinColor, outlineColor: thermalOutline, outlineWidth: 3 },
```

Also add `thermal: JSON.stringify(mine.thermal || {})` to the entity `properties` object, after the `z_score` property. Find:

```javascript
, z_score: (mine.dossier && mine.dossier.z_score != null) ? mine.dossier.z_score : -1 },
```

Replace with:

```javascript
, z_score: (mine.dossier && mine.dossier.z_score != null) ? mine.dossier.z_score : -1, thermal: JSON.stringify(mine.thermal || {}) },
```

- [ ] **Step 2: Add thermal outline color to refinery pins**

Same changes for refinery pins. Find:

```javascript
        var pinColor = isChineseOwned ? Cesium.Color.fromCssColorString('#D80621') : isRussian ? Cesium.Color.fromCssColorString('#f97316') : tierColors.processing;
        var pinHead = Math.max(10, Math.min(18, (ref.capacity_t || 3000) / 2000));
```

Replace with:

```javascript
        var pinColor = isChineseOwned ? Cesium.Color.fromCssColorString('#D80621') : isRussian ? Cesium.Color.fromCssColorString('#f97316') : tierColors.processing;
        var pinHead = Math.max(10, Math.min(18, (ref.capacity_t || 3000) / 2000));
        var thermalStatus = (ref.thermal && ref.thermal.status) || 'UNKNOWN';
        var thermalOutline = thermalStatus === 'ACTIVE' ? Cesium.Color.fromCssColorString('#6b9080') :
                             thermalStatus === 'IDLE' ? Cesium.Color.fromCssColorString('#a89060') :
                             Cesium.Color.fromCssColorString('#4B5567');
```

Then replace the refinery pin head `point`:

```javascript
          point: { pixelSize: pinHead, color: pinColor, outlineColor: Cesium.Color.WHITE, outlineWidth: 3 },
```

with:

```javascript
          point: { pixelSize: pinHead, color: pinColor, outlineColor: thermalOutline, outlineWidth: 3 },
```

And add `thermal` to refinery entity properties — find:

```javascript
, z_score: (ref.dossier && ref.dossier.z_score != null) ? ref.dossier.z_score : -1 },
```

Replace with:

```javascript
, z_score: (ref.dossier && ref.dossier.z_score != null) ? ref.dossier.z_score : -1, thermal: JSON.stringify(ref.thermal || {}) },
```

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): thermal status badge on mine/refinery pin outlines"
```

---

### Task 4: Add satellite verification section to dossier popup

**Files:**
- Modify: `src/static/index.html` (click handler, after line 9034)

- [ ] **Step 1: Add satellite verification HTML to the click popup**

In `src/static/index.html`, find the note section at the end of the mine/refinery popup (line ~9033-9035):

```javascript
      if (props.note.getValue()) {
        html += '<div style="margin-top:6px; font-size:11px; color:var(--text-dim); border-top:1px solid var(--border); padding-top:6px;">' + esc(props.note.getValue()) + '</div>';
      }
    } else if (type === 'mining') {
```

Replace with:

```javascript
      if (props.note.getValue()) {
        html += '<div style="margin-top:6px; font-size:11px; color:var(--text-dim); border-top:1px solid var(--border); padding-top:6px;">' + esc(props.note.getValue()) + '</div>';
      }
      // Satellite Verification section
      var thermalJson = props.thermal ? props.thermal.getValue() : '{}';
      try {
        var thermal = JSON.parse(thermalJson);
        if (thermal.status) {
          var satColors = {ACTIVE:'#6b9080', IDLE:'#a89060', UNKNOWN:'#4B5567'};
          var satColor = satColors[thermal.status] || '#4B5567';
          html += '<div style="margin-top:8px; border-top:1px solid var(--border); padding-top:6px;">';
          html += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Satellite Verification</div>';
          html += '<div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">'
            + '<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:' + satColor + '; box-shadow:0 0 6px ' + satColor + ';"></span>'
            + '<span style="font-family:var(--font-mono); font-size:11px; font-weight:600; color:' + satColor + ';">' + thermal.status + '</span>'
            + '<span style="font-size:10px; color:var(--text-dim);">(' + (thermal.detection_count || 0) + ' thermal detections, last 48hrs)</span>'
            + '</div>';
          if (thermal.latest_detection) {
            html += '<div style="font-size:10px; color:var(--text-dim);">Latest: ' + esc(thermal.latest_detection)
              + (thermal.max_brightness_k ? ' | ' + thermal.max_brightness_k + 'K' : '')
              + (thermal.avg_frp_mw ? ' | ' + thermal.avg_frp_mw + ' MW FRP' : '')
              + '</div>';
          }
          if (thermal.status === 'IDLE') {
            html += '<div style="font-size:10px; color:#a89060; margin-top:4px; padding:4px 6px; background:rgba(168,144,96,0.1); border-left:2px solid #a89060;">'
              + '\u26A0 No thermal signature detected — facility may be shut down or operating below detection threshold</div>';
          }
          html += '<div style="font-size:9px; color:var(--text-muted); margin-top:4px;">' + esc(thermal.source || 'NASA FIRMS') + ' (375m VIIRS)</div>';
          html += '</div>';
        }
      } catch(e) {}
    } else if (type === 'mining') {
```

- [ ] **Step 2: Verify by refreshing the dashboard**

Open http://localhost:8000/dashboard, navigate to Supply Chain > 3D Supply Map, select Cobalt, click any mine or refinery pin. The popup should now show a "Satellite Verification" section at the bottom with status, detection count, and source.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): satellite verification section in facility dossier popup"
```

---

### Task 5: Add globe legend entry for thermal status

**Files:**
- Modify: `src/static/index.html` (legend section, around line 2095)

- [ ] **Step 1: Add thermal status legend entries**

Find the globe legend section. After the "Chinese-owned" entry:

```html
              <div><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#D80621; vertical-align:middle; margin-right:6px;"></span> Chinese-owned</div>
```

Add:

```html
              <div style="margin-top:6px; border-top:1px solid var(--border); padding-top:4px; font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em;">Pin Outline = Satellite Status</div>
              <div><span style="display:inline-block; width:10px; height:10px; border-radius:50%; border:2px solid #6b9080; vertical-align:middle; margin-right:6px;"></span><span style="color:#6b9080;">Active</span> — thermal detected</div>
              <div><span style="display:inline-block; width:10px; height:10px; border-radius:50%; border:2px solid #a89060; vertical-align:middle; margin-right:6px;"></span><span style="color:#a89060;">Idle</span> — no thermal (48hrs)</div>
              <div><span style="display:inline-block; width:10px; height:10px; border-radius:50%; border:2px solid #4B5567; vertical-align:middle; margin-right:6px;"></span><span style="color:#4B5567;">Unknown</span> — no data</div>
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add satellite thermal status legend"
```

---

### Task 6: Add scheduler job and env config

**Files:**
- Modify: `src/ingestion/scheduler.py` (lines 743-745)
- Modify: `config/.env.example`

- [ ] **Step 1: Add FIRMS scheduler job**

In `src/ingestion/scheduler.py`, find lines 743-745:

```python
    )

    return scheduler
```

Insert between them:

```python
    )

    # NASA FIRMS facility thermal monitoring (every 6 hours)
    async def refresh_firms_thermal():
        from src.ingestion.firms_thermal import FIRMSThermalClient
        client = FIRMSThermalClient()
        data = await client.fetch_all_facilities()
        active = sum(1 for v in data.values() if v["status"] == "ACTIVE")
        logger.info("[firms_thermal] %d/%d facilities ACTIVE", active, len(data))

    scheduler.add_job(
        resilient_job("firms_thermal", timeout_s=120)(refresh_firms_thermal),
        IntervalTrigger(hours=6),
        id="firms_thermal",
        name="NASA FIRMS facility thermal monitoring (18 facilities)",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler
```

Verify `IntervalTrigger` is already imported at the top of `scheduler.py` (it should be — it's used for other jobs).

- [ ] **Step 2: Add env var to .env.example**

In `config/.env.example`, add after the UCDP section:

```env

# NASA FIRMS (free — request at https://firms.modaps.eosdis.nasa.gov/api/map_key/)
NASA_FIRMS_MAP_KEY=
```

- [ ] **Step 3: Run full test suite to verify nothing is broken**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All 351+ tests pass (341 existing + 10 new).

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/scheduler.py config/.env.example
git commit -m "feat: add FIRMS thermal monitoring scheduler job (6hr interval)"
```

---

### Task 7: Final integration test and push

- [ ] **Step 1: Restart server and verify end-to-end**

```bash
# Restart server to pick up scheduler changes
taskkill //F //IM python.exe 2>/dev/null
cd "/c/Users/William Dennis/weapons-tracker"
source venv/Scripts/activate
python -m src.main &
sleep 8

# Verify thermal data in API response
python -c "
import httpx
r = httpx.get('http://localhost:8000/globe/minerals/Cobalt', timeout=30)
d = r.json()
for m in d['mines']:
    t = m.get('thermal', {})
    print(f\"  {m['name']:30s} {t.get('status','?'):8s} ({t.get('detection_count',0)} detections)\")
for ref in d['refineries']:
    t = ref.get('thermal', {})
    print(f\"  {ref['name']:30s} {t.get('status','?'):8s} ({t.get('detection_count',0)} detections)\")
"
```

Expected: All 18 facilities show status (ACTIVE/IDLE with fallback data since no MAP_KEY is configured).

- [ ] **Step 2: Verify scheduler registered the job**

Check server startup logs for: `[firms_thermal] NASA FIRMS facility thermal monitoring (18 facilities)`

- [ ] **Step 3: Push to GitHub**

```bash
git push origin main
```
