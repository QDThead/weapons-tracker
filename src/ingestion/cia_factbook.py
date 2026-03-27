"""CIA World Factbook military data connector.

Downloads country JSON files from the archived factbook.json GitHub repository
and extracts military & security data for key nations.

Repository: https://github.com/factbook/factbook.json
Base URL: https://raw.githubusercontent.com/factbook/factbook.json/master/

The repo uses GEC (formerly FIPS) two-letter country codes organized in regional
directories (e.g., europe/uk.json, north-america/ca.json).

Data extracted:
  - Military branches / force composition
  - Military personnel strength
  - Military expenditure as % of GDP (latest 5 years)
  - Military note (strategic context)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

FACTBOOK_BASE_URL = (
    "https://raw.githubusercontent.com/factbook/factbook.json/master"
)

# Cache TTL: 24 hours (factbook data is updated weekly, not hourly)
_CACHE_TTL = 86400.0

# Default 20 key nations: (region, fips_code, display_name, iso3)
DEFAULT_COUNTRIES: list[tuple[str, str, str, str]] = [
    ("north-america",        "ca",  "Canada",       "CAN"),
    ("north-america",        "us",  "United States", "USA"),
    ("europe",               "uk",  "United Kingdom","GBR"),
    ("central-asia",         "rs",  "Russia",        "RUS"),
    ("east-n-southeast-asia","ch",  "China",         "CHN"),
    ("europe",               "gm",  "Germany",       "DEU"),
    ("europe",               "fr",  "France",        "FRA"),
    ("south-asia",           "in",  "India",         "IND"),
    ("middle-east",          "tu",  "Turkey",        "TUR"),
    ("australia-oceania",    "as",  "Australia",     "AUS"),
    ("east-n-southeast-asia","ja",  "Japan",         "JPN"),
    ("east-n-southeast-asia","ks",  "South Korea",   "KOR"),
    ("middle-east",          "is",  "Israel",        "ISR"),
    ("middle-east",          "ir",  "Iran",          "IRN"),
    ("middle-east",          "sa",  "Saudi Arabia",  "SAU"),
    ("europe",               "no",  "Norway",        "NOR"),
    ("europe",               "sw",  "Sweden",        "SWE"),
    ("europe",               "fi",  "Finland",       "FIN"),
    ("europe",               "pl",  "Poland",        "POL"),
    ("europe",               "up",  "Ukraine",       "UKR"),
]


@dataclass
class FactbookMilitaryRecord:
    """Military data extracted from CIA World Factbook for one country."""

    country_name: str
    fips_code: str
    country_iso3: str | None
    military_branches: str          # Force composition text
    military_personnel: int | None  # Active duty strength (parsed from text)
    military_expenditure_pct_gdp: float | None  # Most recent year % of GDP
    military_expenditure_history: dict[int, float] = field(default_factory=dict)  # year -> % GDP
    military_equipment: str = ""    # Inventory & acquisitions text
    military_deployments: str = ""  # Current deployments text
    military_note: str = ""         # Strategic context / notes


def _extract_text(obj: dict, *keys: str) -> str:
    """Safely extract .text from a nested dict using the given key sequence."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key, {})
        else:
            return ""
    if isinstance(obj, dict):
        return obj.get("text", "")
    return str(obj) if obj else ""


def _parse_personnel(text: str) -> int | None:
    """Extract an integer personnel count from freeform text.

    Examples:
      "approximately 75,000 active-duty military personnel" -> 75000
      "about 960,000 (900,000 Army; 40,000 Navy; 20,000 Air Force)" -> 960000
    """
    # Look for patterns like "75,000" or "75000" possibly preceded by "approximately"
    pattern = r"(?:approximately|about|around|roughly)?\s*([\d,]+)\s*(?:active|personnel|troops|military|armed)"
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            pass
    # Fallback: first large number with commas
    m2 = re.search(r"\b(\d{1,3}(?:,\d{3})+)\b", text)
    if m2:
        try:
            return int(m2.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_expenditure_pct(text: str) -> float | None:
    """Extract % of GDP from text like '1.5% of GDP (2024 est.)'.

    Returns float or None.
    """
    m = re.search(r"([\d.]+)\s*%\s*(?:of\s+GDP)?", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _parse_military_section(
    data: dict,
    fips_code: str,
    country_name: str,
    country_iso3: str | None,
) -> FactbookMilitaryRecord:
    """Parse the 'Military and Security' section of a Factbook JSON blob."""
    mil = data.get("Military and Security", {})

    # Military branches / forces
    branches_obj = mil.get("Military and security forces", {})
    branches_text = branches_obj.get("text", "")
    if not branches_text:
        # Some countries use a slightly different key
        branches_text = _extract_text(mil, "Military branches")

    # Personnel strength
    strength_obj = mil.get("Military and security service personnel strengths", {})
    strength_text = strength_obj.get("text", "")
    personnel = _parse_personnel(strength_text)

    # Expenditure — multi-year nested object
    expenditure_obj = mil.get("Military expenditures", {})
    history: dict[int, float] = {}
    for key, val in expenditure_obj.items():
        # Key format: "Military Expenditures 2024"
        year_m = re.search(r"(\d{4})", key)
        if year_m:
            year = int(year_m.group(1))
            text = val.get("text", "") if isinstance(val, dict) else str(val)
            pct = _parse_expenditure_pct(text)
            if pct is not None:
                history[year] = pct

    latest_pct: float | None = None
    if history:
        latest_year = max(history.keys())
        latest_pct = history[latest_year]

    # Equipment inventories
    equip_obj = mil.get("Military equipment inventories and acquisitions", {})
    equipment_text = equip_obj.get("text", "")

    # Deployments
    deploy_obj = mil.get("Military deployments", {})
    if isinstance(deploy_obj, dict):
        deploy_text = deploy_obj.get("text", "")
    else:
        deploy_text = ""

    # Military note
    note_obj = mil.get("Military - note", {})
    if isinstance(note_obj, dict):
        note_text = note_obj.get("text", "")
    else:
        note_text = ""

    return FactbookMilitaryRecord(
        country_name=country_name,
        fips_code=fips_code,
        country_iso3=country_iso3,
        military_branches=branches_text,
        military_personnel=personnel,
        military_expenditure_pct_gdp=latest_pct,
        military_expenditure_history=history,
        military_equipment=equipment_text,
        military_deployments=deploy_text,
        military_note=note_text,
    )


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL."""

    records: list[FactbookMilitaryRecord]
    fetched_at: float


class CIAFactbookClient:
    """Client for CIA World Factbook military data.

    Fetches per-country JSON files from the factbook.json GitHub mirror and
    extracts Military & Security data. Results are cached for 24 hours.

    Usage::

        client = CIAFactbookClient()
        records = await client.fetch_military_data()
        # or with custom country list:
        records = await client.fetch_military_data(
            countries=[("north-america", "ca"), ("europe", "uk")]
        )
    """

    def __init__(
        self,
        timeout: float = 30.0,
        cache_ttl: float = _CACHE_TTL,
        max_concurrency: int = 5,
    ):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.max_concurrency = max_concurrency
        self._cache: _CacheEntry | None = None

    async def _fetch_country(
        self,
        client: httpx.AsyncClient,
        region: str,
        fips_code: str,
    ) -> dict | None:
        """Fetch a single country JSON file from the factbook repo."""
        url = f"{FACTBOOK_BASE_URL}/{region}/{fips_code}.json"
        try:
            response = await client.get(url)
            if response.status_code == 404:
                logger.warning("Country file not found: %s/%s", region, fips_code)
                return None
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(
                "Failed to fetch factbook data for %s/%s: %s", region, fips_code, e
            )
            return None

    async def fetch_military_data(
        self,
        countries: list[tuple[str, str]] | None = None,
    ) -> list[FactbookMilitaryRecord]:
        """Download and parse CIA Factbook military data for key nations.

        Args:
            countries: List of (region, fips_code) tuples.
                       Defaults to DEFAULT_COUNTRIES (20 key nations).
                       If you also want the display name and ISO3, use
                       fetch_military_data_full() instead.

        Returns:
            List of FactbookMilitaryRecord, one per country successfully fetched.
        """
        # Build lookup for display_name and iso3 from DEFAULT_COUNTRIES
        default_lookup: dict[tuple[str, str], tuple[str, str]] = {
            (r, f): (name, iso3) for r, f, name, iso3 in DEFAULT_COUNTRIES
        }

        # Resolve country list
        if countries is None:
            resolved = [
                (region, fips, name, iso3)
                for region, fips, name, iso3 in DEFAULT_COUNTRIES
            ]
        else:
            resolved = []
            for region, fips in countries:
                name, iso3 = default_lookup.get((region, fips), (fips.upper(), None))
                resolved.append((region, fips, name, iso3))

        # Return cached if fresh
        cache_key = tuple(sorted((r, f) for r, f, _, _ in resolved))
        if (
            self._cache is not None
            and time.monotonic() - self._cache.fetched_at < self.cache_ttl
        ):
            logger.info(
                "Returning %d cached CIA Factbook records", len(self._cache.records)
            )
            return self._cache.records

        # Fetch all countries concurrently (bounded)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        records: list[FactbookMilitaryRecord] = []

        async def fetch_one(
            client: httpx.AsyncClient,
            region: str,
            fips: str,
            name: str,
            iso3: str | None,
        ) -> FactbookMilitaryRecord | None:
            async with semaphore:
                data = await self._fetch_country(client, region, fips)
                if data is None:
                    return None
                try:
                    return _parse_military_section(data, fips, name, iso3)
                except Exception as e:
                    logger.warning(
                        "Failed to parse military section for %s: %s", name, e
                    )
                    return None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            tasks = [
                fetch_one(client, region, fips, name, iso3)
                for region, fips, name, iso3 in resolved
            ]
            results = await asyncio.gather(*tasks, return_exceptions=False)

        for r in results:
            if r is not None:
                records.append(r)

        logger.info(
            "Fetched %d/%d CIA Factbook military records",
            len(records),
            len(resolved),
        )
        self._cache = _CacheEntry(records=records, fetched_at=time.monotonic())
        return records
