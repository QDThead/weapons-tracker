from __future__ import annotations

from fastapi.testclient import TestClient


def _get_client():
    from src.main import app
    return TestClient(app)


def test_get_validation_sources():
    """GET /validation/sources returns full registry."""
    client = _get_client()
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


def test_get_validation_health():
    """GET /validation/health returns health data per connector."""
    client = _get_client()
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


def test_validation_sources_contains_arctic():
    """Registry contains arctic keys from seed data."""
    client = _get_client()
    resp = client.get("/validation/sources")
    data = resp.json()
    assert "arctic" in data["registry"]
    assert "arctic.bases" in data["registry"]
