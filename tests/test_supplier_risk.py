"""tests/test_supplier_risk.py"""
from __future__ import annotations

from datetime import date, datetime

from src.storage.database import init_db, SessionLocal
from src.storage.models import (
    DefenceSupplier, SupplierContract, SupplierRiskScore,
    SupplierSector, OwnershipType, ContractStatus, RiskDimension,
)
from src.storage.persistence import PersistenceService
from src.analysis.supplier_risk import SupplierRiskScorer


def _setup():
    init_db()
    session = SessionLocal()
    svc = PersistenceService(session)
    return session, svc


def test_foreign_ownership_canadian():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="Irving", sector=SupplierSector.SHIPBUILDING,
            ownership_type=OwnershipType.CANADIAN_PRIVATE,
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_foreign_ownership(supplier)
        assert score == 0
    finally:
        session.close()


def test_foreign_ownership_allied_subsidiary():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="GD Canada", sector=SupplierSector.LAND_VEHICLES,
            ownership_type=OwnershipType.FOREIGN_SUBSIDIARY,
            parent_country="United States",
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_foreign_ownership(supplier)
        assert score == 50
        assert "United States" in rationale
    finally:
        session.close()


def test_single_source_sole_supplier():
    session, svc = _setup()
    try:
        svc.upsert_supplier(name="Irving Solo", sector=SupplierSector.SHIPBUILDING)
        supplier = session.query(DefenceSupplier).filter_by(name="Irving Solo").first()
        svc.upsert_contract(
            supplier_id=supplier.id, contract_number="SOLE-001",
            contract_value_cad=1e9, sector=SupplierSector.SHIPBUILDING,
            status=ContractStatus.ACTIVE, award_date=date(2024, 1, 1),
        )
        scorer = SupplierRiskScorer(session)
        score, rationale = scorer.score_single_source(supplier)
        assert score == 90
        assert "shipbuilding" in rationale.lower()
    finally:
        session.close()


def test_composite_score():
    session, svc = _setup()
    try:
        supplier = svc.upsert_supplier(
            name="Test Composite", sector=SupplierSector.AEROSPACE,
            ownership_type=OwnershipType.CANADIAN_PUBLIC,
        )
        svc.upsert_contract(
            supplier_id=supplier.id, contract_number="COMP-001",
            contract_value_cad=5e8, sector=SupplierSector.AEROSPACE,
            status=ContractStatus.ACTIVE, award_date=date(2024, 1, 1),
        )
        scorer = SupplierRiskScorer(session)
        composite = scorer.score_supplier(supplier)
        assert 0 <= composite <= 100
        scores = session.query(SupplierRiskScore).filter_by(supplier_id=supplier.id).all()
        assert len(scores) == 6
    finally:
        session.close()
