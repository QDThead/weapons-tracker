"""DSCA Major Arms Sales via Federal Register API.

Fetches US arms sale notifications published in the Federal Register.
These are mandatory Congressional notifications under Section 36(b)
of the Arms Export Control Act — every major US arms sale is here.

Data includes: buyer country, weapon systems, dollar value, date.
Updated within days of DSCA approval. Free, no auth required.

Reference: https://www.federalregister.gov/
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

FR_API = "https://www.federalregister.gov/api/v1/documents.json"
FR_DOC_API = "https://www.federalregister.gov/api/v1/documents"


@dataclass
class ArmsSaleNotification:
    """A US arms sale notification from the Federal Register."""
    document_number: str
    publication_date: str
    buyer_country: str
    total_value_usd: float | None
    weapon_systems: str
    transmittal_number: str
    url: str
    raw_text: str


class DSCASalesClient:
    """Client for fetching DSCA arms sale notifications via the Federal Register API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_recent_sales(
        self, count: int = 20, year: int | None = None
    ) -> list[ArmsSaleNotification]:
        """Fetch recent arms sale notifications.

        Args:
            count: Number of notifications to fetch (max 100).
            year: Filter by year (e.g., 2026). None = all years.

        Returns:
            List of parsed sale notifications.
        """
        params = {
            "conditions[term]": '"arms sales notification"',
            "conditions[agencies][]": "defense-department",
            "per_page": min(count, 100),
            "order": "newest",
            "fields[]": ["document_number", "title", "publication_date",
                         "html_url", "raw_text_url"],
        }
        if year:
            params["conditions[publication_date][year]"] = year

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Fetching DSCA sales from Federal Register (count=%d)", count)
            response = await client.get(FR_API, params=params)
            response.raise_for_status()

        data = response.json()
        documents = data.get("results", [])
        logger.info("Found %d arms sale documents", len(documents))

        # Fetch full text for each and parse
        sales = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for doc in documents:
                try:
                    sale = await self._parse_notification(client, doc)
                    if sale:
                        sales.append(sale)
                except Exception as e:
                    logger.warning("Failed to parse %s: %s", doc.get("document_number"), e)

        return sales

    async def _parse_notification(
        self, client: httpx.AsyncClient, doc: dict
    ) -> ArmsSaleNotification | None:
        """Fetch and parse a single arms sale notification."""
        raw_url = doc.get("raw_text_url")
        if not raw_url:
            return None

        response = await client.get(raw_url)
        response.raise_for_status()
        text = response.text

        # Extract buyer country
        buyer = ""
        buyer_match = re.search(
            r'\(i\)\s*Prospective Purchaser:\s*(?:Government of\s*)?(.+?)(?:\n|$)',
            text, re.IGNORECASE
        )
        if buyer_match:
            buyer = buyer_match.group(1).strip().rstrip(".")

        # Extract total value
        total_value = None
        value_match = re.search(
            r'TOTAL[.\s]*\$?([\d,.]+)\s*(billion|million)',
            text, re.IGNORECASE
        )
        if value_match:
            num = float(value_match.group(1).replace(",", ""))
            unit = value_match.group(2).lower()
            total_value = num * 1e9 if unit == "billion" else num * 1e6

        # Extract weapon systems description
        weapons = ""
        weapons_match = re.search(
            r'Major Defense Equipment.*?:\s*\n(.*?)(?:Non-Major|TOTAL|\(iv\))',
            text, re.DOTALL | re.IGNORECASE
        )
        if weapons_match:
            raw_weapons = weapons_match.group(1)
            # Clean up and extract key items
            lines = [line.strip() for line in raw_weapons.split("\n") if line.strip()]
            items = []
            for line in lines:
                line = re.sub(r'\s+', ' ', line)
                if re.search(r'\d', line) and len(line) > 10:
                    items.append(line)
            weapons = "; ".join(items[:5])

        # Extract transmittal number
        transmittal = ""
        trans_match = re.search(r'Transmittal No\.\s*(\S+)', text)
        if trans_match:
            transmittal = trans_match.group(1)

        if not buyer:
            return None

        return ArmsSaleNotification(
            document_number=doc.get("document_number", ""),
            publication_date=doc.get("publication_date", ""),
            buyer_country=buyer,
            total_value_usd=total_value,
            weapon_systems=weapons,
            transmittal_number=transmittal,
            url=doc.get("html_url", ""),
            raw_text=text[:2000],
        )
