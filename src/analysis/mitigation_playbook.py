"""Mitigation Playbook — Rule-based COA recommendations for detected risks.

Maps risk patterns to deterministic Course of Action recommendations.
Addresses DND Q13: Decision Support & Mitigation Capabilities.
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from src.storage.models import (
    MitigationAction, SupplierRiskScore, RiskTaxonomyScore,
    SupplyChainAlert, DefenceSupplier, RiskDimension,
)

logger = logging.getLogger(__name__)

# Priority map for sorting
PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# ── Playbook: (risk_source, dimension_pattern) → COA template ──
# Each entry: action text, timeline, responsible party
PLAYBOOK: dict[tuple[str, str], dict] = {
    # Supplier risks
    ("supplier", "foreign_ownership"): {
        "action": "Initiate National Security Review; suspend new PO issuance pending FOCI assessment",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("supplier", "customer_concentration"): {
        "action": "Engage supplier on revenue diversification plan; assess business continuity risk",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("supplier", "single_source"): {
        "action": "Qualify alternate supplier; estimated qualification time: 90 days. Initiate dual-source program",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("supplier", "contract_activity"): {
        "action": "Engage supplier for business continuity review; activate safety stock if available",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("supplier", "sanctions_proximity"): {
        "action": "Conduct sanctions compliance audit; review sub-tier material sourcing for restricted origins",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("supplier", "contract_performance"): {
        "action": "Issue corrective action request (CAR); increase inspection frequency; review contract terms",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    # Taxonomy — FOCI (category 1)
    ("taxonomy", "1a"): {"action": "Investigate IP litigation; assess trade secret exposure for DND programs", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "1b"): {"action": "Request supplier cyber posture assessment; brief CCCS on threat activity", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1c"): {"action": "Initiate UBO (Ultimate Beneficial Ownership) review; flag for FOCI assessment", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "1d"): {"action": "Monitor M&A activity; prepare FOCI impact assessment if acquisition proceeds", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1e"): {"action": "Investigate shell company structure; escalate to CI if confirmed", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "1h"): {"action": "Trace material provenance to origin; verify no sanctioned-country sourcing", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "1k"): {"action": "Escalate to Canadian Intelligence Command; initiate enhanced screening", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Political (category 2)
    ("taxonomy", "2b"): {"action": "Assess impact on logistics corridors; identify alternate trade routes", "timeline": "30 days", "responsible": "DSCRO"},
    ("taxonomy", "2c"): {"action": "Activate conflict supply chain contingency; assess inventory buffer adequacy", "timeline": "Immediate", "responsible": "DSCRO"},
    ("taxonomy", "2d"): {"action": "Monitor tariff developments; model cost impact on active contracts", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "2e"): {"action": "Cross-reference updated sanctions list; flag affected suppliers and routes", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Manufacturing (category 3)
    ("taxonomy", "3a"): {"action": "Initiate dual-source qualification program; document sole-source justification", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3b"): {"action": "Purchase safety stock from secondary supplier; monitor commodity market", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "3d"): {"action": "Map geographic concentration; identify alternative regions for sourcing", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3f"): {"action": "Qualify alternate supplier; estimated qualification time: 90 days", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "3j"): {"action": "Initiate DMSMS review; identify form-fit-function replacements", "timeline": "90 days", "responsible": "Program Office"},
    ("taxonomy", "3l"): {"action": "Review production schedules with supplier; assess impact on delivery milestones", "timeline": "30 days", "responsible": "Program Office"},
    ("taxonomy", "3p"): {"action": "Trace raw material sources; ensure no sanctioned-origin materials in supply chain", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "3s"): {"action": "Pre-order critical components; negotiate priority allocation with supplier", "timeline": "Immediate", "responsible": "Procurement"},
    # Taxonomy — Cyber (category 4)
    ("taxonomy", "4a"): {"action": "Request supplier network security assessment; review data handling procedures", "timeline": "30 days", "responsible": "Security"},
    ("taxonomy", "4c"): {"action": "Brief CCCS on intrusion indicators; assess data exposure scope", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4e"): {"action": "Request incident report from supplier; assess DND data exposure; review contract terms", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4f"): {"action": "Activate cyber incident response plan; assess operational impact", "timeline": "Immediate", "responsible": "Security"},
    ("taxonomy", "4j"): {"action": "Assess CVE applicability to DND systems; coordinate patch deployment", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Transport (category 7)
    ("taxonomy", "7a"): {"action": "Activate alternate shipping route; pre-position safety stock at secondary depot", "timeline": "Immediate", "responsible": "DSCRO"},
    ("taxonomy", "7c"): {"action": "Issue delivery performance improvement notice; escalate if no improvement in 30 days", "timeline": "30 days", "responsible": "Program Office"},
    # Taxonomy — Compliance (category 10)
    ("taxonomy", "10h"): {"action": "Initiate conflict mineral trace; verify 3TG (tin, tantalum, tungsten, gold) sourcing", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "10j"): {"action": "Review export control classification; ensure ITAR/EAR compliance", "timeline": "Immediate", "responsible": "Security"},
    # Taxonomy — Financial (category 12)
    ("taxonomy", "12b"): {"action": "Purchase safety stock from secondary supplier to cover 6-month gap; monitor Z-Score", "timeline": "30 days", "responsible": "Procurement"},
    ("taxonomy", "12d"): {"action": "Assess supplier revenue concentration; develop business continuity plan", "timeline": "90 days", "responsible": "Procurement"},
    ("taxonomy", "12e"): {"action": "Review cost baseline; negotiate revised contract terms if overrun exceeds 10%", "timeline": "30 days", "responsible": "Program Office"},
    # PSI alerts
    ("psi", "chokepoint_blocked"): {"action": "Divert shipments to alternate port; assess transit time impact", "timeline": "Immediate", "responsible": "DSCRO"},
    ("psi", "material_shortage"): {"action": "Purchase safety stock from secondary supplier to cover 6-month gap", "timeline": "30 days", "responsible": "Procurement"},
    ("psi", "sanctions_risk"): {"action": "Initiate supply chain re-sourcing; flag affected NSNs for review", "timeline": "Immediate", "responsible": "Security"},
    ("psi", "concentration_risk"): {"action": "Identify alternate sources across different geographies; begin qualification", "timeline": "90 days", "responsible": "Procurement"},
    ("psi", "supplier_disruption"): {"action": "Activate business continuity plan; contact secondary suppliers", "timeline": "Immediate", "responsible": "DSCRO"},
    ("psi", "demand_surge"): {"action": "Negotiate priority allocation with suppliers; assess production capacity", "timeline": "30 days", "responsible": "Procurement"},
}


def _compute_priority(score: float) -> str:
    if score >= 85: return "critical"
    if score >= 70: return "high"
    if score >= 50: return "medium"
    return "low"


class MitigationPlaybook:
    """Generates COA recommendations from risk scores using the playbook."""

    def __init__(self, session: Session):
        self.session = session

    def _upsert_action(self, risk_source: str, risk_entity: str, risk_dimension: str,
                        risk_score: float, coa: dict, priority: str) -> bool:
        """Upsert a single COA. Returns True if new/updated, False if skipped."""
        existing = self.session.query(MitigationAction).filter_by(
            risk_source=risk_source,
            risk_entity=risk_entity,
            risk_dimension=risk_dimension,
        ).filter(MitigationAction.status != "resolved").first()

        if existing:
            existing.risk_score = risk_score
            existing.coa_action = coa["action"]
            existing.coa_priority = priority
            existing.coa_timeline = coa.get("timeline")
            existing.coa_responsible = coa.get("responsible")
            existing.updated_at = datetime.utcnow()
            return True
        else:
            self.session.add(MitigationAction(
                risk_source=risk_source,
                risk_entity=risk_entity,
                risk_dimension=risk_dimension,
                risk_score=risk_score,
                coa_action=coa["action"],
                coa_priority=priority,
                coa_timeline=coa.get("timeline"),
                coa_responsible=coa.get("responsible"),
                status="open",
            ))
            return True

    def generate_all_coas(self) -> dict:
        """Generate COAs from all risk sources. Returns counts."""
        generated = 0
        updated = 0
        skipped = 0

        # 1. Supplier risk scores
        supplier_risks = self.session.query(SupplierRiskScore).filter(
            SupplierRiskScore.score > 50,
        ).all()
        for rs in supplier_risks:
            supplier = self.session.get(DefenceSupplier, rs.supplier_id)
            if not supplier:
                continue
            dim_value = rs.dimension.value  # Convert SQLEnum to string
            key = ("supplier", dim_value)
            coa = PLAYBOOK.get(key)
            if not coa and rs.score > 70:
                coa = {"action": f"Review {dim_value.replace('_', ' ')} risk for {supplier.name}; determine appropriate mitigation", "timeline": "30 days", "responsible": "DSCRO"}
            if coa:
                priority = _compute_priority(rs.score)
                is_new = self._upsert_action("supplier", supplier.name, dim_value, rs.score, coa, priority)
                if is_new:
                    generated += 1

        # 2. Taxonomy scores
        taxonomy_risks = self.session.query(RiskTaxonomyScore).filter(
            RiskTaxonomyScore.score > 50,
        ).all()
        for ts in taxonomy_risks:
            key = ("taxonomy", ts.subcategory_key)
            coa = PLAYBOOK.get(key)
            if not coa and ts.score > 70:
                coa = {"action": f"Review {ts.subcategory_name} risk; determine appropriate mitigation", "timeline": "30 days", "responsible": "DSCRO"}
            if coa:
                priority = _compute_priority(ts.score)
                entity = f"[{ts.subcategory_key}] {ts.subcategory_name}"
                is_new = self._upsert_action("taxonomy", entity, ts.subcategory_key, ts.score, coa, priority)
                if is_new:
                    generated += 1

        # 3. PSI alerts
        psi_alerts = self.session.query(SupplyChainAlert).filter(
            SupplyChainAlert.is_active == True,
        ).all()
        for alert in psi_alerts:
            alert_type = alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(alert.alert_type)
            key = ("psi", alert_type)
            coa = PLAYBOOK.get(key)
            if not coa:
                coa = {"action": f"Assess impact of {alert_type.replace('_', ' ')}; coordinate response", "timeline": "30 days", "responsible": "DSCRO"}
            severity_score = {"critical": 95, "high": 80, "medium": 60, "low": 40}.get(str(alert.severity), 60)
            priority = _compute_priority(severity_score)
            is_new = self._upsert_action("psi", alert.title or alert_type, alert_type, severity_score, coa, priority)
            if is_new:
                generated += 1

        self.session.commit()
        logger.info("COA generation: %d generated/updated, %d skipped", generated, skipped)
        return {"generated": generated, "updated": updated, "skipped_resolved": skipped}
