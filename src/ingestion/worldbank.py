"""World Bank Arms Trade Indicators connector.

Fetches arms imports/exports TIV data and military expenditure
via the World Bank Open Data API. No authentication required.

Indicators:
  MS.MIL.MPRT.KD — Arms imports (SIPRI TIV, constant 1990 USD)
  MS.MIL.XPRT.KD — Arms exports (SIPRI TIV, constant 1990 USD)
  MS.MIL.XPND.GD.ZS — Military expenditure (% of GDP)

Reference: https://api.worldbank.org/v2/
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

WB_API_BASE = "https://api.worldbank.org/v2"

INDICATORS = {
    "arms_imports": "MS.MIL.MPRT.KD",
    "arms_exports": "MS.MIL.XPRT.KD",
    "military_expenditure_pct_gdp": "MS.MIL.XPND.GD.ZS",
}


@dataclass
class TradeIndicatorRecord:
    """A single country-year trade indicator record."""
    country_name: str
    country_iso3: str
    year: int
    arms_imports_tiv: float | None
    arms_exports_tiv: float | None
    military_expenditure_pct_gdp: float | None


class WorldBankClient:
    """Client for the World Bank Open Data API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def _fetch_indicator(
        self, indicator: str, country: str = "all", date_range: str = "2000:2025"
    ) -> list[dict]:
        """Fetch a single indicator from the World Bank API.

        Args:
            indicator: World Bank indicator code.
            country: ISO3 country code or "all".
            date_range: Year range (e.g., "2000:2025").

        Returns:
            List of data points as dicts.
        """
        url = f"{WB_API_BASE}/country/{country}/indicator/{indicator}"
        params = {
            "format": "json",
            "date": date_range,
            "per_page": 10000,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Fetching World Bank indicator %s for %s", indicator, country)
            response = await client.get(url, params=params)
            response.raise_for_status()

        data = response.json()
        if len(data) < 2:
            return []

        return [
            entry for entry in data[1]
            if entry.get("value") is not None
        ]

    async def fetch_arms_trade_data(
        self, country: str = "all", start_year: int = 2000, end_year: int = 2025
    ) -> list[TradeIndicatorRecord]:
        """Fetch arms imports, exports, and military expenditure for countries.

        Args:
            country: ISO3 code (e.g., "CAN") or "all" for global data.
            start_year: Start of date range.
            end_year: End of date range.

        Returns:
            List of TradeIndicatorRecord per country per year.
        """
        date_range = f"{start_year}:{end_year}"

        # Fetch all three indicators
        imports_data = await self._fetch_indicator(INDICATORS["arms_imports"], country, date_range)
        exports_data = await self._fetch_indicator(INDICATORS["arms_exports"], country, date_range)
        milexp_data = await self._fetch_indicator(INDICATORS["military_expenditure_pct_gdp"], country, date_range)

        # Index by (country_iso3, year) for merging
        imports_idx = {
            (e["country"]["id"], int(e["date"])): e["value"]
            for e in imports_data
        }
        exports_idx = {
            (e["country"]["id"], int(e["date"])): e["value"]
            for e in exports_data
        }
        milexp_idx = {
            (e["country"]["id"], int(e["date"])): e["value"]
            for e in milexp_data
        }

        # Collect all unique (country, year) pairs
        all_keys = set(imports_idx.keys()) | set(exports_idx.keys()) | set(milexp_idx.keys())

        # Build country name lookup from any of the datasets
        country_names = {}
        for dataset in [imports_data, exports_data, milexp_data]:
            for entry in dataset:
                country_names[entry["country"]["id"]] = entry["country"]["value"]

        records = []
        for iso3, year in sorted(all_keys):
            records.append(TradeIndicatorRecord(
                country_name=country_names.get(iso3, iso3),
                country_iso3=iso3,
                year=year,
                arms_imports_tiv=imports_idx.get((iso3, year)),
                arms_exports_tiv=exports_idx.get((iso3, year)),
                military_expenditure_pct_gdp=milexp_idx.get((iso3, year)),
            ))

        logger.info("Fetched %d trade indicator records from World Bank", len(records))
        return records

    async def fetch_top_importers(self, year: int = 2024, limit: int = 20) -> list[TradeIndicatorRecord]:
        """Fetch top arms importing countries for a given year."""
        records = await self.fetch_arms_trade_data(country="all", start_year=year, end_year=year)
        records = [r for r in records if r.arms_imports_tiv is not None and r.arms_imports_tiv > 0]
        records.sort(key=lambda r: r.arms_imports_tiv or 0, reverse=True)
        return records[:limit]

    async def fetch_top_exporters(self, year: int = 2024, limit: int = 20) -> list[TradeIndicatorRecord]:
        """Fetch top arms exporting countries for a given year."""
        records = await self.fetch_arms_trade_data(country="all", start_year=year, end_year=year)
        records = [r for r in records if r.arms_exports_tiv is not None and r.arms_exports_tiv > 0]
        records.sort(key=lambda r: r.arms_exports_tiv or 0, reverse=True)
        return records[:limit]
