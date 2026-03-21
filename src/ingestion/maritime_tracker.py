"""Maritime arms shipment tracker.

Uses aisstream.io (free WebSocket) to monitor vessel movements
for potential arms transport — focusing on Ro-Ro ships, military
logistics vessels, and traffic through key chokepoints.

Reference: https://aisstream.io/
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import websockets

logger = logging.getLogger(__name__)

AISSTREAM_WS_URL = "wss://stream.aisstream.io/v0/stream"

# Key maritime chokepoints for arms shipments
CHOKEPOINTS = {
    "Strait of Hormuz": [[25.5, 55.5], [27.0, 57.0]],
    "Suez Canal": [[29.5, 32.0], [31.5, 33.0]],
    "Strait of Malacca": [[-1.0, 99.0], [4.0, 104.0]],
    "Bab el-Mandeb": [[12.0, 43.0], [13.5, 44.0]],
    "Bosphorus": [[40.9, 28.8], [41.3, 29.2]],
    "English Channel": [[49.5, -2.0], [51.5, 2.0]],
    "Panama Canal": [[8.5, -80.0], [9.5, -79.0]],
    "Northwest Passage": [[68.0, -130.0], [76.0, -60.0]],
    "Halifax NS": [[44.0, -64.5], [45.0, -63.0]],
    "Esquimalt BC": [[48.0, -124.0], [49.0, -123.0]],
}

# AIS ship type codes for vessels of interest
# 50-59: Special craft, 35: Military ops
MILITARY_SHIP_TYPES = {35, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59}

# Ro-Ro and cargo types that commonly carry military vehicles
RORO_CARGO_TYPES = {
    70, 71, 72, 73, 74, 75, 76, 77, 78, 79,  # Cargo ships
}


@dataclass
class VesselPosition:
    """A vessel position update from AIS."""
    mmsi: int
    name: str
    ship_type: int
    callsign: str
    flag: str

    latitude: float
    longitude: float
    course: float
    speed: float
    heading: float

    destination: str
    eta: str
    draught: float

    is_military: bool
    is_roro_cargo: bool
    chokepoint: str | None

    seen_at: datetime


class MaritimeTrackerClient:
    """Client for monitoring maritime vessel movements via aisstream.io."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("AISSTREAM_API_KEY", "")

    def _build_subscribe_message(self, bounding_boxes: list[list] | None = None) -> str:
        """Build the WebSocket subscription message."""
        if bounding_boxes is None:
            # Default: monitor all chokepoints
            bounding_boxes = list(CHOKEPOINTS.values())

        return json.dumps({
            "APIKey": self.api_key,
            "BoundingBoxes": bounding_boxes,
            "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
        })

    async def stream_positions(
        self,
        callback: Callable[[VesselPosition], None],
        bounding_boxes: list[list] | None = None,
        duration_seconds: int = 300,
    ):
        """Stream vessel positions via WebSocket.

        Args:
            callback: Function called for each vessel position.
            bounding_boxes: Geographic areas to monitor.
            duration_seconds: How long to stream (default 5 min).
        """
        subscribe_msg = self._build_subscribe_message(bounding_boxes)

        logger.info("Connecting to aisstream.io WebSocket")
        async with websockets.connect(AISSTREAM_WS_URL) as ws:
            await ws.send(subscribe_msg)
            logger.info("Subscribed to AIS stream")

            end_time = asyncio.get_event_loop().time() + duration_seconds

            while asyncio.get_event_loop().time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(msg)
                    position = self._parse_message(data)
                    if position:
                        callback(position)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.warning("Error processing AIS message: %s", e)

        logger.info("AIS stream session ended")

    async def snapshot_chokepoint(
        self, chokepoint_name: str, duration_seconds: int = 60
    ) -> list[VesselPosition]:
        """Capture a snapshot of vessels at a specific chokepoint.

        Args:
            chokepoint_name: Name from CHOKEPOINTS dict.
            duration_seconds: How long to collect (default 60s).

        Returns:
            List of unique vessel positions seen.
        """
        if chokepoint_name not in CHOKEPOINTS:
            raise ValueError(f"Unknown chokepoint: {chokepoint_name}. Available: {list(CHOKEPOINTS.keys())}")

        bbox = CHOKEPOINTS[chokepoint_name]
        vessels: dict[int, VesselPosition] = {}

        def collect(position: VesselPosition):
            position.chokepoint = chokepoint_name
            vessels[position.mmsi] = position

        await self.stream_positions(
            callback=collect,
            bounding_boxes=[bbox],
            duration_seconds=duration_seconds,
        )

        return list(vessels.values())

    def _parse_message(self, data: dict) -> VesselPosition | None:
        """Parse an aisstream.io message into a VesselPosition."""
        msg_type = data.get("MessageType")
        if msg_type != "PositionReport":
            return None

        message = data.get("Message", {}).get("PositionReport", {})
        meta = data.get("MetaData", {})

        lat = message.get("Latitude")
        lon = message.get("Longitude")
        if lat is None or lon is None:
            return None

        mmsi = meta.get("MMSI", 0)
        ship_type = meta.get("ShipType", 0)

        # Determine which chokepoint (if any)
        chokepoint = None
        for name, bbox in CHOKEPOINTS.items():
            if (bbox[0][0] <= lat <= bbox[1][0] and bbox[0][1] <= lon <= bbox[1][1]):
                chokepoint = name
                break

        return VesselPosition(
            mmsi=mmsi,
            name=meta.get("ShipName", "").strip(),
            ship_type=ship_type,
            callsign=message.get("CallSign", ""),
            flag=meta.get("country_iso3", ""),
            latitude=lat,
            longitude=lon,
            course=message.get("Cog", 0),
            speed=message.get("Sog", 0),
            heading=message.get("TrueHeading", 0),
            destination=meta.get("Destination", ""),
            eta=meta.get("ETA", ""),
            draught=meta.get("Draught", 0),
            is_military=ship_type in MILITARY_SHIP_TYPES,
            is_roro_cargo=ship_type in RORO_CARGO_TYPES,
            chokepoint=chokepoint,
            seen_at=datetime.utcnow(),
        )
