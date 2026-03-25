"""Defence Supplier Exposure API endpoints.

Provides Canadian defence supplier risk analysis, contract concentration,
ownership breakdown, and alert data for the DND intelligence dashboard.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select, func

from src.storage.database import SessionLocal
from src.storage.models import (
    DefenceSupplier,
    SupplierContract,
    SupplierRiskScore,
    OwnershipType,
    ContractStatus,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Suppliers"])

# In-memory cache: key -> (timestamp, data)
_cache: dict[str, tuple[float, dict | list]] = {}
_TTL = 300  # 5 minutes


def _check_cache(key: str) -> dict | list | None:
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _TTL:
        return cached[1]
    return None


def _set_cache(key: str, data: dict | list) -> None:
    _cache[key] = (time.time(), data)


# ------------------------------------------------------------------
# 1. GET /dashboard/suppliers — all suppliers sorted by risk desc
# ------------------------------------------------------------------

@router.get("/suppliers")
async def get_suppliers():
    """All defence suppliers sorted by composite risk score descending."""
    cached = _check_cache("suppliers")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.execute(select(DefenceSupplier)).scalars().all()

        # Sort in Python to avoid SQL nullslast complexity
        sorted_suppliers = sorted(
            suppliers,
            key=lambda s: s.risk_score_composite if s.risk_score_composite is not None else 0.0,
            reverse=True,
        )

        def _risk_level(score):
            if score is None: return "unknown"
            if score >= 70: return "red"
            if score >= 40: return "amber"
            return "green"

        supplier_data = []
        total_score = 0
        scored_count = 0
        for s in sorted_suppliers:
            top_risk = session.execute(
                select(SupplierRiskScore).where(SupplierRiskScore.supplier_id == s.id)
                .order_by(SupplierRiskScore.score.desc())
            ).scalars().first()
            active_count = session.execute(
                select(func.count()).where(
                    SupplierContract.supplier_id == s.id,
                    SupplierContract.status == ContractStatus.ACTIVE,
                )
            ).scalar() or 0
            total_value = session.execute(
                select(func.sum(SupplierContract.contract_value_cad))
                .where(SupplierContract.supplier_id == s.id)
            ).scalar() or 0

            supplier_data.append({
                "name": s.name,
                "sector": s.sector.value if s.sector else "other",
                "ownership_type": s.ownership_type.value if s.ownership_type else "unknown",
                "parent_company": s.parent_company,
                "parent_country": s.parent_country,
                "contract_value_total_cad": total_value,
                "active_contracts": active_count,
                "risk_score_composite": s.risk_score_composite,
                "risk_level": _risk_level(s.risk_score_composite),
                "top_risk_dimension": top_risk.dimension.value if top_risk else None,
            })
            if s.risk_score_composite is not None:
                total_score += s.risk_score_composite
                scored_count += 1

        result = {
            "total_suppliers": len(sorted_suppliers),
            "avg_risk_score": round(total_score / scored_count) if scored_count else 0,
            "suppliers": supplier_data,
        }
        _set_cache("suppliers", result)
        return result
    except Exception as e:
        logger.error("get_suppliers failed: %s", e)
        return {"total_suppliers": 0, "suppliers": [], "error": str(e)}
    finally:
        session.close()


# ------------------------------------------------------------------
# 2. GET /dashboard/suppliers/concentration — sector-level analysis
# ------------------------------------------------------------------

@router.get("/suppliers/concentration")
async def get_concentration():
    """Sector-level supplier counts and sole-source flags."""
    cached = _check_cache("suppliers:concentration")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.execute(select(DefenceSupplier)).scalars().all()
        contracts = session.execute(select(SupplierContract)).scalars().all()

        # Count suppliers per sector
        sector_supplier_count: dict[str, int] = defaultdict(int)
        for s in suppliers:
            if s.sector:
                sector_supplier_count[s.sector.value] += 1

        # Count sole-source contracts per sector
        sector_sole_source: dict[str, int] = defaultdict(int)
        sector_contract_value: dict[str, float] = defaultdict(float)
        for c in contracts:
            if c.sector:
                sector = c.sector.value
                if c.is_sole_source:
                    sector_sole_source[sector] += 1
                sector_contract_value[sector] += c.contract_value_cad or 0.0

        all_sectors = set(sector_supplier_count.keys()) | set(sector_contract_value.keys())
        sectors = []
        for sector in sorted(all_sectors):
            supplier_count = sector_supplier_count.get(sector, 0)
            sole_source_contracts = sector_sole_source.get(sector, 0)
            sectors.append({
                "sector": sector,
                "supplier_count": supplier_count,
                "total_contract_value_cad": round(sector_contract_value.get(sector, 0.0), 2),
                "sole_source_contracts": sole_source_contracts,
                "is_sole_source_risk": supplier_count <= 1 or sole_source_contracts > 0,
            })

        result = {
            "sectors": sectors,
            "total_sectors": len(sectors),
        }
        _set_cache("suppliers:concentration", result)
        return result
    except Exception as e:
        logger.error("get_concentration failed: %s", e)
        return {"sectors": [], "total_sectors": 0, "error": str(e)}
    finally:
        session.close()


# ------------------------------------------------------------------
# 3. GET /dashboard/suppliers/risk-matrix — scatter plot data
# ------------------------------------------------------------------

@router.get("/suppliers/risk-matrix")
async def get_risk_matrix():
    """Scatter plot data: x=total contract value (CAD), y=composite risk score."""
    cached = _check_cache("suppliers:risk-matrix")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.execute(select(DefenceSupplier)).scalars().all()
        contracts = session.execute(select(SupplierContract)).scalars().all()

        # Sum contract values per supplier
        supplier_contract_value: dict[int, float] = defaultdict(float)
        for c in contracts:
            supplier_contract_value[c.supplier_id] += c.contract_value_cad or 0.0

        points = []
        for s in suppliers:
            points.append({
                "id": s.id,
                "name": s.name,
                "sector": s.sector.value if s.sector else None,
                "ownership_type": s.ownership_type.value if s.ownership_type else None,
                "x": supplier_contract_value.get(s.id, 0.0),
                "y": s.risk_score_composite if s.risk_score_composite is not None else 0.0,
            })

        result = {
            "points": points,
            "x_label": "Total Contract Value (CAD)",
            "y_label": "Composite Risk Score (0-100)",
        }
        _set_cache("suppliers:risk-matrix", result)
        return result
    except Exception as e:
        logger.error("get_risk_matrix failed: %s", e)
        return {"points": [], "error": str(e)}
    finally:
        session.close()


# ------------------------------------------------------------------
# 4. GET /dashboard/suppliers/ownership — breakdown by ownership type
# ------------------------------------------------------------------

@router.get("/suppliers/ownership")
async def get_ownership():
    """Ownership breakdown and foreign supplier list."""
    cached = _check_cache("suppliers:ownership")
    if cached:
        return cached

    session = SessionLocal()
    try:
        suppliers = session.execute(select(DefenceSupplier)).scalars().all()

        breakdown: dict[str, int] = defaultdict(int)
        foreign_suppliers = []

        for s in suppliers:
            ownership = s.ownership_type.value if s.ownership_type else "unknown"
            breakdown[ownership] += 1

            if s.ownership_type == OwnershipType.FOREIGN_SUBSIDIARY:
                foreign_suppliers.append({
                    "id": s.id,
                    "name": s.name,
                    "sector": s.sector.value if s.sector else None,
                    "parent_company": s.parent_company,
                    "parent_country": s.parent_country,
                    "risk_score_composite": s.risk_score_composite,
                })

        # Sort foreign suppliers by risk score descending
        foreign_suppliers.sort(
            key=lambda s: s["risk_score_composite"] if s["risk_score_composite"] is not None else 0.0,
            reverse=True,
        )

        result = {
            "breakdown": dict(breakdown),
            "total_suppliers": len(suppliers),
            "foreign_suppliers": foreign_suppliers,
            "foreign_count": len(foreign_suppliers),
        }
        _set_cache("suppliers:ownership", result)
        return result
    except Exception as e:
        logger.error("get_ownership failed: %s", e)
        return {"breakdown": {}, "foreign_suppliers": [], "error": str(e)}
    finally:
        session.close()


# ------------------------------------------------------------------
# 5. GET /dashboard/suppliers/alerts — risk scores >70
# ------------------------------------------------------------------

@router.get("/suppliers/alerts")
async def get_supplier_alerts():
    """Supplier risk alerts: risk scores above 70, sorted by severity."""
    cached = _check_cache("suppliers:alerts")
    if cached:
        return cached

    session = SessionLocal()
    try:
        # Get all risk scores above threshold
        risk_scores = session.execute(
            select(SupplierRiskScore).where(SupplierRiskScore.score > 70.0)
        ).scalars().all()

        alerts = []
        for rs in risk_scores:
            supplier = session.get(DefenceSupplier, rs.supplier_id)
            if not supplier:
                continue
            alerts.append({
                "supplier_id": rs.supplier_id,
                "supplier_name": supplier.name,
                "sector": supplier.sector.value if supplier.sector else None,
                "dimension": rs.dimension.value if rs.dimension else None,
                "score": rs.score,
                "rationale": rs.rationale,
                "scored_at": rs.scored_at.isoformat() if rs.scored_at else None,
            })

        # Sort by score descending (most severe first)
        alerts.sort(key=lambda a: a["score"], reverse=True)

        result = {"alerts": alerts, "total_alerts": len(alerts)}
        _set_cache("suppliers:alerts", result)
        return result
    except Exception as e:
        logger.error("get_supplier_alerts failed: %s", e)
        return {"alerts": [], "total_alerts": 0, "error": str(e)}
    finally:
        session.close()


# ------------------------------------------------------------------
# 6. GET /dashboard/suppliers/{name}/profile — MUST be registered last
# ------------------------------------------------------------------

@router.get("/suppliers/{name}/profile")
async def get_supplier_profile(name: str):
    """Single supplier detail with contracts and risk scores."""
    cache_key = f"suppliers:profile:{name}"
    cached = _check_cache(cache_key)
    if cached:
        return cached

    session = SessionLocal()
    try:
        supplier = session.execute(
            select(DefenceSupplier).where(DefenceSupplier.name == name)
        ).scalar_one_or_none()

        if not supplier:
            return {"error": f"Supplier not found: {name}"}

        contracts = session.execute(
            select(SupplierContract).where(SupplierContract.supplier_id == supplier.id)
        ).scalars().all()

        risk_scores = session.execute(
            select(SupplierRiskScore).where(SupplierRiskScore.supplier_id == supplier.id)
        ).scalars().all()

        result = {
            "id": supplier.id,
            "name": supplier.name,
            "legal_name": supplier.legal_name,
            "sector": supplier.sector.value if supplier.sector else None,
            "ownership_type": supplier.ownership_type.value if supplier.ownership_type else None,
            "parent_company": supplier.parent_company,
            "parent_country": supplier.parent_country,
            "headquarters_city": supplier.headquarters_city,
            "headquarters_province": supplier.headquarters_province,
            "risk_score_composite": supplier.risk_score_composite,
            "estimated_revenue_cad": supplier.estimated_revenue_cad,
            "dnd_contract_revenue_cad": supplier.dnd_contract_revenue_cad,
            "employee_count": supplier.employee_count,
            "contracts": [
                {
                    "id": c.id,
                    "contract_number": c.contract_number,
                    "contract_value_cad": c.contract_value_cad,
                    "description": c.description,
                    "department": c.department,
                    "award_date": c.award_date.isoformat() if c.award_date else None,
                    "end_date": c.end_date.isoformat() if c.end_date else None,
                    "status": c.status.value if c.status else None,
                    "sector": c.sector.value if c.sector else None,
                    "is_sole_source": c.is_sole_source,
                }
                for c in contracts
            ],
            "risk_scores": [
                {
                    "dimension": rs.dimension.value if rs.dimension else None,
                    "score": rs.score,
                    "rationale": rs.rationale,
                    "scored_at": rs.scored_at.isoformat() if rs.scored_at else None,
                }
                for rs in risk_scores
            ],
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_supplier_profile %s failed: %s", name, e)
        return {"error": f"Failed to load profile for {name}"}
    finally:
        session.close()
