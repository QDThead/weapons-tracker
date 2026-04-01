"""Tests for multi-source flight tracking."""
from __future__ import annotations

import pytest
from src.ingestion.flight_tracker import (
    FlightTrackerClient,
    MilitaryFlightRecord,
    ADSB_SOURCES,
)
from datetime import datetime


class TestAdsbSources:
    def test_three_sources_defined(self):
        assert len(ADSB_SOURCES) == 3

    def test_sources_have_required_fields(self):
        for src in ADSB_SOURCES:
            assert "name" in src
            assert "url" in src
            assert src["url"].startswith("https://")

    def test_adsb_lol_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "adsb.lol" in names

    def test_adsb_fi_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "adsb.fi" in names

    def test_airplanes_live_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "airplanes.live" in names


class TestDeduplication:
    def _make_record(self, hex, callsign="TEST", type="C17", sources=None):
        return MilitaryFlightRecord(
            icao_hex=hex, callsign=callsign, aircraft_type=type,
            aircraft_description="Test", registration="",
            latitude=65.0, longitude=-95.0, altitude_ft=35000,
            ground_speed_knots=450, heading=340, vertical_rate=0,
            is_military=True, country_of_origin="",
            squawk="", seen_at=datetime.utcnow(), sources=sources or [],
        )

    def test_dedup_keeps_unique(self):
        client = FlightTrackerClient()
        records = [
            self._make_record("AE1234", sources=["adsb.lol"]),
            self._make_record("AE5678", sources=["adsb.fi"]),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 2

    def test_dedup_merges_sources(self):
        client = FlightTrackerClient()
        records = [
            self._make_record("AE1234", sources=["adsb.lol"]),
            self._make_record("AE1234", sources=["adsb.fi"]),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 1
        assert "adsb.lol" in deduped[0].sources
        assert "adsb.fi" in deduped[0].sources

    def test_dedup_three_sources(self):
        client = FlightTrackerClient()
        records = [
            self._make_record("AE1234", sources=["adsb.lol"]),
            self._make_record("AE1234", sources=["adsb.fi"]),
            self._make_record("AE1234", sources=["airplanes.live"]),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 1
        assert len(deduped[0].sources) == 3

    def test_dedup_case_insensitive(self):
        client = FlightTrackerClient()
        records = [
            self._make_record("ae1234", sources=["adsb.lol"]),
            self._make_record("AE1234", sources=["adsb.fi"]),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 1


class TestSourcesField:
    def test_record_has_sources_field(self):
        r = MilitaryFlightRecord(
            icao_hex="AE1234", callsign="TEST", aircraft_type="C17",
            aircraft_description="C-17", registration="",
            latitude=0, longitude=0, altitude_ft=0,
            ground_speed_knots=0, heading=0, vertical_rate=0,
            is_military=True, country_of_origin="",
            squawk="", seen_at=datetime.utcnow(), sources=["adsb.lol"],
        )
        assert hasattr(r, "sources")
        assert r.sources == ["adsb.lol"]

    def test_record_default_sources_empty(self):
        r = MilitaryFlightRecord(
            icao_hex="AE1234", callsign="TEST", aircraft_type="C17",
            aircraft_description="C-17", registration="",
            latitude=0, longitude=0, altitude_ft=0,
            ground_speed_knots=0, heading=0, vertical_rate=0,
            is_military=True, country_of_origin="",
            squawk="", seen_at=datetime.utcnow(),
        )
        assert r.sources == []
