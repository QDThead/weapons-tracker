"""Arctic security assessment API endpoints.

Provides Arctic-focused intelligence for Canadian government:
  - Force balance across Arctic nations
  - NATO vs Russia capability comparison
  - Northern Sea Route naval threat assessment
  - Weapon accumulation timelines
  - Russia weakness signals (import dependency)
  - Live Arctic military flights
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Query
from sqlalchemy import text

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arctic", tags=["Arctic"])

# 5-minute cache
_arctic_cache: dict[str, tuple[float, dict]] = {}
_ARCTIC_TTL = 300

ARCTIC_NATO_NATIONS = [
    "Norway", "Finland", "Sweden", "Denmark", "Estonia", "Latvia",
    "Lithuania", "Iceland", "Poland", "Canada", "United States",
]

ARCTIC_ALL_NATIONS = [
    "Russia", "Canada", "United States", "Norway", "Finland",
    "Sweden", "Denmark", "Iceland",
]

# For Northern Sea Route analysis, also include Japan and China
NSR_NATIONS = ["Russia", "China", "Norway", "United States", "Canada", "Japan"]

# Naval weapon categories (from weapon_description patterns)
NAVAL_KEYWORDS = [
    "ship", "submarine", "frigate", "corvette", "patrol",
    "torpedo", "naval", "destroyer", "cruiser", "carrier",
]


def _query(session, sql, params=None):
    return session.execute(text(sql), params or {}).fetchall()


def _make_placeholders(prefix, items):
    """Create named parameter placeholders and a param dict."""
    placeholders = ", ".join(f":{prefix}{i}" for i in range(len(items)))
    params = {f"{prefix}{i}": c for i, c in enumerate(items)}
    return placeholders, params


@router.get("/assessment")
async def get_arctic_assessment():
    """Full Arctic security assessment computed from DB.

    Returns force_balance, nato_vs_russia, northern_sea_route_threats,
    weapon_accumulation_timeline, and russia_weakness_signals.
    Cached for 5 minutes.
    """
    cache_key = "arctic_assessment"
    cached = _arctic_cache.get(cache_key)
    if cached and time.time() - cached[0] < _ARCTIC_TTL:
        return cached[1]

    session = SessionLocal()
    try:
        result = {
            "force_balance": _compute_force_balance(session),
            "nato_vs_russia": _compute_nato_vs_russia(session),
            "northern_sea_route_threats": _compute_nsr_threats(session),
            "weapon_accumulation_timeline": _compute_timeline(session),
            "russia_weakness_signals": _compute_russia_weakness(session),
        }
        _arctic_cache[cache_key] = (time.time(), result)
        return result
    finally:
        session.close()


@router.get("/flights")
async def get_arctic_flights():
    """Live Arctic military flights (lat > 55).

    Fetches from adsb.lol, filters for Arctic, classifies by nation.
    Cached for 5 minutes.
    """
    cache_key = "arctic_flights"
    cached = _arctic_cache.get(cache_key)
    if cached and time.time() - cached[0] < _ARCTIC_TTL:
        return cached[1]

    try:
        from src.ingestion.flight_tracker import FlightTrackerClient

        tracker = FlightTrackerClient()
        flights = await tracker.fetch_military_aircraft()

        arctic_flights = [f for f in flights if f.latitude > 55]

        # Classify flights
        russian_prefixes = ("RF", "RA", "RU", "RSD", "RFF")
        chinese_prefixes = ("CA", "CCA", "BAW", "CHN", "PLA")
        nato_prefixes = (
            "CANF", "RCAF", "CFC",  # Canada
            "RCH", "GOLD", "JAKE", "REACH", "DOOM", "HAWK",  # US
            "RRR", "ASCOT",  # UK
            "NORW", "NOW",  # Norway
            "FIN", "FAF",  # Finland
            "SVF",  # Sweden
            "DAF",  # Denmark
            "POL", "PLF",  # Poland
            "GAF",  # Germany
            "FAF", "CTM",  # France
        )

        classified = []
        counts = {"russian": 0, "chinese": 0, "nato": 0, "unknown": 0}

        for f in arctic_flights:
            cs = (f.callsign or "").upper().strip()
            origin = (f.country_of_origin or "").lower()

            if any(cs.startswith(p) for p in russian_prefixes) or "russia" in origin:
                nation = "russian"
            elif any(cs.startswith(p) for p in chinese_prefixes) or "china" in origin:
                nation = "chinese"
            elif any(cs.startswith(p) for p in nato_prefixes) or origin in (
                "canada", "united states", "norway", "finland",
                "sweden", "denmark", "poland", "united kingdom",
                "germany", "france", "iceland",
            ):
                nation = "nato"
            else:
                nation = "unknown"

            counts[nation] += 1
            classified.append({
                "callsign": f.callsign,
                "aircraft_type": f.aircraft_type,
                "aircraft_description": f.aircraft_description,
                "latitude": f.latitude,
                "longitude": f.longitude,
                "altitude_ft": f.altitude_ft,
                "heading": f.heading,
                "ground_speed_knots": f.ground_speed_knots,
                "nation": nation,
                "country_of_origin": f.country_of_origin,
            })

        result = {
            "total_arctic": len(arctic_flights),
            "counts": counts,
            "flights": classified,
            "timestamp": time.time(),
        }
        _arctic_cache[cache_key] = (time.time(), result)
        return result
    except Exception as e:
        logger.error("Arctic flights fetch failed: %s", e)
        return {
            "total_arctic": 0,
            "counts": {"russian": 0, "chinese": 0, "nato": 0, "unknown": 0},
            "flights": [],
            "timestamp": time.time(),
            "error": str(e),
        }


def _compute_force_balance(session) -> list[dict]:
    """For each Arctic nation, compute arms import profile."""
    nations = ARCTIC_ALL_NATIONS
    ph, params = _make_placeholders("n", nations)

    # Total imports by nation (2015-2025)
    rows = _query(session, f"""
        SELECT c.name,
               SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv,
               COUNT(*) as deal_count
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY c.name
        ORDER BY total_tiv DESC
    """, params)
    import_totals = {r[0]: {"total_tiv": r[1], "deals": r[2]} for r in rows}

    # Weapon category breakdown by nation
    rows = _query(session, f"""
        SELECT c.name, at.weapon_description,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY c.name, at.weapon_description
    """, params)
    weapon_breakdown = {}
    for r in rows:
        country = r[0]
        if country not in weapon_breakdown:
            weapon_breakdown[country] = {}
        desc = r[1] or "Unknown"
        weapon_breakdown[country][desc] = {"tiv": r[2], "deals": r[3]}

    # Top suppliers per nation
    rows = _query(session, f"""
        SELECT buyer.name as buyer, seller.name as seller,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries buyer ON at.buyer_id = buyer.id
        JOIN countries seller ON at.seller_id = seller.id
        WHERE buyer.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY buyer.name, seller.name
        ORDER BY buyer.name, tiv DESC
    """, params)
    suppliers = {}
    for r in rows:
        buyer = r[0]
        if buyer not in suppliers:
            suppliers[buyer] = []
        suppliers[buyer].append({"seller": r[1], "tiv": r[2]})

    # Trend: compare 2015-2019 vs 2020-2025
    rows = _query(session, f"""
        SELECT c.name,
               SUM(CASE WHEN at.order_year BETWEEN 2015 AND 2019
                   THEN COALESCE(at.tiv_delivered, 0) ELSE 0 END) as early_tiv,
               SUM(CASE WHEN at.order_year BETWEEN 2020 AND 2025
                   THEN COALESCE(at.tiv_delivered, 0) ELSE 0 END) as late_tiv
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
        GROUP BY c.name
    """, params)
    trends = {}
    for r in rows:
        early = r[1] or 0
        late = r[2] or 0
        if early > 0:
            change_pct = round((late - early) / early * 100, 1)
        elif late > 0:
            change_pct = 999
        else:
            change_pct = 0
        trends[r[0]] = {
            "early_tiv": early,
            "late_tiv": late,
            "change_pct": change_pct,
            "direction": "growing" if late > early else "shrinking" if late < early else "stable",
        }

    result = []
    for nation in nations:
        totals = import_totals.get(nation, {"total_tiv": 0, "deals": 0})
        wb = weapon_breakdown.get(nation, {})
        # Sort weapon categories by TIV
        sorted_weapons = sorted(wb.items(), key=lambda x: x[1]["tiv"], reverse=True)
        top_suppliers = suppliers.get(nation, [])[:5]
        trend = trends.get(nation, {"early_tiv": 0, "late_tiv": 0, "change_pct": 0, "direction": "stable"})

        is_nato = nation in ARCTIC_NATO_NATIONS
        result.append({
            "nation": nation,
            "alliance": "nato" if is_nato else "non-nato",
            "total_imports_tiv": totals["total_tiv"],
            "deal_count": totals["deals"],
            "weapon_categories": [
                {"type": w[0], "tiv": w[1]["tiv"], "deals": w[1]["deals"]}
                for w in sorted_weapons[:8]
            ],
            "top_suppliers": top_suppliers,
            "trend": trend,
        })

    return result


def _compute_nato_vs_russia(session) -> dict:
    """NATO Arctic nations' imports vs Russia's export capability."""
    # NATO Arctic imports
    ph, params = _make_placeholders("n", ARCTIC_NATO_NATIONS)
    rows = _query(session, f"""
        SELECT SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
    """, params)
    nato_imports = {"tiv": rows[0][0] or 0, "deals": rows[0][1]} if rows else {"tiv": 0, "deals": 0}

    # NATO Arctic by weapon category
    rows = _query(session, f"""
        SELECT at.weapon_description,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY at.weapon_description
        ORDER BY tiv DESC
    """, params)
    nato_categories = [
        {"type": r[0] or "Unknown", "tiv": r[1], "deals": r[2]}
        for r in rows[:10]
    ]

    # Russia's exports as proxy for capability
    rows = _query(session, """
        SELECT SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.seller_id = c.id
        WHERE c.name = 'Russia'
          AND at.order_year >= 2015 AND at.order_year <= 2025
    """)
    russia_exports = {"tiv": rows[0][0] or 0, "deals": rows[0][1]} if rows else {"tiv": 0, "deals": 0}

    # Russia exports by weapon category
    rows = _query(session, """
        SELECT at.weapon_description,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.seller_id = c.id
        WHERE c.name = 'Russia'
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY at.weapon_description
        ORDER BY tiv DESC
    """)
    russia_categories = [
        {"type": r[0] or "Unknown", "tiv": r[1], "deals": r[2]}
        for r in rows[:10]
    ]

    return {
        "nato_arctic_imports": nato_imports,
        "nato_arctic_categories": nato_categories,
        "russia_exports": russia_exports,
        "russia_categories": russia_categories,
        "balance_ratio": round(nato_imports["tiv"] / russia_exports["tiv"], 2) if russia_exports["tiv"] > 0 else None,
    }


def _compute_nsr_threats(session) -> dict:
    """Countries with naval assets near the Northern Sea Route."""
    ph, params = _make_placeholders("n", NSR_NATIONS)

    # Build naval keyword filter
    naval_conditions = " OR ".join(
        f"LOWER(at.weapon_description) LIKE :nk{i}"
        for i in range(len(NAVAL_KEYWORDS))
    )
    for i, kw in enumerate(NAVAL_KEYWORDS):
        params[f"nk{i}"] = f"%{kw}%"

    rows = _query(session, f"""
        SELECT buyer.name,
               at.weapon_description,
               seller.name as supplier,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries buyer ON at.buyer_id = buyer.id
        JOIN countries seller ON at.seller_id = seller.id
        WHERE buyer.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
          AND ({naval_conditions})
        GROUP BY buyer.name, at.weapon_description, seller.name
        ORDER BY buyer.name, tiv DESC
    """, params)

    by_country: dict[str, dict] = {}
    for r in rows:
        country = r[0]
        if country not in by_country:
            by_country[country] = {"total_naval_tiv": 0, "deals": 0, "assets": [], "suppliers": {}}
        by_country[country]["total_naval_tiv"] += r[3]
        by_country[country]["deals"] += r[4]
        by_country[country]["assets"].append({
            "type": r[1],
            "supplier": r[2],
            "tiv": r[3],
            "deals": r[4],
        })
        supplier = r[2]
        if supplier not in by_country[country]["suppliers"]:
            by_country[country]["suppliers"][supplier] = 0
        by_country[country]["suppliers"][supplier] += r[3]

    # Also get Russia's naval exports (what they sell = proxy for what fleet they have)
    rows = _query(session, """
        SELECT at.weapon_description,
               buyer.name as buyer,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries seller ON at.seller_id = seller.id
        JOIN countries buyer ON at.buyer_id = buyer.id
        WHERE seller.name = 'Russia'
          AND at.order_year >= 2015 AND at.order_year <= 2025
          AND (""" + " OR ".join(
              f"LOWER(at.weapon_description) LIKE :rnk{i}"
              for i in range(len(NAVAL_KEYWORDS))
          ) + """)
        GROUP BY at.weapon_description, buyer.name
        ORDER BY tiv DESC
    """, {f"rnk{i}": f"%{kw}%" for i, kw in enumerate(NAVAL_KEYWORDS)})

    russia_naval_exports = [
        {"type": r[0], "buyer": r[1], "tiv": r[2], "deals": r[3]}
        for r in rows
    ]

    return {
        "countries": by_country,
        "russia_naval_exports": russia_naval_exports,
        "chokepoints": [
            {"name": "Bering Strait", "lat": 65.8, "lon": -168.8},
            {"name": "Barents Sea", "lat": 73.0, "lon": 35.0},
            {"name": "Kara Sea", "lat": 76.0, "lon": 70.0},
            {"name": "Norwegian Sea", "lat": 67.0, "lon": 2.0},
        ],
    }


def _compute_timeline(session) -> list[dict]:
    """Year-by-year weapon imports for Arctic nations."""
    ph, params = _make_placeholders("n", ARCTIC_ALL_NATIONS)

    rows = _query(session, f"""
        SELECT c.name, at.order_year,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ({ph})
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY c.name, at.order_year
        ORDER BY at.order_year, c.name
    """, params)

    timeline: dict[int, dict[str, dict]] = {}
    for r in rows:
        year = r[1]
        country = r[0]
        if year not in timeline:
            timeline[year] = {}
        timeline[year][country] = {"tiv": r[2], "deals": r[3]}

    return [
        {
            "year": year,
            "countries": data,
        }
        for year, data in sorted(timeline.items())
    ]


def _compute_russia_weakness(session) -> dict:
    """What Russia is importing -- signs of domestic production issues."""
    rows = _query(session, """
        SELECT seller.name as seller,
               at.weapon_description,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv,
               COUNT(*) as deals,
               MIN(at.order_year) as earliest,
               MAX(at.order_year) as latest
        FROM arms_transfers at
        JOIN countries buyer ON at.buyer_id = buyer.id
        JOIN countries seller ON at.seller_id = seller.id
        WHERE buyer.name = 'Russia'
          AND at.order_year >= 2015 AND at.order_year <= 2025
        GROUP BY seller.name, at.weapon_description
        ORDER BY tiv DESC
    """)

    imports = []
    by_supplier: dict[str, float] = {}
    total_tiv = 0.0

    for r in rows:
        supplier = r[0]
        tiv = r[2]
        imports.append({
            "supplier": supplier,
            "weapon_type": r[1],
            "tiv": tiv,
            "deals": r[3],
            "year_range": f"{r[4]}-{r[5]}",
        })
        if supplier not in by_supplier:
            by_supplier[supplier] = 0
        by_supplier[supplier] += tiv
        total_tiv += tiv

    # Highlight Iran and China specifically
    iran_tiv = by_supplier.get("Iran", 0)
    china_tiv = by_supplier.get("China", 0)

    # Get recent imports (2020+) vs earlier
    rows_recent = _query(session, """
        SELECT seller.name,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries buyer ON at.buyer_id = buyer.id
        JOIN countries seller ON at.seller_id = seller.id
        WHERE buyer.name = 'Russia'
          AND at.order_year >= 2020
        GROUP BY seller.name
        ORDER BY tiv DESC
    """)
    recent_imports = [{"supplier": r[0], "tiv": r[1]} for r in rows_recent]

    return {
        "total_imports_tiv": total_tiv,
        "imports_by_type": imports[:20],
        "by_supplier": dict(sorted(by_supplier.items(), key=lambda x: x[1], reverse=True)),
        "iran_tiv": iran_tiv,
        "china_tiv": china_tiv,
        "recent_imports_2020_plus": recent_imports,
        "analysis": {
            "iran_dependency": f"Russia importing TIV {iran_tiv:.0f}M from Iran" if iran_tiv > 0 else "No Iranian imports detected",
            "china_dependency": f"Russia importing TIV {china_tiv:.0f}M from China" if china_tiv > 0 else "No Chinese imports detected",
            "signal": "Domestic production stress" if (iran_tiv + china_tiv) > 100 else "Limited import dependency",
        },
    }
