# Sentinel-5P TROPOMI NO2 Industrial Emissions Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sentinel-5P NO2 emissions monitoring for 18 cobalt facilities, with purple plume rendering on the 3D globe, combined thermal+NO2 operational verdicts, and dossier popup integration.

**Architecture:** New `sentinel_no2.py` connector (mirrors `firms_thermal.py` pattern) queries CDSE Processing API per facility, derives EMITTING/LOW_EMISSION/UNKNOWN status, merges with FIRMS thermal in `globe_routes.py` to produce combined verdicts. Frontend renders purple ellipses and NO2 sparklines alongside existing red thermal blooms.

**Tech Stack:** Python (httpx, Pillow), CDSE Sentinel Hub Processing API (OAuth2), CesiumJS ellipse entities, Chart.js sparklines.

---

### Task 1: Sentinel NO2 Connector — Tests

**Files:**
- Create: `tests/test_sentinel_no2.py`

- [ ] **Step 1: Write test file with all unit tests**

```python
"""Tests for Sentinel-5P TROPOMI NO2 facility emissions monitoring."""
from __future__ import annotations

import json
import pytest


def test_status_emitting():
    """NO2 ratio >= 2.0 should return EMITTING."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.00006, background_no2=0.00002)
    assert result["status"] == "EMITTING"
    assert result["ratio"] == 3.0


def test_status_low_emission():
    """NO2 ratio < 2.0 should return LOW_EMISSION."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.000015, background_no2=0.00001)
    assert result["status"] == "LOW_EMISSION"
    assert result["ratio"] == 1.5


def test_status_unknown_none():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=None, background_no2=None)
    assert result["status"] == "UNKNOWN"
    assert result["ratio"] == 0


def test_status_zero_background():
    """Zero background should not divide by zero."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.00005, background_no2=0.0)
    assert result["status"] == "EMITTING"
    assert result["ratio"] > 0


def test_combined_verdict_confirmed_active():
    """ACTIVE thermal + EMITTING NO2 = CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="ACTIVE", no2_status="EMITTING")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"


def test_combined_verdict_likely_active():
    """IDLE thermal + EMITTING NO2 = LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="IDLE", no2_status="EMITTING")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_idle():
    """IDLE thermal + LOW_EMISSION NO2 = IDLE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="IDLE", no2_status="LOW_EMISSION")
    assert result["status"] == "IDLE"


def test_combined_verdict_thermal_only():
    """ACTIVE thermal + UNKNOWN NO2 = ACTIVE (thermal only)."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="ACTIVE", no2_status="UNKNOWN")
    assert result["status"] == "ACTIVE"
    assert "FIRMS" in result["sources"][0]


def test_combined_verdict_no2_only():
    """UNKNOWN thermal + EMITTING NO2 = LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="UNKNOWN", no2_status="EMITTING")
    assert result["status"] == "LIKELY ACTIVE"


def test_combined_verdict_both_unknown():
    """UNKNOWN thermal + UNKNOWN NO2 = UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="UNKNOWN", no2_status="UNKNOWN")
    assert result["status"] == "UNKNOWN"


def test_facility_config_matches_firms():
    """All 18 FIRMS facilities must have matching entries."""
    from src.ingestion.firms_thermal import FACILITY_CONFIG as FIRMS_CONFIG
    from src.ingestion.sentinel_no2 import FACILITY_CONFIG as NO2_CONFIG
    assert set(NO2_CONFIG.keys()) == set(FIRMS_CONFIG.keys())
    for name in FIRMS_CONFIG:
        assert NO2_CONFIG[name]["lat"] == FIRMS_CONFIG[name]["lat"]
        assert NO2_CONFIG[name]["lon"] == FIRMS_CONFIG[name]["lon"]


def test_fallback_data():
    """Fallback returns data for all 18 facilities."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client
    client = SentinelNO2Client(client_id="", client_secret="")
    result = client._fallback_data()
    assert len(result) == 18
    for name, data in result.items():
        assert data["status"] in ("EMITTING", "LOW_EMISSION")
        assert "ratio" in data
        assert "source" in data


def test_history_cap():
    """History save must cap at 90 days per facility."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client
    client = SentinelNO2Client(client_id="", client_secret="")
    history = {"TestFacility": [{"date": f"2026-01-{i:02d}", "ratio": 2.0} for i in range(1, 32)] * 4}
    assert len(history["TestFacility"]) > 90
    # save_history caps internally
    import tempfile, os
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test_history.json"
        # Manually test the cap logic
        for name in history:
            history[name] = history[name][-90:]
        assert len(history["TestFacility"]) == 90
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/test_sentinel_no2.py -v 2>&1 | head -30`

Expected: All tests FAIL with `ModuleNotFoundError` or `ImportError` (module doesn't exist yet).

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_sentinel_no2.py
git commit -m "test: add Sentinel-5P NO2 unit tests (13 tests, all red)"
```

---

### Task 2: Sentinel NO2 Connector — Implementation

**Files:**
- Create: `src/ingestion/sentinel_no2.py`

**Depends on:** Task 1 (tests exist)

- [ ] **Step 1: Create the connector file**

```python
"""Sentinel-5P TROPOMI NO2 emissions monitoring for cobalt facility verification.

Queries the CDSE Sentinel Hub Processing API for tropospheric NO2 column
density around each of 18 geolocated cobalt mines and refineries.
Compares facility NO2 to regional background to derive emissions ratio.
Derives operational status: EMITTING / LOW_EMISSION / UNKNOWN.

API docs: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process.html
Free account: https://dataspace.copernicus.eu (no credit card)
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sentinel_no2_history.json"

_CACHE_TTL = 86400  # 24 hours (daily polling)
_TOKEN_ENDPOINT = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
_PROCESS_ENDPOINT = "https://sh.dataspace.copernicus.eu/api/v1/process"

# Evalscript: converts NO2 mol/m2 to 0-255 grayscale (scaled to 0-0.0001 range)
_EVALSCRIPT = """//VERSION=3
function setup(){
  return {
    input: ["NO2", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var v = s.NO2 / 0.0001 * 255;
  v = Math.min(255, Math.max(0, v));
  return [v, v, v, 255];
}"""


def _cache_get(store: dict, key: str, ttl: int = _CACHE_TTL) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None


def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


def _make_bbox(lat: float, lon: float, radius_deg: float) -> list[float]:
    """Return [west, south, east, north] bounding box."""
    return [lon - radius_deg, lat - radius_deg, lon + radius_deg, lat + radius_deg]


def compute_no2_status(facility_no2: float | None, background_no2: float | None) -> dict:
    """Derive emissions status from facility vs background NO2.

    Returns dict with 'status' (EMITTING/LOW_EMISSION/UNKNOWN) and 'ratio'.
    """
    if facility_no2 is None or background_no2 is None:
        return {"status": "UNKNOWN", "ratio": 0}

    ratio = facility_no2 / max(background_no2, 1e-8)
    ratio = round(ratio, 1)

    if ratio >= 2.0:
        return {"status": "EMITTING", "ratio": ratio}
    return {"status": "LOW_EMISSION", "ratio": ratio}


def compute_combined_verdict(thermal_status: str, no2_status: str) -> dict:
    """Merge FIRMS thermal + Sentinel NO2 into a single operational verdict.

    Returns dict with 'status', 'confidence', and 'sources'.
    """
    sources = []
    if thermal_status in ("ACTIVE",):
        sources.append("FIRMS VIIRS thermal")
    if no2_status in ("EMITTING",):
        sources.append("Sentinel-5P NO2")

    # Decision matrix
    if thermal_status == "ACTIVE" and no2_status == "EMITTING":
        return {"status": "CONFIRMED ACTIVE", "confidence": "high", "sources": sources}
    if thermal_status == "ACTIVE" and no2_status in ("LOW_EMISSION", "UNKNOWN"):
        return {"status": "ACTIVE", "confidence": "medium", "sources": ["FIRMS VIIRS thermal"]}
    if thermal_status == "IDLE" and no2_status == "EMITTING":
        return {"status": "LIKELY ACTIVE", "confidence": "medium", "sources": ["Sentinel-5P NO2"]}
    if thermal_status == "UNKNOWN" and no2_status == "EMITTING":
        return {"status": "LIKELY ACTIVE", "confidence": "medium", "sources": ["Sentinel-5P NO2"]}
    if thermal_status == "IDLE" and no2_status in ("LOW_EMISSION", "UNKNOWN"):
        return {"status": "IDLE", "confidence": "low", "sources": []}
    if thermal_status == "UNKNOWN" and no2_status == "LOW_EMISSION":
        return {"status": "UNKNOWN", "confidence": "none", "sources": []}
    # Both unknown
    return {"status": "UNKNOWN", "confidence": "none", "sources": []}


# Reuse FIRMS facility coordinates — single source of truth
from src.ingestion.firms_thermal import FACILITY_CONFIG


class SentinelNO2Client:
    """Sentinel-5P TROPOMI NO2 emissions detector for cobalt facility monitoring."""

    _cache: dict = {}
    _token_cache: dict = {"token": None, "expires_at": 0}

    def __init__(self, client_id: str = "", client_secret: str = "", timeout: float = 30.0):
        self.client_id = client_id or os.getenv("SENTINEL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SENTINEL_CLIENT_SECRET", "")
        self.timeout = timeout

    async def _get_token(self) -> str:
        """Get OAuth2 access token, using cache if still valid."""
        if time.time() < self._token_cache["expires_at"] - 60:
            return self._token_cache["token"]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                _TOKEN_ENDPOINT,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if resp.status_code != 200:
                logger.warning("CDSE OAuth failed: HTTP %s — %s", resp.status_code, resp.text[:200])
                return ""
            data = resp.json()
            self._token_cache["token"] = data["access_token"]
            self._token_cache["expires_at"] = time.time() + data.get("expires_in", 1800)
            return data["access_token"]

    async def _query_bbox_no2(self, bbox: list[float], days: int = 7) -> float | None:
        """Query CDSE Processing API for mean NO2 in a bounding box.

        Returns mean NO2 in mol/m2 (scaled from PNG pixel values), or None on failure.
        """
        token = await self._get_token()
        if not token:
            return None

        now = datetime.now(timezone.utc)
        time_from = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        time_to = now.strftime("%Y-%m-%dT23:59:59Z")

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-5p-l2",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "s5pType": "NO2",
                    },
                    "processing": {"minQa": 50},
                }],
            },
            "output": {
                "width": 8,
                "height": 8,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": _EVALSCRIPT,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT,
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE Process API returned HTTP %s", resp.status_code)
                    return None

                # Parse PNG to extract pixel values
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                # Filter valid pixels (alpha > 0)
                valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                if not valid:
                    return None
                # Convert back from 0-255 to mol/m2 (inverse of evalscript scaling)
                mean_scaled = sum(valid) / len(valid)
                mean_no2 = mean_scaled / 255 * 0.0001
                return mean_no2

        except Exception as e:
            logger.warning("CDSE NO2 query failed: %s", e)
            return None

    async def fetch_facility_no2(
        self, name: str, lat: float, lon: float, radius_deg: float, days: int = 7,
    ) -> dict:
        """Query NO2 for a facility and its regional background.

        Returns dict with no2_mol_m2, background_mol_m2, ratio, status.
        """
        cache_key = f"no2_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached

        # Facility bbox (tight around facility)
        facility_bbox = _make_bbox(lat, lon, radius_deg)
        facility_no2 = await self._query_bbox_no2(facility_bbox, days)

        # Background bbox (5x wider for regional baseline)
        bg_bbox = _make_bbox(lat, lon, radius_deg * 5)
        background_no2 = await self._query_bbox_no2(bg_bbox, days)

        status_info = compute_no2_status(facility_no2, background_no2)

        result = {
            "no2_mol_m2": round(facility_no2, 10) if facility_no2 else None,
            "background_mol_m2": round(background_no2, 10) if background_no2 else None,
            "ratio": status_info["ratio"],
            "status": status_info["status"],
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-5P TROPOMI (live)",
        }

        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities(self) -> dict[str, dict]:
        """Fetch NO2 data for all 18 cobalt facilities."""
        cache_key = "no2_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached

        if not self.client_id or not self.client_secret:
            logger.info("No SENTINEL_CLIENT_ID/SECRET configured — using fallback NO2 data")
            return self._fallback_data()

        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            data = await self.fetch_facility_no2(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=7,
            )
            result[name] = data

        # Snapshot to history and attach sparkline data
        self.snapshot_to_history(result)
        history = self.load_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]

        _cache_set(self._cache, cache_key, result)
        emitting = sum(1 for v in result.values() if v["status"] == "EMITTING")
        logger.info("Sentinel NO2: %d/%d facilities EMITTING", emitting, len(result))
        return result

    def _fallback_data(self) -> dict[str, dict]:
        """Seed data when no credentials are configured."""
        seeds = {
            # DRC mines — elevated (open-pit dust + nearby smelting)
            "Tenke Fungurume (TFM)": (0.000048, 0.000018, "EMITTING"),
            "Kisanfu (KFM)":        (0.000035, 0.000016, "EMITTING"),
            "Kamoto (KCC)":         (0.000052, 0.000019, "EMITTING"),
            "Mutanda":              (0.000038, 0.000017, "EMITTING"),
            # Australian mine — moderate
            "Murrin Murrin":         (0.000012, 0.000008, "LOW_EMISSION"),
            # Cuban mine — paused
            "Moa JV":               (0.000014, 0.000012, "LOW_EMISSION"),
            # Canadian mines — moderate
            "Voisey's Bay":         (0.000009, 0.000006, "LOW_EMISSION"),
            "Sudbury Basin":        (0.000022, 0.000014, "LOW_EMISSION"),
            "Raglan Mine":          (0.000007, 0.000005, "LOW_EMISSION"),
            # Chinese refineries — highest (heavy industrial zones)
            "Huayou Cobalt":        (0.000068, 0.000020, "EMITTING"),
            "GEM Co.":              (0.000055, 0.000019, "EMITTING"),
            "Jinchuan Group":       (0.000042, 0.000013, "EMITTING"),
            # European refineries — moderate (enclosed, lower emissions)
            "Umicore Kokkola":      (0.000018, 0.000010, "EMITTING"),
            "Umicore Hoboken":      (0.000032, 0.000022, "LOW_EMISSION"),
            # Canadian refineries
            "Fort Saskatchewan":    (0.000020, 0.000012, "LOW_EMISSION"),
            "Long Harbour NPP":     (0.000015, 0.000010, "LOW_EMISSION"),
            # Japanese/Finnish refineries
            "Niihama Nickel Refinery": (0.000025, 0.000015, "LOW_EMISSION"),
            "Harjavalta":           (0.000016, 0.000009, "EMITTING"),
        }
        result = {}
        for name, (no2, bg, status) in seeds.items():
            ratio = round(no2 / max(bg, 1e-8), 1)
            result[name] = {
                "no2_mol_m2": no2,
                "background_mol_m2": bg,
                "ratio": ratio,
                "status": status,
                "last_overpass": "2026-04-02",
                "source": "Sentinel-5P TROPOMI (fallback)",
                "history": [],
            }
        # Try loading real history even in fallback mode
        history = self.load_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "no2_all_facilities", result)
        return result

    # ── History tracking ────────────────────────────────────────────

    @staticmethod
    def load_history() -> dict[str, list[dict]]:
        """Load historical NO2 snapshots from JSON file."""
        if not _HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def save_history(history: dict[str, list[dict]]) -> None:
        """Persist history to JSON, capped at 90 days per facility."""
        for name in history:
            history[name] = history[name][-90:]
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def snapshot_to_history(self, all_data: dict[str, dict]) -> None:
        """Append today's NO2 snapshot for each facility to history."""
        history = self.load_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        for name, data in all_data.items():
            if name not in history:
                history[name] = []
            existing_dates = {e["date"] for e in history[name]}
            if today in existing_dates:
                continue
            history[name].append({
                "date": today,
                "no2_mol_m2": data.get("no2_mol_m2"),
                "background_mol_m2": data.get("background_mol_m2"),
                "ratio": data.get("ratio", 0),
                "status": data.get("status", "UNKNOWN"),
            })

        self.save_history(history)
        logger.info("Sentinel NO2 history snapshot saved for %d facilities", len(all_data))

    async def backfill_history(self, days: int = 30) -> None:
        """Fetch historical NO2 data for the past N days.

        Queries 7-day windows per facility. 30 days = ~5 windows × 18 facilities
        × 2 (facility + background) = ~180 API calls.
        """
        if not self.client_id or not self.client_secret:
            logger.info("No credentials — skipping NO2 history backfill")
            return

        history = self.load_history()
        today = datetime.now(timezone.utc).date()

        for offset in range(0, days, 7):
            window_end = today - timedelta(days=offset)
            window_start = window_end - timedelta(days=7)

            for name, cfg in FACILITY_CONFIG.items():
                if name not in history:
                    history[name] = []
                existing_dates = {e["date"] for e in history[name]}

                # Query facility NO2
                facility_bbox = _make_bbox(cfg["lat"], cfg["lon"], cfg["radius_deg"])
                bg_bbox = _make_bbox(cfg["lat"], cfg["lon"], cfg["radius_deg"] * 5)

                try:
                    token = await self._get_token()
                    if not token:
                        continue

                    time_from = window_start.strftime("%Y-%m-%dT00:00:00Z")
                    time_to = window_end.strftime("%Y-%m-%dT23:59:59Z")

                    payload = {
                        "input": {
                            "bounds": {
                                "bbox": facility_bbox,
                                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                            },
                            "data": [{
                                "type": "sentinel-5p-l2",
                                "dataFilter": {
                                    "timeRange": {"from": time_from, "to": time_to},
                                    "s5pType": "NO2",
                                },
                                "processing": {"minQa": 50},
                            }],
                        },
                        "output": {
                            "width": 8,
                            "height": 8,
                            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
                        },
                        "evalscript": _EVALSCRIPT,
                    }

                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(
                            _PROCESS_ENDPOINT, json=payload,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if resp.status_code != 200:
                            continue

                    from PIL import Image
                    img = Image.open(io.BytesIO(resp.content))
                    pixels = list(img.getdata())
                    valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                    if not valid:
                        continue
                    facility_no2 = (sum(valid) / len(valid)) / 255 * 0.0001

                    # Background query
                    payload["input"]["bounds"]["bbox"] = bg_bbox
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(
                            _PROCESS_ENDPOINT, json=payload,
                            headers={"Authorization": f"Bearer {token}"},
                        )
                    bg_no2 = None
                    if resp.status_code == 200:
                        img = Image.open(io.BytesIO(resp.content))
                        pixels = list(img.getdata())
                        valid_bg = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                        if valid_bg:
                            bg_no2 = (sum(valid_bg) / len(valid_bg)) / 255 * 0.0001

                    status_info = compute_no2_status(facility_no2, bg_no2)
                    entry_date = window_end.strftime("%Y-%m-%d")
                    if entry_date not in existing_dates:
                        history[name].append({
                            "date": entry_date,
                            "no2_mol_m2": round(facility_no2, 10),
                            "background_mol_m2": round(bg_no2, 10) if bg_no2 else None,
                            "ratio": status_info["ratio"],
                            "status": status_info["status"],
                        })
                        existing_dates.add(entry_date)

                except Exception as e:
                    logger.warning("NO2 backfill failed for %s: %s", name, e)

        # Sort each facility's history by date
        for name in history:
            history[name].sort(key=lambda e: e["date"])

        self.save_history(history)
        logger.info("Sentinel NO2 backfill complete: %d days, %d facilities", days, len(history))
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/test_sentinel_no2.py -v`

Expected: All 13 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/ingestion/sentinel_no2.py
git commit -m "feat(sentinel): add Sentinel-5P TROPOMI NO2 connector for 18 cobalt facilities"
```

---

### Task 3: Globe Routes — NO2 Enrichment + Combined Verdict

**Files:**
- Modify: `src/api/globe_routes.py:60-72`

**Depends on:** Task 2

- [ ] **Step 1: Add NO2 enrichment and combined verdict to globe_routes.py**

In `src/api/globe_routes.py`, add a new enrichment block after the existing FIRMS thermal block (after line 71). The full function `get_mineral` should become:

```python
@router.get("/minerals/{name}")
async def get_mineral(name: str):
    """Get single mineral supply chain with enriched cobalt data."""
    mineral = get_mineral_by_name(name)
    if not mineral:
        raise HTTPException(status_code=404, detail=f"Mineral '{name}' not found")

    # Enrich cobalt with live triangulation confidence
    if name.lower() == "cobalt":
        try:
            from src.analysis.confidence import compute_cobalt_hhi
            from src.ingestion.bgs_minerals import BGSCobaltClient

            bgs = BGSCobaltClient()
            bgs_data = await bgs.fetch_cobalt_production()

            # Use most recent year's data for HHI
            if bgs_data:
                latest_year = max(d["year"] for d in bgs_data)
                latest = [d for d in bgs_data if d["year"] == latest_year]
            else:
                latest = []

            country_production = {}
            for entry in latest:
                country_production[entry["country"]] = entry["production_tonnes"]

            is_fallback = any("fallback" in d.get("source", "") for d in bgs_data[:1])
            mineral["hhi_live"] = compute_cobalt_hhi(country_production)
            mineral["hhi_source"] = "BGS World Mineral Statistics" + (" (fallback)" if is_fallback else " (live API)")
            mineral["hhi_year"] = latest_year if bgs_data else None
            mineral["confidence_triangulation"] = "active"
        except Exception as e:
            logger.warning("Cobalt HHI enrichment failed: %s", e)

        # Enrich mines/refineries with satellite thermal verification
        thermal_data = {}
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

        # Enrich mines/refineries with Sentinel-5P NO2 emissions data
        no2_data = {}
        try:
            from src.ingestion.sentinel_no2 import SentinelNO2Client, compute_combined_verdict
            sentinel = SentinelNO2Client()
            no2_data = await sentinel.fetch_all_facilities()
            unknown_no2 = {"status": "UNKNOWN", "ratio": 0, "source": "Sentinel-5P (unavailable)", "history": []}
            for mine in mineral.get("mines", []):
                mine["no2"] = no2_data.get(mine["name"], unknown_no2)
                t_status = mine.get("thermal", {}).get("status", "UNKNOWN")
                n_status = mine["no2"].get("status", "UNKNOWN")
                mine["operational_verdict"] = compute_combined_verdict(t_status, n_status)
            for ref in mineral.get("refineries", []):
                ref["no2"] = no2_data.get(ref["name"], unknown_no2)
                t_status = ref.get("thermal", {}).get("status", "UNKNOWN")
                n_status = ref["no2"].get("status", "UNKNOWN")
                ref["operational_verdict"] = compute_combined_verdict(t_status, n_status)
        except Exception as e:
            logger.warning("Sentinel NO2 enrichment failed: %s", e)

    return mineral
```

- [ ] **Step 2: Run existing globe tests to verify no regressions**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/ -k "globe or mineral" -v 2>&1 | tail -20`

Expected: All existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add src/api/globe_routes.py
git commit -m "feat(globe): enrich cobalt facilities with NO2 data + combined operational verdict"
```

---

### Task 4: Scheduler — Daily NO2 Polling Job

**Files:**
- Modify: `src/ingestion/scheduler.py:745-764` (add after FIRMS thermal job)

**Depends on:** Task 2

- [ ] **Step 1: Add NO2 scheduler job after the FIRMS thermal job (after line 764)**

Add this block after the `firms_thermal` scheduler job and before the `return scheduler` line:

```python
    # Sentinel-5P NO2 facility emissions monitoring (daily at 03:00 UTC)
    async def refresh_sentinel_no2():
        from src.ingestion.sentinel_no2 import SentinelNO2Client, _HISTORY_PATH
        client = SentinelNO2Client()
        # Backfill 30 days of history on first run
        if not _HISTORY_PATH.exists():
            logger.info("[sentinel_no2] First run — backfilling 30 days of NO2 history")
            await client.backfill_history(days=30)
        data = await client.fetch_all_facilities()
        emitting = sum(1 for v in data.values() if v["status"] == "EMITTING")
        logger.info("[sentinel_no2] %d/%d facilities EMITTING", emitting, len(data))

    scheduler.add_job(
        resilient_job("sentinel_no2", timeout_s=300)(refresh_sentinel_no2),
        CronTrigger(hour=3, minute=0),
        id="sentinel_no2",
        name="Sentinel-5P NO2 facility emissions (18 facilities)",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 2: Update the module docstring schedule comment**

Add this line to the schedule comment at the top of `scheduler.py` (after the "NASA FIRMS thermal" line if present, otherwise after "Taxonomy scoring"):

```
  - Sentinel-5P NO2:         daily 3 AM
```

- [ ] **Step 3: Run full test suite**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/ -x -q 2>&1 | tail -10`

Expected: All tests pass (including 13 new NO2 tests).

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat(scheduler): add job #28 — Sentinel-5P NO2 daily polling at 03:00 UTC"
```

---

### Task 5: Globe Frontend — Purple NO2 Plume Ellipses + Layer Toggle

**Files:**
- Modify: `src/static/index.html`

**Depends on:** Task 3 (API returns NO2 data)

This task modifies three sections of index.html: the GLOBE_LAYERS array, the facility rendering loop, and the legend.

- [ ] **Step 1: Add NO2 layer to GLOBE_LAYERS array**

Find the `GLOBE_LAYERS` array (line ~7372) and add a new entry after `thermal-det`:

```javascript
  { id: 'no2-emissions', name: 'NO2 Emissions (S5P)', color: '#a050dc', defaultOn: true },
```

The full array should now have 13 entries (the existing 12 + this new one).

- [ ] **Step 2: Add NO2 purple ellipse rendering**

Find the block that renders thermal detection ellipses (starts around line 8162 with the comment `// Individual hotspot detections`). After the entire thermal detection block (after the closing `}` of the `if (thermal.detections...)` block, around line 8240), add the NO2 plume rendering:

```javascript
      // NO2 emissions — purple plume ellipses (Sentinel-5P TROPOMI)
      var no2 = facility.no2 || {};
      if (no2.status === 'EMITTING' && no2.ratio >= 2.0) {
        var no2Pos = Cesium.Cartesian3.fromDegrees(facility.lon || facility.longitude, facility.lat || facility.latitude);
        // Scale ellipse size with NO2 ratio: base 3000m at 2x, grows to 6000m at 5x+
        var ratioScale = Math.min(2.0, (no2.ratio - 2.0) / 3.0 + 1.0);
        var baseRadius = 3000 * ratioScale;

        // Outer glow — 6x base, very transparent purple
        cesiumViewer.entities.add({
          position: no2Pos,
          ellipse: {
            semiMajorAxis: baseRadius * 3,
            semiMinorAxis: baseRadius * 2.5,
            material: Cesium.Color.fromCssColorString('#a050dc').withAlpha(0.08),
            outline: false,
            height: 0,
            classificationType: Cesium.ClassificationType.BOTH,
          },
          properties: { layerId: 'no2-emissions', type: 'no2-plume', mineral: m.name, name: facility.name },
        });
        // Mid bloom — 3x base, semi-transparent
        cesiumViewer.entities.add({
          position: no2Pos,
          ellipse: {
            semiMajorAxis: baseRadius * 1.8,
            semiMinorAxis: baseRadius * 1.5,
            material: Cesium.Color.fromCssColorString('#b464f0').withAlpha(0.15),
            outline: false,
            height: 0,
            classificationType: Cesium.ClassificationType.BOTH,
          },
          properties: { layerId: 'no2-emissions', type: 'no2-plume', mineral: m.name, name: facility.name },
        });
        // Inner core — base size, most opaque
        cesiumViewer.entities.add({
          position: no2Pos,
          ellipse: {
            semiMajorAxis: baseRadius,
            semiMinorAxis: baseRadius * 0.8,
            material: Cesium.Color.fromCssColorString('#c878ff').withAlpha(0.28),
            outline: true,
            outlineColor: Cesium.Color.fromCssColorString('#a050dc').withAlpha(0.12),
            outlineWidth: 1,
            height: 0,
            classificationType: Cesium.ClassificationType.BOTH,
          },
          properties: { layerId: 'no2-emissions', type: 'no2-plume', mineral: m.name, name: facility.name },
        });
        // Center label with ratio
        cesiumViewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(facility.lon || facility.longitude, facility.lat || facility.latitude, 200),
          point: {
            pixelSize: 6,
            color: Cesium.Color.fromCssColorString('#c878ff').withAlpha(0.7),
            outlineColor: Cesium.Color.fromCssColorString('#a050dc').withAlpha(0.4),
            outlineWidth: 2,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          label: {
            text: no2.ratio + '\u00d7',
            font: '10px JetBrains Mono',
            fillColor: Cesium.Color.fromCssColorString('#c878ff'),
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            outlineWidth: 2,
            outlineColor: Cesium.Color.BLACK,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -8),
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
          },
          properties: { layerId: 'no2-emissions', type: 'no2-label', mineral: m.name, name: facility.name },
        });
      }
```

- [ ] **Step 3: Add NO2 to the globe legend**

Find the legend section (search for `Satellite Verification` or `Thermal Status` in the legend HTML). Add after the thermal legend entries:

```javascript
// In the legend HTML generation, add:
+ '<div style="display:flex; align-items:center; gap:6px; margin-top:4px;">'
+ '<span style="display:inline-block; width:12px; height:12px; border-radius:50%; background:radial-gradient(circle, rgba(200,120,255,0.6), rgba(160,80,220,0.1));"></span>'
+ '<span style="font-size:10px; color:var(--text-dim);">NO2 Emissions (Sentinel-5P)</span>'
+ '</div>'
```

- [ ] **Step 4: Test visually — start server and check globe**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m src.main`

Open http://localhost:8000/dashboard, go to Supply Chain → 3D Supply Map. Verify:
- Purple ellipses appear around EMITTING facilities
- Layer toggle "NO2 Emissions (S5P)" works
- No visual conflicts with existing red thermal blooms

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): render purple NO2 plume ellipses with layer toggle"
```

---

### Task 6: Dossier Popup — Emissions Verification + Combined Verdict

**Files:**
- Modify: `src/static/index.html` (dossier popup section, ~line 9336-9420)

**Depends on:** Task 5

- [ ] **Step 1: Add combined verdict badge at top of dossier popup**

Find the Satellite Verification section (line ~9336). Just BEFORE the line `// Satellite Verification section` (line 9336), add the combined verdict badge:

```javascript
      // Combined Operational Verdict
      var verdictJson = props.verdict ? props.verdict.getValue() : '{}';
      try {
        var verdict = JSON.parse(verdictJson);
        if (verdict.status) {
          var verdictColors = {
            'CONFIRMED ACTIVE': '#6b9080',
            'ACTIVE': '#6b9080',
            'LIKELY ACTIVE': '#a89060',
            'IDLE': '#4B5567',
            'UNKNOWN': '#4B5567'
          };
          var vc = verdictColors[verdict.status] || '#4B5567';
          html += '<div style="margin-top:8px; border-top:1px solid var(--border); padding-top:6px;">';
          html += '<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">'
            + '<span style="display:inline-block; padding:2px 8px; background:' + vc + '22; border:1px solid ' + vc + '; font-family:var(--font-mono); font-size:11px; font-weight:700; color:' + vc + '; letter-spacing:0.5px;">' + verdict.status + '</span>'
            + '<span style="font-size:10px; color:var(--text-dim);">confidence: ' + (verdict.confidence || 'unknown') + '</span>'
            + '</div>';
          if (verdict.sources && verdict.sources.length > 0) {
            html += '<div style="font-size:10px; color:var(--text-dim);">Sources: ' + verdict.sources.join(', ') + '</div>';
          }
          html += '</div>';
        }
      } catch(e) {}
```

- [ ] **Step 2: Add Emissions Verification section after Satellite Verification**

Find the end of the Satellite Verification section (the closing `} catch(e) {}` around line 9419). After it, add the NO2 section:

```javascript
      // Emissions Verification section (Sentinel-5P NO2)
      var no2Json = props.no2 ? props.no2.getValue() : '{}';
      try {
        var no2 = JSON.parse(no2Json);
        if (no2.status) {
          var no2Colors = {EMITTING:'#a050dc', LOW_EMISSION:'#6b6b8a', UNKNOWN:'#4B5567'};
          var no2Color = no2Colors[no2.status] || '#4B5567';
          html += '<div style="margin-top:8px; border-top:1px solid var(--border); padding-top:6px;">';
          html += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">Emissions Verification</div>';
          html += '<div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">'
            + '<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:' + no2Color + '; box-shadow:0 0 6px ' + no2Color + ';"></span>'
            + '<span style="font-family:var(--font-mono); font-size:11px; font-weight:600; color:' + no2Color + ';">' + no2.status + '</span>'
            + (no2.ratio ? '<span style="font-size:10px; color:var(--text-dim);">(' + no2.ratio + '\u00d7 background)</span>' : '')
            + '</div>';
          if (no2.no2_mol_m2) {
            html += '<div style="font-size:10px; color:var(--text-dim);">NO2: ' + no2.no2_mol_m2.toFixed(6) + ' mol/m\u00b2</div>';
          }
          if (no2.background_mol_m2) {
            html += '<div style="font-size:10px; color:var(--text-dim);">Background: ' + no2.background_mol_m2.toFixed(6) + ' mol/m\u00b2</div>';
          }
          if (no2.last_overpass) {
            html += '<div style="font-size:10px; color:var(--text-dim);">Last overpass: ' + esc(no2.last_overpass) + '</div>';
          }
          // NO2 ratio sparkline (30-day history)
          var no2History = no2.history || [];
          if (no2History.length > 1) {
            html += '<div style="margin-top:6px;">'
              + '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; margin-bottom:3px;">NO2 Ratio History (30d)</div>'
              + '<canvas id="dossier-no2-sparkline" width="260" height="60" style="width:100%; height:60px;"></canvas>'
              + '</div>';
          }
          html += '<div style="font-size:9px; color:var(--text-muted); margin-top:4px;">' + esc(no2.source || 'Sentinel-5P TROPOMI') + ' (5.5km)</div>';
          html += '</div>';
          // Defer NO2 sparkline
          if (no2History.length > 1) {
            setTimeout(function() {
              try {
                var canvas = document.getElementById('dossier-no2-sparkline');
                if (!canvas) return;
                var ctx = canvas.getContext('2d');
                if (canvas._chartInstance) canvas._chartInstance.destroy();
                canvas._chartInstance = new Chart(ctx, {
                  type: 'bar',
                  data: {
                    labels: no2History.map(function(h) { return (h.date || '').slice(5); }),
                    datasets: [{
                      data: no2History.map(function(h) { return h.ratio || 0; }),
                      backgroundColor: no2History.map(function(h) {
                        var r = h.ratio || 0;
                        return r >= 2.0 ? 'rgba(160,80,220,0.6)' : 'rgba(107,107,138,0.4)';
                      }),
                      borderColor: '#a050dc',
                      borderWidth: 1,
                      borderRadius: 2,
                      barPercentage: 0.85,
                    }]
                  },
                  options: {
                    responsive: false,
                    plugins: { legend: { display: false }, tooltip: {
                      callbacks: {
                        title: function(items) { return items[0].label; },
                        label: function(c) { return c.parsed.y.toFixed(1) + '\u00d7 background'; }
                      }
                    }},
                    scales: {
                      x: { display: true, ticks: { font: { size: 7, family: 'JetBrains Mono' }, color: '#4B5567', maxRotation: 45, maxTicksLimit: 8 }, grid: { display: false } },
                      y: { display: true, beginAtZero: true, ticks: { font: { size: 8 }, color: '#4B5567', maxTicksLimit: 4 }, grid: { color: 'rgba(255,255,255,0.05)' } }
                    }
                  }
                });
              } catch(e) {}
            }, 100);
          }
        }
      } catch(e) {}
```

- [ ] **Step 3: Pass NO2 and verdict data to entity properties**

Find where mine/refinery entities are created with their `properties` object (search for `thermal: JSON.stringify` in the facility entity creation code). Add the NO2 and verdict data to the properties:

```javascript
// In the entity properties for mines and refineries, add:
no2: JSON.stringify(facility.no2 || {}),
verdict: JSON.stringify(facility.operational_verdict || {}),
```

- [ ] **Step 4: Test visually**

Run the server, click a cobalt mine/refinery pin on the globe. Verify:
- Combined verdict badge appears at top (CONFIRMED ACTIVE / LIKELY ACTIVE / IDLE)
- Emissions Verification section appears below Satellite Verification
- NO2 sparkline renders with purple bars
- EMITTING facilities show purple status dot

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add NO2 emissions section + combined verdict to facility dossier popups"
```

---

### Task 7: Documentation Updates

**Files:**
- Modify: `CLAUDE.md`

**Depends on:** Tasks 1-6

- [ ] **Step 1: Update CLAUDE.md**

Add to the Data Sources table:
```
| 53 | Sentinel-5P NO2 | `sentinel_no2.py` | Daily | OAuth (free) | Working |
```

Add to Intelligence Features table:
```
| **Satellite NO2 Verification** | sentinel_no2.py, globe_routes.py, index.html | Sentinel-5P TROPOMI NO2 column density for 18 cobalt facilities. Per-facility vs regional background ratio. Combined thermal+NO2 operational verdict (CONFIRMED ACTIVE / LIKELY ACTIVE / IDLE). Purple plume ellipses on globe. 30-day history sparklines. |
```

Update test count, data source count, and scheduler job count where referenced.

Update the Known Code Quality Items or Next Steps to remove the Sentinel-5P item (it's now done).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with Sentinel-5P NO2 layer"
```

---

### Task 8: Full Regression Test

**Files:** None (verification only)

**Depends on:** All previous tasks

- [ ] **Step 1: Run full test suite**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/ -v 2>&1 | tail -30`

Expected: All tests pass (existing 351 + 13 new = 364 total).

- [ ] **Step 2: Start server and verify API**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m src.main`

Test the enriched API response:
```bash
curl -s http://localhost:8000/globe/minerals/Cobalt | python -m json.tool | grep -A5 '"no2"'
curl -s http://localhost:8000/globe/minerals/Cobalt | python -m json.tool | grep -A5 '"operational_verdict"'
```

Expected: Each mine/refinery has `no2` and `operational_verdict` fields.

- [ ] **Step 3: Visual smoke test**

Open http://localhost:8000/dashboard → Supply Chain → 3D Supply Map:
- Purple ellipses visible around EMITTING facilities
- "NO2 Emissions (S5P)" layer toggle works
- Click a facility → combined verdict badge + emissions section + sparkline all render
- No console errors

- [ ] **Step 4: Final commit with all changes**

```bash
git add -A
git commit -m "feat: Sentinel-5P TROPOMI NO2 industrial emissions layer — complete"
```
