"""Natural Resources Canada — Cobalt Facts page scraper.

Extracts Canadian cobalt production, exports, and import data from
the NRCan minerals facts page. Critical context for a DND platform.
"""
from __future__ import annotations

import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours

def _cache_get(store: dict, key: str) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None

def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


class NRCanCobaltClient:
    """Scrapes Canadian cobalt statistics from NRCan minerals facts page.

    Source: https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis/minerals-metals-facts/cobalt-facts
    No auth required. Updated annually by NRCan.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_canada_cobalt_stats(self) -> dict:
        """Return Canadian cobalt production, exports, and context.

        Returns dict with production_tonnes, exports_value_cad,
        provinces, world_rank, and source metadata.
        """
        cached = _cache_get(self._cache, "nrcan_cobalt")
        if cached is not None:
            return cached

        url = "https://natural-resources.canada.ca/minerals-mining/mining-data-statistics-analysis/minerals-metals-facts/cobalt-facts"

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    logger.warning("NRCan cobalt page returned HTTP %s", resp.status_code)
                    return self._fallback_data()

                html = resp.text
                result = self._parse_facts_page(html)
                _cache_set(self._cache, "nrcan_cobalt", result)
                return result

        except Exception as e:
            logger.warning("NRCan cobalt fetch failed: %s", e)
            return self._fallback_data()

    def _parse_facts_page(self, html: str) -> dict:
        """Extract key statistics from the NRCan cobalt facts HTML."""
        result = self._fallback_data()
        result["source"] = "NRCan Cobalt Facts (live)"

        # Try to extract production figure
        # NRCan typically shows: "In 2024, Canadian mines produced X,XXX tonnes of cobalt"
        prod_match = re.search(
            r'(?:produced|production)[^0-9]*?([\d,]+)\s*(?:tonnes|t)\s*(?:of\s+)?cobalt',
            html, re.IGNORECASE
        )
        if prod_match:
            result["production_tonnes"] = int(prod_match.group(1).replace(",", ""))

        # Try to extract export value
        # NRCan shows: "$XXX million" for exports
        export_match = re.search(
            r'export[^$]*?\$\s*([\d,.]+)\s*(million|billion)',
            html, re.IGNORECASE
        )
        if export_match:
            value = float(export_match.group(1).replace(",", ""))
            if "billion" in export_match.group(2).lower():
                value *= 1000
            result["exports_value_cad_millions"] = round(value)

        # Try to extract world rank
        rank_match = re.search(
            r'(\d+)(?:th|st|nd|rd)[- ]largest\s+(?:producer|cobalt)',
            html, re.IGNORECASE
        )
        if rank_match:
            result["world_rank"] = int(rank_match.group(1))

        return result

    def _fallback_data(self) -> dict:
        """NRCan 2024 cobalt data (from NRCan website, manually seeded)."""
        return {
            "production_tonnes": 3351,
            "production_year": 2024,
            "exports_value_cad_millions": 344,
            "world_rank": 6,
            "provinces": [
                {"name": "Quebec", "share_pct": 35, "note": "Raglan Mine (Glencore)"},
                {"name": "Ontario", "share_pct": 33, "note": "Sudbury Basin (Vale, Glencore)"},
                {"name": "Newfoundland and Labrador", "share_pct": 28, "note": "Voisey's Bay / Long Harbour (Vale)"},
                {"name": "Manitoba", "share_pct": 4, "note": "Thompson (Vale)"},
            ],
            "key_producers": [
                {"company": "Vale Base Metals", "sites": ["Voisey's Bay", "Sudbury", "Long Harbour", "Thompson"]},
                {"company": "Glencore", "sites": ["Raglan Mine", "Sudbury"]},
                {"company": "Sherritt International", "sites": ["Fort Saskatchewan (refining only, Cuban feed)"]},
            ],
            "notes": [
                "Canada is the world's 6th-largest cobalt producer",
                "Sherritt Fort Saskatchewan is the only non-Chinese vertically integrated cobalt refinery",
                "Moa JV (Cuba) operations paused Feb 2026 due to Cuban fuel crisis",
            ],
            "source": "NRCan Cobalt Facts 2024 (fallback)",
        }
