"""tests/test_scenario_engine.py — Unit tests for ScenarioEngine."""
from __future__ import annotations

import pytest

from src.analysis.scenario_engine import ScenarioEngine


class TestSingleLayers:
    """Test individual disruption layer types."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_sanctions_layer_zeros_country_nodes(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert "impact" in result
        assert "cascade" in result
        assert "coa" in result
        assert "sufficiency" in result
        assert result["impact"]["supply_reduction_pct"] > 0
        assert result["impact"]["supply_reduction_pct"] >= 50

    def test_sanctions_layer_has_required_impact_fields(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        impact = result["impact"]
        assert "value_at_risk_usd" in impact
        assert "platforms_affected" in impact
        assert "risk_score" in impact
        assert "risk_rating" in impact
        assert "likelihood" in impact
        assert "supply_reduction_pct" in impact
        assert "lead_time_increase_days" in impact
        assert isinstance(impact["value_at_risk_usd"], (int, float))
        assert impact["risk_rating"] in ("LOW", "HIGH", "CRITICAL")

    def test_material_shortage_layer(self):
        result = self.engine.run(
            layers=[{"type": "material_shortage", "params": {"reduction_pct": 40}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"]["supply_reduction_pct"] >= 30
        assert result["sufficiency"]["ratio"] < 1.0

    def test_route_disruption_layer(self):
        result = self.engine.run(
            layers=[{"type": "route_disruption", "params": {"chokepoint": "Strait of Malacca", "duration_days": 90}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"]["lead_time_increase_days"] > 0

    def test_supplier_failure_layer(self):
        result = self.engine.run(
            layers=[{"type": "supplier_failure", "params": {"entity": "Mutanda Mine", "failure_type": "insolvency"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"]["supply_reduction_pct"] > 0

    def test_demand_surge_layer(self):
        result = self.engine.run(
            layers=[{"type": "demand_surge", "params": {"region": "NATO", "increase_pct": 50}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["sufficiency"]["demand_t"] > result["sufficiency"]["supply_t"] or result["impact"]["risk_score"] > 0

    def test_unknown_mineral_raises(self):
        engine = ScenarioEngine("Unobtainium")
        with pytest.raises(ValueError, match="Unknown mineral"):
            engine.run(layers=[], demand_surge_pct=0, time_horizon_months=12)

    def test_empty_layers_returns_baseline(self):
        result = self.engine.run(layers=[], demand_surge_pct=0, time_horizon_months=12)
        assert result["impact"]["supply_reduction_pct"] == 0
        assert result["impact"]["risk_score"] == 0
        assert result["impact"]["risk_rating"] == "LOW"
        assert result["sufficiency"]["ratio"] >= 0.9
