"""Scenario Sandbox engine — multi-variable disruption simulation.

Computes cascading supply chain impacts for a selected mineral by
composing stackable disruption layers (sanctions, shortages, route
disruptions, supplier failures, demand surges).
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from src.analysis.mineral_supply_chains import CHOKEPOINTS, get_mineral_by_name


# Platform program values (annual sustainment, CAD approx → USD)
_PLATFORM_VALUES_USD: dict[str, int] = {
    "CF-18 Hornet": 500_000_000,
    "CF-188 Hornet": 500_000_000,
    "CP-140 Aurora": 350_000_000,
    "CC-150 Polaris": 120_000_000,
    "CH-148 Cyclone": 280_000_000,
    "CH-149 Cormorant": 200_000_000,
    "CC-177 Globemaster": 300_000_000,
    "CC-130J Hercules": 250_000_000,
    "CT-114 Tutor": 80_000_000,
    "F-35A Lightning II": 1_200_000_000,
    "Halifax-class Frigate": 400_000_000,
}

# Base likelihood per layer type (combined multiplicatively)
_LAYER_LIKELIHOODS: dict[str, float] = {
    "sanctions_expansion": 0.60,
    "material_shortage": 0.70,
    "route_disruption": 0.50,
    "supplier_failure": 0.40,
    "demand_surge": 0.80,
}


class ScenarioEngine:
    """Multi-variable scenario simulation for a single mineral."""

    def __init__(self, mineral_name: str) -> None:
        self.mineral_name = mineral_name
        self.mineral_data = get_mineral_by_name(mineral_name)

    def run(
        self,
        layers: list[dict],
        demand_surge_pct: float = 0,
        time_horizon_months: int = 12,
    ) -> dict:
        """Run a multi-layer scenario and return unified results."""
        if not self.mineral_data:
            raise ValueError(f"Unknown mineral: {self.mineral_name}")

        scenario_id = f"sc-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"

        # Build working state from mineral data
        state = self._build_baseline_state()

        # Apply each layer sequentially
        for layer in layers:
            self._apply_layer(state, layer)

        # Apply global demand surge
        if demand_surge_pct != 0:
            state["demand_t"] = state["demand_t"] * (1 + demand_surge_pct / 100)

        # Propagate cascade through tiers
        cascade = self._propagate_cascade(state)

        # Compute impact metrics
        impact = self._compute_impact(state, cascade, layers, time_horizon_months)

        # Generate COAs
        coa = self._generate_coas(state, layers, impact)

        # Compute sufficiency — scale baseline supply by disruption ratio
        node_total = state.get("node_supply_total", state["baseline_supply_t"])
        disruption_ratio = state["effective_supply_t"] / max(node_total, 1)
        supply_t = state["baseline_supply_t"] * disruption_ratio
        demand_t = state["demand_t"]
        ratio = supply_t / demand_t if demand_t > 0 else 999
        if ratio >= 0.9:
            verdict = "Sufficient"
        else:
            deficit_pct = round((1 - ratio) * 100)
            verdict = f"{deficit_pct}% deficit" + (" — CRITICAL" if ratio < 0.5 else "")

        return {
            "scenario_id": scenario_id,
            "mineral": self.mineral_name,
            "layers": layers,
            "impact": impact,
            "cascade": cascade,
            "coa": coa,
            "sufficiency": {
                "supply_t": round(supply_t, 1),
                "demand_t": round(demand_t, 1),
                "ratio": round(ratio, 3),
                "verdict": verdict,
            },
        }

    def _build_baseline_state(self) -> dict:
        """Build a mutable working state from the mineral data."""
        m = self.mineral_data
        suf = m.get("sufficiency", {})

        # Mines with capacity
        mines = []
        for mine in m.get("mines", []):
            mines.append({
                "name": mine["name"],
                "country": mine["country"],
                "owner": mine.get("owner", "Unknown"),
                "production_t": mine.get("production_t", 0),
                "capacity_remaining_pct": 100,
                "status": "operational",
            })

        # Refineries with capacity
        refineries = []
        for ref in m.get("refineries", []):
            refineries.append({
                "name": ref["name"],
                "country": ref["country"],
                "owner": ref.get("owner", "Unknown"),
                "capacity_t": ref.get("capacity_t", 0),
                "capacity_remaining_pct": 100,
                "status": "operational",
            })

        # Alloys
        alloys = []
        for alloy in suf.get("alloys", m.get("components", [])):
            if isinstance(alloy, dict) and "alloy" in alloy:
                alloys.append({
                    "name": alloy["alloy"],
                    "co_pct": alloy.get("co_pct", 0),
                    "use": alloy.get("use", ""),
                    "capacity_remaining_pct": 100,
                    "status": "operational",
                })

        # Platforms from sufficiency demand data
        platforms = []
        for d in suf.get("demand", []):
            platforms.append({
                "name": d["platform"],
                "engine": d.get("engine", ""),
                "kg_yr": d.get("kg_yr", 0),
                "type": d.get("type", "direct"),
                "threshold_ratio": d.get("threshold_ratio", 0.5),
                "status": "operational",
                "value_usd": _PLATFORM_VALUES_USD.get(d["platform"], 200_000_000),
            })

        # Shipping routes
        routes = []
        for r in m.get("shipping_routes", []):
            # Extract chokepoints: use structured field if present,
            # otherwise infer from risk_reason text
            cps = r.get("chokepoints", [])
            if not cps:
                reason = r.get("risk_reason", "")
                cps = [name for name in CHOKEPOINTS if name.lower() in reason.lower()]
            routes.append({
                "name": r.get("name", r.get("route_name", "")),
                "from": r.get("from", r.get("origin", "")),
                "to": r.get("to", r.get("destination", "")),
                "chokepoints": cps,
                "transit_days": r.get("transit_days", r.get("distance_nm", 0) / 300),
                "delay_days": 0,
                "status": "operational",
            })

        # Baseline supply/demand
        scenarios = suf.get("scenarios", [])
        baseline = scenarios[0] if scenarios else {"supply_t": 237000, "demand_t": 237000}

        # Track undisrupted node-level totals as the reference for supply reduction
        # (named mines/refineries may not sum to the global baseline figure)
        node_mining_total = sum(m["production_t"] for m in mines)
        node_refining_total = sum(r["capacity_t"] for r in refineries)
        node_supply_total = min(node_mining_total, node_refining_total) if mines else baseline.get("supply_t", 237000)

        return {
            "mines": mines,
            "refineries": refineries,
            "alloys": alloys,
            "platforms": platforms,
            "routes": routes,
            "baseline_supply_t": baseline.get("supply_t", 237000),
            "node_supply_total": node_supply_total,
            "effective_supply_t": node_supply_total,
            "demand_t": baseline.get("demand_t", 237000),
        }

    def _apply_layer(self, state: dict, layer: dict) -> None:
        """Apply a single disruption layer to the working state."""
        layer_type = layer.get("type", "")
        params = layer.get("params", {})

        if layer_type == "sanctions_expansion":
            self._apply_sanctions(state, params)
        elif layer_type == "material_shortage":
            self._apply_material_shortage(state, params)
        elif layer_type == "route_disruption":
            self._apply_route_disruption(state, params)
        elif layer_type == "supplier_failure":
            self._apply_supplier_failure(state, params)
        elif layer_type == "demand_surge":
            self._apply_demand_surge(state, params)

    def _apply_sanctions(self, state: dict, params: dict) -> None:
        """Zero out capacity for all nodes in the sanctioned country."""
        country = params.get("country", "")
        for mine in state["mines"]:
            if mine["country"].lower() == country.lower():
                mine["capacity_remaining_pct"] = 0
                mine["status"] = "disrupted"
        for ref in state["refineries"]:
            if ref["country"].lower() == country.lower():
                ref["capacity_remaining_pct"] = 0
                ref["status"] = "disrupted"
        self._recalc_supply(state)

    def _apply_material_shortage(self, state: dict, params: dict) -> None:
        """Reduce mining capacity by specified percentage."""
        reduction = params.get("reduction_pct", 40)
        for mine in state["mines"]:
            mine["capacity_remaining_pct"] = max(
                0, mine["capacity_remaining_pct"] * (1 - reduction / 100)
            )
            if mine["capacity_remaining_pct"] < 20:
                mine["status"] = "disrupted"
            elif mine["capacity_remaining_pct"] < 80:
                mine["status"] = "degraded"
        self._recalc_supply(state)

    def _apply_route_disruption(self, state: dict, params: dict) -> None:
        """Add delay to routes passing through the specified chokepoint."""
        chokepoint = params.get("chokepoint", "")
        duration_days = params.get("duration_days", 90)
        for route in state["routes"]:
            cps = route.get("chokepoints", [])
            if isinstance(cps, str):
                cps = [cps]
            if any(chokepoint.lower() in cp.lower() for cp in cps):
                route["delay_days"] += duration_days * 0.5  # 50% of blockage as average delay
                route["status"] = "disrupted"

    def _apply_supplier_failure(self, state: dict, params: dict) -> None:
        """Zero out a specific mine or refinery (partial name match)."""
        entity = params.get("entity", "").lower()
        if not entity:
            return
        for mine in state["mines"]:
            if entity in mine["name"].lower() or mine["name"].lower() in entity:
                mine["capacity_remaining_pct"] = 0
                mine["status"] = "disrupted"
        for ref in state["refineries"]:
            if entity in ref["name"].lower() or ref["name"].lower() in entity:
                ref["capacity_remaining_pct"] = 0
                ref["status"] = "disrupted"
        self._recalc_supply(state)

    def _apply_demand_surge(self, state: dict, params: dict) -> None:
        """Increase demand by specified percentage."""
        increase = params.get("increase_pct", 30)
        state["demand_t"] = state["demand_t"] * (1 + increase / 100)

    def _recalc_supply(self, state: dict) -> None:
        """Recalculate effective supply based on remaining mine/refinery capacity."""
        if not state["mines"] and not state["refineries"]:
            return  # No node data — keep baseline
        total_mining = sum(
            m["production_t"] * m["capacity_remaining_pct"] / 100
            for m in state["mines"]
        )
        total_refining_capacity = sum(
            r["capacity_t"] * r["capacity_remaining_pct"] / 100
            for r in state["refineries"]
        )
        state["effective_supply_t"] = min(total_mining, total_refining_capacity) if state["mines"] else state["node_supply_total"]

    def _propagate_cascade(self, state: dict) -> dict:
        """Build the 4-tier cascade data for the Sankey visualization."""
        baseline = state["baseline_supply_t"]

        # Tier 1: Mining
        mining_nodes = []
        for m in state["mines"]:
            effective = m["production_t"] * m["capacity_remaining_pct"] / 100
            loss_pct = round(100 - m["capacity_remaining_pct"], 1)
            mining_nodes.append({
                "name": m["name"],
                "country": m["country"],
                "status": m["status"],
                "capacity_loss_pct": loss_pct,
                "volume_t": round(effective, 1),
                "original_t": m["production_t"],
            })

        # Tier 2: Processing
        processing_nodes = []
        for r in state["refineries"]:
            effective = r["capacity_t"] * r["capacity_remaining_pct"] / 100
            loss_pct = round(100 - r["capacity_remaining_pct"], 1)
            processing_nodes.append({
                "name": r["name"],
                "country": r["country"],
                "status": r["status"],
                "capacity_loss_pct": loss_pct,
                "volume_t": round(effective, 1),
                "original_t": r["capacity_t"],
            })

        # Tier 3: Alloys — degraded proportionally to refining loss
        refining_ratio = (
            sum(n["volume_t"] for n in processing_nodes)
            / max(sum(n["original_t"] for n in processing_nodes), 1)
        ) if processing_nodes else 1.0
        alloy_nodes = []
        for a in state["alloys"]:
            eff_pct = a["capacity_remaining_pct"] * refining_ratio
            alloy_nodes.append({
                "name": a["name"],
                "status": "disrupted" if eff_pct < 50 else "degraded" if eff_pct < 80 else "operational",
                "capacity_loss_pct": round(100 - eff_pct, 1),
            })

        # Tier 4: Platforms — at risk if supply ratio < threshold
        supply_ratio = state["effective_supply_t"] / max(state["demand_t"], 1)
        platform_nodes = []
        for p in state["platforms"]:
            at_risk = supply_ratio < p["threshold_ratio"]
            platform_nodes.append({
                "name": p["name"],
                "engine": p["engine"],
                "status": "disrupted" if at_risk else "operational",
                "value_usd": p["value_usd"],
                "at_risk": at_risk,
            })

        # Flows — connections between tiers
        flows = []
        for m_node in mining_nodes:
            for p_node in processing_nodes:
                volume_share = (m_node["original_t"] / max(sum(n["original_t"] for n in mining_nodes), 1)) * 100
                flows.append({
                    "from": m_node["name"],
                    "to": p_node["name"],
                    "volume_pct": round(volume_share / max(len(processing_nodes), 1), 1),
                    "status": "blocked" if m_node["status"] == "disrupted" or p_node["status"] == "disrupted" else "active",
                })

        # Tier-level summary
        mining_loss = round(
            (1 - sum(n["volume_t"] for n in mining_nodes) / max(sum(n["original_t"] for n in mining_nodes), 1)) * 100, 1
        ) if mining_nodes else 0
        processing_loss = round(
            (1 - sum(n["volume_t"] for n in processing_nodes) / max(sum(n["original_t"] for n in processing_nodes), 1)) * 100, 1
        ) if processing_nodes else 0
        alloy_loss = round(
            sum(n["capacity_loss_pct"] for n in alloy_nodes) / max(len(alloy_nodes), 1), 1
        ) if alloy_nodes else 0
        platforms_at_risk = sum(1 for p in platform_nodes if p["at_risk"])

        return {
            "tiers": [
                {"name": "Mining", "nodes": mining_nodes, "loss_pct": mining_loss},
                {"name": "Processing", "nodes": processing_nodes, "loss_pct": processing_loss},
                {"name": "Alloys", "nodes": alloy_nodes, "loss_pct": alloy_loss},
                {"name": "Platforms", "nodes": platform_nodes, "loss_pct": 0},
            ],
            "flows": flows,
            "summary": {
                "mining_loss_pct": mining_loss,
                "processing_loss_pct": processing_loss,
                "alloy_loss_pct": alloy_loss,
                "platforms_at_risk": platforms_at_risk,
            },
        }

    def _compute_impact(
        self, state: dict, cascade: dict, layers: list[dict], time_horizon_months: int
    ) -> dict:
        """Compute the unified impact metrics."""
        if not layers:
            return {
                "value_at_risk_usd": 0,
                "platforms_affected": 0,
                "risk_score": 0,
                "risk_rating": "LOW",
                "likelihood": 0.0,
                "supply_reduction_pct": 0,
                "lead_time_increase_days": 0,
            }

        # Supply reduction — compare against undisrupted node total, not global baseline
        node_total = state.get("node_supply_total", state["baseline_supply_t"])
        supply_reduction_pct = round(
            max(0, (1 - state["effective_supply_t"] / max(node_total, 1)) * 100), 1
        )

        # Platforms affected
        platform_tier = cascade["tiers"][3]
        platforms_affected = sum(1 for p in platform_tier["nodes"] if p.get("at_risk"))

        # Value at risk — sum of affected platform values
        value_at_risk = sum(
            p["value_usd"] for p in platform_tier["nodes"] if p.get("at_risk")
        )

        # Lead time increase from route disruptions
        lead_time_days = sum(r["delay_days"] for r in state["routes"])

        # Likelihood — union probability: P(at least one event occurs)
        # = 1 - product(1 - p_i), ensuring more layers always increases or holds likelihood.
        # Single-layer base probabilities are scaled so that one high-confidence layer
        # (e.g. sanctions at 0.60) maps to a plausible compound value after ×2 scaling.
        not_happening = 1.0
        for layer in layers:
            base = _LAYER_LIKELIHOODS.get(layer.get("type", ""), 0.5)
            # Route disruption scales with duration
            if layer["type"] == "route_disruption":
                duration = layer.get("params", {}).get("duration_days", 90)
                base = base * min(duration / 365, 1.0)
            not_happening *= (1.0 - base)
        raw_likelihood = 1.0 - not_happening
        likelihood = round(raw_likelihood, 2)

        # Risk score: composite
        supply_factor = min(supply_reduction_pct / 100, 1.0)
        platform_factor = min(platforms_affected / max(len(platform_tier["nodes"]), 1), 1.0)
        risk_score = round(
            (likelihood * 40 + supply_factor * 30 + platform_factor * 30) * 100 / 100
        )
        risk_score = min(100, max(0, risk_score))

        # Risk rating
        if risk_score >= 70:
            risk_rating = "CRITICAL"
        elif risk_score >= 40:
            risk_rating = "HIGH"
        else:
            risk_rating = "LOW"

        return {
            "value_at_risk_usd": round(value_at_risk),
            "platforms_affected": platforms_affected,
            "risk_score": risk_score,
            "risk_rating": risk_rating,
            "likelihood": likelihood,
            "likelihood_method": "combined_independent",
            "supply_reduction_pct": round(supply_reduction_pct, 1),
            "lead_time_increase_days": round(lead_time_days),
        }

    def _generate_coas(self, state: dict, layers: list[dict], impact: dict) -> list[dict]:
        """Generate COAs from the mineral's existing playbook + layer-specific actions."""
        coas: list[dict] = []
        suf = self.mineral_data.get("sufficiency", {})
        existing_coas = suf.get("coa", [])

        # Include existing mineral COAs with risk reduction estimates
        risk_score = impact.get("risk_score", 0)
        for ec in existing_coas:
            coas.append({
                "id": ec["id"],
                "action": ec["action"],
                "priority": "critical" if risk_score >= 70 else "high" if risk_score >= 40 else "medium",
                "cost_estimate": ec.get("cost", "Unknown"),
                "risk_reduction_pts": round(risk_score * 0.15),  # ~15% per COA
                "timeline_months": 6,
                "affected_platforms": [
                    p["name"] for p in state["platforms"] if p.get("status") != "operational"
                ] or [p["name"] for p in state["platforms"][:3]],
            })

        # Add layer-specific COAs
        layer_types = {l["type"] for l in layers}
        if "sanctions_expansion" in layer_types:
            country = next(
                (l["params"].get("country", "") for l in layers if l["type"] == "sanctions_expansion"), ""
            )
            coas.append({
                "id": "COA-S1",
                "action": f"Identify alternative suppliers outside {country}",
                "priority": "critical",
                "cost_estimate": "$10-50M",
                "risk_reduction_pts": round(risk_score * 0.2),
                "timeline_months": 12,
                "affected_platforms": [p["name"] for p in state["platforms"] if p.get("status") != "operational"],
            })
        if "route_disruption" in layer_types:
            coas.append({
                "id": "COA-R1",
                "action": "Reroute shipments via alternative maritime corridors",
                "priority": "high",
                "cost_estimate": "$5-15M/yr",
                "risk_reduction_pts": round(risk_score * 0.12),
                "timeline_months": 1,
                "affected_platforms": [p["name"] for p in state["platforms"]],
            })
        if "supplier_failure" in layer_types:
            coas.append({
                "id": "COA-F1",
                "action": "Qualify replacement supplier and accelerate onboarding",
                "priority": "critical",
                "cost_estimate": "$20-80M",
                "risk_reduction_pts": round(risk_score * 0.18),
                "timeline_months": 18,
                "affected_platforms": [p["name"] for p in state["platforms"] if p.get("status") != "operational"],
            })

        return coas
