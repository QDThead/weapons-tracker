"""UN Register of Conventional Arms (UNROCA) connector.

Fetches unit-level arms transfer data — how many battle tanks, combat aircraft,
armoured vehicles, artillery systems, missiles, warships, and small arms each
country imported or exported in a given reporting year.

API: https://www.unroca.org/api/
Coverage: 1992–present, ~195 reporting countries.
Auth: None required (public API).
Freshness: Annual (member states submit reports each year).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

UNROCA_API_BASE = "https://www.unroca.org/api"

# 24-hour TTL for the aggregate key-countries fetch
_CACHE_TTL = 86_400  # seconds
_cache: dict[str, tuple[float, dict | list]] = {}

# Heavy-weapon field codes → human-readable category names
HW_FIELD_MAP = {
    "ca": "Combat aircraft",
    "ca_gen": "Combat aircraft (generic)",
    "bt": "Battle tanks",
    "acv": "Armoured combat vehicles",
    "lcas": "Large-calibre artillery systems",
    "mml": "Multiple-launch rocket systems",
    "mml_gen": "Multiple-launch rocket systems (generic)",
    "ah": "Attack helicopters",
    "ah_gen": "Attack helicopters (generic)",
    "ws": "Warships",
    "auavf": "Armed/attack UAVs",
    "mnpd": "Man-portable air-defence systems (MANPADS)",
}

# Small-arms export field codes → human-readable names
SALW_EXP_FIELD_MAP = {
    "sa_rsp": "Revolvers and self-loading pistols",
    "sa_smg": "Sub-machine guns",
    "sa_ar": "Assault rifles",
    "sa_lmg": "Light machine guns",
    "sa_rc": "Rifles and carbines",
    "sa_o": "Other small arms",
    "lw1": "Heavy machine guns (LW)",
    "lw2": "Hand-held / under-barrel / mounted grenade launchers (LW)",
    "lw3": "Portable anti-tank guns (LW)",
    "lw4": "Recoilless rifles (LW)",
    "lw5": "Portable launchers of anti-tank missile / rocket systems (LW)",
    "lw6": "Portable launchers of anti-aircraft missile systems (LW)",
    "lw7": "Mortars <100 mm calibre (LW)",
}

# Time-series weapon-type verbose labels
SA_TIME_FIELDS = {
    "sa_ar": "Assault rifles",
    "sa_lmg": "Light machine guns",
    "sa_rc": "Rifles and carbines",
    "sa_rsp": "Revolvers and self-loading pistols",
    "sa_smg": "Sub-machine guns",
    "sa_o": "Other small arms",
}

LW_TIME_FIELDS = {
    "lw1": "Heavy machine guns",
    "lw2": "Grenade launchers",
    "lw3": "Portable anti-tank guns",
    "lw4": "Recoilless rifles",
    "lw5": "Portable anti-tank missile/rocket launchers",
    "lw6": "Portable anti-aircraft missile launchers",
    "lw7": "Mortars <100 mm",
}

# Key countries to fetch in the aggregate call — use verified UNROCA slugs.
# Retrieve the full list via GET /api/country-list/ to find any country's slug.
KEY_COUNTRY_SLUGS = [
    "russian-federation",
    "united-states",           # "United States" in UNROCA
    "china",
    "france",
    "germany",
    "united-kingdom",
    "israel",
    "india",
    "republic-of-korea",       # South Korea
    "turkey",                  # Türkiye
    "canada",
    "australia",
    "italy",
    "ukraine",
    "islamic-republic-of-iran",  # Iran
]


@dataclass
class UNROCAHWTransfer:
    """A single heavy-weapons transfer entry from the hw_imp matrix."""
    partner_country: str
    partner_slug: str
    partner_iso2: str
    category_code: str
    category_name: str
    quantity: int
    # _1 = own-country report; _2 = partner-country report
    report_type: str  # "own" | "partner"


@dataclass
class UNROCASALWEntry:
    """A small-arms / light-weapons export entry."""
    destination_country: str
    destination_slug: str
    destination_iso2: str
    category_code: str
    category_name: str
    quantity: int
    report_type: str  # "own" | "partner"


@dataclass
class UNROCATimeSeries:
    """Yearly totals for a single weapon type (own + other reports)."""
    weapon_type_code: str
    weapon_type_name: str
    own_values: list[dict]    # [{year, amount, contains_classified}]
    other_values: list[dict]  # [{year, amount, contains_classified}]


@dataclass
class UNROCACountryProfile:
    """Parsed country profile from the UNROCA API."""
    country_name: str
    country_slug: str
    country_iso2: str
    # Heavy weapons imports — each entry is a country that sent weapons here
    hw_imports: list[UNROCAHWTransfer] = field(default_factory=list)
    # SALW exports — each entry is a destination country
    salw_exports: list[UNROCASALWEntry] = field(default_factory=list)
    # Time series (small arms + light weapons imports over time)
    sa_time_series: list[UNROCATimeSeries] = field(default_factory=list)
    lw_time_series: list[UNROCATimeSeries] = field(default_factory=list)


def _parse_hw_imp(hw_imp: list[dict]) -> list[UNROCAHWTransfer]:
    """Extract non-null heavy-weapon import entries from hw_imp matrix row."""
    transfers: list[UNROCAHWTransfer] = []
    for row in hw_imp:
        partner = row.get("country", "")
        slug = row.get("countryname_slug", "")
        iso2 = row.get("acro", "")
        for code, name in HW_FIELD_MAP.items():
            val_own = row.get(f"{code}_1")
            val_partner = row.get(f"{code}_2")
            if val_own and isinstance(val_own, (int, float)) and val_own > 0:
                transfers.append(UNROCAHWTransfer(
                    partner_country=partner,
                    partner_slug=slug,
                    partner_iso2=iso2,
                    category_code=code,
                    category_name=name,
                    quantity=int(val_own),
                    report_type="own",
                ))
            if val_partner and isinstance(val_partner, (int, float)) and val_partner > 0:
                transfers.append(UNROCAHWTransfer(
                    partner_country=partner,
                    partner_slug=slug,
                    partner_iso2=iso2,
                    category_code=code,
                    category_name=name,
                    quantity=int(val_partner),
                    report_type="partner",
                ))
    return transfers


def _parse_salw_exp(salw_exp: list[dict]) -> list[UNROCASALWEntry]:
    """Extract non-null SALW export entries."""
    entries: list[UNROCASALWEntry] = []
    for row in salw_exp:
        dest = row.get("country", "")
        slug = row.get("countryname_slug", "")
        iso2 = row.get("acro", "")
        for code, name in SALW_EXP_FIELD_MAP.items():
            val_own = row.get(f"{code}_1")
            val_partner = row.get(f"{code}_2")
            if val_own and isinstance(val_own, (int, float)) and val_own > 0:
                entries.append(UNROCASALWEntry(
                    destination_country=dest,
                    destination_slug=slug,
                    destination_iso2=iso2,
                    category_code=code,
                    category_name=name,
                    quantity=int(val_own),
                    report_type="own",
                ))
            if val_partner and isinstance(val_partner, (int, float)) and val_partner > 0:
                entries.append(UNROCASALWEntry(
                    destination_country=dest,
                    destination_slug=slug,
                    destination_iso2=iso2,
                    category_code=code,
                    category_name=name,
                    quantity=int(val_partner),
                    report_type="partner",
                ))
    return entries


def _parse_time_series(rows: list[dict], field_map: dict[str, str]) -> list[UNROCATimeSeries]:
    """Parse a sa_imp_time or lw_imp_time array into UNROCATimeSeries objects."""
    series: list[UNROCATimeSeries] = []
    for row in rows:
        tow = row.get("tow", "")
        tow_verbose = row.get("tow_verbose", field_map.get(tow, tow))
        own_raw = row.get("own_values", [])
        other_raw = row.get("other_values", [])
        own = [
            {"year": e["year"], "amount": e.get("amount", 0), "classified": e.get("contains_classified", False)}
            for e in own_raw
            if isinstance(e, dict) and e.get("amount", 0)
        ]
        other = [
            {"year": e["year"], "amount": e.get("amount", 0), "classified": e.get("contains_classified", False)}
            for e in other_raw
            if isinstance(e, dict) and e.get("amount", 0)
        ]
        if own or other:
            series.append(UNROCATimeSeries(
                weapon_type_code=tow,
                weapon_type_name=tow_verbose,
                own_values=own,
                other_values=other,
            ))
    return series


class UNROCAClient:
    """Client for the UN Register of Conventional Arms public API.

    Endpoints:
      GET /api/country-list/        — list of all reporting countries
      GET /api/{slug}/              — full country profile with transfer data

    No authentication required.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_country_list(self) -> list[dict]:
        """Fetch the full list of UNROCA reporting countries.

        Returns:
            List of dicts: [{name, slug, iso2}]
        """
        cached = _cache.get("country_list")
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{UNROCA_API_BASE}/country-list/")
            resp.raise_for_status()
            raw = resp.json()

        result = [
            {
                "name": row.get("name_en", ""),
                "slug": row.get("countryname_slug", ""),
                "iso2": row.get("iso_2_acronym", ""),
            }
            for row in raw
        ]
        _cache["country_list"] = (time.time(), result)
        logger.info("UNROCA: fetched %d countries", len(result))
        return result

    async def fetch_country_transfers(self, slug: str) -> dict:
        """Fetch full country profile and parse into structured transfer data.

        Args:
            slug: UNROCA country slug (e.g. 'canada', 'russian-federation').

        Returns:
            Structured dict:
            {
              country: str,
              slug: str,
              iso2: str,
              hw_imports: [
                {partner, partner_iso2, category, quantity, report_type}
              ],
              salw_exports: [
                {destination, destination_iso2, category, quantity, report_type}
              ],
              sa_time_series: [
                {weapon_type, weapon_type_name, own_values:[{year,amount}], other_values:[...]}
              ],
              lw_time_series: [...],
              total_hw_import_units: int,
              total_salw_export_units: int,
            }
        """
        cache_key = f"country:{slug}"
        cached = _cache.get(cache_key)
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{UNROCA_API_BASE}/{slug}/")
            resp.raise_for_status()
            raw = resp.json()

        # Country metadata may be embedded or inferred from the slug
        country_meta = raw.get("country", {})
        country_name = country_meta.get("name_en", slug.replace("-", " ").title()) if isinstance(country_meta, dict) else slug.replace("-", " ").title()
        iso2 = country_meta.get("iso_2_acronym", "") if isinstance(country_meta, dict) else ""

        hw_imp_raw = raw.get("hw_imp", [])
        salw_exp_raw = raw.get("salw_exp", [])
        sa_time_raw = raw.get("sa_imp_time", [])
        lw_time_raw = raw.get("lw_imp_time", [])

        hw_imports = _parse_hw_imp(hw_imp_raw)
        salw_exports = _parse_salw_exp(salw_exp_raw)
        sa_series = _parse_time_series(sa_time_raw, SA_TIME_FIELDS)
        lw_series = _parse_time_series(lw_time_raw, LW_TIME_FIELDS)

        result = {
            "country": country_name,
            "slug": slug,
            "iso2": iso2,
            "hw_imports": [
                {
                    "partner": t.partner_country,
                    "partner_slug": t.partner_slug,
                    "partner_iso2": t.partner_iso2,
                    "category": t.category_name,
                    "category_code": t.category_code,
                    "quantity": t.quantity,
                    "report_type": t.report_type,
                }
                for t in hw_imports
            ],
            "salw_exports": [
                {
                    "destination": e.destination_country,
                    "destination_slug": e.destination_slug,
                    "destination_iso2": e.destination_iso2,
                    "category": e.category_name,
                    "category_code": e.category_code,
                    "quantity": e.quantity,
                    "report_type": e.report_type,
                }
                for e in salw_exports
            ],
            "sa_time_series": [
                {
                    "weapon_type": s.weapon_type_code,
                    "weapon_type_name": s.weapon_type_name,
                    "own_values": s.own_values,
                    "other_values": s.other_values,
                }
                for s in sa_series
            ],
            "lw_time_series": [
                {
                    "weapon_type": s.weapon_type_code,
                    "weapon_type_name": s.weapon_type_name,
                    "own_values": s.own_values,
                    "other_values": s.other_values,
                }
                for s in lw_series
            ],
            "total_hw_import_units": sum(t.quantity for t in hw_imports),
            "total_salw_export_units": sum(e.quantity for e in salw_exports),
        }

        _cache[cache_key] = (time.time(), result)
        logger.info(
            "UNROCA: %s — %d hw_import entries, %d salw_export entries",
            slug, len(hw_imports), len(salw_exports),
        )
        return result

    async def fetch_key_countries(self) -> dict:
        """Fetch and aggregate UNROCA data for 15 key countries.

        Uses a 24-hour cache. Fetches each country sequentially to avoid
        hammering the API.

        Returns:
            {
              source: str,
              note: str,
              countries: [
                {
                  name, slug, iso2,
                  total_hw_import_units, total_salw_export_units,
                  top_hw_import_sources: [{partner, total_units}],
                  top_salw_export_destinations: [{destination, total_units}],
                  hw_categories: {category: total_units},
                  salw_categories: {category: total_units},
                }
              ],
              total_countries_fetched: int,
              errors: [str],
            }
        """
        cached = _cache.get("key_countries")
        if cached and time.time() - cached[0] < _CACHE_TTL:
            return cached[1]  # type: ignore[return-value]

        countries_out = []
        errors = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for slug in KEY_COUNTRY_SLUGS:
                try:
                    resp = await client.get(f"{UNROCA_API_BASE}/{slug}/")
                    resp.raise_for_status()
                    raw = resp.json()

                    country_meta = raw.get("country", {})
                    country_name = (
                        country_meta.get("name_en", slug.replace("-", " ").title())
                        if isinstance(country_meta, dict)
                        else slug.replace("-", " ").title()
                    )
                    iso2 = country_meta.get("iso_2_acronym", "") if isinstance(country_meta, dict) else ""

                    hw_imports = _parse_hw_imp(raw.get("hw_imp", []))
                    salw_exports = _parse_salw_exp(raw.get("salw_exp", []))

                    # Top HW import sources — aggregate by partner country
                    hw_by_partner: dict[str, int] = {}
                    for t in hw_imports:
                        hw_by_partner[t.partner_country] = hw_by_partner.get(t.partner_country, 0) + t.quantity

                    top_hw_sources = sorted(
                        [{"partner": k, "total_units": v} for k, v in hw_by_partner.items()],
                        key=lambda x: x["total_units"],
                        reverse=True,
                    )[:10]

                    # Top SALW export destinations
                    salw_by_dest: dict[str, int] = {}
                    for e in salw_exports:
                        salw_by_dest[e.destination_country] = salw_by_dest.get(e.destination_country, 0) + e.quantity

                    top_salw_dests = sorted(
                        [{"destination": k, "total_units": v} for k, v in salw_by_dest.items()],
                        key=lambda x: x["total_units"],
                        reverse=True,
                    )[:10]

                    # Category breakdowns
                    hw_cats: dict[str, int] = {}
                    for t in hw_imports:
                        hw_cats[t.category_name] = hw_cats.get(t.category_name, 0) + t.quantity

                    salw_cats: dict[str, int] = {}
                    for e in salw_exports:
                        salw_cats[e.category_name] = salw_cats.get(e.category_name, 0) + e.quantity

                    countries_out.append({
                        "name": country_name,
                        "slug": slug,
                        "iso2": iso2,
                        "total_hw_import_units": sum(t.quantity for t in hw_imports),
                        "total_salw_export_units": sum(e.quantity for e in salw_exports),
                        "top_hw_import_sources": top_hw_sources,
                        "top_salw_export_destinations": top_salw_dests,
                        "hw_categories": hw_cats,
                        "salw_categories": salw_cats,
                    })

                except httpx.HTTPStatusError as exc:
                    msg = f"{slug}: HTTP {exc.response.status_code}"
                    logger.warning("UNROCA key-countries fetch failed — %s", msg)
                    errors.append(msg)
                except Exception as exc:  # noqa: BLE001
                    msg = f"{slug}: {exc}"
                    logger.warning("UNROCA key-countries fetch failed — %s", msg)
                    errors.append(msg)

        result = {
            "source": "UN Register of Conventional Arms (UNROCA)",
            "url": "https://www.unroca.org/",
            "note": (
                "Unit counts as reported by member states. _1 fields = reporting "
                "country's own submission; _2 fields = partner country's submission. "
                "Heavy weapons: combat aircraft, battle tanks, armoured vehicles, "
                "large-calibre artillery, MLRS, attack helicopters, warships, UAVs, MANPADS. "
                "SALW = small arms and light weapons exports."
            ),
            "countries": countries_out,
            "total_countries_fetched": len(countries_out),
            "errors": errors,
        }
        _cache["key_countries"] = (time.time(), result)
        logger.info(
            "UNROCA: fetched %d/%d key countries (%d errors)",
            len(countries_out), len(KEY_COUNTRY_SLUGS), len(errors),
        )
        return result
