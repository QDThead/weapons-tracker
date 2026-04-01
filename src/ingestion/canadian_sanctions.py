"""Canadian Sanctions (GAC SEMA) connector.

Fetches Canada's consolidated autonomous sanctions list from Global Affairs
Canada. Covers the Special Economic Measures Act (SEMA) and the Justice for
Victims of Corrupt Foreign Officials Act (JVCFOA/Magnitsky).

Source XML: international.gc.ca SEMA list.
Freshness: updated as sanctions are added/modified. Auth: none required.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

import httpx

logger = logging.getLogger(__name__)

SEMA_XML_URL = (
    "https://www.international.gc.ca/world-monde/assets/office_docs/"
    "international_relations-relations_internationales/sanctions/sema-lmes.xml"
)

OPENSANCTIONS_JSON_URL = (
    "https://data.opensanctions.org/datasets/latest/"
    "ca_dfatd_sema_sanctions/index.json"
)


@dataclass
class CanadianSanctionEntry:
    """A single entity on Canada's sanctions list."""

    name: str
    entity_type: str
    country: str | None
    regime: str | None
    schedule: str | None
    date_listed: str | None

    def to_dict(self) -> dict:
        return asdict(self)


class CanadianSanctionsClient:
    """Async client for the GAC consolidated sanctions list."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_sanctions(self) -> list[CanadianSanctionEntry]:
        """Fetch and parse the Canadian SEMA sanctions XML.

        Falls back to OpenSanctions JSON if the GAC XML fails.
        """
        entries = await self._try_gac_xml()
        if entries:
            return entries

        logger.warning("GAC XML failed, trying OpenSanctions fallback")
        return await self._try_opensanctions()

    async def _try_gac_xml(self) -> list[CanadianSanctionEntry]:
        """Parse the official GAC XML sanctions list."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(SEMA_XML_URL)
                response.raise_for_status()
            except Exception as e:
                logger.warning("GAC SEMA XML fetch failed: %s", e)
                return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.warning("GAC SEMA XML parse failed: %s", e)
            return []

        entries: list[CanadianSanctionEntry] = []
        for record in root.iter():
            if record.tag in ("record", "item", "entity", "Record", "Item", "Entity"):
                name = self._get_text(record, ["LastName", "Entity", "Name", "name",
                                                "GivenName", "last_name"])
                given = self._get_text(record, ["GivenName", "given_name", "FirstName"])
                if given and name:
                    name = f"{given} {name}"
                if not name:
                    continue

                entries.append(CanadianSanctionEntry(
                    name=name.strip(),
                    entity_type=self._get_text(record, ["Type", "type", "EntityType"]) or "Unknown",
                    country=self._get_text(record, ["Country", "country", "CountryOfResidence"]),
                    regime=self._get_text(record, ["Regime", "regime", "Schedule", "Act"]),
                    schedule=self._get_text(record, ["Schedule", "schedule"]),
                    date_listed=self._get_text(record, ["DateListed", "date_listed", "ListingDate"]),
                ))

        if not entries:
            for record in root.iter():
                if record.text and record.text.strip() and record.tag not in (
                    "root", "data", "sanctions", "list"
                ):
                    pass

        logger.info("GAC SEMA: parsed %d sanctioned entities", len(entries))
        return entries

    async def _try_opensanctions(self) -> list[CanadianSanctionEntry]:
        """Fallback: fetch structured data from OpenSanctions mirror."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(OPENSANCTIONS_JSON_URL)
                resp.raise_for_status()
                index = resp.json()
            except Exception as e:
                logger.error("OpenSanctions fallback failed: %s", e)
                return []

        targets_url = None
        for resource in index.get("resources", []):
            if "targets.simple" in resource.get("name", ""):
                targets_url = resource.get("url")
                break

        if not targets_url:
            logger.warning("OpenSanctions: no targets.simple resource found")
            return self._build_summary_from_index(index)

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                resp = await client.get(targets_url)
                resp.raise_for_status()
            except Exception as e:
                logger.warning("OpenSanctions targets fetch failed: %s", e)
                return self._build_summary_from_index(index)

        entries: list[CanadianSanctionEntry] = []
        import csv
        import io
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            name = row.get("name", "").strip()
            if not name:
                continue
            entries.append(CanadianSanctionEntry(
                name=name,
                entity_type=row.get("schema", "Unknown"),
                country=(row.get("countries") or "").split(";")[0].strip() or None,
                regime=row.get("datasets", "").replace("ca_dfatd_sema_sanctions", "SEMA"),
                schedule=None,
                date_listed=row.get("first_seen"),
            ))

        logger.info("OpenSanctions fallback: parsed %d entries", len(entries))
        return entries

    @staticmethod
    def _build_summary_from_index(index: dict) -> list[CanadianSanctionEntry]:
        """Build a minimal summary from the OpenSanctions index metadata."""
        target_count = index.get("target_count", 0)
        title = index.get("title", "Canadian Sanctions")
        return [CanadianSanctionEntry(
            name=f"{title} ({target_count} entities)",
            entity_type="summary",
            country=None,
            regime="SEMA + JVCFOA",
            schedule=None,
            date_listed=index.get("last_change"),
        )]

    @staticmethod
    def _get_text(element: ET.Element, tag_names: list[str]) -> str | None:
        for tag in tag_names:
            el = element.find(tag)
            if el is not None and el.text:
                return el.text.strip()
        return None
