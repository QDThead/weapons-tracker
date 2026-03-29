"""tests/test_supplier_routes.py"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService
from src.api.routes import app
from src.api.supplier_routes import router as supplier_router

# Register supplier routes on app (main.py does this at startup)
app.include_router(supplier_router)


def _seed():
    init_db()
    session = SessionLocal()
    svc = PersistenceService(session)
    s1 = svc.upsert_supplier(
        name="Irving Shipbuilding", sector=SupplierSector.SHIPBUILDING,
        ownership_type=OwnershipType.CANADIAN_PRIVATE,
    )
    s1.risk_score_composite = 72.0
    s2 = svc.upsert_supplier(
        name="GD Land Systems Canada", sector=SupplierSector.LAND_VEHICLES,
        ownership_type=OwnershipType.FOREIGN_SUBSIDIARY,
        parent_company="General Dynamics", parent_country="United States",
    )
    s2.risk_score_composite = 55.0
    svc.upsert_contract(
        supplier_id=s1.id, contract_number="CSC-001",
        contract_value_cad=30e9, sector=SupplierSector.SHIPBUILDING,
        status=ContractStatus.ACTIVE, award_date=date(2023, 1, 1),
    )
    svc.upsert_contract(
        supplier_id=s2.id, contract_number="LAV-001",
        contract_value_cad=5e9, sector=SupplierSector.LAND_VEHICLES,
        status=ContractStatus.ACTIVE, award_date=date(2023, 6, 1),
    )
    svc.upsert_risk_score(s1.id, RiskDimension.SINGLE_SOURCE, 90.0, "Sole shipbuilder")
    svc.upsert_risk_score(s2.id, RiskDimension.FOREIGN_OWNERSHIP, 50.0, "US subsidiary")
    session.commit()
    session.close()


client = TestClient(app)


def test_get_suppliers():
    _seed()
    resp = client.get("/dashboard/suppliers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_suppliers"] >= 2
    names = [s["name"] for s in data["suppliers"]]
    assert "Irving Shipbuilding" in names


def test_get_supplier_profile():
    _seed()
    resp = client.get("/dashboard/suppliers/Irving Shipbuilding/profile")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Irving Shipbuilding"
    assert data["sector"] == "shipbuilding"
    assert len(data["contracts"]) >= 1


def test_get_supplier_profile_not_found():
    _seed()
    resp = client.get("/dashboard/suppliers/NonexistentCorp/profile")
    assert resp.status_code == 404


def test_get_concentration():
    _seed()
    resp = client.get("/dashboard/suppliers/concentration")
    assert resp.status_code == 200
    data = resp.json()
    sectors = {s["sector"] for s in data["sectors"]}
    assert "shipbuilding" in sectors


def test_get_risk_matrix():
    _seed()
    resp = client.get("/dashboard/suppliers/risk-matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["points"]) >= 2
    assert all("x" in p and "y" in p for p in data["points"])


def test_get_ownership():
    _seed()
    resp = client.get("/dashboard/suppliers/ownership")
    assert resp.status_code == 200
    data = resp.json()
    assert "breakdown" in data
    assert len(data["foreign_suppliers"]) >= 1
    # At least one foreign supplier should have a parent country
    parent_countries = [f["parent_country"] for f in data["foreign_suppliers"] if f.get("parent_country")]
    assert len(parent_countries) >= 1


def test_get_alerts():
    _seed()
    resp = client.get("/dashboard/suppliers/alerts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["alerts"]) >= 1
