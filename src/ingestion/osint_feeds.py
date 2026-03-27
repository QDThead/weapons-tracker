"""OSINT Feed Connectors — 5 lightweight data sources.

Provides:
  - FREDCommodityClient     — FRED commodity prices (no API key)
  - CISAKevClient           — CISA Known Exploited Vulnerabilities
  - GDACSDisasterClient     — GDACS active disaster alerts
  - CelestrakSatelliteClient — Celestrak military satellite TLEs
  - CSISMissileClient       — CSIS Missile Threat database
"""
from __future__ import annotations

import csv
import io
import logging
import re
import time
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared cache helpers (24-hour TTL per client)
# ---------------------------------------------------------------------------
_CACHE_TTL = 86400.0  # 24 hours


def _cache_get(store: dict, key: str) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# 1. FRED Commodity Prices
# ---------------------------------------------------------------------------

FRED_SERIES: dict[str, str] = {
    "Nickel":   "PNICKUSDM",
    "Aluminum": "PALUMUSDM",
    "Copper":   "PCOPPUSDM",
    "Oil WTI":  "DCOILWTICO",
    "Uranium":  "PURANUSDM",
    "Iron Ore": "PIORECRUSDM",
    "Tin":      "PTINUSDM",
}

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"


class FREDCommodityClient:
    """Fetches defence-critical commodity prices from FRED via direct CSV download."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_commodity_prices(self) -> dict:
        """Return commodity price data for defence-critical raw materials.

        Returns
        -------
        dict with key ``commodities``: list of {name, series, latest_price,
        latest_date, prices_30d}
        """
        cached = _cache_get(self._cache, "fred_commodities")
        if cached is not None:
            return cached

        commodities = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for name, series_id in FRED_SERIES.items():
                try:
                    url = f"{FRED_BASE}?id={series_id}&cosd=2024-01-01"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning("FRED %s returned HTTP %s", series_id, resp.status_code)
                        continue

                    # Parse CSV: observation_date,<SERIES_ID>
                    # Column names vary by series; grab the first two columns
                    reader = csv.reader(io.StringIO(resp.text))
                    prices_all: list[dict] = []
                    header = next(reader, None)  # skip header row
                    for row in reader:
                        if len(row) < 2:
                            continue
                        raw = row[0].strip()
                        val_str = row[1].strip()
                        if not raw or val_str in ("", "."):
                            continue
                        try:
                            price = float(val_str)
                            prices_all.append({"date": raw, "price": price})
                        except ValueError:
                            continue

                    if not prices_all:
                        continue

                    # Most recent 30 data points
                    prices_30d = prices_all[-30:]
                    latest = prices_all[-1]

                    commodities.append({
                        "name": name,
                        "series": series_id,
                        "latest_price": latest["price"],
                        "latest_date": latest["date"],
                        "unit": "USD per metric ton" if name not in ("Oil WTI",) else "USD per barrel",
                        "prices_30d": prices_30d,
                    })

                except Exception as exc:
                    logger.warning("FRED fetch failed for %s: %s", series_id, exc)

        result = {"commodities": commodities, "source": "FRED (St. Louis Fed)", "total": len(commodities)}
        _cache_set(self._cache, "fred_commodities", result)
        return result


# ---------------------------------------------------------------------------
# 2. CISA Known Exploited Vulnerabilities
# ---------------------------------------------------------------------------

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

DEFENCE_VENDORS = {
    "cisco", "microsoft", "fortinet", "palo alto", "f5", "vmware",
    "citrix", "adobe", "apple", "sap",
}


class CISAKevClient:
    """Fetches CISA Known Exploited Vulnerabilities filtered to defence-relevant vendors."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_kev_catalog(self) -> list[dict]:
        """Return KEV entries for defence-relevant vendors.

        Returns
        -------
        list of {cve_id, vendor, product, description, date_added, due_date,
        required_action}
        """
        cached = _cache_get(self._cache, "cisa_kev")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(CISA_KEV_URL)
                if resp.status_code != 200:
                    logger.warning("CISA KEV returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()
                vulns = data.get("vulnerabilities", [])

                results: list[dict] = []
                for v in vulns:
                    vendor = (v.get("vendorProject") or "").lower()
                    if not any(dv in vendor for dv in DEFENCE_VENDORS):
                        continue
                    results.append({
                        "cve_id": v.get("cveID", ""),
                        "vendor": v.get("vendorProject", ""),
                        "product": v.get("product", ""),
                        "description": v.get("shortDescription", ""),
                        "date_added": v.get("dateAdded", ""),
                        "due_date": v.get("dueDate", ""),
                        "required_action": v.get("requiredAction", ""),
                    })

                _cache_set(self._cache, "cisa_kev", results)
                return results

        except Exception as exc:
            logger.warning("CISA KEV fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 3. GDACS Disaster Alerts
# ---------------------------------------------------------------------------

GDACS_SEARCH_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"


class GDACSDisasterClient:
    """Fetches active Orange/Red disaster alerts from GDACS."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_active_disasters(self) -> list[dict]:
        """Return active Orange and Red level disaster events from the last 30 days.

        Returns
        -------
        list of {event_type, name, country, alert_level, latitude, longitude,
        date, severity}
        """
        cached = _cache_get(self._cache, "gdacs_disasters")
        if cached is not None:
            return cached

        try:
            now = datetime.now(timezone.utc)
            from_date = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            to_date = now.strftime("%Y-%m-%d")

            params = {
                "eventlist": "EQ,TC,FL,VO",
                "fromDate": from_date,
                "toDate": to_date,
                "alertlevel": "Orange;Red",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(GDACS_SEARCH_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("GDACS returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()
                # GDACS returns {"features": [...]} GeoJSON-like structure
                features = data.get("features", [])
                results: list[dict] = []
                for feat in features:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [None, None])
                    results.append({
                        "event_type": props.get("eventtype", ""),
                        "name": props.get("name", ""),
                        "country": props.get("country", ""),
                        "alert_level": props.get("alertlevel", ""),
                        "latitude": coords[1] if len(coords) > 1 else None,
                        "longitude": coords[0] if coords else None,
                        "date": props.get("fromdate", ""),
                        "severity": props.get("severitydata", {}).get("severity", ""),
                    })

                _cache_set(self._cache, "gdacs_disasters", results)
                return results

        except Exception as exc:
            logger.warning("GDACS fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 4. Celestrak Military Satellites
# ---------------------------------------------------------------------------

CELESTRAK_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=military&FORMAT=json"


class CelestrakSatelliteClient:
    """Fetches military satellite orbital data from Celestrak."""

    _cache: dict = {}

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_military_satellites(self) -> list[dict]:
        """Return orbital elements for military satellites.

        Returns
        -------
        list of {object_name, norad_id, inclination, period_minutes, epoch}
        """
        cached = _cache_get(self._cache, "celestrak_sats")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(CELESTRAK_URL)
                if resp.status_code != 200:
                    logger.warning("Celestrak returned HTTP %s", resp.status_code)
                    return []

                entries = resp.json()
                results: list[dict] = []
                for e in entries:
                    # Mean motion (rev/day) -> period in minutes
                    mean_motion = e.get("MEAN_MOTION")
                    period_min: float | None = None
                    if mean_motion and float(mean_motion) > 0:
                        period_min = round(1440.0 / float(mean_motion), 2)

                    results.append({
                        "object_name": e.get("OBJECT_NAME", ""),
                        "norad_id": e.get("NORAD_CAT_ID", ""),
                        "inclination": float(e["INCLINATION"]) if e.get("INCLINATION") else None,
                        "period_minutes": period_min,
                        "epoch": e.get("EPOCH", ""),
                    })

                _cache_set(self._cache, "celestrak_sats", results)
                return results

        except Exception as exc:
            logger.warning("Celestrak fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 5. CSIS Missile Threat Database
# ---------------------------------------------------------------------------

CSIS_MISSILE_URL = "https://missilethreat.csis.org/wp-json/wp/v2/missile?per_page=100"
CSIS_DEFSYS_URL = "https://missilethreat.csis.org/wp-json/wp/v2/defsys?per_page=100"

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(raw: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    if not raw:
        return ""
    text = _HTML_TAG_RE.sub(" ", raw)
    return _WHITESPACE_RE.sub(" ", text).strip()


class CSISMissileClient:
    """Fetches missile and defence system data from CSIS Missile Threat."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_missile_data(self) -> dict:
        """Return missiles and defence systems from CSIS Missile Threat database.

        Returns
        -------
        dict with keys ``missiles`` and ``defense_systems``
        """
        cached = _cache_get(self._cache, "csis_missiles")
        if cached is not None:
            return cached

        missiles: list[dict] = []
        defense_systems: list[dict] = []

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            # Fetch missiles
            try:
                resp = await client.get(CSIS_MISSILE_URL)
                if resp.status_code == 200:
                    for item in resp.json():
                        # ACF custom fields may be an empty list if not exposed publicly
                        acf = item.get("acf") or {}
                        if isinstance(acf, list):
                            acf = {}
                        content_raw = item.get("content", {})
                        content_text = _strip_html(
                            content_raw.get("rendered", "") if isinstance(content_raw, dict) else str(content_raw)
                        )
                        title_raw = item.get("title", {})
                        name = _strip_html(
                            title_raw.get("rendered", "") if isinstance(title_raw, dict) else str(title_raw)
                        )
                        missiles.append({
                            "name": name,
                            "country": acf.get("country", ""),
                            "type": acf.get("type", ""),
                            "range": acf.get("range", ""),
                            "status": acf.get("status", ""),
                            "description": content_text[:500] if content_text else "",
                            "slug": item.get("slug", ""),
                            "modified": item.get("modified", ""),
                        })
                else:
                    logger.warning("CSIS missiles returned HTTP %s", resp.status_code)
            except Exception as exc:
                logger.warning("CSIS missiles fetch failed: %s", exc)

            # Fetch defence systems
            try:
                resp = await client.get(CSIS_DEFSYS_URL)
                if resp.status_code == 200:
                    for item in resp.json():
                        acf = item.get("acf") or {}
                        if isinstance(acf, list):
                            acf = {}
                        title_raw = item.get("title", {})
                        name = _strip_html(
                            title_raw.get("rendered", "") if isinstance(title_raw, dict) else str(title_raw)
                        )
                        content_raw = item.get("content", {})
                        content_text = _strip_html(
                            content_raw.get("rendered", "") if isinstance(content_raw, dict) else str(content_raw)
                        )
                        defense_systems.append({
                            "name": name,
                            "country": acf.get("country", ""),
                            "type": acf.get("type", ""),
                            "description": content_text[:300] if content_text else "",
                            "slug": item.get("slug", ""),
                        })
                else:
                    logger.warning("CSIS defsys returned HTTP %s", resp.status_code)
            except Exception as exc:
                logger.warning("CSIS defsys fetch failed: %s", exc)

        result = {
            "missiles": missiles,
            "defense_systems": defense_systems,
            "source": "CSIS Missile Threat (missilethreat.csis.org)",
            "total_missiles": len(missiles),
            "total_defense_systems": len(defense_systems),
        }
        _cache_set(self._cache, "csis_missiles", result)
        return result
