"""Wikidata SPARQL connector for weapon BOM and corporate ownership data.

Queries the Wikidata public SPARQL endpoint to extract:
- Weapon system -> manufacturer relationships (P176)
- Weapon system -> component relationships (P527)
- Component -> material relationships (P186)
- Corporate ownership chains (P749, P355)

Free, no auth. Rate limit: ~5 requests/minute.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"


@dataclass
class WikidataRelation:
    """A relationship extracted from Wikidata."""
    subject: str
    subject_label: str
    predicate: str
    object_: str
    object_label: str


class WikidataBOMClient:
    """Client for extracting weapon BOM data from Wikidata SPARQL."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def _query(self, sparql: str) -> list[dict]:
        """Execute a SPARQL query against Wikidata."""
        headers = {"Accept": "application/sparql-results+json"}
        params = {"query": sparql}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Wikidata SPARQL query (%d chars)", len(sparql))
            response = await client.get(
                WIKIDATA_SPARQL_URL, params=params, headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        results = []
        for binding in data.get("results", {}).get("bindings", []):
            row = {}
            for key, val in binding.items():
                row[key] = val.get("value", "")
            results.append(row)

        logger.info("Wikidata returned %d results", len(results))
        return results

    async def fetch_weapon_manufacturers(self, limit: int = 500) -> list[WikidataRelation]:
        """Fetch weapon system -> manufacturer relationships."""
        sparql = f"""
        SELECT ?weapon ?weaponLabel ?manufacturer ?manufacturerLabel WHERE {{
          ?weapon wdt:P31/wdt:P279* wd:Q15142889 .
          ?weapon wdt:P176 ?manufacturer .
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """
        rows = await self._query(sparql)
        return [
            WikidataRelation(
                subject=r.get("weapon", ""),
                subject_label=r.get("weaponLabel", ""),
                predicate="manufactured_by",
                object_=r.get("manufacturer", ""),
                object_label=r.get("manufacturerLabel", ""),
            )
            for r in rows
        ]

    async def fetch_weapon_components(self, weapon_qid: str) -> list[WikidataRelation]:
        """Fetch components of a specific weapon system (P527 has parts)."""
        sparql = f"""
        SELECT ?part ?partLabel ?material ?materialLabel ?mfr ?mfrLabel WHERE {{
          wd:{weapon_qid} wdt:P527+ ?part .
          OPTIONAL {{ ?part wdt:P186 ?material . }}
          OPTIONAL {{ ?part wdt:P176 ?mfr . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 200
        """
        rows = await self._query(sparql)
        relations = []
        for r in rows:
            relations.append(WikidataRelation(
                subject=weapon_qid,
                subject_label=r.get("partLabel", ""),
                predicate="has_component",
                object_=r.get("part", ""),
                object_label=r.get("partLabel", ""),
            ))
        return relations

    async def fetch_defense_company_subsidiaries(
        self, limit: int = 500,
    ) -> list[WikidataRelation]:
        """Fetch defense company ownership chains (P749 parent, P355 subsidiary)."""
        sparql = f"""
        SELECT ?company ?companyLabel ?parent ?parentLabel ?country ?countryLabel WHERE {{
          ?company wdt:P452 wd:Q232405 .
          OPTIONAL {{ ?company wdt:P749 ?parent . }}
          OPTIONAL {{ ?company wdt:P17 ?country . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """
        rows = await self._query(sparql)
        return [
            WikidataRelation(
                subject=r.get("company", ""),
                subject_label=r.get("companyLabel", ""),
                predicate="subsidiary_of",
                object_=r.get("parent", ""),
                object_label=r.get("parentLabel", ""),
            )
            for r in rows
            if r.get("parent")
        ]
