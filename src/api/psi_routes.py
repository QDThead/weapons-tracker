"""Predictive Supplier Insights (PSI) API endpoints.

Provides supply chain risk analysis, knowledge graph data,
scenario simulation, and disruption alerting.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from src.storage.database import SessionLocal
from src.storage.models import (
    SupplyChainAlert,
    SupplyChainMaterial,
    SupplyChainNode,
    SupplyChainEdge,
    SupplyChainRoute,
    SupplyChainNodeType,
    Country,
    MitigationAction,
)
from src.storage.persistence import PersistenceService
from src.analysis.supply_chain import SupplyChainAnalyzer
from src.analysis.supply_chain_graph import SupplyChainGraph
from src.analysis.scenario_engine import ScenarioEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/psi", tags=["Supply Chain"])

# Cache following existing dashboard_routes.py pattern
_psi_cache: dict[str, tuple[float, dict | list]] = {}
_PSI_TTL = 300         # 5 minutes for risk scores
_PSI_GRAPH_TTL = 3600  # 1 hour for knowledge graph
_PSI_TAXONOMY_TTL = 3600  # 1 hour for taxonomy scores


def _check_cache(key: str, ttl: int) -> dict | list | None:
    cached = _psi_cache.get(key)
    if cached and time.time() - cached[0] < ttl:
        return cached[1]
    return None


def _set_cache(key: str, data: dict | list) -> None:
    _psi_cache[key] = (time.time(), data)


# ------------------------------------------------------------------
# Pydantic models for request bodies
# ------------------------------------------------------------------

class ScenarioRequest(BaseModel):
    type: str
    parameters: dict


class ScenarioLayerRequest(BaseModel):
    type: str
    params: dict

class ScenarioRequestV2(BaseModel):
    mineral: str
    layers: list[ScenarioLayerRequest]
    demand_surge_pct: float = 0
    time_horizon_months: int = 12


class ScenarioExportRequest(BaseModel):
    scenarios: list[dict]


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("/overview")
async def get_supply_chain_overview():
    """Global supply chain risk dashboard summary."""
    cached = _check_cache("overview", _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        analyzer = SupplyChainAnalyzer(session)
        result = analyzer.get_overview()
        _set_cache("overview", result)
        return result
    except Exception as e:
        logger.error("PSI overview failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to compute supply chain overview")
    finally:
        session.close()


@router.get("/risk/{country}")
async def get_country_risk(country: str):
    """6-dimension risk assessment for a country."""
    cache_key = f"risk:{country}"
    cached = _check_cache(cache_key, _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        analyzer = SupplyChainAnalyzer(session)
        profile = analyzer.compute_country_risk(country)
        mitigations = analyzer.generate_mitigations(profile)

        result = {
            **profile.to_dict(),
            "mitigations": [
                {
                    "priority": m.priority,
                    "title": m.title,
                    "description": m.description,
                    "risk_type": m.risk_type,
                    "timeline_months": m.estimated_timeline_months,
                }
                for m in mitigations
            ],
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("PSI risk for %s failed: %s", country, e)
        raise HTTPException(status_code=500, detail=f"Failed to compute risk for {country}")
    finally:
        session.close()


@router.get("/material/{name}")
async def get_material_risk(name: str):
    """Risk assessment for a specific critical material."""
    cache_key = f"material:{name}"
    cached = _check_cache(cache_key, _PSI_GRAPH_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        analyzer = SupplyChainAnalyzer(session)
        scarcity = analyzer.score_material_scarcity(name)

        material = session.execute(
            select(SupplyChainMaterial).where(SupplyChainMaterial.name == name)
        ).scalar_one_or_none()

        if not material:
            raise HTTPException(status_code=404, detail=f"Material not found: {name}")

        producers = []
        if material.top_producers:
            try:
                producers = json.loads(material.top_producers)
            except (json.JSONDecodeError, TypeError):
                pass

        # Find dependent platforms
        mat_node = session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.material_id == material.id,
                SupplyChainNode.node_type == SupplyChainNodeType.MATERIAL,
            )
        ).scalar_one_or_none()

        dependent_platforms: list[str] = []
        if mat_node:
            # Walk edges upward to find platforms
            visited: set[int] = set()
            queue = [mat_node.id]
            while queue:
                nid = queue.pop(0)
                if nid in visited:
                    continue
                visited.add(nid)
                node = session.execute(
                    select(SupplyChainNode).where(SupplyChainNode.id == nid)
                ).scalar_one_or_none()
                if node and node.node_type == SupplyChainNodeType.PLATFORM:
                    dependent_platforms.append(node.name)
                edges = session.execute(
                    select(SupplyChainEdge).where(
                        SupplyChainEdge.parent_node_id == nid
                    )
                ).scalars().all()
                for edge in edges:
                    queue.append(edge.child_node_id)

        result = {
            "name": material.name,
            "category": material.category.value if material.category else "other",
            "scarcity_score": round(scarcity, 1),
            "concentration_index": round(material.concentration_index or 0, 3),
            "strategic_importance": material.strategic_importance or 1,
            "defense_applications": material.defense_applications or "",
            "top_producers": producers,
            "dependent_platforms": dependent_platforms,
        }
        _set_cache(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PSI material %s failed: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Failed to get material info: {name}")
    finally:
        session.close()


@router.get("/platform/{weapon}")
async def get_platform_vulnerability(weapon: str):
    """BOM tree and risk analysis for a weapon platform."""
    cache_key = f"platform:{weapon}"
    cached = _check_cache(cache_key, _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        graph = SupplyChainGraph(session)
        graph.build()
        bom = graph.explode_bom(weapon)

        if not bom:
            raise HTTPException(status_code=404, detail=f"Platform not found: {weapon}")

        def bom_to_dict(entry) -> dict:
            return {
                "name": entry.name,
                "type": entry.node_type,
                "company": entry.company,
                "country": entry.country,
                "is_sole_source": entry.is_sole_source,
                "confidence": entry.confidence,
                "children": [bom_to_dict(c) for c in entry.children],
            }

        result = {
            "platform": weapon,
            "bom": bom_to_dict(bom),
            "total_components": _count_bom_nodes(bom),
            "sole_source_count": _count_sole_source(bom),
        }
        _set_cache(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PSI platform %s failed: %s", weapon, e)
        raise HTTPException(status_code=500, detail=f"Failed to analyze platform: {weapon}")
    finally:
        session.close()


@router.post("/scenario")
async def run_scenario(request: ScenarioRequest):
    """Run a what-if scenario simulation."""
    session = SessionLocal()
    try:
        analyzer = SupplyChainAnalyzer(session)
        result = analyzer.simulate_scenario({
            "type": request.type,
            "parameters": request.parameters,
        })
        return result
    except Exception as e:
        logger.error("PSI scenario failed: %s", e)
        raise HTTPException(status_code=500, detail="Scenario simulation failed")
    finally:
        session.close()


@router.post("/scenario/v2")
async def run_scenario_v2(request: ScenarioRequestV2):
    """Run a multi-variable what-if scenario with cascade propagation."""
    try:
        engine = ScenarioEngine(request.mineral)
        result = engine.run(
            layers=[{"type": l.type, "params": l.params} for l in request.layers],
            demand_surge_pct=request.demand_surge_pct,
            time_horizon_months=request.time_horizon_months,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Scenario v2 failed: %s", e)
        raise HTTPException(status_code=500, detail="Scenario simulation failed")


@router.post("/scenario/export/pdf")
async def export_scenario_pdf(request: ScenarioExportRequest):
    """Generate a PDF briefing from scenario results."""
    from fpdf import FPDF
    from fastapi.responses import Response

    def _safe(text: str) -> str:
        """Replace characters outside Latin-1 range so Helvetica can encode them."""
        return (
            text
            .replace("\u2013", "-")   # en-dash
            .replace("\u2014", "--")  # em-dash
            .replace("\u2019", "'")   # right single quotation
            .replace("\u2018", "'")   # left single quotation
            .replace("\u201c", '"')   # left double quotation
            .replace("\u201d", '"')   # right double quotation
            .encode("latin-1", errors="replace")
            .decode("latin-1")
        )

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for i, scenario in enumerate(request.scenarios):
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        mineral = scenario.get("mineral", "Unknown")
        pdf.cell(0, 10, _safe(f"Scenario Briefing: {mineral}"), new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 10)
        layers = scenario.get("layers", [])
        if layers:
            pdf.cell(0, 8, f"Disruption Layers: {len(layers)}", new_x="LMARGIN", new_y="NEXT")
            for layer in layers:
                layer_type = layer.get("type", "unknown").replace("_", " ").title()
                params = layer.get("params", {})
                param_str = ", ".join(f"{k}: {v}" for k, v in params.items())
                pdf.cell(0, 6, _safe(f"  - {layer_type}: {param_str}"), new_x="LMARGIN", new_y="NEXT")

        impact = scenario.get("impact", {})
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Impact Summary", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Value at Risk: ${impact.get('value_at_risk_usd', 0):,.0f}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Platforms Affected: {impact.get('platforms_affected', 0)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, _safe(f"Risk Score: {impact.get('risk_score', 0)} ({impact.get('risk_rating', 'N/A')})"), new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Likelihood: {impact.get('likelihood', 0)}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Supply Reduction: {impact.get('supply_reduction_pct', 0)}%", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 6, f"Lead Time Increase: {impact.get('lead_time_increase_days', 0)} days", new_x="LMARGIN", new_y="NEXT")

        cascade = scenario.get("cascade", {})
        tiers = cascade.get("tiers", [])
        if tiers:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Disruption Cascade", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for tier in tiers:
                tier_name = tier.get("name", "")
                loss = tier.get("loss_pct", 0)
                node_count = len(tier.get("nodes", []))
                disrupted = sum(1 for n in tier.get("nodes", []) if n.get("status") == "disrupted")
                pdf.cell(0, 6, _safe(f"  {tier_name}: {disrupted}/{node_count} disrupted, -{loss}% capacity"), new_x="LMARGIN", new_y="NEXT")

        coas = scenario.get("coa", [])
        if coas:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Recommended Courses of Action", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            for coa in coas:
                priority = coa.get("priority", "medium").upper()
                action = coa.get("action", "")
                cost = coa.get("cost_estimate", "TBD")
                pdf.cell(0, 6, _safe(f"  [{priority}] {action} (Cost: {cost})"), new_x="LMARGIN", new_y="NEXT")

        suf = scenario.get("sufficiency", {})
        if suf:
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Supply Sufficiency", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"  Supply: {suf.get('supply_t', 0):,.0f} t/yr | Demand: {suf.get('demand_t', 0):,.0f} t/yr", new_x="LMARGIN", new_y="NEXT")
            pdf.cell(0, 6, _safe(f"  Ratio: {suf.get('ratio', 0):.3f}x | Verdict: {suf.get('verdict', 'N/A')}"), new_x="LMARGIN", new_y="NEXT")

    if len(request.scenarios) > 1:
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Scenario Comparison", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        pdf.ln(4)

        header = "Metric"
        for s in request.scenarios:
            header += f" | {s.get('mineral', '?')}"
        pdf.cell(0, 6, header, new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 1, "-" * 80, new_x="LMARGIN", new_y="NEXT")

        metrics = ["value_at_risk_usd", "platforms_affected", "risk_score", "likelihood", "supply_reduction_pct", "lead_time_increase_days"]
        labels = ["Value at Risk ($)", "Platforms Affected", "Risk Score", "Likelihood", "Supply Reduction (%)", "Lead Time (+days)"]
        for metric, label in zip(metrics, labels):
            row = label
            for s in request.scenarios:
                val = s.get("impact", {}).get(metric, 0)
                if metric == "value_at_risk_usd":
                    row += f" | ${val:,.0f}"
                else:
                    row += f" | {val}"
            pdf.cell(0, 6, row, new_x="LMARGIN", new_y="NEXT")

    pdf_bytes = pdf.output()
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scenario-briefing.pdf"},
    )


@router.get("/graph")
async def get_knowledge_graph(
    node_type: str | None = Query(None, description="Filter by node type"),
    risk_min: float = Query(0, description="Minimum risk score"),
    country: str | None = Query(None, description="Filter by country"),
):
    """Knowledge graph data for D3.js visualization."""
    cache_key = f"graph:{node_type}:{risk_min}:{country}"
    cached = _check_cache(cache_key, _PSI_GRAPH_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        graph = SupplyChainGraph(session)
        graph.build()
        result = graph.to_d3_json(
            node_type_filter=node_type,
            risk_min=risk_min,
            country_filter=country,
        )
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("PSI graph failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to build knowledge graph")
    finally:
        session.close()


@router.get("/suppliers/{name}")
async def get_supplier_profile(name: str):
    """Supplier company profile with risk factors and alternatives."""
    cache_key = f"supplier:{name}"
    cached = _check_cache(cache_key, _PSI_GRAPH_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        from src.storage.models import DefenseCompany

        # Escape LIKE wildcards in user input
        escaped = name.replace("%", r"\%").replace("_", r"\_")

        # Get company data
        companies = session.execute(
            select(DefenseCompany)
            .where(DefenseCompany.name.ilike(f"%{escaped}%"))
            .order_by(DefenseCompany.year.desc())
        ).scalars().all()

        if not companies:
            raise HTTPException(status_code=404, detail=f"Supplier not found: {name}")

        latest = companies[0]
        country = session.execute(
            select(Country).where(Country.id == latest.country_id)
        ).scalar_one_or_none()

        # Revenue trend
        revenue_trend = [
            {"year": c.year, "arms_revenue_usd_m": c.arms_revenue_usd, "rank": c.rank}
            for c in companies
        ]

        # Supply chain nodes linked to this company
        nodes = session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.company_name.ilike(f"%{escaped}%")
            )
        ).scalars().all()

        # Find alternatives via graph
        graph = SupplyChainGraph(session)
        graph.build()
        alternatives = []
        for node in nodes:
            alts = graph.find_alternatives(node.name)
            alternatives.extend(alts)

        result = {
            "name": latest.name,
            "country": country.name if country else "unknown",
            "latest_rank": latest.rank,
            "latest_arms_revenue_usd_m": latest.arms_revenue_usd,
            "revenue_trend": revenue_trend[:10],
            "supply_chain_nodes": [
                {"name": n.name, "type": n.node_type.value if n.node_type else "unknown"}
                for n in nodes
            ],
            "alternatives": alternatives[:10],
        }
        _set_cache(cache_key, result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("PSI supplier %s failed: %s", name, e)
        raise HTTPException(status_code=500, detail=f"Failed to get supplier: {name}")
    finally:
        session.close()


@router.get("/alerts")
async def get_supply_chain_alerts(
    severity_min: int = Query(1, description="Minimum severity (1-5)"),
    is_active: bool = Query(True, description="Only active alerts"),
):
    """Active supply chain disruption alerts."""
    cache_key = f"alerts:{severity_min}:{is_active}"
    cached = _check_cache(cache_key, _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        query = select(SupplyChainAlert).where(
            SupplyChainAlert.severity >= severity_min,
        )
        if is_active:
            query = query.where(SupplyChainAlert.is_active == True)  # noqa: E712

        query = query.order_by(SupplyChainAlert.severity.desc())
        alerts = session.execute(query).scalars().all()

        result = [
            {
                "id": a.id,
                "type": a.alert_type.value if a.alert_type else "unknown",
                "severity": a.severity,
                "title": a.title,
                "description": a.description or "",
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in alerts
        ]
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("PSI alerts failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get alerts")
    finally:
        session.close()


@router.get("/chokepoints")
async def get_chokepoint_status():
    """Strategic chokepoint status with risk levels and affected routes."""
    cached = _check_cache("chokepoints", _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        from src.analysis.supply_chain import CHOKEPOINT_RISK

        routes = session.execute(select(SupplyChainRoute)).scalars().all()

        # Aggregate per chokepoint
        cp_data: dict[str, dict] = {}
        for cp_name, risk in CHOKEPOINT_RISK.items():
            cp_data[cp_name] = {
                "name": cp_name,
                "risk_factor": risk,
                "affected_routes": 0,
                "routes": [],
            }

        for route in routes:
            if not route.chokepoints:
                continue
            try:
                cps = json.loads(route.chokepoints)
            except (json.JSONDecodeError, TypeError):
                continue

            origin = session.execute(
                select(Country).where(Country.id == route.origin_country_id)
            ).scalar_one_or_none()
            dest = session.execute(
                select(Country).where(Country.id == route.destination_country_id)
            ).scalar_one_or_none()

            for cp in cps:
                if cp in cp_data:
                    cp_data[cp]["affected_routes"] += 1
                    cp_data[cp]["routes"].append({
                        "origin": origin.name if origin else "unknown",
                        "destination": dest.name if dest else "unknown",
                        "route_name": route.route_name or "",
                    })

        result = sorted(
            cp_data.values(),
            key=lambda x: x["risk_factor"],
            reverse=True,
        )
        _set_cache("chokepoints", result)
        return result
    except Exception as e:
        logger.error("PSI chokepoints failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to get chokepoint data")
    finally:
        session.close()


@router.get("/propagation")
async def get_disruption_propagation(
    disruption_type: str = Query(..., description="material, country, component, or company"),
    entity: str = Query(..., description="Name of disrupted entity"),
    severity: float = Query(1.0, description="Severity multiplier 0.0-1.0"),
):
    """Disruption cascade analysis showing affected platforms."""
    cache_key = f"propagation:{disruption_type}:{entity}:{severity}"
    cached = _check_cache(cache_key, _PSI_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        graph = SupplyChainGraph(session)
        graph.build()
        affected = graph.propagate_disruption(disruption_type, entity, severity)

        result = {
            "disruption": {
                "type": disruption_type,
                "entity": entity,
                "severity": severity,
            },
            "affected_count": len(affected),
            "affected_items": [
                {
                    "name": a.node_name,
                    "type": a.node_type,
                    "depth": a.depth,
                    "severity": a.severity,
                    "path": a.path,
                }
                for a in affected[:50]
            ],
            "by_type": _group_by_type(affected),
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("PSI propagation failed: %s", e)
        raise HTTPException(status_code=500, detail="Propagation analysis failed")
    finally:
        session.close()


@router.get("/forecasts")
async def get_forecasts():
    """Predictive analytics — 12-18 month supply chain risk forecasts."""
    cached = _check_cache("forecasts", _PSI_GRAPH_TTL)
    if cached:
        return cached

    from src.analysis.forecasting import SupplyChainForecaster
    session = SessionLocal()
    try:
        forecaster = SupplyChainForecaster(session)
        result = forecaster.generate_all_forecasts()
        _set_cache("forecasts", result)
        return result
    except Exception as e:
        logger.error("Forecasting failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/taxonomy")
async def get_taxonomy():
    """All 13 DND risk taxonomy categories with composite scores."""
    cached = _check_cache("taxonomy", _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    from src.analysis.risk_taxonomy import RiskTaxonomyScorer
    from src.storage.models import RiskTaxonomyScore
    from src.analysis.confidence import compute_confidence
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        composites = scorer.compute_category_composites()

        cats = sorted(composites.values(), key=lambda c: c["composite_score"], reverse=True)
        global_score = sum(c["composite_score"] for c in cats) / len(cats) if cats else 0

        for cat in cats:
            cat_conf = compute_confidence(
                data_source=cat["data_source"],
                risk_source="taxonomy",
                dimension=str(cat["category_id"]),
                session=session,
            )
            cat["confidence"] = cat_conf

        high_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "high")
        med_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "medium")
        low_count = sum(1 for c in cats if c.get("confidence", {}).get("level") == "low")
        avg_conf = sum(c.get("confidence", {}).get("score", 0) for c in cats) / max(len(cats), 1)
        tri_count = sum(1 for c in cats if c.get("confidence", {}).get("triangulated"))

        result = {
            "global_composite": round(global_score, 1),
            "global_risk_level": "red" if global_score >= 70 else "amber" if global_score >= 40 else "green",
            "categories": cats,
            "live_count": sum(1 for c in cats if c["data_source"] == "live"),
            "hybrid_count": sum(1 for c in cats if c["data_source"] == "hybrid"),
            "seeded_count": sum(1 for c in cats if c["data_source"] == "seeded"),
            "total_subcategories": 121,
            "last_scored": session.query(func.max(RiskTaxonomyScore.scored_at)).scalar().isoformat() if session.query(func.max(RiskTaxonomyScore.scored_at)).scalar() else None,
            "confidence_summary": {
                "high_count": high_count,
                "medium_count": med_count,
                "low_count": low_count,
                "avg_confidence": round(avg_conf),
                "triangulated_pct": round(tri_count / max(len(cats), 1) * 100),
            },
        }
        _set_cache("taxonomy", result)
        return result
    except Exception as e:
        logger.error("get_taxonomy failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/taxonomy/summary")
async def get_taxonomy_summary():
    """Dashboard-ready 13-card summary for Insights page."""
    cached = _check_cache("taxonomy_summary", _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    from src.analysis.risk_taxonomy import RiskTaxonomyScorer
    from src.analysis.confidence import compute_confidence
    session = SessionLocal()
    try:
        scorer = RiskTaxonomyScorer(session)
        scorer.seed_initial_scores()
        composites = scorer.compute_category_composites()

        cats = sorted(composites.values(), key=lambda c: c["category_id"])
        global_score = sum(c["composite_score"] for c in cats) / len(cats) if cats else 0

        category_cards = []
        for c in cats:
            cat_conf = compute_confidence(
                data_source=c["data_source"],
                risk_source="taxonomy",
                dimension=str(c["category_id"]),
                session=session,
            )
            category_cards.append({
                "category_id": c["category_id"],
                "short_name": c["short_name"],
                "icon": c["icon"],
                "score": c["composite_score"],
                "risk_level": c["risk_level"],
                "trend": c["trend"],
                "data_source": c["data_source"],
                "confidence": cat_conf,
            })

        result = {
            "global_composite": round(global_score, 1),
            "categories": category_cards,
        }
        _set_cache("taxonomy_summary", result)
        return result
    except Exception as e:
        logger.error("get_taxonomy_summary failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/taxonomy/{category_id}")
async def get_taxonomy_category(category_id: int):
    """Single category with all sub-category details."""
    from src.analysis.risk_taxonomy import TAXONOMY_DEFINITIONS, RiskTaxonomyScorer
    from src.storage.models import RiskTaxonomyScore
    from src.analysis.confidence import compute_confidence

    if category_id not in TAXONOMY_DEFINITIONS:
        raise HTTPException(status_code=404, detail="Resource not found")

    cache_key = f"taxonomy_cat_{category_id}"
    cached = _check_cache(cache_key, _PSI_TAXONOMY_TTL)
    if cached:
        return cached

    session = SessionLocal()
    try:
        cat = TAXONOMY_DEFINITIONS[category_id]
        rows = session.query(RiskTaxonomyScore).filter_by(
            category_id=category_id
        ).order_by(RiskTaxonomyScore.score.desc()).all()

        if not rows:
            scorer = RiskTaxonomyScorer(session)
            scorer.seed_initial_scores()
            rows = session.query(RiskTaxonomyScore).filter_by(
                category_id=category_id
            ).order_by(RiskTaxonomyScore.score.desc()).all()

        avg_score = sum(r.score for r in rows) / len(rows) if rows else 0

        subcategory_dicts = []
        for r in rows:
            sub_conf = compute_confidence(
                data_source=r.data_source,
                risk_source="taxonomy",
                dimension=r.subcategory_key,
                session=session,
            )
            subcategory_dicts.append({
                "key": r.subcategory_key,
                "name": r.subcategory_name,
                "score": round(r.score, 1),
                "psi_module": r.psi_module,
                "data_source": r.data_source,
                "rationale": r.rationale,
                "last_event": r.last_event,
                "confidence": sub_conf,
            })

        result = {
            "category_id": category_id,
            "category_name": cat["name"],
            "short_name": cat["short_name"],
            "composite_score": round(avg_score, 1),
            "data_source": cat["subcategories"][0]["data_source"] if cat["subcategories"] else "seeded",
            "subcategories": subcategory_dicts,
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_taxonomy_category failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# --- Cobalt Alert & Risk Register Persistence (G2, G3) ---

class CobaltAlertAction(BaseModel):
    alert_id: str
    action: str
    analyst: str = ""

@router.get("/alerts/cobalt/live")
async def get_cobalt_live_alerts():
    """Get live-generated Cobalt alerts from GDELT + rule engine."""
    from src.analysis.cobalt_alert_engine import get_cached_alerts, run_cobalt_alert_engine
    cached, ts = get_cached_alerts()
    if cached and ts and (datetime.utcnow() - ts).total_seconds() < 1800:
        return {"alerts": cached, "count": len(cached), "generated_at": ts.isoformat(), "cached": True}
    try:
        alerts = await run_cobalt_alert_engine()
        return {"alerts": alerts, "count": len(alerts), "generated_at": datetime.utcnow().isoformat(), "cached": False}
    except Exception as e:
        logger.error("Cobalt live alerts failed: %s", e)
        return {"alerts": cached or [], "count": len(cached or []), "error": "Live generation failed, showing cached"}


@router.post("/alerts/cobalt/action")
async def cobalt_alert_action(req: CobaltAlertAction):
    """Record an analyst action on a Cobalt watchtower alert."""
    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        row = svc.upsert_mitigation_action(
            risk_source="cobalt_alert",
            risk_entity=req.alert_id,
            risk_dimension=req.action,
            risk_score=0.0,
            coa_action=req.action,
            coa_priority="high",
            status=req.action,
            notes=req.analyst,
        )
        return {
            "status": "recorded",
            "alert_id": row.risk_entity,
            "action": row.coa_action,
            "analyst": row.notes or "",
            "timestamp": (row.updated_at or row.created_at).isoformat(),
        }
    except Exception as e:
        logger.error("cobalt_alert_action failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()

@router.get("/alerts/cobalt/actions")
async def get_cobalt_alert_actions():
    """Get all recorded Cobalt alert actions."""
    session = SessionLocal()
    try:
        rows = session.query(MitigationAction).filter_by(
            risk_source="cobalt_alert",
        ).all()
        return [
            {
                "alert_id": r.risk_entity,
                "action": r.coa_action,
                "analyst": r.notes or "",
                "timestamp": (r.updated_at or r.created_at).isoformat(),
            }
            for r in rows
        ]
    except Exception as e:
        logger.error("get_cobalt_alert_actions failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


class RegisterStatusUpdate(BaseModel):
    risk_id: str
    new_status: str
    analyst: str = ""

@router.patch("/register/cobalt/{risk_id}")
async def update_cobalt_register_status(risk_id: str, update: RegisterStatusUpdate):
    """Update status of a Cobalt risk register entry."""
    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        row = svc.upsert_mitigation_action(
            risk_source="cobalt_register",
            risk_entity=risk_id,
            risk_dimension="status_override",
            risk_score=0.0,
            coa_action=update.new_status,
            coa_priority="medium",
            status=update.new_status,
            notes=update.analyst,
        )
        return {
            "status": "updated",
            "risk_id": row.risk_entity,
            "new_status": row.coa_action,
            "analyst": row.notes or "",
            "timestamp": (row.updated_at or row.created_at).isoformat(),
        }
    except Exception as e:
        logger.error("update_cobalt_register_status failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()

@router.get("/register/cobalt/status")
async def get_cobalt_register_status():
    """Get all Cobalt risk register status overrides."""
    session = SessionLocal()
    try:
        rows = session.query(MitigationAction).filter_by(
            risk_source="cobalt_register",
        ).all()
        return {
            r.risk_entity: {
                "risk_id": r.risk_entity,
                "status": r.coa_action,
                "analyst": r.notes or "",
                "timestamp": (r.updated_at or r.created_at).isoformat(),
            }
            for r in rows
        }
    except Exception as e:
        logger.error("get_cobalt_register_status failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _count_bom_nodes(entry) -> int:
    count = 1
    for child in entry.children:
        count += _count_bom_nodes(child)
    return count


def _count_sole_source(entry) -> int:
    count = 1 if entry.is_sole_source else 0
    for child in entry.children:
        count += _count_sole_source(child)
    return count


def _group_by_type(items) -> dict[str, int]:
    groups: dict[str, int] = {}
    for item in items:
        t = item.node_type
        groups[t] = groups.get(t, 0) + 1
    return groups
