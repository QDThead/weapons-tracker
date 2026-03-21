"""Dashboard-specific API endpoints.

Fast, DB-backed endpoints optimized for the dashboard UI.
These avoid hitting external APIs on every page load.
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/transfers")
async def get_all_transfers(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    """Get all transfers from DB with seller/buyer names resolved."""
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT
                c1.name as seller,
                c2.name as buyer,
                at.weapon_description,
                at.order_year,
                at.number_ordered,
                at.number_delivered,
                at.tiv_per_unit,
                at.tiv_total_order,
                at.tiv_delivered,
                at.status,
                at.comments,
                ws.designation as weapon_designation,
                ws.category as weapon_category
            FROM arms_transfers at
            JOIN countries c1 ON at.seller_id = c1.id
            JOIN countries c2 ON at.buyer_id = c2.id
            LEFT JOIN weapon_systems ws ON at.weapon_system_id = ws.id
            ORDER BY at.tiv_delivered DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), {"limit": limit, "offset": offset}).fetchall()

        return [
            {
                "seller": r[0],
                "buyer": r[1],
                "weapon_description": r[2],
                "order_year": r[3],
                "number_ordered": r[4],
                "number_delivered": r[5],
                "tiv_per_unit": r[6],
                "tiv_total_order": r[7],
                "tiv_delivered": r[8],
                "status": r[9],
                "comments": r[10],
                "weapon_designation": r[11],
                "weapon_category": r[12],
            }
            for r in rows
        ]
    finally:
        session.close()


@router.get("/flows")
async def get_trade_flows(
    start_year: int = Query(2015, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
    min_tiv: float = Query(0, ge=0),
):
    """Get aggregated seller→buyer trade flows for visualization."""
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT
                c1.name as seller,
                c2.name as buyer,
                SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv,
                COUNT(*) as deal_count
            FROM arms_transfers at
            JOIN countries c1 ON at.seller_id = c1.id
            JOIN countries c2 ON at.buyer_id = c2.id
            WHERE at.order_year >= :start_year
              AND at.order_year <= :end_year
            GROUP BY c1.name, c2.name
            HAVING SUM(COALESCE(at.tiv_delivered, 0)) >= :min_tiv
            ORDER BY total_tiv DESC
        """), {"start_year": start_year, "end_year": end_year, "min_tiv": min_tiv}).fetchall()

        return [
            {"seller": r[0], "buyer": r[1], "total_tiv": r[2], "deal_count": r[3]}
            for r in rows
        ]
    finally:
        session.close()


@router.get("/country-totals")
async def get_country_totals(
    start_year: int = Query(2015, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get total exports and imports TIV for each country."""
    session = SessionLocal()
    try:
        exports = session.execute(text("""
            SELECT c.name, SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv, COUNT(*) as deals
            FROM arms_transfers at
            JOIN countries c ON at.seller_id = c.id
            WHERE at.order_year >= :start_year AND at.order_year <= :end_year
            GROUP BY c.name
        """), {"start_year": start_year, "end_year": end_year}).fetchall()

        imports = session.execute(text("""
            SELECT c.name, SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv, COUNT(*) as deals
            FROM arms_transfers at
            JOIN countries c ON at.buyer_id = c.id
            WHERE at.order_year >= :start_year AND at.order_year <= :end_year
            GROUP BY c.name
        """), {"start_year": start_year, "end_year": end_year}).fetchall()

        export_map = {r[0]: {"tiv": r[1], "deals": r[2]} for r in exports}
        import_map = {r[0]: {"tiv": r[1], "deals": r[2]} for r in imports}

        all_countries = set(export_map.keys()) | set(import_map.keys())
        return [
            {
                "country": c,
                "exports_tiv": export_map.get(c, {}).get("tiv", 0),
                "export_deals": export_map.get(c, {}).get("deals", 0),
                "imports_tiv": import_map.get(c, {}).get("tiv", 0),
                "import_deals": import_map.get(c, {}).get("deals", 0),
            }
            for c in sorted(all_countries)
        ]
    finally:
        session.close()


@router.get("/weapon-types")
async def get_weapon_type_breakdown(
    start_year: int = Query(2015, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get deal counts and TIV by weapon description."""
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT
                at.weapon_description,
                SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv,
                COUNT(*) as deal_count
            FROM arms_transfers at
            WHERE at.order_year >= :start_year AND at.order_year <= :end_year
            GROUP BY at.weapon_description
            ORDER BY total_tiv DESC
        """), {"start_year": start_year, "end_year": end_year}).fetchall()

        return [
            {"weapon_type": r[0], "total_tiv": r[1], "deal_count": r[2]}
            for r in rows
        ]
    finally:
        session.close()


def _parse_years(years: str) -> list[int]:
    """Parse a comma-separated year string, raising HTTPException on bad input."""
    try:
        return [int(y.strip()) for y in years.split(",")]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid year format. Expected comma-separated integers.")


# Simple in-memory cache for Comtrade data (annual data, TTL = 1 hour)
_comtrade_cache: dict[str, tuple[float, list]] = {}
_COMTRADE_TTL = 3600


@router.get("/comtrade/exports")
async def get_comtrade_exports(
    years: str = Query("2020,2021,2022,2023", description="Comma-separated years"),
):
    """Get real USD arms export values from UN Comtrade (top exporters). Cached for 1 hour."""
    cache_key = f"exports:{years}"
    cached = _comtrade_cache.get(cache_key)
    if cached and time.time() - cached[0] < _COMTRADE_TTL:
        return cached[1]

    try:
        from src.ingestion.comtrade import ComtradeClient

        year_list = _parse_years(years)
        client = ComtradeClient()
        records = await client.fetch_global_summary(year_list)

        result = [
            {
                "reporter": r.reporter,
                "reporter_iso": r.reporter_iso,
                "partner": r.partner,
                "year": r.year,
                "flow": r.flow,
                "trade_value_usd": r.trade_value_usd,
            }
            for r in records
        ]
        _comtrade_cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Comtrade exports fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch Comtrade data")


@router.get("/comtrade/country/{country_name}")
async def get_comtrade_country(
    country_name: str,
    years: str = Query("2022,2023", description="Comma-separated years"),
):
    """Get UN Comtrade arms trade data for a specific country (exports + imports)."""
    cache_key = f"country:{country_name}:{years}"
    cached = _comtrade_cache.get(cache_key)
    if cached and time.time() - cached[0] < _COMTRADE_TTL:
        return cached[1]

    try:
        from src.ingestion.comtrade import ComtradeClient

        year_list = _parse_years(years)
        client = ComtradeClient()

        exports = await client.fetch_country_exports(country_name, year_list)
        await asyncio.sleep(1.5)  # Comtrade rate limit
        imports = await client.fetch_country_imports(country_name, year_list)

        result = {
            "country": country_name,
            "exports": [
                {
                    "partner": r.partner,
                    "year": r.year,
                    "hs_code": r.hs_code,
                    "hs_description": r.hs_description,
                    "trade_value_usd": r.trade_value_usd,
                }
                for r in exports
            ],
            "imports": [
                {
                    "partner": r.partner,
                    "year": r.year,
                    "hs_code": r.hs_code,
                    "hs_description": r.hs_description,
                    "trade_value_usd": r.trade_value_usd,
                }
                for r in imports
            ],
        }
        _comtrade_cache[cache_key] = (time.time(), result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Comtrade country fetch failed for %s: %s", country_name, e)
        raise HTTPException(status_code=502, detail="Failed to fetch Comtrade data")


# ── Defense News RSS ──

_news_cache: dict[str, tuple[float, list]] = {}
_NEWS_TTL = 900  # 15 minutes


@router.get("/news/live")
async def get_live_defense_news():
    """Get live defense news from RSS feeds. Cached for 15 minutes."""
    cache_key = "rss_news"
    cached = _news_cache.get(cache_key)
    if cached and time.time() - cached[0] < _NEWS_TTL:
        return cached[1]

    try:
        from src.ingestion.defense_news_rss import DefenseNewsRSSClient

        client = DefenseNewsRSSClient()
        articles = await client.fetch_all_feeds(filter_arms=True)
        result = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "summary": a.summary[:200],
            }
            for a in articles[:50]
        ]
        _news_cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("RSS news fetch failed: %s", e)
        return []


# ── DSCA Arms Sales ──

_dsca_cache: dict[str, tuple[float, list]] = {}
_DSCA_TTL = 3600  # 1 hour


@router.get("/dsca/recent")
async def get_recent_dsca_sales(count: int = Query(20, ge=1, le=50)):
    """Get recent US arms sale notifications from the Federal Register. Cached 1 hour."""
    cache_key = f"dsca:{count}"
    cached = _dsca_cache.get(cache_key)
    if cached and time.time() - cached[0] < _DSCA_TTL:
        return cached[1]

    try:
        from src.ingestion.dsca_sales import DSCASalesClient

        client = DSCASalesClient()
        sales = await client.fetch_recent_sales(count=count)
        result = [
            {
                "date": s.publication_date,
                "buyer": s.buyer_country,
                "value_usd": s.total_value_usd,
                "weapons": s.weapon_systems,
                "transmittal": s.transmittal_number,
                "url": s.url,
            }
            for s in sales
        ]
        _dsca_cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("DSCA fetch failed: %s", e)
        return []


# ── US Census Monthly Trade ──

_census_cache: dict[str, tuple[float, list]] = {}
_CENSUS_TTL = 3600  # 1 hour


@router.get("/census/monthly")
async def get_us_monthly_arms_trade():
    """Get monthly US arms trade data (HS 93) from Census Bureau. Cached 1 hour."""
    cache_key = "census_monthly"
    cached = _census_cache.get(cache_key)
    if cached and time.time() - cached[0] < _CENSUS_TTL:
        return cached[1]

    try:
        from src.ingestion.census_trade import CensusTradeClient

        client = CensusTradeClient()
        exports = await client.fetch_us_exports()

        result = {
            "months": {},
            "top_partners": {},
        }

        for r in exports:
            key = f"{r.year}-{r.month:02d}"
            if key not in result["months"]:
                result["months"][key] = 0
            result["months"][key] += r.value_usd

            if r.partner_country not in result["top_partners"]:
                result["top_partners"][r.partner_country] = 0
            result["top_partners"][r.partner_country] += r.value_usd

        # Sort partners
        result["top_partners"] = dict(
            sorted(result["top_partners"].items(), key=lambda x: x[1], reverse=True)[:20]
        )
        result["latest_month"] = max(result["months"].keys()) if result["months"] else None
        result["total_records"] = len(exports)

        _census_cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Census trade fetch failed: %s", e)
        return {"months": {}, "top_partners": {}, "latest_month": None}
