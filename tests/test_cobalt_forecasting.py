"""Tests for cobalt forecasting confidence formula."""
from __future__ import annotations

from src.analysis.cobalt_forecasting import _compute_price_forecast


class TestForecastConfidence:
    """Verify forecast confidence is conservative and honest."""

    def _make_prices(self, n_months: int, base: float = 30000, slope: float = 100) -> list[dict]:
        prices = []
        for i in range(n_months):
            year = 2024 + i // 12
            month = (i % 12) + 1
            prices.append({"date": f"{year}-{month:02d}", "usd_mt": base + slope * i})
        return prices

    def test_mediocre_fit_low_confidence(self):
        """R²~0.5 with 8 quarters should NOT give 70%+ confidence."""
        import random
        random.seed(42)
        prices = []
        for i in range(24):
            year = 2024 + i // 12
            month = (i % 12) + 1
            noise = random.uniform(-5000, 5000)
            prices.append({"date": f"{year}-{month:02d}", "usd_mt": 30000 + 200 * i + noise})
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf < 55, f"Confidence {conf}% too high for mediocre R²"

    def test_strong_fit_reasonable_confidence(self):
        prices = self._make_prices(36, base=30000, slope=200)
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert 50 <= conf <= 85, f"Confidence {conf}% out of range for strong fit"

    def test_few_quarters_low_confidence(self):
        prices = self._make_prices(6, base=30000, slope=200)
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf < 40, f"Confidence {conf}% too high for only 2 quarters"

    def test_confidence_never_exceeds_85(self):
        prices = self._make_prices(60, base=30000, slope=200)
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf <= 85, f"Confidence {conf}% exceeds 85% cap"


import json
import os
import tempfile


class TestForecastSnapshot:
    """Verify forecast snapshots are saved for future backtesting."""

    def test_snapshot_writes_json(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            forecast = {
                "price_forecast": {
                    "pct_change": 5.0,
                    "direction": "up",
                    "confidence_pct": 45,
                    "r_squared": 0.6,
                },
                "price_history": [{"quarter": "Q1 2026", "usd_mt": 30000, "type": "forecast"}],
            }
            _store_forecast_snapshot(forecast, path=path)
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert "snapshot_date" in data[0]
            assert data[0]["price_forecast"]["r_squared"] == 0.6

    def test_snapshot_appends_not_overwrites(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            forecast = {"price_forecast": {"pct_change": 5.0, "r_squared": 0.6}, "price_history": []}
            _store_forecast_snapshot(forecast, path=path)
            _store_forecast_snapshot(forecast, path=path)
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 2


class TestForecastSnapshotCap:
    def test_snapshot_capped_at_1000(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            existing = [{"snapshot_date": f"2026-01-{i % 28 + 1:02d}", "price_forecast": {}, "predictions": []} for i in range(999)]
            with open(path, "w") as f:
                json.dump(existing, f)
            forecast = {"price_forecast": {"r_squared": 0.5}, "price_history": []}
            _store_forecast_snapshot(forecast, path=path)
            _store_forecast_snapshot(forecast, path=path)
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 1000
