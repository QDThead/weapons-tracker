"""Scheduled ingestion pipeline.

Runs each data connector on its natural update cadence and persists
results to the database.

Schedule:
  - GDELT arms news:       every 15 minutes
  - Military flights:      every 5 minutes
  - Maritime vessels:       every 5 minutes
  - SIPRI transfers:       daily (checks for new annual data)
  - World Bank indicators: daily
  - SIPRI Top 100:         daily
  - PSI supply chain seed: weekly (refreshes BOM + material data)
"""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from src.storage.database import SessionLocal
from src.storage.persistence import PersistenceService
from src.ingestion.sipri_transfers import SIPRITransfersClient, SIPRIQuery, SIPRI_COUNTRY_CODES
from src.ingestion.worldbank import WorldBankClient
from src.ingestion.gdelt_news import GDELTArmsNewsClient
from src.ingestion.flight_tracker import FlightTrackerClient

logger = logging.getLogger(__name__)


async def ingest_gdelt_news():
    """Fetch and store latest arms trade news."""
    try:
        client = GDELTArmsNewsClient()
        articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=25)

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            count = svc.store_news_articles(articles)
            logger.info("[scheduler] GDELT: stored %d new articles", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] GDELT ingestion failed: %s", e)


async def ingest_military_flights():
    """Fetch and store military transport flight positions."""
    try:
        client = FlightTrackerClient()
        flights = await client.fetch_transport_aircraft()

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            count = svc.store_flight_positions(flights)
            logger.info("[scheduler] Flights: stored %d transport positions", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] Flight ingestion failed: %s", e)


async def ingest_sipri_transfers():
    """Fetch SIPRI transfers for all tracked countries."""
    try:
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

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            count = svc.store_sipri_transfers(all_records)
            logger.info("[scheduler] SIPRI: stored %d new transfers total", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] SIPRI ingestion failed: %s", e)


async def ingest_worldbank_indicators():
    """Fetch World Bank arms trade indicators globally."""
    try:
        client = WorldBankClient()
        records = await client.fetch_arms_trade_data(country="all", start_year=2000, end_year=2025)

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            count = svc.store_trade_indicators(records)
            logger.info("[scheduler] World Bank: stored %d new indicators", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] World Bank ingestion failed: %s", e)


async def refresh_supply_chain():
    """Refresh PSI supply chain data (materials, BOM, risk scores)."""
    try:
        from src.analysis.supply_chain_seed import SupplyChainSeeder

        session = SessionLocal()
        try:
            seeder = SupplyChainSeeder(session)
            counts = seeder.seed_all()
            logger.info("[scheduler] PSI refresh: %s", counts)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] PSI supply chain refresh failed: %s", e)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the ingestion scheduler."""
    scheduler = AsyncIOScheduler()

    # High-frequency: real-time tracking
    scheduler.add_job(
        ingest_military_flights,
        trigger=IntervalTrigger(minutes=5),
        id="flights",
        name="Military flight tracker",
        max_instances=1,
    )

    # Medium-frequency: news monitoring
    scheduler.add_job(
        ingest_gdelt_news,
        trigger=IntervalTrigger(minutes=15),
        id="gdelt",
        name="GDELT arms trade news",
        max_instances=1,
    )

    # Low-frequency: structured databases (daily at 2 AM)
    scheduler.add_job(
        ingest_sipri_transfers,
        trigger=CronTrigger(hour=2, minute=0),
        id="sipri",
        name="SIPRI arms transfers",
        max_instances=1,
    )

    scheduler.add_job(
        ingest_worldbank_indicators,
        trigger=CronTrigger(hour=3, minute=0),
        id="worldbank",
        name="World Bank indicators",
        max_instances=1,
    )

    # PSI: weekly supply chain refresh (Sunday 4 AM)
    scheduler.add_job(
        refresh_supply_chain,
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="psi_supply_chain",
        name="PSI supply chain refresh",
        max_instances=1,
    )

    return scheduler
