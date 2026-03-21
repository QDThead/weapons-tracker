"""UK HMRC Trade Info connector for arms and ammunition data.

Fetches monthly UK arms trade data (HS Chapter 93 — Arms & Ammunition)
from the UK Trade Info OData API. Provides import/export breakdowns
by partner country with values in GBP.

Free, no authentication required. Rate limit: 60 requests/minute.

Reference: https://api.uktradeinfo.com/
OData endpoint: https://api.uktradeinfo.com/OTS
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

HMRC_OTS_URL = "https://api.uktradeinfo.com/OTS"
HMRC_COUNTRY_URL = "https://api.uktradeinfo.com/Country"

# HS93 commodity range: 93000000–93999999
HS93_MIN = 93000000
HS93_MAX = 94000000

# FlowTypeId mapping:
#   1 = EU Imports, 2 = EU Exports, 3 = Non-EU Imports, 4 = Non-EU Exports
IMPORT_FLOW_IDS = {1, 3}
EXPORT_FLOW_IDS = {2, 4}

# Confidential/suppressed country ID to skip
CONFIDENTIAL_COUNTRY_ID = 977

# Max rows per page from HMRC API
PAGE_SIZE = 40000


@dataclass
class UKTradeRecord:
    """A monthly UK trade record for arms/ammunition (HS 93)."""
    partner_country: str
    year: int
    month: int
    value_gbp: int
    direction: str  # "import" or "export"
    commodity_code: int


class UKHMRCTradeClient:
    """Client for the UK HMRC Trade Info OData API.

    Fetches HS Chapter 93 (Arms & Ammunition) trade data for the UK,
    broken down by partner country and month.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._country_cache: dict[int, str] | None = None

    async def _fetch_country_lookup(self, client: httpx.AsyncClient) -> dict[int, str]:
        """Fetch the HMRC country ID-to-name mapping table.

        Results are cached for the lifetime of this client instance.
        """
        if self._country_cache is not None:
            return self._country_cache

        logger.info("Fetching HMRC country lookup table")
        countries: dict[int, str] = {}
        url = HMRC_COUNTRY_URL

        while url:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            for entry in data.get("value", []):
                country_id = entry.get("CountryId")
                country_name = entry.get("CountryName", "")
                alpha_code = entry.get("CountryCodeAlpha", "")
                # Prefer full CountryName over alpha code
                name = country_name if country_name else alpha_code
                if country_id is not None and name:
                    countries[country_id] = name

            # Handle OData pagination (@odata.nextLink)
            url = data.get("@odata.nextLink")

        logger.info("Loaded %d country mappings from HMRC", len(countries))
        self._country_cache = countries
        return countries

    async def _fetch_ots_page(
        self,
        client: httpx.AsyncClient,
        month_id: int,
        skip: int = 0,
    ) -> list[dict]:
        """Fetch a single page of OTS data for a given month.

        Args:
            client: httpx async client.
            month_id: Month in YYYYMM format (e.g. 202501).
            skip: Number of rows to skip (for pagination).

        Returns:
            List of raw OData value dicts.
        """
        odata_filter = (
            f"CommodityId ge {HS93_MIN} and CommodityId lt {HS93_MAX} "
            f"and MonthId eq {month_id}"
        )
        params = {
            "$filter": odata_filter,
            "$select": "CommodityId,CountryId,FlowTypeId,MonthId,Value,NetMass",
        }
        if skip > 0:
            params["$skip"] = str(skip)

        response = await client.get(HMRC_OTS_URL, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("value", [])

    async def _fetch_month(
        self,
        client: httpx.AsyncClient,
        month_id: int,
        countries: dict[int, str],
    ) -> list[UKTradeRecord]:
        """Fetch all HS93 trade records for a single month, handling pagination.

        Args:
            client: httpx async client.
            month_id: Month in YYYYMM format.
            countries: Country ID-to-name lookup.

        Returns:
            List of UKTradeRecord for the month.
        """
        all_rows: list[dict] = []
        skip = 0

        while True:
            page = await self._fetch_ots_page(client, month_id, skip)
            if not page:
                break
            all_rows.extend(page)
            if len(page) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

        year = month_id // 100
        month = month_id % 100

        records: list[UKTradeRecord] = []
        for row in all_rows:
            country_id = row.get("CountryId")
            flow_type = row.get("FlowTypeId")
            value = row.get("Value", 0)
            commodity_code = row.get("CommodityId", 0)

            # Skip confidential/suppressed records
            if country_id == CONFIDENTIAL_COUNTRY_ID:
                continue

            # Skip zero-value entries
            if not value or value <= 0:
                continue

            # Determine direction
            if flow_type in IMPORT_FLOW_IDS:
                direction = "import"
            elif flow_type in EXPORT_FLOW_IDS:
                direction = "export"
            else:
                continue

            partner_name = countries.get(country_id, f"Unknown ({country_id})")

            records.append(UKTradeRecord(
                partner_country=partner_name,
                year=year,
                month=month,
                value_gbp=int(value),
                direction=direction,
                commodity_code=commodity_code,
            ))

        logger.info("HMRC OTS %d: %d records (after filtering)", month_id, len(records))
        return records

    def _default_months(self) -> list[str]:
        """Generate default month IDs for the last 6 months (with ~2-month lag)."""
        now = datetime.now()
        months = []
        for i in range(2, 8):  # 2-7 months ago (data has ~2-month publication lag)
            d = now - timedelta(days=30 * i)
            months.append(f"{d.year}{d.month:02d}")
        return months

    async def fetch_uk_arms_trade(
        self, months: list[str] | None = None
    ) -> list[UKTradeRecord]:
        """Fetch UK arms trade data (HS 93) for the specified months.

        Args:
            months: List of month strings in "YYYYMM" format (e.g. ["202501", "202502"]).
                    Defaults to the last 6 months (offset by 2 months for data lag).

        Returns:
            List of UKTradeRecord with partner country, value, and direction.
        """
        if not months:
            months = self._default_months()

        month_ids = [int(m) for m in months]

        all_records: list[UKTradeRecord] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            # Load country lookup first
            countries = await self._fetch_country_lookup(client)

            for month_id in month_ids:
                try:
                    records = await self._fetch_month(client, month_id, countries)
                    all_records.extend(records)
                except Exception as e:
                    logger.warning("HMRC fetch failed for month %d: %s", month_id, e)
                # Respect rate limit: 60 req/min => ~1 req/sec to be safe
                await asyncio.sleep(1.0)

        logger.info(
            "Fetched %d total UK arms trade records across %d months",
            len(all_records), len(month_ids),
        )
        return all_records
