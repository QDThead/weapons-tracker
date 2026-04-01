"""Cobalt supply chain player monitoring — stock prices and financial data.

Monitors all major publicly listed companies in the cobalt supply chain
using Yahoo Finance. Covers miners, refiners, battery makers, and OEMs.
"""
from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

_CACHE_TTL = 3600  # 1 hour for stock data

def _cache_get(store: dict, key: str) -> object | None:
    entry = store.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    return None

def _cache_set(store: dict, key: str, value: object) -> None:
    store[key] = (time.time(), value)


# All major cobalt supply chain tickers with metadata
COBALT_PLAYERS = {
    # Mining companies
    "3993.HK": {"name": "CMOC Group", "role": "miner", "country": "China", "cobalt_relevance": "World's largest cobalt miner, owns TFM + Kisanfu (DRC)"},
    "GLEN.L": {"name": "Glencore", "role": "miner", "country": "Switzerland", "cobalt_relevance": "Kamoto, Mutanda, Murrin Murrin, Raglan — major Western producer"},
    "S.TO": {"name": "Sherritt International", "role": "miner_refiner", "country": "Canada", "cobalt_relevance": "Only Canadian vertically integrated cobalt producer"},
    "VALE": {"name": "Vale S.A.", "role": "miner_refiner", "country": "Brazil", "cobalt_relevance": "Voisey's Bay mine + Long Harbour refinery (Canada)"},
    # Refiners
    "603799.SS": {"name": "Huayou Cobalt", "role": "refiner", "country": "China", "cobalt_relevance": "World's largest cobalt refiner"},
    "002340.SZ": {"name": "GEM Co.", "role": "refiner", "country": "China", "cobalt_relevance": "Major cobalt recycler, Taixing refinery"},
    "UMI.BR": {"name": "Umicore", "role": "refiner", "country": "Belgium", "cobalt_relevance": "Kokkola + Hoboken refineries — key Western refining"},
    "5713.T": {"name": "Sumitomo Metal Mining", "role": "refiner", "country": "Japan", "cobalt_relevance": "Niihama refinery — Japan's only cobalt refiner"},
    # Battery / downstream
    "300750.SZ": {"name": "CATL", "role": "battery", "country": "China", "cobalt_relevance": "23.75% owner of Kisanfu, world's largest battery maker"},
    "1211.HK": {"name": "BYD", "role": "battery", "country": "China", "cobalt_relevance": "Major EV battery consumer"},
    "006400.KS": {"name": "Samsung SDI", "role": "battery", "country": "South Korea", "cobalt_relevance": "NMC battery cathode consumer"},
    "373220.KS": {"name": "LG Energy Solution", "role": "battery", "country": "South Korea", "cobalt_relevance": "NMC battery cathode consumer"},
    # Defence OEMs (Canada depends on these)
    "RTX": {"name": "RTX Corporation", "role": "oem", "country": "US", "cobalt_relevance": "Pratt & Whitney F135 engine (F-35) — CMSX-4 cobalt superalloy"},
    "GE": {"name": "GE Aerospace", "role": "oem", "country": "US", "cobalt_relevance": "F404 engine (CF-188) — Waspaloy cobalt alloy"},
    "LMT": {"name": "Lockheed Martin", "role": "oem", "country": "US", "cobalt_relevance": "F-35 prime contractor — Canada acquiring 88 aircraft"},
}


class CobaltPlayersClient:
    """Monitors stock prices and financial health for all cobalt supply chain players."""

    _cache: dict = {}

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_all_players(self) -> list[dict]:
        """Return stock data for all cobalt supply chain players.

        Returns list of {ticker, name, role, country, price, market_cap_usd,
        currency, change_pct, cobalt_relevance, source}
        """
        cached = _cache_get(self._cache, "cobalt_players_all")
        if cached is not None:
            return cached

        try:
            results = await asyncio.to_thread(self._fetch_all_sync)
            _cache_set(self._cache, "cobalt_players_all", results)
            return results
        except Exception as e:
            logger.warning("Cobalt players fetch failed: %s", e)
            return self._fallback_data()

    def _fetch_all_sync(self) -> list[dict]:
        """Synchronous yfinance fetch for all tickers."""
        try:
            import yfinance as yf
        except ImportError:
            logger.warning("yfinance not installed, using fallback data")
            return self._fallback_data()

        tickers_str = " ".join(COBALT_PLAYERS.keys())
        yf.download(tickers_str, period="5d", interval="1d", group_by="ticker", progress=False, threads=True)

        results = []
        for ticker, meta in COBALT_PLAYERS.items():
            try:
                info = yf.Ticker(ticker).fast_info
                price = getattr(info, "last_price", None) or 0
                market_cap = getattr(info, "market_cap", None) or 0
                currency = getattr(info, "currency", "USD") or "USD"
                prev_close = getattr(info, "previous_close", None) or price
                change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

                results.append({
                    "ticker": ticker,
                    "name": meta["name"],
                    "role": meta["role"],
                    "country": meta["country"],
                    "price": round(float(price), 4),
                    "market_cap_usd": int(market_cap),
                    "currency": currency,
                    "change_pct": change_pct,
                    "cobalt_relevance": meta["cobalt_relevance"],
                    "source": "Yahoo Finance",
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })
            except Exception as e:
                logger.debug("Failed to fetch %s: %s", ticker, e)
                results.append({
                    "ticker": ticker,
                    "name": meta["name"],
                    "role": meta["role"],
                    "country": meta["country"],
                    "price": 0,
                    "market_cap_usd": 0,
                    "currency": "USD",
                    "change_pct": 0,
                    "cobalt_relevance": meta["cobalt_relevance"],
                    "source": "Yahoo Finance (failed)",
                    "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                })

        logger.info("Fetched stock data for %d cobalt supply chain players", len(results))
        return results

    async def fetch_player(self, ticker: str) -> dict:
        """Fetch data for a single player by ticker."""
        all_players = await self.fetch_all_players()
        for p in all_players:
            if p["ticker"] == ticker:
                return p
        return {"error": f"Ticker {ticker} not found in cobalt players"}

    async def fetch_by_role(self, role: str) -> list[dict]:
        """Fetch players filtered by role (miner, refiner, battery, oem)."""
        all_players = await self.fetch_all_players()
        return [p for p in all_players if role in p["role"]]

    def _fallback_data(self) -> list[dict]:
        """Static fallback data for all players."""
        fallback_prices = {
            "3993.HK": 6.50, "GLEN.L": 4.20, "S.TO": 0.18, "VALE": 10.50,
            "603799.SS": 28.00, "002340.SZ": 7.50, "UMI.BR": 12.00, "5713.T": 3800,
            "300750.SZ": 210.00, "1211.HK": 280.00, "006400.KS": 180000, "373220.KS": 350000,
            "RTX": 130.00, "GE": 200.00, "LMT": 480.00,
        }
        fallback_mcap = {
            "3993.HK": 14_000_000_000, "GLEN.L": 55_000_000_000, "S.TO": 56_000_000,
            "VALE": 45_000_000_000, "603799.SS": 12_000_000_000, "002340.SZ": 4_000_000_000,
            "UMI.BR": 3_000_000_000, "5713.T": 10_000_000_000, "300750.SZ": 900_000_000_000,
            "1211.HK": 800_000_000_000, "006400.KS": 20_000_000_000, "373220.KS": 35_000_000_000,
            "RTX": 155_000_000_000, "GE": 215_000_000_000, "LMT": 125_000_000_000,
        }
        results = []
        for ticker, meta in COBALT_PLAYERS.items():
            results.append({
                "ticker": ticker,
                "name": meta["name"],
                "role": meta["role"],
                "country": meta["country"],
                "price": fallback_prices.get(ticker, 0),
                "market_cap_usd": fallback_mcap.get(ticker, 0),
                "currency": "USD",
                "change_pct": 0,
                "cobalt_relevance": meta["cobalt_relevance"],
                "source": "Estimated (fallback)",
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            })
        return results
