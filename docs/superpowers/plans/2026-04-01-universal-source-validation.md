# Universal Source Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add expandable "Sources & Validation" panels with live health data to every card, table, stat box, and chart across all 7 dashboard tabs.

**Architecture:** Centralized source registry (`source_registry.py`) with ~70 hierarchical key entries, served by two API endpoints (`/validation/sources` cached 1hr, `/validation/health` cached 60s), rendered by a universal `validationManager` JS module that auto-attaches panels to all elements with `data-val-key` attributes.

**Tech Stack:** Python/FastAPI (backend registry + API), vanilla JS (frontend manager), existing CSS design system (cyan accent, glass-morphism)

**Spec:** `docs/superpowers/specs/2026-04-01-universal-source-validation-design.md`

---

### Task 1: Source Registry — Core Module + Key Resolution

**Files:**
- Create: `src/analysis/source_registry.py`
- Create: `tests/test_source_registry.py`

This task builds the core Python registry with hierarchical key resolution. Start with 3 test entries (one section-level, one mid-level, one leaf override) to validate the inheritance logic. The full ~70 entries are populated in Tasks 6–8.

- [ ] **Step 1: Write failing tests for key resolution**

```python
# tests/test_source_registry.py
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
    # "arctic.kpis" has no direct entry, should inherit from "arctic"
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.analysis.source_registry'`

- [ ] **Step 3: Implement source_registry.py with 3 seed entries + resolve function**

```python
# src/analysis/source_registry.py
"""Centralized source validation registry.

Maps hierarchical dot-notation keys to source metadata for every
dashboard UI element. Supports inheritance: if 'arctic.kpis.threat_level'
has no entry, resolution walks up to 'arctic.kpis' then 'arctic'.

Public API:
    resolve_sources(key) -> dict | None
    get_registry() -> dict[str, dict]
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Source type constants (for autocomplete / typo prevention)
# ---------------------------------------------------------------------------
PRIMARY = "Primary"
CROSS_VALIDATION = "Cross-validation"
TRADE_VALIDATION = "Trade validation"
COMPANY_REPORTS = "Company reports"
MANUFACTURER = "Manufacturer datasheets"
DERIVED = "Derived estimate"
REFERENCE = "Reference"
PUBLIC = "Public domain"

# ---------------------------------------------------------------------------
# Registry — hierarchical key -> source metadata
# Populated in Tasks 6-8 with all ~70 entries. Seed entries below for tests.
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, dict] = {
    "arctic": {
        "title": "Arctic Security Assessment — Source Validation",
        "sources": [
            {
                "name": "SIPRI Arms Transfers Database",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases/armstransfers",
                "date": "2025",
                "note": "Annual TIV data for Arctic-nation arms flows (Russia, Canada, Norway, Denmark, USA)",
            },
            {
                "name": "CIA World Factbook — Military",
                "type": PRIMARY,
                "url": "https://www.cia.gov/the-world-factbook/",
                "date": "2024",
                "note": "Force composition, conscription, budget share for all Arctic Council states",
            },
            {
                "name": "Arctic Council Reports",
                "type": REFERENCE,
                "date": "2024",
                "note": "Governance frameworks, shipping route status, environmental assessments",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI transfers + CIA Factbook + Arctic Council governance data",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    "arctic.kpis.ice_extent": {
        "title": "Arctic Sea Ice Extent — Source Validation",
        "sources": [
            {
                "name": "NOAA/NSIDC Sea Ice Index v3",
                "type": PRIMARY,
                "url": "https://nsidc.org/data/seaice_index/",
                "date": "Monthly",
                "note": "Satellite-derived Arctic sea ice extent and concentration, updated monthly",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Single authoritative source — NSIDC is the global standard for sea ice measurement",
        "health_keys": ["noaa_ice"],
    },
    "arctic.bases": {
        "title": "Arctic Base Registry — Source Validation",
        "sources": [
            {
                "name": "SIPRI Military Bases Data Project",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases",
                "date": "2024",
                "note": "25 Arctic military installations with coordinates and capability data",
            },
            {
                "name": "CSIS Arctic Military Tracker",
                "type": CROSS_VALIDATION,
                "url": "https://www.csis.org/programs/americas-program",
                "date": "2024",
                "note": "Cross-validates base locations and operational status",
            },
            {
                "name": "National Ministry of Defence publications",
                "type": REFERENCE,
                "date": "2023-2024",
                "note": "Russia MoD, Canadian DND, US DoD annual reports on Arctic posture",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI + CSIS + national MoD data for 25 installations",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
}


def resolve_sources(key: str) -> dict | None:
    """Resolve a dot-notation key, walking up the hierarchy.

    Examples:
        resolve_sources("arctic.kpis.ice_extent")  -> ice_extent entry
        resolve_sources("arctic.kpis.threat_level") -> inherits "arctic"
        resolve_sources("nonexistent")              -> None
    """
    # Try exact match first
    if key in _REGISTRY:
        return _REGISTRY[key]

    # Walk up: "a.b.c" -> try "a.b" -> try "a"
    parts = key.split(".")
    while len(parts) > 1:
        parts.pop()
        parent_key = ".".join(parts)
        if parent_key in _REGISTRY:
            return _REGISTRY[parent_key]

    return None


def get_registry() -> dict[str, dict]:
    """Return the full registry dict (read-only reference)."""
    return _REGISTRY
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/source_registry.py tests/test_source_registry.py
git commit -m "feat: add source registry with hierarchical key resolution"
```

---

### Task 2: Validation API Endpoints

**Files:**
- Create: `src/api/validation_routes.py`
- Modify: `src/main.py` (add router import + registration)
- Create: `tests/test_validation_routes.py`

- [ ] **Step 1: Write failing tests for both endpoints**

```python
# tests/test_validation_routes.py
from __future__ import annotations

from fastapi.testclient import TestClient


def _get_client():
    from src.main import app
    return TestClient(app)


def test_get_validation_sources():
    """GET /validation/sources returns full registry."""
    client = _get_client()
    resp = client.get("/validation/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "registry" in data
    assert "total_keys" in data
    assert "source_types" in data
    assert isinstance(data["registry"], dict)
    assert data["total_keys"] >= 3
    # Verify entry shape
    for key, entry in data["registry"].items():
        assert "title" in entry
        assert "sources" in entry
        assert "confidence" in entry


def test_get_validation_health():
    """GET /validation/health returns health data per connector."""
    client = _get_client()
    resp = client.get("/validation/health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    # Should have at least some connector keys
    assert len(data) >= 1
    for connector_key, health in data.items():
        assert "last_fetch" in health
        assert "records" in health
        assert "cache_status" in health
        assert "health" in health
        assert health["cache_status"] in ("FRESH", "STALE", "EXPIRED", "UNKNOWN")
        assert health["health"] in ("OK", "STALE", "ERROR", "UNKNOWN")


def test_validation_sources_contains_arctic():
    """Registry contains arctic keys from seed data."""
    client = _get_client()
    resp = client.get("/validation/sources")
    data = resp.json()
    assert "arctic" in data["registry"]
    assert "arctic.bases" in data["registry"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validation_routes.py -v`
Expected: FAIL (routes not registered yet)

- [ ] **Step 3: Implement validation_routes.py**

```python
# src/api/validation_routes.py
"""API endpoints for universal source validation.

GET /validation/sources  — full source registry (cached 1hr)
GET /validation/health   — live connector health (cached 60s)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter

from src.analysis.source_registry import get_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation", tags=["Validation"])

# Server-side caches
_sources_cache: tuple[float, dict] | None = None
_SOURCES_TTL = 3600  # 1 hour

_health_cache: tuple[float, dict] | None = None
_HEALTH_TTL = 60  # 60 seconds

# Source types in display order
_SOURCE_TYPES = [
    "Primary",
    "Cross-validation",
    "Trade validation",
    "Company reports",
    "Manufacturer datasheets",
    "Derived estimate",
    "Reference",
    "Public domain",
]


@router.get("/sources")
async def get_validation_sources():
    """Return the full source validation registry."""
    global _sources_cache
    now = time.time()
    if _sources_cache and now - _sources_cache[0] < _SOURCES_TTL:
        return _sources_cache[1]

    registry = get_registry()
    result = {
        "registry": registry,
        "total_keys": len(registry),
        "source_types": _SOURCE_TYPES,
    }
    _sources_cache = (now, result)
    return result


@router.get("/health")
async def get_validation_health():
    """Return live health/freshness data for all data source connectors."""
    global _health_cache
    now = time.time()
    if _health_cache and now - _health_cache[0] < _HEALTH_TTL:
        return _health_cache[1]

    health = _collect_health()
    _health_cache = (now, health)
    return health


def _collect_health() -> dict:
    """Aggregate health data from all route module caches.

    Each route module stores caches as dict[str, tuple[float, data]].
    We inspect these to determine last fetch time, record counts,
    and staleness.
    """
    now = time.time()
    health: dict[str, dict] = {}

    # Define connector metadata: (display_key, cache_dict, cache_key, expected_ttl, record_counter)
    connectors = _get_connector_specs()

    for spec in connectors:
        key = spec["key"]
        cache_dict = spec.get("cache_dict")
        cache_key = spec.get("cache_key")
        expected_ttl = spec.get("expected_ttl", 3600)

        entry = {
            "last_fetch": None,
            "records": 0,
            "cache_age_seconds": None,
            "cache_status": "UNKNOWN",
            "health": "UNKNOWN",
        }

        if cache_dict and cache_key:
            cached = cache_dict.get(cache_key)
            if cached and isinstance(cached, tuple) and len(cached) == 2:
                ts, data = cached
                age = now - ts
                entry["last_fetch"] = datetime.fromtimestamp(
                    ts, tz=timezone.utc
                ).isoformat()
                entry["cache_age_seconds"] = int(age)

                # Record count
                if isinstance(data, list):
                    entry["records"] = len(data)
                elif isinstance(data, dict):
                    # Try common patterns for record counts
                    for count_key in ("total", "total_records", "count"):
                        if count_key in data:
                            entry["records"] = data[count_key]
                            break
                    else:
                        # Count list-valued keys
                        for v in data.values():
                            if isinstance(v, list):
                                entry["records"] = len(v)
                                break

                # Cache status
                if age < expected_ttl:
                    entry["cache_status"] = "FRESH"
                elif age < expected_ttl * 2:
                    entry["cache_status"] = "STALE"
                else:
                    entry["cache_status"] = "EXPIRED"

                # Health status
                if age < expected_ttl * 2:
                    entry["health"] = "OK"
                else:
                    entry["health"] = "STALE"

        health[key] = entry

    return health


def _get_connector_specs() -> list[dict]:
    """Return connector specifications for health monitoring.

    Each spec maps a display key to the module cache it reads from.
    We import lazily to avoid circular imports and to reflect
    runtime cache state.
    """
    specs: list[dict] = []

    # --- enrichment_routes caches ---
    try:
        from src.api.enrichment_routes import _cache as enrich_cache

        enrichment_connectors = [
            ("worldbank_governance", "gov:CAN,USA,RUS,CHN,GBR,FRA,DEU", 3600),
            ("cia_factbook", "factbook", 3600),
            ("commodity_prices", "commodities", 3600),
            ("cisa_kev", "cisa_kev", 3600),
            ("gdacs_disasters", "gdacs_disasters", 3600),
            ("celestrak_satellites", "celestrak_sats", 3600),
            ("csis_missiles", "csis_missiles", 3600),
            ("un_sanctions", "un_sanctions", 3600),
            ("usgs_earthquakes", "usgs_earthquakes", 3600),
            ("mitre_attack", "mitre_attack", 3600),
            ("imf_weo", "imf_weo", 3600),
            ("nasa_eonet", "nasa_eonet", 3600),
            ("portwatch_chokepoints", "portwatch_chokepoints", 3600),
            ("unhcr_displacement", "unhcr_displacement", 3600),
            ("space_launches", "space_launches", 3600),
            ("submarine_cables", "submarine_cables", 3600),
            ("ripe_internet", "ripe_internet", 3600),
            ("dod_contracts", "dod_contracts", 3600),
            ("usgs_mineral_deposits", "usgs_mineral_deposits", 3600),
            ("wb_conflict_deaths", "wb_conflict_deaths", 3600),
            ("treasury_fiscal", "treasury_fiscal", 3600),
        ]
        for key, cache_key, ttl in enrichment_connectors:
            specs.append(
                {
                    "key": key,
                    "cache_dict": enrich_cache,
                    "cache_key": cache_key,
                    "expected_ttl": ttl,
                }
            )
    except ImportError:
        pass

    # --- dashboard_routes caches ---
    try:
        from src.api.dashboard_routes import (
            _buyer_mirror_cache,
            _comtrade_cache,
            _news_cache,
        )

        specs.append(
            {
                "key": "comtrade_trade",
                "cache_dict": _comtrade_cache,
                "cache_key": "comtrade:*",
                "expected_ttl": 3600,
            }
        )
        specs.append(
            {
                "key": "buyer_mirror",
                "cache_dict": _buyer_mirror_cache,
                "cache_key": "mirror:*",
                "expected_ttl": 3600,
            }
        )
        specs.append(
            {
                "key": "gdelt_news",
                "cache_dict": _news_cache,
                "cache_key": "news:*",
                "expected_ttl": 900,
            }
        )
    except ImportError:
        pass

    # --- supplier_routes cache ---
    try:
        from src.api.supplier_routes import _cache as supplier_cache

        specs.append(
            {
                "key": "suppliers",
                "cache_dict": supplier_cache,
                "cache_key": "suppliers",
                "expected_ttl": 3600,
            }
        )
    except ImportError:
        pass

    return specs
```

- [ ] **Step 4: Register the router in main.py**

Add to `src/main.py` imports (after the existing router imports):

```python
from src.api.validation_routes import router as validation_router
```

Add to router registrations (after the existing `app.include_router` lines):

```python
app.include_router(validation_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_validation_routes.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Run full test suite to verify no regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add src/api/validation_routes.py tests/test_validation_routes.py src/main.py
git commit -m "feat: add /validation/sources and /validation/health API endpoints"
```

---

### Task 3: Frontend — Validation Manager JS Module + CSS

**Files:**
- Modify: `src/static/index.html` (add CSS + JS module)

This task adds the `validationManager` JavaScript object and all CSS classes. No panels are attached yet — that happens in Tasks 4–5.

- [ ] **Step 1: Add CSS classes after the existing `.bom-val-panel` styles**

In `src/static/index.html`, find the closing `}` of the `.bom-val-panel .bvp-note` rule (around line 552). Add the new validation CSS immediately after:

```css
/* --- Universal Source Validation Panels --- */
.val-trigger{display:flex;align-items:center;gap:8px;padding:8px 16px;cursor:pointer;border-top:1px solid rgba(255,255,255,0.04);transition:background 0.2s;}
.val-trigger:hover{background:rgba(0,212,255,0.03);}
.val-trigger .val-chev{color:rgba(0,212,255,0.6);font-size:11px;transition:transform 0.2s;}
.val-trigger.open .val-chev{transform:rotate(90deg);}
.val-trigger .val-label{color:rgba(0,212,255,0.6);font-size:11px;font-weight:500;letter-spacing:0.5px;text-transform:uppercase;}
.val-trigger .val-badge{font-size:9px;padding:1px 6px;border-radius:10px;font-weight:600;margin-left:auto;}
.val-badge-HIGH{background:rgba(16,185,129,0.12);color:rgba(16,185,129,0.8);}
.val-badge-MEDIUM{background:rgba(245,158,11,0.12);color:rgba(245,158,11,0.8);}
.val-badge-LOW{background:rgba(239,68,68,0.12);color:rgba(239,68,68,0.8);}
.val-trigger .val-count{color:rgba(255,255,255,0.3);font-size:10px;}
.val-panel{display:none;padding:16px;background:rgba(0,212,255,0.03);border-left:3px solid var(--accent);font-size:11px;line-height:1.7;}
.val-panel.open{display:block;}
.val-panel .val-src{padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.06);}
.val-panel .val-src:last-of-type{border-bottom:none;}
.val-panel .val-src-header{display:flex;align-items:center;gap:8px;margin-bottom:4px;}
.val-panel .val-src-meta{display:flex;gap:16px;font-size:11px;color:rgba(255,255,255,0.5);margin-bottom:4px;}
.val-panel .val-src-note{font-size:11px;color:rgba(255,255,255,0.4);font-style:italic;}
.val-health{padding:12px 0 8px 0;border-top:2px solid rgba(0,212,255,0.1);margin-top:4px;}
.val-health-label{color:var(--accent);font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;}
.val-health-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;text-align:center;}
.val-health-grid .val-h-num{font-size:14px;font-weight:700;font-family:var(--font-mono);}
.val-health-grid .val-h-label{color:rgba(255,255,255,0.4);font-size:9px;text-transform:uppercase;}
.val-health-grid .val-h-ok{color:var(--accent3);}
.val-health-grid .val-h-stale{color:var(--accent4);}
.val-health-grid .val-h-error{color:var(--accent2);}
.val-confidence{padding:8px 0 4px 0;border-top:1px solid rgba(255,255,255,0.06);color:rgba(255,255,255,0.6);font-size:11px;}
.val-confidence strong{color:var(--accent3);}
```

- [ ] **Step 2: Add the validationManager JS module**

In `src/static/index.html`, find the opening `<script>` tag where global JS starts (the section with utility functions like `esc()`). Add the `validationManager` object near the top, after `esc()` and before the tab-switching logic:

```javascript
/* ── Universal Source Validation Manager ── */
var validationManager = (function() {
  var _registry = null;
  var _health = {};
  var _panelId = 0;
  var _healthInterval = null;

  function _resolve(key) {
    if (!_registry) return null;
    if (_registry[key]) return _registry[key];
    var parts = key.split('.');
    while (parts.length > 1) {
      parts.pop();
      var parent = parts.join('.');
      if (_registry[parent]) return _registry[parent];
    }
    return null;
  }

  function _relativeTime(isoStr) {
    if (!isoStr) return 'N/A';
    var diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return Math.round(diff) + 's ago';
    if (diff < 3600) return Math.round(diff / 60) + 'm ago';
    if (diff < 86400) return Math.round(diff / 3600) + 'h ago';
    return Math.round(diff / 86400) + 'd ago';
  }

  function _healthColor(status) {
    if (status === 'FRESH' || status === 'OK') return 'val-h-ok';
    if (status === 'STALE') return 'val-h-stale';
    return 'val-h-error';
  }

  function _renderPanel(entry, healthKeys) {
    var id = ++_panelId;
    var srcCount = entry.sources ? entry.sources.length : 0;
    var conf = entry.confidence || 'MEDIUM';

    // Trigger bar (collapsed)
    var html = '<div class="val-trigger" id="vt-' + id + '" onclick="validationManager.toggle(' + id + ')">';
    html += '<span class="val-chev">&#9654;</span>';
    html += '<span class="val-label">Sources &amp; Validation</span>';
    html += '<span class="val-badge val-badge-' + esc(conf) + '">' + esc(conf) + '</span>';
    html += '<span class="val-count">' + srcCount + ' source' + (srcCount !== 1 ? 's' : '') + '</span>';
    html += '</div>';

    // Expandable panel
    html += '<div class="val-panel" id="vp-' + id + '">';

    // Sources
    (entry.sources || []).forEach(function(s) {
      html += '<div class="val-src">';
      html += '<div class="val-src-header">';
      var tc = (s.type || '').replace(/\s+/g, '-');
      html += '<span class="bvp-type bvp-' + tc + '">' + esc(s.type) + '</span>';
      html += '<strong style="color:#fff;font-size:13px;">' + esc(s.name) + '</strong>';
      html += '</div>';
      html += '<div class="val-src-meta">';
      if (s.date) html += '<span>Date: ' + esc(s.date) + '</span>';
      if (s.url) html += '<span>|</span><a href="' + esc(s.url) + '" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;">' + esc(s.url.replace(/^https?:\/\/(?:www\.)?/, '').split('/')[0]) + ' &#8599;</a>';
      html += '</div>';
      if (s.note) html += '<div class="val-src-note">' + esc(s.note) + '</div>';
      html += '</div>';
    });

    // Health row
    var hKeys = healthKeys || entry.health_keys || [];
    if (hKeys.length > 0) {
      html += '<div class="val-health">';
      html += '<div class="val-health-label">&#9679; Data Health</div>';
      html += '<div class="val-health-grid" id="vh-' + id + '" data-health-keys="' + esc(hKeys.join(',')) + '">';
      var bestHealth = _getBestHealth(hKeys);
      html += '<div><div class="val-h-num ' + _healthColor(bestHealth.cache_status) + '">' + _relativeTime(bestHealth.last_fetch) + '</div><div class="val-h-label">Last Fetch</div></div>';
      html += '<div><div class="val-h-num" style="color:#fff;">' + (bestHealth.records || 0).toLocaleString() + '</div><div class="val-h-label">Records</div></div>';
      html += '<div><div class="val-h-num ' + _healthColor(bestHealth.cache_status) + '">' + (bestHealth.cache_status || 'UNKNOWN') + '</div><div class="val-h-label">Cache</div></div>';
      html += '<div><div class="val-h-num ' + _healthColor(bestHealth.health) + '">' + (bestHealth.health === 'OK' ? '&#10003; OK' : bestHealth.health || 'UNKNOWN') + '</div><div class="val-h-label">Health</div></div>';
      html += '</div></div>';
    }

    // Confidence
    if (entry.confidence_note) {
      html += '<div class="val-confidence"><strong>Confidence: ' + esc(conf) + '</strong> — ' + esc(entry.confidence_note) + '</div>';
    }

    html += '</div>';
    return html;
  }

  function _getBestHealth(keys) {
    // Aggregate health across multiple connector keys — use the most recent fetch
    var best = { last_fetch: null, records: 0, cache_status: 'UNKNOWN', health: 'UNKNOWN' };
    var totalRecords = 0;
    var latestTs = 0;
    keys.forEach(function(k) {
      var h = _health[k];
      if (h) {
        totalRecords += (h.records || 0);
        var ts = h.last_fetch ? new Date(h.last_fetch).getTime() : 0;
        if (ts > latestTs) {
          latestTs = ts;
          best.last_fetch = h.last_fetch;
          best.cache_status = h.cache_status;
          best.health = h.health;
        }
      }
    });
    best.records = totalRecords;
    return best;
  }

  async function _fetchHealth() {
    try {
      var resp = await fetch('/validation/health');
      if (resp.ok) {
        _health = await resp.json();
        _refreshHealthDisplays();
      }
    } catch (e) { /* silent — health is best-effort */ }
  }

  function _refreshHealthDisplays() {
    document.querySelectorAll('[data-health-keys]').forEach(function(grid) {
      var keys = grid.getAttribute('data-health-keys').split(',');
      var best = _getBestHealth(keys);
      var cells = grid.children;
      if (cells.length >= 4) {
        cells[0].querySelector('.val-h-num').className = 'val-h-num ' + _healthColor(best.cache_status);
        cells[0].querySelector('.val-h-num').textContent = _relativeTime(best.last_fetch);
        cells[1].querySelector('.val-h-num').textContent = (best.records || 0).toLocaleString();
        cells[2].querySelector('.val-h-num').className = 'val-h-num ' + _healthColor(best.cache_status);
        cells[2].querySelector('.val-h-num').textContent = best.cache_status || 'UNKNOWN';
        cells[3].querySelector('.val-h-num').className = 'val-h-num ' + _healthColor(best.health);
        cells[3].querySelector('.val-h-num').innerHTML = best.health === 'OK' ? '&#10003; OK' : (best.health || 'UNKNOWN');
      }
    });
  }

  return {
    init: async function() {
      try {
        var resp = await fetch('/validation/sources');
        if (resp.ok) {
          var data = await resp.json();
          _registry = data.registry || {};
        }
      } catch (e) {
        _registry = {};
      }
      await _fetchHealth();
      if (_healthInterval) clearInterval(_healthInterval);
      _healthInterval = setInterval(_fetchHealth, 60000);
    },

    toggle: function(id) {
      var trigger = document.getElementById('vt-' + id);
      var panel = document.getElementById('vp-' + id);
      if (trigger) trigger.classList.toggle('open');
      if (panel) panel.classList.toggle('open');
    },

    attach: function(element, key) {
      if (!element || !key) return;
      var entry = _resolve(key);
      if (!entry) return;
      // Don't double-attach
      if (element.querySelector('.val-trigger')) return;
      var wrapper = document.createElement('div');
      wrapper.innerHTML = _renderPanel(entry);
      while (wrapper.firstChild) {
        element.appendChild(wrapper.firstChild);
      }
    },

    attachAll: function() {
      document.querySelectorAll('[data-val-key]').forEach(function(el) {
        var key = el.getAttribute('data-val-key');
        if (key) validationManager.attach(el, key);
      });
    },

    resolve: _resolve,
  };
})();
```

- [ ] **Step 3: Initialize validationManager on page load**

Find the existing `DOMContentLoaded` or `window.onload` handler in `index.html`. Add at the end of the initialization block:

```javascript
// Initialize universal source validation
validationManager.init().then(function() {
  validationManager.attachAll();
});
```

- [ ] **Step 4: Manual test — verify the JS loads without errors**

Run: `python -m src.main`
Open: `http://localhost:8000` in browser
Check: Browser console (F12) shows no JS errors. Network tab shows `/validation/sources` and `/validation/health` requests returning 200.

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add validationManager JS module + validation panel CSS"
```

---

### Task 4: Attach Validation Panels — Static HTML Elements (Insights, Arctic, Deals, Compliance)

**Files:**
- Modify: `src/static/index.html` (add `data-val-key` attributes to static HTML elements)

This task adds `data-val-key` attributes to all static HTML elements (cards, tables, stat boxes) that exist in the page HTML before any JS rendering. These get auto-attached by `validationManager.attachAll()` on page load.

- [ ] **Step 1: Add data-val-key to Insights tab elements**

Search for `id="page-insights"` in index.html. Add `data-val-key` attributes to each card/section:

- The freshness banner card: add `data-val-key="insights.freshness"`
- The situation report card/section: add `data-val-key="insights.sitrep"`
- The risk taxonomy 13-card strip container: add `data-val-key="insights.taxonomy"`
- The live news section: add `data-val-key="insights.news"`
- The DSCA sales section: add `data-val-key="insights.dsca"`
- The shifting alliances section: add `data-val-key="insights.alliances"`
- The adversary flows section: add `data-val-key="insights.adversary"`

For each, add the attribute to the outermost `.card` or container `div` for that section.

- [ ] **Step 2: Add data-val-key to Arctic tab elements**

Search for `id="page-arctic"` in index.html. Add `data-val-key` attributes:

- KPI stat boxes container: add `data-val-key="arctic.kpis"`
- Each individual KPI override where applicable (ice extent stat box): `data-val-key="arctic.kpis.ice_extent"`
- Arctic bases table container: `data-val-key="arctic.bases"`
- Flight cards container: `data-val-key="arctic.flights"`
- Shipping routes table: `data-val-key="arctic.routes"`
- Trade cards section: `data-val-key="arctic.trade"`
- Naval/weakness cards: `data-val-key="arctic.naval"`

- [ ] **Step 3: Add data-val-key to Deals tab elements**

Search for `id="page-deals"` or the deals/transfers section. Add:

- Transfers table container: `data-val-key="deals.transfers"`

- [ ] **Step 4: Add data-val-key to Compliance tab elements**

Search for `id="page-compliance"`. Add:

- Compliance matrix container: `data-val-key="compliance.matrix"`

- [ ] **Step 5: Add data-val-key to Data Feeds tab elements**

Search for `id="page-data-feeds"`. Add:

- Feed stats summary: `data-val-key="feeds.stats"`
- Feed cards container: `data-val-key="feeds.status"`

- [ ] **Step 6: Manual test — verify panels appear on static elements**

Run: `python -m src.main`
Open: `http://localhost:8000`
Navigate to each tab. Verify collapsed "Sources & Validation" bars appear at the bottom of every tagged element. Click one to expand — verify sources list, health row, and confidence note display.

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat: attach validation panels to static HTML elements across 5 tabs"
```

---

### Task 5: Attach Validation Panels — Dynamic Content (Canada Intel, Supply Chain)

**Files:**
- Modify: `src/static/index.html` (add `validationManager.attach()` calls in JS render functions)

Many elements are rendered dynamically by JS after API fetches. This task adds `validationManager.attach()` calls to those render functions.

- [ ] **Step 1: Attach panels in Canada Intel render functions**

Find the render functions for Canada Intel tab content (the functions called when the Canada Intel tab is activated — look for `loadCanadaIntel` or similar). After each section's HTML is rendered and inserted into the DOM, add:

```javascript
// After rendering ally/adversary flows
validationManager.attach(document.getElementById('canada-flows-container'), 'canada.flows');
// After rendering threat watchlist
validationManager.attach(document.getElementById('canada-threats-container'), 'canada.threats');
// After rendering supplier cards
validationManager.attach(document.getElementById('canada-suppliers-container'), 'canada.suppliers');
// After rendering Action Centre
validationManager.attach(document.getElementById('canada-actions-container'), 'canada.actions');
```

Adjust the element IDs to match the actual container IDs in the HTML. If the containers don't have IDs, add them or use `querySelector` within the section.

- [ ] **Step 2: Attach panels in Supply Chain render functions**

Find each PSI sub-tab render function and add `validationManager.attach()` after rendering. The key render functions to modify:

For `renderMineralOverview()` (Overview sub-tab):
```javascript
// At end of function, after container.innerHTML = html:
validationManager.attach(container, 'supply.overview');
```

For the Knowledge Graph render function:
```javascript
validationManager.attach(document.getElementById('psi-graph'), 'supply.graph');
```

For the Risk Matrix render function:
```javascript
validationManager.attach(document.getElementById('psi-risks'), 'supply.risks');
```

For the Scenario Sandbox render function:
```javascript
validationManager.attach(document.getElementById('psi-scenarios'), 'supply.scenarios');
```

For the Risk Taxonomy render function:
```javascript
validationManager.attach(document.getElementById('psi-taxonomy'), 'supply.taxonomy');
```

For the Forecasting render function:
```javascript
validationManager.attach(document.getElementById('psi-forecasting'), 'supply.forecasting');
```

For `renderBomExplorer()` (BOM sub-tab) — this replaces the old `renderBomValBtn()` calls:
```javascript
// After rendering the BOM tree, attach per-tier validation:
var bomContainer = document.getElementById('psi-bom');
validationManager.attach(bomContainer.querySelector('.bom-mining-section'), 'supply.bom.mining');
validationManager.attach(bomContainer.querySelector('.bom-processing-section'), 'supply.bom.processing');
validationManager.attach(bomContainer.querySelector('.bom-alloys-section'), 'supply.bom.alloys');
validationManager.attach(bomContainer.querySelector('.bom-platforms-section'), 'supply.bom.platforms');
```

For the Supplier Dossier render function:
```javascript
validationManager.attach(document.getElementById('psi-dossier'), 'supply.dossier');
```

For the Alerts & Sensing render function:
```javascript
validationManager.attach(document.getElementById('psi-alerts'), 'supply.alerts');
```

For the Risk Register render function:
```javascript
validationManager.attach(document.getElementById('psi-register'), 'supply.register');
```

For the Analyst Feedback render function:
```javascript
validationManager.attach(document.getElementById('psi-feedback'), 'supply.feedback');
```

- [ ] **Step 3: Attach panels in the 3D Globe detail panel**

Find the function that renders the globe's supply chain detail panel (triggered when clicking a mineral on the globe). After the detail panel HTML is set:

```javascript
validationManager.attach(document.getElementById('globe-detail-panel'), 'supply.globe');
```

- [ ] **Step 4: Manual test — verify dynamic panels work**

Run: `python -m src.main`
Open: `http://localhost:8000`
Test each dynamically rendered section:
- Canada Intel tab: verify panels appear on flows, threats, suppliers, actions
- Supply Chain > Overview: verify panel appears
- Supply Chain > BOM Explorer: verify per-tier panels appear (replacing old ones)
- Supply Chain > each sub-tab: verify panels appear

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat: attach validation panels to dynamic content (Canada Intel + Supply Chain)"
```

---

### Task 6: Populate Registry — Insights + Arctic + Deals Keys

**Files:**
- Modify: `src/analysis/source_registry.py` (add ~20 entries)
- Modify: `tests/test_source_registry.py` (add registry completeness test)

- [ ] **Step 1: Add test for key completeness**

Add to `tests/test_source_registry.py`:

```python
# All keys that must exist in the final registry
REQUIRED_KEYS = [
    # Insights
    "insights", "insights.sitrep", "insights.sitrep.sanctions",
    "insights.sitrep.arctic", "insights.taxonomy", "insights.news",
    "insights.dsca", "insights.alliances", "insights.freshness",
    "insights.adversary",
    # Arctic
    "arctic", "arctic.kpis.ice_extent", "arctic.bases",
    "arctic.flights", "arctic.routes", "arctic.trade", "arctic.naval",
    # Deals
    "deals", "deals.transfers",
]


def test_required_keys_insights_arctic_deals():
    """All Insights, Arctic, and Deals keys are present."""
    from src.analysis.source_registry import get_registry
    registry = get_registry()
    missing = [k for k in REQUIRED_KEYS if k not in registry]
    assert missing == [], f"Missing registry keys: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_source_registry.py::test_required_keys_insights_arctic_deals -v`
Expected: FAIL (most keys missing)

- [ ] **Step 3: Add all Insights keys to the registry**

Add these entries to `_REGISTRY` in `src/analysis/source_registry.py`:

```python
    "insights": {
        "title": "Intelligence Insights — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "Global arms transfer TIV data (1950–2024) for trade flow analysis"},
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "url": "https://www.gdeltproject.org/", "date": "15-min updates", "note": "Real-time global event monitoring, arms trade keyword filtering"},
            {"name": "OFAC SDN + EU Sanctions", "type": PRIMARY, "date": "On-demand", "note": "17 embargoed countries, sanctions list cross-referencing"},
            {"name": "4x ADS-B Flight Sources", "type": PRIMARY, "date": "Live (60s)", "note": "adsb.lol, adsb.fi, Airplanes.live, ADSB One — military flight tracking"},
            {"name": "NATO Defence Expenditure", "type": PRIMARY, "url": "https://www.nato.int/cps/en/natohq/topics_49198.htm", "date": "2025 est.", "note": "Annual defence spending as % GDP for all NATO members"},
            {"name": "UN Comtrade", "type": TRADE_VALIDATION, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "USD bilateral trade data, buyer-side mirror for opacity circumvention"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Aggregated across 6+ independent primary sources with cross-validation",
        "health_keys": ["sipri_transfers", "gdelt_news", "comtrade_trade"],
    },
    "insights.sitrep": {
        "title": "Situation Report — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Transfer volumes and supplier shift detection"},
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "date": "15-min updates", "note": "News event scoring for threat level indicators"},
            {"name": "OFAC SDN + EU + UN Sanctions", "type": PRIMARY, "date": "On-demand", "note": "Sanctions compliance checking across 17 embargoes"},
            {"name": "Military Flight Tracker (4 ADS-B)", "type": PRIMARY, "date": "Live (60s)", "note": "Arctic and global military flight pattern analysis"},
            {"name": "NATO Defence Expenditure", "type": PRIMARY, "date": "2025 est.", "note": "Canada NATO ranking and rearmament tracking"},
            {"name": "UN Comtrade Buyer Mirror", "type": TRADE_VALIDATION, "date": "2023", "note": "Russia/China export verification via buyer-reported imports"},
        ],
        "confidence": "HIGH",
        "confidence_note": "6 threat indicators each backed by independent primary sources, cross-validated where possible",
        "health_keys": ["sipri_transfers", "gdelt_news", "comtrade_trade"],
    },
    "insights.sitrep.sanctions": {
        "title": "Sanctions & Embargoes — Source Validation",
        "sources": [
            {"name": "OFAC SDN List", "type": PRIMARY, "url": "https://sanctionslist.ofac.treas.gov/", "date": "On-demand", "note": "US Treasury specially designated nationals and blocked persons"},
            {"name": "EU Consolidated Sanctions", "type": PRIMARY, "url": "https://data.europa.eu/data/datasets/consolidated-list-of-persons-groups-and-entities-subject-to-eu-financial-sanctions", "date": "On-demand", "note": "EU financial sanctions list"},
            {"name": "UN Security Council Sanctions", "type": PRIMARY, "url": "https://www.un.org/securitycouncil/sanctions/information", "date": "On-demand", "note": "UNSC consolidated sanctions list"},
            {"name": "Arms Embargo Registry", "type": REFERENCE, "date": "2024", "note": "17 embargoed countries: Afghanistan, Belarus, CAR, China, Cuba, DPRK, DRC, Eritrea, Haiti, Iran, Iraq, Lebanon, Libya, Mali, Russia, Somalia, South Sudan"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across 3 independent sanctions authorities (OFAC, EU, UN) plus curated embargo list",
        "health_keys": ["un_sanctions"],
    },
    "insights.sitrep.arctic": {
        "title": "Arctic Threat Indicator — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Russian Arctic militarization — arms procurement trends"},
            {"name": "CIA World Factbook — Military", "type": PRIMARY, "date": "2024", "note": "Arctic nation force compositions and defence budgets"},
            {"name": "NOAA/NSIDC Sea Ice Index", "type": PRIMARY, "url": "https://nsidc.org/data/seaice_index/", "date": "Monthly", "note": "Ice extent decline rates impacting route accessibility"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Military data from SIPRI + CIA, environmental from NOAA — independent domains corroborate threat picture",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    "insights.taxonomy": {
        "title": "DND Risk Taxonomy (13 Categories) — Source Validation",
        "sources": [
            {"name": "PSI Supply Chain Analytics", "type": PRIMARY, "date": "Live", "note": "6-dimension risk scoring feeds categories 1-3"},
            {"name": "GDELT News Analysis", "type": PRIMARY, "date": "15-min updates", "note": "Real-time OSINT scoring for live categories (1, 2, 3, 11)"},
            {"name": "World Bank Governance Indicators", "type": PRIMARY, "url": "https://info.worldbank.org/governance/wgi/", "date": "2023", "note": "WGI scores for geopolitical instability categories"},
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "13-category, 121 sub-category risk taxonomy definition"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "4 categories scored live from OSINT, 3 hybrid (live + seeded), 6 seeded with drift — coverage expanding",
        "health_keys": ["gdelt_news", "worldbank_governance"],
    },
    "insights.news": {
        "title": "Live Intelligence News — Source Validation",
        "sources": [
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "url": "https://www.gdeltproject.org/", "date": "15-min updates", "note": "Global event database filtered for arms trade, military, and geopolitical keywords"},
            {"name": "Defense News RSS", "type": PRIMARY, "date": "Hourly", "note": "4 feeds: Defense News, Breaking Defense, Jane's, Defense One"},
            {"name": "Disinformation Detection (3-layer)", "type": DERIVED, "date": "Real-time", "note": "State-media domain check + extreme tone scoring + sensationalist title patterns"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "GDELT is comprehensive but noisy — disinformation detection layer provides quality filtering",
        "health_keys": ["gdelt_news"],
    },
    "insights.dsca": {
        "title": "DSCA Arms Sales — Source Validation",
        "sources": [
            {"name": "DSCA Major Arms Sales Notifications", "type": PRIMARY, "url": "https://www.dsca.mil/press-media/major-arms-sales", "date": "Days", "note": "US Defense Security Cooperation Agency — Congressional notifications of foreign military sales"},
            {"name": "Federal Register API", "type": PRIMARY, "url": "https://www.federalregister.gov/", "date": "Days", "note": "Official US government publication of DSCA notifications"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Primary US government source — authoritative for US foreign military sales",
        "health_keys": ["dod_contracts"],
    },
    "insights.alliances": {
        "title": "Shifting Alliances — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Historical supplier-buyer relationships, detects primary supplier changes"},
            {"name": "UN Comtrade Bilateral Trade", "type": CROSS_VALIDATION, "date": "2023", "note": "USD trade values validate TIV-based alliance patterns"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV trends cross-validated with Comtrade USD bilateral data",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "insights.freshness": {
        "title": "Data Source Freshness — Source Validation",
        "sources": [
            {"name": "All 56 Active Connectors", "type": PRIMARY, "date": "Live", "note": "Freshness derived from actual last-fetch timestamps across all data source connectors"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Freshness is computed live from connector cache timestamps — always reflects reality",
        "health_keys": [],
    },
    "insights.adversary": {
        "title": "Adversary Trade Flows — Source Validation",
        "sources": [
            {"name": "UN Comtrade Buyer-Side Mirror", "type": PRIMARY, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "Queries what buyers report importing from Russia/China — circumvents exporter data opacity"},
            {"name": "SIPRI Arms Transfers (TIV)", "type": CROSS_VALIDATION, "date": "2025", "note": "Volume-based cross-check of Comtrade USD values"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Buyer-side mirror technique specifically designed to circumvent Russia/China reporting gaps",
        "health_keys": ["comtrade_trade", "sipri_transfers"],
    },
```

- [ ] **Step 4: Add remaining Arctic + Deals keys**

Add to `_REGISTRY` (note: `arctic`, `arctic.kpis.ice_extent`, and `arctic.bases` already exist from Task 1):

```python
    "arctic.flights": {
        "title": "Arctic Military Flights — Source Validation",
        "sources": [
            {"name": "adsb.lol ADS-B Exchange", "type": PRIMARY, "url": "https://api.adsb.lol/v2/mil", "date": "Live (60s)", "note": "Primary military aircraft transponder feed"},
            {"name": "adsb.fi ADS-B Finland", "type": CROSS_VALIDATION, "url": "https://opendata.adsb.fi/api/v2/mil", "date": "Live (60s)", "note": "Cross-validation feed, identical format"},
            {"name": "Airplanes.live", "type": CROSS_VALIDATION, "url": "https://api.airplanes.live/v2/mil", "date": "Live (60s)", "note": "Third independent ADS-B source"},
            {"name": "ADSB One", "type": CROSS_VALIDATION, "url": "https://api.adsbone.com/v2/mil", "date": "Live (60s)", "note": "Fourth ADS-B source — deduplicated by hex code across all 4"},
        ],
        "confidence": "HIGH",
        "confidence_note": "4 independent ADS-B sources with deduplication — highest confidence for live position data",
        "health_keys": [],
    },
    "arctic.routes": {
        "title": "Arctic Shipping Routes — Source Validation",
        "sources": [
            {"name": "IMF PortWatch", "type": PRIMARY, "url": "https://portwatch.imf.org/", "date": "2024", "note": "Maritime chokepoint monitoring, trade volume through Arctic passages"},
            {"name": "Arctic Council PAME", "type": REFERENCE, "url": "https://pame.is/", "date": "2024", "note": "Protection of the Arctic Marine Environment — official route classifications (NSR, NWP, Transpolar)"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Route definitions from Arctic Council are authoritative; traffic volumes rely on IMF estimates",
        "health_keys": ["portwatch_chokepoints"],
    },
    "arctic.trade": {
        "title": "Arctic Trade Flows — Source Validation",
        "sources": [
            {"name": "UN Comtrade", "type": PRIMARY, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "Bilateral trade values for Arctic-adjacent nations"},
            {"name": "Statistics Canada CIMT", "type": CROSS_VALIDATION, "url": "https://www.statcan.gc.ca/", "date": "Monthly", "note": "Canadian bilateral trade verification"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Comtrade cross-validated with StatCan for Canadian trade corridors",
        "health_keys": ["comtrade_trade"],
    },
    "arctic.naval": {
        "title": "Naval Presence & Russia Weakness — Source Validation",
        "sources": [
            {"name": "CIA World Factbook — Military", "type": PRIMARY, "url": "https://www.cia.gov/the-world-factbook/", "date": "2024", "note": "Naval vessel counts, force readiness, conscription data"},
            {"name": "Jane's Defence Weekly", "type": REFERENCE, "date": "2024", "note": "Order of battle, fleet composition, capability assessments"},
            {"name": "SIPRI Military Expenditure (MILEX)", "type": CROSS_VALIDATION, "url": "https://milex.sipri.org/", "date": "2024", "note": "Military spending trends corroborate force posture analysis"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "CIA Factbook is primary; Jane's adds capability depth but is behind a paywall for full data",
        "health_keys": ["cia_factbook"],
    },
    "deals": {
        "title": "Arms Transfers Database — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "9,311 transfers (1950–2024), 26 sellers, 186 buyers, TIV methodology"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI is the global standard for arms transfer data — single authoritative source",
        "health_keys": ["sipri_transfers"],
    },
    "deals.transfers": {
        "title": "Arms Transfer Records — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "url": "https://www.sipri.org/databases/armstransfers", "date": "2025", "note": "TIV-denominated transfer records with weapon descriptions, order dates, delivery status"},
            {"name": "UN Comtrade HS 93", "type": CROSS_VALIDATION, "url": "https://comtradeplus.un.org/", "date": "2023", "note": "USD trade values for arms & ammunition (HS chapter 93) cross-validate SIPRI TIV volumes"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV cross-validated with Comtrade USD for volume verification",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: All tests PASS including the new completeness test

- [ ] **Step 6: Commit**

```bash
git add src/analysis/source_registry.py tests/test_source_registry.py
git commit -m "feat: populate source registry — Insights, Arctic, Deals (20 keys)"
```

---

### Task 7: Populate Registry — Canada Intel + Data Feeds + Compliance Keys

**Files:**
- Modify: `src/analysis/source_registry.py` (add ~11 entries)
- Modify: `tests/test_source_registry.py` (extend completeness test)

- [ ] **Step 1: Add completeness test for new keys**

Extend the `REQUIRED_KEYS` list in `tests/test_source_registry.py` and add a new test:

```python
REQUIRED_KEYS_TASK7 = [
    # Canada Intel
    "canada", "canada.flows", "canada.threats",
    "canada.suppliers", "canada.suppliers.risk", "canada.actions",
    # Data Feeds
    "feeds", "feeds.status", "feeds.stats",
    # Compliance
    "compliance", "compliance.matrix",
]


def test_required_keys_canada_feeds_compliance():
    """All Canada Intel, Data Feeds, and Compliance keys are present."""
    from src.analysis.source_registry import get_registry
    registry = get_registry()
    missing = [k for k in REQUIRED_KEYS_TASK7 if k not in registry]
    assert missing == [], f"Missing registry keys: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_source_registry.py::test_required_keys_canada_feeds_compliance -v`
Expected: FAIL

- [ ] **Step 3: Add Canada Intel + Data Feeds + Compliance entries**

Add to `_REGISTRY` in `src/analysis/source_registry.py`:

```python
    # --- Canada Intel ---
    "canada": {
        "title": "Canada Intelligence — Source Validation",
        "sources": [
            {"name": "Statistics Canada CIMT", "type": PRIMARY, "url": "https://www.statcan.gc.ca/", "date": "Monthly", "note": "Canadian International Merchandise Trade — bilateral trade by HS code"},
            {"name": "DND Procurement Disclosure", "type": PRIMARY, "url": "https://open.canada.ca/", "date": "Weekly", "note": "Open Canada defence contract disclosures"},
            {"name": "SIPRI Arms Transfers Database", "type": CROSS_VALIDATION, "date": "2025", "note": "Canada as buyer/seller in global arms transfer network"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Canadian government primary sources (StatCan, Open Canada) cross-validated with SIPRI",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "canada.flows": {
        "title": "Ally vs Adversary Trade Flows — Source Validation",
        "sources": [
            {"name": "SIPRI Arms Transfers Database", "type": PRIMARY, "date": "2025", "note": "Bilateral TIV flows — Canada ↔ allies (US, UK, AUS) vs adversary networks (RUS, CHN)"},
            {"name": "UN Comtrade Bilateral", "type": CROSS_VALIDATION, "date": "2023", "note": "USD trade values verify SIPRI TIV flow patterns"},
        ],
        "confidence": "HIGH",
        "confidence_note": "SIPRI TIV patterns cross-validated with Comtrade USD bilateral data",
        "health_keys": ["sipri_transfers", "comtrade_trade"],
    },
    "canada.threats": {
        "title": "Threat Watchlist — Source Validation",
        "sources": [
            {"name": "GDELT Global Knowledge Graph", "type": PRIMARY, "date": "15-min updates", "note": "Real-time event monitoring for threat indicators"},
            {"name": "Sanctions Lists (OFAC/EU/UN)", "type": PRIMARY, "date": "On-demand", "note": "Active sanctions against watchlist countries"},
            {"name": "Military Flight Tracker (4 ADS-B)", "type": PRIMARY, "date": "Live (60s)", "note": "Suspicious flight activity near Canadian airspace"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Multi-source threat indicators — GDELT provides breadth, sanctions provide depth, flights provide immediacy",
        "health_keys": ["gdelt_news"],
    },
    "canada.suppliers": {
        "title": "Defence Supply Base — Source Validation",
        "sources": [
            {"name": "DND Procurement Disclosure", "type": PRIMARY, "url": "https://open.canada.ca/", "date": "Weekly", "note": "Open Canada contract disclosures — vendor names, values, sectors"},
            {"name": "Wikidata SPARQL (Ownership)", "type": CROSS_VALIDATION, "url": "https://query.wikidata.org/", "date": "On-demand", "note": "Parent company chains and country of origin for ownership analysis"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Government procurement data is authoritative; Wikidata enriches ownership chains",
        "health_keys": ["suppliers"],
    },
    "canada.suppliers.risk": {
        "title": "Supplier Risk Ranking — Source Validation",
        "sources": [
            {"name": "PSI 6-Dimension Risk Scoring", "type": DERIVED, "date": "Computed", "note": "Foreign ownership, concentration, single-source, contract activity, sanctions exposure, performance — composite scoring engine"},
            {"name": "DND Procurement Data", "type": PRIMARY, "date": "Weekly", "note": "Contract values and frequency feed concentration and single-source dimensions"},
            {"name": "Sanctions Cross-Check", "type": PRIMARY, "date": "On-demand", "note": "OFAC/EU/UN lists checked against supplier ownership chains"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Scoring model uses real procurement data; some dimensions (performance) rely on limited historical data",
        "health_keys": ["suppliers"],
    },
    "canada.actions": {
        "title": "Action Centre (COAs) — Source Validation",
        "sources": [
            {"name": "Mitigation Playbook (191 entries)", "type": REFERENCE, "date": "2024", "note": "Courses of action across all 13 DND risk categories — auto-generated from risk scores"},
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "Risk taxonomy framework defining mitigation requirements"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "COA playbook is internally curated — mitigations are recommendations, not verified outcomes",
        "health_keys": [],
    },
    # --- Data Feeds ---
    "feeds": {
        "title": "Data Feeds — Source Validation",
        "sources": [
            {"name": "56 Active Data Source Connectors", "type": PRIMARY, "date": "Various", "note": "Live (60s) to Annual freshness across SIPRI, GDELT, Comtrade, NATO, DSCA, ADS-B, and 50 more"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Feed status is computed directly from connector runtime state",
        "health_keys": [],
    },
    "feeds.status": {
        "title": "Feed Health Cards — Source Validation",
        "sources": [
            {"name": "APScheduler Runtime", "type": PRIMARY, "date": "Live", "note": "Scheduler job status, last run time, next scheduled run"},
            {"name": "Connector Cache Metadata", "type": PRIMARY, "date": "Live", "note": "Per-connector cache timestamps and TTL status"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Health data comes directly from runtime — reflects actual connector state",
        "health_keys": [],
    },
    "feeds.stats": {
        "title": "Aggregate Feed Statistics — Source Validation",
        "sources": [
            {"name": "All Connector Caches", "type": DERIVED, "date": "Computed", "note": "Record counts, freshness percentages, error rates aggregated across all 56 connectors"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Computed directly from live connector state — always accurate",
        "health_keys": [],
    },
    # --- Compliance ---
    "compliance": {
        "title": "DMPP 11 Compliance — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 RFI Questions", "type": REFERENCE, "date": "2024", "note": "22 RFI questions with 118 sub-requirements defining PSI compliance"},
            {"name": "Internal Implementation Mapping", "type": DERIVED, "date": "2026-04-01", "note": "Traceability from each sub-requirement to implementing code/API/UI component"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Compliance mapping verified through cobalt-specific audit — 99% compliance achieved",
        "health_keys": [],
    },
    "compliance.matrix": {
        "title": "Compliance Matrix (22 Questions) — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 RFI", "type": REFERENCE, "date": "2024", "note": "Original 22 questions + 118 sub-requirements"},
            {"name": "Implementation Evidence", "type": DERIVED, "date": "2026-04-01", "note": "Each requirement mapped to API endpoint, UI component, or data source with View button for verification"},
            {"name": "Cobalt Compliance Audit", "type": CROSS_VALIDATION, "date": "2026-04-01", "note": "Full audit through cobalt lens: 8 gaps found, 7 fixed, 1 structural (NSN requires NMCRL)"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Traceability verified through cobalt audit — every sub-requirement has implementation evidence",
        "health_keys": [],
    },
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/source_registry.py tests/test_source_registry.py
git commit -m "feat: populate source registry — Canada Intel, Data Feeds, Compliance (11 keys)"
```

---

### Task 8: Populate Registry — Supply Chain Keys + Migrate BOM Validation

**Files:**
- Modify: `src/analysis/source_registry.py` (add ~20 entries)
- Modify: `src/analysis/mineral_supply_chains.py` (remove inline validation)
- Modify: `tests/test_source_registry.py` (extend completeness test)

- [ ] **Step 1: Add completeness test for Supply Chain keys**

Add to `tests/test_source_registry.py`:

```python
REQUIRED_KEYS_TASK8 = [
    "supply.overview", "supply.globe", "supply.graph", "supply.risks",
    "supply.scenarios", "supply.taxonomy", "supply.forecasting",
    "supply.bom", "supply.bom.mining", "supply.bom.processing",
    "supply.bom.alloys", "supply.bom.platforms",
    "supply.dossier", "supply.alerts", "supply.register",
    "supply.feedback", "supply.chokepoints", "supply.hhi",
    "supply.canada", "supply.risk_factors",
]


def test_required_keys_supply_chain():
    """All Supply Chain keys are present."""
    from src.analysis.source_registry import get_registry
    registry = get_registry()
    missing = [k for k in REQUIRED_KEYS_TASK8 if k not in registry]
    assert missing == [], f"Missing registry keys: {missing}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_source_registry.py::test_required_keys_supply_chain -v`
Expected: FAIL

- [ ] **Step 3: Add all Supply Chain entries**

Add to `_REGISTRY` in `src/analysis/source_registry.py`:

```python
    # --- Supply Chain ---
    "supply.overview": {
        "title": "Supply Chain Overview — Source Validation",
        "sources": [
            {"name": "PSI Supply Chain Analytics", "type": PRIMARY, "date": "Computed", "note": "Aggregated risk scores, active alerts, and graph metrics across 30 minerals"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Production data, reserves, and import reliance for critical minerals"},
        ],
        "confidence": "HIGH",
        "confidence_note": "PSI scoring derived from primary USGS + BGS + Comtrade data",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.globe": {
        "title": "3D Supply Chain Globe — Source Validation",
        "sources": [
            {"name": "Mineral Supply Chains Dataset", "type": PRIMARY, "date": "2025", "note": "30 minerals with geo-coordinates, 4-tier flow (mine→process→component→platform)"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "date": "January 2025", "note": "Country production shares and mine locations"},
            {"name": "Shipping Route Analysis", "type": DERIVED, "date": "Computed", "note": "6 corridors with chokepoint risk ratings and lead time estimates"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Geo-coordinates sourced from USGS/BGS; shipping routes from IMF PortWatch + canal authorities",
        "health_keys": ["usgs_mineral_deposits", "portwatch_chokepoints"],
    },
    "supply.graph": {
        "title": "Knowledge Graph — Source Validation",
        "sources": [
            {"name": "NetworkX Graph Engine", "type": DERIVED, "date": "Computed", "note": "90 nodes (materials, components, platforms), 97 edges, BOM explosion paths"},
            {"name": "Supply Chain Seed Data (20 platforms)", "type": REFERENCE, "date": "2025", "note": "Bill of materials for 20 defence platforms mapping subsystems→components→materials→countries"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Graph structure derived from curated BOM data — edge weights are estimated, not measured",
        "health_keys": [],
    },
    "supply.risks": {
        "title": "Risk Matrix — Source Validation",
        "sources": [
            {"name": "PSI 6-Dimension Risk Scoring", "type": DERIVED, "date": "Computed", "note": "Concentration (HHI), sanctions exposure, chokepoint risk, political instability, scarcity, alternatives"},
            {"name": "World Bank Governance Indicators", "type": PRIMARY, "date": "2023", "note": "Political stability and rule of law scores feed instability dimension"},
            {"name": "OFAC/EU/UN Sanctions", "type": PRIMARY, "date": "On-demand", "note": "Sanctions lists feed exposure dimension"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Each risk dimension backed by independent primary data — composite score is transparent",
        "health_keys": ["worldbank_governance", "un_sanctions"],
    },
    "supply.scenarios": {
        "title": "Scenario Sandbox — Source Validation",
        "sources": [
            {"name": "Scenario Engine (Multi-Variable)", "type": DERIVED, "date": "Computed", "note": "Stackable disruption layers: sanctions, shortages, route disruptions, supplier failures, demand surges"},
            {"name": "5 Preset Compound Scenarios", "type": REFERENCE, "date": "2025", "note": "Indo-Pacific Conflict, Arctic Escalation, Global Recession, DRC Collapse, Suez Closure"},
            {"name": "Cascade Propagation Model", "type": DERIVED, "date": "Computed", "note": "4-tier Sankey cascade: Rocks→Processing→Components→Platforms with Likelihood×Impact scoring"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Scenarios are analytical models, not predictions — impact estimates based on historical disruption data",
        "health_keys": [],
    },
    "supply.taxonomy": {
        "title": "Supply Chain Risk Taxonomy — Source Validation",
        "sources": [
            {"name": "DND DMPP 11 Annex B", "type": REFERENCE, "date": "2024", "note": "13-category, 121 sub-category risk taxonomy framework"},
            {"name": "Live OSINT Scoring", "type": PRIMARY, "date": "Real-time", "note": "4 categories scored live (GDELT + sanctions + PSI), 3 hybrid, 6 seeded with drift"},
            {"name": "World Bank WGI", "type": PRIMARY, "date": "2023", "note": "Governance indicators feed geopolitical risk categories"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "7 of 13 categories have live or hybrid scoring; 6 rely on seeded baseline with drift",
        "health_keys": ["gdelt_news", "worldbank_governance"],
    },
    "supply.forecasting": {
        "title": "Price Forecasting — Source Validation",
        "sources": [
            {"name": "IMF Primary Commodity Prices (PCOBALT)", "type": PRIMARY, "url": "https://www.imf.org/en/Research/commodity-prices", "date": "Monthly", "note": "Direct cobalt price series — primary forecast input"},
            {"name": "FRED Nickel Prices (PNICKUSDM)", "type": CROSS_VALIDATION, "url": "https://fred.stlouisfed.org/series/PNICKUSDM", "date": "Monthly", "note": "Fallback proxy when IMF cobalt data unavailable (0.85 correlation)"},
            {"name": "Linear Regression Model", "type": DERIVED, "date": "Computed", "note": "Quarterly regression with R², 90% prediction intervals (t-distribution), 3-scenario fan chart"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "IMF data is authoritative; linear model is simple but transparent — R² and CI published",
        "health_keys": ["imf_weo"],
    },
    "supply.bom": {
        "title": "BOM Explorer — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Country production shares for mining tier"},
            {"name": "AMS Material Specifications", "type": REFERENCE, "date": "Current", "note": "Aerospace material specs (5707, 5405, 5788, 5663) for alloy compositions"},
            {"name": "DND/Canada.ca Fleet Data", "type": PRIMARY, "date": "2024", "note": "CAF platform inventories and engine assignments"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Multi-tier BOM with independent sources per tier — confidence computed per tier from source count",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.bom.mining": {
        "title": "Mining / Extraction — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Country shares (DRC 76%, Indonesia 5%, Russia 5%, Australia 3%) from Table: Cobalt Mine Production"},
            {"name": "BGS World Mineral Statistics", "type": CROSS_VALIDATION, "url": "https://ogcapi.bgs.ac.uk/", "date": "2022-2023", "note": "Live API query confirms DRC dominance; pairwise discrepancy <10% with USGS"},
            {"name": "NRCan Canadian Mineral Production", "type": CROSS_VALIDATION, "date": "2023", "note": "Confirms Canada 3,900t cobalt production — matches USGS within 5%"},
            {"name": "UN Comtrade (HS 2605, 8105)", "type": TRADE_VALIDATION, "date": "Monthly", "note": "10 bilateral corridors queried; DRC→China $2.39B (2023) confirms flow direction"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across 4 independent sources with <10% pairwise discrepancy",
        "health_keys": ["usgs_mineral_deposits", "comtrade_trade"],
    },
    "supply.bom.processing": {
        "title": "Processing / Refining — Source Validation",
        "sources": [
            {"name": "USGS Mineral Commodity Summaries 2025", "type": PRIMARY, "url": "https://pubs.usgs.gov/periodicals/mcs2025/", "date": "January 2025", "note": "Refinery capacities and country shares (China 73% refining)"},
            {"name": "Cobalt Institute", "type": CROSS_VALIDATION, "url": "https://www.cobaltinstitute.org/", "date": "2024", "note": "Industry body refinery data and market reports"},
            {"name": "Company Financial Filings", "type": "Company reports", "date": "Quarterly", "note": "CMOC, Jinchuan, Umicore, Freeport annual reports for capacity verification"},
        ],
        "confidence": "HIGH",
        "confidence_note": "USGS primary, cross-validated with Cobalt Institute and company filings",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.bom.alloys": {
        "title": "Defence Alloys — Source Validation",
        "sources": [
            {"name": "AMS 5707 (Waspaloy)", "type": "Manufacturer datasheets", "date": "Current", "note": "13.5% Co — turbine discs, rings, casings"},
            {"name": "AMS 5405 (Stellite 6)", "type": "Manufacturer datasheets", "date": "Current", "note": "28% Co — wear-resistant valve seats, bushings"},
            {"name": "AMS 5788 (CMSX-4)", "type": "Manufacturer datasheets", "date": "Current", "note": "9.5% Co — single-crystal turbine blades"},
            {"name": "AMS 5663 (Inconel 718)", "type": "Manufacturer datasheets", "date": "Current", "note": "1% Co — structural forgings, fasteners"},
        ],
        "confidence": "HIGH",
        "confidence_note": "AMS specifications are definitive — cobalt percentages are metallurgical constants",
        "health_keys": [],
    },
    "supply.bom.platforms": {
        "title": "CAF Platforms & Engines — Source Validation",
        "sources": [
            {"name": "DND/Canada.ca Fleet Data", "type": PRIMARY, "url": "https://www.canada.ca/en/department-national-defence.html", "date": "2024", "note": "CF-188 Hornet, CP-140 Aurora, Halifax-class, Victoria-class fleet inventories"},
            {"name": "OEM Engine Catalogues", "type": REFERENCE, "date": "Current", "note": "GE F404, GE T64, GE LM2500, Rolls-Royce pressurized water reactor assignments"},
            {"name": "Jane's Defence Equipment", "type": REFERENCE, "date": "2024", "note": "Platform-engine-alloy dependency chains"},
            {"name": "Derived Demand Model", "type": DERIVED, "date": "Computed", "note": "Cobalt demand estimated from fleet size × engines/platform × Co content/engine"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Fleet data is authoritative; demand model is estimated from publicly available engine specifications",
        "health_keys": [],
    },
    "supply.dossier": {
        "title": "Supplier Dossiers — Source Validation",
        "sources": [
            {"name": "Company Financial Filings (SEC/Exchange)", "type": "Company reports", "date": "Quarterly", "note": "Balance sheets for Altman Z-Score computation (18 entities)"},
            {"name": "Wikidata SPARQL (Ownership)", "type": PRIMARY, "url": "https://query.wikidata.org/", "date": "On-demand", "note": "Ultimate beneficial owner (UBO) chains via parent_organization property"},
            {"name": "FOCI Scoring Model", "type": DERIVED, "date": "Computed", "note": "Foreign Ownership, Control, or Influence — 0-100 score from ownership chain + country risk"},
            {"name": "GDELT Intelligence Feed", "type": PRIMARY, "date": "15-min updates", "note": "Recent OSINT articles mentioning each entity"},
        ],
        "confidence": "HIGH",
        "confidence_note": "18 entities with real dossiers — financial data from filings, ownership from Wikidata, intel from GDELT",
        "health_keys": ["gdelt_news"],
    },
    "supply.alerts": {
        "title": "Watchtower Alerts — Source Validation",
        "sources": [
            {"name": "GDELT Keyword Monitoring", "type": PRIMARY, "date": "30-min cycle", "note": "8 keyword queries covering cobalt supply disruption, DRC, China refining, sanctions"},
            {"name": "Rule-Based Triggers", "type": DERIVED, "date": "Computed", "note": "HHI threshold, China refining share, paused operations — auto-generate alerts"},
            {"name": "6 Seed Alerts", "type": REFERENCE, "date": "2025", "note": "Baseline alerts for known risks: DRC instability, China concentration, shipping disruption"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "GDELT provides breadth; rule engine provides precision — SEEDED vs LIVE badges distinguish provenance",
        "health_keys": ["gdelt_news"],
    },
    "supply.register": {
        "title": "Risk Register — Source Validation",
        "sources": [
            {"name": "PSI Risk Scoring", "type": DERIVED, "date": "Computed", "note": "10 catalogued cobalt risks with severity, category, and linked COAs"},
            {"name": "Analyst Status Overrides", "type": PRIMARY, "date": "Persisted", "note": "Risk status (Open→In Progress→Mitigated→Closed) persisted to DB via analyst action"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "Risk identification is model-driven; risk status reflects analyst judgement",
        "health_keys": [],
    },
    "supply.feedback": {
        "title": "Analyst Feedback / RLHF — Source Validation",
        "sources": [
            {"name": "ML Anomaly Detection Engine", "type": DERIVED, "date": "Computed", "note": "Statistical anomaly detection with adaptive z-score thresholds"},
            {"name": "Analyst Adjudications", "type": PRIMARY, "date": "Persisted", "note": "Verified / False Positive feedback loop — adjusts detection thresholds via RLHF"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "ML accuracy improves with feedback — FP rate and threshold visible in panel",
        "health_keys": [],
    },
    "supply.chokepoints": {
        "title": "Strategic Chokepoints — Source Validation",
        "sources": [
            {"name": "IMF PortWatch", "type": PRIMARY, "url": "https://portwatch.imf.org/", "date": "2024", "note": "Maritime chokepoint trade volumes: Malacca, Suez, Cape, Panama, Bab-el-Mandeb, Hormuz"},
            {"name": "Canal Authority Reports", "type": REFERENCE, "date": "2024", "note": "Suez Canal Authority, Panama Canal Authority annual traffic and disruption reports"},
            {"name": "PSI Route Risk Analysis", "type": DERIVED, "date": "Computed", "note": "Lead time and delay estimates from route distance + chokepoint risk factor"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "IMF provides traffic data; risk estimates are model-derived from disruption history",
        "health_keys": ["portwatch_chokepoints"],
    },
    "supply.hhi": {
        "title": "HHI Concentration Index — Source Validation",
        "sources": [
            {"name": "BGS World Mineral Statistics (Live API)", "type": PRIMARY, "url": "https://ogcapi.bgs.ac.uk/", "date": "2022-2023", "note": "Live OGC API query for country production shares — HHI computed in real-time"},
            {"name": "USGS Mineral Commodity Summaries 2025", "type": CROSS_VALIDATION, "date": "January 2025", "note": "Cross-validates BGS production shares — pairwise discrepancy <10%"},
            {"name": "DoJ/FTC HHI Methodology", "type": REFERENCE, "date": "Current", "note": "Standard Herfindahl-Hirschman Index: <1500 low, 1500-2500 moderate, >2500 high concentration"},
        ],
        "confidence": "HIGH",
        "confidence_note": "HHI computed live from BGS API with USGS cross-validation — methodology follows DoJ/FTC standard",
        "health_keys": ["usgs_mineral_deposits"],
    },
    "supply.canada": {
        "title": "Canada Dependency — Source Validation",
        "sources": [
            {"name": "NRCan Canadian Mineral Production", "type": PRIMARY, "url": "https://natural-resources.canada.ca/", "date": "2023", "note": "Canadian cobalt production (3,900t), provincial breakdown"},
            {"name": "DND Fleet Data", "type": PRIMARY, "date": "2024", "note": "CAF platform inventories for demand-side estimation"},
            {"name": "Statistics Canada / UN Comtrade", "type": TRADE_VALIDATION, "date": "Monthly", "note": "Canadian cobalt import values and bilateral corridors"},
            {"name": "Derived Demand Model", "type": DERIVED, "date": "Computed", "note": "Estimates direct CAF cobalt demand from fleet × engines × alloy content"},
        ],
        "confidence": "MEDIUM",
        "confidence_note": "NRCan production is authoritative; demand model is derived from public fleet data",
        "health_keys": ["comtrade_trade"],
    },
    "supply.risk_factors": {
        "title": "Risk Factors — Source Validation",
        "sources": [
            {"name": "USGS Critical Minerals List 2024", "type": PRIMARY, "url": "https://www.usgs.gov/news/national-news-release/us-geological-survey-releases-2022-list-critical-minerals", "date": "2024", "note": "Cobalt classified as critical mineral — import reliance, disruption risk"},
            {"name": "DRC Ministry of Mines", "type": PRIMARY, "date": "2024", "note": "Artisanal mining regulations, export controls, taxation policy"},
            {"name": "Cobalt Institute Market Reports", "type": CROSS_VALIDATION, "url": "https://www.cobaltinstitute.org/", "date": "2024", "note": "Supply-demand balance, inventory levels, market outlook"},
        ],
        "confidence": "HIGH",
        "confidence_note": "Risk factors backed by USGS critical mineral designation + DRC regulatory data + industry reports",
        "health_keys": ["usgs_mineral_deposits"],
    },
```

- [ ] **Step 4: Migrate existing BOM validation data out of mineral_supply_chains.py**

In `src/analysis/mineral_supply_chains.py`, find the Cobalt mineral entry's `"validation"` key (around line 2119–2201). Remove the entire `"validation": { ... }` block from the Cobalt data. The data is now served from `source_registry.py` instead.

Keep the rest of the mineral data intact — only remove the `"validation"` key and its value.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: All tests PASS

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests pass. If any existing tests reference `mineral.validation`, they may need updating to use the new registry. Check for failures in `test_mineral_supply_chains.py` or similar.

- [ ] **Step 6: Commit**

```bash
git add src/analysis/source_registry.py src/analysis/mineral_supply_chains.py tests/test_source_registry.py
git commit -m "feat: populate source registry — Supply Chain (20 keys) + migrate BOM validation"
```

---

### Task 9: Migrate BOM Explorer Rendering to New System

**Files:**
- Modify: `src/static/index.html` (update BOM render functions to use validationManager)

This task replaces the old `renderBomValBtn()` / `toggleBomVal()` calls in the BOM Explorer with the new `validationManager.attach()` system.

- [ ] **Step 1: Update BOM Explorer render function**

In `src/static/index.html`, find the `renderBomExplorer()` function (or wherever BOM tree HTML is built). Replace all calls to `renderBomValBtn(tierKey, validation)` with section containers that can be targeted by `validationManager.attach()`.

For each BOM tier section, ensure it has a class or identifier the attach call can target. For example, replace:

```javascript
html += renderBomValBtn('mining', val);
```

with a wrapper div:

```javascript
html += '<div class="bom-tier-section" data-tier="mining">';
// ... existing mining tier content ...
html += '</div>';
```

Then after setting `container.innerHTML = html`, add the attach calls:

```javascript
container.querySelectorAll('.bom-tier-section').forEach(function(sec) {
  var tier = sec.getAttribute('data-tier');
  if (tier) validationManager.attach(sec, 'supply.bom.' + tier);
});
```

Also attach the overall BOM panel:

```javascript
validationManager.attach(container, 'supply.bom');
```

- [ ] **Step 2: Remove old renderBomValBtn and toggleBomVal if no longer used**

Check if `renderBomValBtn` and `toggleBomVal` are called anywhere else in index.html (search for `renderBomValBtn` and `toggleBomVal`). If they are only used in BOM Explorer and Overview, and both have been migrated, remove the old function definitions and the `_bomValId` counter.

If `renderMineralOverview()` also calls `renderBomValBtn()`, update it similarly — replace those calls with `data-tier` wrapper divs and `validationManager.attach()` after innerHTML is set.

- [ ] **Step 3: Manual test — verify BOM Explorer panels work with new system**

Run: `python -m src.main`
Navigate to Supply Chain > BOM Explorer. Verify:
- Validation panels appear on each BOM tier (Mining, Processing, Alloys, Platforms)
- Panels expand/collapse correctly
- Source citations match the registry data
- Data Health row shows live metrics
- No JS errors in console

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "refactor: migrate BOM Explorer from renderBomValBtn to validationManager"
```

---

### Task 10: Full Integration Test + Regression Check

**Files:**
- Modify: `tests/test_source_registry.py` (add full registry integrity test)

- [ ] **Step 1: Add comprehensive registry integrity test**

```python
def test_full_registry_integrity():
    """Every registry key resolves and has valid shape."""
    from src.analysis.source_registry import get_registry, resolve_sources

    registry = get_registry()
    all_keys = (
        REQUIRED_KEYS + REQUIRED_KEYS_TASK7 + REQUIRED_KEYS_TASK8
    )

    # All required keys exist
    missing = [k for k in all_keys if k not in registry]
    assert missing == [], f"Missing registry keys: {missing}"

    # Every key resolves (including inherited ones that aren't in registry directly)
    test_inherited = [
        "arctic.kpis",  # inherits from arctic
        "arctic.kpis.threat_level",  # inherits from arctic
        "deals.transfers.row",  # inherits from deals.transfers
    ]
    for key in test_inherited:
        result = resolve_sources(key)
        assert result is not None, f"Inherited key {key} did not resolve"

    # Total key count
    assert len(registry) >= 51, f"Expected >= 51 keys, got {len(registry)}"
```

- [ ] **Step 2: Run all source registry tests**

Run: `python -m pytest tests/test_source_registry.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run full project test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All 295+ tests PASS with 0 new failures

- [ ] **Step 4: Manual smoke test across all tabs**

Run: `python -m src.main`
Open: `http://localhost:8000`

Verify on each tab:
- **Insights**: Panels on sitrep, taxonomy strip, news, DSCA, alliances, adversary sections
- **Arctic**: Panels on KPIs, bases table, flights, routes table, trade cards, naval section
- **Deals**: Panel on transfers table
- **Canada Intel**: Panels on flows, threats, suppliers, actions
- **Supply Chain > Overview**: Panel on overview card
- **Supply Chain > BOM Explorer**: Per-tier panels (mining, processing, alloys, platforms)
- **Supply Chain > each sub-tab**: Panel on each section
- **Data Feeds**: Panels on feed cards and stats
- **Compliance**: Panel on compliance matrix

All panels should:
- Show collapsed by default with confidence badge + source count
- Expand on click with full source citations
- Show live Data Health row with last fetch, records, cache status
- Show confidence assessment at bottom

- [ ] **Step 5: Commit**

```bash
git add tests/test_source_registry.py
git commit -m "test: add full registry integrity and regression tests"
```

---

## Summary

| Task | Description | Keys Added | Files |
|------|-------------|------------|-------|
| 1 | Source registry core + key resolution | 3 seed | source_registry.py, test |
| 2 | API endpoints (/validation/sources, /health) | 0 | validation_routes.py, main.py, test |
| 3 | Frontend JS module + CSS | 0 | index.html |
| 4 | Attach panels — static HTML elements | 0 | index.html |
| 5 | Attach panels — dynamic content | 0 | index.html |
| 6 | Populate registry — Insights + Arctic + Deals | ~20 | source_registry.py, test |
| 7 | Populate registry — Canada + Feeds + Compliance | ~11 | source_registry.py, test |
| 8 | Populate registry — Supply Chain + migrate BOM | ~20 | source_registry.py, mineral_supply_chains.py, test |
| 9 | Migrate BOM Explorer to new system | 0 | index.html |
| 10 | Full integration test + regression | 0 | test |

**Total: ~51 explicit registry keys, 10 tasks, 10 commits**
