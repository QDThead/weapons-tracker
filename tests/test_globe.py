"""tests/test_globe.py — Data integrity tests for mineral supply chain module."""
from __future__ import annotations

import pytest

from src.analysis.mineral_supply_chains import get_all_minerals, get_mineral_by_name


VALID_RISK_LEVELS = {"critical", "high", "medium", "low"}

REQUIRED_FIELDS = {
    "name", "category", "mining", "processing", "components",
    "platforms", "hhi", "risk_level", "source",
}


class TestMineralData:
    """Verify mineral supply chain data integrity."""

    def test_get_all_minerals_returns_30(self):
        minerals = get_all_minerals()
        assert len(minerals) == 30

    def test_each_mineral_has_required_fields(self):
        minerals = get_all_minerals()
        for mineral in minerals:
            for field in REQUIRED_FIELDS:
                assert field in mineral, f"{mineral.get('name', '?')} missing field '{field}'"
            assert isinstance(mineral["hhi"], int), (
                f"{mineral['name']} hhi should be int, got {type(mineral['hhi'])}"
            )
            assert mineral["risk_level"] in VALID_RISK_LEVELS, (
                f"{mineral['name']} risk_level '{mineral['risk_level']}' not valid"
            )

    def test_mining_entries_have_coordinates(self):
        minerals = get_all_minerals()
        for mineral in minerals:
            for entry in mineral["mining"]:
                assert "lat" in entry, f"{mineral['name']} mining entry missing lat"
                assert "lon" in entry, f"{mineral['name']} mining entry missing lon"
                assert "country" in entry, f"{mineral['name']} mining entry missing country"
                assert "pct" in entry, f"{mineral['name']} mining entry missing pct"
                assert -90 <= entry["lat"] <= 90, (
                    f"{mineral['name']} mining lat {entry['lat']} out of range"
                )
                assert -180 <= entry["lon"] <= 180, (
                    f"{mineral['name']} mining lon {entry['lon']} out of range"
                )

    def test_processing_entries_have_coordinates(self):
        minerals = get_all_minerals()
        for mineral in minerals:
            for entry in mineral["processing"]:
                assert "lat" in entry, f"{mineral['name']} processing entry missing lat"
                assert "lon" in entry, f"{mineral['name']} processing entry missing lon"
                assert "country" in entry, f"{mineral['name']} processing entry missing country"
                assert "pct" in entry, f"{mineral['name']} processing entry missing pct"
                assert -90 <= entry["lat"] <= 90, (
                    f"{mineral['name']} processing lat {entry['lat']} out of range"
                )
                assert -180 <= entry["lon"] <= 180, (
                    f"{mineral['name']} processing lon {entry['lon']} out of range"
                )

    def test_get_mineral_by_name(self):
        result = get_mineral_by_name("Titanium")
        assert result is not None
        assert result["name"] == "Titanium"

    def test_get_mineral_by_name_case_insensitive(self):
        result = get_mineral_by_name("titanium")
        assert result is not None
        assert result["name"] == "Titanium"

    def test_get_mineral_by_name_not_found(self):
        result = get_mineral_by_name("Unobtanium")
        assert result is None

    def test_chokepoints_have_coordinates(self):
        minerals = get_all_minerals()
        for mineral in minerals:
            for cp in mineral["chokepoints"]:
                assert "name" in cp, f"{mineral['name']} chokepoint missing name"
                assert "lat" in cp, f"{mineral['name']} chokepoint missing lat"
                assert "lon" in cp, f"{mineral['name']} chokepoint missing lon"
                assert -90 <= cp["lat"] <= 90, (
                    f"{mineral['name']} chokepoint lat {cp['lat']} out of range"
                )
                assert -180 <= cp["lon"] <= 180, (
                    f"{mineral['name']} chokepoint lon {cp['lon']} out of range"
                )

    def test_risk_factors_are_strings(self):
        minerals = get_all_minerals()
        for mineral in minerals:
            assert "risk_factors" in mineral, f"{mineral['name']} missing risk_factors"
            assert isinstance(mineral["risk_factors"], list), (
                f"{mineral['name']} risk_factors should be list"
            )
            for factor in mineral["risk_factors"]:
                assert isinstance(factor, str), (
                    f"{mineral['name']} risk_factor should be str, got {type(factor)}"
                )
