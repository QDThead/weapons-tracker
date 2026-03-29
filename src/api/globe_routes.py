"""Globe API endpoints for CesiumJS 3D supply chain visualization.

Serves mineral supply chain data with geo-coordinates for rendering
on the 3D globe. All data sourced from USGS MCS 2025.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.analysis.mineral_supply_chains import get_all_minerals, get_mineral_by_name

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/globe", tags=["Globe"])


@router.get("/minerals")
async def list_minerals():
    """Return all 30 mineral supply chains with geo-coordinates."""
    return get_all_minerals()


@router.get("/minerals/{name}")
async def get_mineral(name: str):
    """Return a single mineral supply chain by name."""
    result = get_mineral_by_name(name)
    if result is None:
        raise HTTPException(status_code=404, detail="Mineral not found")
    return result
