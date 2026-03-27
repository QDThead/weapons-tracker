"""OSINT Feed Connectors — 10 lightweight data sources.

Provides:
  - FREDCommodityClient      — FRED commodity prices (no API key)
  - CISAKevClient            — CISA Known Exploited Vulnerabilities
  - GDACSDisasterClient      — GDACS active disaster alerts
  - CelestrakSatelliteClient — Celestrak military satellite TLEs
  - CSISMissileClient        — CSIS Missile Threat database
  - UNSanctionsClient        — UN Security Council Consolidated Sanctions List
  - USGSEarthquakeClient     — USGS significant earthquakes (M5+, last 30 days)
  - MITREAttackClient        — MITRE ATT&CK threat groups (APT actors)
  - IMFEconomicClient        — IMF World Economic Outlook GDP growth projections
  - NASAEONETClient          — NASA EONET active natural events
"""
from __future__ import annotations

import csv
import io
import logging
import re
import time
import xml.etree.ElementTree as ET
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


# ---------------------------------------------------------------------------
# 6. UN Security Council Consolidated Sanctions List
# ---------------------------------------------------------------------------

UN_SANCTIONS_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"

# XML namespace used by the UN consolidated list
_UN_NS = {"un": "https://scsanctions.un.org/"}


class UNSanctionsClient:
    """Fetches the UN Security Council Consolidated Sanctions List (XML)."""

    _cache: dict = {}

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_un_sanctions(self) -> list[dict]:
        """Return defence-relevant entries from the UN Consolidated Sanctions List.

        Returns
        -------
        list of {name, type, un_list, nationality, date_listed, reference_number}
        Limited to 200 most recently listed entries.
        """
        cached = _cache_get(self._cache, "un_sanctions")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                resp = await client.get(UN_SANCTIONS_URL)
                if resp.status_code != 200:
                    logger.warning("UN Sanctions returned HTTP %s", resp.status_code)
                    return []

                root = ET.fromstring(resp.content)

            results: list[dict] = []

            # The consolidated list uses a flat namespace; try with and without NS
            # Try both individuals and entities sections
            def _find_entries(tag_path: str, entry_type: str) -> None:
                # Try namespaced first
                for section in root.iter():
                    # Match on local tag name to handle any namespace variant
                    local = section.tag.split("}")[-1] if "}" in section.tag else section.tag
                    if local not in ("INDIVIDUALS", "ENTITIES"):
                        continue
                    for child in section:
                        child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if child_local not in ("INDIVIDUAL", "ENTITY"):
                            continue

                        def _text(tag: str) -> str:
                            el = child.find(tag)
                            if el is None:
                                # Try local-name search
                                for sub in child:
                                    sub_local = sub.tag.split("}")[-1] if "}" in sub.tag else sub.tag
                                    if sub_local == tag:
                                        return (sub.text or "").strip()
                            return (el.text or "").strip() if el is not None else ""

                        # Name: try FIRST_NAME + SECOND_NAME or NAME_ORIGINAL_SCRIPT or WHOLE_NAME
                        first = _text("FIRST_NAME")
                        second = _text("SECOND_NAME")
                        third = _text("THIRD_NAME")
                        name_parts = " ".join(p for p in [first, second, third] if p)
                        if not name_parts:
                            name_parts = _text("WHOLE_NAME") or _text("NAME_ORIGINAL_SCRIPT") or "Unknown"

                        # Aliases
                        aliases: list[str] = []
                        for alias_el in child:
                            a_local = alias_el.tag.split("}")[-1] if "}" in alias_el.tag else alias_el.tag
                            if a_local in ("ALIAS", "ALIASES"):
                                for a_child in alias_el:
                                    a_text = (a_child.text or "").strip()
                                    if a_text:
                                        aliases.append(a_text)
                                if alias_el.text and alias_el.text.strip():
                                    aliases.append(alias_el.text.strip())

                        results.append({
                            "name": name_parts,
                            "type": entry_type,
                            "un_list": _text("UN_LIST_TYPE") or _text("LISTED_ON"),
                            "nationality": _text("NATIONALITY") or _text("NATIONALITY_OF_BIRTH"),
                            "date_listed": _text("LISTED_ON") or _text("DATE_OF_LISTING"),
                            "reference_number": _text("REFERENCE_NUMBER") or _text("DATAID"),
                            "aliases": aliases[:5],
                        })

            _find_entries("INDIVIDUAL", "individual")
            _find_entries("ENTITY", "entity")

            # Sort by date_listed descending (most recent first), limit 200
            def _date_key(entry: dict) -> str:
                return entry.get("date_listed") or ""

            results.sort(key=_date_key, reverse=True)
            results = results[:200]

            _cache_set(self._cache, "un_sanctions", results)
            return results

        except Exception as exc:
            logger.warning("UN Sanctions fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 7. USGS Earthquake Feed
# ---------------------------------------------------------------------------

USGS_EARTHQUAKE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


class USGSEarthquakeClient:
    """Fetches significant earthquakes (M5+) from USGS over the past 30 days."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_recent_earthquakes(self) -> list[dict]:
        """Return significant earthquakes from the last 30 days.

        Returns
        -------
        list of {magnitude, place, latitude, longitude, time, depth_km,
        tsunami_warning}
        """
        cached = _cache_get(self._cache, "usgs_earthquakes")
        if cached is not None:
            return cached

        try:
            thirty_days_ago = (
                datetime.now(timezone.utc) - timedelta(days=30)
            ).strftime("%Y-%m-%d")

            params = {
                "format": "geojson",
                "starttime": thirty_days_ago,
                "minmagnitude": "5",
                "orderby": "time",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(USGS_EARTHQUAKE_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("USGS Earthquake returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()
                features = data.get("features", [])

                results: list[dict] = []
                for feat in features:
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates", [None, None, None])

                    # Convert epoch ms to ISO string
                    epoch_ms = props.get("time")
                    iso_time = ""
                    if epoch_ms:
                        try:
                            iso_time = datetime.fromtimestamp(
                                epoch_ms / 1000.0, tz=timezone.utc
                            ).isoformat()
                        except Exception:
                            iso_time = str(epoch_ms)

                    results.append({
                        "magnitude": props.get("mag"),
                        "place": props.get("place", ""),
                        "latitude": coords[1] if len(coords) > 1 else None,
                        "longitude": coords[0] if coords else None,
                        "time": iso_time,
                        "depth_km": round(coords[2], 1) if len(coords) > 2 and coords[2] is not None else None,
                        "tsunami_warning": bool(props.get("tsunami")),
                        "alert": props.get("alert"),
                        "url": props.get("url", ""),
                    })

                _cache_set(self._cache, "usgs_earthquakes", results)
                return results

        except Exception as exc:
            logger.warning("USGS Earthquake fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 8. MITRE ATT&CK Threat Groups
# ---------------------------------------------------------------------------

MITRE_ATTACK_URL = (
    "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
)

# Countries frequently attributed to APT groups — used for simple heuristic detection
_ATTRIBUTION_KEYWORDS: dict[str, str] = {
    "china": "China",
    "chinese": "China",
    "prc": "China",
    "russia": "Russia",
    "russian": "Russia",
    "iran": "Iran",
    "iranian": "Iran",
    "north korea": "North Korea",
    "dprk": "North Korea",
    "lazarus": "North Korea",
    "korea": "North Korea",
    "vietnam": "Vietnam",
    "pakistan": "Pakistan",
    "india": "India",
    "israel": "Israel",
    "turkey": "Turkey",
    "ukraine": "Ukraine",
    "saudi": "Saudi Arabia",
}


def _infer_attribution(description: str) -> str | None:
    """Best-effort country attribution from description text."""
    lower = description.lower()
    for keyword, country in _ATTRIBUTION_KEYWORDS.items():
        if keyword in lower:
            return country
    return None


class MITREAttackClient:
    """Fetches MITRE ATT&CK threat groups (intrusion sets) from the CTI STIX bundle."""

    _cache: dict = {}

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_threat_groups(self) -> list[dict]:
        """Return up to 50 APT / intrusion-set entries from MITRE ATT&CK.

        Returns
        -------
        list of {name, aliases, description, first_seen, last_seen,
        attributed_country}
        """
        cached = _cache_get(self._cache, "mitre_attack")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(MITRE_ATTACK_URL)
                if resp.status_code != 200:
                    logger.warning("MITRE ATT&CK returned HTTP %s", resp.status_code)
                    return []

                bundle = resp.json()

            objects = bundle.get("objects", [])
            results: list[dict] = []

            for obj in objects:
                if obj.get("type") != "intrusion-set":
                    continue
                if obj.get("revoked") or obj.get("x_mitre_deprecated"):
                    continue

                name = obj.get("name", "")
                description = obj.get("description", "")
                aliases = obj.get("aliases", [])
                # Remove the group's own name from aliases list
                aliases = [a for a in aliases if a != name]

                results.append({
                    "name": name,
                    "aliases": aliases[:8],
                    "description": description[:200],
                    "first_seen": obj.get("first_seen", ""),
                    "last_seen": obj.get("last_seen", ""),
                    "attributed_country": _infer_attribution(description),
                    "stix_id": obj.get("id", ""),
                })

            # Sort: attributed countries first (most relevant for defence intel), then alphabetical
            results.sort(key=lambda x: (x["attributed_country"] is None, x["name"]))
            results = results[:50]

            _cache_set(self._cache, "mitre_attack", results)
            return results

        except Exception as exc:
            logger.warning("MITRE ATT&CK fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 9. IMF World Economic Outlook (GDP growth projections)
# ---------------------------------------------------------------------------

IMF_WEO_URL = "https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH"

# 30 key countries relevant to defence supply chain (IMF ISO2 codes)
_IMF_DEFENCE_COUNTRIES: dict[str, str] = {
    "USA": "United States",
    "CAN": "Canada",
    "GBR": "United Kingdom",
    "DEU": "Germany",
    "FRA": "France",
    "RUS": "Russia",
    "CHN": "China",
    "IND": "India",
    "JPN": "Japan",
    "KOR": "South Korea",
    "AUS": "Australia",
    "NOR": "Norway",
    "SWE": "Sweden",
    "FIN": "Finland",
    "POL": "Poland",
    "TUR": "Türkiye",
    "ISR": "Israel",
    "IRN": "Iran",
    "SAU": "Saudi Arabia",
    "ARE": "United Arab Emirates",
    "PAK": "Pakistan",
    "PRK": "North Korea",
    "UKR": "Ukraine",
    "BRA": "Brazil",
    "ZAF": "South Africa",
    "NGA": "Nigeria",
    "MEX": "Mexico",
    "IDN": "Indonesia",
    "MYS": "Malaysia",
    "SGP": "Singapore",
}


class IMFEconomicClient:
    """Fetches IMF World Economic Outlook GDP growth projections."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_gdp_forecasts(self) -> dict:
        """Return GDP growth projections for 30 defence-relevant countries.

        Returns
        -------
        dict {countries: {ISO3: {name, "2024": value, "2025": value, "2026": value}}}
        """
        cached = _cache_get(self._cache, "imf_weo")
        if cached is not None:
            return cached

        try:
            params = {"periods": "2024,2025,2026"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(IMF_WEO_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("IMF WEO returned HTTP %s", resp.status_code)
                    return {"countries": {}}

                data = resp.json()

            # Response structure: {"values": {"NGDP_RPCH": {ISO3: {"2024": val, ...}}}}
            values = data.get("values", {})
            series = values.get("NGDP_RPCH", {})

            countries: dict[str, dict] = {}
            for iso3, periods in series.items():
                if iso3 not in _IMF_DEFENCE_COUNTRIES:
                    continue
                entry: dict = {"name": _IMF_DEFENCE_COUNTRIES[iso3]}
                for year in ("2024", "2025", "2026"):
                    val = periods.get(year)
                    if val is not None:
                        try:
                            entry[year] = round(float(val), 2)
                        except (ValueError, TypeError):
                            entry[year] = None
                    else:
                        entry[year] = None
                countries[iso3] = entry

            result = {"countries": countries, "indicator": "NGDP_RPCH", "source": "IMF World Economic Outlook"}
            _cache_set(self._cache, "imf_weo", result)
            return result

        except Exception as exc:
            logger.warning("IMF WEO fetch failed: %s", exc)
            return {"countries": {}}


# ---------------------------------------------------------------------------
# 10. NASA EONET Active Natural Events
# ---------------------------------------------------------------------------

NASA_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"


class NASAEONETClient:
    """Fetches active natural events from NASA Earth Observatory Natural Event Tracker."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_active_events(self) -> list[dict]:
        """Return active open natural events from NASA EONET.

        Returns
        -------
        list of {title, category, date, latitude, longitude, source}
        """
        cached = _cache_get(self._cache, "nasa_eonet")
        if cached is not None:
            return cached

        try:
            params = {"status": "open", "limit": "20"}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(NASA_EONET_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("NASA EONET returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            events = data.get("events", [])
            results: list[dict] = []

            for event in events:
                # Extract category
                categories = event.get("categories", [])
                category = categories[0].get("title", "") if categories else ""

                # Extract most recent geometry point
                geometries = event.get("geometry", [])
                lat = lon = None
                event_date = ""
                if geometries:
                    # Use most recent (last) geometry entry
                    latest_geo = geometries[-1]
                    coords = latest_geo.get("coordinates", [])
                    if coords and len(coords) >= 2:
                        # Point: [lon, lat]; Polygon: [[lon, lat], ...]
                        if isinstance(coords[0], list):
                            lon, lat = coords[0][0], coords[0][1]
                        else:
                            lon, lat = coords[0], coords[1]
                    event_date = latest_geo.get("date", "")

                # Extract source
                sources = event.get("sources", [])
                source_url = sources[0].get("url", "") if sources else ""

                results.append({
                    "title": event.get("title", ""),
                    "category": category,
                    "date": event_date,
                    "latitude": lat,
                    "longitude": lon,
                    "source": source_url,
                    "eonet_id": event.get("id", ""),
                    "link": event.get("link", ""),
                })

            _cache_set(self._cache, "nasa_eonet", results)
            return results

        except Exception as exc:
            logger.warning("NASA EONET fetch failed: %s", exc)
            return []
