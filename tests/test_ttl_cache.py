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
        cache.set("d", 4)
        assert len(cache) <= 3
        assert cache.get("d") == 4

    def test_oldest_evicted_first(self):
        cache = TTLCache(ttl_seconds=60, max_size=2)
        cache.set("first", 1)
        time.sleep(0.01)
        cache.set("second", 2)
        cache.set("third", 3)
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
