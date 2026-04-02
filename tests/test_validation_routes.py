from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    """Create a fresh test client that won't conflict with other test files."""
    from src.api.validation_routes import router
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


def test_get_validation_sources(client):
    """GET /validation/sources returns full registry."""
    resp = client.get("/validation/sources")
    assert resp.status_code == 200
    data = resp.json()
    assert "registry" in data
    assert "total_keys" in data
    assert "source_types" in data
    assert isinstance(data["registry"], dict)
    assert data["total_keys"] >= 3
    for key, entry in data["registry"].items():
        assert "title" in entry
        assert "sources" in entry
        assert "confidence" in entry


def test_get_validation_health(client):
    """GET /validation/health returns health data per connector."""
    resp = client.get("/validation/health")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert len(data) >= 1
    for connector_key, health in data.items():
        assert "last_fetch" in health
        assert "records" in health
        assert "cache_status" in health
        assert "health" in health
        assert health["cache_status"] in ("FRESH", "STALE", "EXPIRED", "UNKNOWN")
        assert health["health"] in ("OK", "STALE", "ERROR", "UNKNOWN")


def test_validation_sources_contains_arctic(client):
    """Registry contains arctic keys from seed data."""
    resp = client.get("/validation/sources")
    data = resp.json()
    assert "arctic" in data["registry"]
    assert "arctic.bases" in data["registry"]
