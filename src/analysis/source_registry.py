"""Centralized source validation registry.

Maps hierarchical dot-notation keys to source metadata for every
dashboard UI element. Supports inheritance: if 'arctic.kpis.threat_level'
has no entry, resolution walks up to 'arctic.kpis' then 'arctic'.

Public API:
    resolve_sources(key) -> dict | None
    get_registry() -> dict[str, dict]
"""
from __future__ import annotations

# Source type constants
PRIMARY = "Primary"
CROSS_VALIDATION = "Cross-validation"
TRADE_VALIDATION = "Trade validation"
COMPANY_REPORTS = "Company reports"
MANUFACTURER = "Manufacturer datasheets"
DERIVED = "Derived estimate"
REFERENCE = "Reference"
PUBLIC = "Public domain"

_REGISTRY: dict[str, dict] = {
    "arctic": {
        "title": "Arctic Security Assessment — Source Validation",
        "sources": [
            {
                "name": "SIPRI Arms Transfers Database",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases/armstransfers",
                "date": "2025",
                "note": "Annual TIV data for Arctic-nation arms flows (Russia, Canada, Norway, Denmark, USA)",
            },
            {
                "name": "CIA World Factbook — Military",
                "type": PRIMARY,
                "url": "https://www.cia.gov/the-world-factbook/",
                "date": "2024",
                "note": "Force composition, conscription, budget share for all Arctic Council states",
            },
            {
                "name": "Arctic Council Reports",
                "type": REFERENCE,
                "date": "2024",
                "note": "Governance frameworks, shipping route status, environmental assessments",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI transfers + CIA Factbook + Arctic Council governance data",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    "arctic.kpis.ice_extent": {
        "title": "Arctic Sea Ice Extent — Source Validation",
        "sources": [
            {
                "name": "NOAA/NSIDC Sea Ice Index v3",
                "type": PRIMARY,
                "url": "https://nsidc.org/data/seaice_index/",
                "date": "Monthly",
                "note": "Satellite-derived Arctic sea ice extent and concentration, updated monthly",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Single authoritative source — NSIDC is the global standard for sea ice measurement",
        "health_keys": ["noaa_ice"],
    },
    "arctic.bases": {
        "title": "Arctic Base Registry — Source Validation",
        "sources": [
            {
                "name": "SIPRI Military Bases Data Project",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases",
                "date": "2024",
                "note": "25 Arctic military installations with coordinates and capability data",
            },
            {
                "name": "CSIS Arctic Military Tracker",
                "type": CROSS_VALIDATION,
                "url": "https://www.csis.org/programs/americas-program",
                "date": "2024",
                "note": "Cross-validates base locations and operational status",
            },
            {
                "name": "National Ministry of Defence publications",
                "type": REFERENCE,
                "date": "2023-2024",
                "note": "Russia MoD, Canadian DND, US DoD annual reports on Arctic posture",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI + CSIS + national MoD data for 25 installations",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    # ------------------------------------------------------------------
    # Arctic (4 additional)
    # ------------------------------------------------------------------
    "arctic.flights": {
        "title": "Arctic Military Flights — Source Validation",
        "sources": [
            {"name": "adsb.lol ADS-B Exchange", "type": PRIMARY, "url": "https://api.adsb.lol/v2/mil", "date": "Live (60s)", "note": "Primary military aircraft transponder feed"},
            {"name": "adsb.fi ADS-B Finland", "type": CROSS_VALIDATION, "url": "https://opendata.adsb.fi/api/v2/mil", "date": "Live (60s)", "note": "Cross-validation feed"},
            {"name": "Airplanes.live", "type": CROSS_VALIDATION, "url": "https://api.airplanes.live/v2/mil", "date": "Live (60s)", "note": "Third independent ADS-B source"},
            {"name": "ADSB One", "type": CROSS_VALIDATION, "url": "https://api.adsbone.com/v2/mil", "date": "Live (60s)", "note": "Fourth ADS-B source — deduplicated by hex code"},
        ],
        "confidence": "HIGH",
        "confidence_note": "4 independent ADS-B sources with deduplication",
        "health_keys": [],
    },
    "arctic.routes": {
        "title": "Arctic Shipping Routes — Source Validation",
        "sources": [
            {"name": "IMF PortWatch", "type": PRIMARY, "url": "https://portwatch.imf.org/", "date": "2024", "note": "Maritime chokepoint monitoring, Arctic passage traffic"},
            {"name": "Arctic Council PAME", "type": REFERENCE, "url": "https://pame.is/", "date": "2024", "note": "Official route classifications (NSR, NWP, Transpolar)"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Route definitions from Arctic Council are authoritative; traffic volumes rely on IMF estimates",
        "health_keys": ["portwatch_chokepoints"],
    },
    "arctic.trade": {
        "title": "Arctic Trade Flows — Source Validation",
        "sources": [
            {"name": "UN Comtrade", "type": PRIMARY, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "Bilateral trade values for Arctic-adjacent nations"},
            {"name": "Statistics Canada CIMT", "type": CROSS_VALIDATION, "url": "https://www.statcan.gc.ca/", "date": "Monthly", "note": "Canadian bilateral trade verification"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Comtrade cross-validated with StatCan for Canadian corridors",
        "health_keys": ["comtrade_trade"],
    },
    "arctic.naval": {
        "title": "Naval Presence & Russia Weakness — Source Validation",
        "sources": [
            {"name": "CIA World Factbook — Military", "type": PRIMARY, "url": "https://www.cia.gov/the-world-factbook/", "date": "2024", "note": "Naval vessel counts, force readiness, conscription data"},
            {"name": "Jane's Defence Weekly", "type": REFERENCE, "date": "2024", "note": "Order of battle, fleet composition, capability assessments"},
            {"name": "SIPRI Military Expenditure", "type": CROSS_VALIDATION, "url": "https://milex.sipri.org/", "date": "2024", "note": "Military spending trends corroborate force posture"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "CIA Factbook is primary; Jane's adds capability depth",
        "health_keys": ["cia_factbook"],
    },
    # ------------------------------------------------------------------
    # Insights (10)
    # ------------------------------------------------------------------
    "insights": {
        "title": "Intelligence Insights — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "Global arms transfer TIV data (1950–2024) for trade flow analysis"},
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "url": "https://www.gdeltproject.org/", "date": "15-min updates", "note": "Real-time global event monitoring, arms trade keyword filtering"},
            {"name": "OFAC SDN + EU Sanctions", "type": PRIMARY, "date": "On-demand", "note": "17 embargoed countries, sanctions list cross-referencing"},
            {"name": "4x ADS-B Flight Sources", "type": PRIMARY, "date": "Live (60s)", "note": "adsb.lol, adsb.fi, Airplanes.live, ADSB One — military flight tracking"},
            {"name": "NATO Defence Expenditure", "type": PRIMARY, "url": "https://www.nato.int/cps/en/natohq/topics_49198.htm", "date": "2025 est.", "note": "Annual defence spending as % GDP for all NATO members"},
            {"name": "UN Comtrade", "type": TRADE_VALIDATION, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "USD bilateral trade data, buyer-side mirror for opacity circumvention"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Aggregated across 6+ independent primary sources with cross-validation",
        "health_keys": ["sipri_transfers", "gdelt_news", "comtrade_trade"],
    },
    "insights.sitrep": {
        "title": "Situation Report — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Transfer volumes and supplier shift detection"},
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "date": "15-min updates", "note": "News event scoring for threat level indicators"},
            {"name": "OFAC SDN + EU + UN Sanctions", "type": PRIMARY, "date": "On-demand", "note": "Sanctions compliance checking across 17 embargoes"},
            {"name": "Military Flight Tracker (4 ADS-B)", "type": PRIMARY, "date": "Live (60s)", "note": "Arctic and global military flight pattern analysis"},
            {"name": "NATO Defence Expenditure", "type": PRIMARY, "date": "2025 est.", "note": "Canada NATO ranking and rearmament tracking"},
            {"name": "UN Comtrade Buyer Mirror", "type": TRADE_VALIDATION, "date": "2023", "note": "Russia/China export verification via buyer-reported imports"},
        ],
        "confidence": "HIGH",
        "confidence_note": "6 threat indicators each backed by independent primary sources, cross-validated where possible",
        "health_keys": ["sipri_transfers", "gdelt_news", "comtrade_trade"],
    },
    "insights.sitrep.sanctions": {
        "title": "Sanctions & Embargoes — Source Validation",
        "sources": [
            {"name": "OFAC SDN List", "type": PRIMARY, "url": "https://sanctionslist.ofac.treas.gov/", "date": "On-demand", "note": "US Treasury specially designated nationals and blocked persons"},
            {"name": "EU Consolidated Sanctions", "type": PRIMARY, "date": "On-demand", "note": "EU financial sanctions list"},
            {"name": "UN Security Council Sanctions", "type": PRIMARY, "date": "On-demand", "note": "UNSC consolidated sanctions list"},
            {"name": "Arms Embargo Registry", "type": REFERENCE, "date": "2024", "note": "17 embargoed countries"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across 3 independent sanctions authorities (OFAC, EU, UN) plus curated embargo list",
        "health_keys": ["un_sanctions"],
    },
    "insights.sitrep.arctic": {
        "title": "Arctic Threat Indicator — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Russian Arctic militarization — arms procurement trends"},
            {"name": "CIA World Factbook — Military", "type": PRIMARY, "date": "2024", "note": "Arctic nation force compositions and defence budgets"},
            {"name": "NOAA/NSIDC Sea Ice Index", "type": PRIMARY, "url": "https://nsidc.org/data/seaice_index/", "date": "Monthly", "note": "Ice extent decline rates impacting route accessibility"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Military data from SIPRI + CIA, environmental from NOAA — independent domains corroborate threat picture",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    "insights.taxonomy": {
        "title": "DND Risk Taxonomy (13 Categories) — Source Validation",
        "sources": [
            {"name": "PSI Supply Chain Analytics", "type": PRIMARY, "date": "Live", "note": "6-dimension risk scoring feeds categories 1-3"},
            {"name": "GDELT News Analysis", "type": PRIMARY, "date": "15-min updates", "note": "Real-time OSINT scoring for live categories (1, 2, 3, 11)"},
            {"name": "World Bank Governance Indicators", "type": PRIMARY, "url": "https://info.worldbank.org/governance/wgi/", "date": "2023", "note": "WGI scores for geopolitical instability categories"},
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "13-category, 121 sub-category risk taxonomy definition"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "4 categories scored live from OSINT, 3 hybrid, 6 seeded with drift — coverage expanding",
        "health_keys": ["gdelt_news", "worldbank_governance"],
    },
    "insights.news": {
        "title": "Live Intelligence News — Source Validation",
        "sources": [
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "url": "https://www.gdeltproject.org/", "date": "15-min updates", "note": "Global event database filtered for arms trade, military, and geopolitical keywords"},
            {"name": "Defense News RSS", "type": PRIMARY, "date": "Hourly", "note": "4 feeds: Defense News, Breaking Defense, Jane's, Defense One"},
            {"name": "Disinformation Detection (3-layer)", "type": DERIVED, "date": "Real-time", "note": "State-media domain check + extreme tone scoring + sensationalist title patterns"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "GDELT is comprehensive but noisy — disinformation detection layer provides quality filtering",
        "health_keys": ["gdelt_news"],
    },
    "insights.dsca": {
        "title": "DSCA Arms Sales — Source Validation",
        "sources": [
            {"name": "DSCA Major Arms Sales Notifications", "type": PRIMARY, "url": "https://www.dsca.mil/press-media/major-arms-sales", "date": "Days", "note": "US Defense Security Cooperation Agency — Congressional notifications"},
            {"name": "Federal Register API", "type": PRIMARY, "url": "https://www.federalregister.gov/", "date": "Days", "note": "Official US government publication of DSCA notifications"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Primary US government source — authoritative for US foreign military sales",
        "health_keys": ["dod_contracts"],
    },
    "insights.alliances": {
        "title": "Shifting Alliances — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Historical supplier-buyer relationships, detects primary supplier changes"},
            {"name": "UN Comtrade Bilateral Trade", "type": CROSS_VALIDATION, "date": "2023", "note": "USD trade values validate TIV-based alliance patterns"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV trends cross-validated with Comtrade USD bilateral data",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "insights.freshness": {
        "title": "Data Source Freshness — Source Validation",
        "sources": [
            {"name": "All 56 Active Connectors", "type": PRIMARY, "date": "Live", "note": "Freshness derived from actual last-fetch timestamps across all data source connectors"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Freshness is computed live from connector cache timestamps — always reflects reality",
        "health_keys": [],
    },
    "insights.adversary": {
        "title": "Adversary Trade Flows — Source Validation",
        "sources": [
            {"name": "UN Comtrade Buyer-Side Mirror", "type": PRIMARY, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "Queries what buyers report importing from Russia/China"},
            {"name": "SIPRI Arms Transfers (TIV)", "type": CROSS_VALIDATION, "date": "2025", "note": "Volume-based cross-check of Comtrade USD values"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Buyer-side mirror technique specifically designed to circumvent Russia/China reporting gaps",
        "health_keys": ["comtrade_trade", "sipri_transfers"],
    },
    # ------------------------------------------------------------------
    # Deals (2)
    # ------------------------------------------------------------------
    "deals": {
        "title": "Arms Transfers Database — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "9,311 transfers (1950–2024), 26 sellers, 186 buyers"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI is the global standard for arms transfer data",
        "health_keys": ["sipri_transfers"],
    },
    "deals.transfers": {
        "title": "Arms Transfer Records — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "TIV-denominated transfer records with weapon descriptions, order dates, delivery status"},
            {"name": "UN Comtrade HS 93", "type": CROSS_VALIDATION, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "USD trade values for arms & ammunition cross-validate SIPRI TIV volumes"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV cross-validated with Comtrade USD",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    # ------------------------------------------------------------------
    # Canada Intel (6)
    # ------------------------------------------------------------------
    "canada": {
        "title": "Canada Intelligence — Source Validation",
        "sources": [
            {"name": "Statistics Canada CIMT", "type": PRIMARY, "url": "https://www.statcan.gc.ca/", "date": "Monthly", "note": "Canadian International Merchandise Trade — bilateral trade by HS code"},
            {"name": "DND Procurement Disclosure", "type": PRIMARY, "url": "https://open.canada.ca/", "date": "Weekly", "note": "Open Canada defence contract disclosures"},
            {"name": "SIPRI Arms Transfers Database", "type": CROSS_VALIDATION, "date": "2025", "note": "Canada as buyer/seller in global arms transfer network"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Canadian government primary sources cross-validated with SIPRI",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "canada.flows": {
        "title": "Ally vs Adversary Trade Flows — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Bilateral TIV flows — Canada allies vs adversary networks"},
            {"name": "UN Comtrade Bilateral", "type": CROSS_VALIDATION, "date": "2023", "note": "USD trade values verify SIPRI TIV patterns"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV cross-validated with Comtrade USD bilateral data",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "canada.threats": {
        "title": "Threat Watchlist — Source Validation",
        "sources": [
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "date": "15-min updates", "note": "Real-time event monitoring for threat indicators"},
            {"name": "Sanctions Lists (OFAC/EU/UN)", "type": PRIMARY, "date": "On-demand", "note": "Active sanctions against watchlist countries"},
            {"name": "Military Flight Tracker (4 ADS-B)", "type": PRIMARY, "date": "Live (60s)", "note": "Suspicious flight activity near Canadian airspace"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Multi-source threat indicators — GDELT breadth, sanctions depth, flights immediacy",
        "health_keys": ["gdelt_news"],
    },
    "canada.suppliers": {
        "title": "Defence Supply Base — Source Validation",
        "sources": [
            {"name": "DND Procurement Disclosure", "type": PRIMARY, "url": "https://open.canada.ca/", "date": "Weekly", "note": "Open Canada contract disclosures — vendor names, values, sectors"},
            {"name": "Wikidata SPARQL (Ownership)", "type": CROSS_VALIDATION, "url": "https://query.wikidata.org/", "date": "On-demand", "note": "Parent company chains and country of origin"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Government procurement data is authoritative; Wikidata enriches ownership",
        "health_keys": ["suppliers"],
    },
    "canada.suppliers.risk": {
        "title": "Supplier Risk Ranking — Source Validation",
        "sources": [
            {"name": "PSI 6-Dimension Risk Scoring", "type": DERIVED, "date": "Computed", "note": "Foreign ownership, concentration, single-source, contract activity, sanctions, performance"},
            {"name": "DND Procurement Data", "type": PRIMARY, "date": "Weekly", "note": "Contract values and frequency feed concentration dimension"},
            {"name": "Sanctions Cross-Check", "type": PRIMARY, "date": "On-demand", "note": "OFAC/EU/UN lists checked against supplier ownership chains"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Scoring model uses real procurement data; some dimensions rely on limited historical data",
        "health_keys": ["suppliers"],
    },
    "canada.actions": {
        "title": "Action Centre (COAs) — Source Validation",
        "sources": [
            {"name": "Mitigation Playbook (191 entries)", "type": REFERENCE, "date": "2024", "note": "Courses of action across all 13 DND risk categories"},
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "Risk taxonomy framework defining mitigation requirements"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "COA playbook is internally curated — recommendations, not verified outcomes",
        "health_keys": [],
    },
    # ------------------------------------------------------------------
    # Data Feeds (3)
    # ------------------------------------------------------------------
    "feeds": {
        "title": "Data Feeds — Source Validation",
        "sources": [
            {"name": "56 Active Data Source Connectors", "type": PRIMARY, "date": "Various", "note": "Live (60s) to Annual freshness across SIPRI, GDELT, Comtrade, NATO, DSCA, ADS-B, and 50 more"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Feed status computed from connector runtime state",
        "health_keys": [],
    },
    "feeds.status": {
        "title": "Feed Health Cards — Source Validation",
        "sources": [
            {"name": "APScheduler Runtime", "type": PRIMARY, "date": "Live", "note": "Scheduler job status, last run, next scheduled run"},
            {"name": "Connector Cache Metadata", "type": PRIMARY, "date": "Live", "note": "Per-connector cache timestamps and TTL status"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Health from runtime — reflects actual connector state",
        "health_keys": [],
    },
    "feeds.stats": {
        "title": "Aggregate Feed Statistics — Source Validation",
        "sources": [
            {"name": "All Connector Caches", "type": DERIVED, "date": "Computed", "note": "Record counts, freshness, error rates aggregated across all 56 connectors"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Computed from live connector state",
        "health_keys": [],
    },
    # ------------------------------------------------------------------
    # Compliance (2)
    # ------------------------------------------------------------------
    "compliance": {
        "title": "DMPP 11 Compliance — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 RFI Questions", "type": REFERENCE, "date": "2024", "note": "22 RFI questions with 118 sub-requirements"},
            {"name": "Internal Implementation Mapping", "type": DERIVED, "date": "2026-04-01", "note": "Traceability from each sub-requirement to code/API/UI"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Compliance verified through cobalt audit — 99% compliance achieved",
        "health_keys": [],
    },
    "compliance.matrix": {
        "title": "Compliance Matrix — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 RFI", "type": REFERENCE, "date": "2024", "note": "Original 22 questions + 118 sub-requirements"},
            {"name": "Implementation Evidence", "type": DERIVED, "date": "2026-04-01", "note": "Each requirement mapped to API, UI, or data source with View button"},
            {"name": "Cobalt Compliance Audit", "type": CROSS_VALIDATION, "date": "2026-04-01", "note": "Full audit: 8 gaps found, 7 fixed, 1 structural (NSN)"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Traceability verified — every sub-requirement has implementation evidence",
        "health_keys": [],
    },
    # ------------------------------------------------------------------
    # Supply Chain (20)
    # ------------------------------------------------------------------
    "supply.overview": {
        "title": "Supply Chain Overview — Source Validation",
        "sources": [
            {"name": "PSI Supply Chain Analytics", "type": PRIMARY, "date": "Computed", "note": "Aggregated risk scores, alerts, graph metrics across 30 minerals"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Production data, reserves, import reliance"},
        ],
        "confidence": "HIGH",
        "confidence_note": "PSI scoring from primary USGS + BGS + Comtrade data",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.globe": {
        "title": "3D Supply Chain Globe — Source Validation",
        "sources": [
            {"name": "Mineral Supply Chains Dataset", "type": PRIMARY, "date": "2025", "note": "30 minerals with geo-coordinates, 4-tier flow"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "date": "January 2025", "note": "Country production shares and mine locations"},
            {"name": "Shipping Route Analysis", "type": DERIVED, "date": "Computed", "note": "6 corridors with chokepoint risk ratings"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Geo-coordinates from USGS/BGS; routes from IMF PortWatch",
        "health_keys": ["usgs_mineral_deposits", "portwatch_chokepoints"],
    },
    "supply.graph": {
        "title": "Knowledge Graph — Source Validation",
        "sources": [
            {"name": "NetworkX Graph Engine", "type": DERIVED, "date": "Computed", "note": "90 nodes, 97 edges, BOM explosion paths"},
            {"name": "Supply Chain Seed Data (20 platforms)", "type": REFERENCE, "date": "2025", "note": "BOM for 20 defence platforms"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Graph from curated BOM data — edge weights estimated",
        "health_keys": [],
    },
    "supply.risks": {
        "title": "Risk Matrix — Source Validation",
        "sources": [
            {"name": "PSI 6-Dimension Risk Scoring", "type": DERIVED, "date": "Computed", "note": "Concentration, sanctions, chokepoints, instability, scarcity, alternatives"},
            {"name": "World Bank Governance Indicators", "type": PRIMARY, "date": "2023", "note": "Political stability feeds instability dimension"},
            {"name": "OFAC/EU/UN Sanctions", "type": PRIMARY, "date": "On-demand", "note": "Sanctions lists feed exposure dimension"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Each dimension backed by independent primary data",
        "health_keys": ["worldbank_governance", "un_sanctions"],
    },
    "supply.scenarios": {
        "title": "Scenario Sandbox — Source Validation",
        "sources": [
            {"name": "Scenario Engine (Multi-Variable)", "type": DERIVED, "date": "Computed", "note": "Stackable disruption layers with cascade propagation"},
            {"name": "5 Preset Compound Scenarios", "type": REFERENCE, "date": "2025", "note": "Indo-Pacific Conflict, Arctic Escalation, Global Recession, DRC Collapse, Suez Closure"},
            {"name": "Cascade Propagation Model", "type": DERIVED, "date": "Computed", "note": "4-tier Sankey with Likelihood×Impact scoring"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Analytical models, not predictions — impact from historical disruption data",
        "health_keys": [],
    },
    "supply.taxonomy": {
        "title": "Supply Chain Risk Taxonomy — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "13-category, 121 sub-category framework"},
            {"name": "Live OSINT Scoring", "type": PRIMARY, "date": "Real-time", "note": "4 categories live, 3 hybrid, 6 seeded with drift"},
            {"name": "World Bank WGI", "type": PRIMARY, "date": "2023", "note": "Governance indicators for geopolitical categories"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "7 of 13 categories have live/hybrid scoring; 6 seeded",
        "health_keys": ["gdelt_news", "worldbank_governance"],
    },
    "supply.forecasting": {
        "title": "Price Forecasting — Source Validation",
        "sources": [
            {"name": "IMF Primary Commodity Prices (PCOBALT)", "type": PRIMARY, "url": "https://www.imf.org/en/Research/commodity-prices", "date": "Monthly", "note": "Direct cobalt price series — primary forecast input"},
            {"name": "FRED Nickel Prices (PNICKUSDM)", "type": CROSS_VALIDATION, "url": "https://fred.stlouisfed.org/series/PNICKUSDM", "date": "Monthly", "note": "Fallback proxy (0.85 correlation)"},
            {"name": "Linear Regression Model", "type": DERIVED, "date": "Computed", "note": "Quarterly regression with R², 90% CI, 3-scenario fan chart"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "IMF data authoritative; linear model simple but transparent",
        "health_keys": ["imf_weo"],
    },
    "supply.bom": {
        "title": "BOM Explorer — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Country production shares for mining tier"},
            {"name": "AMS Material Specifications", "type": REFERENCE, "date": "Current", "note": "Aerospace specs for alloy compositions"},
            {"name": "DND/Canada.ca Fleet Data", "type": PRIMARY, "date": "2024", "note": "CAF platform inventories and engine assignments"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Multi-tier BOM with independent sources per tier",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.bom.mining": {
        "title": "Mining / Extraction — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Country shares (DRC 76%, Indonesia 5%, Russia 5%, Australia 3%)"},
            {"name": "BGS World Mineral Statistics", "type": CROSS_VALIDATION, "url": "https://ogcapi.bgs.ac.uk/", "date": "2022-2023", "note": "Live API — pairwise discrepancy <10% with USGS"},
            {"name": "NRCan Canadian Mineral Production", "type": CROSS_VALIDATION, "date": "2023", "note": "Canada 3,900t cobalt — matches USGS within 5%"},
            {"name": "UN Comtrade (HS 2605, 8105)", "type": TRADE_VALIDATION, "date": "Monthly", "note": "10 bilateral corridors; DRC→China $2.39B (2023)"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across 4 independent sources",
        "health_keys": ["usgs_mineral_deposits", "comtrade_trade"],
    },
    "supply.bom.processing": {
        "title": "Processing / Refining — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "date": "January 2025", "note": "Refinery capacities (China 73% refining)"},
            {"name": "Cobalt Institute", "type": CROSS_VALIDATION, "url": "https://www.cobaltinstitute.org/", "date": "2024", "note": "Industry refinery data"},
            {"name": "Company Financial Filings", "type": COMPANY_REPORTS, "date": "Quarterly", "note": "CMOC, Jinchuan, Umicore, Freeport annual reports"},
        ],
        "confidence": "HIGH",
        "confidence_note": "USGS primary, cross-validated with Cobalt Institute and filings",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.bom.alloys": {
        "title": "Defence Alloys — Source Validation",
        "sources": [
            {"name": "AMS 5707 (Waspaloy)", "type": MANUFACTURER, "date": "Current", "note": "13.5% Co — turbine discs, rings, casings"},
            {"name": "AMS 5405 (Stellite 6)", "type": MANUFACTURER, "date": "Current", "note": "28% Co — wear-resistant valve seats"},
            {"name": "AMS 5788 (CMSX-4)", "type": MANUFACTURER, "date": "Current", "note": "9.5% Co — single-crystal turbine blades"},
            {"name": "AMS 5663 (Inconel 718)", "type": MANUFACTURER, "date": "Current", "note": "1% Co — structural forgings"},
        ],
        "confidence": "HIGH",
        "confidence_note": "AMS specs are definitive — cobalt percentages are metallurgical constants",
        "health_keys": [],
    },
    "supply.bom.platforms": {
        "title": "CAF Platforms & Engines — Source Validation",
        "sources": [
            {"name": "DND/Canada.ca Fleet Data", "type": PRIMARY, "url": "https://www.canada.ca/en/department-national-defence.html", "date": "2024", "note": "CF-188, CP-140, Halifax-class, Victoria-class inventories"},
            {"name": "OEM Engine Catalogues", "type": REFERENCE, "date": "Current", "note": "GE F404, GE T64, GE LM2500, Rolls-Royce PWR"},
            {"name": "Jane's Defence Equipment", "type": REFERENCE, "date": "2024", "note": "Platform-engine-alloy dependency chains"},
            {"name": "Derived Demand Model", "type": DERIVED, "date": "Computed", "note": "Cobalt demand from fleet × engines × Co content"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Fleet data authoritative; demand model estimated from public specs",
        "health_keys": [],
    },
    "supply.dossier": {
        "title": "Supplier Dossiers — Source Validation",
        "sources": [
            {"name": "Company Financial Filings", "type": COMPANY_REPORTS, "date": "Quarterly", "note": "Balance sheets for Altman Z-Score (18 entities)"},
            {"name": "Wikidata SPARQL (Ownership)", "type": PRIMARY, "url": "https://query.wikidata.org/", "date": "On-demand", "note": "UBO chains via parent_organization property"},
            {"name": "FOCI Scoring Model", "type": DERIVED, "date": "Computed", "note": "Foreign Ownership, Control, Influence — 0-100"},
            {"name": "GDELT Intelligence Feed", "type": PRIMARY, "date": "15-min updates", "note": "Recent OSINT articles per entity"},
        ],
        "confidence": "HIGH",
        "confidence_note": "18 entities with real dossiers — financials, ownership, intel",
        "health_keys": ["gdelt_news"],
    },
    "supply.alerts": {
        "title": "Watchtower Alerts — Source Validation",
        "sources": [
            {"name": "GDELT Keyword Monitoring", "type": PRIMARY, "date": "30-min cycle", "note": "8 keyword queries for cobalt supply disruption"},
            {"name": "Rule-Based Triggers", "type": DERIVED, "date": "Computed", "note": "HHI threshold, China refining share, paused ops"},
            {"name": "6 Seed Alerts", "type": REFERENCE, "date": "2025", "note": "Baseline alerts for known risks"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "GDELT breadth + rule engine precision — SEEDED vs LIVE badges distinguish provenance",
        "health_keys": ["gdelt_news"],
    },
    "supply.register": {
        "title": "Risk Register — Source Validation",
        "sources": [
            {"name": "PSI Risk Scoring", "type": DERIVED, "date": "Computed", "note": "10 catalogued cobalt risks with severity and linked COAs"},
            {"name": "Analyst Status Overrides", "type": PRIMARY, "date": "Persisted", "note": "Status lifecycle persisted to DB via analyst action"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Risk identification model-driven; status reflects analyst judgement",
        "health_keys": [],
    },
    "supply.feedback": {
        "title": "Analyst Feedback / RLHF — Source Validation",
        "sources": [
            {"name": "ML Anomaly Detection Engine", "type": DERIVED, "date": "Computed", "note": "Statistical anomaly detection with adaptive z-score"},
            {"name": "Analyst Adjudications", "type": PRIMARY, "date": "Persisted", "note": "Verified/False Positive feedback adjusts thresholds"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "ML accuracy improves with feedback — FP rate visible in panel",
        "health_keys": [],
    },
    "supply.chokepoints": {
        "title": "Strategic Chokepoints — Source Validation",
        "sources": [
            {"name": "IMF PortWatch", "type": PRIMARY, "url": "https://portwatch.imf.org/", "date": "2024", "note": "Malacca, Suez, Cape, Panama, Bab-el-Mandeb, Hormuz"},
            {"name": "Canal Authority Reports", "type": REFERENCE, "date": "2024", "note": "Suez/Panama annual traffic and disruption reports"},
            {"name": "PSI Route Risk Analysis", "type": DERIVED, "date": "Computed", "note": "Lead time estimates from distance + risk factor"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "IMF traffic data; risk estimates from disruption history",
        "health_keys": ["portwatch_chokepoints"],
    },
    "supply.hhi": {
        "title": "HHI Concentration Index — Source Validation",
        "sources": [
            {"name": "BGS World Mineral Statistics (Live API)", "type": PRIMARY, "url": "https://ogcapi.bgs.ac.uk/", "date": "2022-2023", "note": "Live OGC API — HHI computed in real-time"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": CROSS_VALIDATION, "date": "January 2025", "note": "Cross-validates BGS — discrepancy <10%"},
            {"name": "DoJ/FTC HHI Methodology", "type": REFERENCE, "date": "Current", "note": "Standard: <1500 low, 1500-2500 moderate, >2500 high"},
        ],
        "confidence": "HIGH",
        "confidence_note": "HHI computed live from BGS with USGS cross-validation",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.canada": {
        "title": "Canada Dependency — Source Validation",
        "sources": [
            {"name": "NRCan Canadian Mineral Production", "type": PRIMARY, "url": "https://natural-resources.canada.ca/", "date": "2023", "note": "Canadian cobalt production (3,900t), provincial breakdown"},
            {"name": "DND Fleet Data", "type": PRIMARY, "date": "2024", "note": "CAF platform inventories for demand estimation"},
            {"name": "Statistics Canada / UN Comtrade", "type": TRADE_VALIDATION, "date": "Monthly", "note": "Canadian cobalt import values"},
            {"name": "Derived Demand Model", "type": DERIVED, "date": "Computed", "note": "Direct CAF cobalt demand from fleet × engines × alloy content"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "NRCan production authoritative; demand model derived from public fleet data",
        "health_keys": ["comtrade_trade"],
    },
    "supply.risk_factors": {
        "title": "Risk Factors — Source Validation",
        "sources": [
            {"name": "USGS Critical Minerals List 2024", "type": PRIMARY, "date": "2024", "note": "Cobalt classified as critical mineral"},
            {"name": "DRC Ministry of Mines", "type": PRIMARY, "date": "2024", "note": "Artisanal mining regulations, export controls"},
            {"name": "Cobalt Institute Market Reports", "type": CROSS_VALIDATION, "url": "https://www.cobaltinstitute.org/", "date": "2024", "note": "Supply-demand balance, inventory levels"},
        ],
        "confidence": "HIGH",
        "confidence_note": "USGS critical mineral designation + DRC regulatory + industry reports",
        "health_keys": ["usgs_mineral_deposits"],
    },
}


def resolve_sources(key: str) -> dict | None:
    """Resolve a dot-notation key, walking up the hierarchy.

    If the exact key exists in the registry, return it directly.
    Otherwise, strip the rightmost segment and try the parent key,
    continuing until a match is found or the key is exhausted.

    Returns None if no match is found at any level.
    """
    if key in _REGISTRY:
        return _REGISTRY[key]
    parts = key.split(".")
    while len(parts) > 1:
        parts.pop()
        parent_key = ".".join(parts)
        if parent_key in _REGISTRY:
            return _REGISTRY[parent_key]
    return None


def get_registry() -> dict[str, dict]:
    """Return the full registry dict (read-only reference)."""
    return _REGISTRY
