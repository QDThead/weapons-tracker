"""tests/test_globe.py — Data integrity tests for mineral supply chain module."""
from __future__ import annotations

import pytest

from src.analysis.mineral_supply_chains import get_all_minerals, get_mineral_by_name
from fastapi.testclient import TestClient
from src.api.routes import app
from src.api.globe_routes import router as globe_router

# Ensure globe router is included for tests
if not any(r.path.startswith("/globe") for r in app.routes):
    app.include_router(globe_router)

client = TestClient(app)


VALID_RISK_LEVELS = {"critical", "high", "medium", "low"}

REQUIRED_FIELDS = {
    "name", "category", "mining", "processing", "components",
    "platforms", "hhi", "risk_level", "source", "canada",
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


class TestGlobeAPI:
    """Test the /globe/* API endpoints."""

    def test_get_all_minerals(self):
        resp = client.get("/globe/minerals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 30
        assert data[0]["name"] == "Titanium"

    def test_get_mineral_by_name(self):
        resp = client.get("/globe/minerals/Gallium")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Gallium"
        assert data["hhi"] == 9800

    def test_get_mineral_by_name_case_insensitive(self):
        resp = client.get("/globe/minerals/gallium")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Gallium"

    def test_get_mineral_not_found(self):
        resp = client.get("/globe/minerals/Unobtanium")
        assert resp.status_code == 404

    def test_mineral_response_has_coordinates(self):
        resp = client.get("/globe/minerals/Cobalt")
        data = resp.json()
        assert data["mining"][0]["lat"] == -4.0  # DRC
        assert data["mining"][0]["lon"] == 21.8


class TestCobaltSufficiency:
    """Verify Cobalt sufficiency data structure integrity."""

    def test_cobalt_has_sufficiency_key(self):
        cobalt = get_mineral_by_name("Cobalt")
        assert cobalt is not None
        assert "sufficiency" in cobalt, "Cobalt missing 'sufficiency' key"

    def test_sufficiency_has_required_sections(self):
        suf = get_mineral_by_name("Cobalt")["sufficiency"]
        assert "demand" in suf
        assert "scenarios" in suf
        assert "coa" in suf
        assert "totals" in suf

    def test_demand_entries_have_required_fields(self):
        demand = get_mineral_by_name("Cobalt")["sufficiency"]["demand"]
        assert len(demand) == 16, f"Expected 16 demand entries, got {len(demand)}"
        for d in demand:
            assert "platform" in d, f"Demand entry missing 'platform'"
            assert "kg_yr" in d, f"{d.get('platform','?')} missing 'kg_yr'"
            assert "type" in d, f"{d.get('platform','?')} missing 'type'"
            assert d["type"] in ("direct", "indirect"), (
                f"{d['platform']} type must be 'direct' or 'indirect', got '{d['type']}'"
            )
            assert "threshold_ratio" in d, f"{d['platform']} missing 'threshold_ratio'"
            assert "fleet_note" in d, f"{d['platform']} missing 'fleet_note'"
            assert "risk_note" in d, f"{d['platform']} missing 'risk_note'"
            assert isinstance(d["kg_yr"], (int, float)), (
                f"{d['platform']} kg_yr must be numeric"
            )

    def test_indirect_entries_have_oem_fields(self):
        demand = get_mineral_by_name("Cobalt")["sufficiency"]["demand"]
        indirect = [d for d in demand if d["type"] == "indirect"]
        assert len(indirect) >= 9, f"Expected at least 9 indirect entries, got {len(indirect)}"
        for d in indirect:
            assert "oem" in d, f"{d['platform']} indirect entry missing 'oem'"
            assert "oem_country" in d, f"{d['platform']} indirect entry missing 'oem_country'"
            assert "engine" in d, f"{d['platform']} indirect entry missing 'engine'"

    def test_scenarios_structure(self):
        scenarios = get_mineral_by_name("Cobalt")["sufficiency"]["scenarios"]
        assert len(scenarios) == 5, f"Expected 5 scenarios, got {len(scenarios)}"
        for s in scenarios:
            assert "name" in s
            assert "position" in s
            assert "supply_t" in s
            assert "demand_t" in s
            assert "ratio" in s
            assert "verdict" in s
            assert 0 <= s["position"] <= 100, (
                f"Scenario '{s['name']}' position {s['position']} out of 0-100 range"
            )

    def test_scenarios_sorted_by_position(self):
        scenarios = get_mineral_by_name("Cobalt")["sufficiency"]["scenarios"]
        positions = [s["position"] for s in scenarios]
        assert positions == sorted(positions), "Scenarios must be sorted by position"

    def test_coa_entries_structure(self):
        coas = get_mineral_by_name("Cobalt")["sufficiency"]["coa"]
        assert len(coas) == 6, f"Expected 6 COA entries, got {len(coas)}"
        for c in coas:
            assert "id" in c
            assert "action" in c
            assert "cost" in c
            assert "impact" in c
            assert "relevant_scenarios" in c
            assert isinstance(c["relevant_scenarios"], list)

    def test_totals_structure(self):
        totals = get_mineral_by_name("Cobalt")["sufficiency"]["totals"]
        assert totals["steady_state_kg"] == 307
        assert totals["f35_ramp_kg"] == 740
        assert totals["direct_kg"] == 138
        assert totals["indirect_kg"] == 169
        assert totals["direct_kg"] + totals["indirect_kg"] == totals["steady_state_kg"]

    def test_demand_kg_sums_match_totals(self):
        suf = get_mineral_by_name("Cobalt")["sufficiency"]
        demand = suf["demand"]
        total_kg = sum(d["kg_yr"] for d in demand)
        direct_kg = sum(d["kg_yr"] for d in demand if d["type"] == "direct")
        indirect_kg = sum(d["kg_yr"] for d in demand if d["type"] == "indirect")
        assert abs(total_kg - suf["totals"]["steady_state_kg"]) <= 1, (
            f"Demand sum {total_kg} != steady_state_kg {suf['totals']['steady_state_kg']}"
        )
        assert abs(direct_kg - suf["totals"]["direct_kg"]) <= 1, (
            f"Direct sum {direct_kg} != direct_kg {suf['totals']['direct_kg']}"
        )
        assert abs(indirect_kg - suf["totals"]["indirect_kg"]) <= 1, (
            f"Indirect sum {indirect_kg} != indirect_kg {suf['totals']['indirect_kg']}"
        )


class TestCobaltNewData:
    """Verify new Cobalt sub-tab data structures."""

    def test_forecasting_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "forecasting" in m
        f = m["forecasting"]
        assert "price_forecast" in f
        assert "lead_time" in f
        assert "insolvency_risks" in f
        assert isinstance(f["insolvency_risks"], list)
        assert len(f["insolvency_risks"]) >= 1
        assert "signals" in f
        assert isinstance(f["signals"], list)
        assert len(f["signals"]) >= 3
        assert "price_history" in f
        assert isinstance(f["price_history"], list)

    def test_forecasting_signals_structure(self):
        signals = get_mineral_by_name("Cobalt")["forecasting"]["signals"]
        for s in signals:
            assert "text" in s
            assert "severity" in s
            assert s["severity"] in ("critical", "high", "medium", "low")

    def test_alerts_exist(self):
        m = get_mineral_by_name("Cobalt")
        assert "watchtower_alerts" in m
        alerts = m["watchtower_alerts"]
        assert isinstance(alerts, list)
        assert len(alerts) >= 6

    def test_alerts_structure(self):
        alerts = get_mineral_by_name("Cobalt")["watchtower_alerts"]
        for a in alerts:
            assert "id" in a
            assert "title" in a
            assert "severity" in a and 1 <= a["severity"] <= 5
            assert "category" in a
            assert "sources" in a and isinstance(a["sources"], list)
            assert "confidence" in a and 0 <= a["confidence"] <= 100
            assert "coa" in a
            assert "timestamp" in a

    def test_risk_register_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "risk_register" in m
        rr = m["risk_register"]
        assert isinstance(rr, list)
        assert len(rr) >= 8

    def test_risk_register_structure(self):
        rr = get_mineral_by_name("Cobalt")["risk_register"]
        valid_statuses = {"open", "in_progress", "mitigated", "closed"}
        valid_severities = {"critical", "high", "medium", "low"}
        for r in rr:
            assert "id" in r
            assert "risk" in r
            assert "category" in r
            assert "severity" in r and r["severity"] in valid_severities
            assert "status" in r and r["status"] in valid_statuses
            assert "owner" in r
            assert "due_date" in r
            assert "coas" in r and isinstance(r["coas"], list)

    def test_analyst_feedback_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "analyst_feedback" in m
        af = m["analyst_feedback"]
        assert "accuracy" in af and 0 <= af["accuracy"] <= 100
        assert "fp_rate" in af and 0 <= af["fp_rate"] <= 100
        assert "threshold" in af
        assert "pending" in af and isinstance(af["pending"], list)
        assert len(af["pending"]) >= 3
        assert "recent" in af and isinstance(af["recent"], list)
        assert len(af["recent"]) >= 5

    def test_analyst_feedback_pending_structure(self):
        pending = get_mineral_by_name("Cobalt")["analyst_feedback"]["pending"]
        for p in pending:
            assert "text" in p
            assert "source" in p
            assert "confidence" in p and 0 <= p["confidence"] <= 100

    def test_cobalt_figure_metadata(self):
        """All mines and refineries must have figure_type and figure_source."""
        m = get_mineral_by_name("Cobalt")
        valid_types = ("design_capacity", "actual_2025", "estimated_2025", "restart_estimate", "estimated", "quota_2026")
        for mine in m["mines"]:
            assert "figure_type" in mine, f"Mine {mine['name']} missing figure_type"
            assert "figure_source" in mine, f"Mine {mine['name']} missing figure_source"
            assert "figure_year" in mine, f"Mine {mine['name']} missing figure_year"
            assert mine["figure_type"] in valid_types, f"Mine {mine['name']} invalid figure_type: {mine['figure_type']}"
        for ref in m["refineries"]:
            assert "figure_type" in ref, f"Refinery {ref['name']} missing figure_type"
            assert "figure_source" in ref, f"Refinery {ref['name']} missing figure_source"
            assert "figure_year" in ref, f"Refinery {ref['name']} missing figure_year"

    def test_mine_dossier_exists(self):
        m = get_mineral_by_name("Cobalt")
        tfm = m["mines"][0]
        assert "dossier" in tfm
        d = tfm["dossier"]
        assert "z_score" in d
        assert "insolvency_prob" in d
        assert "ubo_chain" in d and isinstance(d["ubo_chain"], list)
        assert "recent_intel" in d and isinstance(d["recent_intel"], list)


class TestCobaltForecasting:
    """Test the cobalt forecasting computation engine."""

    def test_linear_regression(self):
        from src.analysis.cobalt_forecasting import _linear_regression
        slope, intercept = _linear_regression([1, 2, 3, 4], [2, 4, 6, 8])
        assert abs(slope - 2.0) < 0.01
        assert abs(intercept - 0.0) < 0.01

    def test_compute_lead_time(self):
        from src.analysis.cobalt_forecasting import _compute_lead_time
        m = get_mineral_by_name("Cobalt")
        lt = _compute_lead_time(m)
        assert lt["base_transit_days"] > 0
        assert lt["chokepoint_count"] > 0
        assert lt["days"] > 0
        assert "primary_route" in lt

    def test_compute_insolvency_risks(self):
        from src.analysis.cobalt_forecasting import _compute_insolvency_risks
        m = get_mineral_by_name("Cobalt")
        risks = _compute_insolvency_risks(m)
        assert isinstance(risks, list)
        assert len(risks) > 0
        # Should be sorted by probability descending
        probs = [r["probability_pct"] for r in risks]
        assert probs == sorted(probs, reverse=True)
        for r in risks:
            assert "supplier" in r
            assert "probability_pct" in r
            assert 0 <= r["probability_pct"] <= 100

    def test_compute_price_forecast_with_empty_data(self):
        from src.analysis.cobalt_forecasting import _compute_price_forecast
        result = _compute_price_forecast([])
        assert result["status"] == "no_data"

    def test_compute_price_forecast_with_data(self):
        from src.analysis.cobalt_forecasting import _compute_price_forecast
        prices = [
            {"date": "2025-01-01", "usd_mt": 15000},
            {"date": "2025-02-01", "usd_mt": 15200},
            {"date": "2025-03-01", "usd_mt": 15500},
            {"date": "2025-04-01", "usd_mt": 15100},
            {"date": "2025-05-01", "usd_mt": 15300},
            {"date": "2025-06-01", "usd_mt": 15600},
        ]
        result = _compute_price_forecast(prices)
        assert "price_forecast" in result
        assert "price_history" in result
        assert len(result["price_history"]) > len(prices) // 3  # quarters + forecasts
        # Should have forecast entries
        forecast_entries = [p for p in result["price_history"] if p["type"] == "forecast"]
        assert len(forecast_entries) == 4
