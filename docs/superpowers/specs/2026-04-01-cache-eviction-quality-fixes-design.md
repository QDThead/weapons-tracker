# Design Spec: Cache Eviction + Quality Fixes

**Date:** 2026-04-01
**Scope:** Fix unbounded cache growth (memory leak), CSS accessibility gaps, connection pool config, forecast snapshot cap

---

## Context

Quality audit found that all ~15 in-memory caches across API route files grow unbounded — expired entries are checked by TTL on read but never removed from the dict. Over weeks of uptime, this leaks memory. Additionally, CSS is missing focus states for keyboard accessibility, and the SQLAlchemy connection pool has no configuration.

---

## 1. Shared TTLCache Utility

**New file:** `src/utils/cache.py`

A lightweight TTL cache with max-size eviction. No external dependencies.

```python
class TTLCache:
    """Thread-safe TTL cache with max-size eviction."""

    def __init__(self, ttl_seconds: int, max_size: int = 500):
        self._store: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl_seconds
        self._max_size = max_size

    def get(self, key: str) -> Any | None:
        """Return cached value if key exists and not expired, else None."""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, value = entry
        if time.time() - ts >= self._ttl:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        """Store value. Evicts expired entries and oldest if over max_size."""
        self._evict_expired()
        self._store[key] = (time.time(), value)
        if len(self._store) > self._max_size:
            self._evict_oldest()

    def _evict_expired(self) -> None:
        """Remove all entries past TTL."""
        now = time.time()
        expired = [k for k, (ts, _) in self._store.items() if now - ts >= self._ttl]
        for k in expired:
            del self._store[k]

    def _evict_oldest(self) -> None:
        """Remove oldest entries until at max_size."""
        while len(self._store) > self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
```

Also create `src/utils/__init__.py` (empty).

---

## 2. Route File Migration

Replace raw dict caches with TTLCache instances. Each file follows the same mechanical pattern:

**Before (typical pattern):**
```python
_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 900  # 15 min

async def get_something():
    key = "something"
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return data
    data = await fetch_data()
    _cache[key] = (time.time(), data)
    return data
```

**After:**
```python
from src.utils.cache import TTLCache
_cache = TTLCache(ttl_seconds=900, max_size=200)

async def get_something():
    cached = _cache.get("something")
    if cached is not None:
        return cached
    data = await fetch_data()
    _cache.set("something", data)
    return data
```

### Files to migrate:

| File | Cache Variables | TTL | Max Size |
|------|----------------|-----|----------|
| `dashboard_routes.py` | `_comtrade_cache`, `_buyer_mirror_cache`, `_news_cache`, `_dsca_cache`, `_census_cache`, `_nato_cache`, `_hmrc_cache`, `_eurostat_cache`, `_statcan_cache`, `_flight_analysis_cache`, `_sanctions_cache` | Various (900-86400s) | 200 each |
| `arctic_routes.py` | `_arctic_cache` | 300s | 100 |
| `psi_routes.py` | `_psi_cache` | 1800s | 200 |
| `supplier_routes.py` | `_cache` | 900s | 100 |
| `mitigation_routes.py` | `_cache` | 900s | 100 |
| `enrichment_routes.py` | `_cache` | 3600s | 300 |
| `validation_routes.py` | Uses caches from other modules (reads only) | N/A | N/A |
| `cyber_threat_intel.py` | `_CYBER_CACHE` | 21600s | 50 |

**validation_routes.py note:** This file imports private cache dicts from other modules to check health. After migration, it needs to import the TTLCache instances instead. The health check logic changes from `key in _cache` to checking `len(cache)` or similar.

---

## 3. Forecast Snapshot Cap

**File:** `src/analysis/cobalt_forecasting.py`

In `_store_forecast_snapshot()`, after appending the new snapshot, trim to max 1000 entries:

```python
    existing.append(snapshot)
    if len(existing) > 1000:
        existing = existing[-1000:]
```

---

## 4. CSS Accessibility Fixes

**File:** `src/static/index.html` (style block)

### Focus states (add near end of style block):

```css
.btn-primary:focus-visible,
.bom-validate-btn:focus-visible,
.feeds-refresh-btn:focus-visible,
.compliance-filter:focus-visible,
.cc-view-btn:focus-visible,
.extra-view-btn:focus-visible,
.nav-tab:focus-visible {
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

### WebKit backdrop-filter prefixes:

Find `.nav-dropdown-menu` and `.suf-coa-card` — add `-webkit-backdrop-filter: blur(16px);` before the existing `backdrop-filter: blur(16px);` line.

---

## 5. Connection Pool Configuration

**File:** `src/storage/database.py`

Add pool configuration for non-SQLite databases:

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

---

## Test Plan

| Area | Tests |
|------|-------|
| TTLCache.get() returns None for expired | Unit test |
| TTLCache.set() evicts expired entries | Unit test |
| TTLCache max_size enforcement | Unit test |
| TTLCache.get() returns value within TTL | Unit test |
| Forecast snapshot trim to 1000 | Unit test |
| Connection pool config (non-sqlite) | Unit test |
| Existing test suite passes | Regression |

---

## Out of Scope

- Async SQLAlchemy migration (documented as future work)
- Pagination on supplier routes (needs API contract change)
- Error response standardization (larger refactor)
- Redis or external cache (overkill for current scale)
