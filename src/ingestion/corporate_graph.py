"""Corporate ownership graph connector.

Builds defense company ownership chains from multiple OSINT sources:
- Wikidata SPARQL (primary): P749 parent org, P355 subsidiary
- OpenCorporates (supplemental): free tier, 50 requests/day
- SEC EDGAR (US companies): 10-K filings for supply chain info

Used to populate SupplyChainNode and SupplyChainEdge tables
with corporate ownership relationships.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
OPENCORPORATES_URL = "https://api.opencorporates.com/v0.4/companies/search"
SEC_EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


@dataclass
class CorporateEntity:
    """A company with ownership information."""
    name: str
    country: str
    parent_name: str | None = None
    is_state_owned: bool = False
    industry: str = "defense"
    source: str = "wikidata"


class CorporateGraphClient:
    """Client for building defense company ownership graphs."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_defense_companies_wikidata(
        self, limit: int = 300,
    ) -> list[CorporateEntity]:
        """Fetch defense companies with ownership from Wikidata."""
        sparql = f"""
        SELECT ?company ?companyLabel ?parent ?parentLabel
               ?country ?countryLabel ?ownerType ?ownerTypeLabel
        WHERE {{
          ?company wdt:P452 wd:Q232405 .
          OPTIONAL {{ ?company wdt:P749 ?parent . }}
          OPTIONAL {{ ?company wdt:P17 ?country . }}
          OPTIONAL {{ ?company wdt:P31 ?ownerType .
                     FILTER(?ownerType = wd:Q270791) }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """
        headers = {"Accept": "application/sparql-results+json"}
        params = {"query": sparql}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Fetching defense companies from Wikidata")
            response = await client.get(
                WIKIDATA_SPARQL_URL, params=params, headers=headers,
            )
            response.raise_for_status()

        data = response.json()
        entities = []
        seen = set()

        for binding in data.get("results", {}).get("bindings", []):
            name = binding.get("companyLabel", {}).get("value", "")
            if not name or name in seen:
                continue
            seen.add(name)

            country = binding.get("countryLabel", {}).get("value", "")
            parent = binding.get("parentLabel", {}).get("value", "")
            is_state = bool(binding.get("ownerType"))

            entities.append(CorporateEntity(
                name=name,
                country=country,
                parent_name=parent if parent else None,
                is_state_owned=is_state,
                source="wikidata",
            ))

        logger.info("Fetched %d defense companies from Wikidata", len(entities))
        return entities

    async def search_opencorporates(self, company_name: str) -> dict | None:
        """Search OpenCorporates for basic company info (free tier: 50/day)."""
        params = {"q": company_name}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(OPENCORPORATES_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPError as e:
                logger.warning("OpenCorporates search failed for %s: %s", company_name, e)
                return None

        data = response.json()
        companies = data.get("results", {}).get("companies", [])
        if not companies:
            return None

        top = companies[0].get("company", {})
        return {
            "name": top.get("name", ""),
            "jurisdiction": top.get("jurisdiction_code", ""),
            "status": top.get("current_status", ""),
            "registered_address": top.get("registered_address_in_full", ""),
        }
