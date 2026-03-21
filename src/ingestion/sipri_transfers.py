"""SIPRI Arms Transfers Database connector.

Fetches deal-level arms transfer data from SIPRI's new backend API.
Data covers all major conventional arms transfers since 1950.
Updated annually (March).

Reference: https://armstransfers.sipri.org/
API backend: https://atbackend.sipri.org/api/p/
"""

from __future__ import annotations

import base64
import csv
import io
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# New SIPRI backend API (public, no auth required)
SIPRI_API_BASE = "https://atbackend.sipri.org/api/p"

# SIPRI weapon category entity IDs (from /typelists/getAllArmamentCategories)
WEAPON_CATEGORIES = {
    "Air-defence systems": 1050204,
    "Aircraft": 1050194,
    "Armoured vehicles": 1050196,
    "Artillery": 1050195,
    "Engines": 1050197,
    "Missiles": 1050199,
    "Naval weapons": 1050206,
    "Sensors": 1050198,
    "Satellites": 1050203,
    "Ships": 1050205,
    "Other": 1050202,
    "SALW": 1050201,
}

# Backward-compatible mapping: country name → entity ID.
# This is a curated subset for the scheduler. The client also supports
# resolving any country name dynamically via the API.
SIPRI_COUNTRY_CODES = {
    "Canada": 1050339,
    "United States": 1050595,
    "United Kingdom": 1050559,
    "France": 1050443,
    "Germany": 1050674,
    "Russia": 1050481,
    "China": 1050672,
    "India": 1050473,
    "Israel": 1050426,
    "Ukraine": 1050536,
    "Australia": 1050385,
    "South Korea": 1050325,
    "Japan": 1050409,
    "Turkiye": 1050685,
    "Saudi Arabia": 1050663,
    "Egypt": 1050652,
    "Italy": 1050407,
    "Sweden": 1050484,
    "Brazil": 1050387,
    "Iran": 1050412,
    "Pakistan": 1050519,
    "Poland": 1050520,
    "Netherlands": 1050503,
    "Norway": 1050482,
    "Spain": 1050518,
    "Taiwan": 1050362,
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
    number_delivered: str = ""


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
    """Client for querying the SIPRI Arms Transfers Database.

    Uses the new backend API at atbackend.sipri.org which accepts
    POST requests with filter-based queries and returns base64-encoded CSV.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._country_cache: dict[str, int] | None = None

    async def _ensure_country_cache(self, client: httpx.AsyncClient) -> None:
        """Fetch and cache the full country → entity ID mapping."""
        if self._country_cache is not None:
            return

        response = await client.get(f"{SIPRI_API_BASE}/countries/getAllCountriesTrimmed")
        response.raise_for_status()
        countries = response.json()
        self._country_cache = {c["Name"]: c["EntityId"] for c in countries}
        logger.info("Cached %d SIPRI country codes", len(self._country_cache))

    async def _resolve_country(self, client: httpx.AsyncClient, name: str) -> int:
        """Resolve a country name to its SIPRI entity ID."""
        await self._ensure_country_cache(client)
        assert self._country_cache is not None

        # Exact match first
        entity_id = self._country_cache.get(name)
        if entity_id is not None:
            return entity_id

        # Case-insensitive match
        name_lower = name.lower()
        for cached_name, eid in self._country_cache.items():
            if cached_name.lower() == name_lower:
                return eid

        available = sorted(self._country_cache.keys())
        raise ValueError(f"Unknown country: {name}. Available: {available[:20]}...")

    def _build_filters(self, query: SIPRIQuery) -> dict:
        """Build the POST request body for the trade register endpoint."""
        filters = []

        if query.seller_country_codes:
            filters.append({
                "field": "Supplier",
                "oldField": "",
                "condition": "contains",
                "value1": "",
                "value2": "",
                "listData": query.seller_country_codes,
            })

        if query.buyer_country_codes:
            filters.append({
                "field": "Recipient",
                "oldField": "",
                "condition": "contains",
                "value1": "",
                "value2": "",
                "listData": query.buyer_country_codes,
            })

        # Year range filters
        filters.append({
            "field": "Delivery year",
            "oldField": "",
            "condition": "contains",
            "value1": query.low_year,
            "value2": query.high_year,
            "listData": [],
        })
        filters.append({
            "field": "Order year",
            "oldField": "",
            "condition": "contains",
            "value1": 0,
            "value2": query.high_year,
            "listData": [],
        })

        if query.armament_category_ids:
            filters.append({
                "field": "Weapon category",
                "oldField": "",
                "condition": "contains",
                "value1": "",
                "value2": "",
                "listData": query.armament_category_ids,
            })

        if query.include_open_deals:
            filters.append({
                "field": "opendeals",
                "oldField": "",
                "condition": "",
                "value1": "",
                "value2": "",
                "listData": [],
            })

        return {"filters": filters, "logic": "AND"}

    async def fetch_transfers(self, query: SIPRIQuery) -> list[SIPRITransferRecord]:
        """Fetch arms transfer records from SIPRI.

        Args:
            query: Query parameters specifying countries, years, and weapon types.

        Returns:
            List of transfer records.
        """
        request_body = self._build_filters(query)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching SIPRI transfers: sellers=%s, buyers=%s, years=%d-%d",
                query.seller_country_codes, query.buyer_country_codes,
                query.low_year, query.high_year,
            )
            response = await client.post(
                f"{SIPRI_API_BASE}/trades/trade-register-csv/",
                json=request_body,
            )
            response.raise_for_status()

        data = response.json()
        csv_bytes = base64.b64decode(data["bytes"])
        # SIPRI CSV uses latin-1 encoding for special characters
        csv_text = csv_bytes.decode("latin-1")

        return self._parse_csv(csv_text)

    def _parse_csv(self, csv_text: str) -> list[SIPRITransferRecord]:
        """Parse SIPRI CSV export into structured records.

        New CSV format columns (0-indexed):
            0: Recipient, 1: Supplier, 2: Year of order, 3: (marker),
            4: Number ordered, 5: (marker), 6: Weapon designation,
            7: Weapon description, 8: Number delivered, 9: (marker),
            10: Year(s) of delivery, 11: status, 12: Comments,
            13: SIPRI TIV per unit, 14: SIPRI TIV for total order,
            15: SIPRI TIV of delivered weapons
        """
        records = []
        reader = csv.reader(io.StringIO(csv_text))

        # Skip header/metadata rows (SIPRI CSV has ~11 metadata rows before data)
        headers_found = False
        for row in reader:
            if not row:
                continue

            # Look for the header row
            if not headers_found:
                if len(row) > 3 and "recipient" in row[0].lower():
                    headers_found = True
                continue

            # Parse data rows (need at least 12 columns for a valid record)
            if len(row) >= 12:
                record = SIPRITransferRecord(
                    buyer=row[0].strip(),
                    seller=row[1].strip(),
                    order_year=row[2].strip(),
                    number_ordered=row[4].strip() if len(row) > 4 else "",
                    weapon_designation=row[6].strip() if len(row) > 6 else "",
                    weapon_description=row[7].strip() if len(row) > 7 else "",
                    number_delivered=row[8].strip() if len(row) > 8 else "",
                    delivery_years=row[10].strip() if len(row) > 10 else "",
                    status=row[11].strip() if len(row) > 11 else "",
                    comments=row[12].strip() if len(row) > 12 else "",
                    tiv_per_unit=row[13].strip() if len(row) > 13 else "",
                    tiv_total_order=row[14].strip() if len(row) > 14 else "",
                    tiv_delivered=row[15].strip() if len(row) > 15 else "",
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
            # Try dynamic resolution via the API
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                code = await self._resolve_country(client, country_name)

        query = SIPRIQuery(seller_country_codes=[code], low_year=low_year, high_year=high_year)
        return await self.fetch_transfers(query)

    async def fetch_country_imports(
        self, country_name: str, low_year: int = 2000, high_year: int = 2025
    ) -> list[SIPRITransferRecord]:
        """Fetch all imports for a specific country."""
        code = SIPRI_COUNTRY_CODES.get(country_name)
        if code is None:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                code = await self._resolve_country(client, country_name)

        query = SIPRIQuery(buyer_country_codes=[code], low_year=low_year, high_year=high_year)
        return await self.fetch_transfers(query)

    async def fetch_bilateral_trade(
        self, seller: str, buyer: str, low_year: int = 2000, high_year: int = 2025
    ) -> list[SIPRITransferRecord]:
        """Fetch arms transfers between two specific countries."""
        seller_code = SIPRI_COUNTRY_CODES.get(seller)
        buyer_code = SIPRI_COUNTRY_CODES.get(buyer)

        if seller_code is None or buyer_code is None:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if seller_code is None:
                    seller_code = await self._resolve_country(client, seller)
                if buyer_code is None:
                    buyer_code = await self._resolve_country(client, buyer)

        query = SIPRIQuery(
            seller_country_codes=[seller_code],
            buyer_country_codes=[buyer_code],
            low_year=low_year,
            high_year=high_year,
        )
        return await self.fetch_transfers(query)
