"""OSINT Feed Connectors — 22 lightweight data sources.

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
  - PortWatchClient          — IMF PortWatch maritime chokepoint traffic (HDX)
  - OpenSkyClient            — OpenSky Network real-time Arctic aircraft tracking
  - UNHCRClient              — UNHCR refugee/displacement statistics
  - SpaceLaunchClient        — Space launch tracking (The Space Devs)
  - SubmarineCableClient     — TeleGeography submarine cable infrastructure
  - RIPEInternetClient       — RIPE Stat internet infrastructure monitoring
  - USASpendingClient        — US DoD procurement contracts (USASpending.gov)
  - USGSMineralClient        — USGS critical mineral deposit locations
  - WorldBankConflictClient  — World Bank battle-related deaths indicator
  - TreasuryFiscalClient     — US Treasury daily debt and fiscal data
  - OpenAlexResearchClient   — OpenAlex defence research trends
  - RIPEAtlasClient          — RIPE Atlas internet connectivity probe status
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


# ---------------------------------------------------------------------------
# 11. PortWatch — IMF Maritime Chokepoint Traffic (HDX)
# ---------------------------------------------------------------------------

PORTWATCH_CKAN_URL = (
    "https://data.humdata.org/api/3/action/package_show"
    "?id=957b1c2f-a9b9-436c-a576-f7f3ddb9d736"
)

# Hardcoded baseline data for the 10 most strategically important chokepoints.
# These are used as fallback if the live HDX/CSV fetch fails, and are enriched
# with live vessel-count data when available.
_CHOKEPOINT_BASELINE: list[dict] = [
    {
        "name": "Strait of Hormuz",
        "region": "Middle East / Persian Gulf",
        "vessel_count": 21000,
        "status": "active",
        "strategic_importance": "critical",
        "notes": "~20% of global oil trade; Iran interdiction risk",
    },
    {
        "name": "Strait of Malacca",
        "region": "Southeast Asia",
        "vessel_count": 94000,
        "status": "active",
        "strategic_importance": "critical",
        "notes": "Busiest chokepoint by vessel count; China-India-US nexus",
    },
    {
        "name": "Suez Canal",
        "region": "North Africa / Red Sea",
        "vessel_count": 19000,
        "status": "reduced",
        "strategic_importance": "critical",
        "notes": "Houthi attacks have diverted ~40% of traffic to Cape of Good Hope",
    },
    {
        "name": "Bab-el-Mandeb",
        "region": "Horn of Africa / Red Sea",
        "vessel_count": 17000,
        "status": "elevated_risk",
        "strategic_importance": "critical",
        "notes": "Houthi missile/drone attacks on commercial shipping since 2023",
    },
    {
        "name": "Turkish Straits (Bosphorus/Dardanelles)",
        "region": "Black Sea / Mediterranean",
        "vessel_count": 42000,
        "status": "restricted",
        "strategic_importance": "high",
        "notes": "Montreux Convention restricts warships; Russia Black Sea Fleet exit blocked",
    },
    {
        "name": "Strait of Gibraltar",
        "region": "Atlantic / Mediterranean",
        "vessel_count": 45000,
        "status": "active",
        "strategic_importance": "high",
        "notes": "NATO strategic gateway between Atlantic and Mediterranean",
    },
    {
        "name": "Denmark Strait / GIUK Gap",
        "region": "North Atlantic / Arctic",
        "vessel_count": 8500,
        "status": "active",
        "strategic_importance": "high",
        "notes": "Critical NATO anti-submarine warfare chokepoint; Russia submarine transit route",
    },
    {
        "name": "Luzon Strait",
        "region": "Western Pacific / South China Sea",
        "vessel_count": 35000,
        "status": "active",
        "strategic_importance": "high",
        "notes": "Key access route between Pacific and South China Sea; US-China tension zone",
    },
    {
        "name": "Panama Canal",
        "region": "Central America",
        "vessel_count": 14000,
        "status": "reduced",
        "strategic_importance": "high",
        "notes": "Drought-reduced capacity 2023-2024; US strategic interest renewed 2025",
    },
    {
        "name": "Cape of Good Hope",
        "region": "Southern Africa",
        "vessel_count": 32000,
        "status": "elevated",
        "strategic_importance": "medium",
        "notes": "Traffic surge due to Red Sea/Suez diversions since late 2023",
    },
]


class PortWatchClient:
    """Fetches maritime chokepoint traffic data from IMF PortWatch via HDX CKAN API.

    Falls back to hardcoded baseline data for the 10 most strategic chokepoints
    if the live CSV resource is unavailable.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_chokepoint_traffic(self) -> list[dict]:
        """Return chokepoint traffic data for the 10 most strategic maritime chokepoints.

        Returns
        -------
        list of {name, region, vessel_count, status, strategic_importance, notes}
        """
        cached = _cache_get(self._cache, "portwatch_chokepoints")
        if cached is not None:
            return cached

        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Try to get the CKAN package metadata to find the CSV resource URL
                resp = await client.get(PORTWATCH_CKAN_URL)
                if resp.status_code == 200:
                    pkg = resp.json()
                    resources = pkg.get("result", {}).get("resources", [])

                    # Find a CSV resource that looks like chokepoint data
                    csv_url: str | None = None
                    for res in resources:
                        fmt = (res.get("format") or "").lower()
                        name = (res.get("name") or "").lower()
                        if fmt == "csv" and ("chokepoint" in name or "traffic" in name or "vessel" in name):
                            csv_url = res.get("url")
                            break
                    # Fallback: first CSV resource
                    if not csv_url:
                        for res in resources:
                            if (res.get("format") or "").lower() == "csv":
                                csv_url = res.get("url")
                                break

                    if csv_url:
                        csv_resp = await client.get(csv_url)
                        if csv_resp.status_code == 200:
                            reader = csv.DictReader(io.StringIO(csv_resp.text))
                            for row in reader:
                                # Best-effort field extraction; columns vary by dataset version
                                name_val = (
                                    row.get("chokepoint") or row.get("name") or
                                    row.get("port_name") or row.get("location", "")
                                ).strip()
                                if not name_val:
                                    continue
                                vessel_raw = (
                                    row.get("vessel_count") or row.get("vessels") or
                                    row.get("total_vessels") or row.get("count", "")
                                ).strip()
                                try:
                                    vessel_count = int(float(vessel_raw))
                                except (ValueError, TypeError):
                                    vessel_count = 0
                                results.append({
                                    "name": name_val,
                                    "region": row.get("region", ""),
                                    "vessel_count": vessel_count,
                                    "status": "active",
                                    "strategic_importance": "unknown",
                                    "notes": "",
                                })

        except Exception as exc:
            logger.warning("PortWatch live fetch failed: %s", exc)

        # Fall back to baseline data if live fetch returned nothing useful
        if not results:
            logger.info("PortWatch: using hardcoded baseline chokepoint data")
            results = list(_CHOKEPOINT_BASELINE)

        _cache_set(self._cache, "portwatch_chokepoints", results)
        return results


# ---------------------------------------------------------------------------
# 12. OpenSky Network — Real-time Arctic Aircraft Tracking
# ---------------------------------------------------------------------------

OPENSKY_ARCTIC_URL = "https://opensky-network.org/api/states/all"

# State vector positional index mapping (OpenSky API v1)
_OS_ICAO24 = 0
_OS_CALLSIGN = 1
_OS_ORIGIN_COUNTRY = 2
_OS_TIME_POSITION = 3
_OS_LAST_CONTACT = 4
_OS_LONGITUDE = 5
_OS_LATITUDE = 6
_OS_BARO_ALTITUDE = 7
_OS_ON_GROUND = 8
_OS_VELOCITY = 9
_OS_TRUE_TRACK = 10
_OS_VERTICAL_RATE = 11
_OS_SENSORS = 12
_OS_GEO_ALTITUDE = 13
_OS_SQUAWK = 14
_OS_SPI = 15
_OS_POSITION_SOURCE = 16


class OpenSkyClient:
    """Fetches real-time aircraft positions over the Arctic (lat > 55N) from OpenSky Network.

    Complements the existing adsb.lol flight tracker with an independent data source.
    No authentication required for anonymous access (rate-limited to ~10 req/min).
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_arctic_aircraft(self) -> list[dict]:
        """Return aircraft currently tracked over the Arctic region (lat 55N–90N).

        Returns
        -------
        list of {icao24, callsign, origin_country, latitude, longitude,
        altitude, velocity}
        """
        cached = _cache_get(self._cache, "opensky_arctic")
        if cached is not None:
            return cached

        try:
            params = {
                "lamin": "55",
                "lamax": "90",
                "lomin": "-180",
                "lomax": "180",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(OPENSKY_ARCTIC_URL, params=params)
                if resp.status_code == 429:
                    logger.warning("OpenSky rate-limited (429); returning empty list")
                    return []
                if resp.status_code != 200:
                    logger.warning("OpenSky returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            states = data.get("states") or []
            results: list[dict] = []

            for sv in states:
                if not sv or len(sv) < 17:
                    continue
                lat = sv[_OS_LATITUDE]
                lon = sv[_OS_LONGITUDE]
                if lat is None or lon is None:
                    continue

                altitude_m = sv[_OS_BARO_ALTITUDE]
                velocity_ms = sv[_OS_VELOCITY]

                results.append({
                    "icao24": sv[_OS_ICAO24] or "",
                    "callsign": (sv[_OS_CALLSIGN] or "").strip(),
                    "origin_country": sv[_OS_ORIGIN_COUNTRY] or "",
                    "latitude": round(lat, 4) if lat is not None else None,
                    "longitude": round(lon, 4) if lon is not None else None,
                    "altitude": round(altitude_m, 0) if altitude_m is not None else None,
                    "velocity": round(velocity_ms * 1.944, 1) if velocity_ms is not None else None,  # m/s -> knots
                    "on_ground": bool(sv[_OS_ON_GROUND]),
                    "squawk": sv[_OS_SQUAWK] or "",
                })

            _cache_set(self._cache, "opensky_arctic", results)
            return results

        except Exception as exc:
            logger.warning("OpenSky fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 13. UNHCR — Refugee and Displacement Statistics
# ---------------------------------------------------------------------------

UNHCR_POPULATION_URL = "https://api.unhcr.org/population/v1/population/"


class UNHCRClient:
    """Fetches UNHCR refugee and displacement statistics.

    Displacement data is a key indicator of conflict intensity and forced
    migration driven by armed conflict — directly relevant to the DND
    geopolitical threat assessment mission.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_displacement_data(self) -> list[dict]:
        """Return top displacement situations ordered by total refugee count.

        Returns
        -------
        list of {country_of_origin, country_of_asylum, year, refugees,
        idps, asylum_seekers}
        """
        cached = _cache_get(self._cache, "unhcr_displacement")
        if cached is not None:
            return cached

        try:
            params = {
                "year_from": "2022",
                "year_to": "2023",
                "limit": "50",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(UNHCR_POPULATION_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("UNHCR API returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            items = data.get("items", [])
            results: list[dict] = []

            for item in items:
                refugees = item.get("refugees") or 0
                idps = item.get("idps") or 0
                asylum_seekers = item.get("asylum_seekers") or 0
                try:
                    refugees = int(refugees)
                    idps = int(idps)
                    asylum_seekers = int(asylum_seekers)
                except (TypeError, ValueError):
                    refugees = idps = asylum_seekers = 0

                results.append({
                    "country_of_origin": item.get("coo_name") or item.get("coo") or "",
                    "country_of_asylum": item.get("coa_name") or item.get("coa") or "",
                    "year": item.get("year"),
                    "refugees": refugees,
                    "idps": idps,
                    "asylum_seekers": asylum_seekers,
                    "total_displaced": refugees + idps + asylum_seekers,
                })

            # Sort by total displaced, highest first
            results.sort(key=lambda x: x["total_displaced"], reverse=True)

            _cache_set(self._cache, "unhcr_displacement", results)
            return results

        except Exception as exc:
            logger.warning("UNHCR fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 14. Space Launch Client — The Space Devs
# ---------------------------------------------------------------------------

SPACE_LAUNCH_URL = "https://ll.thespacedevs.com/2.3.0/launches/"


class SpaceLaunchClient:
    """Fetches recent space launch data from The Space Devs Launch Library 2.

    Military and dual-use space launches are an important indicator of
    strategic capability development — particularly for ISR, ASAT, and
    hypersonic delivery systems.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_recent_launches(self) -> list[dict]:
        """Return recent space launches with country, rocket, and mission type.

        Returns
        -------
        list of {name, launch_date, country, rocket, mission_type, status, pad_location}
        """
        cached = _cache_get(self._cache, "space_launches")
        if cached is not None:
            return cached

        try:
            params = {
                "format": "json",
                "limit": "20",
                "ordering": "-net",
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(SPACE_LAUNCH_URL, params=params)
                if resp.status_code == 429:
                    logger.warning("Space Devs API rate-limited (429)")
                    return []
                if resp.status_code != 200:
                    logger.warning("Space Devs API returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            launches = data.get("results", [])
            results: list[dict] = []

            for launch in launches:
                rocket_info = launch.get("rocket") or {}
                config = rocket_info.get("configuration") or {}

                pad_info = launch.get("pad") or {}
                location_info = pad_info.get("location") or {}

                mission_info = launch.get("mission") or {}

                status_info = launch.get("status") or {}

                # Extract launch country from pad location or launch service provider
                lsp = launch.get("launch_service_provider") or {}
                country_code = (
                    location_info.get("country_code") or
                    lsp.get("country_code") or
                    ""
                )

                results.append({
                    "name": launch.get("name", ""),
                    "launch_date": launch.get("net", ""),
                    "country": country_code,
                    "rocket": config.get("full_name") or config.get("name") or "",
                    "mission_type": mission_info.get("type") or mission_info.get("orbit", {}).get("name") if mission_info else "",
                    "status": status_info.get("name") or status_info.get("abbrev") or "",
                    "pad_location": location_info.get("name") or pad_info.get("name") or "",
                    "launch_service_provider": lsp.get("name") or "",
                })

            _cache_set(self._cache, "space_launches", results)
            return results

        except Exception as exc:
            logger.warning("Space Devs fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 15. SubmarineCableClient — TeleGeography Submarine Cable Map
# ---------------------------------------------------------------------------

SUBMARINE_CABLE_ALL_URL = "https://www.submarinecablemap.com/api/v3/cable/all.json"
SUBMARINE_CABLE_DETAIL_URL = "https://www.submarinecablemap.com/api/v3/cable/{slug}.json"

# Strategically important cable slugs (defence intelligence focus: Russia neighbours,
# Arctic, NATO transatlantic, Indo-Pacific, critical chokepoints)
_STRATEGIC_CABLE_SLUGS: list[str] = [
    "2africa",
    "africa-coast-to-europe-ace",
    "asc",                               # America-Africa
    "bal-lt",                            # Baltic
    "c-lion1",                           # Mediterranean-Europe
    "dunant",                            # Google transatlantic
    "far-north-fiber",                   # Arctic
    "flag-falcon",                       # Middle East-Europe
    "havfrue-anoraat",                   # Atlantic (Google/Facebook)
    "india-europe-xpress-iex",           # India-Europe
    "marea",                             # Microsoft/Facebook transatlantic
    "peace",                             # Pakistan-East Africa-Europe
    "polar-connect",                     # Arctic Canada-Norway
    "ses",                               # South East Asia
    "skkу",                              # Korea-Japan
    "smatv",                             # South Atlantic
    "southern-cross-cable-network-sccn", # Pacific
    "tasman-global-access-tga",          # Aus-NZ
    "transatlantic-express-tax",         # Transatlantic
    "transarctic-cable-system-tacs",     # Arctic
]


class SubmarineCableClient:
    """Fetches submarine cable infrastructure data from TeleGeography.

    The TeleGeography API returns only id+name in the all.json index.
    This client fetches per-cable detail for ~20 strategically important
    cable systems. Submarine cables carry ~95% of international internet
    traffic; sabotage events (e.g., Baltic Sea 2024) are a key grey-zone
    warfare vector.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_submarine_cables(self) -> list[dict]:
        """Return cable details for strategically important submarine cable systems.

        Returns
        -------
        list of {name, length_km, ready_for_service, owners, landing_points_count}
        """
        cached = _cache_get(self._cache, "submarine_cables")
        if cached is not None:
            return cached

        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # First get the full index to validate slugs / discover new cables
                index_resp = await client.get(SUBMARINE_CABLE_ALL_URL)
                known_slugs: set[str] = set()
                if index_resp.status_code == 200:
                    all_cables = index_resp.json()
                    known_slugs = {c.get("id", "") for c in all_cables if c.get("id")}

                # Fetch detail for each strategic cable
                for slug in _STRATEGIC_CABLE_SLUGS:
                    # Skip slugs that aren't in the current index (cable may have been renamed)
                    if known_slugs and slug not in known_slugs:
                        logger.debug("Cable slug %r not in TeleGeography index; skipping", slug)
                        continue
                    try:
                        detail_url = SUBMARINE_CABLE_DETAIL_URL.format(slug=slug)
                        resp = await client.get(detail_url)
                        if resp.status_code != 200:
                            logger.debug("Cable %r returned HTTP %s", slug, resp.status_code)
                            continue
                        cable = resp.json()
                    except Exception as exc:
                        logger.debug("Cable detail fetch failed for %r: %s", slug, exc)
                        continue

                    # Parse length: API returns strings like "17,000 km"
                    length_raw = cable.get("length") or ""
                    length_km: int | None = None
                    if length_raw:
                        digits = re.sub(r"[^\d]", "", str(length_raw))
                        if digits:
                            try:
                                length_km = int(digits)
                            except ValueError:
                                length_km = None

                    # Owners: may be list of dicts or strings
                    owners_raw = cable.get("owners") or []
                    if isinstance(owners_raw, list):
                        owners = [
                            (o.get("name") or str(o)) if isinstance(o, dict) else str(o)
                            for o in owners_raw
                        ]
                    else:
                        owners = []

                    landing_pts = cable.get("landing_points") or []
                    landing_count = len(landing_pts) if isinstance(landing_pts, list) else 0

                    results.append({
                        "name": cable.get("name") or slug,
                        "slug": slug,
                        "length_km": length_km,
                        "ready_for_service": cable.get("rfs") or cable.get("ready_for_service") or "",
                        "owners": owners[:10],
                        "landing_points_count": landing_count,
                        "is_planned": cable.get("is_planned") or False,
                    })

        except Exception as exc:
            logger.warning("Submarine Cable Map fetch failed: %s", exc)

        _cache_set(self._cache, "submarine_cables", results)
        return results


# ---------------------------------------------------------------------------
# 16. RIPEInternetClient — RIPE Stat Internet Infrastructure
# ---------------------------------------------------------------------------

RIPE_STAT_URL = "https://stat.ripe.net/data/country-resource-stats/data.json"

# Key countries for internet infrastructure monitoring
_RIPE_COUNTRIES: list[str] = ["RU", "CN", "US", "IR", "KP", "UA", "CA", "GB"]


class RIPEInternetClient:
    """Fetches internet infrastructure data from RIPE Stat.

    Internet infrastructure metrics (BGP routing, ASN counts, IP prefix
    allocation) are indicators of a country's cyber domain resilience and
    potential for internet shutdown events relevant to conflict escalation.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_internet_infrastructure(self) -> dict:
        """Return internet infrastructure statistics for key countries.

        Returns
        -------
        dict {countries: {code: {asns_registered, asns_routed, ipv4_prefixes}}}
        """
        cached = _cache_get(self._cache, "ripe_internet")
        if cached is not None:
            return cached

        countries_data: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for country_code in _RIPE_COUNTRIES:
                try:
                    params = {"resource": country_code}
                    resp = await client.get(RIPE_STAT_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning(
                            "RIPE Stat returned HTTP %s for %s", resp.status_code, country_code
                        )
                        continue

                    data = resp.json()
                    # RIPE Stat returns "stats" as a time-series list of entries.
                    # Each entry has: asns_ris (routed), asns_stats (registered),
                    # v4_prefixes_ris (routed prefixes), stats_date.
                    # Use the most recent entry (last in the list).
                    stats_list = (data.get("data") or {}).get("stats") or []
                    if not stats_list:
                        continue

                    latest = stats_list[-1] if isinstance(stats_list, list) else stats_list

                    asns_registered = latest.get("asns_stats") or latest.get("asns_registered") or 0
                    asns_routed = latest.get("asns_ris") or latest.get("asns_routed") or 0
                    ipv4_prefixes = latest.get("v4_prefixes_ris") or latest.get("ipv4_prefixes") or 0
                    stats_date = latest.get("stats_date") or ""

                    countries_data[country_code] = {
                        "asns_registered": asns_registered,
                        "asns_routed": asns_routed,
                        "ipv4_prefixes": ipv4_prefixes,
                        "stats_date": stats_date,
                    }

                except Exception as exc:
                    logger.warning("RIPE Stat fetch failed for %s: %s", country_code, exc)

        result = {
            "countries": countries_data,
            "source": "RIPE Stat (stat.ripe.net)",
            "monitored_countries": _RIPE_COUNTRIES,
        }
        _cache_set(self._cache, "ripe_internet", result)
        return result


# ---------------------------------------------------------------------------
# 17. USASpendingClient — US DoD Procurement Contracts
# ---------------------------------------------------------------------------

USA_SPENDING_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"

_USA_SPENDING_BODY: dict = {
    "filters": {
        "keywords": ["defense", "military", "weapons"],
        "agencies": [
            {
                "type": "awarding",
                "tier": "toptier",
                "name": "Department of Defense",
            }
        ],
        "time_period": [
            {"start_date": "2025-01-01", "end_date": "2026-12-31"}
        ],
    },
    "fields": [
        "Award ID",
        "Recipient Name",
        "Award Amount",
        "Description",
        "Start Date",
        "Award Type",
    ],
    "limit": 20,
    "order": "desc",
    "sort": "Award Amount",
}


class USASpendingClient:
    """Fetches US DoD procurement contracts from USASpending.gov.

    Provides real-time visibility into Department of Defense contract awards,
    including recipient names, amounts, and contract descriptions. Key
    indicator of defence industrial base activity and procurement priorities.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_dod_contracts(self) -> list[dict]:
        """Return recent DoD contract awards ordered by amount (descending).

        Returns
        -------
        list of {award_id, recipient, amount, description, date, type}
        """
        cached = _cache_get(self._cache, "dod_contracts")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    USA_SPENDING_URL,
                    json=_USA_SPENDING_BODY,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    logger.warning("USASpending returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            results_raw = data.get("results", [])
            results: list[dict] = []

            for item in results_raw:
                amount_raw = item.get("Award Amount")
                try:
                    amount = float(amount_raw) if amount_raw is not None else None
                except (TypeError, ValueError):
                    amount = None

                results.append({
                    "award_id": item.get("Award ID") or "",
                    "recipient": item.get("Recipient Name") or "",
                    "amount": amount,
                    "description": (item.get("Description") or "")[:300],
                    "date": item.get("Start Date") or "",
                    "type": item.get("Award Type") or "",
                })

            _cache_set(self._cache, "dod_contracts", results)
            return results

        except Exception as exc:
            logger.warning("USASpending DoD contracts fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 18. USGSMineralClient — Critical Mineral Deposit Locations
# ---------------------------------------------------------------------------

USGS_MRDS_URL = "https://mrdata.usgs.gov/services/mrds"

_MINERAL_QUERIES: list[str] = [
    "Lithium",
    "Cobalt",
    "Titanium",
    "Rare Earth",
    "Tungsten",
]


class USGSMineralClient:
    """Fetches critical mineral deposit locations from USGS Mineral Resources Data System.

    MRDS provides georeferenced data on mineral deposits worldwide.
    Critical minerals are essential inputs for advanced weapons platforms,
    electronics, and propulsion systems — a key supply chain risk indicator.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_mineral_deposits(self) -> dict:
        """Return critical mineral deposit locations for defence-relevant minerals.

        Returns
        -------
        dict {minerals: [{name, deposits: [{location, country, lat, lon, deposit_type}]}]}
        """
        cached = _cache_get(self._cache, "usgs_mineral_deposits")
        if cached is not None:
            return cached

        minerals_result: list[dict] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for mineral in _MINERAL_QUERIES:
                deposits: list[dict] = []
                try:
                    params = {
                        "service": "WFS",
                        "version": "1.1.0",
                        "request": "GetFeature",
                        "typeName": "mrds-high",
                        "maxFeatures": "20",
                        "CQL_FILTER": f"commod_desc LIKE '%{mineral}%'",
                        "outputFormat": "application/json",
                    }
                    resp = await client.get(USGS_MRDS_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning(
                            "USGS MRDS returned HTTP %s for %s", resp.status_code, mineral
                        )
                        minerals_result.append({"name": mineral, "deposits": deposits})
                        continue

                    data = resp.json()
                    features = data.get("features", [])

                    for feat in features:
                        props = feat.get("properties", {}) or {}
                        geom = feat.get("geometry", {}) or {}
                        coords = geom.get("coordinates") or []

                        lat = lon = None
                        if coords and len(coords) >= 2:
                            lon = coords[0]
                            lat = coords[1]

                        deposits.append({
                            "location": props.get("site_name") or props.get("dep_id") or "",
                            "country": props.get("country") or "",
                            "lat": round(lat, 4) if lat is not None else None,
                            "lon": round(lon, 4) if lon is not None else None,
                            "deposit_type": props.get("dep_type") or props.get("commod_desc") or mineral,
                        })

                except Exception as exc:
                    logger.warning("USGS MRDS fetch failed for %s: %s", mineral, exc)

                minerals_result.append({"name": mineral, "deposits": deposits})

        result = {"minerals": minerals_result}
        _cache_set(self._cache, "usgs_mineral_deposits", result)
        return result


# ---------------------------------------------------------------------------
# 19. WorldBankConflictClient — Battle-Related Deaths Indicator
# ---------------------------------------------------------------------------

WORLDBANK_CONFLICT_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/VC.BTL.DETH"
    "?format=json&per_page=100&date=2020:2023"
)


class WorldBankConflictClient:
    """Fetches battle-related deaths indicator from the World Bank.

    VC.BTL.DETH tracks battle-related deaths (including civilians killed
    in war) from the UCDP/PRIO Armed Conflict dataset. A key indicator
    of active conflict intensity by country.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_conflict_deaths(self) -> list[dict]:
        """Return countries with non-null battle-related death counts (2020–2023).

        Returns
        -------
        list of {country, iso3, year, deaths}
        """
        cached = _cache_get(self._cache, "wb_conflict_deaths")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(WORLDBANK_CONFLICT_URL)
                if resp.status_code != 200:
                    logger.warning(
                        "World Bank Conflict API returned HTTP %s", resp.status_code
                    )
                    return []

                payload = resp.json()

            # World Bank JSON wraps data in a 2-element list: [meta, data]
            if not isinstance(payload, list) or len(payload) < 2:
                logger.warning("World Bank Conflict: unexpected response structure")
                return []

            records = payload[1] or []
            results: list[dict] = []

            for rec in records:
                if rec.get("value") is None:
                    continue
                try:
                    deaths = int(float(rec["value"]))
                except (TypeError, ValueError):
                    continue

                country_info = rec.get("country", {})
                results.append({
                    "country": country_info.get("value") or rec.get("countryiso3code") or "",
                    "iso3": rec.get("countryiso3code") or "",
                    "year": rec.get("date") or "",
                    "deaths": deaths,
                })

            # Sort by deaths descending for relevance
            results.sort(key=lambda x: x["deaths"], reverse=True)

            _cache_set(self._cache, "wb_conflict_deaths", results)
            return results

        except Exception as exc:
            logger.warning("World Bank Conflict Deaths fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 20. TreasuryFiscalClient — US Treasury Daily Debt & Fiscal Data
# ---------------------------------------------------------------------------

TREASURY_DEBT_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v2/accounting/od/debt_to_penny"
    "?sort=-record_date&page[size]=10"
)

_TREASURY_FISCAL_TTL = 3600.0  # 1-hour cache (daily updates from Treasury)


class TreasuryFiscalClient:
    """Fetches US Treasury daily debt-to-the-penny and fiscal data.

    The US national debt level and its trajectory are macro indicators
    for defence budget sustainability and dollar-denominated arms financing
    capacity. Treasury updates this data daily on business days.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def _cache_get_fiscal(self, key: str) -> object | None:
        """Override cache get with 1-hour TTL for Treasury data."""
        entry = self._cache.get(key)
        if entry and time.time() - entry[0] < _TREASURY_FISCAL_TTL:
            return entry[1]
        return None

    async def fetch_us_fiscal_data(self) -> dict:
        """Return US total public debt outstanding with 30-day trend.

        Returns
        -------
        dict {total_debt_usd, date, trend_30d}
        """
        cached = self._cache_get_fiscal("treasury_fiscal")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(TREASURY_DEBT_URL)
                if resp.status_code != 200:
                    logger.warning(
                        "Treasury Fiscal API returned HTTP %s", resp.status_code
                    )
                    return {"error": f"HTTP {resp.status_code}"}

                data = resp.json()

            records = data.get("data", [])
            if not records:
                return {"error": "No data returned"}

            def _parse_debt(row: dict) -> float | None:
                for field in ("tot_pub_debt_out_amt", "debt_outstanding_amt", "amt"):
                    val = row.get(field)
                    if val is not None:
                        try:
                            return float(val)
                        except (TypeError, ValueError):
                            pass
                return None

            latest = records[0]
            latest_debt = _parse_debt(latest)
            latest_date = latest.get("record_date") or ""

            # 30-day trend: compare first vs last record in the 10-record window
            trend_30d: float | None = None
            if len(records) >= 2:
                oldest_debt = _parse_debt(records[-1])
                if latest_debt is not None and oldest_debt is not None and oldest_debt > 0:
                    trend_30d = round(latest_debt - oldest_debt, 2)

            result = {
                "total_debt_usd": latest_debt,
                "date": latest_date,
                "trend_30d": trend_30d,
                "source": "US Treasury Fiscal Data API",
                "unit": "USD",
                "recent_records": [
                    {
                        "date": r.get("record_date", ""),
                        "total_debt_usd": _parse_debt(r),
                    }
                    for r in records
                ],
            }

            _cache_set(self._cache, "treasury_fiscal", result)
            return result

        except Exception as exc:
            logger.warning("Treasury Fiscal fetch failed: %s", exc)
            return {"error": str(exc)}


# ---------------------------------------------------------------------------
# 21. OpenAlexResearchClient — Defence Research Trends
# ---------------------------------------------------------------------------

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

_OPENALEX_PARAMS: dict = {
    "search": "defence supply chain military procurement",
    "per-page": "10",
    "sort": "publication_date:desc",
}


class OpenAlexResearchClient:
    """Fetches defence research trends from the OpenAlex academic database.

    OpenAlex is a fully open catalogue of academic research. Tracking
    recent publications on defence supply chains and military procurement
    reveals emerging risk themes ahead of policy and market movements.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_defence_research(self) -> list[dict]:
        """Return recent academic works on defence supply chain and procurement.

        Returns
        -------
        list of {title, authors, publication_date, journal, cited_by_count, topics}
        """
        cached = _cache_get(self._cache, "openalex_research")
        if cached is not None:
            return cached

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    OPENALEX_WORKS_URL,
                    params=_OPENALEX_PARAMS,
                    headers={"User-Agent": "WeaponsTracker/1.0 (mailto:info@example.com)"},
                )
                if resp.status_code != 200:
                    logger.warning("OpenAlex returned HTTP %s", resp.status_code)
                    return []

                data = resp.json()

            works = data.get("results", [])
            results: list[dict] = []

            for work in works:
                # Extract authors (up to 5)
                authorships = work.get("authorships", [])
                authors = [
                    a.get("author", {}).get("display_name", "")
                    for a in authorships[:5]
                    if a.get("author")
                ]

                # Extract journal / source name
                primary_location = work.get("primary_location") or {}
                source = primary_location.get("source") or {}
                journal = source.get("display_name") or ""

                # Extract topics
                topics = [
                    t.get("display_name", "")
                    for t in (work.get("topics") or [])[:5]
                ]

                results.append({
                    "title": work.get("display_name") or work.get("title") or "",
                    "authors": authors,
                    "publication_date": work.get("publication_date") or "",
                    "journal": journal,
                    "cited_by_count": work.get("cited_by_count") or 0,
                    "topics": topics,
                    "doi": work.get("doi") or "",
                    "open_access": (work.get("open_access") or {}).get("is_oa") or False,
                })

            _cache_set(self._cache, "openalex_research", results)
            return results

        except Exception as exc:
            logger.warning("OpenAlex research fetch failed: %s", exc)
            return []


# ---------------------------------------------------------------------------
# 22. RIPEAtlasClient — Internet Connectivity Monitoring via Probe Status
# ---------------------------------------------------------------------------

RIPE_ATLAS_PROBES_URL = "https://atlas.ripe.net/api/v2/probes/"

# Countries to monitor for internet connectivity resilience
_ATLAS_COUNTRIES: list[str] = ["US", "RU", "UA", "CN", "IR", "KP", "CA", "GB", "DE", "IL"]


class RIPEAtlasClient:
    """Fetches internet connectivity probe status from RIPE Atlas by country.

    RIPE Atlas probes are a globally distributed measurement network.
    Active probe counts per country are an indicator of internet
    infrastructure health. Sudden drops in probe count can indicate
    internet shutdowns or major infrastructure disruptions during conflicts.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    @staticmethod
    def _classify_connectivity(count: int) -> str:
        if count > 500:
            return "healthy"
        elif count >= 100:
            return "moderate"
        elif count > 0:
            return "limited"
        return "isolated"

    async def fetch_connectivity_status(self) -> dict:
        """Return active RIPE Atlas probe counts and connectivity status by country.

        Returns
        -------
        dict {countries: {code: {active_probes, status}}}
        """
        cached = _cache_get(self._cache, "ripe_atlas_connectivity")
        if cached is not None:
            return cached

        countries_data: dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for cc in _ATLAS_COUNTRIES:
                try:
                    params = {
                        "country_code": cc,
                        "status": "1",    # 1 = Connected/active
                        "page_size": "1", # We only need the count field
                    }
                    resp = await client.get(RIPE_ATLAS_PROBES_URL, params=params)
                    if resp.status_code != 200:
                        logger.warning(
                            "RIPE Atlas returned HTTP %s for %s", resp.status_code, cc
                        )
                        countries_data[cc] = {"active_probes": 0, "status": "unknown"}
                        continue

                    data = resp.json()
                    active_probes = data.get("count", 0)
                    try:
                        active_probes = int(active_probes)
                    except (TypeError, ValueError):
                        active_probes = 0

                    countries_data[cc] = {
                        "active_probes": active_probes,
                        "status": self._classify_connectivity(active_probes),
                    }

                except Exception as exc:
                    logger.warning("RIPE Atlas fetch failed for %s: %s", cc, exc)
                    countries_data[cc] = {"active_probes": 0, "status": "unknown"}

        result = {
            "countries": countries_data,
            "monitored_countries": _ATLAS_COUNTRIES,
            "classification": {
                "healthy": ">500 active probes",
                "moderate": "100–500 active probes",
                "limited": "<100 active probes",
                "isolated": "0 active probes",
            },
            "source": "RIPE Atlas (atlas.ripe.net)",
        }
        _cache_set(self._cache, "ripe_atlas_connectivity", result)
        return result
