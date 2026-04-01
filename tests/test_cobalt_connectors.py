"""Tests for cobalt-specific data source connectors."""
from __future__ import annotations

import pytest
from src.ingestion.bgs_minerals import BGSCobaltClient
from src.ingestion.nrcan_cobalt import NRCanCobaltClient


class TestBGSCobaltClient:
    def test_fallback_data_structure(self):
        client = BGSCobaltClient()
        data = client._fallback_data()
        assert len(data) > 0
        for entry in data:
            assert "country" in entry
            assert "year" in entry
            assert "production_tonnes" in entry
            assert "source" in entry
            assert isinstance(entry["production_tonnes"], (int, float))

    def test_fallback_has_drc(self):
        client = BGSCobaltClient()
        data = client._fallback_data()
        countries = [d["country"] for d in data]
        assert "Congo (Kinshasa)" in countries

    def test_fallback_has_canada(self):
        client = BGSCobaltClient()
        data = client._fallback_data()
        countries = [d["country"] for d in data]
        assert "Canada" in countries


class TestNRCanCobaltClient:
    def test_fallback_data_structure(self):
        client = NRCanCobaltClient()
        data = client._fallback_data()
        assert "production_tonnes" in data
        assert "provinces" in data
        assert "key_producers" in data
        assert isinstance(data["production_tonnes"], int)

    def test_fallback_has_provinces(self):
        client = NRCanCobaltClient()
        data = client._fallback_data()
        provinces = [p["name"] for p in data["provinces"]]
        assert "Quebec" in provinces
        assert "Ontario" in provinces
        assert "Newfoundland and Labrador" in provinces

    def test_fallback_shares_sum_to_100(self):
        client = NRCanCobaltClient()
        data = client._fallback_data()
        total = sum(p["share_pct"] for p in data["provinces"])
        assert total == 100

    def test_fallback_production_reasonable(self):
        client = NRCanCobaltClient()
        data = client._fallback_data()
        assert 1000 < data["production_tonnes"] < 10000
