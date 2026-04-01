"""Centralized source validation registry.

Maps hierarchical dot-notation keys to source metadata for every
dashboard UI element. Supports inheritance: if 'arctic.kpis.threat_level'
has no entry, resolution walks up to 'arctic.kpis' then 'arctic'.

Public API:
    resolve_sources(key) -> dict | None
    get_registry() -> dict[str, dict]
"""
from __future__ import annotations

# Source type constants
PRIMARY = "Primary"
CROSS_VALIDATION = "Cross-validation"
TRADE_VALIDATION = "Trade validation"
COMPANY_REPORTS = "Company reports"
MANUFACTURER = "Manufacturer datasheets"
DERIVED = "Derived estimate"
REFERENCE = "Reference"
PUBLIC = "Public domain"

_REGISTRY: dict[str, dict] = {
    "arctic": {
        "title": "Arctic Security Assessment — Source Validation",
        "sources": [
            {
                "name": "SIPRI Arms Transfers Database",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases/armstransfers",
                "date": "2025",
                "note": "Annual TIV data for Arctic-nation arms flows (Russia, Canada, Norway, Denmark, USA)",
            },
            {
                "name": "CIA World Factbook — Military",
                "type": PRIMARY,
                "url": "https://www.cia.gov/the-world-factbook/",
                "date": "2024",
                "note": "Force composition, conscription, budget share for all Arctic Council states",
            },
            {
                "name": "Arctic Council Reports",
                "type": REFERENCE,
                "date": "2024",
                "note": "Governance frameworks, shipping route status, environmental assessments",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI transfers + CIA Factbook + Arctic Council governance data",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
    "arctic.kpis.ice_extent": {
        "title": "Arctic Sea Ice Extent — Source Validation",
        "sources": [
            {
                "name": "NOAA/NSIDC Sea Ice Index v3",
                "type": PRIMARY,
                "url": "https://nsidc.org/data/seaice_index/",
                "date": "Monthly",
                "note": "Satellite-derived Arctic sea ice extent and concentration, updated monthly",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Single authoritative source — NSIDC is the global standard for sea ice measurement",
        "health_keys": ["noaa_ice"],
    },
    "arctic.bases": {
        "title": "Arctic Base Registry — Source Validation",
        "sources": [
            {
                "name": "SIPRI Military Bases Data Project",
                "type": PRIMARY,
                "url": "https://www.sipri.org/databases",
                "date": "2024",
                "note": "25 Arctic military installations with coordinates and capability data",
            },
            {
                "name": "CSIS Arctic Military Tracker",
                "type": CROSS_VALIDATION,
                "url": "https://www.csis.org/programs/americas-program",
                "date": "2024",
                "note": "Cross-validates base locations and operational status",
            },
            {
                "name": "National Ministry of Defence publications",
                "type": REFERENCE,
                "date": "2023-2024",
                "note": "Russia MoD, Canadian DND, US DoD annual reports on Arctic posture",
            },
        ],
        "confidence": "HIGH",
        "confidence_note": "Triangulated across SIPRI + CSIS + national MoD data for 25 installations",
        "health_keys": ["sipri_transfers", "cia_factbook"],
    },
}


def resolve_sources(key: str) -> dict | None:
    """Resolve a dot-notation key, walking up the hierarchy.

    If the exact key exists in the registry, return it directly.
    Otherwise, strip the rightmost segment and try the parent key,
    continuing until a match is found or the key is exhausted.

    Returns None if no match is found at any level.
    """
    if key in _REGISTRY:
        return _REGISTRY[key]
    parts = key.split(".")
    while len(parts) > 1:
        parts.pop()
        parent_key = ".".join(parts)
        if parent_key in _REGISTRY:
            return _REGISTRY[parent_key]
    return None


def get_registry() -> dict[str, dict]:
    """Return the full registry dict (read-only reference)."""
    return _REGISTRY
