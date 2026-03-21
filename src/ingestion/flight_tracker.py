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

ADSB_LOL_API = "https://api.adsb.lol/v2"

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


class FlightTrackerClient:
    """Client for tracking military transport flights via adsb.lol."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_military_aircraft(self) -> list[MilitaryFlightRecord]:
        """Fetch all currently visible military-flagged aircraft.

        Uses the adsb.lol military filter endpoint.
        """
        url = f"{ADSB_LOL_API}/mil"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Fetching military aircraft from adsb.lol")
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        aircraft_list = data.get("ac", [])

        records = []
        for ac in aircraft_list:
            record = self._parse_aircraft(ac)
            if record:
                records.append(record)

        logger.info("Detected %d military aircraft", len(records))
        return records

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
        """Fetch all aircraft of a specific ICAO type code.

        Args:
            type_code: ICAO type designator (e.g., "C17", "IL76").
        """
        url = f"{ADSB_LOL_API}/type/{type_code}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Fetching aircraft type %s from adsb.lol", type_code)
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        aircraft_list = data.get("ac", [])

        records = []
        for ac in aircraft_list:
            record = self._parse_aircraft(ac)
            if record:
                records.append(record)

        logger.info("Found %d aircraft of type %s", len(records), type_code)
        return records

    async def fetch_area(
        self, lat: float, lon: float, radius_nm: int = 100
    ) -> list[MilitaryFlightRecord]:
        """Fetch military aircraft within a radius of a point.

        Args:
            lat: Center latitude.
            lon: Center longitude.
            radius_nm: Radius in nautical miles.
        """
        url = f"{ADSB_LOL_API}/point/{lat}/{lon}/{radius_nm}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()

        data = response.json()
        aircraft_list = data.get("ac", [])

        records = []
        for ac in aircraft_list:
            record = self._parse_aircraft(ac)
            if record and record.is_military:
                records.append(record)

        return records

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
            altitude_ft=float(ac.get("alt_baro", 0) or 0),
            ground_speed_knots=float(ac.get("gs", 0) or 0),
            heading=float(ac.get("true_heading", ac.get("track", 0)) or 0),
            vertical_rate=float(ac.get("baro_rate", 0) or 0),
            is_military=is_military,
            country_of_origin=country,
            squawk=ac.get("squawk", ""),
            seen_at=datetime.utcnow(),
        )
