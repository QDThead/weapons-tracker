from __future__ import annotations

import pytest


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
