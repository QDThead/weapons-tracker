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
    """Get single mineral supply chain with enriched cobalt data."""
    from src.analysis.mineral_supply_chains import get_mineral_by_name
    mineral = get_mineral_by_name(name)
    if not mineral:
        raise HTTPException(status_code=404, detail=f"Mineral '{name}' not found")

    # Enrich cobalt with triangulation confidence
    if name.lower() == "cobalt":
        try:
            from src.analysis.confidence import compute_cobalt_hhi
            from src.ingestion.bgs_minerals import BGSCobaltClient

            bgs = BGSCobaltClient()
            bgs_data = bgs._fallback_data()

            country_production = {}
            for entry in bgs_data:
                country_production[entry["country"]] = entry["production_tonnes"]

            mineral["hhi_live"] = compute_cobalt_hhi(country_production)
            mineral["hhi_source"] = "BGS World Mineral Statistics"
            mineral["confidence_triangulation"] = "active"
        except Exception:
            pass

    return mineral


@router.get("/minerals/{name}/forecast")
async def get_mineral_forecast(name: str):
    """Return computed forecast for a mineral (live data + regression)."""
    if name.lower() != "cobalt":
        raise HTTPException(status_code=404, detail="Forecasting only available for Cobalt currently")
    from src.analysis.cobalt_forecasting import compute_cobalt_forecast
    return await compute_cobalt_forecast()
