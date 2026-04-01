"""Tests for financial scoring and Sherritt connector."""
from __future__ import annotations

import pytest
from src.analysis.financial_scoring import compute_altman_z, compute_sherritt_z_score
from src.ingestion.sherritt_cobalt import SherrittCobaltClient


class TestAltmanZScore:
    def test_healthy_company(self):
        """A healthy company should be in the safe zone."""
        result = compute_altman_z({
            "total_assets_usd_m": 10000,
            "total_liabilities_usd_m": 4000,
            "working_capital_usd_m": 2000,
            "retained_earnings_usd_m": 3000,
            "ebit_usd_m": 1500,
            "revenue_usd_m": 8000,
            "market_cap_usd_m": 15000,
            "source": "test",
        })
        assert result["zone"] == "safe"
        assert result["z_score"] > 2.99

    def test_distressed_company(self):
        """A distressed company should be in the distress zone."""
        result = compute_altman_z({
            "total_assets_usd_m": 1850,
            "total_liabilities_usd_m": 1620,
            "working_capital_usd_m": -45,
            "retained_earnings_usd_m": -890,
            "ebit_usd_m": 15,
            "revenue_usd_m": 380,
            "market_cap_usd_m": 41,
            "source": "test",
        })
        assert result["zone"] == "distress"
        assert result["z_score"] < 1.81

    def test_zero_assets_returns_error(self):
        result = compute_altman_z({"total_assets_usd_m": 0, "total_liabilities_usd_m": 100})
        assert result["zone"] == "insufficient_data"

    def test_components_present(self):
        result = compute_altman_z({
            "total_assets_usd_m": 1000,
            "total_liabilities_usd_m": 500,
            "working_capital_usd_m": 200,
            "retained_earnings_usd_m": 100,
            "ebit_usd_m": 50,
            "revenue_usd_m": 400,
            "market_cap_usd_m": 800,
            "source": "test",
        })
        assert "components" in result
        assert "x1_working_capital_ratio" in result["components"]


class TestSherrittZScore:
    def test_sherritt_is_distressed(self):
        """Sherritt with real Q3 2025 financials should be in distress zone."""
        client = SherrittCobaltClient()
        financials = client._fallback_financials()
        result = compute_sherritt_z_score(financials)
        assert result["zone"] == "distress"
        assert result["z_score"] < 1.81
        assert result["entity"] == "Sherritt International"


class TestSherrittClient:
    def test_fallback_stock(self):
        client = SherrittCobaltClient()
        data = client._fallback_stock()
        assert data["ticker"] == "S.TO"
        assert data["price_cad"] > 0
        assert data["shares_outstanding"] > 0

    def test_fallback_ops(self):
        client = SherrittCobaltClient()
        data = client._fallback_ops()
        assert data["moa_jv_status"] == "paused"
        assert data["fort_saskatchewan_status"] == "operating"

    def test_fallback_financials(self):
        client = SherrittCobaltClient()
        data = client._fallback_financials()
        assert data["total_assets_usd_m"] > 0
        assert data["total_liabilities_usd_m"] > 0
        assert "period" in data
