"""Tests for cobalt production data triangulation and HHI computation."""
from __future__ import annotations

import pytest
from src.analysis.confidence import (
    triangulate_cobalt_production,
    compute_cobalt_hhi,
    SourceDataPoint,
)


class TestSourceDataPoint:
    def test_creation(self):
        s = SourceDataPoint(name="USGS MCS 2025", value_t=170000, year=2024, tier="live")
        assert s.value_t == 170000
        assert s.tier == "live"


class TestTriangulation:
    def test_single_source_low_confidence(self):
        sources = [SourceDataPoint("USGS MCS 2025", 170000, 2024, "live")]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["triangulated"] is False
        assert result["confidence_level"] in ("low", "medium")
        assert result["source_count"] == 1

    def test_three_agreeing_sources_high_confidence(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 168000, 2024, "live"),
            SourceDataPoint("Comtrade implied", 172000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["triangulated"] is True
        assert result["confidence_level"] == "high"
        assert result["source_count"] == 3
        assert 165000 < result["production_t"] < 175000

    def test_discrepancy_detected(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 100000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert len(result["discrepancies"]) > 0
        disc = result["discrepancies"][0]
        assert disc["severity"] in ("warning", "critical")
        assert disc["delta_pct"] > 25

    def test_year_gap_noted(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 130000, 2022, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        discrepancies = result["discrepancies"]
        if discrepancies:
            assert discrepancies[0]["year_gap"] == 2

    def test_within_tolerance_no_discrepancy(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 167000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert len(result["discrepancies"]) == 0

    def test_empty_sources(self):
        result = triangulate_cobalt_production("DRC", [])
        assert result["source_count"] == 0
        assert result["triangulated"] is False
        assert result["confidence_level"] == "low"


class TestHHI:
    def test_monopoly_hhi(self):
        data = {"CountryA": 100000}
        hhi = compute_cobalt_hhi(data)
        assert hhi == 10000

    def test_duopoly_hhi(self):
        data = {"A": 50000, "B": 50000}
        hhi = compute_cobalt_hhi(data)
        assert hhi == 5000

    def test_cobalt_realistic_hhi(self):
        data = {
            "DRC": 170000,
            "Indonesia": 12000,
            "Russia": 8900,
            "Australia": 5900,
            "Philippines": 4800,
            "Canada": 3351,
            "Cuba": 3800,
            "Madagascar": 2800,
            "Other": 19449,
        }
        hhi = compute_cobalt_hhi(data)
        assert 5500 < hhi < 6500

    def test_zero_production(self):
        hhi = compute_cobalt_hhi({})
        assert hhi == 0
