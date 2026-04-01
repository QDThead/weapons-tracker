"""Data Enrichment API endpoints.

Exposes governance indicators, economic data, exchange rates,
and other enrichment sources for the PSI risk engine.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException

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
        logger.error("Governance indicators fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("Economic indicators fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("Exchange rates fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("FRED commodity fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("CISA KEV fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("GDACS disasters fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("Celestrak satellites fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("CSIS missiles fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("UN Sanctions fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("USGS Earthquake fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("MITRE ATT&CK fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("IMF WEO fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.error("NASA EONET fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/chokepoints-traffic")
async def get_chokepoints_traffic():
    """IMF PortWatch maritime chokepoint vessel traffic — 10 most strategic global chokepoints."""
    cached = _check("portwatch_chokepoints")
    if cached:
        return cached

    from src.ingestion.osint_feeds import PortWatchClient
    try:
        client = PortWatchClient()
        chokepoints = await client.fetch_chokepoint_traffic()
        result = {
            "source": "IMF PortWatch via OCHA Humanitarian Data Exchange (HDX)",
            "url": "https://data.humdata.org/dataset/957b1c2f-a9b9-436c-a576-f7f3ddb9d736",
            "note": "10 most strategically important maritime chokepoints. Vessel counts are annual estimates.",
            "total": len(chokepoints),
            "chokepoints": chokepoints,
        }
        _cache["portwatch_chokepoints"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("PortWatch chokepoint fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/arctic-aircraft")
async def get_arctic_aircraft():
    """OpenSky Network real-time aircraft positions over the Arctic (lat > 55N)."""
    cached = _check("opensky_arctic")
    if cached:
        return cached

    from src.ingestion.osint_feeds import OpenSkyClient
    try:
        client = OpenSkyClient()
        aircraft = await client.fetch_arctic_aircraft()
        result = {
            "source": "OpenSky Network (opensky-network.org)",
            "url": "https://opensky-network.org/api/states/all",
            "filter": "Latitude 55N–90N (Arctic region), anonymous access",
            "note": "Complements adsb.lol data. Rate-limited to ~10 req/min for anonymous users.",
            "total": len(aircraft),
            "aircraft": aircraft,
        }
        _cache["opensky_arctic"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("OpenSky Arctic aircraft fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/displacement")
async def get_displacement():
    """UNHCR refugee and displacement statistics — top displacement situations 2022-2023."""
    cached = _check("unhcr_displacement")
    if cached:
        return cached

    from src.ingestion.osint_feeds import UNHCRClient
    try:
        client = UNHCRClient()
        records = await client.fetch_displacement_data()
        result = {
            "source": "UNHCR Population Statistics API",
            "url": "https://api.unhcr.org/population/v1/population/",
            "coverage": "2022–2023",
            "note": "Top 50 displacement situations by total displaced. Conflict-driven displacement "
                    "is a key indicator of armed conflict intensity.",
            "total": len(records),
            "displacement": records,
        }
        _cache["unhcr_displacement"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("UNHCR displacement fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/space-launches")
async def get_space_launches():
    """Recent space launches — country, rocket, mission type (The Space Devs)."""
    cached = _check("space_launches")
    if cached:
        return cached

    from src.ingestion.osint_feeds import SpaceLaunchClient
    try:
        client = SpaceLaunchClient()
        launches = await client.fetch_recent_launches()
        result = {
            "source": "The Space Devs — Launch Library 2",
            "url": "https://ll.thespacedevs.com/2.3.0/launches/",
            "note": "20 most recent launches. Military/dual-use launches are key indicators of "
                    "ISR, ASAT, and hypersonic capability development.",
            "total": len(launches),
            "launches": launches,
        }
        _cache["space_launches"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Space Devs launch fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/submarine-cables")
async def get_submarine_cables():
    """TeleGeography submarine cable infrastructure — global cable systems with owners and landing points."""
    cached = _check("submarine_cables")
    if cached:
        return cached

    from src.ingestion.osint_feeds import SubmarineCableClient
    try:
        client = SubmarineCableClient()
        cables = await client.fetch_submarine_cables()
        result = {
            "source": "TeleGeography Submarine Cable Map",
            "url": "https://www.submarinecablemap.com/api/v3/cable/all.json",
            "note": "Submarine cables carry ~95% of international internet traffic. Sabotage events "
                    "(e.g., Baltic Sea 2024) are a key grey-zone warfare vector.",
            "total": len(cables),
            "cables": cables,
        }
        _cache["submarine_cables"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Submarine cable fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/internet-infrastructure")
async def get_internet_infrastructure():
    """RIPE Stat internet infrastructure monitoring — ASN and prefix counts for key countries."""
    cached = _check("ripe_internet")
    if cached:
        return cached

    from src.ingestion.osint_feeds import RIPEInternetClient
    try:
        client = RIPEInternetClient()
        result = await client.fetch_internet_infrastructure()
        result["note"] = (
            "Internet infrastructure metrics (ASN counts, routed prefixes) are indicators of "
            "cyber domain resilience and internet shutdown risk during conflict escalation."
        )
        _cache["ripe_internet"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("RIPE Stat fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/dod-contracts")
async def get_dod_contracts():
    """US DoD procurement contracts from USASpending.gov — top 20 by award amount."""
    cached = _check("dod_contracts")
    if cached:
        return cached

    from src.ingestion.osint_feeds import USASpendingClient
    try:
        client = USASpendingClient()
        contracts = await client.fetch_dod_contracts()
        result = {
            "source": "USASpending.gov — US Federal Spending",
            "url": "https://api.usaspending.gov/api/v2/search/spending_by_award/",
            "filter": "DoD awards, 2025-2026, keywords: defense/military/weapons",
            "note": "Top 20 DoD contracts by award amount. Key indicator of defence industrial base activity.",
            "total": len(contracts),
            "contracts": contracts,
        }
        _cache["dod_contracts"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("USASpending DoD contracts fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/mineral-deposits")
async def get_mineral_deposits():
    """USGS critical mineral deposit locations — lithium, cobalt, titanium, rare earth, tungsten."""
    cached = _check("usgs_mineral_deposits")
    if cached:
        return cached

    from src.ingestion.osint_feeds import USGSMineralClient
    try:
        client = USGSMineralClient()
        result = await client.fetch_mineral_deposits()
        result["source"] = "USGS Mineral Resources Data System (MRDS)"
        result["url"] = "https://mrdata.usgs.gov/services/mrds"
        result["note"] = (
            "Georeferenced critical mineral deposit locations. "
            "These minerals are essential inputs for advanced weapons platforms, "
            "electronics, and propulsion systems."
        )
        _cache["usgs_mineral_deposits"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("USGS Mineral deposits fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/conflict-deaths")
async def get_conflict_deaths():
    """World Bank battle-related deaths indicator (VC.BTL.DETH) — 2020–2023."""
    cached = _check("wb_conflict_deaths")
    if cached:
        return cached

    from src.ingestion.osint_feeds import WorldBankConflictClient
    try:
        client = WorldBankConflictClient()
        records = await client.fetch_conflict_deaths()
        result = {
            "source": "World Bank — Battle-Related Deaths (UCDP/PRIO Armed Conflict dataset)",
            "url": "https://api.worldbank.org/v2/country/all/indicator/VC.BTL.DETH",
            "indicator": "VC.BTL.DETH",
            "coverage": "2020–2023",
            "note": "Countries with non-null values only. Tracks battle-related deaths including civilians.",
            "total": len(records),
            "records": records,
        }
        _cache["wb_conflict_deaths"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("World Bank Conflict Deaths fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/us-fiscal")
async def get_us_fiscal():
    """US Treasury daily debt-to-the-penny and 30-day trend."""
    cached = _check("treasury_fiscal")
    # TreasuryFiscalClient uses 1-hour TTL internally; use same here
    if cached:
        return cached

    from src.ingestion.osint_feeds import TreasuryFiscalClient
    try:
        client = TreasuryFiscalClient()
        result = await client.fetch_us_fiscal_data()
        result.setdefault("source", "US Treasury Fiscal Data API")
        result.setdefault("url", "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny")
        result.setdefault("note", (
            "US national debt level and trajectory are macro indicators of defence budget "
            "sustainability and dollar-denominated arms financing capacity. Updated daily."
        ))
        _cache["treasury_fiscal"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Treasury Fiscal fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/defence-research")
async def get_defence_research():
    """OpenAlex academic research trends on defence supply chains and military procurement."""
    cached = _check("openalex_research")
    if cached:
        return cached

    from src.ingestion.osint_feeds import OpenAlexResearchClient
    try:
        client = OpenAlexResearchClient()
        works = await client.fetch_defence_research()
        result = {
            "source": "OpenAlex Open Academic Research Database",
            "url": "https://api.openalex.org/works",
            "query": "defence supply chain military procurement",
            "note": (
                "10 most recent academic publications. Emerging research themes often "
                "precede policy and market movements in the defence sector."
            ),
            "total": len(works),
            "works": works,
        }
        _cache["openalex_research"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("OpenAlex research fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/connectivity")
async def get_connectivity():
    """RIPE Atlas internet connectivity probe status by country — active probe counts."""
    cached = _check("ripe_atlas_connectivity")
    if cached:
        return cached

    from src.ingestion.osint_feeds import RIPEAtlasClient
    try:
        client = RIPEAtlasClient()
        result = await client.fetch_connectivity_status()
        result.setdefault("source", "RIPE Atlas (atlas.ripe.net)")
        result.setdefault("url", "https://atlas.ripe.net/api/v2/probes/")
        result.setdefault("note", (
            "Active RIPE Atlas probe counts per country. Sudden drops indicate internet "
            "shutdowns or major infrastructure disruptions — a grey-zone warfare indicator."
        ))
        _cache["ripe_atlas_connectivity"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("RIPE Atlas connectivity fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/critical-cves")
async def get_critical_cves():
    """NIST NVD latest critical CVEs (CVSS v3 >= 9.0) published in the last 7 days."""
    cached = _check("nvd_critical_cves")
    if cached:
        return cached

    from src.ingestion.osint_feeds import NVDCveClient
    try:
        client = NVDCveClient()
        cves = await client.fetch_critical_cves()
        result = {
            "source": "NIST National Vulnerability Database (NVD)",
            "url": "https://services.nvd.nist.gov/rest/json/cves/2.0",
            "filter": "CVSS v3 CRITICAL severity, last 7 days",
            "cache_ttl": "6 hours",
            "total": len(cves),
            "cves": cves,
        }
        _cache["nvd_critical_cves"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("NVD CVE fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/severe-weather")
async def get_severe_weather():
    """NOAA NWS active Extreme/Severe weather alerts for North America."""
    cached = _check("noaa_severe_weather")
    if cached:
        return cached

    from src.ingestion.osint_feeds import NOAAWeatherClient
    try:
        client = NOAAWeatherClient()
        alerts = await client.fetch_severe_weather()
        result = {
            "source": "NOAA National Weather Service (weather.gov)",
            "url": "https://api.weather.gov/alerts/active",
            "filter": "Status: actual, Severity: Extreme or Severe, limit 20",
            "cache_ttl": "6 hours",
            "total": len(alerts),
            "alerts": alerts,
        }
        _cache["noaa_severe_weather"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("NOAA Weather fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/nuclear-arsenals")
async def get_nuclear_arsenals():
    """FAS nuclear warhead estimates for all 9 nuclear-armed states (2024 figures)."""
    cached = _check("fas_nuclear_arsenals")
    if cached:
        return cached

    from src.ingestion.osint_feeds import FASNuclearClient
    try:
        client = FASNuclearClient()
        arsenals = await client.fetch_nuclear_arsenals()
        total_warheads = sum(a["total_warheads"] for a in arsenals)
        total_deployed = sum(
            a["deployed_strategic"] for a in arsenals if a["deployed_strategic"] is not None
        )
        result = {
            "source": "Federation of American Scientists — Status of World Nuclear Forces",
            "url": "https://fas.org/issues/nuclear-weapons/status-world-nuclear-forces/",
            "as_of": "Latest available (FAS via Our World in Data)",
            "note": "Live data from OWID CSV; falls back to hardcoded 2024 if unavailable.",
            "total_nuclear_states": len(arsenals),
            "global_total_warheads": total_warheads,
            "global_deployed_strategic": total_deployed,
            "arsenals": arsenals,
        }
        _cache["fas_nuclear_arsenals"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("FAS Nuclear fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/armed-forces")
async def get_armed_forces():
    """World Bank military personnel data (MS.MIL.TOTL.P1) for 16 key countries."""
    cached = _check("wb_armed_forces")
    if cached:
        return cached

    from src.ingestion.osint_feeds import WorldBankArmedForcesClient
    try:
        client = WorldBankArmedForcesClient()
        forces = await client.fetch_armed_forces()
        result = {
            "source": "World Bank Open Data — Armed Forces Personnel (MS.MIL.TOTL.P1)",
            "url": "https://data.worldbank.org/indicator/MS.MIL.TOTL.P1",
            "year": 2020,
            "note": "Includes all active duty military. Reserve and paramilitary forces may be excluded.",
            "total_countries": len(forces),
            "countries": forces,
        }
        _cache["wb_armed_forces"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("World Bank Armed Forces fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unroca")
async def get_unroca_transfers():
    """UN Register of Conventional Arms — unit-level weapons transfer data.

    Returns aggregate data for 15 key countries: total heavy-weapon import
    units and SALW export units, top partners, and category breakdowns.
    Data covers 1992–present as reported by UN member states.
    Cached for 24 hours.
    """
    cached = _check("unroca_key")
    if cached:
        return cached

    from src.ingestion.unroca import UNROCAClient
    try:
        client = UNROCAClient()
        result = await client.fetch_key_countries()
        _cache["unroca_key"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("UNROCA key-countries fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unroca/{country}")
async def get_unroca_country(country: str):
    """UNROCA data for a specific country (use slug, e.g. 'canada', 'russian-federation').

    Returns:
      - hw_imports: heavy-weapon transfers received (by partner country & category)
      - salw_exports: small arms / light weapons exported (by destination & category)
      - sa_time_series: yearly small-arms import totals by weapon type (1992–present)
      - lw_time_series: yearly light-weapons import totals by weapon type (1992–present)

    Slugs follow the UNROCA convention — use hyphens for multi-word names,
    e.g. 'united-states-of-america', 'russian-federation', 'republic-of-korea'.
    Cached for 24 hours per country.
    """
    cache_key = f"unroca:{country}"
    cached = _check(cache_key)
    if cached:
        return cached

    from src.ingestion.unroca import UNROCAClient
    try:
        client = UNROCAClient()
        result = await client.fetch_country_transfers(country)
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("UNROCA country fetch failed (%s): %s", country, e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/unroca-countries")
async def get_unroca_country_list():
    """Full list of UNROCA reporting countries with name, slug, and ISO-2 code."""
    cached = _check("unroca_countries")
    if cached:
        return cached

    from src.ingestion.unroca import UNROCAClient
    try:
        client = UNROCAClient()
        countries = await client.fetch_country_list()
        result = {
            "source": "UN Register of Conventional Arms (UNROCA)",
            "url": "https://www.unroca.org/api/country-list/",
            "total": len(countries),
            "countries": countries,
        }
        _cache["unroca_countries"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("UNROCA country list fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")



@router.get("/opensanctions")
async def get_opensanctions():
    """OpenSanctions consolidated sanctions (329 sources, daily updates)."""
    cached = _check("opensanctions")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import OpenSanctionsClient
        client = OpenSanctionsClient()
        data = await client.fetch_sanctions_stats()
        _cache["opensanctions"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch OpenSanctions data")


@router.get("/military-bases")
async def get_military_bases():
    """US DoD military installations worldwide (Data.gov)."""
    cached = _check("military_bases")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import USMilitaryBasesClient
        client = USMilitaryBasesClient()
        data = await client.fetch_bases()
        _cache["military_bases"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch military bases data")


@router.get("/dod-spending")
async def get_dod_spending():
    """US DoD contract spending from USAspending.gov."""
    cached = _check("dod_spending")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import USASpendingDefenceClient
        client = USASpendingDefenceClient()
        data = await client.fetch_dod_spending()
        _cache["dod_spending"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch DoD spending data")


# ── CONFLICT & WAR DATA ──────────────────────────────────────────


@router.get("/conflict/equipment-losses")
async def get_equipment_losses():
    """Russian equipment losses in Ukraine (WarSpotting — photo-verified, geolocated)."""
    cached = _check("warspotting")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import WarSpottingClient
        client = WarSpottingClient()
        data = await client.fetch_recent_losses()
        result = {"source": "WarSpotting.net", "records": len(data), "data": data}
        _cache["warspotting"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch equipment losses")


@router.get("/conflict/russian-casualties")
async def get_russian_casualties():
    """Daily Russian military losses (Ukrainian General Staff claims)."""
    cached = _check("ru_casualties")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import RussianCasualtiesClient
        client = RussianCasualtiesClient()
        data = await client.fetch_daily_losses()
        _cache["ru_casualties"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch Russian casualties")


@router.get("/conflict/fire-detections")
async def get_fire_detections(country: str = "UKR", days: int = 2):
    """NASA FIRMS satellite fire detections for conflict zone monitoring."""
    cache_key = f"firms_{country}_{days}"
    cached = _check(cache_key)
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import NASAFIRMSClient
        client = NASAFIRMSClient()
        data = await client.fetch_conflict_fires(country=country, days=days)
        result = {"source": "NASA FIRMS VIIRS", "country": country, "records": len(data), "data": data[:200]}
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch fire detections")


@router.get("/conflict/gdelt-events")
async def get_gdelt_conflict_events(timespan: str = "24h"):
    """GDELT conflict/military event news (updates every 15 min)."""
    cached = _check(f"gdelt_conflict_{timespan}")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import GDELTConflictClient
        client = GDELTConflictClient()
        data = await client.fetch_conflict_events(timespan=timespan)
        result = {"source": "GDELT DOC 2.0", "records": len(data), "data": data}
        _cache[f"gdelt_conflict_{timespan}"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch GDELT conflict events")


# ── COBALT SUPPLY CHAIN INTELLIGENCE ─────────────────────────────


@router.get("/cobalt/prices")
async def get_cobalt_prices():
    """IMF monthly cobalt spot prices (USD/metric ton)."""
    cached = _check("cobalt_prices")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import IMFCobaltPriceClient
        client = IMFCobaltPriceClient()
        data = await client.fetch_cobalt_prices()
        result = {"source": "IMF PCPS", "records": len(data), "data": data[:60]}
        _cache["cobalt_prices"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch cobalt prices")


@router.get("/cobalt/drc-mines")
async def get_drc_mines():
    """IPIS DRC artisanal mining sites with conflict indicators."""
    cached = _check("drc_mines")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import IPISDRCMinesClient
        client = IPISDRCMinesClient()
        data = await client.fetch_drc_mines()
        result = {"source": "IPIS Research", "records": len(data), "data": data[:50]}
        _cache["drc_mines"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch DRC mine data")


@router.get("/cobalt/production")
async def get_cobalt_production():
    """USGS world cobalt production by country."""
    cached = _check("cobalt_production")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import USGSCobaltDataClient
        client = USGSCobaltDataClient()
        data = await client.fetch_cobalt_production()
        result = {"source": "USGS MCS 2025", "records": len(data), "data": data}
        _cache["cobalt_production"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch cobalt production data")


@router.get("/cobalt/refiners")
async def get_cobalt_refiners():
    """RMI-assessed cobalt refiners with compliance status."""
    cached = _check("cobalt_refiners")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import RMICobaltRefinersClient
        client = RMICobaltRefinersClient()
        data = await client.fetch_refiners()
        result = {"source": "RMI Cobalt Refiners List", "records": len(data), "data": data}
        _cache["cobalt_refiners"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch cobalt refiner data")


@router.get("/cobalt/sec-filings")
async def get_cobalt_sec_filings():
    """SEC EDGAR filings mentioning cobalt/superalloy supply chain risks."""
    cached = _check("cobalt_sec")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import SECEdgarCobaltClient
        client = SECEdgarCobaltClient()
        data = await client.fetch_cobalt_filings()
        result = {"source": "SEC EDGAR", "records": len(data), "data": data}
        _cache["cobalt_sec"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch SEC filings")


@router.get("/cobalt/market")
async def get_cobalt_market():
    """Cobalt Institute market overview (supply, demand, refining concentration)."""
    cached = _check("cobalt_market")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import CobaltInstituteClient
        client = CobaltInstituteClient()
        data = await client.fetch_market_data()
        result = data
        _cache["cobalt_market"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch cobalt market data")


@router.get("/cobalt/cmoc")
async def get_cmoc_production():
    """CMOC Group cobalt production (TFM + Kisanfu mines, 31% global share)."""
    cached = _check("cmoc_production")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import CMOCProductionClient
        client = CMOCProductionClient()
        data = await client.fetch_production()
        result = data
        _cache["cmoc_production"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch CMOC production data")


@router.get("/cobalt/glencore")
async def get_glencore_production():
    """Glencore cobalt production (KCC + Mutanda + Murrin Murrin + Raglan)."""
    cached = _check("glencore_production")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import GlencoreProductionClient
        client = GlencoreProductionClient()
        data = await client.fetch_production()
        result = data
        _cache["glencore_production"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch Glencore production data")


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
            {
                "name": "IMF PortWatch — Maritime Chokepoint Traffic",
                "endpoint": "/enrichment/chokepoints-traffic",
                "indicators": 5,
                "freshness": "Annual (with live HDX fetch)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "OpenSky Network — Arctic Aircraft Tracking",
                "endpoint": "/enrichment/arctic-aircraft",
                "indicators": 7,
                "freshness": "Real-time (rate-limited, 24h cache)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "UNHCR Refugee and Displacement Statistics",
                "endpoint": "/enrichment/displacement",
                "indicators": 5,
                "freshness": "Annual (2022-2023)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Space Devs — Launch Library 2",
                "endpoint": "/enrichment/space-launches",
                "indicators": 7,
                "freshness": "Near real-time (rate-limited, 24h cache)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "TeleGeography Submarine Cable Map",
                "endpoint": "/enrichment/submarine-cables",
                "indicators": 5,
                "freshness": "Ongoing (cable commissioning updates)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "RIPE Stat — Internet Infrastructure",
                "endpoint": "/enrichment/internet-infrastructure",
                "indicators": 3,
                "freshness": "Near real-time",
                "auth": "None required",
                "status": "active",
                "countries": ["RU", "CN", "US", "IR", "KP", "UA", "CA", "GB"],
            },
            {
                "name": "USASpending.gov — DoD Procurement Contracts",
                "endpoint": "/enrichment/dod-contracts",
                "indicators": 6,
                "freshness": "Daily (contract award updates)",
                "auth": "None required",
                "status": "active",
                "filter": "DoD awards 2025-2026, keywords: defense/military/weapons",
            },
            {
                "name": "USGS Mineral Resources Data System (MRDS)",
                "endpoint": "/enrichment/mineral-deposits",
                "indicators": 5,
                "freshness": "Annual (deposit registry updates)",
                "auth": "None required",
                "status": "active",
                "minerals": ["Lithium", "Cobalt", "Titanium", "Rare Earth", "Tungsten"],
            },
            {
                "name": "World Bank — Battle-Related Deaths (VC.BTL.DETH)",
                "endpoint": "/enrichment/conflict-deaths",
                "indicators": 4,
                "freshness": "Annual (2020-2023)",
                "auth": "None required",
                "status": "active",
                "source_dataset": "UCDP/PRIO Armed Conflict dataset",
            },
            {
                "name": "US Treasury Fiscal Data — Debt to the Penny",
                "endpoint": "/enrichment/us-fiscal",
                "indicators": 3,
                "freshness": "Daily (business days)",
                "auth": "None required",
                "status": "active",
                "cache_ttl": "1 hour",
            },
            {
                "name": "OpenAlex — Defence Research Trends",
                "endpoint": "/enrichment/defence-research",
                "indicators": 6,
                "freshness": "Near real-time (academic publication index)",
                "auth": "None required",
                "status": "active",
                "query": "defence supply chain military procurement",
            },
            {
                "name": "RIPE Atlas — Internet Connectivity Probe Status",
                "endpoint": "/enrichment/connectivity",
                "indicators": 2,
                "freshness": "Near real-time (24h cache)",
                "auth": "None required",
                "status": "active",
                "countries": ["US", "RU", "UA", "CN", "IR", "KP", "CA", "GB", "DE", "IL"],
                "classification": ">500=healthy, 100-500=moderate, <100=limited, 0=isolated",
            },
            {
                "name": "NIST National Vulnerability Database — Critical CVEs",
                "endpoint": "/enrichment/critical-cves",
                "indicators": 6,
                "freshness": "Near real-time (6h cache)",
                "auth": "None required",
                "status": "active",
                "filter": "CVSS v3 CRITICAL (>= 9.0), last 7 days",
                "cache_ttl": "6 hours",
            },
            {
                "name": "NOAA NWS — Severe/Extreme Weather Alerts",
                "endpoint": "/enrichment/severe-weather",
                "indicators": 7,
                "freshness": "Near real-time (6h cache)",
                "auth": "None required",
                "status": "active",
                "filter": "Severity: Extreme or Severe, status: actual",
                "cache_ttl": "6 hours",
            },
            {
                "name": "FAS — Nuclear Warhead Estimates (9 States)",
                "endpoint": "/enrichment/nuclear-arsenals",
                "indicators": 5,
                "freshness": "Annual (hardcoded 2024 estimates)",
                "auth": "None required",
                "status": "active",
                "states": ["Russia", "USA", "China", "France", "UK", "Pakistan", "India", "Israel", "North Korea"],
            },
            {
                "name": "World Bank — Armed Forces Personnel (MS.MIL.TOTL.P1)",
                "endpoint": "/enrichment/armed-forces",
                "indicators": 4,
                "freshness": "Annual (2020 data)",
                "auth": "None required",
                "status": "active",
                "countries": 16,
            },
            {
                "name": "UN Register of Conventional Arms (UNROCA)",
                "endpoint": "/enrichment/unroca",
                "indicators": 6,
                "freshness": "Annual (member-state submissions, 1992–present)",
                "auth": "None required",
                "status": "active",
                "note": "Unit-level transfers: battle tanks, combat aircraft, armoured vehicles, artillery, MLRS, helicopters, warships, UAVs, MANPADS, SALW",
                "countries": 15,
                "per_country_endpoint": "/enrichment/unroca/{slug}",
                "country_list_endpoint": "/enrichment/unroca-countries",
            },
            {
                "name": "Tor Project Exit Node List",
                "endpoint": "/cyber/tor-nodes",
                "indicators": 1,
                "freshness": "Live (6h cache)",
                "auth": "None required",
                "status": "active",
                "note": "Current Tor exit node IPs — indicators of anonymized access infrastructure used by threat actors.",
                "source_url": "https://check.torproject.org/torbulkexitlist",
            },
            {
                "name": "APT Threat Actor Registry (Defence DIB)",
                "endpoint": "/cyber/threat-actors",
                "indicators": 7,
                "freshness": "Static (public reporting — updated with major advisories)",
                "auth": "None required",
                "status": "active",
                "note": "13 tracked APT groups: APT28, APT29, APT41, Lazarus, APT33, Turla, APT10, Sandworm, Kimsuky, Charming Kitten, APT1, Cozy Bear, Fancy Bear.",
                "sources": ["MITRE ATT&CK", "Mandiant", "CrowdStrike", "CISA"],
            },
            {
                "name": "Defence Industrial Base Breach Registry",
                "endpoint": "/cyber/breaches",
                "indicators": 5,
                "freshness": "Static (open-source reporting)",
                "auth": "None required",
                "status": "active",
                "note": "13 documented breaches: SolarWinds, MS Exchange ProxyLogon, Boeing LockBit, MOVEit, Lockheed Martin, BAE Systems, MBDA, and others.",
                "sources": ["Reuters", "CyberScoop", "CISA advisories", "company disclosures"],
            },
            {
                "name": "Cyber IOC Aggregated Summary",
                "endpoint": "/cyber/ioc-summary",
                "indicators": 8,
                "freshness": "6-hour cache (Tor live; others estimated from public dashboards)",
                "auth": "None required",
                "status": "active",
                "note": "Combines Tor exit count, CISA KEV estimate, NVD critical CVE estimate, and MITRE ATT&CK group metrics.",
            },
            {
                "name": "Canadian Defence Supplier Cyber Risk Assessment",
                "endpoint": "/cyber/supplier-risk",
                "indicators": 6,
                "freshness": "Static (updated with major breach events)",
                "auth": "None required",
                "status": "active",
                "note": "14 Canadian DIB suppliers assessed by sector sensitivity, foreign ownership, breach history, and active APT targeting.",
                "suppliers": 14,
            },
            {
                "name": "Unified Cyber Threat Report",
                "endpoint": "/cyber/report",
                "indicators": 10,
                "freshness": "6-hour cache (aggregated)",
                "auth": "None required",
                "status": "active",
                "note": "Full threat picture: overall level, executive summary, IOC summary, APT actors, breach indicators, supplier risk top-5.",
            },
            {
                "name": "GC Defence News (DND/GAC/Public Safety)",
                "endpoint": "/enrichment/gc-defence-news",
                "indicators": 5,
                "freshness": "30-minute refresh (4 Atom feeds)",
                "auth": "None required",
                "status": "active",
                "feeds": ["DND", "GAC", "Defence & Security", "Public Safety"],
            },
            {
                "name": "NATO News RSS",
                "endpoint": "/enrichment/nato-news",
                "indicators": 5,
                "freshness": "1-hour refresh",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "NORAD Press Releases",
                "endpoint": "/enrichment/norad-news",
                "indicators": 5,
                "freshness": "6-hour refresh (Arctic intercepts, exercises)",
                "auth": "None required",
                "status": "active",
            },
            {
                "name": "Canadian Sanctions (GAC SEMA/JVCFOA)",
                "endpoint": "/enrichment/canadian-sanctions",
                "indicators": 6,
                "freshness": "Daily (updated as sanctions change)",
                "auth": "None required",
                "status": "active",
                "note": "Canada's autonomous sanctions under SEMA + JVCFOA (Magnitsky), separate from OFAC/EU.",
            },
            {
                "name": "Arctic OSINT News (3 sources)",
                "endpoint": "/enrichment/arctic-osint",
                "indicators": 6,
                "freshness": "2-hour refresh",
                "auth": "None required",
                "status": "active",
                "feeds": ["High North News", "Arctic Today", "Barents Observer"],
            },
            {
                "name": "Parliament NDDN Committee",
                "endpoint": "/enrichment/parliament-nddn",
                "indicators": 5,
                "freshness": "Daily (weekly when in session)",
                "auth": "None required",
                "status": "active",
                "note": "Standing Committee on National Defence — meetings, studies, witness lists.",
            },
        ],
        "total_sources": 58,
        "total_active": 58,
    }


# ── ECONOMIC & TRADE INTELLIGENCE ────────────────────────────────


@router.get("/metals/prices")
async def get_metal_prices():
    """FRED monthly defence-relevant metal and energy commodity prices (13 series)."""
    cached = _check("fred_metals")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import FREDDefenceMetalsClient
        client = FREDDefenceMetalsClient()
        data = await client.fetch_metal_prices()
        result = {"source": "FRED", "records": len(data), "data": data}
        _cache["fred_metals"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch metal prices")


@router.get("/risk-indicators")
async def get_risk_indicators():
    """FRED daily financial risk and geopolitical stress indicators (8 series)."""
    cached = _check("fred_risk")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import FREDRiskIndicatorsClient
        client = FREDRiskIndicatorsClient()
        data = await client.fetch_risk_indicators()
        result = {"source": "FRED", "records": len(data), "data": data}
        _cache["fred_risk"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch risk indicators")


@router.get("/fx-rates")
async def get_fx_rates():
    """Daily exchange rates for 15 defence-relevant currencies (ECB via Frankfurter)."""
    cached = _check("fx_rates")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import FrankfurterFXClient
        client = FrankfurterFXClient()
        data = await client.fetch_rates()
        _cache["fx_rates"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch exchange rates")


# ── GEOPOLITICAL OSINT ───────────────────────────────────────────


@router.get("/geopolitical/un-voting")
async def get_un_voting():
    """UN General Assembly voting alignment data (Harvard Dataverse)."""
    cached = _check("un_voting")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import UNVotingClient
        client = UNVotingClient()
        data = await client.fetch_voting_summary()
        _cache["un_voting"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch UN voting data")


@router.get("/geopolitical/democracy-index")
async def get_democracy_index():
    """V-Dem democracy scores and regime classification for defence-relevant countries."""
    cached = _check("vdem")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import VDemDemocracyClient
        client = VDemDemocracyClient()
        data = await client.fetch_democracy_scores()
        _cache["vdem"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch V-Dem data")


@router.get("/geopolitical/think-tank-analysis")
async def get_think_tank_analysis():
    """Latest defence/security analysis from 6 leading think tanks (RSS)."""
    cached = _check("think_tanks")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import ThinkTankRSSClient
        client = ThinkTankRSSClient()
        data = await client.fetch_latest()
        result = {"source": "Think Tank RSS (6 feeds)", "records": len(data), "data": data}
        _cache["think_tanks"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch think tank analysis")


@router.get("/geopolitical/gov-defence-news")
async def get_gov_defence_news():
    """Government defence press releases (US DoD, UK MoD, Arms Control Association)."""
    cached = _check("gov_defence_news")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import GovDefenceNewsClient
        client = GovDefenceNewsClient()
        data = await client.fetch_latest()
        result = {"source": "Government Defence News (4 feeds)", "records": len(data), "data": data}
        _cache["gov_defence_news"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch government defence news")


# ── CYBER THREAT & CONFLICT INTELLIGENCE ─────────────────────────


@router.get("/cyber/mitre-stix")
async def get_mitre_stix_groups():
    """MITRE ATT&CK STIX 2.1 threat groups (160+ intrusion sets)."""
    cached = _check("mitre_stix")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import MITREAttackSTIXClient
        client = MITREAttackSTIXClient()
        data = await client.fetch_threat_groups()
        result = {"source": "MITRE ATT&CK STIX 2.1", "records": len(data), "data": data[:50]}
        _cache["mitre_stix"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch MITRE STIX data")


@router.get("/cyber/malpedia")
async def get_malpedia_actors():
    """Malpedia threat actor profiles with malware family linkages."""
    cached = _check("malpedia_actors")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import MalpediaActorsClient
        client = MalpediaActorsClient()
        data = await client.fetch_actors()
        result = {"source": "Malpedia (Fraunhofer FKIE)", "records": len(data), "data": data[:50]}
        _cache["malpedia_actors"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch Malpedia data")


@router.get("/cyber/apt-crossref")
async def get_apt_crossref():
    """ThaiCERT/ETDA APT group cross-reference (MISP Galaxy format)."""
    cached = _check("thaicert_apt")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import ThaiCERTAPTClient
        client = ThaiCERTAPTClient()
        data = await client.fetch_apt_galaxy()
        result = {"source": "ThaiCERT ETDA MISP Galaxy", "records": len(data), "data": data[:50]}
        _cache["thaicert_apt"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch APT cross-reference data")


@router.get("/cyber/kev-live")
async def get_cisa_kev_live():
    """CISA Known Exploited Vulnerabilities catalog (live, updated weekdays)."""
    cached = _check("cisa_kev_live")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import CISAKEVLiveClient
        client = CISAKEVLiveClient()
        data = await client.fetch_kev_catalog()
        _cache["cisa_kev_live"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch CISA KEV data")


@router.get("/cyber/breach-news")
async def get_breach_news():
    """DataBreaches.net latest breach news (RSS, updated daily)."""
    cached = _check("databreaches")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import DataBreachesRSSClient
        client = DataBreachesRSSClient()
        data = await client.fetch_latest()
        result = {"source": "DataBreaches.net", "records": len(data), "data": data}
        _cache["databreaches"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch breach news")


@router.get("/conflict/displacement")
async def get_displacement():
    """IDMC internal displacement updates (daily, rolling 180 days)."""
    cached = _check("idmc")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import IDMCDisplacementClient
        client = IDMCDisplacementClient()
        data = await client.fetch_displacement()
        result = {"source": "IDMC", "records": len(data), "data": data}
        _cache["idmc"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch displacement data")


@router.get("/conflict/ucdp")
async def get_ucdp_conflict():
    """UCDP conflict data (battle deaths 1989-2024, georeferenced events)."""
    cached = _check("ucdp_conflict")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import UCDPConflictClient
        client = UCDPConflictClient()
        data = await client.fetch_conflict_summary()
        _cache["ucdp_conflict"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch UCDP conflict data")


# ── ARCTIC, MARITIME & PROCUREMENT ───────────────────────────────


@router.get("/arctic/sea-ice")
async def get_arctic_sea_ice():
    """NSIDC daily Arctic sea ice extent (since 1978)."""
    cached = _check("nsidc_ice")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import NSIDCSeaIceClient
        client = NSIDCSeaIceClient()
        data = await client.fetch_ice_extent()
        result = {"source": "NSIDC Sea Ice Index v4", "records": len(data), "data": data}
        _cache["nsidc_ice"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch sea ice data")


@router.get("/maritime/chokepoints")
async def get_chokepoint_traffic():
    """IMF PortWatch daily vessel transit data for 28 global chokepoints."""
    cached = _check("portwatch_choke")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import PortWatchChokepointsClient
        client = PortWatchChokepointsClient()
        data = await client.fetch_chokepoints()
        result = {"source": "IMF PortWatch", "records": len(data), "data": data}
        _cache["portwatch_choke"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch chokepoint data")


@router.get("/maritime/ports")
async def get_port_activity(country: str = ""):
    """IMF PortWatch port activity data (2,033 global ports)."""
    cache_key = f"portwatch_ports_{country}"
    cached = _check(cache_key)
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import PortWatchPortsClient
        client = PortWatchPortsClient()
        data = await client.fetch_ports(country_iso3=country)
        result = {"source": "IMF PortWatch", "records": len(data), "data": data}
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch port data")


@router.get("/maritime/canal-transits")
async def get_canal_transits():
    """HDX monthly transit data for Suez, Panama, Bosphorus, Gulf of Aden."""
    cached = _check("hdx_canals")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import HDXCanalTransitsClient
        client = HDXCanalTransitsClient()
        data = await client.fetch_transits()
        _cache["hdx_canals"] = (time.time(), data)
        return data
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch canal transit data")


@router.get("/arctic/icebreakers")
async def get_icebreaker_fleet():
    """Global icebreaker fleet from Wikidata SPARQL (50+ vessels)."""
    cached = _check("icebreakers")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import WikidataIcebreakerClient
        client = WikidataIcebreakerClient()
        data = await client.fetch_icebreakers()
        result = {"source": "Wikidata SPARQL", "records": len(data), "data": data}
        _cache["icebreakers"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch icebreaker data")


@router.get("/arctic/news")
async def get_arctic_news():
    """Arctic security and policy news from The Arctic Institute RSS."""
    cached = _check("arctic_institute")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import ArcticInstituteRSSClient
        client = ArcticInstituteRSSClient()
        data = await client.fetch_latest()
        result = {"source": "The Arctic Institute", "records": len(data), "data": data}
        _cache["arctic_institute"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch Arctic news")


@router.get("/procurement/canadabuys")
async def get_canadabuys_tenders():
    """CanadaBuys new tender notices (updated every 2 hours)."""
    cached = _check("canadabuys")
    if cached:
        return cached
    try:
        from src.ingestion.osint_feeds import CanadaBuysTendersClient
        client = CanadaBuysTendersClient()
        data = await client.fetch_new_tenders()
        result = {"source": "CanadaBuys", "records": len(data), "data": data}
        _cache["canadabuys"] = (time.time(), result)
        return result
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch CanadaBuys tenders")


# ── CANADA INTEL FRESH FEEDS ─────────────────────────────────────────────────


@router.get("/gc-defence-news")
async def get_gc_defence_news():
    """Government of Canada defence news from DND, GAC, Defence & Security, Public Safety."""
    cached = _check("gc_defence_news")
    if cached:
        return cached
    from src.ingestion.gc_defence_news import GCDefenceNewsClient
    try:
        client = GCDefenceNewsClient()
        articles = await client.fetch_all(filter_defence=True)
        result = {
            "source": "Government of Canada News (4 feeds)",
            "records": len(articles),
            "data": [a.to_dict() for a in articles],
        }
        _cache["gc_defence_news"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("GC Defence News fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/nato-news")
async def get_nato_news():
    """Latest NATO news from the official RSS feed."""
    cached = _check("nato_news")
    if cached:
        return cached
    from src.ingestion.nato_news import NATONewsClient
    try:
        client = NATONewsClient()
        articles = await client.fetch_latest()
        result = {
            "source": "NATO Official RSS",
            "records": len(articles),
            "data": [a.to_dict() for a in articles],
        }
        _cache["nato_news"] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("NATO News fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/norad-news")
async def get_norad_news():
    """NORAD press releases (Arctic intercepts, exercises, aerospace warnings)."""
    cache_key = "norad_news"
    cached = _check(cache_key)
    if cached:
        return cached
    from src.ingestion.norad_news import NORADNewsClient
    try:
        client = NORADNewsClient()
        releases = await client.fetch_press_releases()
        result = {
            "source": "NORAD Newsroom",
            "records": len(releases),
            "arctic_related": sum(1 for r in releases if r.is_arctic_related),
            "data": [r.to_dict() for r in releases],
        }
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("NORAD News fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/canadian-sanctions")
async def get_canadian_sanctions():
    """Canadian consolidated autonomous sanctions list (SEMA + JVCFOA)."""
    cache_key = "canadian_sanctions"
    cached = _check(cache_key)
    if cached:
        return cached
    from src.ingestion.canadian_sanctions import CanadianSanctionsClient
    try:
        client = CanadianSanctionsClient()
        entries = await client.fetch_sanctions()
        countries: dict[str, int] = {}
        for e in entries:
            if e.country:
                countries[e.country] = countries.get(e.country, 0) + 1
        result = {
            "source": "Global Affairs Canada SEMA/JVCFOA",
            "total_entities": len(entries),
            "countries_targeted": len(countries),
            "top_countries": dict(sorted(countries.items(), key=lambda x: -x[1])[:20]),
            "data": [e.to_dict() for e in entries[:200]],
        }
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Canadian Sanctions fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/arctic-osint")
async def get_arctic_osint_news():
    """Arctic OSINT news from High North News, Arctic Today, Barents Observer."""
    cache_key = "arctic_osint"
    cached = _check(cache_key)
    if cached:
        return cached
    from src.ingestion.arctic_news import ArcticNewsClient
    try:
        client = ArcticNewsClient()
        articles = await client.fetch_all(filter_security=False)
        result = {
            "source": "Arctic OSINT (3 feeds)",
            "records": len(articles),
            "security_related": sum(1 for a in articles if a.is_security_related),
            "data": [a.to_dict() for a in articles],
        }
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Arctic OSINT fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/parliament-nddn")
async def get_parliament_nddn():
    """NDDN (Standing Committee on National Defence) activity."""
    cache_key = "parliament_nddn"
    cached = _check(cache_key)
    if cached:
        return cached
    from src.ingestion.parliament_nddn import ParliamentNDDNClient
    try:
        client = ParliamentNDDNClient()
        activities = await client.fetch_activities()
        by_type: dict[str, int] = {}
        for a in activities:
            by_type[a.activity_type] = by_type.get(a.activity_type, 0) + 1
        result = {
            "source": "House of Commons — NDDN",
            "records": len(activities),
            "by_type": by_type,
            "data": [a.to_dict() for a in activities],
        }
        _cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Parliament NDDN fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
