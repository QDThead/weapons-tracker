"""NetworkX-based knowledge graph for defense supply chain analysis.

Builds a directed graph from the PSI database tables and provides
traversal methods for BOM explosion, disruption propagation,
alternative supplier lookup, and D3.js export.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.storage.models import (
    Country,
    WeaponSystem,
    ArmsTransfer,
    DefenseCompany,
    SupplyChainMaterial,
    SupplyChainNode,
    SupplyChainEdge,
    SupplyChainRoute,
    SupplyChainNodeType,
)

logger = logging.getLogger(__name__)


@dataclass
class AffectedItem:
    """An item affected by a disruption event."""
    node_id: int
    node_name: str
    node_type: str
    depth: int
    severity: float
    path: list[str] = field(default_factory=list)


@dataclass
class BOMEntry:
    """A single entry in an exploded bill of materials."""
    node_id: int
    name: str
    node_type: str
    company: str | None
    country: str | None
    is_sole_source: bool
    confidence: float
    children: list[BOMEntry] = field(default_factory=list)


class SupplyChainGraph:
    """Multi-layer knowledge graph for defense supply chain analysis.

    Constructed from PSI database tables. Provides graph traversal for:
    - BOM explosion (weapon -> components -> materials -> source countries)
    - Disruption propagation (material disruption -> affected platforms)
    - Alternative supplier lookup
    - D3.js-ready JSON export for visualization
    """

    def __init__(self, session: Session):
        self.session = session
        self.graph = nx.DiGraph()
        self._node_lookup: dict[int, dict] = {}

    def build(self) -> nx.DiGraph:
        """Construct the full graph from database records."""
        self.graph.clear()
        self._node_lookup.clear()

        self._add_supply_chain_nodes()
        self._add_supply_chain_edges()
        self._add_country_nodes()
        self._add_material_country_edges()

        logger.info(
            "Supply chain graph built: %d nodes, %d edges",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return self.graph

    # ------------------------------------------------------------------ build

    def _add_supply_chain_nodes(self) -> None:
        """Add all SupplyChainNode records as graph nodes."""
        nodes = self.session.execute(
            select(SupplyChainNode)
        ).scalars().all()

        for node in nodes:
            nid = f"SCN:{node.id}"
            attrs = {
                "db_id": node.id,
                "name": node.name,
                "node_type": node.node_type.value if node.node_type else "unknown",
                "description": node.description or "",
                "company": node.company_name or "",
                "country_id": node.country_id,
                "material_id": node.material_id,
                "weapon_system_id": node.weapon_system_id,
                "risk_score": node.risk_score or 0,
            }
            self.graph.add_node(nid, **attrs)
            self._node_lookup[node.id] = attrs

    def _add_supply_chain_edges(self) -> None:
        """Add all SupplyChainEdge records as graph edges."""
        edges = self.session.execute(
            select(SupplyChainEdge)
        ).scalars().all()

        for edge in edges:
            src = f"SCN:{edge.parent_node_id}"
            dst = f"SCN:{edge.child_node_id}"
            if src in self.graph and dst in self.graph:
                self.graph.add_edge(
                    src, dst,
                    dependency_type=edge.dependency_type,
                    is_sole_source=edge.is_sole_source,
                    alternative_count=edge.alternative_count,
                    confidence=edge.confidence or 0.5,
                    source=edge.source or "",
                )

    def _add_country_nodes(self) -> None:
        """Add country nodes for material source countries."""
        countries = self.session.execute(select(Country)).scalars().all()
        for c in countries:
            nid = f"CTR:{c.id}"
            self.graph.add_node(nid, **{
                "db_id": c.id,
                "name": c.name,
                "node_type": "country",
                "iso3": c.iso_alpha3 or "",
                "region": c.region or "",
            })

    def _add_material_country_edges(self) -> None:
        """Link material nodes to their source countries via top_producers."""
        materials = self.session.execute(
            select(SupplyChainMaterial)
        ).scalars().all()

        for mat in materials:
            if not mat.top_producers:
                continue
            try:
                producers = json.loads(mat.top_producers)
            except (json.JSONDecodeError, TypeError):
                continue

            # Find the SCN node for this material
            mat_node = self.session.execute(
                select(SupplyChainNode).where(
                    SupplyChainNode.material_id == mat.id,
                    SupplyChainNode.node_type == SupplyChainNodeType.MATERIAL,
                )
            ).scalar_one_or_none()

            if not mat_node:
                continue

            mat_nid = f"SCN:{mat_node.id}"

            for prod in producers:
                country_name = prod.get("country", "")
                country = self.session.execute(
                    select(Country).where(Country.name == country_name)
                ).scalar_one_or_none()
                if country:
                    ctr_nid = f"CTR:{country.id}"
                    self.graph.add_edge(
                        ctr_nid, mat_nid,
                        dependency_type="produces_material",
                        pct=prod.get("pct", 0),
                        tonnes=prod.get("tonnes", 0),
                    )

    # --------------------------------------------------------- BOM explosion

    def explode_bom(self, platform_name: str) -> BOMEntry | None:
        """Trace all dependencies for a weapon platform.

        Returns a nested BOMEntry tree: platform -> subsystems -> components -> materials.
        """
        root_node = self.session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.node_type == SupplyChainNodeType.PLATFORM,
                SupplyChainNode.name == platform_name,
            )
        ).scalar_one_or_none()

        if not root_node:
            return None

        return self._build_bom_tree(root_node.id, visited=set())

    def _build_bom_tree(self, node_id: int, visited: set[int]) -> BOMEntry:
        """Recursively build a BOM tree from a node."""
        if node_id in visited:
            info = self._node_lookup.get(node_id, {})
            return BOMEntry(
                node_id=node_id,
                name=info.get("name", "unknown"),
                node_type=info.get("node_type", "unknown"),
                company=info.get("company"),
                country=None,
                is_sole_source=False,
                confidence=0,
            )

        visited.add(node_id)
        info = self._node_lookup.get(node_id, {})
        nid = f"SCN:{node_id}"

        # Country name lookup
        country_name = None
        if info.get("country_id"):
            country = self.session.execute(
                select(Country).where(Country.id == info["country_id"])
            ).scalar_one_or_none()
            if country:
                country_name = country.name

        entry = BOMEntry(
            node_id=node_id,
            name=info.get("name", "unknown"),
            node_type=info.get("node_type", "unknown"),
            company=info.get("company"),
            country=country_name,
            is_sole_source=False,
            confidence=1.0,
        )

        # Find children (edges where this node is the child, i.e. this node
        # depends on parent nodes — but for BOM we want: what does this platform
        # contain? That means edges where this is the *child_node_id* in a
        # "contains" relationship go the other way. Actually in our model:
        # parent_node (dependency) -> child_node (dependent).
        # So a platform "contains" a subsystem means:
        #   edge: parent=subsystem, child=platform (platform depends on subsystem)
        # To find what a platform contains, find edges where child_node_id = platform.
        edges = self.session.execute(
            select(SupplyChainEdge).where(
                SupplyChainEdge.child_node_id == node_id
            )
        ).scalars().all()

        for edge in edges:
            child_entry = self._build_bom_tree(edge.parent_node_id, visited)
            child_entry.is_sole_source = edge.is_sole_source
            child_entry.confidence = edge.confidence or 0.5
            entry.children.append(child_entry)

        return entry

    # ------------------------------------------------- disruption propagation

    def propagate_disruption(
        self,
        disruption_type: str,
        entity_name: str,
        severity: float = 1.0,
    ) -> list[AffectedItem]:
        """Propagate a disruption through the supply chain graph.

        Args:
            disruption_type: "material", "country", "component", or "company".
            entity_name: Name of the disrupted entity.
            severity: Initial severity multiplier (0.0 - 1.0).

        Returns:
            Affected items sorted by severity descending.
        """
        seed_ids = self._find_seed_nodes(disruption_type, entity_name)
        if not seed_ids:
            logger.warning("No seed nodes found for %s: %s", disruption_type, entity_name)
            return []

        affected: list[AffectedItem] = []
        visited: set[int] = set()
        queue: deque[tuple[int, int, float, list[str]]] = deque()

        for sid in seed_ids:
            info = self._node_lookup.get(sid, {})
            queue.append((sid, 0, severity, [info.get("name", str(sid))]))

        while queue:
            node_id, depth, sev, path = queue.popleft()
            if node_id in visited:
                continue
            visited.add(node_id)

            info = self._node_lookup.get(node_id, {})
            affected.append(AffectedItem(
                node_id=node_id,
                node_name=info.get("name", "unknown"),
                node_type=info.get("node_type", "unknown"),
                depth=depth,
                severity=round(sev, 3),
                path=list(path),
            ))

            # Find downstream dependents: edges where parent_node_id = node_id
            # (meaning child_node depends on this node)
            edges = self.session.execute(
                select(SupplyChainEdge).where(
                    SupplyChainEdge.parent_node_id == node_id
                )
            ).scalars().all()

            for edge in edges:
                attenuation = 0.8 if edge.alternative_count > 0 else 1.0
                new_sev = sev * attenuation
                if new_sev > 0.05:
                    child_info = self._node_lookup.get(edge.child_node_id, {})
                    queue.append((
                        edge.child_node_id,
                        depth + 1,
                        new_sev,
                        path + [child_info.get("name", str(edge.child_node_id))],
                    ))

        # Sort by severity descending
        affected.sort(key=lambda a: a.severity, reverse=True)
        return affected

    def _find_seed_nodes(self, disruption_type: str, entity_name: str) -> list[int]:
        """Find starting node IDs for a disruption event."""
        if disruption_type == "material":
            node = self.session.execute(
                select(SupplyChainNode).where(
                    SupplyChainNode.node_type == SupplyChainNodeType.MATERIAL,
                    SupplyChainNode.name == entity_name,
                )
            ).scalar_one_or_none()
            return [node.id] if node else []

        if disruption_type == "component":
            node = self.session.execute(
                select(SupplyChainNode).where(
                    SupplyChainNode.node_type == SupplyChainNodeType.COMPONENT,
                    SupplyChainNode.name == entity_name,
                )
            ).scalar_one_or_none()
            return [node.id] if node else []

        if disruption_type == "country":
            country = self.session.execute(
                select(Country).where(Country.name == entity_name)
            ).scalar_one_or_none()
            if not country:
                return []
            nodes = self.session.execute(
                select(SupplyChainNode).where(
                    SupplyChainNode.country_id == country.id
                )
            ).scalars().all()
            return [n.id for n in nodes]

        if disruption_type == "company":
            nodes = self.session.execute(
                select(SupplyChainNode).where(
                    SupplyChainNode.company_name == entity_name
                )
            ).scalars().all()
            return [n.id for n in nodes]

        return []

    # ---------------------------------------------------- alternative lookup

    def find_alternatives(self, node_name: str) -> list[dict]:
        """Find alternative suppliers/sources for a given node.

        Looks for other nodes of the same type that serve the same dependents.
        """
        node = self.session.execute(
            select(SupplyChainNode).where(SupplyChainNode.name == node_name)
        ).scalar_one_or_none()

        if not node:
            return []

        # Find what depends on this node (child_node_id entries where this is parent)
        dependents = self.session.execute(
            select(SupplyChainEdge).where(
                SupplyChainEdge.parent_node_id == node.id
            )
        ).scalars().all()

        if not dependents:
            return []

        dependent_ids = {e.child_node_id for e in dependents}

        # Find other nodes of the same type that also serve the same dependents
        alternatives = []
        same_type_nodes = self.session.execute(
            select(SupplyChainNode).where(
                SupplyChainNode.node_type == node.node_type,
                SupplyChainNode.id != node.id,
            )
        ).scalars().all()

        for alt in same_type_nodes:
            alt_deps = self.session.execute(
                select(SupplyChainEdge).where(
                    SupplyChainEdge.parent_node_id == alt.id
                )
            ).scalars().all()
            alt_dep_ids = {e.child_node_id for e in alt_deps}

            overlap = dependent_ids & alt_dep_ids
            if overlap:
                country_name = None
                if alt.country_id:
                    country = self.session.execute(
                        select(Country).where(Country.id == alt.country_id)
                    ).scalar_one_or_none()
                    country_name = country.name if country else None

                alternatives.append({
                    "name": alt.name,
                    "node_type": alt.node_type.value if alt.node_type else "unknown",
                    "company": alt.company_name,
                    "country": country_name,
                    "shared_dependents": len(overlap),
                })

        return alternatives

    # ------------------------------------------------------- D3.js export

    def to_d3_json(
        self,
        node_type_filter: str | None = None,
        risk_min: float = 0,
        country_filter: str | None = None,
        include_countries: bool = False,
    ) -> dict:
        """Export the graph as D3.js-compatible JSON.

        Returns:
            {"nodes": [...], "edges": [...], "summary": {...}}
        """
        nodes = []
        node_ids_included: set[str] = set()

        for nid, data in self.graph.nodes(data=True):
            nt = data.get("node_type", "")

            # Skip country nodes unless requested
            if nt == "country" and not include_countries:
                continue

            # Apply filters
            if node_type_filter and nt != node_type_filter:
                continue
            if risk_min > 0 and data.get("risk_score", 0) < risk_min:
                continue
            if country_filter:
                country_id = data.get("country_id")
                if country_id:
                    country = self.session.execute(
                        select(Country).where(Country.id == country_id)
                    ).scalar_one_or_none()
                    if country and country.name != country_filter:
                        continue

            nodes.append({
                "id": nid,
                "name": data.get("name", ""),
                "type": nt,
                "risk": data.get("risk_score", 0),
                "company": data.get("company", ""),
                "description": data.get("description", ""),
            })
            node_ids_included.add(nid)

        edges = []
        for src, dst, data in self.graph.edges(data=True):
            if src in node_ids_included and dst in node_ids_included:
                edges.append({
                    "source": src,
                    "target": dst,
                    "dependency_type": data.get("dependency_type", ""),
                    "is_sole_source": data.get("is_sole_source", False),
                    "confidence": data.get("confidence", 0.5),
                })

        # Summary by type
        type_counts: dict[str, int] = {}
        for n in nodes:
            t = n["type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "nodes": nodes,
            "edges": edges,
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "by_type": type_counts,
            },
        }
