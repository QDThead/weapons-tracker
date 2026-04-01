from __future__ import annotations

import pytest

REQUIRED_KEYS = [
    # Insights (10)
    "insights", "insights.sitrep", "insights.sitrep.sanctions",
    "insights.sitrep.arctic", "insights.taxonomy", "insights.news",
    "insights.dsca", "insights.alliances", "insights.freshness",
    "insights.adversary",
    # Arctic (existing 3 + new 4 = 7 explicit)
    "arctic", "arctic.kpis.ice_extent", "arctic.bases",
    "arctic.flights", "arctic.routes", "arctic.trade", "arctic.naval",
    # Deals (2)
    "deals", "deals.transfers",
    # Canada Intel (6)
    "canada", "canada.flows", "canada.threats",
    "canada.suppliers", "canada.suppliers.risk", "canada.actions",
    # Data Feeds (3)
    "feeds", "feeds.status", "feeds.stats",
    # Compliance (2)
    "compliance", "compliance.matrix",
    # Supply Chain (20)
    "supply.overview", "supply.globe", "supply.graph", "supply.risks",
    "supply.scenarios", "supply.taxonomy", "supply.forecasting",
    "supply.bom", "supply.bom.mining", "supply.bom.processing",
    "supply.bom.alloys", "supply.bom.platforms",
    "supply.dossier", "supply.alerts", "supply.register",
    "supply.feedback", "supply.chokepoints", "supply.hhi",
    "supply.canada", "supply.risk_factors",
]


def test_all_required_keys_present():
    """All required registry keys are present."""
    from src.analysis.source_registry import get_registry
    registry = get_registry()
    missing = [k for k in REQUIRED_KEYS if k not in registry]
    assert missing == [], f"Missing registry keys: {missing}"


def test_full_registry_integrity():
    """Every registry key resolves and has valid shape."""
    from src.analysis.source_registry import get_registry, resolve_sources
    registry = get_registry()
    assert len(registry) >= 50, f"Expected >= 50 keys, got {len(registry)}"
    # Test inherited keys resolve
    for key in ["arctic.kpis", "arctic.kpis.threat_level", "deals.transfers.row"]:
        result = resolve_sources(key)
        assert result is not None, f"Inherited key {key} did not resolve"


def test_resolve_exact_key():
    """Exact key match returns the entry directly."""
    from src.analysis.source_registry import resolve_sources
    result = resolve_sources("arctic")
    assert result is not None
    assert result["title"] == "Arctic Security Assessment — Source Validation"
    assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert len(result["sources"]) >= 1
    assert "health_keys" in result


def test_resolve_inherited_key():
    """Key with no direct entry inherits from parent."""
    from src.analysis.source_registry import resolve_sources
    result = resolve_sources("arctic.kpis")
    parent = resolve_sources("arctic")
    assert result is not None
    assert result["title"] == parent["title"]
    assert result["sources"] == parent["sources"]


def test_resolve_override_key():
    """Leaf key overrides parent when it has its own entry."""
    from src.analysis.source_registry import resolve_sources
    result = resolve_sources("arctic.kpis.ice_extent")
    parent = resolve_sources("arctic")
    assert result is not None
    assert result["title"] != parent["title"]
    assert any("NOAA" in s["name"] or "NSIDC" in s["name"] for s in result["sources"])


def test_resolve_unknown_key_returns_none():
    """Completely unknown key returns None."""
    from src.analysis.source_registry import resolve_sources
    result = resolve_sources("nonexistent.key.path")
    assert result is None


def test_get_full_registry():
    """Full registry returns all entries as a dict."""
    from src.analysis.source_registry import get_registry
    registry = get_registry()
    assert isinstance(registry, dict)
    assert "arctic" in registry
    assert len(registry) >= 3


def test_source_entry_shape():
    """Every registry entry has required fields."""
    from src.analysis.source_registry import get_registry
    for key, entry in get_registry().items():
        assert "title" in entry, f"{key} missing title"
        assert "sources" in entry, f"{key} missing sources"
        assert "confidence" in entry, f"{key} missing confidence"
        assert "confidence_note" in entry, f"{key} missing confidence_note"
        assert "health_keys" in entry, f"{key} missing health_keys"
        assert entry["confidence"] in ("HIGH", "MEDIUM", "LOW"), f"{key} invalid confidence"
        for src in entry["sources"]:
            assert "name" in src, f"{key} source missing name"
            assert "type" in src, f"{key} source missing type"
            assert src["type"] in (
                "Primary", "Cross-validation", "Trade validation",
                "Company reports", "Manufacturer datasheets",
                "Derived estimate", "Reference", "Public domain"
            ), f"{key} source invalid type: {src['type']}"
