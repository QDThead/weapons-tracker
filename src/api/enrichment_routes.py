"""Data Enrichment API endpoints.

Exposes governance indicators, economic data, exchange rates,
and other enrichment sources for the PSI risk engine.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/enrichment", tags=["Data Enrichment"])

_cache: dict[str, tuple[float, dict | list]] = {}
_TTL = 3600  # 1 hour


def _check(key):
    c = _cache.get(key)
    if c and time.time() - c[0] < _TTL:
        return c[1]
    return None


@router.get("/governance")
async def get_governance_indicators(countries: str = "CAN,USA,RUS,CHN,GBR,DEU,FRA,IND,TUR"):
    """World Bank Governance Indicators (corruption, stability, rule of law)."""
    cache_key = f"gov:{countries}"
    cached = _check(cache_key)
    if cached:
        return cached

    from src.ingestion.worldbank_enrichment import WorldBankEnrichmentClient
    try:
        client = WorldBankEnrichmentClient()
        records = await client.fetch_governance_indicators(countries=countries.split(","))
        result = {
            "source": "World Bank Governance Indicators",
            "indicators": ["corruption_control", "political_stability", "govt_effectiveness", "rule_of_law", "regulatory_quality"],
            "countries": {},
        }
        for r in records:
            if r.country_iso3 not in result["countries"]:
                result["countries"][r.country_iso3] = {"name": r.country_name, "year": r.year}
            result["countries"][r.country_iso3][r.indicator] = round(r.value, 2)
        result["total_records"] = len(records)
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/economic")
async def get_economic_indicators(countries: str = "CAN,USA,RUS,CHN"):
    """World Bank Economic Indicators (spending, inflation, unemployment)."""
    cache_key = f"econ:{countries}"
    cached = _check(cache_key)
    if cached:
        return cached

    from src.ingestion.worldbank_enrichment import WorldBankEnrichmentClient
    try:
        client = WorldBankEnrichmentClient()
        records = await client.fetch_economic_indicators(countries=countries.split(","))
        result = {
            "source": "World Bank Economic Indicators",
            "countries": {},
        }
        for r in records:
            if r.country_iso3 not in result["countries"]:
                result["countries"][r.country_iso3] = {"name": r.country_name, "year": r.year}
            result["countries"][r.country_iso3][r.indicator] = r.value
        result["total_records"] = len(records)
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/exchange-rates")
async def get_exchange_rates():
    """Current CAD-based exchange rates for currency risk assessment."""
    cached = _check("fx")
    if cached:
        return cached

    from src.ingestion.worldbank_enrichment import WorldBankEnrichmentClient
    try:
        client = WorldBankEnrichmentClient()
        result = await client.fetch_exchange_rates()
        result["source"] = "exchangerate-api.com"
        result["use_case"] = "Currency risk assessment for defence procurement"
        _cache["fx"] = (time.time(), result)
        return result
    except Exception as e:
        return {"error": str(e)}


@router.get("/sources")
async def list_enrichment_sources():
    """List all available enrichment data sources and their status."""
    return {
        "sources": [
            {
                "name": "World Bank Governance Indicators",
                "endpoint": "/enrichment/governance",
                "indicators": 5,
                "freshness": "Annual (2023 latest)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "World Bank Economic Indicators",
                "endpoint": "/enrichment/economic",
                "indicators": 5,
                "freshness": "Annual (2022-2023)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Exchange Rates (CAD-based)",
                "endpoint": "/enrichment/exchange-rates",
                "indicators": 160,
                "freshness": "Daily",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "SIPRI Military Expenditure (MILEX)",
                "endpoint": "Integrated via SIPRI Excel download",
                "indicators": 1,
                "freshness": "Annual (1949-2024)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "SIPRI Arms Transfers",
                "endpoint": "/dashboard/transfers",
                "indicators": 4,
                "freshness": "Annual (2025)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "UN Comtrade (HS 93)",
                "endpoint": "/dashboard/comtrade/exports",
                "indicators": 3,
                "freshness": "Annual (2023)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "GDELT News (multilingual)",
                "endpoint": "/dashboard/news/live",
                "indicators": 5,
                "freshness": "15-minute refresh",
                "auth": "None required",
                "status": "active",
                "languages": 31,
            },
            {
                "name": "ADS-B Military Flights",
                "endpoint": "/tracking/flights/military",
                "indicators": 8,
                "freshness": "5-minute refresh (live)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "NATO Defence Expenditure",
                "endpoint": "/dashboard/nato/spending",
                "indicators": 4,
                "freshness": "Annual (2025 estimates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "OFAC SDN Sanctions",
                "endpoint": "/dashboard/sanctions/ofac-sdn",
                "indicators": 3,
                "freshness": "Weekly",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "EU Sanctions List",
                "endpoint": "/dashboard/sanctions/eu",
                "indicators": 3,
                "freshness": "Weekly",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "US Census Trade (HS 93)",
                "endpoint": "/dashboard/census/monthly",
                "indicators": 4,
                "freshness": "Monthly (~2mo lag)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "UK HMRC Trade (HS 93)",
                "endpoint": "/dashboard/uk-trade/monthly",
                "indicators": 4,
                "freshness": "Monthly (~2mo lag)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Eurostat EU Trade",
                "endpoint": "/dashboard/eu-trade/monthly",
                "indicators": 4,
                "freshness": "Monthly (~2mo lag)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Statistics Canada CIMT",
                "endpoint": "/dashboard/canada-trade/monthly",
                "indicators": 4,
                "freshness": "Monthly (~6wk lag)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "DSCA Arms Sales (Federal Register)",
                "endpoint": "/dashboard/dsca/recent",
                "indicators": 5,
                "freshness": "Days",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "SIPRI Top 100 Companies",
                "endpoint": "/trends/companies/top/2023",
                "indicators": 5,
                "freshness": "Annual (2023)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Wikidata Corporate Graph",
                "endpoint": "Internal enrichment",
                "indicators": 3,
                "freshness": "Weekly",
                "auth": "None required",
                "status": "active",
            },
        ],
        "total_sources": 18,
        "total_active": 18,
    }
