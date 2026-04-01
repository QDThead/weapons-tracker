"""Tests for Comtrade cobalt bilateral trade flow queries."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from src.ingestion.comtrade import (
    ComtradeMaterialsClient,
    COMTRADE_COUNTRY_CODES,
    MATERIAL_SOURCE_COUNTRIES,
    COBALT_BILATERAL_CORRIDORS,
    ComtradeRecord,
)


class TestCobaltM49Codes:
    """Verify all cobalt-relevant countries have M49 codes."""

    def test_belgium_in_codes(self):
        assert "Belgium" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Belgium"] == 56

    def test_finland_in_codes(self):
        assert "Finland" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Finland"] == 246

    def test_zambia_in_codes(self):
        assert "Zambia" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Zambia"] == 894

    def test_cuba_in_codes(self):
        assert "Cuba" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Cuba"] == 192

    def test_morocco_in_codes(self):
        assert "Morocco" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Morocco"] == 504

    def test_madagascar_in_codes(self):
        assert "Madagascar" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Madagascar"] == 450

    def test_drc_in_codes(self):
        assert "DRC" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["DRC"] == 180

    def test_cobalt_source_countries_expanded(self):
        sources = MATERIAL_SOURCE_COUNTRIES["cobalt"]
        assert 180 in sources  # DRC
        assert 156 in sources  # China
        assert 246 in sources  # Finland
        assert 56 in sources   # Belgium
        assert 124 in sources  # Canada


class TestCobaltBilateralCorridors:
    """Verify corridor definitions."""

    def test_corridors_defined(self):
        assert len(COBALT_BILATERAL_CORRIDORS) >= 6

    def test_drc_china_corridor(self):
        drc_china = [c for c in COBALT_BILATERAL_CORRIDORS if c["reporter"] == 156 and c["partner"] == 180]
        assert len(drc_china) > 0, "DRC->China corridor (buyer-side: China reports imports FROM DRC)"


class TestFetchCobaltBilateralFlows:
    """Test the bilateral query function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_records(self):
        client = ComtradeMaterialsClient(subscription_key="test-key")
        mock_records = [
            ComtradeRecord(
                reporter="China", reporter_iso="CHN", partner="Congo", partner_iso="COD",
                year=2023, flow="Import", hs_code="810520",
                hs_description="Cobalt unwrought/powder",
                trade_value_usd=2_390_000_000, quantity=85000, net_weight_kg=85000000,
            ),
        ]
        with patch.object(client, "fetch", new_callable=AsyncMock, return_value=mock_records):
            results = await client.fetch_cobalt_bilateral_flows(years=[2023])
        assert len(results) > 0
        assert results[0].trade_value_usd == 2_390_000_000

    @pytest.mark.asyncio
    async def test_uses_buyer_side_mirror_for_drc(self):
        """DRC corridors should query the IMPORTER (e.g., China), not DRC."""
        client = ComtradeMaterialsClient(subscription_key="test-key")
        queries_made = []

        async def capture_fetch(query):
            queries_made.append(query)
            return []

        client.fetch = capture_fetch
        await client.fetch_cobalt_bilateral_flows(years=[2023])
        has_buyer_mirror = any(
            156 in q.reporter_codes and 180 in q.partner_codes and "M" in q.flow_codes
            for q in queries_made
        )
        assert has_buyer_mirror, "Should use buyer-side mirror: China reports imports FROM DRC"
