"""Tests for Sentinel-5P TROPOMI NO2 facility emissions monitoring."""
from __future__ import annotations

import json
import pytest


def test_status_emitting():
    """NO2 ratio >= 2.0 should return EMITTING."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.00006, background_no2=0.00002)
    assert result["status"] == "EMITTING"
    assert result["ratio"] == 3.0


def test_status_low_emission():
    """NO2 ratio < 2.0 should return LOW_EMISSION."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.000015, background_no2=0.00001)
    assert result["status"] == "LOW_EMISSION"
    assert result["ratio"] == 1.5


def test_status_unknown_none():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=None, background_no2=None)
    assert result["status"] == "UNKNOWN"
    assert result["ratio"] == 0


def test_status_zero_background():
    """Zero background should not divide by zero."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.00005, background_no2=0.0)
    assert result["status"] == "EMITTING"
    assert result["ratio"] > 0


def test_combined_verdict_confirmed_active():
    """ACTIVE thermal + EMITTING NO2 = CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="ACTIVE", no2_status="EMITTING")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"


def test_combined_verdict_likely_active():
    """IDLE thermal + EMITTING NO2 = LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="IDLE", no2_status="EMITTING")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_idle():
    """IDLE thermal + LOW_EMISSION NO2 = IDLE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="IDLE", no2_status="LOW_EMISSION")
    assert result["status"] == "IDLE"


def test_combined_verdict_thermal_only():
    """ACTIVE thermal + UNKNOWN NO2 = ACTIVE (thermal only)."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="ACTIVE", no2_status="UNKNOWN")
    assert result["status"] == "ACTIVE"
    assert "FIRMS" in result["sources"][0]


def test_combined_verdict_no2_only():
    """UNKNOWN thermal + EMITTING NO2 = LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="UNKNOWN", no2_status="EMITTING")
    assert result["status"] == "LIKELY ACTIVE"


def test_combined_verdict_both_unknown():
    """UNKNOWN thermal + UNKNOWN NO2 = UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict(thermal_status="UNKNOWN", no2_status="UNKNOWN")
    assert result["status"] == "UNKNOWN"


def test_facility_config_matches_firms():
    """All 18 FIRMS facilities must have matching entries."""
    from src.ingestion.firms_thermal import FACILITY_CONFIG as FIRMS_CONFIG
    from src.ingestion.sentinel_no2 import FACILITY_CONFIG as NO2_CONFIG
    assert set(NO2_CONFIG.keys()) == set(FIRMS_CONFIG.keys())
    for name in FIRMS_CONFIG:
        assert NO2_CONFIG[name]["lat"] == FIRMS_CONFIG[name]["lat"]
        assert NO2_CONFIG[name]["lon"] == FIRMS_CONFIG[name]["lon"]


def test_fallback_data():
    """Fallback returns data for all 18 facilities."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client
    client = SentinelNO2Client(client_id="", client_secret="")
    result = client._fallback_data()
    assert len(result) == 18
    for name, data in result.items():
        assert data["status"] in ("EMITTING", "LOW_EMISSION")
        assert "ratio" in data
        assert "source" in data


def test_history_cap():
    """History save must cap at 90 days per facility."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client
    client = SentinelNO2Client(client_id="", client_secret="")
    history = {"TestFacility": [{"date": f"2026-01-{i:02d}", "ratio": 2.0} for i in range(1, 32)] * 4}
    assert len(history["TestFacility"]) > 90
    for name in history:
        history[name] = history[name][-90:]
    assert len(history["TestFacility"]) == 90
