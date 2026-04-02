"""Supply chain risk analysis engine for Predictive Supplier Insights.

Provides 6-dimension risk scoring, scenario simulation, and
mitigation recommendations for defense supply chains.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.storage.models import (
    ArmsTransfer,
    Country,
    DefenseCompany,
    SupplyChainAlert,
    SupplyChainEdge,
    SupplyChainMaterial,
    SupplyChainNode,
    SupplyChainRoute,
    SupplyChainNodeType,
    TradeIndicator,
)
from src.ingestion.sanctions import SanctionsClient

logger = logging.getLogger(__name__)

# Chokepoint risk factors (0-100)
CHOKEPOINT_RISK: dict[str, int] = {
    "Taiwan Strait": 90,
    "Bashi Channel": 85,
    "Strait of Hormuz": 85,
    "Bab el-Mandeb": 80,
    "Suez Canal": 70,
    "Strait of Malacca": 60,
    "Strait of Gibraltar": 40,
    "Bosphorus": 50,
    "English Channel": 25,
    "Panama Canal": 35,
    "Northwest Passage": 45,
}

# NATO member countries (for allied/adversary classification)
NATO_MEMBERS = {
    "United States", "Canada", "United Kingdom", "France", "Germany",
    "Italy", "Spain", "Netherlands", "Belgium", "Norway", "Denmark",
    "Poland", "Turkiye", "Greece", "Portugal", "Czech Republic",
    "Hungary", "Romania", "Bulgaria", "Croatia", "Slovakia", "Slovenia",
    "Latvia", "Lithuania", "Estonia", "Albania", "Montenegro",
    "North Macedonia", "Finland", "Sweden", "Luxembourg", "Iceland",
}


@dataclass
class RiskProfile:
    """Multi-dimension risk assessment for a country or platform."""
    entity_name: str
    supplier_concentration: float = 0
    sanctions_proximity: float = 0
    chokepoint_exposure: float = 0
    geopolitical_instability: float = 0
    material_scarcity: float = 0
    alternative_availability: float = 0
    composite: float = 0

    WEIGHTS = {
        "supplier_concentration": 0.25,
        "sanctions_proximity": 0.20,
        "chokepoint_exposure": 0.15,
        "geopolitical_instability": 0.15,
        "material_scarcity": 0.15,
        "alternative_availability": 0.10,
    }

    def compute_composite(self) -> float:
        scores = {
            "supplier_concentration": self.supplier_concentration,
            "sanctions_proximity": self.sanctions_proximity,
            "chokepoint_exposure": self.chokepoint_exposure,
            "geopolitical_instability": self.geopolitical_instability,
            "material_scarcity": self.material_scarcity,
            "alternative_availability": self.alternative_availability,
        }
        self.composite = round(
            sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS), 1
        )
        return self.composite

    def to_dict(self) -> dict:
        return {
            "entity": self.entity_name,
            "scores": {
                "supplier_concentration": round(self.supplier_concentration, 1),
                "sanctions_proximity": round(self.sanctions_proximity, 1),
                "chokepoint_exposure": round(self.chokepoint_exposure, 1),
                "geopolitical_instability": round(self.geopolitical_instability, 1),
                "material_scarcity": round(self.material_scarcity, 1),
                "alternative_availability": round(self.alternative_availability, 1),
            },
            "composite": round(self.composite, 1),
            "weights": dict(self.WEIGHTS),
        }


@dataclass
class Mitigation:
    """A recommended mitigation action."""
    priority: int  # 1-5 (5 = critical)
    title: str
    description: str
    risk_type: str
    affected_entities: list[str] = field(default_factory=list)
    estimated_timeline_months: int = 0


class SupplyChainAnalyzer:
    """Supply chain risk scoring and scenario analysis engine."""

    def __init__(self, session: Session):
        self.session = session
        self._sanctions = SanctionsClient()

    # =========================================================== risk scoring

    def score_supplier_concentration(self, country_name: str) -> float:
        """Score 0-100 for supplier concentration risk.

        Computes HHI (Herfindahl-Hirschman Index) on arms imports
        grouped by seller country.
        """
        country = self._get_country(country_name)
        if not country:
            return 0

        query = (
            select(
                ArmsTransfer.seller_id,
                func.coalesce(func.sum(ArmsTransfer.tiv_delivered), 0).label("tiv"),
            )
            .where(ArmsTransfer.buyer_id == country.id)
            .group_by(ArmsTransfer.seller_id)
        )
        rows = self.session.execute(query).all()

        if not rows:
            return 0

        total_tiv = sum(r.tiv for r in rows)
        if total_tiv <= 0:
            return 0

        # HHI = sum of squared market shares (0-10000)
        hhi = sum((r.tiv / total_tiv * 100) ** 2 for r in rows)

        # Also check single-supplier dominance
        top_share = max(r.tiv / total_tiv for r in rows)

        if top_share > 0.6:
            return min(100, 90 + (top_share - 0.6) * 25)
        if hhi > 2500:
            return min(100, 75 + (hhi - 2500) / 100)

        # Normalize HHI to 0-100 scale
        return min(100, hhi / 100)

    def score_sanctions_proximity(self, country_name: str) -> float:
        """Score 0-100 for how close a country's suppliers are to sanctions."""
        country = self._get_country(country_name)
        if not country:
            return 0

        embargoed = {e.iso3 for e in self._sanctions.get_embargoed_countries()}

        # Get this country's suppliers
        suppliers = self.session.execute(
            select(
                Country.name,
                Country.iso_alpha3,
                func.sum(ArmsTransfer.tiv_delivered).label("tiv"),
            )
            .join(ArmsTransfer, ArmsTransfer.seller_id == Country.id)
            .where(ArmsTransfer.buyer_id == country.id)
            .group_by(Country.id)
        ).all()

        if not suppliers:
            return 0

        total_tiv = sum(s.tiv or 0 for s in suppliers)
        if total_tiv <= 0:
            return 0

        score = 0.0
        for supplier in suppliers:
            share = (supplier.tiv or 0) / total_tiv
            iso3 = supplier.iso_alpha3 or ""

            # Direct sanctions
            if iso3 in embargoed:
                score += share * 100

            # One-hop: does this supplier trade with embargoed countries?
            supplier_country = self._get_country(supplier.name)
            if supplier_country:
                embargoed_partners = self.session.execute(
                    select(func.count()).select_from(ArmsTransfer).join(
                        Country, ArmsTransfer.buyer_id == Country.id
                    ).where(
                        ArmsTransfer.seller_id == supplier_country.id,
                        Country.iso_alpha3.in_(embargoed),
                    )
                ).scalar() or 0

                if embargoed_partners > 0:
                    score += share * min(40, embargoed_partners * 10)

        return min(100, round(score, 1))

    def score_chokepoint_exposure(self, country_name: str) -> float:
        """Score 0-100 for chokepoint risk on supply routes."""
        country = self._get_country(country_name)
        if not country:
            return 0

        routes = self.session.execute(
            select(SupplyChainRoute).where(
                SupplyChainRoute.destination_country_id == country.id
            )
        ).scalars().all()

        if not routes:
            return 0

        total_risk = 0.0
        for route in routes:
            if not route.chokepoints:
                continue
            try:
                chokepoints = json.loads(route.chokepoints)
            except (json.JSONDecodeError, TypeError):
                continue

            route_risk = 0
            for cp in chokepoints:
                route_risk += CHOKEPOINT_RISK.get(cp, 30)

            total_risk += min(100, route_risk)

        return min(100, round(total_risk / len(routes), 1))

    def score_geopolitical_instability(self, country_name: str) -> float:
        """Score 0-100 for instability of supplier countries."""
        country = self._get_country(country_name)
        if not country:
            return 0

        suppliers = self.session.execute(
            select(
                Country.name,
                func.sum(ArmsTransfer.tiv_delivered).label("tiv"),
            )
            .join(ArmsTransfer, ArmsTransfer.seller_id == Country.id)
            .where(ArmsTransfer.buyer_id == country.id)
            .group_by(Country.id)
        ).all()

        if not suppliers:
            return 0

        total_tiv = sum(s.tiv or 0 for s in suppliers)
        if total_tiv <= 0:
            return 0

        score = 0.0
        for supplier in suppliers:
            share = (supplier.tiv or 0) / total_tiv
            name = supplier.name

            # Non-NATO countries with high military spending = instability signal
            if name not in NATO_MEMBERS:
                # Check mil spending % GDP
                indicator = self.session.execute(
                    select(TradeIndicator).join(Country).where(
                        Country.name == name,
                    ).order_by(TradeIndicator.year.desc())
                ).scalars().first()

                mil_pct = 0
                if indicator and indicator.military_expenditure_pct_gdp:
                    mil_pct = indicator.military_expenditure_pct_gdp

                # High mil spending in non-NATO = risk
                if mil_pct > 4:
                    score += share * 80
                elif mil_pct > 2:
                    score += share * 40
                else:
                    score += share * 20

        return min(100, round(score, 1))

    def score_material_scarcity(self, material_name: str) -> float:
        """Score 0-100 for supply concentration of a critical material."""
        material = self.session.execute(
            select(SupplyChainMaterial).where(
                SupplyChainMaterial.name == material_name
            )
        ).scalar_one_or_none()

        if not material:
            return 0

        # Use pre-computed concentration index
        ci = material.concentration_index or 0

        # Check if top producers are embargoed
        embargoed = {e.country for e in self._sanctions.get_embargoed_countries()}
        adversary_share = 0.0
        if material.top_producers:
            try:
                producers = json.loads(material.top_producers)
                for p in producers:
                    if p.get("country") in embargoed:
                        adversary_share += p.get("pct", 0) / 100
            except (json.JSONDecodeError, TypeError):
                pass

        if adversary_share > 0.5:
            return min(100, 90 + adversary_share * 10)

        # HHI > 0.25 is highly concentrated
        if ci > 0.5:
            return min(100, 70 + (ci - 0.5) * 60)
        if ci > 0.25:
            return min(100, 40 + (ci - 0.25) * 120)

        return min(100, round(ci * 160, 1))

    def score_alternative_availability(self, node_name: str) -> float:
        """Score 0-100 for lack of alternative suppliers (higher = worse)."""
        # Find edges where this node is the parent (i.e. things depend on it)
        node = self.session.execute(
            select(SupplyChainNode).where(SupplyChainNode.name == node_name)
        ).scalar_one_or_none()

        if not node:
            return 50  # Unknown = moderate risk

        edges = self.session.execute(
            select(SupplyChainEdge).where(
                SupplyChainEdge.parent_node_id == node.id
            )
        ).scalars().all()

        if not edges:
            return 20  # Nothing depends on it

        # Check the worst case among all dependencies
        worst = 0
        for edge in edges:
            if edge.is_sole_source:
                worst = max(worst, 95)
            elif edge.alternative_count == 0:
                worst = max(worst, 80)
            elif edge.alternative_count <= 2:
                worst = max(worst, 50)
            elif edge.alternative_count <= 4:
                worst = max(worst, 30)
            else:
                worst = max(worst, 15)

        return worst

    # ====================================================== composite scoring

    def compute_country_risk(self, country_name: str) -> RiskProfile:
        """Compute full 6-dimension risk profile for a country."""
        profile = RiskProfile(entity_name=country_name)
        profile.supplier_concentration = self.score_supplier_concentration(country_name)
        profile.sanctions_proximity = self.score_sanctions_proximity(country_name)
        profile.chokepoint_exposure = self.score_chokepoint_exposure(country_name)
        profile.geopolitical_instability = self.score_geopolitical_instability(country_name)

        # Average material scarcity across all materials
        materials = self.session.execute(
            select(SupplyChainMaterial)
        ).scalars().all()
        if materials:
            scores = [self.score_material_scarcity(m.name) for m in materials]
            profile.material_scarcity = round(sum(scores) / len(scores), 1)

        # Average alternative availability across supply chain nodes
        nodes = self.session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.node_type.in_([
                    SupplyChainNodeType.COMPONENT,
                    SupplyChainNodeType.MATERIAL,
                ])
            )
        ).scalars().all()
        if nodes:
            scores = [self.score_alternative_availability(n.name) for n in nodes]
            profile.alternative_availability = round(sum(scores) / len(scores), 1)

        profile.compute_composite()
        return profile

    # ====================================================== scenario modeling

    def simulate_scenario(self, scenario: dict) -> dict:
        """Run a what-if scenario simulation.

        Args:
            scenario: Dict with "type" and "parameters" keys.
                Types: "sanctions_expansion", "material_shortage",
                       "route_disruption", "demand_surge", "supplier_substitution"

        Returns:
            Impact assessment with affected items and recommendations.
        """
        scenario_type = scenario.get("type", "")
        params = scenario.get("parameters", {})

        if scenario_type == "sanctions_expansion":
            return self._scenario_sanctions(params)
        if scenario_type == "material_shortage":
            return self._scenario_material_shortage(params)
        if scenario_type == "route_disruption":
            return self._scenario_route_disruption(params)
        if scenario_type == "demand_surge":
            return self._scenario_demand_surge(params)
        if scenario_type == "supplier_substitution":
            return self._scenario_supplier_sub(params)

        return {"error": f"Unknown scenario type: {scenario_type}"}

    def _scenario_sanctions(self, params: dict) -> dict:
        """Simulate sanctions expansion to a new country."""
        country_name = params.get("country", "")
        country = self._get_country(country_name)
        if not country:
            return {"error": f"Unknown country: {country_name}"}

        # Find all transfers from this country
        exports = self.session.execute(
            select(
                Country.name.label("buyer"),
                func.sum(ArmsTransfer.tiv_delivered).label("tiv"),
                func.count().label("deals"),
            )
            .join(Country, ArmsTransfer.buyer_id == Country.id)
            .where(ArmsTransfer.seller_id == country.id)
            .group_by(Country.id)
            .order_by(func.sum(ArmsTransfer.tiv_delivered).desc())
        ).all()

        affected_countries = [
            {"country": r.buyer, "tiv_at_risk": round(r.tiv or 0, 1), "deals": r.deals}
            for r in exports
        ]

        # Find supply chain nodes in this country
        affected_nodes = self.session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.country_id == country.id
            )
        ).scalars().all()

        return {
            "scenario": {"type": "sanctions_expansion", "country": country_name},
            "impact_summary": {
                "affected_buyer_countries": len(affected_countries),
                "total_tiv_at_risk": round(sum(r.tiv or 0 for r in exports), 1),
                "affected_supply_chain_nodes": len(affected_nodes),
            },
            "affected_countries": affected_countries[:20],
            "affected_nodes": [
                {"name": n.name, "type": n.node_type.value if n.node_type else "unknown"}
                for n in affected_nodes
            ],
            "recommendations": [
                {"action": f"Identify alternative suppliers for components from {country_name}",
                 "priority": "critical"},
                {"action": f"Assess stockpile levels for materials sourced from {country_name}",
                 "priority": "high"},
                {"action": f"Review contracts with {country_name}-based entities",
                 "priority": "high"},
            ],
        }

    def _scenario_material_shortage(self, params: dict) -> dict:
        """Simulate a critical material supply reduction."""
        material_name = params.get("material", "")
        reduction_pct = params.get("reduction_pct", 40)

        material = self.session.execute(
            select(SupplyChainMaterial).where(
                SupplyChainMaterial.name == material_name
            )
        ).scalar_one_or_none()

        if not material:
            return {"error": f"Unknown material: {material_name}"}

        current_scarcity = self.score_material_scarcity(material_name)
        projected_scarcity = min(100, current_scarcity + reduction_pct * 0.8)

        # Find all platforms that depend on this material
        mat_node = self.session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.material_id == material.id,
                SupplyChainNode.node_type == SupplyChainNodeType.MATERIAL,
            )
        ).scalar_one_or_none()

        affected_platforms: list[dict] = []
        if mat_node:
            # Traverse upward: material -> component -> subsystem -> platform
            visited: set[int] = set()
            queue = [mat_node.id]
            while queue:
                nid = queue.pop(0)
                if nid in visited:
                    continue
                visited.add(nid)

                node = self.session.execute(
                    select(SupplyChainNode).where(SupplyChainNode.id == nid)
                ).scalar_one_or_none()

                if node and node.node_type == SupplyChainNodeType.PLATFORM:
                    affected_platforms.append({
                        "platform": node.name,
                        "company": node.company_name or "unknown",
                    })

                # Find dependents (edges where parent = this node)
                edges = self.session.execute(
                    select(SupplyChainEdge).where(
                        SupplyChainEdge.parent_node_id == nid
                    )
                ).scalars().all()

                for edge in edges:
                    queue.append(edge.child_node_id)

        return {
            "scenario": {
                "type": "material_shortage",
                "material": material_name,
                "reduction_pct": reduction_pct,
            },
            "impact_summary": {
                "scarcity_before": round(current_scarcity, 1),
                "scarcity_after": round(projected_scarcity, 1),
                "affected_platforms": len(affected_platforms),
            },
            "affected_platforms": affected_platforms,
            "recommendations": [
                {"action": f"Establish strategic stockpile of {material_name}", "priority": "critical"},
                {"action": f"Qualify alternative materials for {material_name}-dependent components", "priority": "high"},
                {"action": f"Engage with allied producers to secure supply agreements", "priority": "high"},
            ],
        }

    def _scenario_route_disruption(self, params: dict) -> dict:
        """Simulate a chokepoint blockage."""
        chokepoint = params.get("chokepoint", "")
        duration_days = params.get("duration_days", 90)

        # Find all routes through this chokepoint
        all_routes = self.session.execute(
            select(SupplyChainRoute)
        ).scalars().all()

        affected_routes = []
        for route in all_routes:
            if not route.chokepoints:
                continue
            try:
                cps = json.loads(route.chokepoints)
            except (json.JSONDecodeError, TypeError):
                continue

            if chokepoint in cps:
                origin = self.session.execute(
                    select(Country).where(Country.id == route.origin_country_id)
                ).scalar_one_or_none()
                dest = self.session.execute(
                    select(Country).where(Country.id == route.destination_country_id)
                ).scalar_one_or_none()
                affected_routes.append({
                    "route": route.route_name,
                    "origin": origin.name if origin else "unknown",
                    "destination": dest.name if dest else "unknown",
                    "distance_nm": route.distance_nm,
                })

        risk_factor = CHOKEPOINT_RISK.get(chokepoint, 50)
        severity = min(1.0, risk_factor / 100 * (min(duration_days, 365) / 180))

        return {
            "scenario": {
                "type": "route_disruption",
                "chokepoint": chokepoint,
                "duration_days": duration_days,
            },
            "impact_summary": {
                "affected_routes": len(affected_routes),
                "chokepoint_risk_factor": risk_factor,
                "severity": round(severity, 2),
            },
            "affected_routes": affected_routes,
            "recommendations": [
                {"action": f"Reroute shipments avoiding {chokepoint}", "priority": "critical"},
                {"action": "Activate strategic reserves for affected materials", "priority": "high"},
                {"action": "Coordinate with allied navies for maritime security", "priority": "medium"},
            ],
        }

    def _scenario_demand_surge(self, params: dict) -> dict:
        """Simulate increased procurement demand."""
        region = params.get("region", "NATO")
        increase_pct = params.get("increase_pct", 30)

        # Find top suppliers by TIV and assess capacity
        top_suppliers = self.session.execute(
            select(
                Country.name,
                func.sum(ArmsTransfer.tiv_delivered).label("total_tiv"),
                func.count().label("deal_count"),
            )
            .join(Country, ArmsTransfer.seller_id == Country.id)
            .group_by(Country.id)
            .order_by(func.sum(ArmsTransfer.tiv_delivered).desc())
            .limit(15)
        ).all()

        bottlenecks = []
        for s in top_suppliers:
            projected = (s.total_tiv or 0) * (1 + increase_pct / 100)
            if projected > (s.total_tiv or 0) * 1.2:
                bottlenecks.append({
                    "supplier": s.name,
                    "current_tiv": round(s.total_tiv or 0, 1),
                    "projected_tiv": round(projected, 1),
                    "deals": s.deal_count,
                })

        return {
            "scenario": {
                "type": "demand_surge",
                "region": region,
                "increase_pct": increase_pct,
            },
            "impact_summary": {
                "potential_bottleneck_suppliers": len(bottlenecks),
            },
            "bottlenecks": bottlenecks,
            "recommendations": [
                {"action": "Pre-position orders with key suppliers to lock capacity", "priority": "high"},
                {"action": "Diversify across multiple Tier 1 suppliers", "priority": "high"},
                {"action": "Accelerate domestic production qualification", "priority": "medium"},
            ],
        }

    def _scenario_supplier_sub(self, params: dict) -> dict:
        """Simulate replacing one supplier with another."""
        original = params.get("original_supplier", "")
        replacement = params.get("replacement_supplier", "")

        orig_country = self._get_country(original)
        repl_country = self._get_country(replacement)

        if not orig_country or not repl_country:
            return {"error": "Unknown supplier country(s)"}

        # What does the original supply?
        orig_exports = self.session.execute(
            select(
                Country.name.label("buyer"),
                func.sum(ArmsTransfer.tiv_delivered).label("tiv"),
            )
            .join(Country, ArmsTransfer.buyer_id == Country.id)
            .where(ArmsTransfer.seller_id == orig_country.id)
            .group_by(Country.id)
            .order_by(func.sum(ArmsTransfer.tiv_delivered).desc())
        ).all()

        # What does the replacement already supply?
        repl_exports = self.session.execute(
            select(func.sum(ArmsTransfer.tiv_delivered))
            .where(ArmsTransfer.seller_id == repl_country.id)
        ).scalar() or 0

        return {
            "scenario": {
                "type": "supplier_substitution",
                "original": original,
                "replacement": replacement,
            },
            "impact_summary": {
                "original_export_tiv": round(sum(r.tiv or 0 for r in orig_exports), 1),
                "replacement_current_tiv": round(repl_exports, 1),
                "affected_buyers": len(orig_exports),
            },
            "affected_buyers": [
                {"country": r.buyer, "tiv_to_replace": round(r.tiv or 0, 1)}
                for r in orig_exports[:15]
            ],
            "recommendations": [
                {"action": f"Assess {replacement}'s production capacity for required systems", "priority": "critical"},
                {"action": "Negotiate framework agreements with replacement supplier", "priority": "high"},
                {"action": "Plan transition timeline and interoperability testing", "priority": "high"},
            ],
        }

    # ========================================================== mitigations

    def generate_mitigations(self, profile: RiskProfile) -> list[Mitigation]:
        """Generate mitigation recommendations from a risk profile."""
        mitigations: list[Mitigation] = []

        if profile.supplier_concentration > 60:
            mitigations.append(Mitigation(
                priority=5,
                title=f"Diversify arms suppliers for {profile.entity_name}",
                description=f"Supplier concentration score is {profile.supplier_concentration:.0f}/100. "
                            "Qualify additional suppliers to reduce single-source dependency.",
                risk_type="supplier_concentration",
                estimated_timeline_months=18,
            ))

        if profile.sanctions_proximity > 50:
            mitigations.append(Mitigation(
                priority=4,
                title=f"Review sanctions exposure for {profile.entity_name} supply chain",
                description=f"Sanctions proximity score is {profile.sanctions_proximity:.0f}/100. "
                            "Assess compliance risk and identify non-sanctioned alternatives.",
                risk_type="sanctions_proximity",
                estimated_timeline_months=6,
            ))

        if profile.chokepoint_exposure > 60:
            mitigations.append(Mitigation(
                priority=4,
                title=f"Develop alternative logistics routes for {profile.entity_name}",
                description=f"Chokepoint exposure score is {profile.chokepoint_exposure:.0f}/100. "
                            "Pre-plan alternative shipping routes avoiding contested chokepoints.",
                risk_type="chokepoint_exposure",
                estimated_timeline_months=12,
            ))

        if profile.material_scarcity > 60:
            mitigations.append(Mitigation(
                priority=5,
                title="Establish strategic stockpiles of critical materials",
                description=f"Material scarcity score is {profile.material_scarcity:.0f}/100. "
                            "Build 6-12 month reserves of high-risk materials.",
                risk_type="material_scarcity",
                estimated_timeline_months=12,
            ))

        if profile.alternative_availability > 70:
            mitigations.append(Mitigation(
                priority=5,
                title="Develop second sources for sole-source components",
                description=f"Alternative availability score is {profile.alternative_availability:.0f}/100. "
                            "Fund qualification of domestic or allied alternative producers.",
                risk_type="alternative_availability",
                estimated_timeline_months=24,
            ))

        if profile.geopolitical_instability > 50:
            mitigations.append(Mitigation(
                priority=3,
                title=f"Monitor supplier country stability for {profile.entity_name}",
                description=f"Geopolitical instability score is {profile.geopolitical_instability:.0f}/100. "
                            "Establish early warning indicators and contingency plans.",
                risk_type="geopolitical_instability",
                estimated_timeline_months=3,
            ))

        # Sort by priority descending
        mitigations.sort(key=lambda m: m.priority, reverse=True)
        return mitigations

    # ============================================================== overview

    def get_overview(self) -> dict:
        """Get global supply chain risk overview for the dashboard."""
        # Global material scarcity averages
        materials = self.session.execute(
            select(SupplyChainMaterial)
        ).scalars().all()

        material_risks = []
        for m in materials:
            score = self.score_material_scarcity(m.name)
            material_risks.append({
                "name": m.name,
                "category": m.category.value if m.category else "other",
                "scarcity_score": round(score, 1),
                "concentration_index": round(m.concentration_index or 0, 3),
                "strategic_importance": m.strategic_importance or 1,
            })

        material_risks.sort(key=lambda x: x["scarcity_score"], reverse=True)

        # Active alerts
        alerts = self.session.execute(
            select(SupplyChainAlert)
            .where(SupplyChainAlert.is_active == True)  # noqa: E712
            .order_by(SupplyChainAlert.severity.desc())
        ).scalars().all()

        alert_list = [
            {
                "id": a.id,
                "type": a.alert_type.value if a.alert_type else "unknown",
                "severity": a.severity,
                "title": a.title,
                "description": a.description or "",
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]

        # Canada-specific risk
        canada_risk = self.compute_country_risk("Canada")

        # Graph stats
        node_count = self.session.execute(
            select(func.count()).select_from(SupplyChainNode)
        ).scalar() or 0
        edge_count = self.session.execute(
            select(func.count()).select_from(SupplyChainEdge)
        ).scalar() or 0
        route_count = self.session.execute(
            select(func.count()).select_from(SupplyChainRoute)
        ).scalar() or 0

        return {
            "global_risk_score": canada_risk.composite,
            "risk_dimensions": canada_risk.to_dict()["scores"],
            "top_material_risks": material_risks[:10],
            "active_alerts": alert_list,
            "graph_stats": {
                "nodes": node_count,
                "edges": edge_count,
                "routes": route_count,
                "materials": len(materials),
            },
            "canada_risk": canada_risk.to_dict(),
        }

    # ============================================================== helpers

    def _get_country(self, name: str) -> Country | None:
        return self.session.execute(
            select(Country).where(Country.name == name)
        ).scalar_one_or_none()
