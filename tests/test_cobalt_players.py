"""Tests for cobalt supply chain player monitoring."""
from __future__ import annotations

from src.ingestion.cobalt_players import CobaltPlayersClient, COBALT_PLAYERS


class TestCobaltPlayersClient:
    def test_all_tickers_defined(self):
        assert len(COBALT_PLAYERS) == 15

    def test_roles_present(self):
        roles = {m["role"] for m in COBALT_PLAYERS.values()}
        assert "miner" in roles
        assert "refiner" in roles
        assert "battery" in roles
        assert "oem" in roles

    def test_fallback_data_complete(self):
        client = CobaltPlayersClient()
        data = client._fallback_data()
        assert len(data) == 15
        for player in data:
            assert "ticker" in player
            assert "name" in player
            assert "role" in player
            assert "price" in player
            assert "market_cap_usd" in player
            assert player["price"] >= 0

    def test_fallback_has_sherritt(self):
        client = CobaltPlayersClient()
        data = client._fallback_data()
        sherritt = [p for p in data if p["ticker"] == "S.TO"]
        assert len(sherritt) == 1
        assert sherritt[0]["name"] == "Sherritt International"
        assert sherritt[0]["country"] == "Canada"

    def test_fallback_has_oems(self):
        client = CobaltPlayersClient()
        data = client._fallback_data()
        oems = [p for p in data if p["role"] == "oem"]
        assert len(oems) == 3
        names = {p["name"] for p in oems}
        assert "RTX Corporation" in names
        assert "GE Aerospace" in names
        assert "Lockheed Martin" in names

    def test_canadian_players(self):
        canadian = [m for m in COBALT_PLAYERS.values() if m["country"] == "Canada"]
        assert len(canadian) == 1  # Sherritt
        assert canadian[0]["name"] == "Sherritt International"

    def test_chinese_players(self):
        chinese = [m for m in COBALT_PLAYERS.values() if m["country"] == "China"]
        assert len(chinese) >= 4  # CMOC, Huayou, GEM, CATL, BYD
