"""US Census Bureau Foreign Trade API connector.

Provides MONTHLY arms trade data (HS Chapter 93) for US imports and exports
by partner country. Much more current than annual sources — typically
available within 2 months of the trade date.

Free, no auth required for basic queries.

Reference: https://api.census.gov/data/timeseries/intltrade.html
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

CENSUS_EXPORTS_URL = "https://api.census.gov/data/timeseries/intltrade/exports/hs"
CENSUS_IMPORTS_URL = "https://api.census.gov/data/timeseries/intltrade/imports/hs"

# Aggregate region codes to exclude (we only want actual countries)
_EXCLUDE_CODES = {
    "0000",  # Total
    "-",     # Unknown
}
_EXCLUDE_PREFIXES = ("OECD", "NATO", "ASIA", "APEC", "EUROPE", "PACIFIC",
                     "EURO ", "TWENTY", "OPEC", "CAFTA", "NORTH AM",
                     "SOUTH AM", "CENTRAL AM", "AFRICA", "MIDDLE EAST",
                     "SOUTH/CENT", "ASEAN", "WESTERN")


@dataclass
class CensusTradeRecord:
    """A monthly US trade record for arms/ammunition."""
    partner_country: str
    partner_code: str
    year: int
    month: int
    value_usd: int
    direction: str  # "export" or "import"
    commodity: str


class CensusTradeClient:
    """Client for the US Census Bureau Foreign Trade API."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch_us_exports(
        self, months: list[str] | None = None
    ) -> list[CensusTradeRecord]:
        """Fetch US arms exports by partner country.

        Args:
            months: List of "YYYY-MM" strings. Defaults to last 6 months.

        Returns:
            List of monthly export records by country.
        """
        if not months:
            from datetime import datetime, timedelta
            now = datetime.now()
            months = []
            for i in range(2, 8):  # 2-7 months ago (data has ~2 month lag)
                d = now - timedelta(days=30 * i)
                months.append(f"{d.year}-{d.month:02d}")

        all_records = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for month in months:
                try:
                    records = await self._fetch_month(client, CENSUS_EXPORTS_URL,
                                                     "E_COMMODITY", month, "export")
                    all_records.extend(records)
                except Exception as e:
                    logger.warning("Census export fetch failed for %s: %s", month, e)

        return all_records

    async def fetch_us_imports(
        self, months: list[str] | None = None
    ) -> list[CensusTradeRecord]:
        """Fetch US arms imports by partner country."""
        if not months:
            from datetime import datetime, timedelta
            now = datetime.now()
            months = []
            for i in range(2, 8):
                d = now - timedelta(days=30 * i)
                months.append(f"{d.year}-{d.month:02d}")

        all_records = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for month in months:
                try:
                    records = await self._fetch_month(client, CENSUS_IMPORTS_URL,
                                                     "I_COMMODITY", month, "import")
                    all_records.extend(records)
                except Exception as e:
                    logger.warning("Census import fetch failed for %s: %s", month, e)

        return all_records

    async def _fetch_month(
        self, client: httpx.AsyncClient, base_url: str,
        commodity_var: str, month: str, direction: str
    ) -> list[CensusTradeRecord]:
        """Fetch a single month of trade data."""
        params = {
            "get": f"CTY_CODE,CTY_NAME,ALL_VAL_MO",
            "COMM_LVL": "HS2",
            commodity_var: "93",
            "time": month,
        }
        response = await client.get(base_url, params=params)
        response.raise_for_status()

        data = response.json()
        if len(data) < 2:
            return []

        year, mo = month.split("-")
        records = []
        for row in data[1:]:
            code = row[0]
            name = row[1]
            value = int(row[2]) if row[2] else 0

            # Skip aggregates and zero-value
            if code in _EXCLUDE_CODES or value == 0:
                continue
            if any(name.upper().startswith(p) for p in _EXCLUDE_PREFIXES):
                continue

            records.append(CensusTradeRecord(
                partner_country=name,
                partner_code=code,
                year=int(year),
                month=int(mo),
                value_usd=value,
                direction=direction,
                commodity="HS 93 - Arms & Ammunition",
            ))

        logger.info("Census %s %s: %d country records", direction, month, len(records))
        return records
