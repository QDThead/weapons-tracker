"""6-dimension risk scoring engine for Canadian defence suppliers.

Scores each supplier across: foreign ownership, customer concentration,
single source dependency, contract activity trend, sanctions proximity,
and contract performance. Persists dimension scores and composite to DB.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.storage.models import (
    DefenceSupplier,
    SupplierContract,
    SupplierRiskScore,
    ContractStatus,
    OwnershipType,
    RiskDimension,
    SupplierSector,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLIED_COUNTRIES = {
    "United States", "United Kingdom", "France", "Germany", "Italy",
    "Australia", "New Zealand", "Japan", "South Korea", "Netherlands",
    "Belgium", "Norway", "Denmark", "Sweden", "Finland", "Poland",
    "Spain", "Portugal", "Czech Republic", "Romania", "Turkey",
}

EMBARGOED_COUNTRIES = {
    "Russia", "Belarus", "Iran", "North Korea", "Syria", "Myanmar",
    "China", "Venezuela", "Cuba", "Sudan", "South Sudan",
    "Central African Republic", "Democratic Republic of the Congo",
    "Libya", "Somalia", "Yemen", "Iraq",
}

WEIGHTS = {
    RiskDimension.FOREIGN_OWNERSHIP: 0.20,
    RiskDimension.CUSTOMER_CONCENTRATION: 0.15,
    RiskDimension.SINGLE_SOURCE: 0.25,
    RiskDimension.CONTRACT_ACTIVITY: 0.15,
    RiskDimension.SANCTIONS_PROXIMITY: 0.10,
    RiskDimension.CONTRACT_PERFORMANCE: 0.15,
}


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class SupplierRiskScorer:
    """Computes 6-dimension risk scores for a DefenceSupplier."""

    def __init__(self, session: Session) -> None:
        self.session = session

    # --- Dimension 1: Foreign Ownership (20%) ---

    def score_foreign_ownership(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on corporate ownership structure.

        Returns:
            (score 0-100, rationale string)
        """
        ownership = supplier.ownership_type
        country = supplier.parent_country

        if ownership in (
            OwnershipType.CANADIAN_PRIVATE,
            OwnershipType.CANADIAN_PUBLIC,
            OwnershipType.CROWN_CORP,
        ):
            return 0.0, "Fully Canadian-owned — no foreign ownership risk"

        if ownership == OwnershipType.JOINT_VENTURE:
            if country and country in ALLIED_COUNTRIES:
                return 30.0, f"Joint venture with allied country ({country})"
            if country and country in EMBARGOED_COUNTRIES:
                return 90.0, f"Joint venture with embargoed country ({country})"
            return 50.0, f"Joint venture with {country or 'unknown country'}"

        if ownership == OwnershipType.FOREIGN_SUBSIDIARY:
            if country and country in EMBARGOED_COUNTRIES:
                return 90.0, f"Subsidiary of embargoed country ({country})"
            if country and country in ALLIED_COUNTRIES:
                return 50.0, f"Subsidiary of {country} — allied but foreign-controlled"
            if country:
                return 75.0, f"Subsidiary of non-allied country ({country})"
            return 60.0, "Foreign subsidiary — parent country unknown"

        # Fallback for unknown ownership
        return 20.0, "Ownership classification unclear — low default risk applied"

    # --- Dimension 2: Customer Concentration (15%) ---

    def score_customer_concentration(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on DND revenue as share of total revenue.

        Returns:
            (score 0-100, rationale string)
        """
        total_rev = supplier.estimated_revenue_cad
        dnd_rev = supplier.dnd_contract_revenue_cad

        if not total_rev or not dnd_rev or total_rev <= 0:
            return 65.0, "Revenue data unavailable — default moderate concentration risk applied"

        pct = (dnd_rev / total_rev) * 100.0

        if pct >= 90:
            return 90.0, f"DND comprises {pct:.0f}% of revenue — extreme single-customer dependency"
        if pct >= 75:
            return 75.0, f"DND comprises {pct:.0f}% of revenue — very high concentration"
        if pct >= 50:
            return 55.0, f"DND comprises {pct:.0f}% of revenue — significant concentration"
        if pct >= 25:
            return 30.0, f"DND comprises {pct:.0f}% of revenue — moderate concentration"
        return 10.0, f"DND comprises {pct:.0f}% of revenue — well-diversified customer base"

    # --- Dimension 3: Single Source (25%) ---

    def score_single_source(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on whether this supplier is sole or one of few in their sector.

        Returns:
            (score 0-100, rationale string)
        """
        if not supplier.sector:
            return 50.0, "Sector not specified — cannot assess single-source status"

        sector = supplier.sector

        # Count distinct active suppliers in the same sector (by distinct supplier_id)
        supplier_count = (
            self.session.query(func.count(func.distinct(SupplierContract.supplier_id)))
            .filter(
                SupplierContract.sector == sector,
                SupplierContract.status == ContractStatus.ACTIVE,
            )
            .scalar()
        ) or 0

        sector_label = sector.value.replace("_", " ")

        if supplier_count <= 1:
            return 90.0, f"Sole active supplier in {sector_label} — critical single-source risk"
        if supplier_count == 2:
            return 60.0, f"One of only 2 suppliers in {sector_label} — high concentration"
        return 20.0, f"One of {supplier_count} suppliers in {sector_label} — adequate competition"

    # --- Dimension 4: Contract Activity (15%) ---

    def score_contract_activity(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on contract volume trend: last 2yr vs prior 2yr.

        Returns:
            (score 0-100, rationale string)
        """
        today = date.today()
        two_yr_ago = date(today.year - 2, today.month, today.day)
        four_yr_ago = date(today.year - 4, today.month, today.day)

        recent_value = (
            self.session.query(func.coalesce(func.sum(SupplierContract.contract_value_cad), 0.0))
            .filter(
                SupplierContract.supplier_id == supplier.id,
                SupplierContract.award_date >= two_yr_ago,
            )
            .scalar()
        ) or 0.0

        prior_value = (
            self.session.query(func.coalesce(func.sum(SupplierContract.contract_value_cad), 0.0))
            .filter(
                SupplierContract.supplier_id == supplier.id,
                SupplierContract.award_date >= four_yr_ago,
                SupplierContract.award_date < two_yr_ago,
            )
            .scalar()
        ) or 0.0

        if recent_value == 0 and prior_value == 0:
            # Check if supplier has any active contracts (regardless of award date)
            active_count = self.session.query(SupplierContract).filter(
                SupplierContract.supplier_id == supplier.id,
                SupplierContract.status == ContractStatus.ACTIVE,
            ).count()
            if active_count > 0:
                return 30.0, f"{active_count} active contract(s) in progress — awarded before lookback window but still delivering"
            return 90.0, "No contract activity in 4 years — supplier may be dormant"

        if recent_value == 0:
            # Check if supplier has active contracts still delivering
            active_count = self.session.query(SupplierContract).filter(
                SupplierContract.supplier_id == supplier.id,
                SupplierContract.status == ContractStatus.ACTIVE,
            ).count()
            if active_count > 0:
                return 30.0, f"No new awards in 2yr but {active_count} active contract(s) still delivering (CAD {prior_value/1e6:.0f}M awarded previously)"
            return 90.0, f"No recent contracts (prior 2yr: CAD {prior_value/1e6:.1f}M) — activity has ceased"

        if prior_value == 0:
            return 20.0, f"New supplier with CAD {recent_value/1e6:.1f}M in recent contracts — no prior baseline"

        ratio = recent_value / prior_value

        if ratio >= 0.85:
            return 20.0, f"Stable/growing contract activity (recent {recent_value/1e6:.1f}M vs prior {prior_value/1e6:.1f}M CAD)"
        if ratio >= 0.50:
            return 50.0, f"Moderate decline in contract activity ({ratio:.0%} of prior period)"
        if ratio >= 0.25:
            return 70.0, f"Significant decline in contract activity ({ratio:.0%} of prior period)"
        return 80.0, f"Severe decline in contract activity ({ratio:.0%} of prior period) — potential exit risk"

    # --- Dimension 5: Sanctions Proximity (10%) ---

    def score_sanctions_proximity(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on ownership ties to sanctioned countries and material dependencies."""
        country = supplier.parent_country

        # Check PSI material dependencies from sanctioned sources
        from src.storage.models import SupplyChainMaterial
        material_risk = False
        try:
            sanctioned_materials = self.session.query(SupplyChainMaterial).filter(
                SupplyChainMaterial.top_producers.ilike('%Russia%') |
                SupplyChainMaterial.top_producers.ilike('%China%') |
                SupplyChainMaterial.top_producers.ilike('%Iran%')
            ).count()
            if sanctioned_materials > 0:
                material_risk = True
        except Exception:
            pass

        if country and country in EMBARGOED_COUNTRIES:
            return 90.0, f"Parent country {country} is fully embargoed"

        PARTIAL_SANCTIONS = {"China", "Turkey", "India"}
        if country and country in PARTIAL_SANCTIONS:
            return 40.0, f"Parent country {country} has partial sanctions/restrictions"

        if material_risk:
            return 70.0, "Depends on materials sourced from sanctioned countries (PSI cross-reference)"

        if not country:
            return 0.0, "No foreign ownership — no sanctions exposure"
        return 0.0, f"Parent country {country} is not sanctioned"

    # --- Dimension 6: Contract Performance (15%) ---

    def score_contract_performance(self, supplier: DefenceSupplier) -> tuple[float, str]:
        """Score based on terminated contract ratio.

        Returns:
            (score 0-100, rationale string)
        """
        total = (
            self.session.query(func.count(SupplierContract.id))
            .filter(SupplierContract.supplier_id == supplier.id)
            .scalar()
        ) or 0

        if total == 0:
            return 50.0, "No contract history — performance cannot be assessed"

        terminated = (
            self.session.query(func.count(SupplierContract.id))
            .filter(
                SupplierContract.supplier_id == supplier.id,
                SupplierContract.status == ContractStatus.TERMINATED,
            )
            .scalar()
        ) or 0

        ratio = terminated / total

        if ratio == 0:
            return 10.0, f"No terminated contracts out of {total} — excellent performance record"
        if ratio < 0.10:
            return 30.0, f"{terminated}/{total} contracts terminated ({ratio:.0%}) — minor performance issues"
        if ratio < 0.25:
            return 60.0, f"{terminated}/{total} contracts terminated ({ratio:.0%}) — notable performance concerns"
        return 85.0, f"{terminated}/{total} contracts terminated ({ratio:.0%}) — serious performance record"

    # --- Composite Scorer ---

    def score_supplier(self, supplier: DefenceSupplier) -> float:
        """Compute all 6 dimension scores, persist them, update composite.

        Returns:
            Composite weighted score 0-100.
        """
        dimension_methods = {
            RiskDimension.FOREIGN_OWNERSHIP: self.score_foreign_ownership,
            RiskDimension.CUSTOMER_CONCENTRATION: self.score_customer_concentration,
            RiskDimension.SINGLE_SOURCE: self.score_single_source,
            RiskDimension.CONTRACT_ACTIVITY: self.score_contract_activity,
            RiskDimension.SANCTIONS_PROXIMITY: self.score_sanctions_proximity,
            RiskDimension.CONTRACT_PERFORMANCE: self.score_contract_performance,
        }

        composite = 0.0
        now = datetime.utcnow()

        for dimension, method in dimension_methods.items():
            score, rationale = method(supplier)
            weight = WEIGHTS[dimension]
            composite += score * weight

            # Upsert the dimension score
            existing = (
                self.session.query(SupplierRiskScore)
                .filter_by(supplier_id=supplier.id, dimension=dimension)
                .first()
            )
            if existing:
                existing.score = score
                existing.rationale = rationale
                existing.scored_at = now
            else:
                row = SupplierRiskScore(
                    supplier_id=supplier.id,
                    dimension=dimension,
                    score=score,
                    rationale=rationale,
                    scored_at=now,
                )
                self.session.add(row)

        composite = round(min(max(composite, 0.0), 100.0), 2)
        supplier.risk_score_composite = composite
        self.session.commit()

        logger.info(
            "Scored supplier %s: composite=%.1f",
            supplier.name,
            composite,
        )
        return composite

    def score_all_suppliers(self) -> dict[str, float]:
        """Score every supplier in the database.

        Returns:
            Mapping of supplier name -> composite score.
        """
        suppliers = self.session.query(DefenceSupplier).all()
        results: dict[str, float] = {}
        for supplier in suppliers:
            try:
                results[supplier.name] = self.score_supplier(supplier)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to score supplier %s: %s", supplier.name, exc)
        return results
