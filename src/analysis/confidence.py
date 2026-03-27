"""Confidence scoring utility — "Glass Box" data integrity.

Computes confidence levels for any risk assessment based on
data source type and number of independent corroborating sources.
"""
from __future__ import annotations

import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Source definitions: which independent data sources back each risk dimension
_SUPPLIER_SOURCES = {
    "foreign_ownership": [
        ("Wikidata ownership", "parent_company"),    # check DefenceSupplier.parent_company IS NOT NULL
        ("OFAC/EU sanctions", "sanctions_proximity"), # check SupplierRiskScore exists for sanctions_proximity
        ("SIPRI Top 100", "sipri_rank"),              # check DefenceSupplier.sipri_rank IS NOT NULL
    ],
    "customer_concentration": [
        ("Open Canada procurement", "contracts"),     # check SupplierContract count > 0
        ("Estimated revenue data", "revenue"),        # check DefenceSupplier.estimated_revenue_cad IS NOT NULL
    ],
    "single_source": [
        ("Procurement contracts", "contracts"),
        ("SIPRI arms transfers", "transfers"),
    ],
    "contract_activity": [
        ("Procurement contracts", "contracts"),
    ],
    "sanctions_proximity": [
        ("OFAC SDN list", "ofac"),
        ("EU sanctions list", "eu_sanctions"),
        ("PSI material dependencies", "psi_materials"),
    ],
    "contract_performance": [
        ("Procurement contracts", "contracts"),
    ],
}

_TAXONOMY_LIVE_SOURCES = {
    "1": [("GDELT news", None), ("Sanctions lists", None), ("Wikidata corporate graph", None)],
    "2": [("GDELT geopolitical news", None), ("Sanctions lists", None)],
    "3": [("PSI supply chain data", None), ("Supplier risk scores", None), ("SIPRI transfers", None)],
    "11": [("World Bank indicators", None), ("Comtrade trade data", None)],
}

_PSI_SOURCES = {
    "material_shortage": [("PSI material data", None), ("Comtrade trade flows", None)],
    "chokepoint_blocked": [("Chokepoint registry", None), ("Maritime/AIS data", None)],
    "sanctions_risk": [("OFAC SDN", None), ("EU sanctions", None), ("PSI graph", None)],
    "concentration_risk": [("PSI concentration analyzer", None), ("Comtrade data", None)],
    "supplier_disruption": [("GDELT news", None), ("Financial data", None)],
    "demand_surge": [("NATO spending data", None), ("DSCA sales", None)],
}


def compute_confidence(
    data_source: str | None,
    risk_source: str,
    dimension: str,
    session: Session,
) -> dict:
    """Compute confidence for a risk assessment.

    Args:
        data_source: "live", "hybrid", "seeded", or None (infer from risk_source)
        risk_source: "supplier", "taxonomy", "psi", "mitigation"
        dimension: The specific risk dimension (e.g., "foreign_ownership", "1a", "material_shortage")
        session: SQLAlchemy session (reuse the caller's session, do NOT open a new one)

    Returns:
        dict with level, score, source_count, sources, triangulated, label
    """
    # Determine data source if not provided (for mitigation actions)
    if data_source is None:
        if risk_source == "supplier":
            data_source = "live"
        elif risk_source == "psi":
            data_source = "live"
        elif risk_source == "taxonomy":
            # Infer from dimension prefix
            cat_id = dimension.rstrip("abcdefghijklmnopqrst")
            live_cats = {"1", "2", "3", "11"}
            hybrid_cats = {"7", "10", "12"}
            if cat_id in live_cats:
                data_source = "live"
            elif cat_id in hybrid_cats:
                data_source = "hybrid"
            else:
                data_source = "seeded"
        else:
            data_source = "seeded"

    # Count sources
    sources = _count_sources(risk_source, dimension, session)
    source_count = len(sources)
    source_names = [s[0] for s in sources]

    # Determine confidence level and score
    if data_source == "live":
        if source_count >= 3:
            level = "high"
            score = min(80 + source_count * 5, 95)
        elif source_count >= 1:
            level = "medium"
            score = 60 + source_count * 5
        else:
            level = "medium"
            score = 55
            source_names = ["Computed from OSINT data"]
            source_count = 1
    elif data_source == "hybrid":
        level = "medium"
        score = 50 + source_count * 5
        score = min(score, 70)
    else:  # seeded
        level = "low"
        score = 25 + source_count * 5
        score = min(score, 35)
        if source_count <= 1:
            source_names = ["Seeded baseline"]
            source_count = 1

    triangulated = source_count >= 3

    # Generate label
    if triangulated:
        label = f"Triangulated ({source_count} sources)"
    elif source_count >= 2:
        label = f"Corroborated ({source_count} sources)"
    elif data_source == "seeded":
        label = "Seeded baseline - limited corroboration"
    else:
        label = f"Single source (live OSINT)"

    return {
        "level": level,
        "score": score,
        "source_count": source_count,
        "sources": source_names,
        "triangulated": triangulated,
        "label": label,
    }


def _count_sources(risk_source: str, dimension: str, session: Session) -> list[tuple[str, str | None]]:
    """Count how many independent sources back this risk dimension."""
    active_sources = []

    if risk_source == "supplier":
        # Check which supplier data sources are actually populated
        from src.storage.models import DefenceSupplier, SupplierContract, SupplierRiskScore, RiskDimension
        source_defs = _SUPPLIER_SOURCES.get(dimension, [])
        for source_name, check_key in source_defs:
            if check_key == "parent_company":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.parent_company.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "sipri_rank":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.sipri_rank.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "contracts":
                count = session.query(SupplierContract).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "revenue":
                count = session.query(DefenceSupplier).filter(DefenceSupplier.estimated_revenue_cad.isnot(None)).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key == "sanctions_proximity":
                count = session.query(SupplierRiskScore).filter(SupplierRiskScore.dimension == RiskDimension.SANCTIONS_PROXIMITY).count()
                if count > 0:
                    active_sources.append((source_name, check_key))
            elif check_key in ("ofac", "eu_sanctions", "psi_materials", "transfers"):
                # These are always available (static/cached data)
                active_sources.append((source_name, check_key))

    elif risk_source == "taxonomy":
        cat_id = dimension.rstrip("abcdefghijklmnopqrst")
        source_defs = _TAXONOMY_LIVE_SOURCES.get(cat_id, [])
        if source_defs:
            active_sources = source_defs
        else:
            active_sources = [("Seeded baseline", None)]

    elif risk_source == "psi":
        source_defs = _PSI_SOURCES.get(dimension, [])
        if source_defs:
            active_sources = source_defs
        else:
            active_sources = [("PSI risk engine", None)]

    else:
        active_sources = [("Platform assessment", None)]

    return active_sources
