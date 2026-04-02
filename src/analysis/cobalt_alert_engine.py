"""Cobalt Alert Engine — generates alerts from GDELT keywords and rule-based triggers.

Addresses DND Q1 (SENSE) and Q11 (Automated Sensing).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from src.analysis.mineral_supply_chains import get_mineral_by_name

logger = logging.getLogger(__name__)

_cached_alerts: list[dict] = []
_cache_timestamp: datetime | None = None

COBALT_GDELT_QUERIES = [
    "cobalt DRC Congo mining",
    "cobalt export ban quota restriction",
    "cobalt China refining disruption",
    "cobalt price crash spike",
    "cobalt mine accident shutdown",
    "CMOC Glencore cobalt acquisition",
    "cobalt sanctions embargo",
    "Sherritt cobalt Cuba",
]


async def generate_gdelt_alerts() -> list[dict]:
    """Scan GDELT for cobalt-related news and generate alerts."""
    from src.ingestion.gdelt_news import GDELTArmsNewsClient

    connector = GDELTArmsNewsClient()
    alerts: list[dict] = []

    for query in COBALT_GDELT_QUERIES:
        try:
            articles = await connector.search_articles(
                query=query, timespan="1440", max_records=5
            )
            for article in articles:
                if not article.title:
                    continue
                tone = article.tone or 0
                severity = 5 if tone < -8 else 4 if tone < -5 else 3 if tone < -2 else 2

                alerts.append({
                    "id": f"GDELT-{hash(article.url) % 100000:05d}",
                    "title": article.title[:200],
                    "severity": severity,
                    "category": _infer_category(article.title),
                    "sources": [article.source or "GDELT"],
                    "confidence": min(90, max(40, 50 + int(abs(tone) * 3))),
                    "coa": _suggest_coa(article.title),
                    "timestamp": (article.published_at or datetime.utcnow()).isoformat(),
                    "source_url": article.url,
                    "auto_generated": True,
                })
        except Exception as e:
            logger.warning("GDELT cobalt query failed for '%s': %s", query[:30], e)

    logger.info("Generated %d GDELT cobalt alerts", len(alerts))
    return alerts


def generate_rule_alerts() -> list[dict]:
    """Run rule-based checks against current Cobalt data."""
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        return []

    alerts: list[dict] = []

    # Rule: HHI concentration
    hhi = mineral.get("hhi", 0)
    if hhi > 5000:
        alerts.append({
            "id": "RULE-CONC-001",
            "title": f"Cobalt mining HHI at {hhi} — extreme supply concentration (DRC {mineral.get('mining', [{}])[0].get('pct', 0)}%)",
            "severity": 5 if hhi > 6000 else 4,
            "category": "Manufacturing/Supply",
            "sources": ["USGS MCS 2025", "PSI Concentration Index"],
            "confidence": 95,
            "coa": "Diversify sourcing to Australian, Philippine, and Canadian deposits",
            "timestamp": datetime.utcnow().isoformat(),
            "auto_generated": True,
        })

    # Rule: China refining dominance
    processing = mineral.get("processing", [])
    china_pct = sum(p.get("pct", 0) for p in processing if p.get("country") == "China")
    if china_pct > 70:
        alerts.append({
            "id": "RULE-CHINA-001",
            "title": f"China controls {china_pct}% of global cobalt refining — adversary chokepoint",
            "severity": 5,
            "category": "FOCI",
            "sources": ["USGS MCS 2025", "CRU Group Cobalt Market Report"],
            "confidence": 95,
            "coa": "Support Finnish/Norwegian refinery expansion; DPSA allied allocation",
            "timestamp": datetime.utcnow().isoformat(),
            "auto_generated": True,
        })

    # Rule: Paused operations
    for ref in mineral.get("refineries", []):
        note = (ref.get("note") or "").lower()
        if "paused" in note or "suspended" in note or "idled" in note:
            alerts.append({
                "id": f"RULE-PAUSE-{ref.get('name', 'UNK')[:8].upper().replace(' ', '')}",
                "title": f"{ref.get('name', 'Unknown')} operations paused — {ref.get('note', '')}",
                "severity": 4,
                "category": "Financial",
                "sources": [f"{ref.get('owner', 'Unknown')} Operations Report", "PSI Supply Chain Monitor"],
                "confidence": 90,
                "coa": f"Assess alternative refineries; monitor {ref.get('owner', 'operator')} restart timeline",
                "timestamp": datetime.utcnow().isoformat(),
                "auto_generated": True,
            })

    # Rule 4: Data discrepancy alert (from triangulation)
    try:
        from src.analysis.confidence import triangulate_cobalt_production, SourceDataPoint
        from src.ingestion.bgs_minerals import BGSCobaltClient

        drc_sources = []
        # BGS source
        try:
            bgs_client = BGSCobaltClient()
            bgs_data = bgs_client._fallback_data()
            for entry in bgs_data:
                if entry.get("country") == "Congo (Kinshasa)":
                    drc_sources.append(SourceDataPoint("BGS WMS", entry["production_tonnes"], entry.get("year", 2022), "live"))
                    break
        except Exception:
            pass
        # USGS figure from mineral_supply_chains
        cobalt = get_mineral_by_name("Cobalt")
        if cobalt:
            drc_mines = [m for m in cobalt.get("mines", []) if m.get("country") == "DRC"]
            drc_total = sum(m.get("production_t", 0) for m in drc_mines)
            if drc_total > 0:
                drc_sources.append(SourceDataPoint("USGS MCS 2025", drc_total, 2024, "live"))

        if len(drc_sources) >= 2:
            tri = triangulate_cobalt_production("DRC", drc_sources)
            for disc in tri.get("discrepancies", []):
                if disc["severity"] in ("warning", "critical"):
                    alerts.append({
                        "id": f"RULE-DISC-DRC-{len(alerts)}",
                        "title": f"Production data discrepancy: DRC cobalt — {disc['source_a']} vs {disc['source_b']} ({disc['delta_pct']}% delta)",
                        "severity": 4 if disc["severity"] == "critical" else 3,
                        "category": "Economic",
                        "sources": [disc["source_a"], disc["source_b"]],
                        "confidence": 80,
                        "coa": "Verify with Comtrade export volumes and company-reported DRC production figures",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "auto_generated": True,
                    })
    except Exception:
        logger.warning("Discrepancy alert rule failed", exc_info=True)

    logger.info("Generated %d rule-based cobalt alerts", len(alerts))
    return alerts


def _infer_category(title: str) -> str:
    """Infer alert category from article title keywords."""
    t = title.lower()
    if any(w in t for w in ["sanction", "embargo", "ban", "restrict"]):
        return "Political"
    if any(w in t for w in ["acquire", "merger", "ownership", "soe", "state-owned"]):
        return "FOCI"
    if any(w in t for w in ["price", "cost", "market", "crash", "spike"]):
        return "Economic"
    if any(w in t for w in ["cyber", "hack", "malware", "breach"]):
        return "Cyber"
    if any(w in t for w in ["mine", "accident", "spill", "pollution", "environment"]):
        return "Environmental"
    if any(w in t for w in ["ship", "route", "port", "transport", "logistics"]):
        return "Transportation"
    return "Manufacturing/Supply"


def _suggest_coa(title: str) -> str:
    """Suggest a course of action based on alert title."""
    t = title.lower()
    if "sanction" in t or "ban" in t:
        return "Activate alternative supply sources; review DPSA allocation"
    if "price" in t:
        return "Assess stockpile draw-down; review contract escalation clauses"
    if "acquisition" in t or "merger" in t:
        return "Initiate FOCI review; assess supply chain impact"
    if "accident" in t or "shutdown" in t:
        return "Monitor production recovery timeline; activate safety stock"
    return "Monitor situation; assess impact on Canadian defence supply chain"


def _apply_aging(alert: dict) -> dict | None:
    """Apply age-based severity demotion to an alert.

    Returns None if alert should be excluded (>90 days old).
    """
    ts_str = alert.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return alert  # Can't parse — keep as-is

    age_days = (datetime.now(timezone.utc) - ts).days

    if age_days > 90:
        return None
    elif age_days > 30:
        alert = {**alert, "severity": min(alert.get("severity", 1), 1), "aged": True}
    elif age_days > 7:
        alert = {**alert, "severity": max(1, alert.get("severity", 1) - 1), "aged": True}

    return alert


async def run_cobalt_alert_engine() -> list[dict]:
    """Main entry point — run both GDELT and rule-based alert generation."""
    global _cached_alerts, _cache_timestamp
    gdelt_alerts = await generate_gdelt_alerts()
    rule_alerts = generate_rule_alerts()

    all_alerts = gdelt_alerts + rule_alerts
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in all_alerts:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    aged: list[dict] = []
    for a in deduped:
        result = _apply_aging(a)
        if result is not None:
            aged.append(result)

    logger.info("Cobalt Alert Engine: %d total (%d GDELT, %d rules, %d deduped, %d after aging)",
                len(all_alerts), len(gdelt_alerts), len(rule_alerts), len(deduped), len(aged))
    _cached_alerts = aged
    _cache_timestamp = datetime.now(timezone.utc)
    return aged


def get_cached_alerts() -> tuple[list[dict], datetime | None]:
    """Return cached alerts from the last scheduled run."""
    return _cached_alerts, _cache_timestamp
