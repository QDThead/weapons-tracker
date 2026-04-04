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
    if ratio >= 2.0:
        return {"status": "EMITTING", "ratio": ratio}
    return {"status": "LOW_EMISSION", "ratio": ratio}


def compute_combined_verdict(thermal_status: str, no2_status: str) -> dict:
    sources = []
    if thermal_status == "ACTIVE":
        sources.append("FIRMS VIIRS thermal")
    if no2_status == "EMITTING":
        sources.append("Sentinel-5P NO2")

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
    return {"status": "UNKNOWN", "confidence": "none", "sources": []}


# Reuse FIRMS facility coordinates — single source of truth
from src.ingestion.firms_thermal import FACILITY_CONFIG


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

    async def fetch_facility_thumbnail(self, lat: float, lon: float, radius_deg: float = 0.1) -> bytes | None:
        """Fetch a Sentinel-2 true-color thumbnail for a facility location.

        Returns PNG bytes or None on failure. Cached for 24 hours.
        """
        cache_key = f"thumb_{lat:.4f}_{lon:.4f}"
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
                "width": 256,
                "height": 256,
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
