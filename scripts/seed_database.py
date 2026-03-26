"""Initial database seeding script.

Performs a full data load from all sources:
  1. SIPRI Arms Transfers — all major countries (2000-2025)
  2. World Bank indicators — global arms trade + military spending
  3. GDELT news — backfill last 7 days of arms trade news
  4. Military flights — single snapshot of current transport aircraft

Run once to populate the database, then the scheduler maintains it.

Usage:
    python -m scripts.seed_database
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

# Add project root to path
sys.path.insert(0, ".")

from src.storage.database import init_db, SessionLocal
from src.storage.persistence import PersistenceService
from src.ingestion.sipri_transfers import (
    SIPRITransfersClient, SIPRIQuery, SIPRI_COUNTRY_CODES,
)
from src.ingestion.worldbank import WorldBankClient
from src.ingestion.gdelt_news import GDELTArmsNewsClient
from src.ingestion.flight_tracker import FlightTrackerClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("seed")


async def seed_sipri_transfers(svc: PersistenceService):
    """Fetch and store SIPRI arms transfers for all tracked countries."""
    logger.info("=" * 60)
    logger.info("PHASE 1: SIPRI Arms Transfers")
    logger.info("=" * 60)

    client = SIPRITransfersClient(timeout=60.0)
    total_inserted = 0

    for country_name, code in SIPRI_COUNTRY_CODES.items():
        try:
            # Fetch exports
            query = SIPRIQuery(
                seller_country_codes=[code],
                low_year=2000,
                high_year=2025,
            )
            records = await client.fetch_transfers(query)

            if records:
                inserted = svc.store_sipri_transfers(records)
                total_inserted += inserted
                logger.info(
                    "  %s exports: %d records fetched, %d new stored",
                    country_name, len(records), inserted,
                )

            # Be polite to SIPRI servers
            await asyncio.sleep(1.0)

        except Exception as e:
            logger.warning("  Failed to fetch %s: %s", country_name, e)

    logger.info("SIPRI total: %d new transfers stored", total_inserted)
    return total_inserted


async def seed_worldbank_indicators(svc: PersistenceService):
    """Fetch and store World Bank arms trade indicators globally."""
    logger.info("=" * 60)
    logger.info("PHASE 2: World Bank Arms Trade Indicators")
    logger.info("=" * 60)

    client = WorldBankClient(timeout=60.0)

    try:
        records = await client.fetch_arms_trade_data(
            country="all",
            start_year=2000,
            end_year=2025,
        )
        inserted = svc.store_trade_indicators(records)
        logger.info("World Bank: %d records fetched, %d new stored", len(records), inserted)
        return inserted
    except Exception as e:
        logger.error("World Bank fetch failed: %s", e)
        return 0


async def seed_gdelt_news(svc: PersistenceService):
    """Backfill arms trade news from the last 7 days."""
    logger.info("=" * 60)
    logger.info("PHASE 3: GDELT Arms Trade News (7-day backfill)")
    logger.info("=" * 60)

    client = GDELTArmsNewsClient(timeout=30.0)

    try:
        articles = await client.fetch_latest_arms_news(
            timespan_minutes=7 * 24 * 60,  # 7 days
            max_per_query=75,
        )
        inserted = svc.store_news_articles(articles)
        logger.info("GDELT: %d articles fetched, %d new stored", len(articles), inserted)
        return inserted
    except Exception as e:
        logger.error("GDELT fetch failed: %s", e)
        return 0


async def seed_flight_snapshot(svc: PersistenceService):
    """Take a snapshot of current military transport flights."""
    logger.info("=" * 60)
    logger.info("PHASE 4: Military Transport Flight Snapshot")
    logger.info("=" * 60)

    client = FlightTrackerClient()

    try:
        flights = await client.fetch_transport_aircraft()
        inserted = svc.store_flight_positions(flights)
        logger.info("Flights: %d transports detected, %d stored", len(flights), inserted)
        return inserted
    except Exception as e:
        logger.error("Flight snapshot failed: %s", e)
        return 0


async def main():
    start_time = time.time()

    logger.info("Weapons Tracker — Database Seeding")
    logger.info("Initializing database...")
    init_db()

    session = SessionLocal()
    svc = PersistenceService(session)

    try:
        # Run each phase sequentially (SIPRI has rate limits)
        sipri_count = await seed_sipri_transfers(svc)
        wb_count = await seed_worldbank_indicators(svc)
        gdelt_count = await seed_gdelt_news(svc)
        flight_count = await seed_flight_snapshot(svc)

        # Seed taxonomy scores
        from src.analysis.risk_taxonomy import RiskTaxonomyScorer
        scorer = RiskTaxonomyScorer(session)
        taxonomy_count = scorer.seed_initial_scores()
        print(f"  Taxonomy: seeded {taxonomy_count} risk scores across 13 categories")

        elapsed = time.time() - start_time

        logger.info("=" * 60)
        logger.info("SEEDING COMPLETE")
        logger.info("=" * 60)
        logger.info("  SIPRI transfers:    %d new records", sipri_count)
        logger.info("  World Bank indicators: %d new records", wb_count)
        logger.info("  GDELT news articles:   %d new records", gdelt_count)
        logger.info("  Flight snapshots:      %d new records", flight_count)
        logger.info("  Total time: %.1f seconds", elapsed)
        logger.info("")
        logger.info("You can now start the API server:")
        logger.info("  python -m src.main")
        logger.info("")
        logger.info("And query trends at:")
        logger.info("  http://localhost:8000/trends/summary")
        logger.info("  http://localhost:8000/trends/global/volume")
        logger.info("  http://localhost:8000/trends/country/Canada/profile")

    finally:
        session.close()


if __name__ == "__main__":
    asyncio.run(main())
