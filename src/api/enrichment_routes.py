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
        logger.warning("PortWatch chokepoint fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("OpenSky Arctic aircraft fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("UNHCR displacement fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("Space Devs launch fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("Submarine cable fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("RIPE Stat fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("USASpending DoD contracts fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("USGS Mineral deposits fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("World Bank Conflict Deaths fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("Treasury Fiscal fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("OpenAlex research fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("RIPE Atlas connectivity fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("NVD CVE fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("NOAA Weather fetch failed: %s", e)
        return {"error": str(e)}


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
            "as_of": "2024 estimates (published 2025)",
            "note": "Hardcoded from latest FAS public estimates. Deployed strategic counts exclude tactical warheads.",
            "total_nuclear_states": len(arsenals),
            "global_total_warheads": total_warheads,
            "global_deployed_strategic": total_deployed,
            "arsenals": arsenals,
        }
        _cache["fas_nuclear_arsenals"] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("FAS Nuclear fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("World Bank Armed Forces fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("UNROCA key-countries fetch failed: %s", e)
        return {"error": str(e)}


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
        logger.warning("UNROCA country fetch failed (%s): %s", country, e)
        return {"error": str(e), "slug_tried": country,
                "hint": "Use /enrichment/unroca/countries for valid slugs"}


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
        logger.warning("UNROCA country list fetch failed: %s", e)
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
        ],
        "total_sources": 46,
        "total_active": 46,
    }
