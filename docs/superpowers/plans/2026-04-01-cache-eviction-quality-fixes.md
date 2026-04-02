# Cache Eviction + Quality Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix unbounded in-memory cache growth (memory leak) across all API routes, add CSS accessibility focus states, configure connection pool, and cap forecast snapshots.

**Architecture:** Create a shared `TTLCache` class, then mechanically replace all raw dict caches across 8 files. Update validation_routes.py to read from the new cache objects. Add CSS focus-visible states and webkit prefixes. Add pool config for non-SQLite.

**Tech Stack:** Python 3.9+ (FastAPI, SQLAlchemy), CSS, pytest

**Spec:** `docs/superpowers/specs/2026-04-01-cache-eviction-quality-fixes-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/utils/__init__.py` | NEW — empty package init |
| `src/utils/cache.py` | NEW — TTLCache class |
| `tests/test_ttl_cache.py` | NEW — TTLCache unit tests |
| `src/api/dashboard_routes.py` | MODIFY — replace 11 raw dict caches |
| `src/api/arctic_routes.py` | MODIFY — replace `_arctic_cache` |
| `src/api/psi_routes.py` | MODIFY — replace `_psi_cache` |
| `src/api/supplier_routes.py` | MODIFY — replace `_cache` |
| `src/api/mitigation_routes.py` | MODIFY — replace `_cache` |
| `src/api/enrichment_routes.py` | MODIFY — replace `_cache` |
| `src/api/validation_routes.py` | MODIFY — update imports to use TTLCache |
| `src/analysis/cyber_threat_intel.py` | MODIFY — replace `_CYBER_CACHE` |
| `src/analysis/cobalt_forecasting.py` | MODIFY — add snapshot cap |
| `src/static/index.html` | MODIFY — CSS focus states + webkit prefixes |
| `src/storage/database.py` | MODIFY — connection pool config |

---

### Task 1: Create TTLCache Utility + Tests

**Files:**
- Create: `src/utils/__init__.py`
- Create: `src/utils/cache.py`
- Create: `tests/test_ttl_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ttl_cache.py`:
```python
"""Tests for TTLCache utility."""
from __future__ import annotations

import time
from unittest.mock import patch

from src.utils.cache import TTLCache


class TestTTLCacheGet:
    def test_returns_none_for_missing_key(self):
        cache = TTLCache(ttl_seconds=60)
        assert cache.get("missing") is None

    def test_returns_value_within_ttl(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key", {"data": 123})
        assert cache.get("key") == {"data": 123}

    def test_returns_none_after_expiry(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set("key", "value")
        with patch("src.utils.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            assert cache.get("key") is None


class TestTTLCacheEviction:
    def test_expired_entries_removed_on_set(self):
        cache = TTLCache(ttl_seconds=1)
        cache.set("old", "data")
        with patch("src.utils.cache.time") as mock_time:
            mock_time.time.return_value = time.time() + 2
            cache.set("new", "data")
            assert "old" not in cache._store
            assert cache.get("new") == "data"

    def test_max_size_enforced(self):
        cache = TTLCache(ttl_seconds=60, max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict oldest
        assert len(cache) <= 3
        assert cache.get("d") == 4

    def test_oldest_evicted_first(self):
        cache = TTLCache(ttl_seconds=60, max_size=2)
        cache.set("first", 1)
        time.sleep(0.01)
        cache.set("second", 2)
        cache.set("third", 3)  # Evicts "first"
        assert cache.get("first") is None
        assert cache.get("second") == 2
        assert cache.get("third") == 3


class TestTTLCacheClear:
    def test_clear_removes_all(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None


class TestTTLCacheLen:
    def test_len_counts_entries(self):
        cache = TTLCache(ttl_seconds=60)
        assert len(cache) == 0
        cache.set("a", 1)
        assert len(cache) == 1
        cache.set("b", 2)
        assert len(cache) == 2


class TestTTLCacheHealthInfo:
    def test_health_returns_entry_info(self):
        cache = TTLCache(ttl_seconds=60)
        cache.set("key", [1, 2, 3])
        info = cache.health("key")
        assert info is not None
        assert info["exists"] is True
        assert "age_seconds" in info
        assert info["age_seconds"] < 2

    def test_health_returns_none_for_missing(self):
        cache = TTLCache(ttl_seconds=60)
        info = cache.health("missing")
        assert info is not None
        assert info["exists"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_ttl_cache.py -v -p no:recording`
Expected: FAIL — module not found

- [ ] **Step 3: Create the utils package and TTLCache**

Create `src/utils/__init__.py` (empty file).

Create `src/utils/cache.py`:
```python
"""Shared TTL cache with max-size eviction.

Replaces raw dict caches across all API route files.
Entries are evicted when expired (on read/write) and
oldest entries are dropped when max_size is exceeded.
"""
from __future__ import annotations

import time
from typing import Any


class TTLCache:
    """In-memory TTL cache with max-size eviction."""

    __slots__ = ("_store", "_ttl", "_max_size")

    def __init__(self, ttl_seconds: int, max_size: int = 500) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        """Return cached value if exists and not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts >= self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Store value. Evicts expired entries, then oldest if over max_size."""
        self._evict_expired()
        self._store[key] = (time.time(), value)
        if len(self._store) > self._max_size:
            self._evict_oldest()

    def health(self, key: str) -> dict:
        """Return health info for a cache key (for validation_routes)."""
        entry = self._store.get(key)
        if entry is None:
            return {"exists": False, "age_seconds": None}
        ts, _ = entry
        return {"exists": True, "age_seconds": round(time.time() - ts, 1)}

    def has_any(self) -> bool:
        """Return True if cache has any non-expired entries."""
        self._evict_expired()
        return len(self._store) > 0

    def clear(self) -> None:
        """Remove all entries."""
        self._store.clear()

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts >= self._ttl]
        for k in expired:
            del self._store[k]

    def _evict_oldest(self) -> None:
        while len(self._store) > self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]

    def __len__(self) -> int:
        return len(self._store)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_ttl_cache.py -v -p no:recording`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/__init__.py src/utils/cache.py tests/test_ttl_cache.py
git commit -m "feat: add TTLCache utility with max-size eviction"
```

---

### Task 2: Migrate dashboard_routes.py Caches

**Files:**
- Modify: `src/api/dashboard_routes.py`

This file has 11 separate cache dicts, each with its own TTL constant. Replace all with TTLCache instances.

- [ ] **Step 1: Replace cache declarations**

At the top of `dashboard_routes.py`, after existing imports, add:
```python
from src.utils.cache import TTLCache
```

Then replace all 11 cache dict + TTL constant pairs. Find and replace each pair. The pattern for each:

**Before (example — _comtrade_cache):**
```python
_comtrade_cache: dict[str, tuple[float, list]] = {}
_COMTRADE_TTL = 3600
```

**After:**
```python
_comtrade_cache = TTLCache(ttl_seconds=3600, max_size=200)
```

Do this for ALL 11 caches, preserving variable names but removing the TTL constants:

| Old Dict | Old TTL Constant | TTL Value | New Declaration |
|----------|-----------------|-----------|-----------------|
| `_comtrade_cache` | `_COMTRADE_TTL` | 3600 | `_comtrade_cache = TTLCache(ttl_seconds=3600, max_size=200)` |
| `_buyer_mirror_cache` | `_BUYER_MIRROR_TTL` | 3600 | `_buyer_mirror_cache = TTLCache(ttl_seconds=3600, max_size=50)` |
| `_news_cache` | `_NEWS_TTL` | 900 | `_news_cache = TTLCache(ttl_seconds=900, max_size=100)` |
| `_dsca_cache` | `_DSCA_TTL` | 3600 | `_dsca_cache = TTLCache(ttl_seconds=3600, max_size=50)` |
| `_census_cache` | `_CENSUS_TTL` | 3600 | `_census_cache = TTLCache(ttl_seconds=3600, max_size=50)` |
| `_nato_cache` | `_NATO_TTL` | 86400 | `_nato_cache = TTLCache(ttl_seconds=86400, max_size=50)` |
| `_hmrc_cache` | `_HMRC_TTL` | 3600 | `_hmrc_cache = TTLCache(ttl_seconds=3600, max_size=50)` |
| `_eurostat_cache` | `_EUROSTAT_TTL` | 3600 | `_eurostat_cache = TTLCache(ttl_seconds=3600, max_size=50)` |
| `_statcan_cache` | `_STATCAN_TTL` | 86400 | `_statcan_cache = TTLCache(ttl_seconds=86400, max_size=50)` |
| `_flight_analysis_cache` | `_FLIGHT_ANALYSIS_TTL` | 300 | `_flight_analysis_cache = TTLCache(ttl_seconds=300, max_size=20)` |
| `_sanctions_cache` | `_SANCTIONS_TTL` | 3600 | `_sanctions_cache = TTLCache(ttl_seconds=3600, max_size=100)` |

- [ ] **Step 2: Replace cache read patterns**

Find every cache read pattern in the file. The typical pattern is:
```python
    if key in _some_cache:
        ts, data = _some_cache[key]
        if time.time() - ts < _SOME_TTL:
            return data
```

Replace with:
```python
    cached = _some_cache.get(key)
    if cached is not None:
        return cached
```

- [ ] **Step 3: Replace cache write patterns**

Find every cache write pattern:
```python
    _some_cache[key] = (time.time(), data)
```

Replace with:
```python
    _some_cache.set(key, data)
```

- [ ] **Step 4: Remove orphaned TTL constant references**

After replacing all reads/writes, delete the 11 TTL constant lines (e.g., `_COMTRADE_TTL = 3600`). Also remove any `import time` if it was only used for cache timestamps (check if `time` is used elsewhere in the file first).

- [ ] **Step 5: Run existing tests**

Run: `python -m pytest tests/ -q -p no:recording --ignore=tests/test_adversarial.py --ignore=tests/test_scenario_adversarial.py --ignore=tests/test_scenario_api.py -x`
Expected: ALL PASS (no behavior change — same TTLs, same keys)

- [ ] **Step 6: Commit**

```bash
git add src/api/dashboard_routes.py
git commit -m "fix: replace 11 unbounded dict caches with TTLCache in dashboard_routes"
```

---

### Task 3: Migrate Remaining Route Caches

**Files:**
- Modify: `src/api/arctic_routes.py`
- Modify: `src/api/psi_routes.py`
- Modify: `src/api/supplier_routes.py`
- Modify: `src/api/mitigation_routes.py`
- Modify: `src/api/enrichment_routes.py`
- Modify: `src/analysis/cyber_threat_intel.py`

Same mechanical pattern as Task 2 for each file.

- [ ] **Step 1: Migrate arctic_routes.py**

Add `from src.utils.cache import TTLCache` to imports.

Replace the 1 cache dict + 3 TTL constants:
```python
_arctic_cache = TTLCache(ttl_seconds=300, max_size=100)
```
Remove `_ARCTIC_TTL = 300`, `_BASES_TTL = 3600`, `_CURRENT_TTL = 3600`.

**IMPORTANT:** This file uses different TTLs for different keys within the same cache dict. Since TTLCache has a single TTL, create 3 separate caches:
```python
_arctic_cache = TTLCache(ttl_seconds=300, max_size=50)      # assessments, flights
_arctic_bases_cache = TTLCache(ttl_seconds=3600, max_size=10) # bases
_arctic_current_cache = TTLCache(ttl_seconds=3600, max_size=10) # current intel
```

Then update the read/write patterns for each key to use the appropriate cache. Keys that previously checked `_BASES_TTL` should use `_arctic_bases_cache`, keys that checked `_CURRENT_TTL` use `_arctic_current_cache`, all others use `_arctic_cache`.

Replace all `if key in _arctic_cache: ts, data = _arctic_cache[key]; if time.time() - ts < TTL:` patterns with `cached = _arctic_X_cache.get(key); if cached is not None:`.

Replace all `_arctic_cache[key] = (time.time(), data)` with `_arctic_X_cache.set(key, data)`.

- [ ] **Step 2: Migrate psi_routes.py**

Add `from src.utils.cache import TTLCache` to imports.

This file has 1 dict with 3 TTLs and helper functions `_check_cache(key, ttl)` / `_set_cache(key, data)`. Create 3 caches:
```python
_psi_cache = TTLCache(ttl_seconds=300, max_size=200)          # general PSI data
_psi_graph_cache = TTLCache(ttl_seconds=3600, max_size=50)    # graph endpoints
_psi_taxonomy_cache = TTLCache(ttl_seconds=3600, max_size=50) # taxonomy endpoints
```

Remove `_PSI_TTL`, `_PSI_GRAPH_TTL`, `_PSI_TAXONOMY_TTL` constants.

Replace the `_check_cache` and `_set_cache` helper functions with direct `.get()` / `.set()` calls, using the appropriate cache based on which TTL was previously passed.

- [ ] **Step 3: Migrate supplier_routes.py**

Add `from src.utils.cache import TTLCache`.

Replace:
```python
_cache: dict[str, tuple[float, Any]] = {}
_TTL = 300
```
With:
```python
_cache = TTLCache(ttl_seconds=300, max_size=100)
```

Remove `_TTL` constant. Replace `_check_cache` and `_set_cache` helpers with direct `.get()` / `.set()` calls.

- [ ] **Step 4: Migrate mitigation_routes.py**

Add `from src.utils.cache import TTLCache`.

Replace:
```python
_cache: dict[str, tuple[float, dict]] = {}
_TTL = 300
```
With:
```python
_cache = TTLCache(ttl_seconds=300, max_size=100)
```

Remove `_TTL` constant. Replace `_check_cache`, `_set_cache`, `_clear_cache` helpers. The `_clear_cache()` becomes `_cache.clear()`.

- [ ] **Step 5: Migrate enrichment_routes.py**

Add `from src.utils.cache import TTLCache`.

Replace:
```python
_cache: dict[str, tuple[float, Any]] = {}
_TTL = 3600
```
With:
```python
_cache = TTLCache(ttl_seconds=3600, max_size=300)
```

Remove `_TTL` constant. This file has a `_get_cached(key)` helper pattern — replace with `_cache.get(key)`. Replace all `_cache[key] = (time.time(), data)` with `_cache.set(key, data)`.

- [ ] **Step 6: Migrate cyber_threat_intel.py**

Add `from src.utils.cache import TTLCache`.

Replace:
```python
_CYBER_CACHE: dict[str, tuple[float, Any]] = {}
_CYBER_TTL = 21600
```
With:
```python
_CYBER_CACHE = TTLCache(ttl_seconds=21600, max_size=50)
```

Remove `_CYBER_TTL` constant. Replace all read/write patterns.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -q -p no:recording --ignore=tests/test_adversarial.py --ignore=tests/test_scenario_adversarial.py --ignore=tests/test_scenario_api.py -x`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/arctic_routes.py src/api/psi_routes.py src/api/supplier_routes.py src/api/mitigation_routes.py src/api/enrichment_routes.py src/analysis/cyber_threat_intel.py
git commit -m "fix: replace unbounded dict caches with TTLCache in 6 modules"
```

---

### Task 4: Update validation_routes.py Cache Imports

**Files:**
- Modify: `src/api/validation_routes.py`

This file imports raw cache dicts from other modules to check health status. After migration, the cache objects are TTLCache instances instead of raw dicts, so the health-check code needs updating.

- [ ] **Step 1: Update the health check logic**

In `_get_connector_specs()` (around line 112), the code checks cache health by looking into raw dicts. The TTLCache class now has a `.health(key)` method that returns `{exists, age_seconds}`.

Update the enrichment section (lines 116-141):
```python
    try:
        from src.api.enrichment_routes import _cache as enrich_cache
        enrichment_connectors = [
            # ... same list of tuples ...
        ]
        for key, cache_key, ttl in enrichment_connectors:
            specs.append({"key": key, "cache_obj": enrich_cache, "cache_key": cache_key, "expected_ttl": ttl})
    except ImportError:
        pass
```

Update dashboard imports (lines 144-149):
```python
    try:
        from src.api.dashboard_routes import _buyer_mirror_cache, _comtrade_cache, _news_cache
        specs.append({"key": "comtrade_trade", "cache_obj": _comtrade_cache, "cache_key": "comtrade:*", "expected_ttl": 3600})
        specs.append({"key": "buyer_mirror", "cache_obj": _buyer_mirror_cache, "cache_key": "mirror:*", "expected_ttl": 3600})
        specs.append({"key": "gdelt_news", "cache_obj": _news_cache, "cache_key": "news:*", "expected_ttl": 900})
    except ImportError:
        pass
```

Update supplier import (lines 151-154):
```python
    try:
        from src.api.supplier_routes import _cache as supplier_cache
        specs.append({"key": "suppliers", "cache_obj": supplier_cache, "cache_key": "suppliers", "expected_ttl": 3600})
    except ImportError:
        pass
```

Then update `_build_health()` (around line 72) to use the TTLCache `.health()` method instead of raw dict access. The current pattern accesses `cache_dict[cache_key]` directly — change to:
```python
    cache_obj = spec.get("cache_obj") or spec.get("cache_dict")
    if hasattr(cache_obj, "health"):
        info = cache_obj.health(spec["cache_key"])
        if info["exists"]:
            entry["last_fetch"] = ...  # compute from age_seconds
            entry["cache_status"] = "OK" if info["age_seconds"] < spec["expected_ttl"] else "STALE"
    elif isinstance(cache_obj, dict):
        # Legacy fallback for any remaining raw dicts
        ...
```

Also update `_sources_cache` and `_health_cache` in validation_routes.py itself:
```python
from src.utils.cache import TTLCache
_sources_cache = TTLCache(ttl_seconds=3600, max_size=5)
_health_cache = TTLCache(ttl_seconds=60, max_size=5)
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_validation_routes.py tests/test_ttl_cache.py -v -p no:recording`
Expected: PASS (or same pre-existing failures from async issues)

- [ ] **Step 3: Commit**

```bash
git add src/api/validation_routes.py
git commit -m "fix: update validation_routes to use TTLCache health() method"
```

---

### Task 5: Forecast Snapshot Cap + Connection Pool + CSS

**Files:**
- Modify: `src/analysis/cobalt_forecasting.py`
- Modify: `src/storage/database.py`
- Modify: `src/static/index.html`

- [ ] **Step 1: Add snapshot cap**

In `src/analysis/cobalt_forecasting.py`, in `_store_forecast_snapshot()`, after the line `existing.append(snapshot)` (line ~528), add:
```python
    # Keep only last 1000 snapshots to prevent unbounded growth
    if len(existing) > 1000:
        existing = existing[-1000:]
```

- [ ] **Step 2: Add snapshot cap test**

Add to `tests/test_cobalt_forecasting.py`:
```python
class TestForecastSnapshotCap:
    def test_snapshot_capped_at_1000(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            # Pre-populate with 999 entries
            existing = [{"snapshot_date": f"2026-01-{i:02d}", "price_forecast": {}, "predictions": []} for i in range(999)]
            with open(path, "w") as f:
                json.dump(existing, f)
            # Add 2 more (total 1001 -> should trim to 1000)
            forecast = {"price_forecast": {"r_squared": 0.5}, "price_history": []}
            _store_forecast_snapshot(forecast, path=path)
            _store_forecast_snapshot(forecast, path=path)
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 1000
```

- [ ] **Step 3: Add connection pool config**

In `src/storage/database.py`, replace line 13:
```python
engine = create_engine(DATABASE_URL, echo=False)
```
With:
```python
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False)
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=5,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
```

- [ ] **Step 4: Add CSS focus states and webkit prefixes**

In `src/static/index.html`, in the `<style>` block, find the `.nav-dropdown-menu` selector (around line 136) and add before the `backdrop-filter: blur(16px);` line:
```css
    -webkit-backdrop-filter: blur(16px);
```

Find the `.suf-coa-card` selector (around line 1073) and add before the `backdrop-filter: blur(16px);` line:
```css
    -webkit-backdrop-filter: blur(16px);
```

Add at the end of the `<style>` block (before `</style>`):
```css
/* Keyboard focus states — WCAG 2.1 AA */
.btn-primary:focus-visible,
.bom-validate-btn:focus-visible,
.feeds-refresh-btn:focus-visible,
.compliance-filter:focus-visible,
.cc-view-btn:focus-visible,
.extra-view-btn:focus-visible,
.nav-tab:focus-visible,
.psi-tab-btn:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
.news-item a:focus-visible,
.arctic-news-item a:focus-visible,
.ins-country-link:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
}
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_cobalt_forecasting.py tests/test_ttl_cache.py -v -p no:recording`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add src/analysis/cobalt_forecasting.py tests/test_cobalt_forecasting.py src/storage/database.py src/static/index.html
git commit -m "fix: forecast snapshot cap (1000), connection pool config, CSS focus states"
```

---

## Verification

After all 5 tasks complete:

1. Run full test suite: `python -m pytest tests/ -q -p no:recording --ignore=tests/test_adversarial.py --ignore=tests/test_scenario_adversarial.py --ignore=tests/test_scenario_api.py`
2. Verify TTLCache is used everywhere: `grep -r "dict\[str, tuple\[float" src/` should return NO results (all raw dict caches replaced)
3. Start server: `python -m src.main` — verify dashboard loads, compliance page works, data feeds show freshness
