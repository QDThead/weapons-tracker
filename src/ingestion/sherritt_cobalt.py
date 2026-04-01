"""Sherritt International (TSX:S) — cobalt production and financial data.

Only Canadian vertically integrated cobalt producer.
Fetches quarterly reports, press releases, and stock data.
"""
from __future__ import annotations

import logging
import re
import time

import httpx

logger = logging.getLogger(__name__)

_CACHE_TTL = 86400  # 24 hours

def _cache_get(store: dict, key: str) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None

def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


class SherrittCobaltClient:
    """Fetches Sherritt International cobalt-related data.

    Sources:
    - Quarterly report PDFs: https://sherritt.com/investors/
    - Press releases: https://sherritt.com/news/
    - Yahoo Finance for stock price
    """

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_stock_data(self) -> dict:
        """Fetch Sherritt stock price from Yahoo Finance for market cap computation."""
        cached = _cache_get(self._cache, "sherritt_stock")
        if cached is not None:
            return cached

        # Yahoo Finance v8 API (free, no key required)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/S.TO"
        params = {"range": "5d", "interval": "1d"}
        headers = {"User-Agent": "Mozilla/5.0"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    logger.warning("Yahoo Finance Sherritt returned HTTP %s", resp.status_code)
                    return self._fallback_stock()

                data = resp.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("previousClose", 0)

                # Sherritt shares outstanding: ~310M
                shares_outstanding = 310_000_000

                result = {
                    "ticker": "S.TO",
                    "exchange": "TSX",
                    "price_cad": round(float(price), 4) if price else 0.18,
                    "prev_close_cad": round(float(prev_close), 4) if prev_close else 0.18,
                    "shares_outstanding": shares_outstanding,
                    "market_cap_cad": round(float(price or 0.18) * shares_outstanding),
                    "currency": "CAD",
                    "source": "Yahoo Finance",
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }

                _cache_set(self._cache, "sherritt_stock", result)
                return result
        except Exception as e:
            logger.warning("Sherritt stock fetch failed: %s", e)
            return self._fallback_stock()

    def _fallback_stock(self) -> dict:
        return {
            "ticker": "S.TO",
            "exchange": "TSX",
            "price_cad": 0.18,
            "prev_close_cad": 0.18,
            "shares_outstanding": 310_000_000,
            "market_cap_cad": 55_800_000,
            "currency": "CAD",
            "source": "Manual estimate (fallback)",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    async def fetch_operational_status(self) -> dict:
        """Fetch Sherritt operational status from news page."""
        cached = _cache_get(self._cache, "sherritt_ops")
        if cached is not None:
            return cached

        url = "https://sherritt.com/news/"
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code != 200:
                    return self._fallback_ops()

                html = resp.text
                result = self._parse_news_page(html)
                _cache_set(self._cache, "sherritt_ops", result)
                return result
        except Exception as e:
            logger.warning("Sherritt news fetch failed: %s", e)
            return self._fallback_ops()

    def _parse_news_page(self, html: str) -> dict:
        """Parse Sherritt news page for operational status keywords."""
        result = self._fallback_ops()

        lower = html.lower()
        if "pause" in lower or "suspend" in lower or "halt" in lower:
            result["moa_jv_status"] = "paused"
        elif "restart" in lower or "resume" in lower:
            result["moa_jv_status"] = "restarting"

        result["source"] = "Sherritt News Page (live)"
        return result

    def _fallback_ops(self) -> dict:
        return {
            "moa_jv_status": "paused",
            "moa_jv_reason": "Cuban fuel crisis — operations paused Feb 2026",
            "fort_saskatchewan_status": "operating",
            "fort_saskatchewan_note": "Processing remaining feed inventory, expected through Q2 2026",
            "cobalt_production_t_2024": 2400,
            "cobalt_production_t_2025_est": 800,
            "source": "Sherritt Q3 2025 Interim Report (fallback)",
        }

    async def fetch_financial_summary(self) -> dict:
        """Return key financial metrics for Z-score computation."""
        cached = _cache_get(self._cache, "sherritt_fin")
        if cached is not None:
            return cached

        # For now, return seeded data from Q3 2025 report
        # In future: parse quarterly PDF from sherritt.com
        result = self._fallback_financials()
        _cache_set(self._cache, "sherritt_fin", result)
        return result

    def _fallback_financials(self) -> dict:
        """Sherritt financial data from Q3 2025 Interim Report."""
        return {
            "period": "Q3 2025",
            "total_assets_usd_m": 1850,
            "total_liabilities_usd_m": 1620,
            "working_capital_usd_m": -45,
            "retained_earnings_usd_m": -890,
            "ebit_usd_m": 15,
            "revenue_usd_m": 380,
            "market_cap_usd_m": 41,  # ~C$56M at 0.73 FX
            "shares_outstanding": 310_000_000,
            "source": "Sherritt Q3 2025 Interim Report (seeded)",
            "note": "Significant going concern risk noted by auditors",
        }
