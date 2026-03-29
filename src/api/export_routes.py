"""Data export endpoints — CSV and Excel downloads.

Provides bulk export of arms transfers, defence suppliers, news articles,
and risk taxonomy scores in CSV and Excel formats.
"""
from __future__ import annotations

import csv
import io
import logging

from fastapi import APIRouter
from starlette.responses import StreamingResponse
import openpyxl

from src.storage.database import SessionLocal
from src.storage.models import (
    ArmsTransfer,
    ArmsTradeNews,
    Country,
    DefenceSupplier,
    RiskTaxonomyScore,
    WeaponSystem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/export", tags=["Export"])

# ── Transfer columns ────────────────────────────────────────────────────────
_TRANSFER_COLUMNS = [
    "seller",
    "buyer",
    "weapon_description",
    "weapon_designation",
    "order_year",
    "delivery_year_start",
    "number_ordered",
    "number_delivered",
    "status",
    "tiv_delivered",
    "source",
]


def _transfer_rows(session):
    """Query all arms transfers joined with seller/buyer names and weapon system."""
    from sqlalchemy.orm import aliased

    SellerCountry = aliased(Country, name="seller_country")
    BuyerCountry = aliased(Country, name="buyer_country")

    results = (
        session.query(
            SellerCountry.name.label("seller"),
            BuyerCountry.name.label("buyer"),
            ArmsTransfer.weapon_description,
            WeaponSystem.designation.label("weapon_designation"),
            ArmsTransfer.order_year,
            ArmsTransfer.delivery_year_start,
            ArmsTransfer.number_ordered,
            ArmsTransfer.number_delivered,
            ArmsTransfer.status,
            ArmsTransfer.tiv_delivered,
            ArmsTransfer.source,
        )
        .join(SellerCountry, ArmsTransfer.seller_id == SellerCountry.id)
        .join(BuyerCountry, ArmsTransfer.buyer_id == BuyerCountry.id)
        .outerjoin(WeaponSystem, ArmsTransfer.weapon_system_id == WeaponSystem.id)
        .all()
    )
    return results


# ── CSV / Excel helpers ─────────────────────────────────────────────────────

def _rows_to_csv(columns: list[str], rows) -> io.StringIO:
    """Convert a list of SQLAlchemy result rows into a CSV StringIO buffer."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([
            str(val.value) if hasattr(val, "value") else (val if val is not None else "")
            for val in row
        ])
    buf.seek(0)
    return buf


def _rows_to_excel(columns: list[str], rows, sheet_name: str = "Sheet1") -> io.BytesIO:
    """Convert a list of SQLAlchemy result rows into an Excel BytesIO buffer."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(columns)
    for row in rows:
        ws.append([
            str(val.value) if hasattr(val, "value") else (val if val is not None else "")
            for val in row
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ── Transfers ────────────────────────────────────────────────────────────────

@router.get("/transfers/csv")
async def export_transfers_csv():
    """Export all arms transfers as a CSV file."""
    session = SessionLocal()
    try:
        rows = _transfer_rows(session)
        buf = _rows_to_csv(_TRANSFER_COLUMNS, rows)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=arms_transfers.csv",
            },
        )
    except Exception as e:
        logger.error("Transfer CSV export failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.get("/transfers/excel")
async def export_transfers_excel():
    """Export all arms transfers as an Excel (.xlsx) file."""
    session = SessionLocal()
    try:
        rows = _transfer_rows(session)
        buf = _rows_to_excel(_TRANSFER_COLUMNS, rows, sheet_name="Arms Transfers")
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": "attachment; filename=arms_transfers.xlsx",
            },
        )
    except Exception as e:
        logger.error("Transfer Excel export failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


# ── Suppliers ────────────────────────────────────────────────────────────────

_SUPPLIER_COLUMNS = [
    "name",
    "sector",
    "ownership_type",
    "headquarters_country",
    "employee_count",
    "is_active",
]


@router.get("/suppliers/csv")
async def export_suppliers_csv():
    """Export all defence suppliers as a CSV file."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                DefenceSupplier.name,
                DefenceSupplier.sector,
                DefenceSupplier.ownership_type,
                DefenceSupplier.parent_country.label("headquarters_country"),
                DefenceSupplier.employee_count,
            )
            .all()
        )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(_SUPPLIER_COLUMNS)
        for row in results:
            name, sector, ownership_type, hq_country, emp_count = row
            writer.writerow([
                name or "",
                str(sector.value) if sector and hasattr(sector, "value") else (sector or ""),
                str(ownership_type.value) if ownership_type and hasattr(ownership_type, "value") else (ownership_type or ""),
                hq_country or "",
                emp_count if emp_count is not None else "",
                "true",  # is_active — model has no is_active field; default to true
            ])
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=defence_suppliers.csv",
            },
        )
    except Exception as e:
        logger.error("Supplier CSV export failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


# ── News ─────────────────────────────────────────────────────────────────────

_NEWS_COLUMNS = [
    "title",
    "url",
    "source_name",
    "published_at",
    "tone_score",
]


@router.get("/news/csv")
async def export_news_csv():
    """Export all arms-trade news articles as a CSV file."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                ArmsTradeNews.title,
                ArmsTradeNews.url,
                ArmsTradeNews.source_name,
                ArmsTradeNews.published_at,
                ArmsTradeNews.tone_score,
            )
            .all()
        )
        buf = _rows_to_csv(_NEWS_COLUMNS, results)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=arms_trade_news.csv",
            },
        )
    except Exception as e:
        logger.error("News CSV export failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


# ── Risk Taxonomy ────────────────────────────────────────────────────────────

_TAXONOMY_COLUMNS = [
    "subcategory_key",
    "category_id",
    "category_name",
    "subcategory_name",
    "score",
    "data_source",
    "scored_at",
]


@router.get("/taxonomy/csv")
async def export_taxonomy_csv():
    """Export all DND risk taxonomy scores as a CSV file."""
    session = SessionLocal()
    try:
        results = (
            session.query(
                RiskTaxonomyScore.subcategory_key,
                RiskTaxonomyScore.category_id,
                RiskTaxonomyScore.category_name,
                RiskTaxonomyScore.subcategory_name,
                RiskTaxonomyScore.score,
                RiskTaxonomyScore.data_source,
                RiskTaxonomyScore.scored_at,
            )
            .all()
        )
        buf = _rows_to_csv(_TAXONOMY_COLUMNS, results)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=risk_taxonomy_scores.csv",
            },
        )
    except Exception as e:
        logger.error("Taxonomy CSV export failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()
