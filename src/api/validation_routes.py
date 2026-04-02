"""API endpoints for universal source validation.

GET /validation/sources  — full source registry (cached 1hr)
GET /validation/health   — live connector health (cached 60s)
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter

from src.analysis.source_registry import get_registry
from src.utils.cache import TTLCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation", tags=["Validation"])

_sources_cache = TTLCache(ttl_seconds=3600, max_size=5)
_health_cache = TTLCache(ttl_seconds=60, max_size=5)

_SOURCE_TYPES = [
    "Primary", "Cross-validation", "Trade validation",
    "Company reports", "Manufacturer datasheets",
    "Derived estimate", "Reference", "Public domain",
]


@router.get("/sources")
async def get_validation_sources():
    """Return the full source validation registry."""
    cached = _sources_cache.get("sources")
    if cached is not None:
        return cached
    registry = get_registry()
    result = {
        "registry": registry,
        "total_keys": len(registry),
        "source_types": _SOURCE_TYPES,
    }
    _sources_cache.set("sources", result)
    return result


@router.get("/health")
async def get_validation_health():
    """Return live health/freshness data for all data source connectors."""
    cached = _health_cache.get("health")
    if cached is not None:
        return cached
    health = _collect_health()
    _health_cache.set("health", health)
    return health


def _collect_health() -> dict:
    """Aggregate health data from all route module caches."""
    health: dict[str, dict] = {}
    connectors = _get_connector_specs()
    for spec in connectors:
        key = spec["key"]
        cache_obj = spec.get("cache_obj") or spec.get("cache_dict")
        cache_key = spec.get("cache_key", "")
        expected_ttl = spec.get("expected_ttl", 3600)
        entry = {
            "last_fetch": None,
            "records": 0,
            "cache_age_seconds": None,
            "cache_status": "UNKNOWN",
            "health": "UNKNOWN",
        }
        if cache_obj is not None and cache_key:
            age: float | None = None
            data = None

            if hasattr(cache_obj, "health"):
                # TTLCache path
                # Wildcard keys (e.g. "comtrade:*", "mirror:*", "news:*") — check if
                # any entry exists in the cache rather than a specific key.
                if cache_key.endswith(":*"):
                    oldest = cache_obj.oldest_entry()
                    if oldest is not None:
                        ts, data = oldest
                        age = time.time() - ts
                else:
                    info = cache_obj.health(cache_key)
                    if info["exists"]:
                        age = info["age_seconds"]
                        data = cache_obj.get(cache_key)
            elif isinstance(cache_obj, dict):
                # Legacy plain-dict fallback
                cached_entry = cache_obj.get(cache_key)
                if cached_entry and isinstance(cached_entry, tuple) and len(cached_entry) == 2:
                    ts, data = cached_entry
                    age = time.time() - ts

            if age is not None:
                # Reconstruct last_fetch from current time minus age
                last_fetch_ts = time.time() - age
                entry["last_fetch"] = datetime.fromtimestamp(last_fetch_ts, tz=timezone.utc).isoformat()
                entry["cache_age_seconds"] = int(age)
                if isinstance(data, list):
                    entry["records"] = len(data)
                elif isinstance(data, dict):
                    for count_key in ("total", "total_records", "count"):
                        if count_key in data:
                            entry["records"] = data[count_key]
                            break
                    else:
                        for v in data.values():
                            if isinstance(v, list):
                                entry["records"] = len(v)
                                break
                if age < expected_ttl:
                    entry["cache_status"] = "FRESH"
                elif age < expected_ttl * 2:
                    entry["cache_status"] = "STALE"
                else:
                    entry["cache_status"] = "EXPIRED"
                if age < expected_ttl * 2:
                    entry["health"] = "OK"
                else:
                    entry["health"] = "STALE"
        health[key] = entry
    return health


def _get_connector_specs() -> list[dict]:
    """Return connector specifications for health monitoring."""
    specs: list[dict] = []
    try:
        from src.api.enrichment_routes import _cache as enrich_cache
        enrichment_connectors = [
            ("worldbank_governance", "gov:CAN,USA,RUS,CHN,GBR,FRA,DEU", 3600),
            ("cia_factbook", "factbook", 3600),
            ("commodity_prices", "commodities", 3600),
            ("cisa_kev", "cisa_kev", 3600),
            ("gdacs_disasters", "gdacs_disasters", 3600),
            ("celestrak_satellites", "celestrak_sats", 3600),
            ("csis_missiles", "csis_missiles", 3600),
            ("un_sanctions", "un_sanctions", 3600),
            ("usgs_earthquakes", "usgs_earthquakes", 3600),
            ("mitre_attack", "mitre_attack", 3600),
            ("imf_weo", "imf_weo", 3600),
            ("nasa_eonet", "nasa_eonet", 3600),
            ("portwatch_chokepoints", "portwatch_chokepoints", 3600),
            ("unhcr_displacement", "unhcr_displacement", 3600),
            ("space_launches", "space_launches", 3600),
            ("submarine_cables", "submarine_cables", 3600),
            ("ripe_internet", "ripe_internet", 3600),
            ("dod_contracts", "dod_contracts", 3600),
            ("usgs_mineral_deposits", "usgs_mineral_deposits", 3600),
            ("wb_conflict_deaths", "wb_conflict_deaths", 3600),
            ("treasury_fiscal", "treasury_fiscal", 3600),
        ]
        for key, cache_key, ttl in enrichment_connectors:
            specs.append({"key": key, "cache_obj": enrich_cache, "cache_key": cache_key, "expected_ttl": ttl})
    except ImportError:
        pass
    try:
        from src.api.dashboard_routes import _buyer_mirror_cache, _comtrade_cache, _news_cache
        specs.append({"key": "comtrade_trade", "cache_obj": _comtrade_cache, "cache_key": "comtrade:*", "expected_ttl": 3600})
        specs.append({"key": "buyer_mirror", "cache_obj": _buyer_mirror_cache, "cache_key": "mirror:*", "expected_ttl": 3600})
        specs.append({"key": "gdelt_news", "cache_obj": _news_cache, "cache_key": "news:*", "expected_ttl": 900})
    except ImportError:
        pass
    try:
        from src.api.supplier_routes import _cache as supplier_cache
        specs.append({"key": "suppliers", "cache_obj": supplier_cache, "cache_key": "suppliers", "expected_ttl": 3600})
    except ImportError:
        pass
    return specs
