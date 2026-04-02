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
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]

    def oldest_entry(self) -> tuple[float, Any] | None:
        """Return (timestamp, value) of the oldest non-expired entry, or None."""
        self._evict_expired()
        if not self._store:
            return None
        oldest_key = next(iter(self._store))
        return self._store[oldest_key]

    def __len__(self) -> int:
        return len(self._store)
