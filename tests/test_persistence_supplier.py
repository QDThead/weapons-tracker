"""tests/test_persistence_supplier.py"""
from __future__ import annotations

from datetime import date, datetime

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService


def _fresh_session():
    init_db()
    return SessionLocal()


def test_upsert_supplier_creates_new():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(
            name="Irving Shipbuilding",
            sector=SupplierSector.SHIPBUILDING,
            ownership_type=OwnershipType.CANADIAN_PRIVATE,
        )
        result = session.query(DefenceSupplier).filter_by(name="Irving Shipbuilding").first()
        assert result is not None
        assert result.sector == SupplierSector.SHIPBUILDING
    finally:
        session.close()


def test_upsert_supplier_updates_existing():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="CAE", sector=SupplierSector.SIMULATION)
        svc.upsert_supplier(name="CAE", sector=SupplierSector.SIMULATION, parent_company="Test Parent")
        results = session.query(DefenceSupplier).filter_by(name="CAE").all()
        assert len(results) == 1
        assert results[0].parent_company == "Test Parent"
    finally:
        session.close()


def test_upsert_contract():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="GD Canada", sector=SupplierSector.LAND_VEHICLES)
        supplier = session.query(DefenceSupplier).filter_by(name="GD Canada").first()
        svc.upsert_contract(
            supplier_id=supplier.id,
            contract_number="W8486-12345",
            contract_value_cad=500000000.0,
            department="DND",
            award_date=date(2023, 6, 15),
            sector=SupplierSector.LAND_VEHICLES,
        )
        contract = session.query(SupplierContract).filter_by(contract_number="W8486-12345").first()
        assert contract is not None
        assert contract.contract_value_cad == 500000000.0
    finally:
        session.close()


def test_upsert_risk_score():
    session = _fresh_session()
    try:
        svc = PersistenceService(session)
        svc.upsert_supplier(name="Test Corp", sector=SupplierSector.AEROSPACE)
        supplier = session.query(DefenceSupplier).filter_by(name="Test Corp").first()
        svc.upsert_risk_score(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
            score=50.0,
            rationale="Subsidiary of US company",
        )
        score = session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
        ).first()
        assert score is not None
        assert score.score == 50.0

        # Upsert should update, not duplicate
        svc.upsert_risk_score(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
            score=60.0,
            rationale="Updated",
        )
        scores = session.query(SupplierRiskScore).filter_by(
            supplier_id=supplier.id,
            dimension=RiskDimension.FOREIGN_OWNERSHIP,
        ).all()
        assert len(scores) == 1
        assert scores[0].score == 60.0
    finally:
        session.close()
