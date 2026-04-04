"""Globe API endpoints for CesiumJS 3D supply chain visualization.

Serves mineral supply chain data with geo-coordinates for rendering
on the 3D globe. All data sourced from USGS MCS 2025.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

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
    mineral = get_mineral_by_name(name)
    if not mineral:
        raise HTTPException(status_code=404, detail=f"Mineral '{name}' not found")

    # Enrich cobalt with live triangulation confidence
    if name.lower() == "cobalt":
        try:
            from src.analysis.confidence import compute_cobalt_hhi
            from src.ingestion.bgs_minerals import BGSCobaltClient

            bgs = BGSCobaltClient()
            bgs_data = await bgs.fetch_cobalt_production()

            # Use most recent year's data for HHI
            if bgs_data:
                latest_year = max(d["year"] for d in bgs_data)
                latest = [d for d in bgs_data if d["year"] == latest_year]
            else:
                latest = []

            country_production = {}
            for entry in latest:
                country_production[entry["country"]] = entry["production_tonnes"]

            is_fallback = any("fallback" in d.get("source", "") for d in bgs_data[:1])
            mineral["hhi_live"] = compute_cobalt_hhi(country_production)
            mineral["hhi_source"] = "BGS World Mineral Statistics" + (" (fallback)" if is_fallback else " (live API)")
            mineral["hhi_year"] = latest_year if bgs_data else None
            mineral["confidence_triangulation"] = "active"
        except Exception as e:
            logger.warning("Cobalt HHI enrichment failed: %s", e)

        # Enrich mines/refineries with satellite thermal verification
        try:
            from src.ingestion.firms_thermal import FIRMSThermalClient
            firms = FIRMSThermalClient()
            thermal_data = await firms.fetch_all_facilities()
            unknown_thermal = {"status": "UNKNOWN", "detection_count": 0, "source": "NASA FIRMS (unavailable)", "detections": []}
            for mine in mineral.get("mines", []):
                mine["thermal"] = thermal_data.get(mine["name"], unknown_thermal)
            for ref in mineral.get("refineries", []):
                ref["thermal"] = thermal_data.get(ref["name"], unknown_thermal)
        except Exception as e:
            logger.warning("FIRMS thermal enrichment failed: %s", e)

        # Enrich mines/refineries with Sentinel-5P NO2 emissions data
        try:
            from src.ingestion.sentinel_no2 import SentinelNO2Client, compute_combined_verdict
            sentinel = SentinelNO2Client()
            no2_data = await sentinel.fetch_all_facilities()
            unknown_no2 = {"status": "UNKNOWN", "ratio": 0, "source": "Sentinel-5P (unavailable)", "history": []}
            for mine in mineral.get("mines", []):
                mine["no2"] = no2_data.get(mine["name"], unknown_no2)
                t_status = mine.get("thermal", {}).get("status", "UNKNOWN")
                n_status = mine["no2"].get("status", "UNKNOWN")
                mine["operational_verdict"] = compute_combined_verdict(t_status, n_status)
            for ref in mineral.get("refineries", []):
                ref["no2"] = no2_data.get(ref["name"], unknown_no2)
                t_status = ref.get("thermal", {}).get("status", "UNKNOWN")
                n_status = ref["no2"].get("status", "UNKNOWN")
                ref["operational_verdict"] = compute_combined_verdict(t_status, n_status)
        except Exception as e:
            logger.warning("Sentinel NO2 enrichment failed: %s", e)

    return mineral


@router.get("/facility/thumbnail")
async def get_facility_thumbnail(lat: float, lon: float):
    """Return a Sentinel-2 true-color satellite thumbnail for a facility location."""
    try:
        from src.ingestion.sentinel_no2 import SentinelNO2Client
        client = SentinelNO2Client()
        png_bytes = await client.fetch_facility_thumbnail(lat, lon)
        if png_bytes:
            return Response(content=png_bytes, media_type="image/png")
        raise HTTPException(status_code=503, detail="Satellite imagery unavailable")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Thumbnail fetch failed: %s", e)
        raise HTTPException(status_code=503, detail="Satellite imagery unavailable")


@router.get("/minerals/{name}/forecast")
async def get_mineral_forecast(name: str):
    """Return computed forecast for a mineral (live data + regression)."""
    if name.lower() != "cobalt":
        raise HTTPException(status_code=404, detail="Forecasting only available for Cobalt currently")
    from src.analysis.cobalt_forecasting import compute_cobalt_forecast
    return await compute_cobalt_forecast()
