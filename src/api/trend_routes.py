"""Trend analysis API endpoints.

Provides historical trend data for weapons trade visualization
and analysis. All data comes from the persisted database.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from src.storage.database import SessionLocal
from src.analysis.trends import TrendAnalyzer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trends", tags=["Trends"])


def _get_analyzer() -> tuple[object, TrendAnalyzer]:
    """Create a session and analyzer. Returns (session, analyzer)."""
    session = SessionLocal()
    try:
        return session, TrendAnalyzer(session)
    except Exception:
        session.close()
        raise


# --- Database Summary ---


@router.get("/summary")
async def get_summary():
    """Get overall database summary statistics."""
    session, analyzer = _get_analyzer()
    try:
        return analyzer.summary_stats()
    except Exception as e:
        logger.error("Summary stats fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Global Trends ---


@router.get("/global/volume")
async def get_global_volume(
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get global arms trade volume by year (TIV + deal count)."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.global_volume_by_year(start_year, end_year)
        return [{"year": r.year, "tiv_total": r.tiv_total, "deal_count": r.deal_count} for r in results]
    except Exception as e:
        logger.error("Global volume query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/global/categories")
async def get_global_categories(
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get global arms trade broken down by weapon category."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.global_category_breakdown(start_year, end_year)
        return [
            {
                "category": r.category,
                "tiv_total": r.tiv_total,
                "deal_count": r.deal_count,
                "pct_of_total": r.pct_of_total,
            }
            for r in results
        ]
    except Exception as e:
        logger.error("Global category breakdown failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/global/top-pairs")
async def get_top_trading_pairs(
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
    limit: int = Query(20, ge=1, le=100),
):
    """Get the highest-volume seller→buyer country pairs."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.top_trading_pairs(start_year, end_year, limit)
        return [
            {
                "seller": r.seller,
                "buyer": r.buyer,
                "tiv_total": r.tiv_total,
                "deal_count": r.deal_count,
            }
            for r in results
        ]
    except Exception as e:
        logger.error("Top trading pairs query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Country Trends ---


@router.get("/country/{country}/profile")
async def get_country_profile(
    country: str,
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get a comprehensive arms trade profile for a country.

    Includes total exports/imports, top partners, and weapon category breakdown.
    """
    session, analyzer = _get_analyzer()
    try:
        profile = analyzer.country_profile(country, start_year, end_year)
        if not profile:
            return {"error": f"Country '{country}' not found in database"}

        return {
            "country": profile.country,
            "total_exports_tiv": profile.total_exports_tiv,
            "total_imports_tiv": profile.total_imports_tiv,
            "export_deal_count": profile.export_deal_count,
            "import_deal_count": profile.import_deal_count,
            "top_export_partners": profile.top_export_partners,
            "top_import_partners": profile.top_import_partners,
            "top_weapon_categories": profile.top_weapon_categories,
        }
    except Exception as e:
        logger.error("Country profile fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/country/{country}/exports")
async def get_country_export_trend(
    country: str,
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get a country's arms export volume by year."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.country_exports_by_year(country, start_year, end_year)
        return [{"year": r.year, "tiv_total": r.tiv_total, "deal_count": r.deal_count} for r in results]
    except Exception as e:
        logger.error("Country export trend query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/country/{country}/imports")
async def get_country_import_trend(
    country: str,
    start_year: int = Query(2000, ge=1950, le=2025),
    end_year: int = Query(2025, ge=1950, le=2025),
):
    """Get a country's arms import volume by year."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.country_imports_by_year(country, start_year, end_year)
        return [{"year": r.year, "tiv_total": r.tiv_total, "deal_count": r.deal_count} for r in results]
    except Exception as e:
        logger.error("Country import trend query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Year-Over-Year Changes ---


@router.get("/changes/imports")
async def get_biggest_import_changes(
    year: int = Query(2024, ge=1960, le=2025),
    limit: int = Query(10, ge=1, le=50),
):
    """Find countries with the biggest year-over-year change in arms imports."""
    session, analyzer = _get_analyzer()
    try:
        results = analyzer.biggest_import_changes(year, limit)
        return [
            {
                "country": r.country,
                "year": r.year,
                "prev_year": r.prev_year,
                "tiv_current": r.tiv_current,
                "tiv_previous": r.tiv_previous,
                "change_pct": r.change_pct,
            }
            for r in results
        ]
    except Exception as e:
        logger.error("Import changes query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Defense Companies ---


@router.get("/companies/{company_name}")
async def get_company_trend(
    company_name: str,
    start_year: int = Query(2002, ge=2002, le=2025),
    end_year: int = Query(2025, ge=2002, le=2025),
):
    """Get revenue trend for a specific defense company."""
    session, analyzer = _get_analyzer()
    try:
        trend = analyzer.company_revenue_trend(company_name, start_year, end_year)
        if not trend:
            return {"error": f"Company '{company_name}' not found in database"}

        return {
            "name": trend.name,
            "country": trend.country,
            "data": [
                {"year": y, "arms_revenue_usd_m": r, "rank": rank}
                for y, r, rank in zip(trend.years, trend.arms_revenue, trend.ranks)
            ],
        }
    except Exception as e:
        logger.error("Company revenue trend fetch failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/companies/top/{year}")
async def get_top_companies(
    year: int,
    limit: int = Query(25, ge=1, le=100),
):
    """Get the top defense companies for a specific year."""
    session, analyzer = _get_analyzer()
    try:
        return analyzer.top_companies_by_year(year, limit)
    except Exception as e:
        logger.error("Top companies query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Activity Trends ---


@router.get("/activity/flights")
async def get_flight_activity(days: int = Query(30, ge=1, le=365)):
    """Get military flight detection counts by day."""
    session, analyzer = _get_analyzer()
    try:
        return analyzer.flight_activity_by_day(days)
    except Exception as e:
        logger.error("Flight activity query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/activity/news")
async def get_news_activity(days: int = Query(30, ge=1, le=365)):
    """Get arms trade news volume and sentiment by day."""
    session, analyzer = _get_analyzer()
    try:
        return analyzer.news_volume_by_day(days)
    except Exception as e:
        logger.error("News activity query failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()
