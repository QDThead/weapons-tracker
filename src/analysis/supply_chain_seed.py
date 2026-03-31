"""BOM (Bill of Materials) seed script for the PSI supply-chain knowledge graph.

Populates the database with curated data for major weapon platforms,
their subsystems, components, critical materials, supply routes,
and initial disruption alerts.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.database import SessionLocal, init_db
from src.storage.models import (
    Country,
    WeaponSystem,
    SupplyChainMaterial,
    SupplyChainNode,
    SupplyChainEdge,
    SupplyChainRoute,
    SupplyChainAlert,
    SupplyChainNodeType,
    AlertType,
    MaterialCategory,
)
from src.storage.persistence import PersistenceService
from src.ingestion.critical_minerals import CriticalMineralsClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform definitions (link to existing WeaponSystem by designation)
# ---------------------------------------------------------------------------

PLATFORMS = [
    "F-35A Lightning II",
    "F-16 Fighting Falcon",
    "F/A-18E/F Super Hornet",
    "Leopard 2A7",
    "M1A2 Abrams",
    "T-90M",
    "Su-35S",
    "S-400 Triumf",
    "Patriot PAC-3",
    "HIMARS",
    "Type 054A",
    "Eurofighter Typhoon",
    "Rafale",
    "Gripen E",
    "CH-47F Chinook",
    "AH-64E Apache",
    "UH-60M Black Hawk",
    "P-8A Poseidon",
    "Virginia-class SSN",
    "Arleigh Burke DDG",
]

# ---------------------------------------------------------------------------
# Subsystem definitions (company_name provided)
# ---------------------------------------------------------------------------

SUBSYSTEMS: list[dict[str, str]] = [
    {"name": "F135-PW-100 Engine", "company_name": "Pratt & Whitney"},
    {"name": "F110-GE-129 Engine", "company_name": "GE Aerospace"},
    {"name": "F414-GE-400 Engine", "company_name": "GE Aerospace"},
    {"name": "EJ200 Engine", "company_name": "Eurojet"},
    {"name": "M88-2 Engine", "company_name": "Safran"},
    {"name": "RM12 Engine", "company_name": "Volvo Aero"},
    {"name": "MTU MB 873 Engine", "company_name": "MTU"},
    {"name": "AGT-1500 Engine", "company_name": "Honeywell"},
    {"name": "AL-41F1S Engine", "company_name": "UEC Saturn"},
    {"name": "T700-GE-401C Engine", "company_name": "GE Aerospace"},
    {"name": "AN/APG-81 AESA Radar", "company_name": "Northrop Grumman"},
    {"name": "AN/APG-68 Radar", "company_name": "Northrop Grumman"},
    {"name": "AN/APG-79 AESA Radar", "company_name": "Raytheon"},
    {"name": "CAPTOR-E Radar", "company_name": "Euroradar"},
    {"name": "RBE2 AESA Radar", "company_name": "Thales"},
    {"name": "Irbis-E Radar", "company_name": "NIIP Tikhomirov"},
    {"name": "92N6E Radar", "company_name": "Almaz-Antey"},
    {"name": "AN/MPQ-65 Radar", "company_name": "Raytheon"},
    {"name": "Mk 41 VLS", "company_name": "Lockheed Martin"},
    {"name": "AEGIS Combat System", "company_name": "Lockheed Martin"},
]

# ---------------------------------------------------------------------------
# Component definitions (company_name where known)
# ---------------------------------------------------------------------------

COMPONENTS: list[dict[str, Optional[str]]] = [
    {"name": "Turbine Blades", "company_name": None},
    {"name": "AESA Antenna Modules", "company_name": None},
    {"name": "Li-ion Battery Pack", "company_name": None},
    {"name": "Guidance Computer", "company_name": None},
    {"name": "Inertial Navigation Unit", "company_name": "Honeywell"},
    {"name": "GPS Receiver Module", "company_name": None},
    {"name": "Infrared Seeker", "company_name": None},
    {"name": "Composite Airframe Panels", "company_name": None},
    {"name": "Ceramic Armor Plates", "company_name": None},
    {"name": "Depleted Uranium Penetrator", "company_name": None},
    {"name": "Solid Rocket Motor", "company_name": "Aerojet Rocketdyne"},
    {"name": "Missile Warhead", "company_name": None},
    {"name": "Hydraulic Actuators", "company_name": None},
    {"name": "Cockpit Displays", "company_name": None},
    {"name": "EW Suite", "company_name": None},
    {"name": "FLIR Turret", "company_name": None},
    {"name": "Ammunition Feed System", "company_name": None},
    {"name": "Nuclear Reactor Core", "company_name": None},
    {"name": "Sonar Array", "company_name": None},
    {"name": "Fire Control Computer", "company_name": None},
]

# ---------------------------------------------------------------------------
# Platform -> Subsystem/Component BOM edges (dependency_type = "contains")
# ---------------------------------------------------------------------------

PLATFORM_SUBSYSTEM_EDGES: dict[str, list[str]] = {
    "F-35A Lightning II": [
        "F135-PW-100 Engine",
        "AN/APG-81 AESA Radar",
        "EW Suite",
        "Li-ion Battery Pack",
        "Composite Airframe Panels",
        "Cockpit Displays",
        "Guidance Computer",
    ],
    "F-16 Fighting Falcon": [
        "F110-GE-129 Engine",
        "AN/APG-68 Radar",
        "FLIR Turret",
        "Guidance Computer",
    ],
    "F/A-18E/F Super Hornet": [
        "F414-GE-400 Engine",
        "AN/APG-79 AESA Radar",
        "EW Suite",
    ],
    "Eurofighter Typhoon": [
        "EJ200 Engine",
        "CAPTOR-E Radar",
    ],
    "Rafale": [
        "M88-2 Engine",
        "RBE2 AESA Radar",
    ],
    "Leopard 2A7": [
        "MTU MB 873 Engine",
        "Ceramic Armor Plates",
        "Fire Control Computer",
    ],
    "M1A2 Abrams": [
        "AGT-1500 Engine",
        "Depleted Uranium Penetrator",
        "Ceramic Armor Plates",
        "Fire Control Computer",
    ],
    "Su-35S": [
        "AL-41F1S Engine",
        "Irbis-E Radar",
    ],
    "S-400 Triumf": [
        "92N6E Radar",
        "Solid Rocket Motor",
        "Missile Warhead",
        "Infrared Seeker",
    ],
    "Patriot PAC-3": [
        "AN/MPQ-65 Radar",
        "Solid Rocket Motor",
        "Guidance Computer",
    ],
    "HIMARS": [
        "Guidance Computer",
        "Solid Rocket Motor",
        "GPS Receiver Module",
    ],
    "Arleigh Burke DDG": [
        "AEGIS Combat System",
        "Mk 41 VLS",
        "Sonar Array",
    ],
    "Virginia-class SSN": [
        "Nuclear Reactor Core",
        "Sonar Array",
        "Mk 41 VLS",
    ],
    "AH-64E Apache": [
        "T700-GE-401C Engine",
        "FLIR Turret",
        "Fire Control Computer",
    ],
}

# ---------------------------------------------------------------------------
# Subsystem -> Component edges (dependency_type = "contains")
# ---------------------------------------------------------------------------

SUBSYSTEM_COMPONENT_EDGES: dict[str, list[str]] = {
    "F135-PW-100 Engine": ["Turbine Blades"],
    "F110-GE-129 Engine": ["Turbine Blades"],
    "F414-GE-400 Engine": ["Turbine Blades"],
    "EJ200 Engine": ["Turbine Blades"],
    "M88-2 Engine": ["Turbine Blades"],
    "RM12 Engine": ["Turbine Blades"],
    "AGT-1500 Engine": ["Turbine Blades"],
    "AL-41F1S Engine": ["Turbine Blades"],
    "T700-GE-401C Engine": ["Turbine Blades"],
    "AN/APG-81 AESA Radar": ["AESA Antenna Modules"],
    "AN/APG-79 AESA Radar": ["AESA Antenna Modules"],
    "CAPTOR-E Radar": ["AESA Antenna Modules"],
    "RBE2 AESA Radar": ["AESA Antenna Modules"],
    "AEGIS Combat System": ["Fire Control Computer", "AESA Antenna Modules"],
}

# ---------------------------------------------------------------------------
# Component -> Material edges (dependency_type = "requires")
# Each tuple: (material_name, sole_source, alternative_count)
# ---------------------------------------------------------------------------

COMPONENT_MATERIAL_EDGES: dict[str, list[tuple[str, bool, int]]] = {
    "Turbine Blades": [
        ("Nickel", False, 2),
        ("Cobalt", False, 2),
        ("Rhenium", False, 2),
    ],
    "AESA Antenna Modules": [
        ("Gallium", True, 0),
        ("Germanium", False, 1),
    ],
    "Li-ion Battery Pack": [
        ("Lithium", False, 1),
        ("Cobalt", False, 1),
    ],
    "Guidance Computer": [
        ("Silicon", False, 2),
        ("Germanium", False, 1),
        ("Tantalum", False, 1),
        ("Rare Earth Elements", False, 1),
    ],
    "Composite Airframe Panels": [
        ("Titanium", False, 1),
        ("Graphite", False, 1),
    ],
    "Ceramic Armor Plates": [
        ("Chromium", False, 1),
        ("Manganese", False, 1),
    ],
    "Depleted Uranium Penetrator": [
        ("Uranium", True, 0),
    ],
    "Solid Rocket Motor": [
        ("Manganese", False, 1),
        ("Copper", False, 1),
    ],
    "Nuclear Reactor Core": [
        ("Uranium", False, 1),
        ("Zirconium", False, 1),
        ("Hafnium", True, 0),
    ],
    "Infrared Seeker": [
        ("Germanium", True, 0),
    ],
    "GPS Receiver Module": [
        ("Gallium", False, 1),
        ("Silicon", False, 1),
    ],
    "Inertial Navigation Unit": [
        ("Beryllium", True, 0),
        ("Germanium", False, 1),
    ],
    "Sonar Array": [
        ("Niobium", False, 1),
        ("Copper", False, 1),
    ],
    "Fire Control Computer": [
        ("Silicon", False, 1),
        ("Tantalum", False, 1),
        ("Gallium", False, 1),
    ],
    "EW Suite": [
        ("Gallium", False, 1),
        ("Germanium", False, 1),
        ("Rare Earth Elements", False, 1),
    ],
    "FLIR Turret": [
        ("Germanium", True, 0),
    ],
    "Cockpit Displays": [
        ("Indium", False, 1),
        ("Silicon", False, 1),
    ],
    "Hydraulic Actuators": [
        ("Chromium", False, 1),
        ("Nickel", False, 1),
    ],
    "Missile Warhead": [
        ("Tungsten", False, 1),
        ("Copper", False, 1),
    ],
    "Ammunition Feed System": [
        ("Manganese", False, 1),
        ("Chromium", False, 1),
    ],
}

# ---------------------------------------------------------------------------
# Supply routes: (origin, destination, chokepoints, distance_nm, risk, notes)
# ---------------------------------------------------------------------------

SUPPLY_ROUTES: list[dict] = [
    {
        "origin": "United States",
        "destination": "Saudi Arabia",
        "chokepoints": ["Strait of Hormuz"],
        "distance_nm": 7000,
        "risk_score": 60,
        "notes": "Primary US-Gulf arms corridor; Hormuz is high-risk chokepoint",
    },
    {
        "origin": "United States",
        "destination": "Japan",
        "chokepoints": ["Panama Canal"],
        "distance_nm": 5500,
        "risk_score": 45,
        "notes": "Pacific alliance resupply route via Panama",
    },
    {
        "origin": "United States",
        "destination": "South Korea",
        "chokepoints": ["Panama Canal"],
        "distance_nm": 5800,
        "risk_score": 45,
        "notes": "Korean Peninsula defense supply line",
    },
    {
        "origin": "United States",
        "destination": "Australia",
        "chokepoints": ["Panama Canal", "Strait of Malacca"],
        "distance_nm": 8000,
        "risk_score": 70,
        "notes": "AUKUS supply route; dual chokepoint exposure",
    },
    {
        "origin": "United States",
        "destination": "Israel",
        "chokepoints": ["Strait of Gibraltar"],
        "distance_nm": 5500,
        "risk_score": 40,
        "notes": "US-Israel strategic resupply corridor",
    },
    {
        "origin": "United States",
        "destination": "Taiwan",
        "chokepoints": ["Panama Canal", "Bashi Channel"],
        "distance_nm": 7200,
        "risk_score": 75,
        "notes": "High-risk contingency route; Bashi Channel contested",
    },
    {
        "origin": "Russia",
        "destination": "India",
        "chokepoints": ["Suez Canal"],
        "distance_nm": 4500,
        "risk_score": 50,
        "notes": "Major Russian arms export corridor to India",
    },
    {
        "origin": "Russia",
        "destination": "China",
        "chokepoints": [],
        "distance_nm": 0,
        "risk_score": 10,
        "notes": "Direct overland rail/road supply; no maritime chokepoints",
    },
    {
        "origin": "Russia",
        "destination": "Algeria",
        "chokepoints": ["Bosphorus", "Strait of Gibraltar"],
        "distance_nm": 3000,
        "risk_score": 65,
        "notes": "Black Sea exit through Bosphorus plus Gibraltar transit",
    },
    {
        "origin": "Russia",
        "destination": "Egypt",
        "chokepoints": ["Bosphorus", "Suez Canal"],
        "distance_nm": 2500,
        "risk_score": 65,
        "notes": "Dual chokepoint exposure through Turkish straits",
    },
    {
        "origin": "France",
        "destination": "India",
        "chokepoints": ["Suez Canal", "Bab el-Mandeb"],
        "distance_nm": 5500,
        "risk_score": 65,
        "notes": "Rafale and submarine delivery route; Red Sea risk",
    },
    {
        "origin": "Germany",
        "destination": "Norway",
        "chokepoints": ["English Channel"],
        "distance_nm": 600,
        "risk_score": 20,
        "notes": "Short North Sea transit; low chokepoint risk",
    },
    {
        "origin": "China",
        "destination": "Pakistan",
        "chokepoints": [],
        "distance_nm": 0,
        "risk_score": 10,
        "notes": "Karakoram Highway / CPEC overland corridor",
    },
    {
        "origin": "China",
        "destination": "Myanmar",
        "chokepoints": [],
        "distance_nm": 0,
        "risk_score": 10,
        "notes": "Direct overland supply via Yunnan border",
    },
    {
        "origin": "China",
        "destination": "Bangladesh",
        "chokepoints": ["Strait of Malacca"],
        "distance_nm": 2800,
        "risk_score": 55,
        "notes": "Maritime route through contested Malacca Strait",
    },
    {
        "origin": "South Korea",
        "destination": "Indonesia",
        "chokepoints": ["Strait of Malacca"],
        "distance_nm": 2500,
        "risk_score": 55,
        "notes": "K-defense export route; Malacca exposure",
    },
    {
        "origin": "United Kingdom",
        "destination": "Canada",
        "chokepoints": ["English Channel"],
        "distance_nm": 2800,
        "risk_score": 25,
        "notes": "NATO North Atlantic supply route",
    },
    {
        "origin": "Congo (DRC)",
        "destination": "China",
        "chokepoints": ["Bab el-Mandeb", "Strait of Malacca"],
        "distance_nm": 8500,
        "risk_score": 75,
        "notes": "Critical cobalt supply route; dual chokepoint, long distance",
    },
    {
        "origin": "Chile",
        "destination": "United States",
        "chokepoints": ["Panama Canal"],
        "distance_nm": 4200,
        "risk_score": 45,
        "notes": "Lithium and copper mineral supply route",
    },
    {
        "origin": "Australia",
        "destination": "Japan",
        "chokepoints": ["Strait of Malacca"],
        "distance_nm": 4000,
        "risk_score": 55,
        "notes": "Rare earth and mineral supply route to Japan",
    },
]

# ---------------------------------------------------------------------------
# Initial disruption alerts
# ---------------------------------------------------------------------------

ALERTS: list[dict] = [
    {
        "alert_type": AlertType.MATERIAL_SHORTAGE,
        "severity": 5,
        "title": "Gallium export controls by China",
        "description": (
            "China implemented export controls on gallium and germanium "
            "effective August 2023, affecting global supply of critical "
            "semiconductor and radar materials. China produces ~80% of "
            "world gallium. Impact cascades to AESA radar modules across "
            "all Western fighter programs."
        ),
        "affected_material": "Gallium",
        "affected_country": "China",
    },
    {
        "alert_type": AlertType.CONCENTRATION_RISK,
        "severity": 4,
        "title": "Cobalt supply concentration in DRC",
        "description": (
            "Democratic Republic of Congo produces ~73% of global cobalt. "
            "Political instability, artisanal mining concerns, and Chinese "
            "ownership of major mines create concentration risk for battery "
            "packs and turbine blade production."
        ),
        "affected_material": "Cobalt",
        "affected_country": "Congo (DRC)",
    },
    {
        "alert_type": AlertType.CONCENTRATION_RISK,
        "severity": 5,
        "title": "Rare earth processing monopoly - China",
        "description": (
            "China controls ~60% of rare earth mining and ~90% of "
            "processing/refining. Rare earths are essential for guidance "
            "computers, EW suites, and precision munitions. No near-term "
            "alternative processing capacity exists at scale."
        ),
        "affected_material": "Rare Earth Elements",
        "affected_country": "China",
    },
    {
        "alert_type": AlertType.SANCTIONS_RISK,
        "severity": 4,
        "title": "Titanium supply from Russia under sanctions pressure",
        "description": (
            "Russia (VSMPO-AVISMA) supplies ~35% of aerospace-grade "
            "titanium globally. Western sanctions and export controls "
            "threaten composite airframe panel production for F-35 and "
            "other platforms. Alternative sourcing from Japan and Kazakhstan "
            "is scaling but insufficient."
        ),
        "affected_material": "Titanium",
        "affected_country": "Russia",
    },
    {
        "alert_type": AlertType.CHOKEPOINT_BLOCKED,
        "severity": 3,
        "title": "Strait of Hormuz tension affecting Gulf routes",
        "description": (
            "Periodic Iranian threats and IRGC naval activity in the "
            "Strait of Hormuz elevate risk for US-Gulf arms supply "
            "routes. ~30% of seaborne oil and significant defense "
            "materiel transits Hormuz daily."
        ),
        "affected_material": None,
        "affected_country": "Iran",
    },
    {
        "alert_type": AlertType.CHOKEPOINT_BLOCKED,
        "severity": 5,
        "title": "Taiwan Strait contingency - semiconductor supply",
        "description": (
            "A Taiwan Strait crisis would disrupt ~60% of global "
            "advanced semiconductor production (TSMC). Impact on "
            "guidance computers, fire control systems, and radar "
            "electronics would be catastrophic for all Western "
            "defense platforms."
        ),
        "affected_material": "Silicon",
        "affected_country": "China",
    },
    {
        "alert_type": AlertType.DEMAND_SURGE,
        "severity": 3,
        "title": "European demand surge for artillery ammunition",
        "description": (
            "Ukraine conflict has driven 5-10x increase in European "
            "artillery ammunition demand. Manganese, chromium, and "
            "copper consumption for ammunition feed systems and shell "
            "casings is straining existing supply chains."
        ),
        "affected_material": "Manganese",
        "affected_country": None,
    },
    {
        "alert_type": AlertType.CONCENTRATION_RISK,
        "severity": 4,
        "title": "Tungsten sole-source risk for AP ammunition",
        "description": (
            "China produces ~80% of global tungsten. Tungsten is "
            "essential for armor-piercing ammunition and missile warheads. "
            "Limited recycling capacity and no significant Western mining "
            "create acute sole-source exposure."
        ),
        "affected_material": "Tungsten",
        "affected_country": "China",
    },
]


# ===========================================================================
# Seeder class
# ===========================================================================


class SupplyChainSeeder:
    """Seeds the PSI supply-chain knowledge graph with curated BOM data."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.ps = PersistenceService(session)
        # Caches for node lookups (name -> SupplyChainNode)
        self._node_cache: dict[str, SupplyChainNode] = {}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def seed_all(self) -> dict[str, int]:
        """Run all seed steps and return counts."""
        counts: dict[str, int] = {}

        logger.info("=== PSI Supply Chain Seed: starting ===")

        counts["materials"] = self._seed_materials()
        counts["nodes"] = self._seed_nodes()
        counts["edges"] = self._seed_edges()
        counts["routes"] = self._seed_routes()
        counts["alerts"] = self._seed_alerts()

        logger.info("=== PSI Supply Chain Seed: complete === %s", counts)
        return counts

    # ------------------------------------------------------------------
    # Step 1 — Materials
    # ------------------------------------------------------------------

    def _seed_materials(self) -> int:
        """Seed critical materials from CriticalMineralsClient."""
        logger.info("Seeding materials ...")
        material_records = CriticalMineralsClient.get_seeded_materials()
        return self.ps.store_materials(material_records)

    # ------------------------------------------------------------------
    # Step 2 — Nodes (platforms, subsystems, components, materials)
    # ------------------------------------------------------------------

    def _seed_nodes(self) -> int:
        """Seed all supply-chain graph nodes."""
        total = 0
        total += self._seed_platform_nodes()
        total += self._seed_subsystem_nodes()
        total += self._seed_component_nodes()
        total += self._seed_material_nodes()
        # Populate lookup cache for edge creation
        self._build_node_cache()
        return total

    def _seed_platform_nodes(self) -> int:
        """Create platform nodes linked to existing WeaponSystem records."""
        logger.info("Seeding platform nodes ...")
        records: list[dict] = []
        for designation in PLATFORMS:
            weapon = self.session.execute(
                select(WeaponSystem).where(
                    WeaponSystem.designation == designation
                )
            ).scalar_one_or_none()

            rec: dict = {
                "node_type": SupplyChainNodeType.PLATFORM,
                "name": designation,
                "description": f"Weapon platform: {designation}",
            }
            if weapon:
                rec["weapon_system_id"] = weapon.id
                if weapon.producer_country_id:
                    rec["country_id"] = weapon.producer_country_id
            records.append(rec)

        return self.ps.store_supply_chain_nodes(records)

    def _seed_subsystem_nodes(self) -> int:
        """Create subsystem nodes with company attribution."""
        logger.info("Seeding subsystem nodes ...")
        records: list[dict] = []
        for sub in SUBSYSTEMS:
            records.append({
                "node_type": SupplyChainNodeType.SUBSYSTEM,
                "name": sub["name"],
                "description": f"Subsystem: {sub['name']}",
                "company_name": sub["company_name"],
            })
        return self.ps.store_supply_chain_nodes(records)

    def _seed_component_nodes(self) -> int:
        """Create component nodes."""
        logger.info("Seeding component nodes ...")
        records: list[dict] = []
        for comp in COMPONENTS:
            rec: dict = {
                "node_type": SupplyChainNodeType.COMPONENT,
                "name": comp["name"],
                "description": f"Component: {comp['name']}",
            }
            if comp.get("company_name"):
                rec["company_name"] = comp["company_name"]
            records.append(rec)
        return self.ps.store_supply_chain_nodes(records)

    def _seed_material_nodes(self) -> int:
        """Create material nodes linked to SupplyChainMaterial records."""
        logger.info("Seeding material nodes ...")
        materials = self.session.execute(
            select(SupplyChainMaterial)
        ).scalars().all()

        records: list[dict] = []
        for mat in materials:
            records.append({
                "node_type": SupplyChainNodeType.MATERIAL,
                "name": mat.name,
                "description": f"Critical material: {mat.name}",
                "material_id": mat.id,
            })
        return self.ps.store_supply_chain_nodes(records)

    # ------------------------------------------------------------------
    # Node cache
    # ------------------------------------------------------------------

    def _build_node_cache(self) -> None:
        """Load all supply-chain nodes into an in-memory lookup."""
        nodes = self.session.execute(
            select(SupplyChainNode)
        ).scalars().all()
        for node in nodes:
            # Key by (node_type, name) for uniqueness
            key = f"{node.node_type.value}::{node.name}"
            self._node_cache[key] = node

    def _get_node(self, node_type: str, name: str) -> Optional[SupplyChainNode]:
        """Look up a cached node by type and name, with fallback to other types."""
        key = f"{node_type}::{name}"
        node = self._node_cache.get(key)
        if node is None:
            # Fallback: some items may be stored under a different node type
            for fallback in ("component", "subsystem", "material", "platform"):
                if fallback == node_type:
                    continue
                alt_key = f"{fallback}::{name}"
                node = self._node_cache.get(alt_key)
                if node:
                    return node
            logger.warning("Node not found: %s / %s", node_type, name)
        return node

    # ------------------------------------------------------------------
    # Step 3 — Edges
    # ------------------------------------------------------------------

    def _seed_edges(self) -> int:
        """Seed all BOM dependency edges."""
        total = 0
        total += self._seed_platform_subsystem_edges()
        total += self._seed_subsystem_component_edges()
        total += self._seed_component_material_edges()
        return total

    def _seed_platform_subsystem_edges(self) -> int:
        """Platform -> Subsystem/Component 'contains' edges."""
        logger.info("Seeding platform -> subsystem/component edges ...")
        records: list[dict] = []

        for platform_name, children in PLATFORM_SUBSYSTEM_EDGES.items():
            platform_node = self._get_node(
                SupplyChainNodeType.PLATFORM.value, platform_name
            )
            if not platform_node:
                continue

            for child_name in children:
                # Child could be a subsystem or a component
                child_node = self._get_node(
                    SupplyChainNodeType.SUBSYSTEM.value, child_name
                )
                if child_node is None:
                    child_node = self._get_node(
                        SupplyChainNodeType.COMPONENT.value, child_name
                    )
                if child_node is None:
                    continue

                records.append({
                    "parent_node_id": child_node.id,
                    "child_node_id": platform_node.id,
                    "dependency_type": "contains",
                    "confidence": 0.9,
                    "source": "manual",
                })

        return self.ps.store_supply_chain_edges(records)

    def _seed_subsystem_component_edges(self) -> int:
        """Subsystem -> Component 'contains' edges."""
        logger.info("Seeding subsystem -> component edges ...")
        records: list[dict] = []

        for subsystem_name, children in SUBSYSTEM_COMPONENT_EDGES.items():
            subsystem_node = self._get_node(
                SupplyChainNodeType.SUBSYSTEM.value, subsystem_name
            )
            if not subsystem_node:
                continue

            for child_name in children:
                child_node = self._get_node(
                    SupplyChainNodeType.COMPONENT.value, child_name
                )
                if child_node is None:
                    continue

                records.append({
                    "parent_node_id": child_node.id,
                    "child_node_id": subsystem_node.id,
                    "dependency_type": "contains",
                    "confidence": 0.9,
                    "source": "manual",
                })

        return self.ps.store_supply_chain_edges(records)

    def _seed_component_material_edges(self) -> int:
        """Component -> Material 'requires' edges."""
        logger.info("Seeding component -> material edges ...")
        records: list[dict] = []

        for component_name, materials in COMPONENT_MATERIAL_EDGES.items():
            component_node = self._get_node(
                SupplyChainNodeType.COMPONENT.value, component_name
            )
            if not component_node:
                continue

            for material_name, sole_source, alt_count in materials:
                material_node = self._get_node(
                    SupplyChainNodeType.MATERIAL.value, material_name
                )
                if material_node is None:
                    continue

                records.append({
                    "parent_node_id": material_node.id,
                    "child_node_id": component_node.id,
                    "dependency_type": "requires",
                    "is_sole_source": sole_source,
                    "alternative_count": alt_count,
                    "confidence": 0.85,
                    "source": "manual",
                })

        return self.ps.store_supply_chain_edges(records)

    # ------------------------------------------------------------------
    # Step 4 — Routes
    # ------------------------------------------------------------------

    def _seed_routes(self) -> int:
        """Seed major defense supply routes with chokepoint metadata."""
        logger.info("Seeding supply routes ...")
        records: list[dict] = []

        for route in SUPPLY_ROUTES:
            origin = self.ps.get_or_create_country(route["origin"])
            dest = self.ps.get_or_create_country(route["destination"])

            route_name = f"{route['origin']} -> {route['destination']}"

            records.append({
                "origin_country_id": origin.id,
                "destination_country_id": dest.id,
                "route_name": route_name,
                "chokepoints": json.dumps(route["chokepoints"]),
                "distance_nm": route["distance_nm"],
                "risk_score": route["risk_score"],
                "notes": route.get("notes"),
            })

        return self.ps.store_supply_chain_routes(records)

    # ------------------------------------------------------------------
    # Step 5 — Alerts
    # ------------------------------------------------------------------

    def _seed_alerts(self) -> int:
        """Seed initial supply-chain disruption alerts."""
        logger.info("Seeding supply-chain alerts ...")
        records: list[dict] = []

        for alert_def in ALERTS:
            rec: dict = {
                "alert_type": alert_def["alert_type"],
                "severity": alert_def["severity"],
                "title": alert_def["title"],
                "description": alert_def["description"],
            }

            # Link to affected material node if specified
            mat_name = alert_def.get("affected_material")
            if mat_name:
                mat_node = self._get_node(
                    SupplyChainNodeType.MATERIAL.value, mat_name
                )
                if mat_node:
                    rec["affected_node_id"] = mat_node.id

            # Link to affected country if specified
            country_name = alert_def.get("affected_country")
            if country_name:
                country = self.ps.get_or_create_country(country_name)
                rec["affected_country_id"] = country.id

            records.append(rec)

        return self.ps.store_supply_chain_alerts(records)


# ===========================================================================
# CLI entry point
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("Initializing database ...")
    init_db()

    print("Opening session ...")
    session = SessionLocal()

    try:
        seeder = SupplyChainSeeder(session)
        counts = seeder.seed_all()

        print("\n--- Supply Chain Seed Summary ---")
        for key, value in counts.items():
            print(f"  {key:>12s}: {value} new records")
        print("--- Done ---\n")
    finally:
        session.close()
