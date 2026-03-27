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


@router.get("/milex")
async def get_milex(countries: str = ""):
    """SIPRI Military Expenditure data (1949-2024) — summary for key countries, latest 5 years."""
    cache_key = f"milex:{countries}"
    cached = _check(cache_key)
    if cached:
        return cached

    from src.ingestion.sipri_milex import SIPRIMilexClient

    # SIPRI labels some countries differently from common names
    KEY_COUNTRIES = {
        "Canada", "United States", "United States of America", "China", "Russia",
        "Germany", "United Kingdom", "France", "India", "Turkey", "Türkiye",
        "Australia", "Japan", "South Korea", "Korea, South", "Israel", "Iran",
        "Saudi Arabia", "Norway", "Sweden", "Finland", "Poland", "Ukraine",
    }

    filter_set = set(c.strip() for c in countries.split(",") if c.strip()) if countries else KEY_COUNTRIES

    try:
        client = SIPRIMilexClient()
        all_records = await client.fetch_milex_data()

        # Find latest 5 years across all data
        all_years = sorted({r.year for r in all_records}, reverse=True)
        recent_years = all_years[:5]

        summary: dict[str, dict] = {}
        for r in all_records:
            if r.country_name not in filter_set:
                continue
            if r.year not in recent_years:
                continue
            if r.country_name not in summary:
                summary[r.country_name] = {
                    "country": r.country_name,
                    "iso3": r.country_iso3,
                    "spending_usd_millions": {},
                    "spending_pct_gdp": {},
                }
            summary[r.country_name]["spending_usd_millions"][r.year] = round(r.spending_usd, 1)
            if r.spending_pct_gdp is not None:
                summary[r.country_name]["spending_pct_gdp"][r.year] = round(r.spending_pct_gdp, 2)

        result = {
            "source": "SIPRI Military Expenditure Database",
            "coverage": "1949-2024",
            "years_shown": sorted(recent_years),
            "unit": "Current USD millions",
            "countries": list(summary.values()),
            "total_countries": len(summary),
            "total_records_parsed": len(all_records),
        }
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.exception("SIPRI MILEX fetch failed")
        return {"error": str(e)}


@router.get("/factbook")
async def get_factbook_military():
    """CIA World Factbook military data for 20 key nations."""
    cached = _check("factbook")
    if cached:
        return cached

    from src.ingestion.cia_factbook import CIAFactbookClient

    try:
        client = CIAFactbookClient()
        records = await client.fetch_military_data()

        countries = []
        for r in records:
            countries.append({
                "country": r.country_name,
                "iso3": r.country_iso3,
                "fips_code": r.fips_code,
                "military_branches": r.military_branches[:500] if r.military_branches else None,
                "military_personnel": r.military_personnel,
                "military_expenditure_pct_gdp": r.military_expenditure_pct_gdp,
                "expenditure_history": {
                    str(y): v for y, v in sorted(r.military_expenditure_history.items(), reverse=True)
                },
                "military_note": r.military_note[:300] if r.military_note else None,
                "deployments": r.military_deployments[:300] if r.military_deployments else None,
            })

        result = {
            "source": "CIA World Factbook (factbook.json mirror)",
            "url": "https://github.com/factbook/factbook.json",
            "total_countries": len(countries),
            "countries": countries,
        }
        _cache["factbook"] = (time.time(), result)
        return result
    except Exception as e:
        logger.exception("CIA Factbook fetch failed")
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
                "endpoint": "/enrichment/milex",
                "indicators": 2,
                "freshness": "Annual (1949-2024)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "CIA World Factbook — Military Data",
                "endpoint": "/enrichment/factbook",
                "indicators": 4,
                "freshness": "Weekly",
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
        "total_sources": 20,
        "total_active": 20,
    }
