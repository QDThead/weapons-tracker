"""SIPRI Arms Transfers Database connector.

Fetches deal-level arms transfer data from SIPRI's export endpoints.
Data covers all major conventional arms transfers since 1950.
Updated annually (March).

Reference: https://armstransfers.sipri.org/
"""

import csv
import io
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

SIPRI_EXPORT_URL = "https://armstrade.sipri.org/armstrade/html/export_trade_register.php"

# SIPRI weapon category codes
WEAPON_CATEGORIES = {
    1: "aircraft",
    2: "air_defence",
    3: "anti_submarine",
    4: "armoured_vehicle",
    5: "artillery",
    6: "engine",
    7: "missile",
    8: "naval_weapon",
    9: "satellite",
    10: "sensor",
    11: "ship",
    12: "other",
}

# SIPRI country codes (subset — full list at SIPRI site)
# These are used in the API query parameters
SIPRI_COUNTRY_CODES = {
    "Canada": 39,
    "United States": 225,
    "United Kingdom": 224,
    "France": 68,
    "Germany": 72,
    "Russia": 179,
    "China": 44,
    "India": 95,
    "Israel": 101,
    "Ukraine": 223,
    "Australia": 10,
    "South Korea": 115,
    "Japan": 106,
    "Turkey": 218,
    "Saudi Arabia": 183,
    "Egypt": 60,
    "Italy": 102,
    "Sweden": 201,
    "Brazil": 31,
    "Iran": 98,
    "Pakistan": 157,
    "Poland": 166,
    "Netherlands": 146,
    "Norway": 154,
    "Spain": 196,
    "Taiwan": 207,
}


@dataclass
class SIPRITransferRecord:
    """A single arms transfer record from SIPRI."""
    seller: str
    buyer: str
    order_year: str
    delivery_years: str
    number_ordered: str
    weapon_designation: str
    weapon_description: str
    status: str
    tiv_per_unit: str
    tiv_total_order: str
    tiv_delivered: str
    comments: str


@dataclass
class SIPRIQuery:
    """Query parameters for the SIPRI Trade Register."""
    seller_country_codes: list[int] = field(default_factory=list)
    buyer_country_codes: list[int] = field(default_factory=list)
    low_year: int = 2000
    high_year: int = 2025
    armament_category_ids: list[int] = field(default_factory=list)
    include_open_deals: bool = True


class SIPRITransfersClient:
    """Client for querying the SIPRI Arms Transfers Database."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def _build_params(self, query: SIPRIQuery) -> dict:
        """Build HTTP params for the SIPRI export endpoint."""
        params = {
            "low_year": query.low_year,
            "high_year": query.high_year,
            "filetype": "csv",
            "include_open_deals": "on" if query.include_open_deals else "",
            "sum": "on",
        }

        for i, code in enumerate(query.seller_country_codes):
            params[f"seller_country_code{i}"] = code

        for i, code in enumerate(query.buyer_country_codes):
            params[f"buyer_country_code{i}"] = code

        for i, cat_id in enumerate(query.armament_category_ids):
            params[f"armament_category_id{i}"] = cat_id

        return params

    async def fetch_transfers(self, query: SIPRIQuery) -> list[SIPRITransferRecord]:
        """Fetch arms transfer records from SIPRI.

        Args:
            query: Query parameters specifying countries, years, and weapon types.

        Returns:
            List of transfer records.
        """
        params = self._build_params(query)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching SIPRI transfers: sellers=%s, buyers=%s, years=%d-%d",
                query.seller_country_codes, query.buyer_country_codes,
                query.low_year, query.high_year,
            )
            response = await client.get(SIPRI_EXPORT_URL, params=params)
            response.raise_for_status()

        return self._parse_csv(response.text)

    def _parse_csv(self, csv_text: str) -> list[SIPRITransferRecord]:
        """Parse SIPRI CSV export into structured records."""
        records = []
        reader = csv.reader(io.StringIO(csv_text))

        # Skip header rows (SIPRI CSV has metadata rows before data)
        headers_found = False
        for row in reader:
            if not row:
                continue

            # Look for the header row
            if not headers_found:
                if len(row) > 3 and "seller" in row[0].lower():
                    headers_found = True
                continue

            # Parse data rows
            if len(row) >= 10:
                record = SIPRITransferRecord(
                    seller=row[0].strip() if len(row) > 0 else "",
                    buyer=row[1].strip() if len(row) > 1 else "",
                    order_year=row[2].strip() if len(row) > 2 else "",
                    delivery_years=row[3].strip() if len(row) > 3 else "",
                    number_ordered=row[4].strip() if len(row) > 4 else "",
                    weapon_designation=row[5].strip() if len(row) > 5 else "",
                    weapon_description=row[6].strip() if len(row) > 6 else "",
                    status=row[7].strip() if len(row) > 7 else "",
                    tiv_per_unit=row[8].strip() if len(row) > 8 else "",
                    tiv_total_order=row[9].strip() if len(row) > 9 else "",
                    tiv_delivered=row[10].strip() if len(row) > 10 else "",
                    comments=row[11].strip() if len(row) > 11 else "",
                )
                records.append(record)

        logger.info("Parsed %d transfer records from SIPRI", len(records))
        return records

    async def fetch_country_exports(
        self, country_name: str, low_year: int = 2000, high_year: int = 2025
    ) -> list[SIPRITransferRecord]:
        """Fetch all exports from a specific country."""
        code = SIPRI_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}. Available: {list(SIPRI_COUNTRY_CODES.keys())}")

        query = SIPRIQuery(seller_country_codes=[code], low_year=low_year, high_year=high_year)
        return await self.fetch_transfers(query)

    async def fetch_country_imports(
        self, country_name: str, low_year: int = 2000, high_year: int = 2025
    ) -> list[SIPRITransferRecord]:
        """Fetch all imports for a specific country."""
        code = SIPRI_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}. Available: {list(SIPRI_COUNTRY_CODES.keys())}")

        query = SIPRIQuery(buyer_country_codes=[code], low_year=low_year, high_year=high_year)
        return await self.fetch_transfers(query)

    async def fetch_bilateral_trade(
        self, seller: str, buyer: str, low_year: int = 2000, high_year: int = 2025
    ) -> list[SIPRITransferRecord]:
        """Fetch arms transfers between two specific countries."""
        seller_code = SIPRI_COUNTRY_CODES.get(seller)
        buyer_code = SIPRI_COUNTRY_CODES.get(buyer)
        if seller_code is None:
            raise ValueError(f"Unknown seller country: {seller}")
        if buyer_code is None:
            raise ValueError(f"Unknown buyer country: {buyer}")

        query = SIPRIQuery(
            seller_country_codes=[seller_code],
            buyer_country_codes=[buyer_code],
            low_year=low_year,
            high_year=high_year,
        )
        return await self.fetch_transfers(query)
