"""Open Canada procurement disclosure scraper.

Fetches DND/CAF contracts from search.open.canada.ca/contracts/
and normalizes vendor names for supplier deduplication.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date

import httpx

from src.storage.models import SupplierSector

logger = logging.getLogger(__name__)

OPEN_CANADA_URL = "https://search.open.canada.ca/opendata/search/contracts"

_STRIP_SUFFIXES = re.compile(
    r"\s*(inc\.?|ltd\.?|ltée?\.?|corp\.?|corporation|company|co\.|"
    r"limited|llc|lp|s\.a\.|gmbh|plc)\s*$",
    re.IGNORECASE,
)
_EXTRA_WHITESPACE = re.compile(r"\s+")

_SECTOR_KEYWORDS: dict[SupplierSector, list[str]] = {
    SupplierSector.SHIPBUILDING: ["frigate", "ship", "vessel", "naval", "maritime"],
    SupplierSector.LAND_VEHICLES: ["lav", "vehicle", "armoured", "armored", "tank"],
    SupplierSector.AEROSPACE: ["aircraft", "helicopter", "jet", "fighter", "f-35", "cf-18"],
    SupplierSector.ELECTRONICS: ["radar", "sensor", "communications", "radio", "electronic"],
    SupplierSector.SIMULATION: ["simulation", "training", "simulator"],
    SupplierSector.MUNITIONS: ["ammunition", "munition", "explosive", "bomb", "missile"],
    SupplierSector.CYBER: ["cyber", "software", "it ", "network", "data"],
    SupplierSector.MAINTENANCE: ["maintenance", "repair", "overhaul", "mro", "sustainment"],
    SupplierSector.SERVICES: ["consulting", "advisory", "professional", "logistics"],
}


@dataclass
class ProcurementRecord:
    """A parsed procurement contract record."""
    vendor_name: str
    vendor_name_normalized: str
    contract_number: str
    contract_value_cad: float
    description: str
    department: str
    award_date: date | None
    end_date: date | None
    is_sole_source: bool
    sector: SupplierSector


def normalize_vendor_name(name: str) -> str:
    """Normalize a vendor name for deduplication."""
    name = name.strip()
    name = _STRIP_SUFFIXES.sub("", name).strip()
    name = _EXTRA_WHITESPACE.sub(" ", name)
    return name


def classify_sector(description: str) -> SupplierSector:
    """Classify a contract description into a sector."""
    desc_lower = description.lower()
    for sector, keywords in _SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                return sector
    return SupplierSector.OTHER


def _parse_date(s: str | None) -> date | None:
    """Parse a date string from the API."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except (ValueError, TypeError):
        return None


class ProcurementScraperClient:
    """Async client for Open Canada procurement disclosure."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_dnd_contracts(
        self,
        start_date: str = "2021-01-01",
        max_records: int = 10000,
    ) -> list[ProcurementRecord]:
        """Fetch National Defence contracts from Open Canada."""
        records: list[ProcurementRecord] = []
        offset = 0
        page_size = 100

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while offset < max_records:
                params = {
                    "search_text": "",
                    "owner_org": "dnd-mdn",
                    "start_row": str(offset),
                    "rows": str(page_size),
                }
                try:
                    resp = await client.get(OPEN_CANADA_URL, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                except Exception as e:
                    logger.error("Procurement API error at offset %d: %s", offset, e)
                    break

                results = data.get("results", [])
                if not results:
                    break

                for item in results:
                    vendor = item.get("vendor_name", "") or ""
                    if not vendor:
                        continue
                    contract_num = item.get("contract_number", "") or item.get("reference_number", "")
                    if not contract_num:
                        continue

                    description = item.get("description", "") or ""
                    value_str = item.get("contract_value", "0") or "0"
                    try:
                        value = float(str(value_str).replace(",", "").replace("$", ""))
                    except (ValueError, TypeError):
                        value = 0.0

                    solicitation = (item.get("solicitation_procedure", "") or "").lower()
                    is_sole_source = "non-competitive" in solicitation

                    records.append(ProcurementRecord(
                        vendor_name=vendor,
                        vendor_name_normalized=normalize_vendor_name(vendor),
                        contract_number=contract_num,
                        contract_value_cad=value,
                        description=description,
                        department=item.get("owner_org", "DND"),
                        award_date=_parse_date(item.get("contract_date")),
                        end_date=_parse_date(item.get("delivery_date")),
                        is_sole_source=is_sole_source,
                        sector=classify_sector(description),
                    ))

                offset += page_size
                logger.info("Fetched %d contracts so far (offset %d)", len(records), offset)
                await asyncio.sleep(1.0)

        logger.info("Total procurement records fetched: %d", len(records))
        return records
