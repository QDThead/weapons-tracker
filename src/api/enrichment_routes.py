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


@router.get("/commodities")
async def get_commodity_prices():
    """FRED commodity prices for defence-critical materials (nickel, aluminum, copper, oil, uranium, iron ore, tin)."""
    cached = _check("commodities")
    if cached:
        return cached

    from src.ingestion.osint_feeds import FREDCommodityClient
    try:
        client = FREDCommodityClient()
        result = await client.fetch_commodity_prices()
        _cache["commodities"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("FRED commodity fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/cyber-threats")
async def get_cyber_threats():
    """CISA Known Exploited Vulnerabilities relevant to defence (Cisco, Microsoft, Fortinet, Palo Alto, etc.)."""
    cached = _check("cisa_kev")
    if cached:
        return cached

    from src.ingestion.osint_feeds import CISAKevClient
    try:
        client = CISAKevClient()
        vulns = await client.fetch_kev_catalog()
        result = {
            "source": "CISA Known Exploited Vulnerabilities Catalog",
            "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            "defence_relevant_vendors": ["Cisco", "Microsoft", "Fortinet", "Palo Alto", "F5", "VMware", "Citrix", "Adobe", "Apple", "SAP"],
            "total": len(vulns),
            "vulnerabilities": vulns,
        }
        _cache["cisa_kev"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("CISA KEV fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/disasters")
async def get_active_disasters():
    """GDACS active disaster alerts (Orange/Red level) — earthquakes, tropical cyclones, floods, volcanoes."""
    cached = _check("gdacs_disasters")
    if cached:
        return cached

    from src.ingestion.osint_feeds import GDACSDisasterClient
    try:
        client = GDACSDisasterClient()
        events = await client.fetch_active_disasters()
        result = {
            "source": "GDACS Global Disaster Alert and Coordination System",
            "url": "https://www.gdacs.org",
            "alert_levels": ["Orange", "Red"],
            "event_types": ["EQ (Earthquake)", "TC (Tropical Cyclone)", "FL (Flood)", "VO (Volcano)"],
            "window_days": 30,
            "total": len(events),
            "events": events,
        }
        _cache["gdacs_disasters"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("GDACS disasters fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/satellites")
async def get_military_satellites():
    """Celestrak military satellite tracking data — orbital elements for all tracked military satellites."""
    cached = _check("celestrak_sats")
    if cached:
        return cached

    from src.ingestion.osint_feeds import CelestrakSatelliteClient
    try:
        client = CelestrakSatelliteClient()
        sats = await client.fetch_military_satellites()
        result = {
            "source": "Celestrak (celestrak.org) — NORAD military group",
            "url": "https://celestrak.org/NORAD/elements/gp.php?GROUP=military",
            "total": len(sats),
            "satellites": sats,
        }
        _cache["celestrak_sats"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("Celestrak satellites fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/missiles")
async def get_missile_data():
    """CSIS missile threat and defense system database — missiles and counter-systems by country."""
    cached = _check("csis_missiles")
    if cached:
        return cached

    from src.ingestion.osint_feeds import CSISMissileClient
    try:
        client = CSISMissileClient()
        result = await client.fetch_missile_data()
        _cache["csis_missiles"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("CSIS missiles fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/un-sanctions")
async def get_un_sanctions():
    """UN Security Council Consolidated Sanctions List — individuals and entities."""
    cached = _check("un_sanctions")
    if cached:
        return cached

    from src.ingestion.osint_feeds import UNSanctionsClient
    try:
        client = UNSanctionsClient()
        entries = await client.fetch_un_sanctions()
        result = {
            "source": "UN Security Council Consolidated Sanctions List",
            "url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
            "note": "200 most recently listed entries. Full list available at the UN source URL.",
            "total": len(entries),
            "entries": entries,
        }
        _cache["un_sanctions"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("UN Sanctions fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/earthquakes")
async def get_earthquakes():
    """USGS significant earthquakes (M5+, last 30 days)."""
    cached = _check("usgs_earthquakes")
    if cached:
        return cached

    from src.ingestion.osint_feeds import USGSEarthquakeClient
    try:
        client = USGSEarthquakeClient()
        quakes = await client.fetch_recent_earthquakes()
        result = {
            "source": "USGS Earthquake Hazards Program",
            "url": "https://earthquake.usgs.gov/fdsnws/event/1/",
            "filter": "Magnitude >= 5.0, last 30 days",
            "total": len(quakes),
            "earthquakes": quakes,
        }
        _cache["usgs_earthquakes"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("USGS Earthquake fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/threat-groups")
async def get_threat_groups():
    """MITRE ATT&CK threat groups (APT actors) — top 50 intrusion sets with attribution."""
    cached = _check("mitre_attack")
    if cached:
        return cached

    from src.ingestion.osint_feeds import MITREAttackClient
    try:
        client = MITREAttackClient()
        groups = await client.fetch_threat_groups()
        result = {
            "source": "MITRE ATT&CK Enterprise (STIX 2.1)",
            "url": "https://attack.mitre.org/groups/",
            "note": "Top 50 intrusion sets; attribution is heuristic based on description text.",
            "total": len(groups),
            "threat_groups": groups,
        }
        _cache["mitre_attack"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("MITRE ATT&CK fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/economic-outlook")
async def get_economic_outlook():
    """IMF World Economic Outlook GDP growth projections for 30 defence-relevant countries."""
    cached = _check("imf_weo")
    if cached:
        return cached

    from src.ingestion.osint_feeds import IMFEconomicClient
    try:
        client = IMFEconomicClient()
        result = await client.fetch_gdp_forecasts()
        result["source"] = "IMF World Economic Outlook Datamapper"
        result["url"] = "https://www.imf.org/external/datamapper/api/v1/NGDP_RPCH"
        result["indicator_name"] = "Real GDP Growth (annual % change)"
        result["periods"] = ["2024", "2025", "2026"]
        _cache["imf_weo"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("IMF WEO fetch failed: %s", e)
        return {"error": str(e)}


@router.get("/natural-events")
async def get_natural_events():
    """NASA EONET active natural events (wildfires, storms, volcanoes, sea/lake ice)."""
    cached = _check("nasa_eonet")
    if cached:
        return cached

    from src.ingestion.osint_feeds import NASAEONETClient
    try:
        client = NASAEONETClient()
        events = await client.fetch_active_events()
        result = {
            "source": "NASA Earth Observatory Natural Event Tracker (EONET)",
            "url": "https://eonet.gsfc.nasa.gov/api/v3/events",
            "filter": "Status: open, limit 20",
            "total": len(events),
            "events": events,
        }
        _cache["nasa_eonet"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("NASA EONET fetch failed: %s", e)
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
            {
                "name": "FRED Commodity Prices",
                "endpoint": "/enrichment/commodities",
                "indicators": 7,
                "freshness": "Monthly/Daily",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "CISA Known Exploited Vulnerabilities",
                "endpoint": "/enrichment/cyber-threats",
                "indicators": 7,
                "freshness": "Ongoing (CISA updates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "GDACS Disaster Alerts",
                "endpoint": "/enrichment/disasters",
                "indicators": 8,
                "freshness": "Near real-time",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Celestrak Military Satellites",
                "endpoint": "/enrichment/satellites",
                "indicators": 5,
                "freshness": "Daily (TLE updates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "CSIS Missile Threat Database",
                "endpoint": "/enrichment/missiles",
                "indicators": 5,
                "freshness": "Weekly",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "UN Security Council Consolidated Sanctions List",
                "endpoint": "/enrichment/un-sanctions",
                "indicators": 6,
                "freshness": "Near real-time (UN updates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "USGS Significant Earthquakes (M5+)",
                "endpoint": "/enrichment/earthquakes",
                "indicators": 8,
                "freshness": "Near real-time",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "MITRE ATT&CK Threat Groups",
                "endpoint": "/enrichment/threat-groups",
                "indicators": 6,
                "freshness": "Monthly (CTI repo updates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "IMF World Economic Outlook (GDP Projections)",
                "endpoint": "/enrichment/economic-outlook",
                "indicators": 3,
                "freshness": "Biannual (IMF WEO releases)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "NASA EONET Active Natural Events",
                "endpoint": "/enrichment/natural-events",
                "indicators": 6,
                "freshness": "Near real-time",
                "auth": "None required",
                "status": "active",
            },
        ],
        "total_sources": 29,
        "total_active": 29,
    }
