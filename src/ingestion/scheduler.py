"""Scheduled ingestion pipeline.

Runs each data connector on its natural update cadence and persists
results to the database.

Schedule:
  - Military flights:       every 5 minutes
  - GDELT arms news:        every 15 minutes
  - Cobalt alert engine:    every 30 minutes
  - Defense News RSS:       every 30 minutes
  - GC Defence News:        every 30 minutes
  - NATO News:              hourly
  - Arctic OSINT:           every 2 hours
  - NORAD News:             every 6 hours
  - Taxonomy scoring:       every 6 hours
  - SIPRI transfers:        daily 2 AM
  - World Bank indicators:  daily 3 AM
  - Cobalt feeds (7 src):   daily 5 AM
  - Canadian Sanctions:     daily 6 AM
  - OFAC SDN:               daily 6:30 AM
  - Parliament NDDN:        daily 8 AM
  - Trade data (4 nations): weekly Monday 2-3 AM
  - CIA Factbook:           weekly Monday 3 AM
  - DND procurement:        weekly Sunday 2 AM
  - Supplier enrichment:    weekly Sunday 3 AM
  - PSI supply chain:       weekly Sunday 4 AM
  - Supplier scoring:       weekly Sunday 5 AM
  - Sentinel-5P NO2:         daily 3 AM
  - Comtrade cobalt:        monthly 1st 6 AM
"""

from __future__ import annotations

import asyncio
import functools
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.storage.database import SessionLocal
from src.storage.persistence import PersistenceService
from src.storage.models import DefenceSupplier, OwnershipType, ContractStatus
from src.analysis.supplier_risk import SupplierRiskScorer
from src.analysis.risk_taxonomy import RiskTaxonomyScorer
from src.ingestion.sipri_transfers import SIPRITransfersClient, SIPRIQuery, SIPRI_COUNTRY_CODES
from src.ingestion.worldbank import WorldBankClient
from src.ingestion.gdelt_news import GDELTArmsNewsClient
from src.ingestion.flight_tracker import FlightTrackerClient
from src.analysis.cobalt_alert_engine import run_cobalt_alert_engine

logger = logging.getLogger(__name__)


@dataclass
class FeedHealthState:
    """Tracks health of a single scheduled feed."""
    status: str = "ok"              # "ok" | "degraded" | "failed"
    last_success: str | None = None  # ISO timestamp
    last_failure: str | None = None  # ISO timestamp
    failure_count: int = 0
    last_error: str = ""            # truncated to 200 chars
    retry_count: int = 0            # retries since last success
    timeout_s: int = 120


feed_health: dict[str, FeedHealthState] = {}


def resilient_job(name: str, timeout_s: int = 120, max_retries: int = 3):
    """Decorator that wraps a scheduler job with retry, timeout, and health tracking."""
    backoff_delays = [15, 30, 60]

    def decorator(func):
        feed_health[name] = FeedHealthState(timeout_s=timeout_s)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            state = feed_health[name]
            last_err = None

            for attempt in range(1, max_retries + 1):
                try:
                    await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_s)
                    # Success — self-heal
                    state.status = "ok"
                    state.last_success = datetime.now(timezone.utc).isoformat()
                    state.failure_count = 0
                    state.retry_count = 0
                    state.last_error = ""
                    return
                except asyncio.TimeoutError:
                    last_err = f"Timeout after {timeout_s}s"
                    logger.warning("[resilient] %s attempt %d/%d timed out after %ds", name, attempt, max_retries, timeout_s)
                except Exception as e:
                    last_err = str(e)[:200]
                    logger.warning("[resilient] %s attempt %d/%d failed: %s", name, attempt, max_retries, last_err)

                state.retry_count = attempt
                if attempt < max_retries:
                    delay = backoff_delays[attempt - 1] if attempt - 1 < len(backoff_delays) else 60
                    await asyncio.sleep(delay)

            # All retries exhausted
            state.failure_count += 1
            state.last_failure = datetime.now(timezone.utc).isoformat()
            state.last_error = last_err or "Unknown error"
            state.status = "failed" if state.failure_count >= 3 else "degraded"
            logger.critical("[resilient] %s FAILED after %d attempts (consecutive failures: %d): %s", name, max_retries, state.failure_count, last_err)

        return wrapper
    return decorator


async def ingest_gdelt_news():
    """Fetch and store latest arms trade news."""
    client = GDELTArmsNewsClient()
    articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=100)

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        count = svc.store_news_articles(articles)
        logger.info("[scheduler] GDELT: stored %d new articles", count)
    finally:
        session.close()


async def ingest_military_flights():
    """Fetch and store military transport flight positions."""
    client = FlightTrackerClient()
    flights = await client.fetch_transport_aircraft()

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        count = svc.store_flight_positions(flights)
        logger.info("[scheduler] Flights: stored %d transport positions", count)
    finally:
        session.close()


async def ingest_sipri_transfers():
    """Fetch SIPRI transfers for all tracked countries."""
    client = SIPRITransfersClient()
    all_records = []

    # Fetch exports for all major exporting countries
    for country_name, code in SIPRI_COUNTRY_CODES.items():
        try:
            query = SIPRIQuery(
                seller_country_codes=[code],
                low_year=2000,
                high_year=2025,
            )
            records = await client.fetch_transfers(query)
            all_records.extend(records)
            logger.info("[scheduler] SIPRI: fetched %d records for %s exports", len(records), country_name)
        except Exception as e:
            logger.warning("[scheduler] SIPRI fetch failed for %s: %s", country_name, e)

    # Also fetch imports for adversary and watchlist nations
    import_countries = ["Russia", "China", "India", "Iran", "DPRK", "Saudi Arabia",
                        "Egypt", "UAE", "Pakistan", "Algeria", "Myanmar"]
    for country_name in import_countries:
        code = SIPRI_COUNTRY_CODES.get(country_name)
        if not code:
            continue
        try:
            query = SIPRIQuery(
                buyer_country_codes=[code],
                low_year=2000,
                high_year=2025,
            )
            records = await client.fetch_transfers(query)
            all_records.extend(records)
            logger.info("[scheduler] SIPRI: fetched %d records for %s imports", len(records), country_name)
        except Exception as e:
            logger.warning("[scheduler] SIPRI import fetch failed for %s: %s", country_name, e)

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        count = svc.store_sipri_transfers(all_records)
        logger.info("[scheduler] SIPRI: stored %d new transfers total", count)
    finally:
        session.close()


async def ingest_worldbank_indicators():
    """Fetch World Bank arms trade indicators globally."""
    client = WorldBankClient()
    records = await client.fetch_arms_trade_data(country="all", start_year=2000, end_year=2025)

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        count = svc.store_trade_indicators(records)
        logger.info("[scheduler] World Bank: stored %d new indicators", count)
    finally:
        session.close()


async def refresh_supply_chain():
    """Refresh PSI supply chain data (materials, BOM, risk scores)."""
    from src.analysis.supply_chain_seed import SupplyChainSeeder

    session = SessionLocal()
    try:
        seeder = SupplyChainSeeder(session)
        counts = seeder.seed_all()
        logger.info("[scheduler] PSI refresh: %s", counts)
    finally:
        session.close()


async def ingest_procurement():
    """Fetch and store DND procurement contracts from Open Canada."""
    from src.ingestion.procurement_scraper import ProcurementScraperClient
    client = ProcurementScraperClient()
    records = await client.fetch_dnd_contracts()

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        for rec in records:
            supplier = svc.upsert_supplier(
                name=rec.vendor_name_normalized,
                sector=rec.sector,
            )
            svc.upsert_contract(
                supplier_id=supplier.id,
                contract_number=rec.contract_number,
                contract_value_cad=rec.contract_value_cad,
                description=rec.description,
                department=rec.department,
                award_date=rec.award_date,
                end_date=rec.end_date,
                is_sole_source=rec.is_sole_source,
                sector=rec.sector,
                status=ContractStatus.ACTIVE if not rec.end_date or rec.end_date >= date.today() else ContractStatus.COMPLETED,
            )
        logger.info("[scheduler] Procurement: stored %d contracts", len(records))
    finally:
        session.close()


async def enrich_suppliers():
    """Enrich supplier records with Wikidata ownership data."""
    from src.ingestion.corporate_graph import CorporateGraphClient
    corp_client = CorporateGraphClient()

    session = SessionLocal()
    try:
        suppliers = session.query(DefenceSupplier).filter(
            DefenceSupplier.parent_company.is_(None)
        ).all()
        enriched = 0
        for s in suppliers:
            entity = await corp_client.fetch_company_ownership(s.name)
            if entity and entity.parent_name:
                s.parent_company = entity.parent_name
                s.parent_country = entity.country
                s.ownership_type = OwnershipType.FOREIGN_SUBSIDIARY if entity.country and entity.country != "Canada" else s.ownership_type
                enriched += 1
        session.commit()
        logger.info("[scheduler] Enriched %d suppliers with ownership data", enriched)
    finally:
        session.close()


async def score_suppliers():
    """Compute risk scores for all defence suppliers."""
    session = SessionLocal()
    try:
        scorer = SupplierRiskScorer(session)
        count = scorer.score_all_suppliers()
        logger.info("[scheduler] Scored %d suppliers", count)
    finally:
        session.close()


async def score_taxonomy():
    """Refresh DND risk taxonomy scores (live + seeded drift)."""
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.score_all()
        logger.info("[scheduler] Taxonomy scoring complete")
        # Generate COA recommendations from updated scores
        from src.analysis.mitigation_playbook import MitigationPlaybook
        playbook = MitigationPlaybook(session)
        coa_result = playbook.generate_all_coas()
        logger.info("[scheduler] COA generation: %s", coa_result)
    finally:
        session.close()


async def refresh_cobalt_feeds():
    """Refresh all cobalt-specific data feeds with fallback detection.

    Each cobalt connector returns a 'source' field that includes
    '(fallback)' when live fetch fails. We detect this and log
    at ERROR level so ops monitoring can alert.
    """
    from src.ingestion.bgs_minerals import BGSCobaltClient
    from src.ingestion.nrcan_cobalt import NRCanCobaltClient
    from src.ingestion.sherritt_cobalt import SherrittCobaltClient
    from src.ingestion.osint_feeds import (
        USGSCobaltDataClient, GlencoreProductionClient,
        CMOCProductionClient, IMFCobaltPriceClient,
    )

    results = {}
    fallbacks = []

    # BGS World Mineral Statistics
    bgs = await BGSCobaltClient().fetch_cobalt_production()
    results["bgs"] = len(bgs)
    if bgs and "fallback" in str(bgs[0].get("source", "")).lower():
        fallbacks.append("BGS")

    # NRCan Canadian Cobalt
    nrcan = await NRCanCobaltClient().fetch_canada_cobalt_stats()
    results["nrcan"] = "ok" if nrcan.get("production_tonnes") else "empty"
    if "fallback" in str(nrcan.get("source", "")).lower():
        fallbacks.append("NRCan")

    # USGS Cobalt Data
    usgs = await USGSCobaltDataClient().fetch_cobalt_production()
    results["usgs"] = len(usgs)

    # Sherritt stock + operations
    sherritt = await SherrittCobaltClient().fetch_stock_data()
    results["sherritt_price"] = sherritt.get("price_cad", "n/a")
    if "fallback" in str(sherritt.get("source", "")).lower():
        fallbacks.append("Sherritt")

    # Glencore production
    glencore = await GlencoreProductionClient().fetch_production()
    results["glencore"] = "ok" if glencore else "empty"
    if glencore and "fallback" in str(glencore.get("source", "")).lower():
        fallbacks.append("Glencore")

    # CMOC production
    cmoc = await CMOCProductionClient().fetch_production()
    results["cmoc"] = "ok" if cmoc else "empty"
    if cmoc and "fallback" in str(cmoc.get("source", "")).lower():
        fallbacks.append("CMOC")

    # IMF Cobalt Prices
    imf = await IMFCobaltPriceClient().fetch_cobalt_prices()
    results["imf_prices"] = len(imf)

    logger.info("[scheduler] Cobalt feeds refreshed: %s", results)

    if fallbacks:
        logger.error(
            "[scheduler] COBALT FALLBACK ALERT: %d/%d feeds returned stale fallback data: %s. "
            "Live API fetch may be failing — investigate immediately.",
            len(fallbacks), 7, ", ".join(fallbacks),
        )


async def ingest_gc_defence_news():
    """Fetch latest Government of Canada defence news."""
    from src.ingestion.gc_defence_news import GCDefenceNewsClient
    client = GCDefenceNewsClient()
    articles = await client.fetch_all(filter_defence=True)
    logger.info("[scheduler] GC Defence News: fetched %d articles", len(articles))


async def ingest_nato_news():
    """Fetch latest NATO news."""
    from src.ingestion.nato_news import NATONewsClient
    client = NATONewsClient()
    articles = await client.fetch_latest()
    logger.info("[scheduler] NATO News: fetched %d articles", len(articles))


async def ingest_norad_news():
    """Fetch NORAD press releases."""
    from src.ingestion.norad_news import NORADNewsClient
    client = NORADNewsClient()
    releases = await client.fetch_press_releases()
    logger.info("[scheduler] NORAD: fetched %d press releases", len(releases))


async def ingest_canadian_sanctions():
    """Fetch Canadian SEMA/JVCFOA sanctions list."""
    from src.ingestion.canadian_sanctions import CanadianSanctionsClient
    client = CanadianSanctionsClient()
    entries = await client.fetch_sanctions()
    logger.info("[scheduler] Canadian Sanctions: fetched %d entries", len(entries))


async def ingest_arctic_osint():
    """Fetch Arctic OSINT news from 3 feeds."""
    from src.ingestion.arctic_news import ArcticNewsClient
    client = ArcticNewsClient()
    articles = await client.fetch_all(filter_security=False)
    logger.info("[scheduler] Arctic OSINT: fetched %d articles", len(articles))


async def ingest_parliament_nddn():
    """Fetch NDDN committee activity."""
    from src.ingestion.parliament_nddn import ParliamentNDDNClient
    client = ParliamentNDDNClient()
    activities = await client.fetch_activities()
    logger.info("[scheduler] NDDN: fetched %d activities", len(activities))


async def ingest_census_trade():
    """Fetch US Census monthly arms trade (HS Chapter 93)."""
    from src.ingestion.census_trade import CensusTradeClient
    client = CensusTradeClient()
    exports = await client.fetch_us_exports()
    imports = await client.fetch_us_imports()
    logger.info("[scheduler] US Census Trade: %d export + %d import records", len(exports), len(imports))


async def ingest_uk_hmrc_trade():
    """Fetch UK HMRC monthly arms trade (OData API)."""
    from src.ingestion.uk_hmrc_trade import UKHMRCTradeClient
    client = UKHMRCTradeClient()
    records = await client.fetch_uk_arms_trade()
    logger.info("[scheduler] UK HMRC Trade: fetched %d records", len(records))


async def ingest_eurostat_trade():
    """Fetch Eurostat EU monthly arms trade (Comext SDMX)."""
    from src.ingestion.eurostat_trade import EurostatTradeClient
    client = EurostatTradeClient()
    records = await client.fetch_eu_arms_trade()
    logger.info("[scheduler] Eurostat Trade: fetched %d records", len(records))


async def ingest_statcan_trade():
    """Fetch Statistics Canada monthly arms trade (CIMT)."""
    from src.ingestion.statcan_trade import StatCanTradeClient
    client = StatCanTradeClient()
    records = await client.fetch_canada_arms_trade()
    logger.info("[scheduler] StatCan Trade: fetched %d records", len(records))


async def ingest_defense_news_rss():
    """Fetch defense news from 4 RSS feeds."""
    from src.ingestion.defense_news_rss import DefenseNewsRSSClient
    client = DefenseNewsRSSClient()
    articles = await client.fetch_all_feeds()
    logger.info("[scheduler] Defense News RSS: fetched %d articles", len(articles))


async def ingest_sanctions_ofac():
    """Fetch OFAC SDN sanctions list."""
    from src.ingestion.sanctions import SanctionsClient
    client = SanctionsClient()
    entries = await client.fetch_ofac_sdn_list()
    logger.info("[scheduler] OFAC SDN: fetched %d entries", len(entries))


async def ingest_cia_factbook():
    """Fetch CIA World Factbook military data for key nations."""
    from src.ingestion.cia_factbook import CIAFactbookClient
    client = CIAFactbookClient()
    records = await client.fetch_military_data()
    logger.info("[scheduler] CIA Factbook: fetched %d country records", len(records))


async def _comtrade_cobalt_inner():
    """Fetch Comtrade cobalt bilateral trade flows."""
    import os
    from src.ingestion.comtrade import ComtradeMaterialsClient
    key = os.getenv("UN_COMTRADE_API_KEY")
    if not key:
        logger.error(
            "[scheduler] UN_COMTRADE_API_KEY not set — Comtrade cobalt bilateral "
            "queries DISABLED. Set the env var to enable (free registration at comtradeplus.un.org)."
        )
        return
    client = ComtradeMaterialsClient(subscription_key=key)
    records = await client.fetch_cobalt_bilateral_flows()
    logger.info("Comtrade cobalt bilateral: fetched %d records", len(records))


async def refresh_usgs_minerals():
    """Fetch live USGS production data for all 30 defense minerals."""
    from src.ingestion.critical_minerals import CriticalMineralsClient
    client = CriticalMineralsClient()
    try:
        fetch = getattr(client, "fetch_all_live_production", None)
        if fetch is None:
            results = await client.fetch_all_summaries()
            logger.info("[scheduler] USGS minerals (summaries): %d fetched", len(results))
        else:
            results = await fetch()
            logger.info("[scheduler] USGS minerals: %d minerals with live data", len(results))
    finally:
        await client.close()


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the ingestion scheduler."""
    scheduler = AsyncIOScheduler()

    # High-frequency: real-time tracking
    scheduler.add_job(
        resilient_job("flights", timeout_s=30)(ingest_military_flights),
        trigger=IntervalTrigger(minutes=5),
        id="flights",
        name="Military flight tracker",
        max_instances=1,
    )

    # Medium-frequency: news monitoring
    scheduler.add_job(
        resilient_job("gdelt", timeout_s=60)(ingest_gdelt_news),
        trigger=IntervalTrigger(minutes=15),
        id="gdelt",
        name="GDELT arms trade news",
        max_instances=1,
    )

    # Cobalt-specific alert engine (every 30 minutes)
    scheduler.add_job(
        resilient_job("cobalt_alerts", timeout_s=90)(run_cobalt_alert_engine),
        trigger=IntervalTrigger(minutes=30),
        id="cobalt_alerts",
        name="Cobalt supply chain alert engine",
        max_instances=1,
    )

    # Low-frequency: structured databases (daily at 2 AM)
    scheduler.add_job(
        resilient_job("sipri")(ingest_sipri_transfers),
        trigger=CronTrigger(hour=2, minute=0),
        id="sipri",
        name="SIPRI arms transfers",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("worldbank")(ingest_worldbank_indicators),
        trigger=CronTrigger(hour=3, minute=0),
        id="worldbank",
        name="World Bank indicators",
        max_instances=1,
    )

    # PSI: weekly supply chain refresh (Sunday 4 AM)
    scheduler.add_job(
        resilient_job("psi_supply_chain")(refresh_supply_chain),
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="psi_supply_chain",
        name="PSI supply chain refresh",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("procurement_scraper")(ingest_procurement),
        CronTrigger(day_of_week="sun", hour=2),
        id="procurement_scraper",
        name="DND procurement scraper",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        resilient_job("supplier_enrichment")(enrich_suppliers),
        CronTrigger(day_of_week="sun", hour=3),
        id="supplier_enrichment",
        name="Supplier ownership enrichment",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        resilient_job("supplier_scoring")(score_suppliers),
        CronTrigger(day_of_week="sun", hour=5),
        id="supplier_scoring",
        name="Supplier risk scoring",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("taxonomy_scoring")(score_taxonomy),
        IntervalTrigger(hours=6),
        id="taxonomy_scoring",
        name="DND risk taxonomy scoring",
        replace_existing=True,
        max_instances=1,
    )

    # Cobalt-specific data feeds (daily at 5 AM)
    scheduler.add_job(
        resilient_job("cobalt_feeds", timeout_s=180)(refresh_cobalt_feeds),
        CronTrigger(hour=5, minute=0),
        id="cobalt_feeds",
        name="Cobalt supply chain data feeds (BGS, NRCan, USGS, Sherritt, Glencore, CMOC)",
        replace_existing=True,
        max_instances=1,
    )

    # ── Canada Intel fresh feeds ──

    scheduler.add_job(
        resilient_job("gc_defence_news", timeout_s=60)(ingest_gc_defence_news),
        trigger=IntervalTrigger(minutes=30),
        id="gc_defence_news",
        name="GC Defence News (DND/GAC/Public Safety)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("nato_news", timeout_s=60)(ingest_nato_news),
        trigger=IntervalTrigger(hours=1),
        id="nato_news",
        name="NATO News RSS",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("norad_news", timeout_s=60)(ingest_norad_news),
        trigger=IntervalTrigger(hours=6),
        id="norad_news",
        name="NORAD Press Releases",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("canadian_sanctions")(ingest_canadian_sanctions),
        trigger=CronTrigger(hour=6, minute=0),
        id="canadian_sanctions",
        name="Canadian Sanctions (GAC SEMA)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("arctic_osint", timeout_s=60)(ingest_arctic_osint),
        trigger=IntervalTrigger(hours=2),
        id="arctic_osint",
        name="Arctic OSINT News (3 feeds)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("parliament_nddn")(ingest_parliament_nddn),
        trigger=CronTrigger(hour=8, minute=0),
        id="parliament_nddn",
        name="Parliament NDDN Committee",
        replace_existing=True,
        max_instances=1,
    )

    # Comtrade cobalt bilateral trade flows — monthly
    scheduler.add_job(
        resilient_job("comtrade_cobalt", timeout_s=180)(_comtrade_cobalt_inner),
        trigger=CronTrigger(day=1, hour=6, minute=0),
        id="comtrade_cobalt",
        name="Comtrade cobalt bilateral flows",
        max_instances=1,
    )

    # ── Trade data feeds (weekly Monday, staggered to avoid concurrent load) ──

    scheduler.add_job(
        resilient_job("census_trade")(ingest_census_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="census_trade",
        name="US Census monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("uk_hmrc_trade")(ingest_uk_hmrc_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=15),
        id="uk_hmrc_trade",
        name="UK HMRC monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("eurostat_trade")(ingest_eurostat_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=30),
        id="eurostat_trade",
        name="Eurostat EU monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("statcan_trade")(ingest_statcan_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=45),
        id="statcan_trade",
        name="Statistics Canada monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("defense_news_rss", timeout_s=60)(ingest_defense_news_rss),
        trigger=IntervalTrigger(minutes=30),
        id="defense_news_rss",
        name="Defense News RSS (4 feeds)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("ofac_sdn")(ingest_sanctions_ofac),
        trigger=CronTrigger(hour=6, minute=30),
        id="ofac_sdn",
        name="OFAC SDN sanctions list",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("cia_factbook")(ingest_cia_factbook),
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="cia_factbook",
        name="CIA World Factbook military data",
        replace_existing=True,
        max_instances=1,
    )

    # USGS mineral production (daily at 5:30 AM)
    scheduler.add_job(
        resilient_job("usgs_minerals", timeout_s=300)(refresh_usgs_minerals),
        CronTrigger(hour=5, minute=30),
        id="usgs_minerals",
        name="USGS mineral production (30 minerals, CSV+PDF)",
        replace_existing=True,
        max_instances=1,
    )

    # NASA FIRMS facility thermal monitoring (every 6 hours)
    async def refresh_firms_thermal():
        from src.ingestion.firms_thermal import FIRMSThermalClient, _HISTORY_PATH
        client = FIRMSThermalClient()
        # Backfill 30 days of history on first run
        if not _HISTORY_PATH.exists():
            logger.info("[firms_thermal] First run — backfilling 30 days of history")
            await client.backfill_history(days=30)
        data = await client.fetch_all_facilities()
        active = sum(1 for v in data.values() if v["status"] == "ACTIVE")
        logger.info("[firms_thermal] %d/%d facilities ACTIVE", active, len(data))

    scheduler.add_job(
        resilient_job("firms_thermal", timeout_s=120)(refresh_firms_thermal),
        IntervalTrigger(hours=6),
        id="firms_thermal",
        name="NASA FIRMS facility thermal monitoring (18 facilities)",
        replace_existing=True,
        max_instances=1,
    )

    # Sentinel-5P NO2 facility emissions monitoring (daily at 03:00 UTC)
    async def refresh_sentinel_no2():
        from src.ingestion.sentinel_no2 import SentinelNO2Client, _HISTORY_PATH
        client = SentinelNO2Client()
        # Backfill 30 days of history on first run
        if not _HISTORY_PATH.exists():
            logger.info("[sentinel_no2] First run — backfilling 30 days of NO2 history")
            await client.backfill_history(days=30)
        data = await client.fetch_all_facilities()
        emitting = sum(1 for v in data.values() if v["status"] == "EMITTING")
        logger.info("[sentinel_no2] %d/%d facilities EMITTING", emitting, len(data))

    scheduler.add_job(
        resilient_job("sentinel_no2", timeout_s=300)(refresh_sentinel_no2),
        CronTrigger(hour=3, minute=0),
        id="sentinel_no2",
        name="Sentinel-5P NO2 facility emissions (18 facilities)",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler
