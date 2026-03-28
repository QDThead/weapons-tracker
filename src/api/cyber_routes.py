"""Cyber Threat Intelligence API endpoints.

Exposes APT actor profiles, Tor exit nodes, defence breach indicators,
IOC summary, and supplier-level cyber risk assessment for the
defence industrial base.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.analysis.cyber_threat_intel import CyberThreatIntelligence

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cyber", tags=["Cyber Threat Intelligence"])

# Module-level singleton — reuses internal 6-hour cache
_cti = CyberThreatIntelligence()


@router.get("/report")
async def get_threat_report():
    """Full cyber threat intelligence report for defence supply chain.

    Aggregates all cyber sub-sources into a unified threat picture:
    APT actors, Tor exit nodes, breach indicators, IOC summary,
    and supplier risk. Overall threat level (CRITICAL/HIGH/ELEVATED/MODERATE)
    computed from supplier risk distribution.
    """
    try:
        return await _cti.generate_threat_report()
    except Exception as exc:
        logger.exception("Cyber threat report failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/threat-actors")
async def get_threat_actors():
    """Nation-state APT groups targeting the defence industrial base.

    Returns 13 tracked APT groups with attribution, TTPs, known operations,
    target sectors, risk level, and MITRE ATT&CK group ID.
    Data sourced from public reporting: MITRE ATT&CK, Mandiant, CrowdStrike,
    NSA/CISA joint advisories.
    """
    try:
        actors = await _cti.fetch_threat_actors()
        return {
            "source": "MITRE ATT&CK / Mandiant / CrowdStrike / CISA (public reporting)",
            "total": len(actors),
            "critical_risk": len([a for a in actors if a.get("risk_level") == "CRITICAL"]),
            "high_risk": len([a for a in actors if a.get("risk_level") == "HIGH"]),
            "active_2024_plus": len([a for a in actors if a.get("last_active", "") >= "2024"]),
            "threat_actors": actors,
        }
    except Exception as exc:
        logger.exception("Threat actors endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/tor-nodes")
async def get_tor_exit_nodes():
    """Current Tor exit node list (anonymized access indicators).

    Fetches the live Tor Project bulk exit list from check.torproject.org.
    Exit nodes are indicators of anonymized infrastructure used by threat
    actors to obfuscate attribution during reconnaissance and exfiltration.
    Cached for 6 hours.
    """
    try:
        nodes = await _cti.fetch_tor_exit_nodes()
        return {
            "source": "Tor Project",
            "url": "https://check.torproject.org/torbulkexitlist",
            "description": (
                "Current Tor exit nodes. These IPs may be used by threat actors "
                "to anonymize reconnaissance and exfiltration traffic targeting "
                "defence industrial base networks."
            ),
            "cache_ttl": "6 hours",
            "total": len(nodes),
            "nodes": nodes,
        }
    except Exception as exc:
        logger.exception("Tor nodes endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/breaches")
async def get_defence_breaches():
    """Known breaches affecting the defence industrial base.

    Returns documented incidents from public reporting covering
    Lockheed Martin, Boeing, BAE Systems, SolarWinds supply chain,
    Microsoft Exchange ProxyLogon, MOVEit, and other defence-adjacent breaches.
    Sources: Reuters, CyberScoop, CISA advisories, company disclosures.
    """
    try:
        breaches = await _cti.fetch_defence_breach_indicators()
        by_type: dict[str, int] = {}
        for b in breaches:
            t = b.get("type", "Unknown")
            by_type[t] = by_type.get(t, 0) + 1

        by_attribution: dict[str, int] = {}
        for b in breaches:
            a = b.get("attributed_to", "Unknown")
            by_attribution[a] = by_attribution.get(a, 0) + 1

        return {
            "source": "Public breach reporting — Reuters, CyberScoop, CISA advisories, company disclosures",
            "note": "Incidents from open-source reporting only. Classified incidents not included.",
            "total": len(breaches),
            "by_type": by_type,
            "by_attribution": by_attribution,
            "breaches": breaches,
        }
    except Exception as exc:
        logger.exception("Defence breaches endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/ioc-summary")
async def get_ioc_summary():
    """Indicator of Compromise summary from all cyber feeds.

    Combines: Tor exit node count, CISA KEV catalogue (approximate),
    NVD critical CVE count (approximate), and MITRE ATT&CK group count
    into a summary dashboard. Live CISA/NVD counts available at
    /enrichment/cyber-threats and /enrichment/critical-cves.
    """
    try:
        return await _cti.fetch_ioc_summary()
    except Exception as exc:
        logger.exception("IOC summary endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/supplier-risk")
async def get_supplier_cyber_risk():
    """Cyber risk assessment for each Canadian defence supplier.

    Assesses 14 key Canadian defence industrial base suppliers against:
    - Sector (aerospace/EW/cyber = higher target value)
    - Foreign ownership (subsidiary of targeted parent = higher risk)
    - Known breaches of parent / peer companies
    - Active APT group targeting of sector

    Risk levels: CRITICAL / HIGH / MODERATE / LOW
    """
    try:
        suppliers = await _cti.assess_supplier_cyber_risk()
        risk_counts = {"CRITICAL": 0, "HIGH": 0, "MODERATE": 0, "LOW": 0}
        for s in suppliers:
            lvl = s.get("cyber_risk_level", "LOW")
            risk_counts[lvl] = risk_counts.get(lvl, 0) + 1

        return {
            "source": "Open-source analysis — DND supplier registry, MITRE ATT&CK, public breach reports",
            "methodology": (
                "Risk scored on: sector sensitivity, foreign ownership, documented parent breaches, "
                "and active APT group targeting of sector."
            ),
            "total_suppliers_assessed": len(suppliers),
            "risk_distribution": risk_counts,
            "suppliers": suppliers,
        }
    except Exception as exc:
        logger.exception("Supplier cyber risk endpoint failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
