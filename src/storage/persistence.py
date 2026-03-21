"""Persistence service — stores fetched data into the database.

Handles upsert logic and deduplication for all entity types.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.models import (
    Country, WeaponSystem, ArmsTransfer, DefenseCompany,
    TradeIndicator, ArmsTradeNews, DeliveryTracking,
    WeaponCategory, DealStatus,
)
from src.ingestion.sipri_transfers import SIPRITransferRecord
from src.ingestion.sipri_companies import DefenseCompanyRecord
from src.ingestion.worldbank import TradeIndicatorRecord
from src.ingestion.gdelt_news import ArmsNewsArticle
from src.ingestion.flight_tracker import MilitaryFlightRecord
from src.ingestion.maritime_tracker import VesselPosition

logger = logging.getLogger(__name__)

# Map SIPRI weapon description keywords to categories
_CATEGORY_KEYWORDS = {
    WeaponCategory.AIRCRAFT: ["aircraft", "fighter", "helicopter", "bomber", "trainer", "transport aircraft", "UAV", "drone"],
    WeaponCategory.AIR_DEFENCE: ["air defence", "air defense", "SAM", "anti-air"],
    WeaponCategory.ANTI_SUBMARINE: ["anti-submarine", "ASW", "torpedo"],
    WeaponCategory.ARMOURED_VEHICLE: ["APC", "IFV", "armoured", "armored", "tank", "MRAP"],
    WeaponCategory.ARTILLERY: ["artillery", "howitzer", "mortar", "gun", "MLRS", "rocket launcher"],
    WeaponCategory.ENGINE: ["engine", "turbofan", "turboprop"],
    WeaponCategory.MISSILE: ["missile", "ATGM", "cruise missile", "ballistic"],
    WeaponCategory.NAVAL_WEAPON: ["naval weapon", "CIWS", "naval gun"],
    WeaponCategory.SATELLITE: ["satellite"],
    WeaponCategory.SENSOR: ["sensor", "radar", "EW", "fire control"],
    WeaponCategory.SHIP: ["frigate", "corvette", "submarine", "destroyer", "patrol", "carrier", "ship", "boat"],
}


def _infer_weapon_category(description: str) -> WeaponCategory:
    """Infer weapon category from a text description."""
    desc_lower = description.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in desc_lower:
                return category
    return WeaponCategory.OTHER


def _infer_deal_status(status_text: str) -> DealStatus:
    """Map SIPRI status text to DealStatus enum."""
    s = status_text.lower().strip()
    if "delivered" in s or "produced" in s:
        return DealStatus.DELIVERED
    if "delivering" in s or "on order" in s:
        return DealStatus.DELIVERING
    if "order" in s:
        return DealStatus.ORDERED
    if "cancel" in s:
        return DealStatus.CANCELLED
    return DealStatus.UNKNOWN


def _safe_int(value: str) -> int | None:
    """Parse an integer from a string, returning None on failure."""
    try:
        cleaned = value.strip().replace(",", "").replace("(", "").replace(")", "")
        if not cleaned:
            return None
        return int(float(cleaned))
    except (ValueError, TypeError):
        return None


def _safe_float(value: str) -> float | None:
    """Parse a float from a string, returning None on failure."""
    try:
        cleaned = value.strip().replace(",", "").replace("(", "").replace(")", "")
        if not cleaned:
            return None
        return float(cleaned)
    except (ValueError, TypeError):
        return None


class PersistenceService:
    """Stores ingested data into the database with deduplication."""

    def __init__(self, session: Session):
        self.session = session
        self._country_cache: dict[str, Country] = {}

    def get_or_create_country(self, name: str) -> Country:
        """Get existing country or create a new one."""
        name = name.strip()
        if not name:
            return self.get_or_create_country("Unknown")

        if name in self._country_cache:
            return self._country_cache[name]

        country = self.session.execute(
            select(Country).where(Country.name == name)
        ).scalar_one_or_none()

        if country is None:
            country = Country(name=name)
            self.session.add(country)
            self.session.flush()

        self._country_cache[name] = country
        return country

    # --- Arms Transfers (SIPRI) ---

    def store_sipri_transfers(self, records: list[SIPRITransferRecord]) -> int:
        """Store SIPRI transfer records, deduplicating by source_id.

        Returns:
            Number of new records inserted.
        """
        inserted = 0

        for record in records:
            source_id = f"{record.seller}|{record.buyer}|{record.weapon_designation}|{record.order_year}"

            existing = self.session.execute(
                select(ArmsTransfer).where(
                    ArmsTransfer.source == "sipri",
                    ArmsTransfer.source_id == source_id,
                )
            ).scalar_one_or_none()

            if existing:
                # Update existing record
                existing.number_delivered = _safe_int(record.number_delivered) or existing.number_delivered
                existing.tiv_delivered = _safe_float(record.tiv_delivered) or existing.tiv_delivered
                existing.status = _infer_deal_status(record.status)
                existing.comments = record.comments or existing.comments
                existing.updated_at = datetime.utcnow()
                continue

            seller = self.get_or_create_country(record.seller)
            buyer = self.get_or_create_country(record.buyer)

            # Get or create weapon system
            weapon_system = self._get_or_create_weapon(
                record.weapon_designation,
                record.weapon_description,
                seller,
            )

            # Parse delivery year range
            delivery_start, delivery_end = self._parse_delivery_years(record.delivery_years)

            transfer = ArmsTransfer(
                seller_id=seller.id,
                buyer_id=buyer.id,
                weapon_system_id=weapon_system.id if weapon_system else None,
                weapon_description=record.weapon_description,
                order_year=_safe_int(record.order_year),
                delivery_year_start=delivery_start,
                delivery_year_end=delivery_end,
                number_ordered=_safe_int(record.number_ordered),
                number_delivered=_safe_int(record.number_delivered),
                status=_infer_deal_status(record.status),
                tiv_per_unit=_safe_float(record.tiv_per_unit),
                tiv_total_order=_safe_float(record.tiv_total_order),
                tiv_delivered=_safe_float(record.tiv_delivered),
                comments=record.comments,
                source="sipri",
                source_id=source_id,
            )
            self.session.add(transfer)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d new SIPRI transfers (%d total processed)", inserted, len(records))
        return inserted

    def _get_or_create_weapon(
        self, designation: str, description: str, producer_country: Country
    ) -> WeaponSystem | None:
        """Get or create a weapon system entry."""
        if not designation.strip():
            return None

        weapon = self.session.execute(
            select(WeaponSystem).where(WeaponSystem.designation == designation.strip())
        ).scalar_one_or_none()

        if weapon is None:
            weapon = WeaponSystem(
                designation=designation.strip(),
                description=description,
                category=_infer_weapon_category(description),
                producer_country_id=producer_country.id,
            )
            self.session.add(weapon)
            self.session.flush()

        return weapon

    @staticmethod
    def _parse_delivery_years(delivery_str: str) -> tuple[int | None, int | None]:
        """Parse SIPRI delivery year string like '2015-2020' or '2018'."""
        cleaned = delivery_str.strip().replace("(", "").replace(")", "")
        if not cleaned:
            return None, None

        if "-" in cleaned:
            parts = cleaned.split("-")
            return _safe_int(parts[0]), _safe_int(parts[-1])

        year = _safe_int(cleaned)
        return year, year

    # --- Defense Companies (SIPRI Top 100) ---

    def store_defense_companies(self, records: list[DefenseCompanyRecord]) -> int:
        """Store defense company records."""
        inserted = 0

        for record in records:
            country = self.get_or_create_country(record.country)

            existing = self.session.execute(
                select(DefenseCompany).where(
                    DefenseCompany.name == record.name,
                    DefenseCompany.year == record.year,
                )
            ).scalar_one_or_none()

            if existing:
                existing.rank = record.rank
                existing.arms_revenue_usd = record.arms_revenue_usd_millions
                existing.total_revenue_usd = record.total_revenue_usd_millions
                continue

            company = DefenseCompany(
                name=record.name,
                country_id=country.id,
                rank=record.rank,
                year=record.year,
                arms_revenue_usd=record.arms_revenue_usd_millions,
                total_revenue_usd=record.total_revenue_usd_millions,
            )
            self.session.add(company)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d new defense companies (%d total processed)", inserted, len(records))
        return inserted

    # --- Trade Indicators (World Bank) ---

    def store_trade_indicators(self, records: list[TradeIndicatorRecord]) -> int:
        """Store World Bank trade indicator records."""
        inserted = 0

        for record in records:
            country = self.get_or_create_country(record.country_name)

            existing = self.session.execute(
                select(TradeIndicator).where(
                    TradeIndicator.country_id == country.id,
                    TradeIndicator.year == record.year,
                )
            ).scalar_one_or_none()

            if existing:
                if record.arms_imports_tiv is not None:
                    existing.arms_imports_tiv = record.arms_imports_tiv
                if record.arms_exports_tiv is not None:
                    existing.arms_exports_tiv = record.arms_exports_tiv
                if record.military_expenditure_pct_gdp is not None:
                    existing.military_expenditure_pct_gdp = record.military_expenditure_pct_gdp
                continue

            indicator = TradeIndicator(
                country_id=country.id,
                year=record.year,
                arms_imports_tiv=record.arms_imports_tiv,
                arms_exports_tiv=record.arms_exports_tiv,
                military_expenditure_pct_gdp=record.military_expenditure_pct_gdp,
            )
            self.session.add(indicator)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d new trade indicators (%d total processed)", inserted, len(records))
        return inserted

    # --- Arms Trade News (GDELT) ---

    def store_news_articles(self, articles: list[ArmsNewsArticle]) -> int:
        """Store arms trade news articles, deduplicating by URL."""
        inserted = 0

        for article in articles:
            if not article.url:
                continue

            existing = self.session.execute(
                select(ArmsTradeNews).where(ArmsTradeNews.url == article.url)
            ).scalar_one_or_none()

            if existing:
                continue

            news = ArmsTradeNews(
                title=article.title,
                url=article.url,
                source_name=article.source,
                published_at=article.published_at,
                language=article.language,
                tone_score=article.tone,
            )
            self.session.add(news)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d new news articles (%d total processed)", inserted, len(articles))
        return inserted

    # --- Delivery Tracking (Flights) ---

    def store_flight_positions(self, flights: list[MilitaryFlightRecord]) -> int:
        """Store military flight position snapshots."""
        inserted = 0

        for flight in flights:
            tracking = DeliveryTracking(
                tracking_type="flight",
                identifier=flight.icao_hex,
                callsign=flight.callsign,
                vessel_or_aircraft_type=f"{flight.aircraft_type} ({flight.aircraft_description})",
                origin_lat=flight.latitude,
                origin_lon=flight.longitude,
                detected_at=flight.seen_at,
                confidence="medium" if flight.is_military else "low",
                notes=f"Alt: {flight.altitude_ft}ft, Speed: {flight.ground_speed_knots}kts, Hdg: {flight.heading}",
            )
            self.session.add(tracking)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d flight position records", inserted)
        return inserted

    # --- Delivery Tracking (Maritime) ---

    def store_vessel_positions(self, vessels: list[VesselPosition]) -> int:
        """Store vessel position snapshots."""
        inserted = 0

        for vessel in vessels:
            tracking = DeliveryTracking(
                tracking_type="maritime",
                identifier=str(vessel.mmsi),
                callsign=vessel.callsign,
                vessel_or_aircraft_type=f"Ship type {vessel.ship_type} ({vessel.name})",
                origin_lat=vessel.latitude,
                origin_lon=vessel.longitude,
                detected_at=vessel.seen_at,
                destination_location=vessel.destination,
                confidence="high" if vessel.is_military else ("medium" if vessel.is_roro_cargo else "low"),
                notes=f"Chokepoint: {vessel.chokepoint or 'N/A'}, Dest: {vessel.destination}, Speed: {vessel.speed}kts",
            )
            self.session.add(tracking)
            inserted += 1

        self.session.commit()
        logger.info("Stored %d vessel position records", inserted)
        return inserted
