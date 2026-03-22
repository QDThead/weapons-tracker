"""Core data models for global weapons trade tracking."""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, Index, Enum as SQLEnum, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class WeaponCategory(str, Enum):
    """SIPRI/UNROCA weapon categories."""
    AIRCRAFT = "aircraft"
    AIR_DEFENCE = "air_defence"
    ANTI_SUBMARINE = "anti_submarine"
    ARMOURED_VEHICLE = "armoured_vehicle"
    ARTILLERY = "artillery"
    ENGINE = "engine"
    MISSILE = "missile"
    NAVAL_WEAPON = "naval_weapon"
    SATELLITE = "satellite"
    SENSOR = "sensor"
    SHIP = "ship"
    OTHER = "other"


class DealStatus(str, Enum):
    """Status of an arms transfer deal."""
    ORDERED = "ordered"
    DELIVERING = "delivering"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


class Country(Base):
    """Country involved in arms trade."""
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    iso_alpha2 = Column(String(2), unique=True)
    iso_alpha3 = Column(String(3), unique=True)
    region = Column(String(100))
    sub_region = Column(String(100))

    exports = relationship("ArmsTransfer", foreign_keys="ArmsTransfer.seller_id", back_populates="seller")
    imports = relationship("ArmsTransfer", foreign_keys="ArmsTransfer.buyer_id", back_populates="buyer")
    companies = relationship("DefenseCompany", back_populates="country")
    trade_indicators = relationship("TradeIndicator", back_populates="country")

    def __repr__(self):
        return f"<Country(name='{self.name}', iso='{self.iso_alpha3}')>"


class WeaponSystem(Base):
    """A specific weapon system or platform."""
    __tablename__ = "weapon_systems"

    id = Column(Integer, primary_key=True)
    designation = Column(String(255), nullable=False)
    description = Column(Text)
    category = Column(SQLEnum(WeaponCategory), nullable=False)
    producer_country_id = Column(Integer, ForeignKey("countries.id"))

    producer_country = relationship("Country")
    transfers = relationship("ArmsTransfer", back_populates="weapon_system")

    __table_args__ = (
        Index("ix_weapon_designation", "designation"),
    )

    def __repr__(self):
        return f"<WeaponSystem(designation='{self.designation}', category='{self.category}')>"


class ArmsTransfer(Base):
    """An individual arms transfer deal — the core entity.

    Maps directly to SIPRI Trade Register records.
    """
    __tablename__ = "arms_transfers"

    id = Column(Integer, primary_key=True)
    seller_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    weapon_system_id = Column(Integer, ForeignKey("weapon_systems.id"))
    weapon_description = Column(Text)

    order_year = Column(Integer)
    delivery_year_start = Column(Integer)
    delivery_year_end = Column(Integer)
    number_ordered = Column(Integer)
    number_delivered = Column(Integer)
    status = Column(SQLEnum(DealStatus), default=DealStatus.UNKNOWN)

    tiv_per_unit = Column(Float)
    tiv_total_order = Column(Float)
    tiv_delivered = Column(Float)

    comments = Column(Text)
    source = Column(String(50), default="sipri")
    source_id = Column(String(255))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    seller = relationship("Country", foreign_keys=[seller_id], back_populates="exports")
    buyer = relationship("Country", foreign_keys=[buyer_id], back_populates="imports")
    weapon_system = relationship("WeaponSystem", back_populates="transfers")

    __table_args__ = (
        Index("ix_transfer_seller", "seller_id"),
        Index("ix_transfer_buyer", "buyer_id"),
        Index("ix_transfer_years", "order_year", "delivery_year_start"),
        UniqueConstraint("source", "source_id", name="uq_transfer_source"),
    )

    def __repr__(self):
        return f"<ArmsTransfer(seller={self.seller_id}, buyer={self.buyer_id}, year={self.order_year})>"


class DefenseCompany(Base):
    """A defense/arms-producing company (SIPRI Top 100)."""
    __tablename__ = "defense_companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    country_id = Column(Integer, ForeignKey("countries.id"))
    rank = Column(Integer)
    year = Column(Integer, nullable=False)
    arms_revenue_usd = Column(Float)
    total_revenue_usd = Column(Float)
    arms_revenue_pct = Column(Float)

    country = relationship("Country", back_populates="companies")

    __table_args__ = (
        UniqueConstraint("name", "year", name="uq_company_year"),
        Index("ix_company_year_rank", "year", "rank"),
    )

    def __repr__(self):
        return f"<DefenseCompany(name='{self.name}', year={self.year}, rank={self.rank})>"


class TradeIndicator(Base):
    """World Bank arms trade indicators per country per year."""
    __tablename__ = "trade_indicators"

    id = Column(Integer, primary_key=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False)
    year = Column(Integer, nullable=False)
    arms_imports_tiv = Column(Float)
    arms_exports_tiv = Column(Float)
    military_expenditure_pct_gdp = Column(Float)

    country = relationship("Country", back_populates="trade_indicators")

    __table_args__ = (
        UniqueConstraint("country_id", "year", name="uq_indicator_country_year"),
        Index("ix_indicator_year", "year"),
    )


class ArmsTradeNews(Base):
    """News articles about arms deals detected via GDELT or other sources."""
    __tablename__ = "arms_trade_news"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    url = Column(Text, nullable=False, unique=True)
    source_name = Column(String(255))
    published_at = Column(DateTime)
    language = Column(String(10))

    seller_country_id = Column(Integer, ForeignKey("countries.id"))
    buyer_country_id = Column(Integer, ForeignKey("countries.id"))
    weapon_keywords = Column(Text)
    tone_score = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    seller_country = relationship("Country", foreign_keys=[seller_country_id])
    buyer_country = relationship("Country", foreign_keys=[buyer_country_id])

    __table_args__ = (
        Index("ix_news_published", "published_at"),
    )


class DeliveryTracking(Base):
    """Suspected weapons delivery events from flight/maritime tracking."""
    __tablename__ = "delivery_tracking"

    id = Column(Integer, primary_key=True)
    tracking_type = Column(String(20), nullable=False)  # "flight" or "maritime"
    identifier = Column(String(100))  # ICAO hex or MMSI
    callsign = Column(String(50))
    vessel_or_aircraft_type = Column(String(255))

    origin_lat = Column(Float)
    origin_lon = Column(Float)
    origin_location = Column(String(255))
    destination_lat = Column(Float)
    destination_lon = Column(Float)
    destination_location = Column(String(255))

    departure_time = Column(DateTime)
    arrival_time = Column(DateTime)
    detected_at = Column(DateTime, default=datetime.utcnow)

    confidence = Column(String(20))  # "low", "medium", "high"
    notes = Column(Text)

    __table_args__ = (
        Index("ix_delivery_type_time", "tracking_type", "detected_at"),
    )
