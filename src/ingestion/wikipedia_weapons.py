"""Wikipedia weapon system infobox parser.

Extracts structured data from Wikipedia weapon system articles:
manufacturer, engine, designer, unit cost, operators.

Uses the Wikipedia MediaWiki API (free, no auth, rate limit 200 req/sec).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"


@dataclass
class WeaponInfobox:
    """Structured data from a Wikipedia weapon system infobox."""
    name: str
    manufacturer: list[str] = field(default_factory=list)
    designer: list[str] = field(default_factory=list)
    engine: str = ""
    engine_manufacturer: str = ""
    unit_cost: str = ""
    operators: list[str] = field(default_factory=list)
    origin_country: str = ""


class WikipediaWeaponsClient:
    """Client for parsing Wikipedia weapon system infoboxes."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_infobox(self, weapon_name: str) -> WeaponInfobox | None:
        """Fetch and parse the infobox from a Wikipedia weapon article."""
        params = {
            "action": "parse",
            "page": weapon_name,
            "prop": "wikitext",
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Wikipedia fetch: %s", weapon_name)
            response = await client.get(WIKIPEDIA_API_URL, params=params)
            response.raise_for_status()

        data = response.json()

        if "error" in data:
            logger.warning("Wikipedia page not found: %s", weapon_name)
            return None

        wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
        if not wikitext:
            return None

        return self._parse_infobox(weapon_name, wikitext)

    def _parse_infobox(self, name: str, wikitext: str) -> WeaponInfobox:
        """Extract infobox fields from wikitext."""
        info = WeaponInfobox(name=name)

        # Extract infobox content
        infobox_match = re.search(
            r"\{\{Infobox[^}]*\n(.*?)\n\}\}",
            wikitext,
            re.DOTALL | re.IGNORECASE,
        )
        if not infobox_match:
            return info

        infobox = infobox_match.group(1)

        # Parse key fields
        info.manufacturer = self._extract_list(infobox, "manufacturer")
        info.designer = self._extract_list(infobox, "designer")
        info.engine = self._extract_value(infobox, "engine")
        info.unit_cost = self._extract_value(infobox, "unit_cost")
        info.origin_country = self._extract_value(infobox, "origin")

        # Try to extract engine manufacturer from engine field
        if info.engine:
            # Common pattern: "CompanyName EngineName"
            parts = info.engine.split()
            if len(parts) >= 2:
                info.engine_manufacturer = parts[0]

        return info

    @staticmethod
    def _extract_value(infobox: str, field_name: str) -> str:
        """Extract a single value from an infobox field."""
        pattern = rf"\|\s*{field_name}\s*=\s*(.+?)(?:\n\||\n\}})"
        match = re.search(pattern, infobox, re.IGNORECASE)
        if not match:
            return ""
        value = match.group(1).strip()
        # Remove wiki markup
        value = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", value)
        value = re.sub(r"\{\{[^}]*\}\}", "", value)
        value = re.sub(r"<[^>]+>", "", value)
        return value.strip()

    @staticmethod
    def _extract_list(infobox: str, field_name: str) -> list[str]:
        """Extract a list of values from an infobox field."""
        pattern = rf"\|\s*{field_name}\s*=\s*(.+?)(?:\n\||\n\}})"
        match = re.search(pattern, infobox, re.IGNORECASE | re.DOTALL)
        if not match:
            return []
        value = match.group(1).strip()
        # Remove wiki markup
        value = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", value)
        value = re.sub(r"\{\{[^}]*\}\}", "", value)
        value = re.sub(r"<[^>]+>", "", value)
        # Split by common separators
        items = re.split(r"[,\n•*]", value)
        return [item.strip() for item in items if item.strip()]
