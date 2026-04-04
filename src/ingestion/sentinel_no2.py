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

_SO2_EVALSCRIPT = """//VERSION=3
function setup(){
  return {
    input: ["SO2", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var v = s.SO2 / 0.001 * 255;
  v = Math.min(255, Math.max(0, v));
  return [v, v, v, 255];
}"""

_SO2_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sentinel_so2_history.json"

_NDVI_EVALSCRIPT = """//VERSION=3
function setup(){
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-10);
  var ndvi_scaled = Math.round((ndvi + 1) / 2 * 255);
  var bare = (s.SCL == 5) ? 255 : 0;
  return [ndvi_scaled, bare, 255, 255];
}"""

_NDVI_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sentinel_ndvi_history.json"


def _cache_get(store: dict, key: str, ttl: int = _CACHE_TTL) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < ttl:
        return entry[1]
    return None


def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


def _make_bbox(lat: float, lon: float, radius_deg: float) -> list[float]:
    return [lon - radius_deg, lat - radius_deg, lon + radius_deg, lat + radius_deg]


def compute_no2_status(facility_no2: float | None, background_no2: float | None) -> dict:
    if facility_no2 is None or background_no2 is None:
        return {"status": "UNKNOWN", "ratio": 0}
    ratio = facility_no2 / max(background_no2, 1e-8)
    ratio = round(ratio, 1)
    if ratio >= 1.5:
        return {"status": "EMITTING", "ratio": ratio}
    return {"status": "LOW_EMISSION", "ratio": ratio}


def compute_so2_status(facility_so2: float | None, background_so2: float | None) -> dict:
    """Classify SO2 emissions: SMELTING (>= 1.5x background) or LOW_SO2."""
    if facility_so2 is None or background_so2 is None:
        return {"status": "UNKNOWN", "ratio": 0}
    ratio = facility_so2 / max(background_so2, 1e-8)
    ratio = round(ratio, 1)
    if ratio >= 1.5:
        return {"status": "SMELTING", "ratio": ratio}
    return {"status": "LOW_SO2", "ratio": ratio}


def compute_ndvi_status(bare_soil_pct: float | None, mean_ndvi: float | None) -> dict:
    """Classify mine activity from Sentinel-2 bare soil percentage."""
    if bare_soil_pct is None or mean_ndvi is None:
        return {"status": "UNKNOWN", "bare_soil_pct": 0, "mean_ndvi": 0}
    if bare_soil_pct > 60:
        return {"status": "ACTIVE_MINING", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}
    if bare_soil_pct >= 30:
        return {"status": "MODERATE", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}
    return {"status": "VEGETATED", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}


def compute_combined_verdict(
    thermal_status: str,
    no2_status: str,
    so2_status: str = "UNKNOWN",
    ndvi_status: str = "UNKNOWN",
    facility_type: str = "mine",
) -> dict:
    """Tier-specific operational verdict from up to 4 satellite signals.

    Mines use: thermal + NO2 + NDVI (ignore SO2).
    Refineries use: thermal + NO2 + SO2 (ignore NDVI).
    UNKNOWN signals are excluded from the count (not confirming or denying).
    """
    sources = []
    active_count = 0
    known_count = 0

    # Thermal — applies to both types
    if thermal_status != "UNKNOWN":
        known_count += 1
        if thermal_status == "ACTIVE":
            active_count += 1
            sources.append("FIRMS VIIRS thermal")

    # NO2 — applies to both types
    if no2_status != "UNKNOWN":
        known_count += 1
        if no2_status == "EMITTING":
            active_count += 1
            sources.append("Sentinel-5P NO2")

    # Tier-specific third signal
    if facility_type == "refinery":
        if so2_status != "UNKNOWN":
            known_count += 1
            if so2_status == "SMELTING":
                active_count += 1
                sources.append("Sentinel-5P SO2")
    else:  # mine
        if ndvi_status != "UNKNOWN":
            known_count += 1
            if ndvi_status == "ACTIVE_MINING":
                active_count += 1
                sources.append("Sentinel-2 NDVI")

    if known_count == 0:
        return {"status": "UNKNOWN", "confidence": "none", "sources": []}

    # Score based on active signals out of known signals
    if active_count >= 3:
        return {"status": "CONFIRMED ACTIVE", "confidence": "high", "sources": sources}
    if active_count == 2:
        # 2/2 known = CONFIRMED, 2/3 known = ACTIVE
        if known_count == 2 and active_count == 2:
            return {"status": "CONFIRMED ACTIVE", "confidence": "high", "sources": sources}
        return {"status": "ACTIVE", "confidence": "medium-high", "sources": sources}
    if active_count == 1:
        return {"status": "LIKELY ACTIVE", "confidence": "medium", "sources": sources}
    return {"status": "IDLE", "confidence": "low", "sources": []}


# Reuse FIRMS facility coordinates — single source of truth
from src.ingestion.firms_thermal import FACILITY_CONFIG

MINE_NAMES = {
    "Tenke Fungurume (TFM)", "Kisanfu (KFM)", "Kamoto (KCC)", "Mutanda",
    "Murrin Murrin", "Moa JV", "Voisey's Bay", "Sudbury Basin", "Raglan Mine",
}


class SentinelNO2Client:
    _cache: dict = {}
    _token_cache: dict = {"token": None, "expires_at": 0}

    def __init__(self, client_id: str = "", client_secret: str = "", timeout: float = 30.0):
        self.client_id = client_id or os.getenv("SENTINEL_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("SENTINEL_CLIENT_SECRET", "")
        self.timeout = timeout

    async def _get_token(self) -> str:
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

    async def _query_bbox_no2(self, bbox: list[float], days: int = 7) -> dict | None:
        """Query NO2 for a bbox. Returns {no2: float, cloud_free_pct: int} or None."""
        token = await self._get_token()
        if not token:
            return None
        # OFFL data lags 2-5 days behind real-time; shift window back 5 days
        now = datetime.now(timezone.utc) - timedelta(days=5)
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
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE Process API returned HTTP %s", resp.status_code)
                    return None
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                total = len(pixels)
                valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                cloud_free_pct = round(len(valid) / max(total, 1) * 100)
                if not valid:
                    return {"no2": None, "cloud_free_pct": cloud_free_pct}
                mean_scaled = sum(valid) / len(valid)
                return {"no2": mean_scaled / 255 * 0.0001, "cloud_free_pct": cloud_free_pct}
        except Exception as e:
            logger.warning("CDSE NO2 query failed: %s", e)
            return None

    async def fetch_facility_thumbnail(self, lat: float, lon: float, radius_deg: float = 0.1, size: int = 256) -> bytes | None:
        """Fetch a Sentinel-2 true-color thumbnail for a facility location.

        Returns PNG bytes or None on failure. Cached for 24 hours per size.
        """
        cache_key = f"thumb_{lat:.4f}_{lon:.4f}_{size}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached

        token = await self._get_token()
        if not token:
            return None

        bbox = _make_bbox(lat, lon, max(radius_deg, 0.05))
        now = datetime.now(timezone.utc)
        time_from = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
        time_to = now.strftime("%Y-%m-%dT23:59:59Z")

        s2_evalscript = (
            "//VERSION=3\n"
            "function setup(){return{input:[\"B04\",\"B03\",\"B02\",\"dataMask\"],"
            "output:{bands:4,sampleType:\"AUTO\"}}}\n"
            "function evaluatePixel(s){return[2.5*s.B04,2.5*s.B03,2.5*s.B02,s.dataMask];}"
        )

        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "maxCloudCoverage": 30,
                    },
                }],
            },
            "output": {
                "width": size,
                "height": size,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": s2_evalscript,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("S2 thumbnail failed: HTTP %s", resp.status_code)
                    return None
                _cache_set(self._cache, cache_key, resp.content)
                return resp.content
        except Exception as e:
            logger.warning("S2 thumbnail failed: %s", e)
            return None

    async def fetch_facility_no2(self, name: str, lat: float, lon: float, radius_deg: float, days: int = 7) -> dict:
        cache_key = f"no2_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        # S5P pixels are ~5.5km — need at least 0.1 deg bbox to capture data
        no2_radius = max(radius_deg, 0.1)
        facility_bbox = _make_bbox(lat, lon, no2_radius)
        facility_result = await self._query_bbox_no2(facility_bbox, days)
        bg_bbox = _make_bbox(lat, lon, no2_radius * 5)
        bg_result = await self._query_bbox_no2(bg_bbox, days)
        facility_no2 = facility_result["no2"] if facility_result else None
        background_no2 = bg_result["no2"] if bg_result else None
        cloud_free_pct = facility_result["cloud_free_pct"] if facility_result else 0
        status_info = compute_no2_status(facility_no2, background_no2)
        result = {
            "no2_mol_m2": round(facility_no2, 10) if facility_no2 else None,
            "background_mol_m2": round(background_no2, 10) if background_no2 else None,
            "ratio": status_info["ratio"],
            "status": status_info["status"],
            "cloud_free_pct": cloud_free_pct,
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-5P TROPOMI (live)",
        }
        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities(self) -> dict[str, dict]:
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
        self.snapshot_to_history(result)
        history = self.load_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]
        _cache_set(self._cache, cache_key, result)
        emitting = sum(1 for v in result.values() if v["status"] == "EMITTING")
        logger.info("Sentinel NO2: %d/%d facilities EMITTING", emitting, len(result))
        return result

    def _fallback_data(self) -> dict[str, dict]:
        seeds = {
            "Tenke Fungurume (TFM)": (0.000048, 0.000018, "EMITTING"),
            "Kisanfu (KFM)":        (0.000035, 0.000016, "EMITTING"),
            "Kamoto (KCC)":         (0.000052, 0.000019, "EMITTING"),
            "Mutanda":              (0.000038, 0.000017, "EMITTING"),
            "Murrin Murrin":         (0.000012, 0.000008, "LOW_EMISSION"),
            "Moa JV":               (0.000014, 0.000012, "LOW_EMISSION"),
            "Voisey's Bay":         (0.000009, 0.000006, "LOW_EMISSION"),
            "Sudbury Basin":        (0.000022, 0.000014, "LOW_EMISSION"),
            "Raglan Mine":          (0.000007, 0.000005, "LOW_EMISSION"),
            "Huayou Cobalt":        (0.000068, 0.000020, "EMITTING"),
            "GEM Co.":              (0.000055, 0.000019, "EMITTING"),
            "Jinchuan Group":       (0.000042, 0.000013, "EMITTING"),
            "Umicore Kokkola":      (0.000018, 0.000010, "EMITTING"),
            "Umicore Hoboken":      (0.000032, 0.000022, "LOW_EMISSION"),
            "Fort Saskatchewan":    (0.000020, 0.000012, "LOW_EMISSION"),
            "Long Harbour NPP":     (0.000015, 0.000010, "LOW_EMISSION"),
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
        history = self.load_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "no2_all_facilities", result)
        return result

    @staticmethod
    def load_history() -> dict[str, list[dict]]:
        if not _HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def save_history(history: dict[str, list[dict]]) -> None:
        for name in history:
            history[name] = history[name][-90:]
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def snapshot_to_history(self, all_data: dict[str, dict]) -> None:
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

    # ── SO2 methods ──────────────────────────────────────────────────────

    async def _query_bbox_so2(self, bbox: list[float], days: int = 7) -> dict | None:
        """Query SO2 for a bbox. Returns {so2: float, cloud_free_pct: int} or None."""
        token = await self._get_token()
        if not token:
            return None
        now = datetime.now(timezone.utc) - timedelta(days=5)
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
                        "s5pType": "SO2",
                    },
                    "processing": {"minQa": 50},
                }],
            },
            "output": {
                "width": 8,
                "height": 8,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": _SO2_EVALSCRIPT,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE SO2 Process API returned HTTP %s", resp.status_code)
                    return None
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                total = len(pixels)
                valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                cloud_free_pct = round(len(valid) / max(total, 1) * 100)
                if not valid:
                    return {"so2": None, "cloud_free_pct": cloud_free_pct}
                mean_scaled = sum(valid) / len(valid)
                return {"so2": mean_scaled / 255 * 0.001, "cloud_free_pct": cloud_free_pct}
        except Exception as e:
            logger.warning("CDSE SO2 query failed: %s", e)
            return None

    async def fetch_facility_so2(self, name: str, lat: float, lon: float, radius_deg: float, days: int = 7) -> dict:
        """Fetch SO2 emissions data for a single facility."""
        cache_key = f"so2_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        so2_radius = max(radius_deg, 0.1)
        facility_bbox = _make_bbox(lat, lon, so2_radius)
        facility_result = await self._query_bbox_so2(facility_bbox, days)
        bg_bbox = _make_bbox(lat, lon, so2_radius * 5)
        bg_result = await self._query_bbox_so2(bg_bbox, days)
        facility_so2 = facility_result["so2"] if facility_result else None
        background_so2 = bg_result["so2"] if bg_result else None
        cloud_free_pct = facility_result["cloud_free_pct"] if facility_result else 0
        status_info = compute_so2_status(facility_so2, background_so2)
        result = {
            "so2_mol_m2": round(facility_so2, 10) if facility_so2 else None,
            "background_mol_m2": round(background_so2, 10) if background_so2 else None,
            "ratio": status_info["ratio"],
            "status": status_info["status"],
            "cloud_free_pct": cloud_free_pct,
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-5P TROPOMI SO2 (live)",
        }
        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities_so2(self) -> dict[str, dict]:
        """Fetch SO2 data for all 18 cobalt facilities."""
        cache_key = "so2_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        if not self.client_id or not self.client_secret:
            logger.info("No SENTINEL credentials — using fallback SO2 data")
            return self._fallback_so2_data()
        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            data = await self.fetch_facility_so2(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=7,
            )
            result[name] = data
        self._snapshot_so2_history(result)
        history = self._load_so2_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]
        _cache_set(self._cache, cache_key, result)
        smelting = sum(1 for v in result.values() if v["status"] == "SMELTING")
        logger.info("Sentinel SO2: %d/%d facilities SMELTING", smelting, len(result))
        return result

    def _fallback_so2_data(self) -> dict[str, dict]:
        """Seed SO2 data when no Copernicus credentials are configured."""
        seeds = {
            "Huayou Cobalt":           (0.00065, 0.00020, "SMELTING"),
            "GEM Co.":                 (0.00050, 0.00018, "SMELTING"),
            "Jinchuan Group":          (0.00070, 0.00015, "SMELTING"),
            "Umicore Kokkola":         (0.00020, 0.00012, "SMELTING"),
            "Umicore Hoboken":         (0.00028, 0.00020, "LOW_SO2"),
            "Fort Saskatchewan":       (0.00015, 0.00010, "LOW_SO2"),
            "Long Harbour NPP":        (0.00012, 0.00009, "LOW_SO2"),
            "Niihama Nickel Refinery":  (0.00022, 0.00013, "SMELTING"),
            "Harjavalta":              (0.00018, 0.00010, "SMELTING"),
            "Tenke Fungurume (TFM)":   (0.00008, 0.00007, "LOW_SO2"),
            "Kisanfu (KFM)":           (0.00006, 0.00006, "LOW_SO2"),
            "Kamoto (KCC)":            (0.00009, 0.00008, "LOW_SO2"),
            "Mutanda":                 (0.00007, 0.00006, "LOW_SO2"),
            "Murrin Murrin":           (0.00004, 0.00003, "LOW_SO2"),
            "Moa JV":                  (0.00005, 0.00005, "LOW_SO2"),
            "Voisey's Bay":            (0.00003, 0.00003, "LOW_SO2"),
            "Sudbury Basin":           (0.00012, 0.00009, "LOW_SO2"),
            "Raglan Mine":             (0.00002, 0.00002, "LOW_SO2"),
        }
        result = {}
        for name, (so2, bg, status) in seeds.items():
            ratio = round(so2 / max(bg, 1e-8), 1)
            result[name] = {
                "so2_mol_m2": so2,
                "background_mol_m2": bg,
                "ratio": ratio,
                "status": status,
                "last_overpass": "2026-04-03",
                "source": "Sentinel-5P TROPOMI SO2 (fallback)",
                "history": [],
            }
        history = self._load_so2_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "so2_all_facilities", result)
        return result

    @staticmethod
    def _load_so2_history() -> dict[str, list[dict]]:
        if not _SO2_HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_SO2_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _save_so2_history(history: dict[str, list[dict]]) -> None:
        for name in history:
            history[name] = history[name][-90:]
        _SO2_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SO2_HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def _snapshot_so2_history(self, all_data: dict[str, dict]) -> None:
        history = self._load_so2_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for name, data in all_data.items():
            if name not in history:
                history[name] = []
            existing_dates = {e["date"] for e in history[name]}
            if today in existing_dates:
                continue
            history[name].append({
                "date": today,
                "so2_mol_m2": data.get("so2_mol_m2"),
                "background_mol_m2": data.get("background_mol_m2"),
                "ratio": data.get("ratio", 0),
                "status": data.get("status", "UNKNOWN"),
            })
        self._save_so2_history(history)
        logger.info("Sentinel SO2 history snapshot saved for %d facilities", len(all_data))

    # ── NDVI methods ─────────────────────────────────────────────────────

    async def _query_bbox_ndvi(self, bbox: list[float], days: int = 30) -> dict | None:
        """Query NDVI + bare soil for a bbox. Returns {bare_soil_pct, mean_ndvi, cloud_free_pct} or None."""
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
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "maxCloudCoverage": 30,
                    },
                }],
            },
            "output": {
                "width": 32,
                "height": 32,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": _NDVI_EVALSCRIPT,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE NDVI query returned HTTP %s", resp.status_code)
                    return None
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                total = len(pixels)
                valid = [(p[0], p[1]) for p in pixels if len(p) >= 4 and p[2] > 0]
                cloud_free_pct = round(len(valid) / max(total, 1) * 100)
                if not valid:
                    return {"bare_soil_pct": None, "mean_ndvi": None, "cloud_free_pct": cloud_free_pct}
                bare_count = sum(1 for _, b in valid if b > 128)
                bare_soil_pct = round(bare_count / len(valid) * 100, 1)
                mean_ndvi_scaled = sum(n for n, _ in valid) / len(valid)
                mean_ndvi = round((mean_ndvi_scaled / 255 * 2) - 1, 3)
                return {"bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi, "cloud_free_pct": cloud_free_pct}
        except Exception as e:
            logger.warning("CDSE NDVI query failed: %s", e)
            return None

    async def fetch_facility_ndvi(self, name: str, lat: float, lon: float, radius_deg: float, days: int = 30) -> dict:
        """Fetch NDVI/bare-soil data for a single mine facility."""
        cache_key = f"ndvi_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        facility_bbox = _make_bbox(lat, lon, max(radius_deg, 0.05))
        result_data = await self._query_bbox_ndvi(facility_bbox, days)
        bare_soil_pct = result_data["bare_soil_pct"] if result_data else None
        mean_ndvi = result_data["mean_ndvi"] if result_data else None
        cloud_free_pct = result_data["cloud_free_pct"] if result_data else 0
        status_info = compute_ndvi_status(bare_soil_pct, mean_ndvi)
        result = {
            "bare_soil_pct": bare_soil_pct,
            "mean_ndvi": mean_ndvi,
            "status": status_info["status"],
            "cloud_free_pct": cloud_free_pct,
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-2 L2A NDVI (live)",
        }
        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities_ndvi(self) -> dict[str, dict]:
        """Fetch NDVI data for all 9 cobalt mines (skip refineries)."""
        cache_key = "ndvi_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        if not self.client_id or not self.client_secret:
            logger.info("No SENTINEL credentials — using fallback NDVI data")
            return self._fallback_ndvi_data()
        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            if name not in MINE_NAMES:
                continue
            data = await self.fetch_facility_ndvi(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=30,
            )
            result[name] = data
        self._snapshot_ndvi_history(result)
        history = self._load_ndvi_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]
        _cache_set(self._cache, cache_key, result)
        active = sum(1 for v in result.values() if v["status"] == "ACTIVE_MINING")
        logger.info("Sentinel NDVI: %d/%d mines ACTIVE_MINING", active, len(result))
        return result

    def _fallback_ndvi_data(self) -> dict[str, dict]:
        """Seed NDVI data for mines when no credentials are configured."""
        seeds = {
            "Tenke Fungurume (TFM)": (82.0, 0.12, "ACTIVE_MINING"),
            "Kisanfu (KFM)":         (71.0, 0.18, "ACTIVE_MINING"),
            "Kamoto (KCC)":          (78.0, 0.14, "ACTIVE_MINING"),
            "Mutanda":               (65.0, 0.22, "ACTIVE_MINING"),
            "Murrin Murrin":          (55.0, 0.28, "MODERATE"),
            "Moa JV":                (38.0, 0.42, "MODERATE"),
            "Voisey's Bay":          (45.0, 0.35, "MODERATE"),
            "Sudbury Basin":         (52.0, 0.30, "MODERATE"),
            "Raglan Mine":           (62.0, 0.20, "ACTIVE_MINING"),
        }
        result = {}
        for name, (bare, ndvi, status) in seeds.items():
            result[name] = {
                "bare_soil_pct": bare,
                "mean_ndvi": ndvi,
                "status": status,
                "last_overpass": "2026-04-03",
                "source": "Sentinel-2 L2A NDVI (fallback)",
                "history": [],
            }
        history = self._load_ndvi_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "ndvi_all_facilities", result)
        return result

    @staticmethod
    def _load_ndvi_history() -> dict[str, list[dict]]:
        if not _NDVI_HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_NDVI_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _save_ndvi_history(history: dict[str, list[dict]]) -> None:
        for name in history:
            history[name] = history[name][-90:]
        _NDVI_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _NDVI_HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def _snapshot_ndvi_history(self, all_data: dict[str, dict]) -> None:
        history = self._load_ndvi_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for name, data in all_data.items():
            if name not in history:
                history[name] = []
            existing_dates = {e["date"] for e in history[name]}
            if today in existing_dates:
                continue
            history[name].append({
                "date": today,
                "bare_soil_pct": data.get("bare_soil_pct"),
                "mean_ndvi": data.get("mean_ndvi"),
                "status": data.get("status", "UNKNOWN"),
            })
        self._save_ndvi_history(history)
        logger.info("Sentinel NDVI history snapshot saved for %d mines", len(all_data))

    # ── NO2 backfill ─────────────────────────────────────────────────────

    async def backfill_history(self, days: int = 30) -> None:
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
                                "dataFilter": {"timeRange": {"from": time_from, "to": time_to}, "s5pType": "NO2"},
                                "processing": {"minQa": 50},
                            }],
                        },
                        "output": {
                            "width": 8, "height": 8,
                            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
                        },
                        "evalscript": _EVALSCRIPT,
                    }
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(_PROCESS_ENDPOINT, json=payload, headers={"Authorization": f"Bearer {token}"})
                        if resp.status_code != 200:
                            continue
                    from PIL import Image
                    img = Image.open(io.BytesIO(resp.content))
                    pixels = list(img.getdata())
                    valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                    if not valid:
                        continue
                    facility_no2 = (sum(valid) / len(valid)) / 255 * 0.0001
                    payload["input"]["bounds"]["bbox"] = bg_bbox
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        resp = await client.post(_PROCESS_ENDPOINT, json=payload, headers={"Authorization": f"Bearer {token}"})
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
        for name in history:
            history[name].sort(key=lambda e: e["date"])
        self.save_history(history)
        logger.info("Sentinel NO2 backfill complete: %d days, %d facilities", days, len(history))
