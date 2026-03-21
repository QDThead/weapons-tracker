"""Russian and Chinese military flight pattern analyzer.

Identifies Russian and Chinese military transport aircraft from live
ADS-B data and flags flights heading toward regions of interest
(Africa, Middle East, South Asia, Arctic) that may indicate arms
deliveries or strategic positioning.

Aircraft identification is based on ICAO hex prefix allocations,
known registration patterns, callsign prefixes, and transport-
category ICAO type codes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from src.ingestion.flight_tracker import MilitaryFlightRecord

logger = logging.getLogger(__name__)

# ── Russian military identification ─────────────────────────────────

# ICAO 24-bit address range for Russia starts with hex "15"
RUSSIAN_HEX_PREFIXES = ("15",)

# Known Russian Air Force registration prefix
RUSSIAN_REGISTRATION_PREFIX = "RF-"

# Russian military callsign prefixes
RUSSIAN_CALLSIGN_PREFIXES = ("RFF",)

# Russian military transport / strategic airlift type codes
RUSSIAN_TRANSPORT_TYPES = {
    "IL76": "Il-76 Candid",
    "A124": "An-124 Ruslan",
    "AN12": "An-12 Cub",
    "IL18": "Il-18 Coot",
    "T154": "Tu-154 Careless",
    "AN26": "An-26 Curl",
}

# ── Chinese military identification ─────────────────────────────────

# ICAO 24-bit address range for Chinese military starts with "78"
CHINESE_HEX_PREFIXES = ("78",)

# Chinese military transport type codes (Y-20 indigenous + IL-76 fleet)
CHINESE_TRANSPORT_TYPES = {
    "Y20":  "Y-20 Kunpeng",
    "IL76": "Il-76 Candid",
}

# ── Regions of interest ─────────────────────────────────────────────


@dataclass
class BoundingBox:
    """Geographic bounding box for a region of interest."""
    name: str
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float

    def contains(self, lat: float, lon: float) -> bool:
        """Return True if the given coordinates fall within this box."""
        return (
            self.lat_min <= lat <= self.lat_max
            and self.lon_min <= lon <= self.lon_max
        )


REGIONS_OF_INTEREST = {
    "africa": BoundingBox(
        name="Africa",
        lat_min=-35.0, lat_max=37.0,
        lon_min=-18.0, lon_max=52.0,
    ),
    "middle_east": BoundingBox(
        name="Middle East",
        lat_min=12.0, lat_max=42.0,
        lon_min=25.0, lon_max=63.0,
    ),
    "south_asia": BoundingBox(
        name="South Asia",
        lat_min=5.0, lat_max=37.0,
        lon_min=60.0, lon_max=98.0,
    ),
}

ARCTIC_LAT_THRESHOLD = 65.0

# ── Dataclasses for analysis results ────────────────────────────────


@dataclass
class IdentifiedFlight:
    """A flight positively identified as Russian or Chinese military."""
    icao_hex: str
    callsign: str
    registration: str
    aircraft_type: str
    aircraft_description: str
    latitude: float
    longitude: float
    altitude_ft: float
    ground_speed_knots: float
    heading: float
    vertical_rate: float
    squawk: str
    origin_country: str
    identification_method: str  # e.g. "hex_prefix", "registration", "callsign", "type+military"
    seen_at: str


@dataclass
class SuspiciousRoute:
    """A Russian/Chinese military flight heading toward a region of interest."""
    flight: IdentifiedFlight
    regions: list[str]
    reason: str


@dataclass
class FlightAnalysisResult:
    """Complete analysis result returned by the analyzer."""
    timestamp: str
    total_military_scanned: int
    russian_military: list[IdentifiedFlight] = field(default_factory=list)
    chinese_military: list[IdentifiedFlight] = field(default_factory=list)
    suspicious_routes: list[SuspiciousRoute] = field(default_factory=list)
    arctic_activity: list[IdentifiedFlight] = field(default_factory=list)


# ── Analyzer ────────────────────────────────────────────────────────


class FlightPatternAnalyzer:
    """Analyzes live military flight data for Russian and Chinese patterns.

    Takes the raw flight list from adsb.lol (as MilitaryFlightRecord
    objects) and classifies aircraft by origin country, flags flights
    transiting regions of interest, and detects Arctic activity.
    """

    # ── Public interface ────────────────────────────────────────────

    def analyze_current_flights(
        self, flights: list[MilitaryFlightRecord]
    ) -> FlightAnalysisResult:
        """Analyze a list of military flights and return structured results.

        Args:
            flights: List of MilitaryFlightRecord from FlightTrackerClient.

        Returns:
            FlightAnalysisResult with Russian, Chinese, suspicious, and
            Arctic classifications.
        """
        russian: list[IdentifiedFlight] = []
        chinese: list[IdentifiedFlight] = []

        for flight in flights:
            ru_method = self._identify_russian(flight)
            if ru_method:
                russian.append(self._to_identified(flight, "Russia", ru_method))
                continue

            cn_method = self._identify_chinese(flight)
            if cn_method:
                chinese.append(self._to_identified(flight, "China", cn_method))

        # Suspicious routes: Russian or Chinese flights in/near buyer regions
        suspicious = self._find_suspicious_routes(russian + chinese)

        # Arctic activity: any identified flights above the threshold
        arctic = [
            f for f in russian + chinese
            if f.latitude >= ARCTIC_LAT_THRESHOLD
        ]

        result = FlightAnalysisResult(
            timestamp=datetime.utcnow().isoformat() + "Z",
            total_military_scanned=len(flights),
            russian_military=russian,
            chinese_military=chinese,
            suspicious_routes=suspicious,
            arctic_activity=arctic,
        )

        logger.info(
            "Flight pattern analysis complete: %d scanned, "
            "%d Russian, %d Chinese, %d suspicious, %d Arctic",
            result.total_military_scanned,
            len(result.russian_military),
            len(result.chinese_military),
            len(result.suspicious_routes),
            len(result.arctic_activity),
        )

        return result

    # ── Identification helpers ──────────────────────────────────────

    @staticmethod
    def _identify_russian(flight: MilitaryFlightRecord) -> str | None:
        """Return the identification method if this flight is Russian military, else None."""
        hex_upper = flight.icao_hex.upper()

        # Check ICAO hex prefix (strongest signal)
        for prefix in RUSSIAN_HEX_PREFIXES:
            if hex_upper.startswith(prefix):
                return "hex_prefix"

        # Check registration prefix (RF-XXXXX)
        if flight.registration and flight.registration.upper().startswith(RUSSIAN_REGISTRATION_PREFIX):
            return "registration"

        # Check callsign prefix
        callsign_upper = flight.callsign.upper().strip()
        for prefix in RUSSIAN_CALLSIGN_PREFIXES:
            if callsign_upper.startswith(prefix):
                return "callsign"

        # Check aircraft type combined with military flag
        if flight.aircraft_type in RUSSIAN_TRANSPORT_TYPES and flight.is_military:
            return "type+military"

        return None

    @staticmethod
    def _identify_chinese(flight: MilitaryFlightRecord) -> str | None:
        """Return the identification method if this flight is Chinese military, else None."""
        hex_upper = flight.icao_hex.upper()

        # Check ICAO hex prefix
        for prefix in CHINESE_HEX_PREFIXES:
            if hex_upper.startswith(prefix):
                return "hex_prefix"

        # Check aircraft type combined with military flag
        if flight.aircraft_type in CHINESE_TRANSPORT_TYPES and flight.is_military:
            return "type+military"

        return None

    @staticmethod
    def _find_suspicious_routes(
        flights: list[IdentifiedFlight],
    ) -> list[SuspiciousRoute]:
        """Flag flights currently over or heading toward arms buyer regions."""
        suspicious: list[SuspiciousRoute] = []

        for flight in flights:
            matched_regions: list[str] = []

            for key, region in REGIONS_OF_INTEREST.items():
                if region.contains(flight.latitude, flight.longitude):
                    matched_regions.append(region.name)

            if matched_regions:
                reason = (
                    f"{flight.origin_country} military {flight.aircraft_description} "
                    f"({flight.aircraft_type}) detected over "
                    f"{', '.join(matched_regions)} at "
                    f"FL{int(flight.altitude_ft / 100):03d}, "
                    f"heading {flight.heading:.0f} deg"
                )
                suspicious.append(SuspiciousRoute(
                    flight=flight,
                    regions=matched_regions,
                    reason=reason,
                ))

        return suspicious

    @staticmethod
    def _to_identified(
        flight: MilitaryFlightRecord,
        country: str,
        method: str,
    ) -> IdentifiedFlight:
        """Convert a MilitaryFlightRecord to an IdentifiedFlight."""
        # Resolve description: prefer Russian/Chinese specific descriptions
        # over the generic MILITARY_TRANSPORT_TYPES lookup done at parse time
        if country == "Russia":
            description = RUSSIAN_TRANSPORT_TYPES.get(
                flight.aircraft_type, flight.aircraft_description
            )
        elif country == "China":
            description = CHINESE_TRANSPORT_TYPES.get(
                flight.aircraft_type, flight.aircraft_description
            )
        else:
            description = flight.aircraft_description

        return IdentifiedFlight(
            icao_hex=flight.icao_hex,
            callsign=flight.callsign,
            registration=flight.registration,
            aircraft_type=flight.aircraft_type,
            aircraft_description=description,
            latitude=flight.latitude,
            longitude=flight.longitude,
            altitude_ft=flight.altitude_ft,
            ground_speed_knots=flight.ground_speed_knots,
            heading=flight.heading,
            vertical_rate=flight.vertical_rate,
            squawk=flight.squawk,
            origin_country=country,
            identification_method=method,
            seen_at=flight.seen_at.isoformat() + "Z",
        )
