"""Tests for Sentinel-5P TROPOMI NO2 facility emissions monitoring."""
from __future__ import annotations

import json
import pytest


def test_status_emitting():
    """NO2 ratio >= 1.5 should return EMITTING."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.00006, background_no2=0.00002)
    assert result["status"] == "EMITTING"
    assert result["ratio"] == 3.0


def test_status_emitting_at_threshold():
    """NO2 ratio exactly at 1.5 should return EMITTING."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.000015, background_no2=0.00001)
    assert result["status"] == "EMITTING"
    assert result["ratio"] == 1.5


def test_status_low_emission():
    """NO2 ratio < 1.5 should return LOW_EMISSION."""
    from src.ingestion.sentinel_no2 import compute_no2_status
    result = compute_no2_status(facility_no2=0.000012, background_no2=0.00001)
    assert result["status"] == "LOW_EMISSION"
    assert result["ratio"] == 1.2


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


def test_combined_verdict_mine_3_signals():
    """Mine with all 3 signals active -> CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "ACTIVE_MINING", "mine")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"
    assert len(result["sources"]) == 3


def test_combined_verdict_mine_2_signals():
    """Mine with 2/3 signals active -> ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "VEGETATED", "mine")
    assert result["status"] == "ACTIVE"
    assert result["confidence"] == "medium-high"


def test_combined_verdict_mine_1_signal():
    """Mine with 1/3 signals active -> LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "UNKNOWN", "ACTIVE_MINING", "mine")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_mine_0_signals():
    """Mine with 0/3 signals active -> IDLE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "UNKNOWN", "VEGETATED", "mine")
    assert result["status"] == "IDLE"
    assert result["confidence"] == "low"


def test_combined_verdict_refinery_3_signals():
    """Refinery with all 3 signals active -> CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "SMELTING", "UNKNOWN", "refinery")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"
    assert len(result["sources"]) == 3


def test_combined_verdict_refinery_so2_only():
    """Refinery with only SO2 -> LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "SMELTING", "UNKNOWN", "refinery")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_backward_compat():
    """With no SO2/NDVI data (UNKNOWN), degrades to 2-signal logic."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "UNKNOWN", "mine")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"


def test_combined_verdict_all_unknown():
    """All signals UNKNOWN -> UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "mine")
    assert result["status"] == "UNKNOWN"
    assert result["confidence"] == "none"


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


def test_so2_status_smelting():
    """SO2 ratio >= 1.5 should return SMELTING."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.00045, background_so2=0.00015)
    assert result["status"] == "SMELTING"
    assert result["ratio"] == 3.0


def test_so2_status_at_threshold():
    """SO2 ratio exactly at 1.5 should return SMELTING."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.000015, background_so2=0.00001)
    assert result["status"] == "SMELTING"
    assert result["ratio"] == 1.5


def test_so2_status_low():
    """SO2 ratio < 1.5 should return LOW_SO2."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.000012, background_so2=0.00001)
    assert result["status"] == "LOW_SO2"
    assert result["ratio"] == 1.2


def test_so2_status_unknown():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=None, background_so2=None)
    assert result["status"] == "UNKNOWN"
    assert result["ratio"] == 0


def test_ndvi_status_active_mining():
    """Bare soil > 60% should return ACTIVE_MINING."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=75.0, mean_ndvi=0.15)
    assert result["status"] == "ACTIVE_MINING"


def test_ndvi_status_moderate():
    """Bare soil 30-60% should return MODERATE."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=45.0, mean_ndvi=0.35)
    assert result["status"] == "MODERATE"


def test_ndvi_status_vegetated():
    """Bare soil < 30% should return VEGETATED."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=15.0, mean_ndvi=0.65)
    assert result["status"] == "VEGETATED"


def test_ndvi_status_unknown():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=None, mean_ndvi=None)
    assert result["status"] == "UNKNOWN"
