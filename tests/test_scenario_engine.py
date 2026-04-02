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


class TestMultiLayer:
    """Test multi-variable scenario composition."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_two_layers_compound_impact(self):
        result = self.engine.run(
            layers=[
                {"type": "sanctions_expansion", "params": {"country": "China"}},
                {"type": "route_disruption", "params": {"chokepoint": "Strait of Malacca", "duration_days": 90}},
            ],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        single = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"]["risk_score"] >= single["impact"]["risk_score"]

    def test_demand_surge_global_param(self):
        baseline = self.engine.run(layers=[], demand_surge_pct=0, time_horizon_months=12)
        surged = self.engine.run(layers=[], demand_surge_pct=50, time_horizon_months=12)
        assert surged["sufficiency"]["demand_t"] > baseline["sufficiency"]["demand_t"]

    def test_three_layers_all_types(self):
        result = self.engine.run(
            layers=[
                {"type": "sanctions_expansion", "params": {"country": "China"}},
                {"type": "material_shortage", "params": {"reduction_pct": 30}},
                {"type": "route_disruption", "params": {"chokepoint": "Suez Canal", "duration_days": 180}},
            ],
            demand_surge_pct=30,
            time_horizon_months=12,
        )
        assert result["impact"]["risk_rating"] == "CRITICAL"
        assert result["impact"]["platforms_affected"] > 0


class TestCascadeStructure:
    """Test cascade data shape for Sankey rendering."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_cascade_has_four_tiers(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert len(result["cascade"]["tiers"]) == 4
        tier_names = [t["name"] for t in result["cascade"]["tiers"]]
        assert tier_names == ["Mining", "Processing", "Alloys", "Platforms"]

    def test_cascade_nodes_have_required_fields(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        mining_node = result["cascade"]["tiers"][0]["nodes"][0]
        assert "name" in mining_node
        assert "country" in mining_node
        assert "status" in mining_node
        assert mining_node["status"] in ("operational", "degraded", "disrupted")

    def test_cascade_summary_present(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        summary = result["cascade"]["summary"]
        assert "mining_loss_pct" in summary
        assert "processing_loss_pct" in summary
        assert "alloy_loss_pct" in summary
        assert "platforms_at_risk" in summary

    def test_cascade_flows_present(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        flows = result["cascade"]["flows"]
        assert isinstance(flows, list)
        if flows:
            flow = flows[0]
            assert "from" in flow
            assert "to" in flow
            assert "status" in flow


class TestCOAGeneration:
    """Test COA auto-generation."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_coas_generated_for_sanctions(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        coas = result["coa"]
        assert len(coas) > 0
        actions = [c["action"] for c in coas]
        assert any("China" in a or "alternative" in a.lower() for a in actions)

    def test_coa_fields_complete(self):
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        for coa in result["coa"]:
            assert "id" in coa
            assert "action" in coa
            assert "priority" in coa
            assert coa["priority"] in ("critical", "high", "medium")
            assert "cost_estimate" in coa
            assert "risk_reduction_pts" in coa
            assert "timeline_months" in coa
            assert "affected_platforms" in coa
            assert isinstance(coa["affected_platforms"], list)

    def test_empty_scenario_no_coas(self):
        result = self.engine.run(layers=[], demand_surge_pct=0, time_horizon_months=12)
        layer_coa_ids = [c["id"] for c in result["coa"] if c["id"].startswith("COA-S") or c["id"].startswith("COA-R") or c["id"].startswith("COA-F")]
        assert len(layer_coa_ids) == 0


class TestLikelihoodScaling:
    """Verify likelihood uses raw probability without artificial scaling."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_single_sanctions_layer_likelihood(self):
        """Single sanctions layer at base 0.60 should produce ~0.60 likelihood, not ~0.96."""
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        likelihood = result["impact"]["likelihood"]
        assert likelihood <= 0.70, f"Likelihood {likelihood} too high — 2x scaling still active?"
        assert likelihood >= 0.50, f"Likelihood {likelihood} too low"

    def test_two_layer_compound_likelihood(self):
        """Two layers should compound: 1 - (1-0.6)(1-0.7) = 0.88."""
        result = self.engine.run(
            layers=[
                {"type": "sanctions_expansion", "params": {"country": "China"}},
                {"type": "material_shortage", "params": {"pct": 50}},
            ],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        likelihood = result["impact"]["likelihood"]
        assert 0.80 <= likelihood <= 0.95, f"Expected ~0.88, got {likelihood}"

    def test_likelihood_method_field_present(self):
        """Response should include likelihood_method field."""
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"].get("likelihood_method") == "combined_independent"
