"""FastAPI routes for the Weapons Tracker API.

Provides endpoints to query arms transfers, defense companies,
trade indicators, arms trade news, and live delivery tracking.
"""

from __future__ import annotations

from fastapi import FastAPI, Query
from pydantic import BaseModel

from src.ingestion.sipri_transfers import SIPRITransfersClient, SIPRIQuery, SIPRI_COUNTRY_CODES
from src.ingestion.sipri_companies import SIPRICompaniesClient
from src.ingestion.worldbank import WorldBankClient
from src.ingestion.gdelt_news import GDELTArmsNewsClient
from src.ingestion.flight_tracker import FlightTrackerClient

app = FastAPI(
    title="Weapons Tracker API",
    description="Global weapons sales and trade tracking across countries using OSINT data sources.",
    version="0.1.0",
)

# --- Health ---


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- Arms Transfers (SIPRI) ---


class TransferOut(BaseModel):
    seller: str
    buyer: str
    weapon_designation: str
    weapon_description: str
    order_year: str
    delivery_years: str
    number_ordered: str
    status: str
    tiv_per_unit: str
    tiv_total_order: str
    tiv_delivered: str
    comments: str


@app.get("/transfers/exports/{country}", response_model=list[TransferOut])
async def get_country_exports(
    country: str,
    low_year: int = Query(2000, ge=1950, le=2025),
    high_year: int = Query(2025, ge=1950, le=2025),
):
    """Get all arms exports from a country."""
    client = SIPRITransfersClient()
    records = await client.fetch_country_exports(country, low_year, high_year)
    return [
        TransferOut(
            seller=r.seller, buyer=r.buyer,
            weapon_designation=r.weapon_designation,
            weapon_description=r.weapon_description,
            order_year=r.order_year, delivery_years=r.delivery_years,
            number_ordered=r.number_ordered, status=r.status,
            tiv_per_unit=r.tiv_per_unit, tiv_total_order=r.tiv_total_order,
            tiv_delivered=r.tiv_delivered, comments=r.comments,
        )
        for r in records
    ]


@app.get("/transfers/imports/{country}", response_model=list[TransferOut])
async def get_country_imports(
    country: str,
    low_year: int = Query(2000, ge=1950, le=2025),
    high_year: int = Query(2025, ge=1950, le=2025),
):
    """Get all arms imports for a country."""
    client = SIPRITransfersClient()
    records = await client.fetch_country_imports(country, low_year, high_year)
    return [
        TransferOut(
            seller=r.seller, buyer=r.buyer,
            weapon_designation=r.weapon_designation,
            weapon_description=r.weapon_description,
            order_year=r.order_year, delivery_years=r.delivery_years,
            number_ordered=r.number_ordered, status=r.status,
            tiv_per_unit=r.tiv_per_unit, tiv_total_order=r.tiv_total_order,
            tiv_delivered=r.tiv_delivered, comments=r.comments,
        )
        for r in records
    ]


@app.get("/transfers/bilateral/{seller}/{buyer}", response_model=list[TransferOut])
async def get_bilateral_transfers(
    seller: str,
    buyer: str,
    low_year: int = Query(2000, ge=1950, le=2025),
    high_year: int = Query(2025, ge=1950, le=2025),
):
    """Get arms transfers between two specific countries."""
    client = SIPRITransfersClient()
    records = await client.fetch_bilateral_trade(seller, buyer, low_year, high_year)
    return [
        TransferOut(
            seller=r.seller, buyer=r.buyer,
            weapon_designation=r.weapon_designation,
            weapon_description=r.weapon_description,
            order_year=r.order_year, delivery_years=r.delivery_years,
            number_ordered=r.number_ordered, status=r.status,
            tiv_per_unit=r.tiv_per_unit, tiv_total_order=r.tiv_total_order,
            tiv_delivered=r.tiv_delivered, comments=r.comments,
        )
        for r in records
    ]


@app.get("/transfers/countries")
async def list_available_countries():
    """List countries available for SIPRI queries."""
    return {"countries": list(SIPRI_COUNTRY_CODES.keys())}


# --- Trade Indicators (World Bank) ---


class IndicatorOut(BaseModel):
    country_name: str
    country_iso3: str
    year: int
    arms_imports_tiv: float | None
    arms_exports_tiv: float | None
    military_expenditure_pct_gdp: float | None


@app.get("/indicators/{country_iso3}", response_model=list[IndicatorOut])
async def get_trade_indicators(
    country_iso3: str,
    start_year: int = Query(2000, ge=1960, le=2025),
    end_year: int = Query(2025, ge=1960, le=2025),
):
    """Get arms trade indicators for a country (World Bank data)."""
    client = WorldBankClient()
    records = await client.fetch_arms_trade_data(country_iso3, start_year, end_year)
    return [
        IndicatorOut(
            country_name=r.country_name, country_iso3=r.country_iso3,
            year=r.year, arms_imports_tiv=r.arms_imports_tiv,
            arms_exports_tiv=r.arms_exports_tiv,
            military_expenditure_pct_gdp=r.military_expenditure_pct_gdp,
        )
        for r in records
    ]


@app.get("/indicators/top/importers", response_model=list[IndicatorOut])
async def get_top_importers(year: int = Query(2024, ge=1960, le=2025)):
    """Get the top arms importing countries for a given year."""
    client = WorldBankClient()
    records = await client.fetch_top_importers(year)
    return [
        IndicatorOut(
            country_name=r.country_name, country_iso3=r.country_iso3,
            year=r.year, arms_imports_tiv=r.arms_imports_tiv,
            arms_exports_tiv=r.arms_exports_tiv,
            military_expenditure_pct_gdp=r.military_expenditure_pct_gdp,
        )
        for r in records
    ]


@app.get("/indicators/top/exporters", response_model=list[IndicatorOut])
async def get_top_exporters(year: int = Query(2024, ge=1960, le=2025)):
    """Get the top arms exporting countries for a given year."""
    client = WorldBankClient()
    records = await client.fetch_top_exporters(year)
    return [
        IndicatorOut(
            country_name=r.country_name, country_iso3=r.country_iso3,
            year=r.year, arms_imports_tiv=r.arms_imports_tiv,
            arms_exports_tiv=r.arms_exports_tiv,
            military_expenditure_pct_gdp=r.military_expenditure_pct_gdp,
        )
        for r in records
    ]


# --- Arms Trade News (GDELT) ---


class NewsOut(BaseModel):
    title: str
    url: str
    source: str
    source_country: str
    language: str
    published_at: str | None
    tone: float | None


@app.get("/news/latest", response_model=list[NewsOut])
async def get_latest_arms_news(
    hours: int = Query(24, ge=1, le=168),
):
    """Get latest arms trade news from global sources."""
    client = GDELTArmsNewsClient()
    articles = await client.fetch_latest_arms_news(timespan_minutes=hours * 60)
    return [
        NewsOut(
            title=a.title, url=a.url, source=a.source,
            source_country=a.source_country, language=a.language,
            published_at=a.published_at.isoformat() if a.published_at else None,
            tone=a.tone,
        )
        for a in articles
    ]


@app.get("/news/country/{country}", response_model=list[NewsOut])
async def get_country_arms_news(
    country: str,
    hours: int = Query(72, ge=1, le=168),
):
    """Get arms trade news mentioning a specific country."""
    client = GDELTArmsNewsClient()
    articles = await client.search_country_arms_news(country, timespan_minutes=hours * 60)
    return [
        NewsOut(
            title=a.title, url=a.url, source=a.source,
            source_country=a.source_country, language=a.language,
            published_at=a.published_at.isoformat() if a.published_at else None,
            tone=a.tone,
        )
        for a in articles
    ]


# --- Live Military Flights ---


class FlightOut(BaseModel):
    icao_hex: str
    callsign: str
    aircraft_type: str
    aircraft_description: str
    registration: str
    latitude: float
    longitude: float
    altitude_ft: float
    ground_speed_knots: float
    heading: float
    is_military: bool
    country_of_origin: str
    sources: list[str] = []


@app.get("/tracking/flights/military", response_model=list[FlightOut])
async def get_military_flights():
    """Get all currently visible military aircraft."""
    client = FlightTrackerClient()
    records = await client.fetch_military_aircraft()
    return [
        FlightOut(
            icao_hex=r.icao_hex, callsign=r.callsign,
            aircraft_type=r.aircraft_type,
            aircraft_description=r.aircraft_description,
            registration=r.registration,
            latitude=r.latitude, longitude=r.longitude,
            altitude_ft=r.altitude_ft,
            ground_speed_knots=r.ground_speed_knots,
            heading=r.heading,
            is_military=r.is_military,
            country_of_origin=r.country_of_origin,
            sources=r.sources,
        )
        for r in records
    ]


@app.get("/tracking/flights/transports", response_model=list[FlightOut])
async def get_transport_flights():
    """Get military transport aircraft (likely weapons/equipment carriers)."""
    client = FlightTrackerClient()
    records = await client.fetch_transport_aircraft()
    return [
        FlightOut(
            icao_hex=r.icao_hex, callsign=r.callsign,
            aircraft_type=r.aircraft_type,
            aircraft_description=r.aircraft_description,
            registration=r.registration,
            latitude=r.latitude, longitude=r.longitude,
            altitude_ft=r.altitude_ft,
            ground_speed_knots=r.ground_speed_knots,
            heading=r.heading,
            is_military=r.is_military,
            country_of_origin=r.country_of_origin,
            sources=r.sources,
        )
        for r in records
    ]
