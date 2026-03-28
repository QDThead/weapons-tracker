"""Cyber Threat Intelligence aggregator for defence supply chain monitoring.

Combines Tor exit node tracking, nation-state APT actor profiles, known breach
indicators, and supplier-level cyber risk assessment into a unified threat picture.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# 6-hour cache TTL (matches enrichment pattern for cyber feeds)
_CYBER_CACHE: dict[str, tuple[float, dict | list]] = {}
_CYBER_TTL = 21600  # 6 hours


def _check_cache(key: str) -> dict | list | None:
    cached = _CYBER_CACHE.get(key)
    if cached and time.time() - cached[0] < _CYBER_TTL:
        return cached[1]
    return None


def _set_cache(key: str, data: dict | list) -> None:
    _CYBER_CACHE[key] = (time.time(), data)


class CyberThreatIntelligence:
    """Aggregates cyber threat intelligence relevant to the defence industrial base.

    Pulls from:
      - Tor Project exit node list (live)
      - Hardcoded APT actor database (public reporting)
      - Hardcoded known breach registry (public reporting)
      - MITRE ATT&CK / CISA KEV cross-reference (via IOC summary)
      - Canadian defence supplier cyber risk assessment
    """

    def __init__(self, session=None):
        self.session = session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def generate_threat_report(self) -> dict:
        """Full cyber threat intelligence report for defence supply chain.

        Aggregates all sub-sources and returns a unified threat picture
        structured for decision-maker consumption.
        """
        cached = _check_cache("full_report")
        if cached:
            return cached

        tor_nodes, threat_actors, breaches, ioc_summary, supplier_risk = (
            await self.fetch_tor_exit_nodes(),
            await self.fetch_threat_actors(),
            await self.fetch_defence_breach_indicators(),
            await self.fetch_ioc_summary(),
            await self.assess_supplier_cyber_risk(),
        )

        # Derive overall threat level
        critical_suppliers = [s for s in supplier_risk if s["cyber_risk_level"] == "CRITICAL"]
        high_suppliers = [s for s in supplier_risk if s["cyber_risk_level"] == "HIGH"]

        if len(critical_suppliers) >= 3:
            overall_level = "CRITICAL"
        elif len(critical_suppliers) >= 1 or len(high_suppliers) >= 5:
            overall_level = "HIGH"
        elif len(high_suppliers) >= 2:
            overall_level = "ELEVATED"
        else:
            overall_level = "MODERATE"

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": "UNCLASSIFIED // OPEN SOURCE",
            "overall_threat_level": overall_level,
            "executive_summary": (
                f"Defence industrial base cyber threat: {overall_level}. "
                f"{len(critical_suppliers)} supplier(s) at CRITICAL risk, "
                f"{len(high_suppliers)} at HIGH risk. "
                f"{ioc_summary['tor_exit_node_count']} active Tor exit nodes detected. "
                f"{len(threat_actors)} tracked APT groups targeting defence. "
                f"{len(breaches)} known breach incidents on record."
            ),
            "ioc_summary": ioc_summary,
            "threat_actors": {
                "total": len(threat_actors),
                "by_attribution": _group_by(threat_actors, "attribution"),
                "active_groups": [a for a in threat_actors if a.get("last_active", "") >= "2023"],
            },
            "breach_indicators": {
                "total": len(breaches),
                "by_type": _group_by(breaches, "type"),
                "recent": [b for b in breaches if b.get("date", "") >= "2020"],
            },
            "anonymized_access": {
                "tor_exit_nodes": len(tor_nodes),
                "note": (
                    "Tor exit node count is an indicator of anonymized access infrastructure. "
                    "Threat actors commonly use Tor to obfuscate attribution during reconnaissance."
                ),
            },
            "supplier_cyber_risk": {
                "total_assessed": len(supplier_risk),
                "critical": len(critical_suppliers),
                "high": len(high_suppliers),
                "moderate": len([s for s in supplier_risk if s["cyber_risk_level"] == "MODERATE"]),
                "low": len([s for s in supplier_risk if s["cyber_risk_level"] == "LOW"]),
                "top_risks": sorted(supplier_risk, key=_risk_sort_key)[:5],
            },
            "sources": [
                "Tor Project exit node list (check.torproject.org)",
                "MITRE ATT&CK Enterprise (public hardcoded profiles)",
                "Public breach reporting (Reuters, CyberScoop, CISA advisories)",
                "Canadian DND supplier registry (open source)",
            ],
        }

        _set_cache("full_report", report)
        return report

    async def fetch_tor_exit_nodes(self) -> list[dict]:
        """Fetch current Tor exit node list — indicators of anonymized access.

        Source: https://check.torproject.org/torbulkexitlist
        Returns plain text, one IP per line.
        """
        cached = _check_cache("tor_nodes")
        if cached:
            return cached

        url = "https://check.torproject.org/torbulkexitlist"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                lines = [ln.strip() for ln in resp.text.splitlines() if ln.strip() and not ln.startswith("#")]
                nodes = [{"ip": ip, "type": "tor_exit", "risk": "indicator"} for ip in lines]
                logger.info("Fetched %d Tor exit nodes", len(nodes))
                _set_cache("tor_nodes", nodes)
                return nodes
        except Exception as exc:
            logger.warning("Tor exit node fetch failed: %s", exc)
            return []

    async def fetch_threat_actors(self) -> list[dict]:
        """Nation-state APT groups targeting the defence industrial base.

        Data sourced from: MITRE ATT&CK, Mandiant, CrowdStrike, FireEye,
        NSA/CISA advisories, and public threat intelligence reports.
        """
        cached = _check_cache("threat_actors")
        if cached:
            return cached

        actors = [
            {
                "name": "APT28",
                "aliases": ["Fancy Bear", "Sofacy", "STRONTIUM", "Pawn Storm", "Sednit"],
                "attribution": "Russia (GRU Unit 26165)",
                "targets": [
                    "defence contractors", "NATO governments", "aerospace", "energy",
                    "election infrastructure", "media",
                ],
                "ttps": [
                    "spear-phishing", "credential harvesting", "X-Agent malware",
                    "VPN exploitation", "living-off-the-land", "LSASS dumping",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": ["Buhtrap", "Operation Pawn Storm", "DNC hack 2016", "SolarWinds (overlap)"],
                "mitre_id": "G0007",
                "note": "Primary GRU cyber unit. Highly active against NATO defence industrial base.",
            },
            {
                "name": "APT29",
                "aliases": ["Cozy Bear", "NOBELIUM", "The Dukes", "Midnight Blizzard"],
                "attribution": "Russia (SVR Foreign Intelligence Service)",
                "targets": [
                    "government agencies", "think tanks", "defence contractors",
                    "technology companies", "critical infrastructure",
                ],
                "ttps": [
                    "supply chain compromise", "OAuth token theft", "WellMess malware",
                    "MiniDuke", "cloud service abuse", "spear-phishing",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": ["SolarWinds supply chain (2020)", "Microsoft Teams phishing (2023)", "COVID-19 vaccine research theft"],
                "mitre_id": "G0016",
                "note": "SVR intelligence collection focused on long-term persistent access. Highly sophisticated.",
            },
            {
                "name": "APT41",
                "aliases": ["Double Dragon", "Winnti", "Barium", "Wicked Panda"],
                "attribution": "China (MSS / Ministry of State Security)",
                "targets": [
                    "defence", "healthcare", "telecommunications", "technology",
                    "gaming (financially motivated)", "semiconductor", "aerospace",
                ],
                "ttps": [
                    "supply chain compromise", "zero-day exploitation", "web shell deployment",
                    "Winnti malware", "ShadowPad", "dual espionage/criminal operations",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": ["CCleaner supply chain", "ASUS ShadowHammer", "US state government breaches 2021-2022"],
                "mitre_id": "G0096",
                "note": "Unique dual mandate: state espionage and financially motivated operations.",
            },
            {
                "name": "Lazarus Group",
                "aliases": ["HIDDEN COBRA", "ZINC", "Labyrinth Chollima", "APT38"],
                "attribution": "North Korea (RGB / Reconnaissance General Bureau)",
                "targets": [
                    "defence contractors", "financial institutions", "cryptocurrency",
                    "aerospace", "nuclear research", "media",
                ],
                "ttps": [
                    "spear-phishing via LinkedIn", "watering hole attacks",
                    "custom malware (BLINDINGCAN, HOPLIGHT)", "cryptocurrency theft",
                    "destructive attacks",
                ],
                "risk_level": "HIGH",
                "last_active": "2025",
                "known_operations": ["Sony hack (2014)", "WannaCry (2017)", "Bangladesh Bank heist", "Operation Dream Job (defence)"],
                "mitre_id": "G0032",
                "note": "Targets defence contractors via fake job offers to fund DPRK weapons programs.",
            },
            {
                "name": "APT33",
                "aliases": ["Elfin", "Refined Kitten", "Magnallium"],
                "attribution": "Iran (IRGC / Islamic Revolutionary Guard Corps)",
                "targets": [
                    "aerospace", "energy", "petrochemical", "defence supply chain",
                    "Saudi Arabia", "US defence contractors",
                ],
                "ttps": [
                    "spear-phishing", "DROPSHOT/StoneDrill wiper", "password spray",
                    "watering hole", "credential harvesting", "VPN exploitation",
                ],
                "risk_level": "HIGH",
                "last_active": "2024",
                "known_operations": ["Shamoon-linked operations", "Boeing/Raytheon targeting", "aviation sector campaigns"],
                "mitre_id": "G0064",
                "note": "Primary focus on aviation and aerospace components of defence supply chain.",
            },
            {
                "name": "Turla",
                "aliases": ["Snake", "Uroburos", "Waterbug", "VENOMOUS BEAR", "Krypton"],
                "attribution": "Russia (FSB Federal Security Service)",
                "targets": [
                    "government ministries", "defence", "intelligence agencies",
                    "embassies", "military", "research institutions",
                ],
                "ttps": [
                    "satellite hijacking for C2", "Carbon backdoor", "Kazuar implant",
                    "watering hole", "USB propagation", "hypervisor-level rootkit",
                ],
                "risk_level": "HIGH",
                "last_active": "2025",
                "known_operations": ["Agent.BTZ (Pentagon 2008)", "Moonlight Maze", "LightNeuron email compromise"],
                "mitre_id": "G0010",
                "note": "One of the most sophisticated and long-running APT groups. FSB signals intelligence.",
            },
            {
                "name": "APT10",
                "aliases": ["Stone Panda", "menuPass", "Red Apollo", "CVNX"],
                "attribution": "China (MSS Tianjin Bureau)",
                "targets": [
                    "managed service providers", "defence contractors",
                    "aerospace", "satellite technology", "pharmaceutical", "government",
                ],
                "ttps": [
                    "MSP compromise for downstream access", "PlugX/QuasarRAT",
                    "spear-phishing", "credential theft", "lateral movement via supply chain",
                ],
                "risk_level": "HIGH",
                "last_active": "2024",
                "known_operations": ["Operation Cloud Hopper (global MSP compromise)", "Operation Soft Cell"],
                "mitre_id": "G0045",
                "note": "Specializes in MSP compromise to reach multiple defence contractor victims simultaneously.",
            },
            {
                "name": "Sandworm",
                "aliases": ["Voodoo Bear", "ELECTRUM", "Telebots", "IRIDIUM"],
                "attribution": "Russia (GRU Unit 74455)",
                "targets": [
                    "critical infrastructure", "energy grid", "defence industrial base",
                    "Ukraine government", "NATO member states",
                ],
                "ttps": [
                    "NotPetya malware", "Industroyer/CrashOverride ICS malware",
                    "BlackEnergy", "destructive wiper attacks", "OT/ICS targeting",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": [
                    "Ukraine power grid attacks (2015, 2016)", "NotPetya (2017, $10B damage)",
                    "Winter Vivern", "Cyclops Blink botnet",
                ],
                "mitre_id": "G0034",
                "note": "Only group known to deploy destructive malware against industrial control systems.",
            },
            {
                "name": "Kimsuky",
                "aliases": ["Velvet Chollima", "Black Banshee", "Thallium", "APT43"],
                "attribution": "North Korea (RGB)",
                "targets": [
                    "South Korea", "US government", "defence think tanks",
                    "nuclear research", "UN Security Council sanctions bodies",
                ],
                "ttps": [
                    "spear-phishing", "BabyShark malware", "credential harvesting",
                    "browser extension abuse", "fake journalist personas",
                ],
                "risk_level": "HIGH",
                "last_active": "2025",
                "known_operations": ["Korea Aerospace Industries targeting", "UN Panel of Experts compromise"],
                "mitre_id": "G0094",
                "note": "Focus on strategic intelligence collection to support DPRK nuclear/missile programs.",
            },
            {
                "name": "Charming Kitten",
                "aliases": ["APT35", "Phosphorus", "TA453", "Mint Sandstorm"],
                "attribution": "Iran (IRGC)",
                "targets": [
                    "academics", "journalists", "human rights activists",
                    "defence researchers", "US government", "Israeli entities",
                ],
                "ttps": [
                    "credential phishing via fake Google/Microsoft portals",
                    "WhatsApp social engineering", "malicious PDF",
                    "POWERSTAR malware", "NokNok (macOS)",
                ],
                "risk_level": "HIGH",
                "last_active": "2025",
                "known_operations": ["Targeting of nuclear deal negotiators", "IAEA researchers", "US Presidential campaign 2020"],
                "mitre_id": "G0059",
                "note": "IRGC intelligence arm targeting defence policy experts and researchers.",
            },
            {
                "name": "APT1",
                "aliases": ["Comment Crew", "Comment Panda", "PLA Unit 61398"],
                "attribution": "China (PLA Unit 61398, 2nd Bureau, 3PLA)",
                "targets": [
                    "US defence contractors", "aerospace", "energy",
                    "telecommunications", "government", "20+ industry sectors",
                ],
                "ttps": [
                    "spear-phishing", "BISCUIT/MANITSME backdoors",
                    "WEBC2 malware family", "data exfiltration at scale",
                ],
                "risk_level": "HIGH",
                "last_active": "2023",
                "known_operations": ["Mandiant APT1 report (2013) — 141 organizations breached", "Operation Byzantine Hades"],
                "mitre_id": "G0006",
                "note": "Exposed by Mandiant in 2013. Operations reportedly restructured but capability maintained.",
            },
            {
                "name": "Cozy Bear",
                "aliases": ["APT29", "The Dukes", "NOBELIUM"],
                "attribution": "Russia (SVR)",
                "targets": [
                    "diplomatic", "think tanks", "health care",
                    "defence policy", "technology companies",
                ],
                "ttps": [
                    "trusted relationship abuse", "MiniDuke", "CozyDuke",
                    "OAuth token theft via device code phishing",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": ["DNC breach (2016)", "SolarWinds (2020)", "Microsoft executive email compromise (2024)"],
                "mitre_id": "G0016",
                "note": "Alias entry — see APT29. SVR long-term access focus.",
            },
            {
                "name": "Fancy Bear",
                "aliases": ["APT28", "Sofacy", "STRONTIUM"],
                "attribution": "Russia (GRU)",
                "targets": ["NATO governments", "defence contractors", "media", "elections"],
                "ttps": [
                    "X-Agent", "Sofacy toolkit", "spear-phishing", "zero-day exploitation",
                ],
                "risk_level": "CRITICAL",
                "last_active": "2025",
                "known_operations": ["DNC hack (2016)", "WADA breach (2016)", "Bundestag hack (2015)", "French election targeting (2017)"],
                "mitre_id": "G0007",
                "note": "Alias entry — see APT28. GRU active measures unit.",
            },
        ]

        _set_cache("threat_actors", actors)
        return actors

    async def fetch_defence_breach_indicators(self) -> list[dict]:
        """Known breaches affecting the defence industrial base (from public reporting).

        Sources: Reuters, WSJ, CyberScoop, CISA advisories, company disclosures.
        """
        cached = _check_cache("breach_indicators")
        if cached:
            return cached

        breaches = [
            {
                "entity": "SolarWinds / Orion Platform",
                "date": "2020-12",
                "type": "Supply Chain Compromise",
                "attributed_to": "APT29 (Russia/SVR)",
                "impact": (
                    "~18,000 organizations backdoored via Orion update. Affected US DoD, "
                    "State Dept, Treasury, DHS, and multiple defence contractors. "
                    "SUNBURST malware persisted for months before detection."
                ),
                "source": "FireEye / CISA Emergency Directive 21-01",
                "affected_entities": ["DoD", "State Dept", "Lockheed Martin", "Microsoft", "Intel"],
            },
            {
                "entity": "Microsoft Exchange Server (ProxyLogon)",
                "date": "2021-03",
                "type": "Zero-Day Exploitation",
                "attributed_to": "APT41 / HAFNIUM (China/MSS)",
                "impact": (
                    "250,000+ servers compromised globally including defence contractors, "
                    "military research, and government agencies. Web shell backdoors deployed "
                    "for persistent access."
                ),
                "source": "Microsoft MSRC / CISA Advisory AA21-062A",
                "affected_entities": ["Multiple defence contractors", "NATO member governments"],
            },
            {
                "entity": "Boeing (Defence division data)",
                "date": "2023-10",
                "type": "Data Exfiltration / Ransomware",
                "attributed_to": "LockBit 3.0 (ransomware group)",
                "impact": (
                    "~43 GB of internal data exfiltrated and published. Included supply chain "
                    "documents, parts inventory, and internal communications. Boeing confirmed breach."
                ),
                "source": "LockBit leak site / Reuters 2023-10-27",
                "affected_entities": ["Boeing Defence, Space & Security"],
            },
            {
                "entity": "MOVEit Transfer (defence supply chain)",
                "date": "2023-06",
                "type": "Supply Chain / Mass Exploitation",
                "attributed_to": "Cl0p ransomware group (Russia-linked)",
                "impact": (
                    "SQL injection zero-day (CVE-2023-34362) exploited at scale. "
                    "Hundreds of organizations including US government contractors, "
                    "L3Harris, and defence-adjacent logistics firms affected."
                ),
                "source": "CISA Advisory / Progress Software disclosure",
                "affected_entities": ["L3Harris", "US government contractors", "defence logistics firms"],
            },
            {
                "entity": "Lockheed Martin (multiple incidents)",
                "date": "2011-05",
                "type": "Network Intrusion (RSA seed compromise)",
                "attributed_to": "China-linked APT (suspected APT1)",
                "impact": (
                    "Intrusion leveraged stolen RSA SecurID tokens to access sensitive networks. "
                    "F-35 JSF design data reportedly targeted. One of the most publicized "
                    "defence contractor breaches of the decade."
                ),
                "source": "Lockheed Martin press release / Reuters",
                "affected_entities": ["Lockheed Martin corporate network", "F-35 JSF program"],
            },
            {
                "entity": "BAE Systems (employee data / project files)",
                "date": "2020-06",
                "type": "Data Exfiltration",
                "attributed_to": "Suspected nation-state (attribution unclear)",
                "impact": (
                    "Employee PII and select project files exposed. Reported via third-party "
                    "supplier compromise. BAE Systems confirmed an incident affecting a subset "
                    "of employee records."
                ),
                "source": "UK NCSC / press reporting",
                "affected_entities": ["BAE Systems Applied Intelligence"],
            },
            {
                "entity": "Northrop Grumman (IT infrastructure)",
                "date": "2011-06",
                "type": "Network Intrusion",
                "attributed_to": "RSA SecurID seed breach exploitation",
                "impact": (
                    "Followed Lockheed Martin breach. Northrop Grumman proactively disconnected "
                    "remote access. Potential access to classified shipbuilding and drone programs."
                ),
                "source": "Wired / Reuters",
                "affected_entities": ["Northrop Grumman corporate IT"],
            },
            {
                "entity": "L-3 Technologies (now L3Harris)",
                "date": "2011-06",
                "type": "Network Intrusion",
                "attributed_to": "RSA SecurID seed breach exploitation",
                "impact": (
                    "Third major US defence contractor targeted in 2011 RSA supply chain cascade. "
                    "L-3 notified by government of potential compromise."
                ),
                "source": "Reuters",
                "affected_entities": ["L-3 Technologies communications division"],
            },
            {
                "entity": "US OPM (Office of Personnel Management)",
                "date": "2015-06",
                "type": "Data Exfiltration (insider records)",
                "attributed_to": "China (APT41 / MSS)",
                "impact": (
                    "21.5 million security clearance records stolen including SF-86 forms "
                    "for all cleared personnel. Devastating for intelligence community "
                    "and defence industrial base employee identification."
                ),
                "source": "OPM / FBI / CISA",
                "affected_entities": ["US cleared defence workers", "IC community"],
            },
            {
                "entity": "Raytheon (subsidiary data)",
                "date": "2021-03",
                "type": "Data Exposure via Third Party",
                "attributed_to": "Accellion FTA zero-day (Cl0p linked)",
                "impact": (
                    "Internal documents exposed via Accellion file-transfer appliance breach. "
                    "Raytheon confirmed exposure of non-classified but sensitive business data."
                ),
                "source": "Mandiant / Raytheon disclosure",
                "affected_entities": ["Raytheon Technologies subsidiary"],
            },
            {
                "entity": "MBDA Missile Systems (USB exfiltration)",
                "date": "2022-08",
                "type": "Insider / Physical Media Exfiltration",
                "attributed_to": "Unknown (criminal sale reported)",
                "impact": (
                    "60 GB of classified NATO and MBDA internal data offered for sale online "
                    "by hacker group. Included weapon system documentation. MBDA confirmed "
                    "theft of commercially sensitive data."
                ),
                "source": "Cyberknow / MBDA press statement",
                "affected_entities": ["MBDA Missile Systems", "NATO member data"],
            },
            {
                "entity": "European Defence Agency (EDA)",
                "date": "2011",
                "type": "Network Intrusion",
                "attributed_to": "Nation-state (unattributed)",
                "impact": (
                    "EDA network compromise revealed during WikiLeaks disclosures. "
                    "Emails and internal communications between EU defence ministries exposed."
                ),
                "source": "WikiLeaks diplomatic cables",
                "affected_entities": ["European Defence Agency", "EU member state defence ministries"],
            },
            {
                "entity": "General Dynamics (cleared facilities)",
                "date": "2020-06",
                "type": "Spear-Phishing / Account Compromise",
                "attributed_to": "Nation-state (Russia-linked, suspected)",
                "impact": (
                    "Employees targeted with COVID-19 themed spear-phishing. "
                    "Attempted access to classified program documentation. "
                    "General Dynamics confirmed targeting."
                ),
                "source": "CyberScoop / CISA advisory",
                "affected_entities": ["General Dynamics Information Technology"],
            },
        ]

        _set_cache("breach_indicators", breaches)
        return breaches

    async def fetch_ioc_summary(self) -> dict:
        """Indicator of Compromise summary from aggregated cyber feeds."""
        cached = _check_cache("ioc_summary")
        if cached:
            return cached

        # Fetch Tor nodes for live count; others are estimated from public reporting
        tor_nodes = await self.fetch_tor_exit_nodes()
        threat_actors = await self.fetch_threat_actors()

        # CISA KEV and NVD CVE counts are estimated from public dashboards
        # (live fetch happens in enrichment_routes.py /cyber-threats and /critical-cves)
        # These are representative figures from the public CISA KEV catalog (as of 2025)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tor_exit_node_count": len(tor_nodes),
            "tor_source": "https://check.torproject.org/torbulkexitlist",
            "cisa_kev_total": 1100,  # approximate — live count via /enrichment/cyber-threats
            "cisa_kev_defence_relevant": 87,
            "cisa_kev_note": "Live count available at /enrichment/cyber-threats",
            "nvd_critical_7d_count": 12,  # approximate — live count via /enrichment/critical-cves
            "nvd_critical_note": "Live count available at /enrichment/critical-cves",
            "mitre_apt_group_count": len(threat_actors),
            "mitre_defence_targeting": len([a for a in threat_actors if "defence" in " ".join(a.get("targets", []))]),
            "active_apt_groups_2024_plus": len([a for a in threat_actors if a.get("last_active", "") >= "2024"]),
            "critical_risk_actors": len([a for a in threat_actors if a.get("risk_level") == "CRITICAL"]),
            "high_risk_actors": len([a for a in threat_actors if a.get("risk_level") == "HIGH"]),
            "combined_threat_score": _compute_threat_score(len(tor_nodes), threat_actors),
        }

        _set_cache("ioc_summary", summary)
        return summary

    async def assess_supplier_cyber_risk(self) -> list[dict]:
        """Cross-reference Canadian defence suppliers against the cyber threat landscape.

        Risk assessment based on:
        - Sector (aerospace/electronics/cyber = higher target value)
        - Foreign ownership (subsidiary of sanctioned-adjacent company = higher risk)
        - Known breaches of parent/peer companies
        - Active APT targeting of sector

        Returns list of supplier risk profiles for the Canadian defence industrial base.
        """
        cached = _check_cache("supplier_risk")
        if cached:
            return cached

        # Canadian defence industrial base — key suppliers (open-source registry)
        # Each assessed against: sector, ownership, breach history, APT targeting
        suppliers = [
            {
                "supplier": "Lockheed Martin Canada",
                "sector": "Aerospace / Weapons Systems",
                "parent": "Lockheed Martin Corporation (USA)",
                "foreign_owned": True,
                "known_parent_breaches": ["2011 RSA SecurID compromise", "F-35 data targeted"],
                "cyber_risk_level": "CRITICAL",
                "threat_actors": ["APT1", "APT28", "APT29", "Lazarus Group"],
                "rationale": (
                    "Primary F-35 JSF integrator. Parent has sustained targeted attacks since 2011. "
                    "Critical weapons platform data makes this a tier-1 APT target. "
                    "Active SIGINT collection by GRU and MSS documented."
                ),
                "key_programs": ["CF-18 replacement / F-35A", "CP-140 Aurora", "CH-47F Chinook"],
            },
            {
                "supplier": "L3Harris Canada (formerly L3 Technologies)",
                "sector": "Communications / EW / ISR",
                "parent": "L3Harris Technologies (USA)",
                "foreign_owned": True,
                "known_parent_breaches": ["2011 RSA SecurID compromise", "MOVEit 2023"],
                "cyber_risk_level": "CRITICAL",
                "threat_actors": ["APT28", "APT41", "Sandworm"],
                "rationale": (
                    "Provides tactical comms and EW systems. Parent L-3 was one of three major "
                    "defence contractors targeted in 2011 RSA cascade. MOVEit exposure in 2023 "
                    "affected L3Harris subsidiaries. EW/SIGINT data is priority for GRU/MSS."
                ),
                "key_programs": ["MIDS-JTRS", "Arctic surveillance", "RCAF comms"],
            },
            {
                "supplier": "CAE Inc.",
                "sector": "Simulation / Training / Defence Electronics",
                "parent": "CAE Inc. (Canadian, TSX: CAE)",
                "foreign_owned": False,
                "known_parent_breaches": [],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT28", "APT10", "Kimsuky"],
                "rationale": (
                    "CAE provides flight simulators and training systems for RCAF and NATO allies. "
                    "Simulator software contains detailed aircraft performance data. "
                    "APT10 MSP compromise pattern applies — CAE provides managed training services. "
                    "High value for adversary pilot training development."
                ),
                "key_programs": ["CF-18 simulator", "CH-148 Cyclone simulator", "NATO pilot training"],
            },
            {
                "supplier": "General Dynamics Canada",
                "sector": "C4ISR / Land Systems / Vehicles",
                "parent": "General Dynamics Corporation (USA)",
                "foreign_owned": True,
                "known_parent_breaches": ["2020 COVID spear-phishing campaign"],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT29", "APT28", "APT41"],
                "rationale": (
                    "Provides LAV 6.0 armoured vehicles and C4ISR systems. Parent targeted in "
                    "2020 COVID-themed spear-phishing. C4ISR architecture data is priority "
                    "collection for adversary military planners."
                ),
                "key_programs": ["LAV 6.0", "TacSatcom", "DND IT infrastructure"],
            },
            {
                "supplier": "Raytheon Canada",
                "sector": "Missiles / Radar / Defence Electronics",
                "parent": "RTX Corporation / Raytheon Technologies (USA)",
                "foreign_owned": True,
                "known_parent_breaches": ["2021 Accellion FTA breach"],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT33", "APT28", "Sandworm"],
                "rationale": (
                    "Provides NASAMS air defence systems and radar. Parent exposed via Accellion "
                    "in 2021. Missile and radar system specs are priority APT collection targets "
                    "particularly for IRGC/APT33 targeting aerospace sector."
                ),
                "key_programs": ["NASAMS (potential)", "RCAF radar systems"],
            },
            {
                "supplier": "MDA Space",
                "sector": "Satellite / Space Intelligence",
                "parent": "MDA Ltd (Canadian, TSX: MDA)",
                "foreign_owned": False,
                "known_parent_breaches": [],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT28", "APT29", "Turla"],
                "rationale": (
                    "Builds RADARSAT constellation and Canadarm. Satellite imagery intelligence "
                    "collection plans are high-value targets. Turla's satellite C2 hijacking "
                    "TTPs directly relevant. Space domain awareness data is priority Russian collection."
                ),
                "key_programs": ["RADARSAT Constellation", "Canadarm3", "ISED space programs"],
            },
            {
                "supplier": "MacDonald Dettwiler (MDA — Legacy division)",
                "sector": "Space / ISR / Geospatial",
                "parent": "MDA Ltd",
                "foreign_owned": False,
                "known_parent_breaches": [],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT28", "APT41"],
                "rationale": (
                    "ISR and geospatial data processing. SAR satellite tasking "
                    "and ground station operations are high-value targets for adversary "
                    "ISR mapping of Canadian capabilities."
                ),
                "key_programs": ["RADARSAT-2 ground segment", "Defence geospatial analytics"],
            },
            {
                "supplier": "Rheinmetall Canada",
                "sector": "Land Systems / Vehicles / Munitions",
                "parent": "Rheinmetall AG (Germany, DAX: RHM)",
                "foreign_owned": True,
                "known_parent_breaches": [],
                "cyber_risk_level": "MODERATE",
                "threat_actors": ["APT28", "APT29"],
                "rationale": (
                    "German parent Rheinmetall is a major NATO supplier. Armoured vehicle and "
                    "munitions production data targeted by Russian APTs seeking to assess "
                    "NATO industrial capacity for Ukraine support."
                ),
                "key_programs": ["TAPV", "LAV upgrade potential", "munitions production"],
            },
            {
                "supplier": "Babcock Canada",
                "sector": "Naval / Maintenance / MRO",
                "parent": "Babcock International Group (UK, LSE: BAB)",
                "foreign_owned": True,
                "known_parent_breaches": ["2020 cyber incident (Babcock UK)"],
                "cyber_risk_level": "MODERATE",
                "threat_actors": ["APT29", "Turla"],
                "rationale": (
                    "Parent Babcock UK confirmed a cyber incident in December 2020 affecting "
                    "classified UK naval maintenance data. Canadian operations share IT systems. "
                    "Naval MRO schedules are intelligence targets."
                ),
                "key_programs": ["HMCS maintenance", "Victoria-class submarine support"],
            },
            {
                "supplier": "Irving Shipbuilding",
                "sector": "Naval / Shipbuilding",
                "parent": "J.D. Irving Ltd (Canadian, private)",
                "foreign_owned": False,
                "known_parent_breaches": [],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT28", "APT29", "Sandworm"],
                "rationale": (
                    "Building Canadian Surface Combatants (15 warships). Ship design files, "
                    "weapon system integration specs, and build schedules are extremely high-value "
                    "targets. Shipbuilding sector has seen increased APT targeting since 2022 "
                    "related to Western naval expansion."
                ),
                "key_programs": ["Canadian Surface Combatant (CSC)", "Arctic Offshore Patrol Ships (AOPS)"],
            },
            {
                "supplier": "NGRAIN / Kongsberg Digital (Canada)",
                "sector": "Training / Simulation Software",
                "parent": "Kongsberg Defence & Aerospace (Norway)",
                "foreign_owned": True,
                "known_parent_breaches": [],
                "cyber_risk_level": "MODERATE",
                "threat_actors": ["APT28", "Turla"],
                "rationale": (
                    "Norwegian parent Kongsberg is a major NATO weapons supplier (NSM, NASAMS). "
                    "Canadian simulation software contains detailed platform models. "
                    "Russian APTs have targeted Norwegian defence firms."
                ),
                "key_programs": ["CF-18 training systems", "tactical simulation"],
            },
            {
                "supplier": "General Dynamics Mission Systems (Canada)",
                "sector": "C4I / Tactical Communications",
                "parent": "General Dynamics Corporation (USA)",
                "foreign_owned": True,
                "known_parent_breaches": ["2020 COVID spear-phishing"],
                "cyber_risk_level": "HIGH",
                "threat_actors": ["APT29", "APT41"],
                "rationale": (
                    "Provides secure tactical comms and mission systems. C4I architecture "
                    "knowledge allows adversaries to plan countermeasures and jamming. "
                    "High-priority collection for MSS and SVR."
                ),
                "key_programs": ["CanadaMission C4I", "RCAF tactical datalinks"],
            },
            {
                "supplier": "Ultra Electronics (Canada — now Cobham Advanced Electronic Systems)",
                "sector": "Electronic Warfare / Sonar",
                "parent": "Cobham plc (UK, private equity owned)",
                "foreign_owned": True,
                "known_parent_breaches": [],
                "cyber_risk_level": "MODERATE",
                "threat_actors": ["APT28", "APT33"],
                "rationale": (
                    "EW and sonar systems. Private equity ownership introduces supply chain risk. "
                    "Sonar signature databases for submarine detection are priority targets for "
                    "adversary submarine programs (Russia, China)."
                ),
                "key_programs": ["Victoria-class sonar", "maritime patrol EW"],
            },
            {
                "supplier": "Allen Vanguard",
                "sector": "Counter-IED / Electronic Attack",
                "parent": "Allen Vanguard (Canadian, private)",
                "foreign_owned": False,
                "known_parent_breaches": [],
                "cyber_risk_level": "LOW",
                "threat_actors": ["APT33", "Charming Kitten"],
                "rationale": (
                    "Counter-IED and electronic attack systems. Primarily relevant to Iran-linked "
                    "threat actors given IED/RCIED connection. Small company with limited external "
                    "attack surface but sensitive CIED effectiveness data."
                ),
                "key_programs": ["RCIED defeat systems", "spectrum management"],
            },
        ]

        _set_cache("supplier_risk", suppliers)
        return suppliers


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------

def _group_by(items: list[dict], key: str) -> dict[str, int]:
    """Count items by a given key value."""
    counts: dict[str, int] = {}
    for item in items:
        val = item.get(key, "Unknown")
        counts[val] = counts.get(val, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _risk_sort_key(supplier: dict) -> int:
    """Numeric sort key for risk level (CRITICAL=0, HIGH=1, MODERATE=2, LOW=3)."""
    order = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "LOW": 3}
    return order.get(supplier.get("cyber_risk_level", "LOW"), 3)


def _compute_threat_score(tor_count: int, actors: list[dict]) -> dict:
    """Compute a composite threat score from IOC inputs."""
    critical_count = len([a for a in actors if a.get("risk_level") == "CRITICAL"])
    high_count = len([a for a in actors if a.get("risk_level") == "HIGH"])
    active_count = len([a for a in actors if a.get("last_active", "") >= "2024"])

    # Score on 0-100 scale
    actor_score = min(100, (critical_count * 15) + (high_count * 5))
    tor_score = min(30, tor_count // 300)  # Tor count: ~8,000 nodes → ~26/30
    active_score = min(30, active_count * 3)

    composite = round((actor_score * 0.5) + (tor_score * 0.2) + (active_score * 0.3))

    return {
        "composite": composite,
        "actor_score": actor_score,
        "tor_indicator_score": tor_score,
        "active_group_score": active_score,
        "interpretation": (
            "HIGH" if composite >= 70
            else "ELEVATED" if composite >= 50
            else "MODERATE" if composite >= 30
            else "LOW"
        ),
    }
