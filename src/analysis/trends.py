"""Historical trend analysis for weapons trade data.

Queries persisted data to compute:
  - Arms trade volume over time (by country, globally)
  - Top trading pairs (seller → buyer)
  - Weapon category breakdowns
  - Year-over-year changes
  - Defense company revenue trends
  - Military flight activity trends
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import func, desc, case, and_, extract
from sqlalchemy.orm import Session

from src.storage.models import (
    ArmsTransfer, Country, WeaponSystem, DefenseCompany,
    TradeIndicator, ArmsTradeNews, DeliveryTracking,
    WeaponCategory,
)

logger = logging.getLogger(__name__)


@dataclass
class YearlyVolume:
    """Trade volume for a single year."""
    year: int
    tiv_total: float
    deal_count: int


@dataclass
class CountryTradeProfile:
    """Trade summary for a single country."""
    country: str
    total_exports_tiv: float
    total_imports_tiv: float
    export_deal_count: int
    import_deal_count: int
    top_export_partners: list[dict]
    top_import_partners: list[dict]
    top_weapon_categories: list[dict]


@dataclass
class TradingPair:
    """A seller-buyer pair with trade volume."""
    seller: str
    buyer: str
    tiv_total: float
    deal_count: int
    weapon_systems: list[str]


@dataclass
class CategoryBreakdown:
    """Trade volume by weapon category."""
    category: str
    tiv_total: float
    deal_count: int
    pct_of_total: float


@dataclass
class CompanyTrend:
    """Revenue trend for a defense company."""
    name: str
    country: str
    years: list[int]
    arms_revenue: list[float | None]
    ranks: list[int | None]


@dataclass
class YearOverYearChange:
    """Year-over-year change for a country."""
    country: str
    year: int
    prev_year: int
    tiv_current: float
    tiv_previous: float
    change_pct: float


class TrendAnalyzer:
    """Analyzes historical weapons trade trends from persisted data."""

    def __init__(self, session: Session):
        self.session = session

    # --- Global Trade Volume ---

    def global_volume_by_year(
        self, start_year: int = 2000, end_year: int = 2025
    ) -> list[YearlyVolume]:
        """Get total global arms trade volume by year."""
        results = (
            self.session.query(
                ArmsTransfer.order_year,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv_total"),
                func.count(ArmsTransfer.id).label("deal_count"),
            )
            .filter(
                ArmsTransfer.order_year.isnot(None),
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(ArmsTransfer.order_year)
            .order_by(ArmsTransfer.order_year)
            .all()
        )

        return [
            YearlyVolume(year=r[0], tiv_total=float(r[1] or 0), deal_count=r[2])
            for r in results
        ]

    # --- Country Trade Volume Over Time ---

    def country_exports_by_year(
        self, country_name: str, start_year: int = 2000, end_year: int = 2025
    ) -> list[YearlyVolume]:
        """Get a country's arms export volume by year."""
        country = self._get_country(country_name)
        if not country:
            return []

        results = (
            self.session.query(
                ArmsTransfer.order_year,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0),
                func.count(ArmsTransfer.id),
            )
            .filter(
                ArmsTransfer.seller_id == country.id,
                ArmsTransfer.order_year.isnot(None),
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(ArmsTransfer.order_year)
            .order_by(ArmsTransfer.order_year)
            .all()
        )

        return [YearlyVolume(year=r[0], tiv_total=float(r[1] or 0), deal_count=r[2]) for r in results]

    def country_imports_by_year(
        self, country_name: str, start_year: int = 2000, end_year: int = 2025
    ) -> list[YearlyVolume]:
        """Get a country's arms import volume by year."""
        country = self._get_country(country_name)
        if not country:
            return []

        results = (
            self.session.query(
                ArmsTransfer.order_year,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0),
                func.count(ArmsTransfer.id),
            )
            .filter(
                ArmsTransfer.buyer_id == country.id,
                ArmsTransfer.order_year.isnot(None),
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(ArmsTransfer.order_year)
            .order_by(ArmsTransfer.order_year)
            .all()
        )

        return [YearlyVolume(year=r[0], tiv_total=float(r[1] or 0), deal_count=r[2]) for r in results]

    # --- Country Trade Profile ---

    def country_profile(
        self, country_name: str, start_year: int = 2000, end_year: int = 2025
    ) -> CountryTradeProfile | None:
        """Build a comprehensive trade profile for a country."""
        country = self._get_country(country_name)
        if not country:
            return None

        # Export totals
        export_stats = (
            self.session.query(
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0),
                func.count(ArmsTransfer.id),
            )
            .filter(
                ArmsTransfer.seller_id == country.id,
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .one()
        )

        # Import totals
        import_stats = (
            self.session.query(
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0),
                func.count(ArmsTransfer.id),
            )
            .filter(
                ArmsTransfer.buyer_id == country.id,
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .one()
        )

        # Top export partners
        top_export_partners = (
            self.session.query(
                Country.name,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
                func.count(ArmsTransfer.id).label("deals"),
            )
            .join(Country, Country.id == ArmsTransfer.buyer_id)
            .filter(
                ArmsTransfer.seller_id == country.id,
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(Country.name)
            .order_by(desc("tiv"))
            .limit(10)
            .all()
        )

        # Top import partners
        top_import_partners = (
            self.session.query(
                Country.name,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
                func.count(ArmsTransfer.id).label("deals"),
            )
            .join(Country, Country.id == ArmsTransfer.seller_id)
            .filter(
                ArmsTransfer.buyer_id == country.id,
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(Country.name)
            .order_by(desc("tiv"))
            .limit(10)
            .all()
        )

        # Weapon category breakdown (exports + imports)
        top_categories = (
            self.session.query(
                WeaponSystem.category,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
                func.count(ArmsTransfer.id).label("deals"),
            )
            .join(WeaponSystem, WeaponSystem.id == ArmsTransfer.weapon_system_id)
            .filter(
                (ArmsTransfer.seller_id == country.id) | (ArmsTransfer.buyer_id == country.id),
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(WeaponSystem.category)
            .order_by(desc("tiv"))
            .all()
        )

        return CountryTradeProfile(
            country=country_name,
            total_exports_tiv=float(export_stats[0] or 0),
            total_imports_tiv=float(import_stats[0] or 0),
            export_deal_count=export_stats[1],
            import_deal_count=import_stats[1],
            top_export_partners=[
                {"country": r[0], "tiv": float(r[1] or 0), "deals": r[2]}
                for r in top_export_partners
            ],
            top_import_partners=[
                {"country": r[0], "tiv": float(r[1] or 0), "deals": r[2]}
                for r in top_import_partners
            ],
            top_weapon_categories=[
                {"category": r[0].value if r[0] else "other", "tiv": float(r[1] or 0), "deals": r[2]}
                for r in top_categories
            ],
        )

    # --- Top Trading Pairs ---

    def top_trading_pairs(
        self, start_year: int = 2000, end_year: int = 2025, limit: int = 20
    ) -> list[TradingPair]:
        """Get the highest-volume seller→buyer pairs."""
        SellerCountry = Country.__table__.alias("seller_country")
        BuyerCountry = Country.__table__.alias("buyer_country")

        results = (
            self.session.query(
                func.min(SellerCountry.c.name).label("seller"),
                func.min(BuyerCountry.c.name).label("buyer"),
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
                func.count(ArmsTransfer.id).label("deals"),
            )
            .join(SellerCountry, SellerCountry.c.id == ArmsTransfer.seller_id)
            .join(BuyerCountry, BuyerCountry.c.id == ArmsTransfer.buyer_id)
            .filter(
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(ArmsTransfer.seller_id, ArmsTransfer.buyer_id)
            .order_by(desc("tiv"))
            .limit(limit)
            .all()
        )

        return [
            TradingPair(
                seller=r[0], buyer=r[1],
                tiv_total=float(r[2] or 0), deal_count=r[3],
                weapon_systems=[],
            )
            for r in results
        ]

    # --- Weapon Category Breakdown ---

    def global_category_breakdown(
        self, start_year: int = 2000, end_year: int = 2025
    ) -> list[CategoryBreakdown]:
        """Get global arms trade broken down by weapon category."""
        results = (
            self.session.query(
                WeaponSystem.category,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
                func.count(ArmsTransfer.id).label("deals"),
            )
            .join(WeaponSystem, WeaponSystem.id == ArmsTransfer.weapon_system_id)
            .filter(
                ArmsTransfer.order_year >= start_year,
                ArmsTransfer.order_year <= end_year,
            )
            .group_by(WeaponSystem.category)
            .order_by(desc("tiv"))
            .all()
        )

        total_tiv = sum(float(r[1] or 0) for r in results)

        return [
            CategoryBreakdown(
                category=r[0].value if r[0] else "other",
                tiv_total=float(r[1] or 0),
                deal_count=r[2],
                pct_of_total=round(float(r[1] or 0) / total_tiv * 100, 1) if total_tiv > 0 else 0,
            )
            for r in results
        ]

    # --- Defense Company Trends ---

    def company_revenue_trend(
        self, company_name: str, start_year: int = 2002, end_year: int = 2025
    ) -> CompanyTrend | None:
        """Get revenue trend for a specific defense company."""
        results = (
            self.session.query(
                DefenseCompany.year,
                DefenseCompany.arms_revenue_usd,
                DefenseCompany.rank,
                Country.name,
            )
            .join(Country, Country.id == DefenseCompany.country_id, isouter=True)
            .filter(
                DefenseCompany.name.ilike(f"%{company_name}%"),
                DefenseCompany.year >= start_year,
                DefenseCompany.year <= end_year,
            )
            .order_by(DefenseCompany.year)
            .all()
        )

        if not results:
            return None

        return CompanyTrend(
            name=company_name,
            country=results[0][3] or "",
            years=[r[0] for r in results],
            arms_revenue=[r[1] for r in results],
            ranks=[r[2] for r in results],
        )

    def top_companies_by_year(self, year: int, limit: int = 25) -> list[dict]:
        """Get top defense companies for a specific year."""
        results = (
            self.session.query(
                DefenseCompany.name,
                DefenseCompany.rank,
                DefenseCompany.arms_revenue_usd,
                DefenseCompany.total_revenue_usd,
                Country.name.label("country"),
            )
            .join(Country, Country.id == DefenseCompany.country_id, isouter=True)
            .filter(DefenseCompany.year == year)
            .order_by(DefenseCompany.rank)
            .limit(limit)
            .all()
        )

        return [
            {
                "name": r[0], "rank": r[1],
                "arms_revenue_usd_m": r[2], "total_revenue_usd_m": r[3],
                "country": r[4] or "",
            }
            for r in results
        ]

    # --- Year-Over-Year Changes ---

    def biggest_import_changes(
        self, year: int, limit: int = 10
    ) -> list[YearOverYearChange]:
        """Find countries with the biggest year-over-year change in arms imports."""
        prev_year = year - 1

        current = dict(
            self.session.query(
                TradeIndicator.country_id,
                TradeIndicator.arms_imports_tiv,
            )
            .filter(TradeIndicator.year == year, TradeIndicator.arms_imports_tiv.isnot(None))
            .all()
        )

        previous = dict(
            self.session.query(
                TradeIndicator.country_id,
                TradeIndicator.arms_imports_tiv,
            )
            .filter(TradeIndicator.year == prev_year, TradeIndicator.arms_imports_tiv.isnot(None))
            .all()
        )

        changes = []
        for country_id, cur_tiv in current.items():
            prev_tiv = previous.get(country_id)
            if prev_tiv and prev_tiv > 0 and cur_tiv:
                change_pct = ((cur_tiv - prev_tiv) / prev_tiv) * 100
                country = self.session.get(Country, country_id)
                if country:
                    changes.append(YearOverYearChange(
                        country=country.name,
                        year=year,
                        prev_year=prev_year,
                        tiv_current=cur_tiv,
                        tiv_previous=prev_tiv,
                        change_pct=round(change_pct, 1),
                    ))

        changes.sort(key=lambda c: abs(c.change_pct), reverse=True)
        return changes[:limit]

    # --- Flight Activity Trends ---

    def flight_activity_by_day(self, days: int = 30) -> list[dict]:
        """Get military flight detection counts by day."""
        results = (
            self.session.query(
                func.date(DeliveryTracking.detected_at).label("day"),
                func.count(DeliveryTracking.id).label("count"),
            )
            .filter(DeliveryTracking.tracking_type == "flight")
            .group_by(func.date(DeliveryTracking.detected_at))
            .order_by(desc("day"))
            .limit(days)
            .all()
        )

        return [
            {"date": str(r[0]), "flight_count": r[1]}
            for r in reversed(results)
        ]

    # --- News Volume Trends ---

    def news_volume_by_day(self, days: int = 30) -> list[dict]:
        """Get arms trade news article counts by day."""
        results = (
            self.session.query(
                func.date(ArmsTradeNews.published_at).label("day"),
                func.count(ArmsTradeNews.id).label("count"),
                func.avg(ArmsTradeNews.tone_score).label("avg_tone"),
            )
            .filter(ArmsTradeNews.published_at.isnot(None))
            .group_by(func.date(ArmsTradeNews.published_at))
            .order_by(desc("day"))
            .limit(days)
            .all()
        )

        return [
            {"date": str(r[0]), "article_count": r[1], "avg_tone": round(float(r[2] or 0), 2)}
            for r in reversed(results)
        ]

    # --- Helpers ---

    def _get_country(self, name: str) -> Country | None:
        """Look up a country by name."""
        from sqlalchemy import select
        return self.session.execute(
            select(Country).where(Country.name == name)
        ).scalar_one_or_none()

    def summary_stats(self) -> dict:
        """Get overall database summary statistics."""
        return {
            "total_transfers": self.session.query(func.count(ArmsTransfer.id)).scalar() or 0,
            "total_countries": self.session.query(func.count(Country.id)).scalar() or 0,
            "total_weapon_systems": self.session.query(func.count(WeaponSystem.id)).scalar() or 0,
            "total_companies": self.session.query(func.count(DefenseCompany.id)).scalar() or 0,
            "total_news_articles": self.session.query(func.count(ArmsTradeNews.id)).scalar() or 0,
            "total_flight_detections": self.session.query(func.count(DeliveryTracking.id)).filter(
                DeliveryTracking.tracking_type == "flight"
            ).scalar() or 0,
            "total_vessel_detections": self.session.query(func.count(DeliveryTracking.id)).filter(
                DeliveryTracking.tracking_type == "maritime"
            ).scalar() or 0,
            "year_range": {
                "earliest": self.session.query(func.min(ArmsTransfer.order_year)).scalar(),
                "latest": self.session.query(func.max(ArmsTransfer.order_year)).scalar(),
            },
        }
