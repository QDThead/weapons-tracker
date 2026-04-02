"""Dashboard-specific API endpoints.

Fast, DB-backed endpoints optimized for the dashboard UI.
These avoid hitting external APIs on every page load.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from src.storage.database import SessionLocal
from src.utils.cache import TTLCache

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
_comtrade_cache = TTLCache(ttl_seconds=3600, max_size=200)


@router.get("/comtrade/exports")
async def get_comtrade_exports(
    years: str = Query("2020,2021,2022,2023", description="Comma-separated years"),
):
    """Get real USD arms export values from UN Comtrade (top exporters). Cached for 1 hour."""
    cache_key = f"exports:{years}"
    cached = _comtrade_cache.get(cache_key)
    if cached is not None:
        return cached

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
        _comtrade_cache.set(cache_key, result)
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
    if cached is not None:
        return cached

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
        _comtrade_cache.set(cache_key, result)
        return result
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except Exception as e:
        logger.error("Comtrade country fetch failed for %s: %s", country_name, e)
        raise HTTPException(status_code=502, detail="Failed to fetch Comtrade data")


# ── Adversary Trade Buyer-Side Mirror ──

_buyer_mirror_cache = TTLCache(ttl_seconds=3600, max_size=50)


@router.get("/adversary-trade/buyer-mirror")
async def get_buyer_side_mirror(
    seller: str = Query(
        ...,
        description="Seller country name: 'Russia' or 'China'",
    ),
    years: str = Query(
        "2022,2023",
        description="Comma-separated years to query",
    ),
):
    """Buyer-side mirror: see what buyer countries report importing from Russia/China.

    Russia and China don't publish reliable arms export data. But their buyers
    do report imports. This endpoint queries known major buyers of the given
    seller for their HS 93 (arms & ammunition) import records from UN Comtrade,
    then aggregates by buyer country, year, and HS code category.

    Cached for 1 hour.
    """
    cache_key = f"buyer_mirror:{seller}:{years}"
    cached = _buyer_mirror_cache.get(cache_key)
    if cached is not None:
        return cached

    year_list = _parse_years(years)

    try:
        from src.ingestion.comtrade import ComtradeClient, ADVERSARY_BUYER_CODES

        if seller not in ADVERSARY_BUYER_CODES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unsupported seller '{seller}'. "
                    f"Supported: {', '.join(ADVERSARY_BUYER_CODES.keys())}"
                ),
            )

        client = ComtradeClient()
        records = await client.fetch_buyer_side_imports(seller, year_list)

        # Aggregate by buyer country
        by_buyer: dict[str, dict] = {}
        for r in records:
            buyer = r.reporter
            if buyer not in by_buyer:
                by_buyer[buyer] = {
                    "buyer": buyer,
                    "buyer_iso": r.reporter_iso,
                    "total_usd": 0.0,
                    "by_year": {},
                    "by_hs_code": {},
                }
            by_buyer[buyer]["total_usd"] += r.trade_value_usd

            # Year breakdown
            yr_key = str(r.year)
            by_buyer[buyer]["by_year"].setdefault(yr_key, 0.0)
            by_buyer[buyer]["by_year"][yr_key] += r.trade_value_usd

            # HS code breakdown
            hs_key = r.hs_code
            if hs_key not in by_buyer[buyer]["by_hs_code"]:
                by_buyer[buyer]["by_hs_code"][hs_key] = {
                    "description": r.hs_description,
                    "total_usd": 0.0,
                }
            by_buyer[buyer]["by_hs_code"][hs_key]["total_usd"] += r.trade_value_usd

        # Sort buyers by total value descending
        buyers_sorted = sorted(by_buyer.values(), key=lambda b: b["total_usd"], reverse=True)

        # Grand totals
        grand_total_usd = sum(b["total_usd"] for b in buyers_sorted)
        total_by_year: dict[str, float] = {}
        for b in buyers_sorted:
            for yr, val in b["by_year"].items():
                total_by_year.setdefault(yr, 0.0)
                total_by_year[yr] += val

        result = {
            "seller": seller,
            "years": year_list,
            "methodology": (
                "Buyer-side mirror: querying import reports filed by known major "
                "buyers of this seller. HS Chapter 93 (arms and ammunition). "
                "Data from UN Comtrade."
            ),
            "grand_total_usd": grand_total_usd,
            "total_by_year": dict(sorted(total_by_year.items())),
            "buyer_count": len(buyers_sorted),
            "record_count": len(records),
            "buyers": buyers_sorted,
        }

        _buyer_mirror_cache.set(cache_key, result)
        return result

    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request parameters")
    except Exception as e:
        logger.error("Buyer-side mirror fetch failed for %s: %s", seller, e)
        raise HTTPException(status_code=502, detail="Failed to fetch buyer-side mirror data")


# ── Defense News RSS ──

_news_cache = TTLCache(ttl_seconds=900, max_size=100)


@router.get("/news/live")
async def get_live_defense_news():
    """Get live defense news from RSS feeds. Cached for 15 minutes."""
    cache_key = "rss_news"
    cached = _news_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.defense_news_rss import DefenseNewsRSSClient

        client = DefenseNewsRSSClient()
        articles = await client.fetch_all_feeds(filter_arms=True)
        rss_articles = [
            {
                "title": a.title,
                "url": a.url,
                "source": a.source,
                "published_at": a.published_at.isoformat() if a.published_at else None,
                "summary": a.summary[:200],
                "language": "English",
            }
            for a in articles[:30]
        ]

        # Also include GDELT multilingual news from DB
        from src.storage.models import ArmsTradeNews
        session = SessionLocal()
        try:
            db_news = session.query(ArmsTradeNews).order_by(
                ArmsTradeNews.published_at.desc()
            ).limit(30).all()
            db_articles = [
                {
                    "title": n.title,
                    "url": n.url,
                    "source": n.source_name or "GDELT",
                    "published_at": n.published_at.isoformat() if n.published_at else None,
                    "summary": "",
                    "language": n.language or "English",
                }
                for n in db_news
            ]
        finally:
            session.close()

        # Merge and deduplicate by URL, sort by date
        seen_urls = set()
        merged = []
        for a in rss_articles + db_articles:
            if a["url"] not in seen_urls:
                seen_urls.add(a["url"])
                merged.append(a)
        merged.sort(key=lambda x: x.get("published_at") or "", reverse=True)
        result = merged[:50]

        _news_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("RSS news fetch failed: %s", e)
        return []


# ── DSCA Arms Sales ──

_dsca_cache = TTLCache(ttl_seconds=3600, max_size=50)


@router.get("/dsca/recent")
async def get_recent_dsca_sales(count: int = Query(20, ge=1, le=50)):
    """Get recent US arms sale notifications from the Federal Register. Cached 1 hour."""
    cache_key = f"dsca:{count}"
    cached = _dsca_cache.get(cache_key)
    if cached is not None:
        return cached

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
        _dsca_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("DSCA fetch failed: %s", e)
        return []


# ── US Census Monthly Trade ──

_census_cache = TTLCache(ttl_seconds=3600, max_size=50)


@router.get("/census/monthly")
async def get_us_monthly_arms_trade():
    """Get monthly US arms trade data (HS 93) from Census Bureau. Cached 1 hour."""
    cache_key = "census_monthly"
    cached = _census_cache.get(cache_key)
    if cached is not None:
        return cached

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

        _census_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("Census trade fetch failed: %s", e)
        return {"months": {}, "top_partners": {}, "latest_month": None}


# ── NATO Defence Expenditure ──

_nato_cache = TTLCache(ttl_seconds=86400, max_size=50)


@router.get("/nato/spending")
async def get_nato_spending(
    country: str | None = Query(None, description="Filter by country name (case-insensitive)"),
    year: int | None = Query(None, ge=2014, le=2025, description="Filter by single year"),
    include_aggregates: bool = Query(False, description="Include NATO Total and Europe+Canada aggregates"),
):
    """Get NATO defence expenditure data for all member countries.

    Returns spending in million USD (current and constant 2021 prices),
    spending as % of GDP, and annual real change. Data spans 2014-2025
    (2024-2025 are estimates). Cached for 24 hours.
    """
    cache_key = f"nato:{country}:{year}:{include_aggregates}"
    cached = _nato_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.nato_spending import NATOSpendingClient

        client = NATOSpendingClient()
        records = await client.fetch_spending_data()

        # Apply filters
        filtered = records
        if not include_aggregates:
            filtered = [r for r in filtered if not r.is_aggregate]
        if country:
            country_lower = country.lower()
            filtered = [r for r in filtered if r.country.lower() == country_lower]
        if year is not None:
            filtered = [r for r in filtered if r.year == year]

        result = [
            {
                "country": r.country,
                "year": r.year,
                "spending_current_usd_millions": r.spending_current_usd_millions,
                "spending_constant_usd_millions": r.spending_constant_usd_millions,
                "pct_gdp": r.pct_gdp,
                "annual_real_change_pct": r.annual_real_change_pct,
                "is_estimate": r.is_estimate,
                "is_aggregate": r.is_aggregate,
            }
            for r in filtered
        ]

        _nato_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("NATO spending fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch NATO spending data")


# ── UK HMRC Arms Trade ──

_hmrc_cache = TTLCache(ttl_seconds=3600, max_size=50)


@router.get("/uk-trade/monthly")
async def get_uk_monthly_arms_trade(
    months: str = Query(
        default="",
        description="Comma-separated months in YYYYMM format (e.g. 202501,202502). Defaults to last 6 months.",
    ),
):
    """Get monthly UK arms trade data (HS 93) from HMRC Trade Info. Cached 1 hour."""
    cache_key = f"hmrc_monthly:{months}"
    cached = _hmrc_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.uk_hmrc_trade import UKHMRCTradeClient

        client = UKHMRCTradeClient()
        month_list = [m.strip() for m in months.split(",") if m.strip()] if months else None
        records = await client.fetch_uk_arms_trade(month_list)

        # Aggregate by month
        monthly_totals: dict[str, dict[str, int]] = {}
        partner_totals: dict[str, int] = {}

        for r in records:
            key = f"{r.year}-{r.month:02d}"
            if key not in monthly_totals:
                monthly_totals[key] = {"imports_gbp": 0, "exports_gbp": 0}
            if r.direction == "import":
                monthly_totals[key]["imports_gbp"] += r.value_gbp
            else:
                monthly_totals[key]["exports_gbp"] += r.value_gbp

            if r.partner_country not in partner_totals:
                partner_totals[r.partner_country] = 0
            partner_totals[r.partner_country] += r.value_gbp

        # Sort partners by total value, keep top 20
        top_partners = dict(
            sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        result = {
            "currency": "GBP",
            "months": dict(sorted(monthly_totals.items())),
            "top_partners": top_partners,
            "latest_month": max(monthly_totals.keys()) if monthly_totals else None,
            "total_records": len(records),
        }

        _hmrc_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("HMRC UK trade fetch failed: %s", e)
        return {"currency": "GBP", "months": {}, "top_partners": {}, "latest_month": None}


# ── Eurostat EU Arms Trade ──

_eurostat_cache = TTLCache(ttl_seconds=3600, max_size=50)


@router.get("/eu-trade/monthly")
async def get_eu_monthly_arms_trade(
    reporters: str = Query(
        default="",
        description=(
            "Comma-separated ISO 2-letter reporter codes "
            "(e.g. DE,FR,IT). Defaults to top 6 EU exporters."
        ),
    ),
    start: str = Query(
        default="",
        description="Start period YYYY-MM (defaults to 12 months ago)",
    ),
    end: str = Query(
        default="",
        description="End period YYYY-MM (defaults to current month)",
    ),
):
    """Get monthly EU arms trade data (HS 93) from Eurostat Comext. Cached 1 hour."""
    cache_key = f"eurostat:{reporters}:{start}:{end}"
    cached = _eurostat_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.eurostat_trade import EurostatTradeClient

        client = EurostatTradeClient()
        reporter_list = (
            [r.strip().upper() for r in reporters.split(",") if r.strip()]
            if reporters
            else None
        )
        start_period = start if start else None
        end_period = end if end else None

        records = await client.fetch_eu_arms_trade(
            reporters=reporter_list,
            start_period=start_period,
            end_period=end_period,
        )

        # Aggregate by month
        monthly_totals: dict[str, dict[str, float]] = {}
        reporter_totals: dict[str, float] = {}
        partner_totals: dict[str, float] = {}

        for r in records:
            key = f"{r.year}-{r.month:02d}"
            if key not in monthly_totals:
                monthly_totals[key] = {"imports_eur": 0.0, "exports_eur": 0.0}
            if r.direction == "import":
                monthly_totals[key]["imports_eur"] += r.value_eur
            else:
                monthly_totals[key]["exports_eur"] += r.value_eur

            if r.reporter not in reporter_totals:
                reporter_totals[r.reporter] = 0.0
            reporter_totals[r.reporter] += r.value_eur

            if r.partner not in partner_totals:
                partner_totals[r.partner] = 0.0
            partner_totals[r.partner] += r.value_eur

        # Sort reporters and partners by total value
        top_reporters = dict(
            sorted(reporter_totals.items(), key=lambda x: x[1], reverse=True)
        )
        top_partners = dict(
            sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        result = {
            "currency": "EUR",
            "months": dict(sorted(monthly_totals.items())),
            "top_reporters": top_reporters,
            "top_partners": top_partners,
            "latest_month": max(monthly_totals.keys()) if monthly_totals else None,
            "total_records": len(records),
        }

        _eurostat_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("Eurostat EU trade fetch failed: %s", e)
        return {
            "currency": "EUR",
            "months": {},
            "top_reporters": {},
            "top_partners": {},
            "latest_month": None,
        }


# ── Statistics Canada Arms Trade ──

_statcan_cache = TTLCache(ttl_seconds=86400, max_size=50)


@router.get("/canada-trade/monthly")
async def get_canada_monthly_arms_trade(
    year: int = Query(
        default=0,
        ge=0,
        le=2030,
        description="Year to fetch (e.g. 2025). Defaults to current year.",
    ),
):
    """Get monthly Canadian arms trade data (HS 93) from Statistics Canada CIMT. Cached 24 hours."""
    if year == 0:
        from datetime import datetime
        year = datetime.now().year

    cache_key = f"statcan:{year}"
    cached = _statcan_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.statcan_trade import StatCanTradeClient

        client = StatCanTradeClient()
        records = await client.fetch_canada_arms_trade(year=year)

        # Aggregate by month
        monthly_totals: dict[str, dict[str, int]] = {}
        partner_totals: dict[str, int] = {}

        for r in records:
            key = f"{r.year}-{r.month:02d}"
            if key not in monthly_totals:
                monthly_totals[key] = {"imports_cad": 0, "exports_cad": 0}
            if r.direction == "import":
                monthly_totals[key]["imports_cad"] += r.value_cad
            else:
                monthly_totals[key]["exports_cad"] += r.value_cad

            if r.partner_country not in partner_totals:
                partner_totals[r.partner_country] = 0
            partner_totals[r.partner_country] += r.value_cad

        # Sort partners by total value, keep top 20
        top_partners = dict(
            sorted(partner_totals.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        result = {
            "currency": "CAD",
            "year": year,
            "months": dict(sorted(monthly_totals.items())),
            "top_partners": top_partners,
            "latest_month": max(monthly_totals.keys()) if monthly_totals else None,
            "total_records": len(records),
        }

        _statcan_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("StatCan Canada trade fetch failed: %s", e)
        return {
            "currency": "CAD",
            "year": year,
            "months": {},
            "top_partners": {},
            "latest_month": None,
        }


# ── Russian / Chinese Military Flight Pattern Analysis ──

_flight_analysis_cache = TTLCache(ttl_seconds=300, max_size=20)


@router.get("/flights/analysis")
async def get_flight_pattern_analysis():
    """Analyze current military flights for Russian and Chinese patterns.

    Fetches live ADS-B data from adsb.lol, identifies Russian and Chinese
    military transport aircraft, and flags flights transiting regions of
    interest (Africa, Middle East, South Asia, Arctic).

    Results are cached for 5 minutes.
    """
    cache_key = "flight_analysis"
    cached = _flight_analysis_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.flight_tracker import FlightTrackerClient
        from src.analysis.flight_patterns import FlightPatternAnalyzer

        tracker = FlightTrackerClient()
        flights = await tracker.fetch_military_aircraft()

        analyzer = FlightPatternAnalyzer()
        analysis = analyzer.analyze_current_flights(flights)

        result = asdict(analysis)

        _flight_analysis_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("Flight pattern analysis failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch or analyze flight data")


# ── Arms Sanctions & Embargoes ──

_sanctions_cache = TTLCache(ttl_seconds=3600, max_size=100)


@router.get("/sanctions/embargoes")
async def get_arms_embargoes():
    """Get all countries currently under arms embargoes.

    Returns a curated list of active UN, EU, US, and regional
    arms embargoes with details on scope, imposing bodies, and dates.
    """
    from src.ingestion.sanctions import SanctionsClient

    client = SanctionsClient()
    embargoes = client.get_embargoed_countries()
    return [
        {
            "country": e.country,
            "iso3": e.iso3,
            "embargo_type": e.embargo_type,
            "imposing_bodies": e.imposing_bodies,
            "since_year": e.since_year,
            "description": e.description,
            "notes": e.notes,
        }
        for e in embargoes
    ]


@router.get("/sanctions/check/{country}")
async def check_country_embargo(country: str):
    """Check if a specific country is under an arms embargo.

    Accepts country name (e.g. 'Russia') or ISO3 code (e.g. 'RUS').
    Case-insensitive.
    """
    from src.ingestion.sanctions import SanctionsClient

    client = SanctionsClient()
    return client.check_country(country)


@router.get("/sanctions/ofac-sdn")
async def get_ofac_sdn_defense_entities():
    """Get defense-related entities from the OFAC SDN (Specially Designated Nationals) list.

    Downloads from US Treasury and filters for military/defense keywords.
    Cached for 1 hour.
    """
    cache_key = "ofac_sdn"
    cached = _sanctions_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.sanctions import SanctionsClient

        client = SanctionsClient()
        entities = await client.fetch_ofac_sdn_list(filter_defense=True)
        result = [
            {
                "name": e.name,
                "entity_type": e.entity_type,
                "program": e.program,
                "remarks": e.remarks,
            }
            for e in entities
        ]
        _sanctions_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("OFAC SDN fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch OFAC SDN data")


@router.get("/sanctions/eu")
async def get_eu_sanctions_defense_entities():
    """Get defense-related entries from the EU Consolidated Sanctions list.

    Downloads from EU and filters for military/defense keywords.
    Cached for 1 hour.
    """
    cache_key = "eu_sanctions"
    cached = _sanctions_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        from src.ingestion.sanctions import SanctionsClient

        client = SanctionsClient()
        entries = await client.fetch_eu_sanctions(filter_defense=True)
        result = [
            {
                "name": e.name,
                "entity_type": e.entity_type,
                "programme": e.programme,
                "remark": e.remark,
            }
            for e in entries
        ]
        _sanctions_cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("EU sanctions fetch failed: %s", e)
        raise HTTPException(status_code=502, detail="Failed to fetch EU sanctions data")
