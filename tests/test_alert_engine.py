"""Tests for cobalt alert engine."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.analysis.cobalt_alert_engine import (
    COBALT_GDELT_QUERIES,
    generate_gdelt_alerts,
    generate_rule_alerts,
    run_cobalt_alert_engine,
    _apply_aging,
)


class TestGDELTQueryCoverage:
    """Verify all 8 GDELT queries are executed."""

    @pytest.mark.asyncio
    async def test_all_8_queries_executed(self):
        queries_called = []

        async def mock_search(query, timespan="1440", max_records=5):
            queries_called.append(query)
            return []

        with patch("src.ingestion.gdelt_news.GDELTArmsNewsClient") as MockClient:
            instance = MockClient.return_value
            instance.search_articles = mock_search
            await generate_gdelt_alerts()

        assert len(queries_called) == 8, f"Expected 8 queries, got {len(queries_called)}"
        for q in COBALT_GDELT_QUERIES:
            assert q in queries_called, f"Query not called: {q}"

    def test_query_count_matches_constant(self):
        assert len(COBALT_GDELT_QUERIES) == 8


class TestAlertAging:
    """Verify alert severity is reduced for old alerts."""

    def test_fresh_alert_keeps_severity(self):
        alert = {"severity": 5, "timestamp": datetime.now(timezone.utc).isoformat()}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 5
        assert result.get("aged") is not True

    def test_8_day_old_alert_reduced(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 4
        assert result["aged"] is True

    def test_35_day_old_alert_capped_at_1(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 1
        assert result["aged"] is True

    def test_95_day_old_alert_excluded(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(days=95)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is None

    def test_unparseable_timestamp_kept(self):
        alert = {"severity": 3, "timestamp": "not-a-date"}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 3
