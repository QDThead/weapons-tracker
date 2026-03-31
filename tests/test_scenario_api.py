"""tests/test_scenario_api.py — Integration tests for scenario v2 API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


class TestScenarioV2Endpoint:
    """Test POST /psi/scenario/v2."""

    def test_single_layer_returns_200(self):
        resp = client.post("/psi/scenario/v2", json={
            "mineral": "Cobalt",
            "layers": [{"type": "sanctions_expansion", "params": {"country": "China"}}],
            "demand_surge_pct": 0,
            "time_horizon_months": 12,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "scenario_id" in data
        assert "impact" in data
        assert "cascade" in data
        assert "coa" in data
        assert "sufficiency" in data

    def test_multi_layer_returns_200(self):
        resp = client.post("/psi/scenario/v2", json={
            "mineral": "Cobalt",
            "layers": [
                {"type": "sanctions_expansion", "params": {"country": "China"}},
                {"type": "route_disruption", "params": {"chokepoint": "Strait of Malacca", "duration_days": 90}},
            ],
            "demand_surge_pct": 30,
            "time_horizon_months": 12,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact"]["risk_score"] > 0

    def test_empty_layers_returns_baseline(self):
        resp = client.post("/psi/scenario/v2", json={
            "mineral": "Cobalt",
            "layers": [],
            "demand_surge_pct": 0,
            "time_horizon_months": 12,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["impact"]["risk_score"] == 0

    def test_unknown_mineral_returns_400(self):
        resp = client.post("/psi/scenario/v2", json={
            "mineral": "Unobtainium",
            "layers": [],
            "demand_surge_pct": 0,
            "time_horizon_months": 12,
        })
        assert resp.status_code == 400

    def test_cascade_has_four_tiers(self):
        resp = client.post("/psi/scenario/v2", json={
            "mineral": "Cobalt",
            "layers": [{"type": "material_shortage", "params": {"reduction_pct": 50}}],
            "demand_surge_pct": 0,
            "time_horizon_months": 12,
        })
        data = resp.json()
        assert len(data["cascade"]["tiers"]) == 4
