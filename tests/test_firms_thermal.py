"""Tests for NASA FIRMS thermal facility monitoring."""
from __future__ import annotations

import pytest

from src.ingestion.firms_thermal import (
    FACILITY_CONFIG,
    FIRMSThermalClient,
    _compute_status,
    _make_bbox,
)


class TestFacilityConfig:
    def test_has_all_18_facilities(self):
        assert len(FACILITY_CONFIG) == 18

    def test_coords_are_valid(self):
        for name, cfg in FACILITY_CONFIG.items():
            assert -90 <= cfg["lat"] <= 90, f"{name} lat out of range"
            assert -180 <= cfg["lon"] <= 180, f"{name} lon out of range"
            assert 0.01 <= cfg["radius_deg"] <= 0.1, f"{name} radius out of range"

    def test_known_facilities_present(self):
        expected = [
            "Tenke Fungurume (TFM)", "Kisanfu (KFM)", "Kamoto (KCC)", "Mutanda",
            "Murrin Murrin", "Moa JV", "Voisey's Bay", "Sudbury Basin", "Raglan Mine",
            "Huayou Cobalt", "GEM Co.", "Jinchuan Group", "Umicore Kokkola",
            "Umicore Hoboken", "Fort Saskatchewan", "Long Harbour NPP",
            "Niihama Nickel Refinery", "Harjavalta",
        ]
        for name in expected:
            assert name in FACILITY_CONFIG, f"Missing facility: {name}"


class TestBoundingBox:
    def test_bbox_computation(self):
        west, south, east, north = _make_bbox(lat=-10.57, lon=26.20, radius_deg=0.08)
        assert abs(west - 26.12) < 0.001
        assert abs(south - (-10.65)) < 0.001
        assert abs(east - 26.28) < 0.001
        assert abs(north - (-10.49)) < 0.001


class TestComputeStatus:
    def test_active_with_detections(self):
        detections = [
            {"bright_ti4": 340.0, "frp": 12.0, "confidence": "high", "acq_date": "2026-04-02", "acq_time": "1342"},
            {"bright_ti4": 338.0, "frp": 10.5, "confidence": "nominal", "acq_date": "2026-04-01", "acq_time": "0215"},
        ]
        result = _compute_status(detections)
        assert result["status"] == "ACTIVE"
        assert result["detection_count"] == 2
        assert result["max_brightness_k"] == 340.0
        assert result["avg_frp_mw"] == 11.25

    def test_idle_no_detections(self):
        result = _compute_status([])
        assert result["status"] == "IDLE"
        assert result["detection_count"] == 0

    def test_unknown_on_none(self):
        result = _compute_status(None)
        assert result["status"] == "UNKNOWN"


class TestFallbackData:
    def test_fallback_has_all_facilities(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert len(data) == 18

    def test_fallback_moa_is_idle(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert data["Moa JV"]["status"] == "IDLE"

    def test_fallback_tfm_is_active(self):
        client = FIRMSThermalClient(map_key="")
        data = client._fallback_data()
        assert data["Tenke Fungurume (TFM)"]["status"] == "ACTIVE"
        assert data["Tenke Fungurume (TFM)"]["detection_count"] > 0
