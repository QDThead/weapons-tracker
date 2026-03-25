"""tests/test_models_supplier.py"""
from __future__ import annotations

from src.storage.models import (
    SupplierSector, OwnershipType, ContractStatus,
    RiskDimension, DefenceSupplier, SupplierContract, SupplierRiskScore,
)


def test_enums_exist():
    assert SupplierSector.SHIPBUILDING == "shipbuilding"
    assert OwnershipType.FOREIGN_SUBSIDIARY == "foreign_subsidiary"
    assert ContractStatus.ACTIVE == "active"
    assert RiskDimension.FOREIGN_OWNERSHIP == "foreign_ownership"


def test_supplier_model_has_columns():
    cols = {c.name for c in DefenceSupplier.__table__.columns}
    assert "name" in cols
    assert "parent_company" in cols
    assert "risk_score_composite" in cols
    assert "sector" in cols


def test_contract_model_has_columns():
    cols = {c.name for c in SupplierContract.__table__.columns}
    assert "contract_number" in cols
    assert "supplier_id" in cols
    assert "is_sole_source" in cols


def test_risk_score_model_has_columns():
    cols = {c.name for c in SupplierRiskScore.__table__.columns}
    assert "dimension" in cols
    assert "score" in cols
    assert "rationale" in cols
