"""British Geological Survey — World Mineral Statistics OGC API.

Provides country-level cobalt production data from 1970-2023.
Free JSON API, no authentication required. Used as triangulation
source alongside USGS data to improve Glass Box confidence scores.
"""
from __future__ import annotations

import logging
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


class BGSCobaltClient:
    """Fetches cobalt production data from BGS OGC API Features endpoint.

    Endpoint: https://ogcapi.bgs.ac.uk/collections/world-mineral-statistics/items
    Query: commodity=Cobalt, statistic_type=Mine production
    Returns country-level cobalt mine production by year.
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_cobalt_production(self) -> list[dict]:
        """Return world cobalt mine production by country and year.

        Returns list of {country, year, production_tonnes, source}
        """
        cached = _cache_get(self._cache, "bgs_cobalt")
        if cached is not None:
            return cached

        url = "https://ogcapi.bgs.ac.uk/collections/world-mineral-statistics/items"
        params = {
            "commodity": "Cobalt",
            "statistic_type": "Mine production",
            "limit": 1000,
            "f": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning("BGS OGC API returned HTTP %s", resp.status_code)
                    return self._fallback_data()

                data = resp.json()
                features = data.get("features", [])
                if not features:
                    logger.warning("BGS OGC API returned no features")
                    return self._fallback_data()

                results = []
                for f in features:
                    props = f.get("properties", {})
                    country = props.get("country", "")
                    year = props.get("year")
                    quantity = props.get("quantity")
                    unit = props.get("unit", "")

                    if country and year and quantity is not None:
                        # Normalize to tonnes
                        tonnes = float(quantity)
                        if "kilogram" in unit.lower():
                            tonnes = tonnes / 1000

                        results.append({
                            "country": country,
                            "year": int(year),
                            "production_tonnes": round(tonnes),
                            "unit_raw": unit,
                            "source": "BGS World Mineral Statistics",
                        })

                results.sort(key=lambda x: (-x["year"], x["country"]))
                logger.info("BGS: fetched %d cobalt production records", len(results))
                _cache_set(self._cache, "bgs_cobalt", results)
                return results

        except Exception as e:
            logger.warning("BGS cobalt fetch failed: %s", e)
            return self._fallback_data()

    def _fallback_data(self) -> list[dict]:
        """BGS cobalt production fallback (2022 data from BGS website)."""
        data = [
            {"country": "Congo (Kinshasa)", "year": 2022, "production_tonnes": 130000},
            {"country": "Indonesia", "year": 2022, "production_tonnes": 10000},
            {"country": "Russia", "year": 2022, "production_tonnes": 8900},
            {"country": "Australia", "year": 2022, "production_tonnes": 5900},
            {"country": "Philippines", "year": 2022, "production_tonnes": 4800},
            {"country": "Canada", "year": 2022, "production_tonnes": 3900},
            {"country": "Cuba", "year": 2022, "production_tonnes": 3800},
            {"country": "Madagascar", "year": 2022, "production_tonnes": 2800},
            {"country": "Papua New Guinea", "year": 2022, "production_tonnes": 3100},
            {"country": "China", "year": 2022, "production_tonnes": 2200},
            {"country": "Finland", "year": 2022, "production_tonnes": 2100},
            {"country": "Morocco", "year": 2022, "production_tonnes": 2300},
        ]
        for d in data:
            d["source"] = "BGS World Mineral Statistics (fallback)"
        _cache_set(self._cache, "bgs_cobalt", data)
        return data

    async def get_latest_year(self) -> dict:
        """Return production data for the most recent year only."""
        all_data = await self.fetch_cobalt_production()
        if not all_data:
            return {"year": None, "countries": []}
        latest_year = max(d["year"] for d in all_data)
        return {
            "year": latest_year,
            "countries": [d for d in all_data if d["year"] == latest_year],
        }
