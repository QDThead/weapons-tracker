"""Military transport flight tracker.

Uses adsb.lol (free, no auth) to detect military transport aircraft
movements that may indicate weapons deliveries.

Monitors: C-17 Globemaster, Il-76, An-124 Ruslan, A400M Atlas,
C-130 Hercules, C-5 Galaxy, Y-20, KC-390.

Reference: https://api.adsb.lol/docs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

ADSB_SOURCES = [
    {"name": "adsb.lol", "url": "https://api.adsb.lol/v2"},
    {"name": "adsb.fi", "url": "https://opendata.adsb.fi/api/v2"},
    {"name": "airplanes.live", "url": "https://api.airplanes.live/v2"},
]

# Military transport aircraft type designators (ICAO type codes)
MILITARY_TRANSPORT_TYPES = {
    "C17":  "C-17 Globemaster III",
    "IL76": "Il-76 Candid",
    "A124": "An-124 Ruslan",
    "A400": "A400M Atlas",
    "C130": "C-130 Hercules",
    "C30J": "C-130J Super Hercules",
    "C5":   "C-5 Galaxy",
    "C5M":  "C-5M Super Galaxy",
    "Y20":  "Y-20 Kunpeng",
    "KC39": "KC-390 Millennium",
    "C2":   "Kawasaki C-2",
    "A310": "A310 MRTT",
    "A330": "A330 MRTT",
    "KC10": "KC-10 Extender",
    "KC46": "KC-46 Pegasus",
}

# Known military operator ICAO hex ranges (partial — expand as needed)
# These are approximate; military hex ranges vary by country
MILITARY_HEX_PREFIXES = {
    "AE": "United States (military)",
    "AF": "United States (military)",
    "43C": "United Kingdom (military)",
    "3F": "Germany (military)",
    "C0": "Canada (military)",
}


@dataclass
class MilitaryFlightRecord:
    """A detected military transport aircraft position."""
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
    vertical_rate: float

    is_military: bool
    country_of_origin: str
    squawk: str

    seen_at: datetime
    sources: list[str] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = []


class FlightTrackerClient:
    """Client for tracking military transport flights via adsb.lol."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_military_aircraft(self) -> list[MilitaryFlightRecord]:
        """Fetch military aircraft from all sources, merge and deduplicate."""
        import asyncio

        async def _fetch_source(source: dict) -> list[MilitaryFlightRecord]:
            url = f"{source['url']}/mil"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                data = response.json()
                records = []
                for ac in data.get("ac", []):
                    record = self._parse_aircraft(ac)
                    if record:
                        record.sources = [source["name"]]
                        records.append(record)
                logger.info("Fetched %d aircraft from %s", len(records), source["name"])
                return records
            except Exception:
                logger.warning("Failed to fetch from %s", source["name"], exc_info=True)
                return []

        results = await asyncio.gather(*[_fetch_source(s) for s in ADSB_SOURCES])
        all_records = []
        for source_records in results:
            all_records.extend(source_records)

        deduped = self._deduplicate(all_records)
        logger.info("Multi-source: %d total, %d after dedup from %d sources",
                     len(all_records), len(deduped), len(ADSB_SOURCES))
        return deduped

    async def fetch_transport_aircraft(self) -> list[MilitaryFlightRecord]:
        """Fetch military transport aircraft specifically.

        Filters the military feed for known transport types.
        """
        all_military = await self.fetch_military_aircraft()
        transports = [
            r for r in all_military
            if r.aircraft_type in MILITARY_TRANSPORT_TYPES
        ]
        logger.info("Filtered to %d transport aircraft", len(transports))
        return transports

    async def fetch_by_type(self, type_code: str) -> list[MilitaryFlightRecord]:
        """Fetch all aircraft of a specific ICAO type code from all sources."""
        import asyncio

        async def _fetch_source(source: dict) -> list[MilitaryFlightRecord]:
            url = f"{source['url']}/type/{type_code}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                data = response.json()
                records = []
                for ac in data.get("ac", []):
                    record = self._parse_aircraft(ac)
                    if record:
                        record.sources = [source["name"]]
                        records.append(record)
                return records
            except Exception:
                logger.warning("Failed to fetch type %s from %s", type_code, source["name"], exc_info=True)
                return []

        results = await asyncio.gather(*[_fetch_source(s) for s in ADSB_SOURCES])
        all_records = []
        for source_records in results:
            all_records.extend(source_records)

        deduped = self._deduplicate(all_records)
        logger.info("Found %d aircraft of type %s (deduped from %d)", len(deduped), type_code, len(all_records))
        return deduped

    async def fetch_area(
        self, lat: float, lon: float, radius_nm: int = 100
    ) -> list[MilitaryFlightRecord]:
        """Fetch military aircraft within a radius of a point."""
        url = f"{ADSB_SOURCES[0]['url']}/point/{lat}/{lon}/{radius_nm}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        aircraft_list = data.get("ac", [])

        records = []
        for ac in aircraft_list:
            record = self._parse_aircraft(ac)
            if record and record.is_military:
                record.sources = [ADSB_SOURCES[0]["name"]]
                records.append(record)

        return records

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Safely convert a value to float.

        Handles non-numeric strings like "ground" returned by adsb.lol
        for alt_baro when aircraft are on the ground.
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _deduplicate(records: list[MilitaryFlightRecord]) -> list[MilitaryFlightRecord]:
        """Deduplicate aircraft by ICAO hex, merging source lists."""
        by_hex: dict[str, MilitaryFlightRecord] = {}
        for r in records:
            hex_key = r.icao_hex.upper()
            if hex_key in by_hex:
                existing = by_hex[hex_key]
                for src in r.sources:
                    if src not in existing.sources:
                        existing.sources.append(src)
            else:
                by_hex[hex_key] = r
        return list(by_hex.values())

    def _parse_aircraft(self, ac: dict) -> MilitaryFlightRecord | None:
        """Parse a raw ADS-B aircraft object into a MilitaryFlightRecord."""
        lat = ac.get("lat")
        lon = ac.get("lon")
        if lat is None or lon is None:
            return None

        icao_hex = ac.get("hex", "").strip()
        aircraft_type = ac.get("t", "")
        db_flags = ac.get("dbFlags", 0)
        is_military = bool(db_flags & 1)  # bit 0 = military

        # Determine country from hex prefix
        country = ""
        for prefix, country_name in MILITARY_HEX_PREFIXES.items():
            if icao_hex.upper().startswith(prefix):
                country = country_name
                break

        return MilitaryFlightRecord(
            icao_hex=icao_hex,
            callsign=ac.get("flight", "").strip(),
            aircraft_type=aircraft_type,
            aircraft_description=MILITARY_TRANSPORT_TYPES.get(aircraft_type, aircraft_type),
            registration=ac.get("r", ""),
            latitude=float(lat),
            longitude=float(lon),
            altitude_ft=self._safe_float(ac.get("alt_baro")),
            ground_speed_knots=self._safe_float(ac.get("gs")),
            heading=self._safe_float(ac.get("true_heading", ac.get("track", 0))),
            vertical_rate=self._safe_float(ac.get("baro_rate")),
            is_military=is_military,
            country_of_origin=country,
            squawk=ac.get("squawk", ""),
            seen_at=datetime.utcnow(),
        )
