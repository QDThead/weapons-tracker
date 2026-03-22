"""Arctic security assessment API endpoints.

Provides Arctic-focused intelligence for Canadian government:
  - Force balance across Arctic nations
  - NATO vs Russia capability comparison
  - Northern Sea Route naval threat assessment
  - Weapon accumulation timelines
  - Russia weakness signals (import dependency)
  - Live Arctic military flights
  - Arctic base registry with threat scoring
"""

from __future__ import annotations

import logging
import math
import time

from fastapi import APIRouter, Query
from sqlalchemy import text

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arctic", tags=["Arctic"])

# 5-minute cache for assessment, 1-hour cache for bases
_arctic_cache: dict[str, tuple[float, dict | list]] = {}
_ARCTIC_TTL = 300
_BASES_TTL = 3600


# ---------------------------------------------------------------------------
# Arctic Bases Registry
# ---------------------------------------------------------------------------

# Ottawa coordinates for distance calculations
OTTAWA_LAT, OTTAWA_LON = 45.42, -75.70

ARCTIC_BASES = [
    # --- RUSSIA ---
    {
        "name": "Severomorsk",
        "country": "Russia",
        "lat": 69.07, "lon": 33.42,
        "type": "naval",
        "alliance": "russia",
        "status": "active",
        "capability": "Northern Fleet HQ, nuclear submarines (Borei/Yasen-class), surface combatants, anti-ship missiles",
        "personnel": 25000,
        "recent_developments": "Russia's primary Arctic naval base. Continuous submarine patrols under ice. New Yasen-M SSGNs deploying.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Olenya/Olenegorsk",
        "country": "Russia",
        "lat": 68.15, "lon": 33.85,
        "type": "air",
        "alliance": "russia",
        "status": "expanding",
        "capability": "Long-range bombers (Tu-22M3 Backfire, Tu-95 Bear), aerial refueling, nuclear strike capability",
        "personnel": 3000,
        "recent_developments": "Reinforced 2025 with additional Tu-22M3 bombers. Regular Arctic patrol flights along Canadian ADIZ.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Rogachevo, Novaya Zemlya",
        "country": "Russia",
        "lat": 71.62, "lon": 52.47,
        "type": "air",
        "alliance": "russia",
        "status": "active",
        "capability": "S-400 SAMs, radar, electronic warfare, 'Trefoil' autonomous base module",
        "personnel": 500,
        "recent_developments": "S-400 SAMs deployed 2019. Autonomous base design allows year-round operation with minimal personnel.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Nagurskoye, Franz Josef Land",
        "country": "Russia",
        "lat": 80.80, "lon": 47.65,
        "type": "air",
        "alliance": "russia",
        "status": "expanding",
        "capability": "MiG-31 interceptors, 'Arctic Shamrock' base, northernmost military installation on Earth",
        "personnel": 800,
        "recent_developments": "World's northernmost military base. MiG-31BM interceptors deployed. 2,500m runway operational.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Temp, Kotelny Island",
        "country": "Russia",
        "lat": 75.98, "lon": 137.86,
        "type": "ground",
        "alliance": "russia",
        "status": "active",
        "capability": "Bastion coastal defense missiles (P-800 Oniks), 'Northern Clover' base, radar coverage",
        "personnel": 400,
        "recent_developments": "'Northern Clover' base with Bastion-P coastal defense systems. Controls access to Northern Sea Route eastern sector.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Wrangel Island",
        "country": "Russia",
        "lat": 71.23, "lon": -179.77,
        "type": "research",
        "alliance": "russia",
        "status": "active",
        "capability": "Radar station, drone surveillance, signals intelligence",
        "personnel": 100,
        "recent_developments": "Upgraded radar and drone surveillance capability. Monitors Bering Strait and approaches to NSR.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Murmansk",
        "country": "Russia",
        "lat": 68.97, "lon": 33.08,
        "type": "naval",
        "alliance": "russia",
        "status": "expanding",
        "capability": "Icebreaker fleet (nuclear + conventional), upgraded docking, logistics hub",
        "personnel": 5000,
        "recent_developments": "Upgraded docking facilities. Home port for world's largest nuclear icebreaker fleet. New Arktika-class icebreakers deploying.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    {
        "name": "Gadzhiyevo",
        "country": "Russia",
        "lat": 69.25, "lon": 33.32,
        "type": "naval",
        "alliance": "russia",
        "status": "active",
        "capability": "Nuclear submarine base (Borei-A class SSBNs), Bulava SLBMs, second-strike nuclear deterrent",
        "personnel": 8000,
        "recent_developments": "Home base for Borei-A class SSBNs carrying Bulava ICBMs. Russia's primary sea-based nuclear deterrent.",
        "flag_emoji": "\U0001f1f7\U0001f1fa",
    },
    # --- USA ---
    {
        "name": "Pituffik Space Base, Greenland",
        "country": "United States",
        "lat": 76.53, "lon": -68.70,
        "type": "space",
        "alliance": "nato",
        "status": "expanding",
        "capability": "Missile warning radar, space surveillance, BMEWS. $25M upgrade program",
        "personnel": 150,
        "recent_developments": "$25M upgrade to missile warning and space surveillance systems. Critical for early warning of ICBM launches over the pole.",
        "flag_emoji": "\U0001f1fa\U0001f1f8",
    },
    {
        "name": "Eielson AFB, Alaska",
        "country": "United States",
        "lat": 64.66, "lon": -147.10,
        "type": "air",
        "alliance": "nato",
        "status": "active",
        "capability": "F-35A Lightning II squadrons, Arctic air superiority, RED FLAG-Alaska exercises",
        "personnel": 5500,
        "recent_developments": "Two F-35A squadrons now operational. Primary USAF Arctic air superiority base.",
        "flag_emoji": "\U0001f1fa\U0001f1f8",
    },
    {
        "name": "Clear SFS, Alaska",
        "country": "United States",
        "lat": 64.29, "lon": -149.19,
        "type": "space",
        "alliance": "nato",
        "status": "active",
        "capability": "LRDR missile warning radar, ICBM tracking, space domain awareness",
        "personnel": 200,
        "recent_developments": "Long Range Discrimination Radar (LRDR) operational. Tracks ICBMs and space objects over the Arctic.",
        "flag_emoji": "\U0001f1fa\U0001f1f8",
    },
    {
        "name": "Fort Greely, Alaska",
        "country": "United States",
        "lat": 63.96, "lon": -145.74,
        "type": "ground",
        "alliance": "nato",
        "status": "active",
        "capability": "Ground-Based Interceptors (GBI), missile defense, Next Generation Interceptor site",
        "personnel": 1500,
        "recent_developments": "40 Ground-Based Interceptors for ICBM defense. Next Generation Interceptor in development.",
        "flag_emoji": "\U0001f1fa\U0001f1f8",
    },
    # --- CANADA ---
    {
        "name": "CFB Yellowknife",
        "country": "Canada",
        "lat": 62.46, "lon": -114.44,
        "type": "ground",
        "alliance": "nato",
        "status": "planned",
        "capability": "Northern Operational Support Hub (announced 2025, $2.67B program), staging base",
        "personnel": 300,
        "recent_developments": "Announced 2025 as part of $2.67B Northern Operations program. Will serve as primary staging base for Arctic operations.",
        "flag_emoji": "\U0001f1e8\U0001f1e6",
    },
    {
        "name": "Inuvik",
        "country": "Canada",
        "lat": 68.36, "lon": -133.72,
        "type": "air",
        "alliance": "nato",
        "status": "expanding",
        "capability": "NORAD Forward Operating Location, radar, upgrading to full operational base",
        "personnel": 100,
        "recent_developments": "Upgrading from FOL to full operational base. NORAD modernization priority. New radar systems planned.",
        "flag_emoji": "\U0001f1e8\U0001f1e6",
    },
    {
        "name": "Iqaluit",
        "country": "Canada",
        "lat": 63.75, "lon": -68.51,
        "type": "air",
        "alliance": "nato",
        "status": "planned",
        "capability": "Northern Operational Support Hub, fighter staging, surveillance",
        "personnel": 100,
        "recent_developments": "Planned Northern Operational Support Hub. Will support fighter deployments and surveillance missions.",
        "flag_emoji": "\U0001f1e8\U0001f1e6",
    },
    {
        "name": "CFB Goose Bay",
        "country": "Canada",
        "lat": 53.32, "lon": -60.42,
        "type": "air",
        "alliance": "nato",
        "status": "expanding",
        "capability": "NORAD modernization, fighter staging, Allied training",
        "personnel": 400,
        "recent_developments": "NORAD modernization investment. Fighter staging for Arctic intercepts. Allied training exercises.",
        "flag_emoji": "\U0001f1e8\U0001f1e6",
    },
    {
        "name": "Nanisivik Naval Facility",
        "country": "Canada",
        "lat": 73.07, "lon": -84.54,
        "type": "naval",
        "alliance": "nato",
        "status": "delayed",
        "capability": "Arctic naval refueling depot (NOT YET OPERATIONAL). Critical gap in Canada's Arctic naval capability.",
        "personnel": 0,
        "recent_developments": "DELAYED - still not fully operational. Originally promised 2015. Canada's only planned Arctic deep-water port for naval vessels.",
        "flag_emoji": "\U0001f1e8\U0001f1e6",
    },
    # --- NORWAY ---
    {
        "name": "Bardufoss",
        "country": "Norway",
        "lat": 69.06, "lon": 18.54,
        "type": "air",
        "alliance": "nato",
        "status": "expanding",
        "capability": "F-35A fighters, reactivated 2024, NATO's northernmost fighter base",
        "personnel": 2000,
        "recent_developments": "Reactivated 2024 for F-35 operations. NATO's northernmost operational fighter base.",
        "flag_emoji": "\U0001f1f3\U0001f1f4",
    },
    {
        "name": "Bod\u00f8",
        "country": "Norway",
        "lat": 67.27, "lon": 14.40,
        "type": "air",
        "alliance": "nato",
        "status": "active",
        "capability": "NATO Combined Air Operations Centre (CAOC), opened Oct 2025, QRA",
        "personnel": 500,
        "recent_developments": "NATO CAOC Finmark opened Oct 2025. Commands all NATO air operations in the High North.",
        "flag_emoji": "\U0001f1f3\U0001f1f4",
    },
    {
        "name": "Troms\u00f8",
        "country": "Norway",
        "lat": 69.68, "lon": 18.94,
        "type": "research",
        "alliance": "nato",
        "status": "active",
        "capability": "Intelligence, surveillance center, satellite ground station, submarine tracking",
        "personnel": 300,
        "recent_developments": "Norwegian Intelligence Service HQ North. Monitors Russian submarine activity in Barents Sea.",
        "flag_emoji": "\U0001f1f3\U0001f1f4",
    },
    # --- FINLAND ---
    {
        "name": "Rovaniemi",
        "country": "Finland",
        "lat": 66.56, "lon": 25.83,
        "type": "air",
        "alliance": "nato",
        "status": "expanding",
        "capability": "Lapland Air Command, F-35s arriving late 2026, close to Russian border",
        "personnel": 1000,
        "recent_developments": "F-35s arriving late 2026. Finland's newest NATO member. 1,340km border with Russia makes this a frontline base.",
        "flag_emoji": "\U0001f1eb\U0001f1ee",
    },
    # --- ICELAND ---
    {
        "name": "Keflav\u00edk",
        "country": "Iceland",
        "lat": 63.97, "lon": -22.61,
        "type": "air",
        "alliance": "nato",
        "status": "active",
        "capability": "NATO air policing rotations, P-8A Poseidon patrols, GIUK gap surveillance",
        "personnel": 100,
        "recent_developments": "NATO air policing rotations. Critical for monitoring GIUK gap submarine transits.",
        "flag_emoji": "\U0001f1ee\U0001f1f8",
    },
    # --- DENMARK ---
    {
        "name": "Station Nord, Greenland",
        "country": "Denmark",
        "lat": 81.60, "lon": -16.67,
        "type": "research",
        "alliance": "nato",
        "status": "active",
        "capability": "Northernmost permanently inhabited military outpost, Arctic surveillance, weather monitoring",
        "personnel": 5,
        "recent_developments": "World's northernmost permanently manned military outpost. Minimal staff but strategically important for Arctic presence.",
        "flag_emoji": "\U0001f1e9\U0001f1f0",
    },
    # --- CHINA ---
    {
        "name": "Yellow River Station, Svalbard",
        "country": "China",
        "lat": 78.92, "lon": 11.93,
        "type": "research",
        "alliance": "china",
        "status": "active",
        "capability": "'Research' station with dual-use radar/satellite tracking. Possible missile early warning capability.",
        "personnel": 25,
        "recent_developments": "Officially a research station, but intelligence analysts assess dual-use radar and satellite tracking capability. China's Arctic foothold.",
        "flag_emoji": "\U0001f1e8\U0001f1f3",
    },
    {
        "name": "Icebreaker Fleet (various)",
        "country": "China",
        "lat": 72.0, "lon": 125.0,
        "type": "naval",
        "alliance": "china",
        "status": "expanding",
        "capability": "5 icebreakers, 3 deployed Arctic 2024, record NSR transits. Xuelong 2 polar-class.",
        "personnel": 500,
        "recent_developments": "Record NSR transits in 2025. 3 icebreakers deployed to Arctic in 2024. Building nuclear icebreaker. 'Near-Arctic state' doctrine.",
        "flag_emoji": "\U0001f1e8\U0001f1f3",
    },
]

# Country name to ISO-alpha3 mapping for DB queries
_COUNTRY_ISO3 = {
    "Russia": "RUS",
    "United States": "USA",
    "Canada": "CAN",
    "Norway": "NOR",
    "Finland": "FIN",
    "Iceland": "ISL",
    "Denmark": "DNK",
    "China": "CHN",
}

# Canadian base coordinates for distance-from-Canada calculations
CANADIAN_BASES = [
    b for b in ARCTIC_BASES if b["country"] == "Canada"
]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two points in kilometres."""
    R = 6371.0
    rlat1, rlon1, rlat2, rlon2 = (
        math.radians(lat1), math.radians(lon1),
        math.radians(lat2), math.radians(lon2),
    )
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_base_threat_level(base: dict) -> int:
    """Assign a 1-5 threat score.

    Factors:
      - Proximity to Ottawa (closer = higher)
      - Offensive capability (bombers/missiles/subs = higher than radar/research)
      - Recent expansion (status=expanding = +1)
      - Alliance (russia/china = threat, nato = friendly -> low)
    """
    if base["alliance"] == "nato":
        # NATO bases are friendly -- score 1 always
        return 1

    score = 2  # baseline for adversary bases

    # Proximity to Ottawa
    dist = _haversine_km(base["lat"], base["lon"], OTTAWA_LAT, OTTAWA_LON)
    if dist < 3000:
        score += 2
    elif dist < 5000:
        score += 1

    # Offensive capability keywords
    cap_lower = base["capability"].lower()
    offensive_keywords = [
        "bomber", "icbm", "slbm", "nuclear", "missile", "submarine",
        "interceptor", "fighter", "strike",
    ]
    if any(kw in cap_lower for kw in offensive_keywords):
        score += 1

    # Status expansion
    if base["status"] == "expanding":
        score += 1

    return min(score, 5)


def _nearest_canadian_base(lat: float, lon: float) -> tuple[str, float]:
    """Return (name, distance_km) of the nearest Canadian base."""
    best_name = "N/A"
    best_dist = float("inf")
    for cb in CANADIAN_BASES:
        d = _haversine_km(lat, lon, cb["lat"], cb["lon"])
        if d < best_dist:
            best_dist = d
            best_name = cb["name"]
    return best_name, round(best_dist)


@router.get("/bases")
async def get_arctic_bases():
    """Comprehensive Arctic base registry with threat scoring.

    Returns all known military bases in the Arctic region, enriched with
    arms import data from the database and threat level scoring.
    Cached for 1 hour.
    """
    cache_key = "arctic_bases"
    cached = _arctic_cache.get(cache_key)
    if cached and time.time() - cached[0] < _BASES_TTL:
        return cached[1]

    # Query DB for arms imports by country since 2020
    country_imports: dict[str, float] = {}
    try:
        session = SessionLocal()
        try:
            # Use trade_indicators table (World Bank mirror of SIPRI TIV)
            rows = session.execute(text("""
                SELECT c.name, SUM(COALESCE(ti.arms_imports_tiv, 0)) as total_tiv
                FROM trade_indicators ti
                JOIN countries c ON ti.country_id = c.id
                WHERE ti.year >= 2020
                  AND c.name IN (:r, :us, :ca, :no, :fi, :is_, :dk, :cn)
                GROUP BY c.name
            """), {
                "r": "Russia", "us": "United States", "ca": "Canada",
                "no": "Norway", "fi": "Finland", "is_": "Iceland",
                "dk": "Denmark", "cn": "China",
            }).fetchall()
            for r in rows:
                country_imports[r[0]] = float(r[1])
        finally:
            session.close()
    except Exception as e:
        logger.warning("Could not query arms imports for bases: %s", e)

    # Also try arms_transfers table as fallback/supplement
    try:
        session = SessionLocal()
        try:
            rows = session.execute(text("""
                SELECT c.name, SUM(COALESCE(at.tiv_delivered, 0)) as total_tiv
                FROM arms_transfers at
                JOIN countries c ON at.buyer_id = c.id
                WHERE at.order_year >= 2020
                  AND c.name IN (:r, :us, :ca, :no, :fi, :is_, :dk, :cn)
                GROUP BY c.name
            """), {
                "r": "Russia", "us": "United States", "ca": "Canada",
                "no": "Norway", "fi": "Finland", "is_": "Iceland",
                "dk": "Denmark", "cn": "China",
            }).fetchall()
            for r in rows:
                existing = country_imports.get(r[0], 0)
                transfer_tiv = float(r[1])
                # Use whichever is larger
                country_imports[r[0]] = max(existing, transfer_tiv)
        finally:
            session.close()
    except Exception as e:
        logger.warning("Could not query arms_transfers for bases: %s", e)

    # Build enriched response
    bases = []
    for b in ARCTIC_BASES:
        threat = _compute_base_threat_level(b)
        dist_ottawa = round(_haversine_km(b["lat"], b["lon"], OTTAWA_LAT, OTTAWA_LON))
        nearest_ca_name, nearest_ca_dist = _nearest_canadian_base(b["lat"], b["lon"])

        bases.append({
            **b,
            "threat_level": threat,
            "distance_to_ottawa_km": dist_ottawa,
            "nearest_canadian_base": nearest_ca_name,
            "distance_to_nearest_canadian_km": nearest_ca_dist,
            "arms_imports_tiv": country_imports.get(b["country"], 0),
        })

    # Sort by threat level descending, then distance ascending
    bases.sort(key=lambda x: (-x["threat_level"], x["distance_to_ottawa_km"]))

    result = {
        "bases": bases,
        "summary": {
            "total_bases": len(bases),
            "russia_bases": sum(1 for b in bases if b["alliance"] == "russia"),
            "nato_bases": sum(1 for b in bases if b["alliance"] == "nato"),
            "china_bases": sum(1 for b in bases if b["alliance"] == "china"),
            "expanding": sum(1 for b in bases if b["status"] == "expanding"),
            "delayed": sum(1 for b in bases if b["status"] == "delayed"),
            "threat_5_count": sum(1 for b in bases if b["threat_level"] == 5),
            "threat_4_count": sum(1 for b in bases if b["threat_level"] == 4),
        },
        "timestamp": time.time(),
    }

    _arctic_cache[cache_key] = (time.time(), result)
    return result

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
