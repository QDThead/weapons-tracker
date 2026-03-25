"""tests/test_procurement_scraper.py"""
from __future__ import annotations

from src.ingestion.procurement_scraper import normalize_vendor_name, classify_sector
from src.storage.models import SupplierSector


def test_normalize_strips_inc():
    assert normalize_vendor_name("Irving Shipbuilding Inc.") == "Irving Shipbuilding"


def test_normalize_strips_ltd():
    assert normalize_vendor_name("CAE Ltd") == "CAE"


def test_normalize_strips_corporation():
    assert normalize_vendor_name("General Dynamics Corporation") == "General Dynamics"


def test_normalize_trims_whitespace():
    assert normalize_vendor_name("  Some Company  Inc  ") == "Some Company"


def test_classify_frigate():
    assert classify_sector("Halifax-class frigate modernization") == SupplierSector.SHIPBUILDING


def test_classify_lav():
    assert classify_sector("LAV 6.0 upgrade package") == SupplierSector.LAND_VEHICLES


def test_classify_aircraft():
    assert classify_sector("CF-18 fighter jet maintenance") == SupplierSector.AEROSPACE


def test_classify_simulation():
    assert classify_sector("Flight simulation training system") == SupplierSector.SIMULATION


def test_classify_unknown():
    assert classify_sector("Office supplies and furniture") == SupplierSector.OTHER
