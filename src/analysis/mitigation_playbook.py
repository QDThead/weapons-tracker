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
# 150+ entries covering all 13 DND Annex B risk categories
PLAYBOOK: dict[tuple[str, str], dict] = {

    # ═══════════════════════════════════════════════════════════════════
    # SUPPLIER RISKS (6 dimensions from SupplierRiskScore model)
    # ═══════════════════════════════════════════════════════════════════
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

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 1: Foreign Ownership, Control, or Influence (FOCI)
    # 15 sub-categories: 1a–1o
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "1a"): {
        "action": "Investigate IP litigation; assess trade secret exposure for DND programs; engage legal to evaluate injunction risk",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1b"): {
        "action": "Request supplier cyber posture assessment; brief CCCS on threat activity; mandate network segmentation for classified work",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "1c"): {
        "action": "Initiate UBO (Ultimate Beneficial Ownership) review; flag for FOCI assessment; verify beneficial ownership through Wikidata and corporate registry cross-reference",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1d"): {
        "action": "Monitor M&A activity; prepare FOCI impact assessment if acquisition proceeds; mandate CFIUS-equivalent review for acquisitions of Tier-1 suppliers by foreign entities",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "1e"): {
        "action": "Investigate shell company structure; escalate to CI if confirmed; cross-reference Panama/Pandora papers and ICIJ offshore leaks database",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "1f"): {
        "action": "Map state-owned enterprise relationships in supplier ownership chain; assess whether SOE influence reaches management or board level; require enhanced reporting obligations",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1g"): {
        "action": "Deploy anomaly detection on supplier production metrics; review physical security protocols at supplier facilities; conduct unannounced quality audits",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "1h"): {
        "action": "Trace material provenance to origin; verify no sanctioned-country sourcing; require blockchain-based chain-of-custody documentation for critical materials",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "1i"): {
        "action": "Screen supplier workforce for adversary intelligence service connections; implement information compartmentalization on sensitive programs; conduct background checks on key personnel with access to CUI",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1j"): {
        "action": "Monitor key personnel departures at defence suppliers; enforce non-compete and IP assignment clauses; require 90-day departure notification for cleared personnel",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1k"): {
        "action": "Escalate to Canadian Intelligence Command; initiate enhanced screening; restrict supplier access to classified programs pending investigation",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "1l"): {
        "action": "Conduct CI threat assessment on supplier base; coordinate with allied Five Eyes CI agencies for shared threat indicators; restrict data access for flagged suppliers",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1m"): {
        "action": "Monitor political risk indicators in supplier-host countries for expropriation or forced nationalization; develop contingency sourcing plan for affected materials; purchase political risk insurance",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "1n"): {
        "action": "Review CI collection activity indicators across supplier regions; enhance OPSEC protocols for supplier communications; implement secure collaboration tools for sensitive program data",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "1o"): {
        "action": "Aggregate CI risk indicators into composite FOCI score; brief ADM(Mat) on overall FOCI exposure; update risk register with recommended mitigations for each flagged supplier",
        "timeline": "30 days",
        "responsible": "Security",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 2: Political & Regulatory
    # 6 sub-categories: 2a–2f
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "2a"): {
        "action": "Cross-reference supplier locations against Global Terrorism Index; screen sub-tier suppliers in high-risk regions; require enhanced due diligence for contracts in conflict zones",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "2b"): {
        "action": "Assess impact on logistics corridors; identify alternate trade routes; pre-position critical stocks at CFB Trenton and CFB Edmonton to reduce transit dependency",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "2c"): {
        "action": "Activate conflict supply chain contingency; assess inventory buffer adequacy; accelerate delivery of in-production orders from conflict-adjacent suppliers",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "2d"): {
        "action": "Monitor tariff developments; model cost impact on active contracts; invoke price adjustment clauses where applicable; brief PSPC on potential budget implications",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "2e"): {
        "action": "Cross-reference updated sanctions list; flag affected suppliers and routes; issue stop-ship orders for any in-transit goods involving sanctioned entities",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "2f"): {
        "action": "Monitor election cycles and government transitions in key supplier nations; assess policy continuity risk for defence cooperation agreements; prepare fallback suppliers for politically sensitive corridors",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    # Additional Political & Regulatory COAs (keyed by category-level triggers)
    ("taxonomy", "2_export_controls"): {
        "action": "Review ITAR/EAR exposure across supplier base; ensure all suppliers have valid export licences; prepare waiver requests for critical items",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "2_regulatory_change"): {
        "action": "Track pending regulatory changes in key jurisdictions (US DFARS, EU Dual-Use Regulation, Canadian EIPA); model compliance cost impact; update contract language proactively",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "2_allied_policy"): {
        "action": "Monitor NATO and Five Eyes procurement policy alignment; identify interoperability risks from divergent national standards; brief DGMPD on policy gaps",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "2_treaty_change"): {
        "action": "Assess impact of Arms Trade Treaty (ATT) compliance changes on current procurement pipelines; verify end-user certificates are current for all active transfers",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "2_embargo_shift"): {
        "action": "Model supply chain impact of potential new embargoes on countries adjacent to current suppliers; identify alternative source countries for affected commodities",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "2_sovereignty"): {
        "action": "Evaluate Canadian Industrial and Technological Benefits (ITB) obligations; ensure sovereign capability retention for critical defence technologies; flag offsets at risk",
        "timeline": "90 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 3: Manufacturing & Supply
    # 20 sub-categories: 3a–3t
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "3a"): {
        "action": "Initiate dual-source qualification program; document sole-source justification per PSPC policy; establish qualification schedule with milestone gates",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3b"): {
        "action": "Purchase safety stock from secondary supplier; monitor commodity market; engage USGS and NRCan for critical mineral supply forecasts",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3c"): {
        "action": "Conduct industrial capacity assessment at Tier-1 suppliers; model surge production requirements against available capacity; negotiate capacity reservation agreements for wartime surge",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3d"): {
        "action": "Map geographic concentration using HHI index; identify alternative regions for sourcing; require suppliers to disclose sub-tier facility locations",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3e"): {
        "action": "Review supplier R&D investment trends; assess Technology Readiness Level (TRL) gaps; engage IDEaS program for alternative technology development",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3f"): {
        "action": "Qualify alternate supplier; estimated qualification time: 90 days; require suppliers to maintain warm production lines for critical items",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3g"): {
        "action": "Review reclamation and repair-and-overhaul (R&O) programs; increase utilization rates for repairable items; establish cannibalization protocols for non-operational platforms",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3h"): {
        "action": "Audit intermediary/reseller relationships in supply chain; verify authorized distributor status; eliminate unnecessary middlemen adding cost and lead time",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3i"): {
        "action": "Review supplier equipment maintenance schedules and downtime history; require preventive maintenance reporting; negotiate equipment uptime SLAs in contracts",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3j"): {
        "action": "Initiate DMSMS review; identify form-fit-function replacements; submit obsolescence case to DMSMS working group; fund bridge buys for end-of-life components",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3k"): {
        "action": "Run network adjacency analysis to identify suppliers whose failure cascades to multiple programs; prioritize risk mitigation for high-adjacency nodes; build buffer stock at cascade chokepoints",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "3l"): {
        "action": "Review production schedules with supplier; assess impact on delivery milestones; invoke liquidated damages clauses if delays exceed contractual thresholds",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3m"): {
        "action": "Conduct safety stock analysis for critical spares; increase reorder points for items below threshold; pre-position spares at forward operating bases and CFB supply depots",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "3n"): {
        "action": "Map outsourced production tiers; verify outsourced facilities meet DND quality and security requirements; require prior approval for further sub-contracting of classified components",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3o"): {
        "action": "Review order fulfillment rates; implement vendor-managed inventory (VMI) for high-velocity items; establish performance improvement targets with penalty/incentive structure",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3p"): {
        "action": "Trace raw material sources; ensure no sanctioned-origin materials in supply chain; require Certificates of Origin for all critical raw material shipments",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "3q"): {
        "action": "Model inventory holding costs vs. stockout risk; negotiate consignment stock agreements with key suppliers; expand warehouse capacity at Montreal and Halifax distribution nodes",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "3r"): {
        "action": "Assess Canadian industrial capability gaps for defence-critical manufacturing; brief ADM(Mat) on sovereign production capacity shortfalls; recommend IDEaS investments to close gaps",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "3s"): {
        "action": "Pre-order critical components; negotiate priority allocation with supplier; establish long-term agreements (LTAs) to lock in lead times and pricing for strategic items",
        "timeline": "Immediate",
        "responsible": "Procurement",
    },
    ("taxonomy", "3t"): {
        "action": "Monitor agricultural commodity markets for ration and textile supply inputs; diversify sourcing for military food supply and natural fibre uniforms; maintain 180-day strategic reserve",
        "timeline": "90 days",
        "responsible": "Procurement",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 4: Technology & Cybersecurity
    # 10 sub-categories: 4a–4j
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "4a"): {
        "action": "Request supplier network security assessment; review data handling procedures; require CMMC Level 2 certification for all DIB suppliers handling CUI",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "4b"): {
        "action": "Investigate OPSEC/INFOSEC violation; conduct damage assessment; mandate security awareness retraining for supplier staff; restrict supplier facility access pending remediation",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "4c"): {
        "action": "Brief CCCS on intrusion indicators; assess data exposure scope; conduct forensic analysis of compromised systems; issue threat advisory to all suppliers in same program",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "4d"): {
        "action": "Assess operational impact of supplier IT system failure; activate manual fallback procedures; require supplier IT disaster recovery plan review within 30 days",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "4e"): {
        "action": "Request incident report from supplier; assess DND data exposure; review contract data protection clauses; notify Privacy Commissioner if PII involved",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "4f"): {
        "action": "Activate cyber incident response plan; assess operational impact; coordinate with CCCS for threat containment; issue supplier-wide advisory for indicators of compromise",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "4g"): {
        "action": "Conduct damage assessment for DCI/PII exposure; initiate breach notification protocol per Privacy Act; mandate encryption-at-rest for all DND data at supplier facilities",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "4h"): {
        "action": "Inventory supplier IT systems at end-of-life; require technology refresh plan for legacy systems; assess risk of running unsupported software on DND-connected networks",
        "timeline": "90 days",
        "responsible": "Security",
    },
    ("taxonomy", "4i"): {
        "action": "Review supplier IT redundancy and failover architecture; require minimum 99.5% uptime SLA for critical supply chain IT systems; assess impact of cloud provider outages on order processing",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "4j"): {
        "action": "Assess CVE applicability to DND systems; coordinate patch deployment within 72 hours for critical vulnerabilities; mandate vulnerability disclosure agreements with all software suppliers",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    # Additional Cyber COAs
    ("taxonomy", "4_supply_chain_attack"): {
        "action": "Implement software bill of materials (SBOM) requirements for all supplied software; verify code signing integrity; mandate third-party penetration testing annually",
        "timeline": "90 days",
        "responsible": "Security",
    },
    ("taxonomy", "4_insider_cyber"): {
        "action": "Require supplier implementation of privileged access management (PAM); enforce principle of least privilege on all DND program systems; monitor for anomalous data exfiltration patterns",
        "timeline": "30 days",
        "responsible": "Security",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 5: Infrastructure
    # 6 sub-categories: 5a–5f
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "5a"): {
        "action": "Assess rail, road, and waterway disruptions affecting supply corridors; identify alternate modal transport options; pre-contract with secondary carriers for surge capacity",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "5b"): {
        "action": "Verify backup power and water supply at critical supplier facilities; require UPS and generator redundancy for production-critical operations; assess municipal utility reliability",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "5c"): {
        "action": "Conduct physical security audit of supplier facilities handling classified materiel; verify compliance with PBMM and ITSG-33 standards; require security guard force certification",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "5d"): {
        "action": "Review supplier critical equipment maintenance logs and failure history; require preventive maintenance programs; negotiate equipment replacement timelines for aging production machinery",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "5e"): {
        "action": "Monitor energy supply security in supplier regions; assess impact of energy price spikes on production costs; require suppliers to develop energy contingency plans including on-site generation",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "5f"): {
        "action": "Review supplier facility condition assessments; flag facilities below acceptable condition index; require capital investment plans for buildings housing DND production lines",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    # Additional Infrastructure COAs
    ("taxonomy", "5_port_capacity"): {
        "action": "Assess port infrastructure capacity at key entry points (Halifax, Esquimalt, Montreal); negotiate priority berthing agreements for military cargo; evaluate inland port alternatives",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "5_arctic_infra"): {
        "action": "Evaluate infrastructure gaps for Arctic resupply operations; assess Nanisivik Naval Facility readiness; plan seasonal pre-positioning of critical materiel at northern depots",
        "timeline": "180 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "5_telecom"): {
        "action": "Verify telecommunications redundancy at supplier facilities; require dual-path internet connectivity; assess satellite communication backup for remote manufacturing sites",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "5_flood_seismic"): {
        "action": "Map supplier facilities against flood plain and seismic zone data; require business continuity plans for facilities in high-hazard zones; verify adequate insurance coverage",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "5_shared_facility"): {
        "action": "Identify suppliers sharing facilities with non-cleared tenants; assess co-location security risks; require physical separation of DND production areas from commercial operations",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "5_warehouse"): {
        "action": "Audit warehouse and storage conditions for DND materiel; verify climate control, humidity, and ESD protection meet MILSPEC requirements; flag non-compliant storage facilities",
        "timeline": "30 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 6: Planning
    # 4 sub-categories: 6a–6d
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "6a"): {
        "action": "Recalibrate demand forecasting models using latest operational tempo data; incorporate NATO rearmament demand signals; reconcile forecast accuracy against 85% target threshold",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "6b"): {
        "action": "Recalculate safety stock levels for critical NSNs using updated lead times; increase reorder points for items below minimum threshold; fund bridge buys to close immediate gaps",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "6c"): {
        "action": "Conduct demand-supply alignment review with DGMPD; synchronize procurement timelines with program delivery milestones; establish monthly S&OP (Sales and Operations Planning) cadence",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "6d"): {
        "action": "Update supply chain constraint models with current lead times, capacity limits, and transportation bottlenecks; integrate constraint data into procurement planning tools",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    # Additional Planning COAs
    ("taxonomy", "6_scenario_planning"): {
        "action": "Develop 3-tier demand scenarios (peacetime, escalation, conflict) for all critical items; validate safety stock levels against each scenario; brief VCDS on readiness gaps",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "6_lead_time_drift"): {
        "action": "Track supplier lead time trends over 12-month window; flag items where lead times have increased >20%; update planning parameters in D/MASIS and DRMIS systems",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "6_lifecycle_planning"): {
        "action": "Review platform lifecycle sustainment plans; ensure in-service support contracts align with remaining service life; identify upcoming obsolescence cliffs requiring advance procurement",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "6_contingency_stock"): {
        "action": "Establish contingency stock levels for NATO Article 5 scenarios; pre-position war reserve materiel at designated locations; coordinate with allied logistics agencies",
        "timeline": "180 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "6_procurement_pipeline"): {
        "action": "Map procurement pipeline against program milestones; identify contracts at risk of lapse or expiry; initiate renewal processes 12 months ahead of expiry to avoid coverage gaps",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "6_demand_signal"): {
        "action": "Integrate operational demand signals from deployed CAF units into procurement planning; reduce forecast-to-order lag for high-consumption items (ammunition, POL, rations)",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "6_capacity_reservation"): {
        "action": "Negotiate industrial capacity reservation agreements with key domestic manufacturers; ensure surge production capability for critical munitions and spare parts",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "6_data_quality"): {
        "action": "Audit supply chain planning data quality in DRMIS; reconcile inventory records with physical counts; correct discrepancies affecting demand forecast accuracy",
        "timeline": "30 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 7: Transportation & Distribution
    # 7 sub-categories: 7a–7g
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "7a"): {
        "action": "Activate alternate shipping route; pre-position safety stock at secondary depot; pre-position critical spares at CFB Trenton and CFB Edmonton to reduce transit dependency",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7b"): {
        "action": "Implement advanced shipping notice (ASN) requirements with all Tier-1 suppliers; deploy shipment tracking for high-value consignments; issue corrective action for accuracy below 95%",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "7c"): {
        "action": "Issue delivery performance improvement notice; escalate if no improvement in 30 days; invoke liquidated damages clause for chronic late deliveries; assess alternative carriers",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "7d"): {
        "action": "Review transport accident reports; assess cargo damage and loss; file insurance claims; update risk assessment for affected route segments; consider armed escort for high-value military cargo",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7e"): {
        "action": "Assess logistics surge capacity for rapid deployment scenarios; negotiate standby transport agreements with commercial carriers; validate RCAF strategic airlift availability for priority items",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7f"): {
        "action": "Investigate cargo loss incident; file claim with carrier; assess whether item requires expedited replacement; review packaging and handling specifications for fragile military items",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7g"): {
        "action": "Monitor trade policy changes affecting container availability and port dwell times; assess customs clearance delays; engage CBSA for priority processing of defence cargo",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    # Additional Transport COAs
    ("taxonomy", "7_cold_chain"): {
        "action": "Verify cold chain integrity for temperature-sensitive materiel (pharmaceuticals, energetics, adhesives); audit carrier compliance with MIL-STD-2073 packaging requirements",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "7_hazmat_transport"): {
        "action": "Review HAZMAT transport compliance for ammunition, propellants, and chemical agents; verify carrier TDG certifications; update emergency response plans for transport corridors",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "7_arctic_resupply"): {
        "action": "Plan seasonal Arctic resupply window (Jul-Oct); coordinate with CCGS icebreaker schedule; pre-stage materiel at Iqaluit and Resolute Bay for northern operations",
        "timeline": "180 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7_modal_shift"): {
        "action": "Evaluate rail-to-truck modal shift options for disrupted corridors; negotiate intermodal agreements with CN/CP Rail and major trucking carriers; assess cost and time trade-offs",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "7_customs_delay"): {
        "action": "Engage CBSA for expedited customs clearance of defence-critical imports; obtain standing ITAR import permits; establish bonded warehouse capacity at key ports of entry",
        "timeline": "30 days",
        "responsible": "Procurement",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 8: Human Capital
    # 5 sub-categories: 8a–8e
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "8a"): {
        "action": "Assess skilled trades vacancy rates at critical suppliers; support supplier workforce development through co-op and apprenticeship programs; coordinate with provincial training institutions for defence manufacturing skills",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "8b"): {
        "action": "Activate work stoppage contingency plan; assess inventory buffer adequacy; engage FMCS for mediation; identify emergency alternate production capacity",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "8c"): {
        "action": "Monitor mass layoff announcements at defence suppliers; assess impact on DND program delivery; engage supplier executive on knowledge retention plan; consider contract acceleration to preserve workforce",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "8d"): {
        "action": "Monitor labour dispute negotiations; assess risk of escalation to work stoppage; build inventory buffer for items from affected supplier; identify backup production facilities",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "8e"): {
        "action": "Monitor boycott campaigns targeting DND suppliers; assess reputational and operational impact; prepare public affairs response; identify alternative suppliers if boycott affects production",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    # Additional Human Capital COAs
    ("taxonomy", "8_security_clearance"): {
        "action": "Track security clearance backlogs at supplier facilities; expedite Personnel Security Screening (PSS) for critical program staff; coordinate with PSPC for priority processing",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "8_key_person"): {
        "action": "Identify key-person dependencies at critical suppliers; require succession planning and knowledge transfer documentation; negotiate key-person retention incentives in contract terms",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "8_demographic"): {
        "action": "Assess supplier workforce age demographics for retirement cliff risks; identify programs dependent on niche expertise; fund knowledge capture initiatives for retiring specialists",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "8_training_gap"): {
        "action": "Identify supplier training gaps for new platform technologies (e.g., additive manufacturing, composite materials); fund targeted training through ITB offset mechanisms",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "8_foreign_worker"): {
        "action": "Assess supplier reliance on temporary foreign worker programs; evaluate immigration policy risks to workforce stability; require workforce contingency plans for LMIA-dependent suppliers",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "8_wage_pressure"): {
        "action": "Monitor wage inflation in defence manufacturing sectors; model contract cost escalation impact; invoke economic price adjustment (EPA) clauses where applicable",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "8_knowledge_transfer"): {
        "action": "Require formal knowledge transfer plans when supplier personnel changes affect DND programs; mandate documentation of tribal knowledge for critical maintenance procedures",
        "timeline": "90 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 9: Environmental
    # 7 sub-categories: 9a–9g
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "9a"): {
        "action": "Map supplier facilities against natural disaster risk zones (earthquake, tsunami, flood); verify business continuity and disaster recovery plans; require annual BCP testing",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "9b"): {
        "action": "Monitor extreme weather forecasts for supplier regions; activate pre-storm inventory pull-forward for threatened facilities; verify supplier storm preparedness protocols",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "9c"): {
        "action": "Integrate long-term climate projections into supply chain planning; assess rising sea level impact on coastal supplier facilities and ports; identify suppliers requiring climate adaptation investment",
        "timeline": "180 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "9d"): {
        "action": "Monitor wildfire risk levels at supplier facilities in BC, Alberta, and Ontario; activate inventory pre-positioning from threatened facilities; coordinate with provincial emergency management",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("taxonomy", "9e"): {
        "action": "Review supplier pandemic preparedness plans; verify remote work capability for non-production staff; assess impact of potential workforce absenteeism on production schedules; maintain PPE stockpile",
        "timeline": "90 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "9f"): {
        "action": "Review man-made disaster risk at supplier facilities (industrial accidents, explosions, structural failures); verify supplier emergency response plans; require annual emergency drill reporting",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "9g"): {
        "action": "Review CBRN incident response plans for suppliers handling hazardous materials; verify compliance with CEPA and TDG regulations; coordinate with local HAZMAT response teams",
        "timeline": "30 days",
        "responsible": "Security",
    },
    # Additional Environmental COAs
    ("taxonomy", "9_esg_compliance"): {
        "action": "Assess supplier ESG compliance against DND Greening Defence requirements; verify carbon reporting and reduction targets; flag suppliers non-compliant with Federal Sustainable Development Strategy",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "9_water_scarcity"): {
        "action": "Identify suppliers in water-stressed regions (semiconductor fabs, chemical processors); assess water availability risk to production continuity; require water conservation plans",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "9_contamination"): {
        "action": "Screen supplier sites for legacy contamination (PFAS, heavy metals); assess remediation liability; verify environmental compliance certificates are current; flag sites under regulatory order",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "9_permafrost"): {
        "action": "Assess infrastructure stability at northern facilities affected by permafrost thaw; review structural integrity of runways, roads, and storage at Arctic supply nodes; plan engineering remediation",
        "timeline": "180 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "9_emissions_regulation"): {
        "action": "Monitor carbon pricing and emissions regulation impact on supplier operating costs; model cost pass-through to DND contracts; assess transition risk for energy-intensive suppliers",
        "timeline": "90 days",
        "responsible": "Procurement",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 10: Compliance
    # 16 sub-categories: 10a–10p
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "10a"): {
        "action": "Implement insider threat detection program at suppliers handling classified materiel; require personnel monitoring for individuals with access to sensitive programs; coordinate with CF CI Group",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "10b"): {
        "action": "Screen supplier sub-tier supply chains against forced labour indicators using ILO and US DOL watchlists; require supplier attestation under Canada's Fighting Against Forced Labour Act (S-211)",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "10c"): {
        "action": "Review supplier OHS incident rates and WSIB/WCB records; require corrective action for suppliers exceeding industry average lost-time injury rates; verify compliance with applicable provincial OHS legislation",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "10d"): {
        "action": "Screen suppliers against adverse media databases; assess reputational risk from pending litigation; flag suppliers involved in high-profile legal disputes that could affect program delivery",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "10e"): {
        "action": "Review supplier procurement fraud indicators; implement data analytics screening on invoicing patterns; coordinate with DND Internal Audit for high-risk supplier reviews",
        "timeline": "90 days",
        "responsible": "Security",
    },
    ("taxonomy", "10f"): {
        "action": "Investigate reported ethics violation; assess scope of non-compliance; require supplier corrective action plan; consider suspension of new contract awards pending resolution",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "10g"): {
        "action": "Review contract non-compliance findings; issue formal notice of default if material; require corrective action plan within 15 business days; track remediation to closure",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "10h"): {
        "action": "Initiate conflict mineral trace; verify 3TG (tin, tantalum, tungsten, gold) sourcing through RMI-compliant CMRT; require supplier participation in Responsible Minerals Initiative",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "10i"): {
        "action": "Monitor Competition Bureau and international antitrust actions involving defence suppliers; assess bid-rigging risk; review procurement processes for competitive integrity",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "10j"): {
        "action": "Review export control classification; ensure ITAR/EAR compliance; verify all Technical Assistance Agreements (TAAs) and Manufacturing License Agreements (MLAs) are current",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "10k"): {
        "action": "Screen supplier sub-tier supply chains against trafficking in persons indicators; require compliance with US TVPA and Canadian Criminal Code provisions; mandate supply chain transparency reporting",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "10l"): {
        "action": "Monitor SEC, OSC, and international regulatory enforcement actions against defence suppliers; assess financial penalty impact on supplier viability; flag material regulatory findings",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "10m"): {
        "action": "Screen suppliers against PSPC Integrity Database, US SAM exclusions, and World Bank debarment lists; require annual attestation of non-debarment status; reject bids from debarred entities",
        "timeline": "Immediate",
        "responsible": "Procurement",
    },
    ("taxonomy", "10n"): {
        "action": "Assess supplier operations against UN Guiding Principles on Business and Human Rights; require human rights impact assessments for operations in high-risk jurisdictions; review compliance with Global Affairs Canada guidance",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "10o"): {
        "action": "Conduct cost/price analysis review; verify supplier cost data submissions under Truth in Negotiations (TINA) equivalent requirements; flag proposals with unsupported cost elements for audit",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "10p"): {
        "action": "Review contractor misconduct history; assess severity and recency of past findings; require enhanced compliance monitoring for suppliers with prior misconduct; consider Integrity Regime implications",
        "timeline": "30 days",
        "responsible": "Security",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 11: Economic
    # 8 sub-categories: 11a–11h
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "11a"): {
        "action": "Assess recession impact on supplier financial health; increase monitoring frequency for Altman Z-Score and credit ratings; activate contingency procurement for suppliers at insolvency risk",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11b"): {
        "action": "Implement commodity price hedging for volatile inputs (titanium, rare earths, aluminum); negotiate fixed-price or capped escalation contracts; build strategic stockpile of price-volatile materials",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11c"): {
        "action": "Model inflation impact on multi-year defence contracts; invoke economic price adjustment (EPA) clauses; renegotiate fixed-price contracts where inflation exceeds original assumptions by >3%",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11d"): {
        "action": "Assess labour market conditions in supplier regions; identify suppliers at risk from high unemployment areas where skilled workforce may have dispersed; monitor rehiring capability",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "11e"): {
        "action": "Map sanctions exposure across full supply chain; model re-sourcing costs and timelines for sanctioned-origin materials; coordinate with Global Affairs Canada on sanctions compliance guidance",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("taxonomy", "11f"): {
        "action": "Monitor economic instability indicators (GDP contraction, currency crisis, banking system stress) in key supplier countries; activate contingency sourcing for suppliers in distressed economies",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "11g"): {
        "action": "Model demand shock impact on supply chain capacity; coordinate with allied nations on shared procurement to aggregate demand; negotiate priority allocation agreements with key manufacturers",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11h"): {
        "action": "Monitor CAD/USD and CAD/EUR exchange rate exposure on active contracts; implement FX hedging for contracts >$10M with foreign-denominated costs; invoke currency adjustment clauses in contracts",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    # Additional Economic COAs
    ("taxonomy", "11_interest_rate"): {
        "action": "Assess interest rate impact on supplier capital costs and investment plans; monitor bank lending conditions for SME defence suppliers; flag suppliers with high debt-to-equity ratios",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11_trade_diversion"): {
        "action": "Monitor trade diversion patterns where sanctioned nations reroute through third countries; verify origin documentation for dual-use goods from transshipment hubs (UAE, Turkey, Kazakhstan)",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "11_insurance_cost"): {
        "action": "Assess rising insurance premiums for conflict-zone transit and high-risk supply corridors; model cost pass-through impact on DND procurement; evaluate self-insurance options for Crown cargo",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "11_subsidy_risk"): {
        "action": "Monitor foreign government subsidies distorting defence industrial competition; assess whether allied procurement policies disadvantage Canadian suppliers; brief DGMPD on unfair trade practices",
        "timeline": "90 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 12: Financial
    # 11 sub-categories: 12a–12k
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "12a"): {
        "action": "Screen suppliers against FINTRAC and FinCEN databases for financial crime indicators; require AML/CTF compliance attestation; flag suppliers with adverse findings for enhanced due diligence",
        "timeline": "30 days",
        "responsible": "Security",
    },
    ("taxonomy", "12b"): {
        "action": "Purchase safety stock from secondary supplier to cover 6-month gap; monitor Z-Score and credit ratings; establish financial health early warning indicators with quarterly reporting",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "12c"): {
        "action": "Review supplier operational efficiency metrics (inventory turns, cash conversion cycle, capacity utilization); flag declining trends; require improvement plan if efficiency drops below industry benchmark",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "12d"): {
        "action": "Assess supplier revenue concentration; develop business continuity plan; encourage supplier commercial diversification to reduce DND dependency below 60% of revenue",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "12e"): {
        "action": "Review cost baseline; negotiate revised contract terms if overrun exceeds 10%; establish earned value management (EVM) reporting requirements; escalate to ADM(Mat) if overrun exceeds 25%",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "12f"): {
        "action": "Monitor defence spending cycle indicators across NATO allies; assess impact of political budget cuts on supplier order books; maintain flexible contract structures to absorb cyclical fluctuations",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "12g"): {
        "action": "Monitor supplier payment performance through Dun & Bradstreet and trade credit reports; flag suppliers with deteriorating payment patterns (>60 day payables); require cash flow improvement plans",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "12h"): {
        "action": "Assess capital access constraints for SME defence suppliers; coordinate with BDC and EDC for defence industry financing programs; evaluate advance payment mechanisms to support supplier liquidity",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "12i"): {
        "action": "Monitor bankruptcy filing indicators for DND suppliers (Chapter 11/CCAA petitions); develop transition plans for critical items; secure IP and tooling rights through contract provisions before insolvency",
        "timeline": "Immediate",
        "responsible": "Procurement",
    },
    ("taxonomy", "12j"): {
        "action": "Track supplier profitability trends (EBITDA margin, gross margin erosion); assess whether margin pressure threatens program delivery; negotiate contract adjustments to sustain supplier viability",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("taxonomy", "12k"): {
        "action": "Screen suppliers against ICIJ offshore leaks databases (Panama Papers, Paradise Papers, Pandora Papers); investigate opaque ownership structures; require full beneficial ownership disclosure",
        "timeline": "30 days",
        "responsible": "Security",
    },
    # Additional Financial COAs
    ("taxonomy", "12_bond_rating"): {
        "action": "Monitor corporate bond rating changes for publicly traded defence suppliers; flag downgrades below investment grade; assess impact on supplier ability to finance major program commitments",
        "timeline": "30 days",
        "responsible": "Procurement",
    },

    # ═══════════════════════════════════════════════════════════════════
    # CATEGORY 13: Product Quality & Design
    # 6 sub-categories: 13a–13f
    # ═══════════════════════════════════════════════════════════════════
    ("taxonomy", "13a"): {
        "action": "Monitor supplier recall databases (CPSC, Health Canada, GIDEP); cross-reference recalled components against DND NSN inventory; quarantine affected stock pending safety assessment",
        "timeline": "Immediate",
        "responsible": "Program Office",
    },
    ("taxonomy", "13b"): {
        "action": "Conduct failure analysis on reported system/parts defects; issue engineering investigation request; determine root cause and scope of affected production lots; mandate corrective action per AS9100",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13c"): {
        "action": "Review specification changes affecting product characteristics; assess form-fit-function impact on weapon systems; coordinate engineering change proposals through configuration management board",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13d"): {
        "action": "Audit use of non-MILSPEC parts in DND systems; require qualification testing for commercial substitutes; mandate MILSPEC compliance or approved deviation documentation per CFTO requirements",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13e"): {
        "action": "Review non-conformance reports (NCRs); conduct root cause analysis using 8D methodology; track corrective/preventive actions to closure; increase source inspection if NCR rate exceeds threshold",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13f"): {
        "action": "Activate counterfeit detection protocols; quarantine suspect parts; conduct destructive physical analysis (DPA) per SAE AS6171; trace distribution chain to identify point of entry; report to GIDEP",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    # Additional Quality COAs
    ("taxonomy", "13_first_article"): {
        "action": "Require First Article Inspection (FAI) per AS9102 for all new or re-sourced production items; mandate FAI report review and approval before production release",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_process_change"): {
        "action": "Require prior notification and approval for manufacturing process changes at supplier facilities; mandate re-qualification testing after process modifications per CFTO C-05-005-001",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_shelf_life"): {
        "action": "Audit shelf-life management for time-sensitive materiel (explosives, sealants, lubricants, batteries); verify FIFO compliance; dispose of expired stock per DND disposal directives",
        "timeline": "30 days",
        "responsible": "DSCRO",
    },
    ("taxonomy", "13_testing_lab"): {
        "action": "Verify supplier testing laboratory accreditation (ISO 17025); audit calibration records for measurement equipment; require independent third-party testing for safety-critical components",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_design_authority"): {
        "action": "Clarify design authority responsibilities between DND and prime contractor; ensure DND retains Type Certificate or design data rights; prevent vendor lock-in on engineering changes",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_software_quality"): {
        "action": "Require DO-178C/ED-12C compliance for safety-critical airborne software; mandate static code analysis and formal verification for weapon system firmware; audit supplier software development processes",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_reliability"): {
        "action": "Review MTBF/MTTR data against contractual reliability requirements; issue reliability improvement warranty (RIW) claims for underperforming systems; require reliability growth testing",
        "timeline": "90 days",
        "responsible": "Program Office",
    },
    ("taxonomy", "13_config_mgmt"): {
        "action": "Audit supplier configuration management practices; verify configuration baselines match as-built documentation; mandate configuration status accounting for all DND platforms",
        "timeline": "30 days",
        "responsible": "Program Office",
    },

    # ═══════════════════════════════════════════════════════════════════
    # PSI ALERTS (Supply Chain Intelligence triggers)
    # ═══════════════════════════════════════════════════════════════════
    ("psi", "chokepoint_blocked"): {
        "action": "Divert shipments to alternate port; assess transit time impact; coordinate with allied naval forces for convoy protection if blockade involved",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("psi", "material_shortage"): {
        "action": "Purchase safety stock from secondary supplier to cover 6-month gap; engage NRCan for domestic mineral sourcing alternatives",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("psi", "sanctions_risk"): {
        "action": "Initiate supply chain re-sourcing; flag affected NSNs for review; coordinate with Global Affairs Canada on sanction-compliant alternatives",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("psi", "concentration_risk"): {
        "action": "Identify alternate sources across different geographies; begin qualification; target HHI reduction below 2500 for critical materials",
        "timeline": "90 days",
        "responsible": "Procurement",
    },
    ("psi", "supplier_disruption"): {
        "action": "Activate business continuity plan; contact secondary suppliers; assess disruption duration and cascading impacts through knowledge graph propagation analysis",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("psi", "demand_surge"): {
        "action": "Negotiate priority allocation with suppliers; assess production capacity; coordinate with allied nations for shared procurement to aggregate buying power",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
    ("psi", "route_disruption"): {
        "action": "Activate alternate logistics corridors; model transit time and cost impact; brief J4 on supply chain timeline adjustments for deployed operations",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("psi", "quality_alert"): {
        "action": "Quarantine affected inventory; conduct incoming inspection of recent shipments; coordinate with supplier quality team for root cause analysis per AS9100 requirements",
        "timeline": "Immediate",
        "responsible": "Program Office",
    },
    ("psi", "obsolescence_alert"): {
        "action": "Initiate lifetime buy assessment for end-of-life components; submit DMSMS case; evaluate form-fit-function replacements; fund bridge procurement",
        "timeline": "30 days",
        "responsible": "Program Office",
    },
    ("psi", "cyber_incident"): {
        "action": "Isolate affected supplier from DND network connections; coordinate with CCCS for threat intelligence sharing; assess data exposure scope; activate incident response protocol",
        "timeline": "Immediate",
        "responsible": "Security",
    },
    ("psi", "geopolitical_escalation"): {
        "action": "Accelerate procurement of items from affected region; build 12-month buffer stock; identify NATO-allied alternative suppliers; brief CDS on supply chain readiness impact",
        "timeline": "Immediate",
        "responsible": "DSCRO",
    },
    ("psi", "price_spike"): {
        "action": "Assess commodity price spike impact on active contracts; invoke price adjustment clauses; evaluate spot vs. contract purchasing strategy; build strategic reserve at current prices if spike is temporary",
        "timeline": "30 days",
        "responsible": "Procurement",
    },
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
