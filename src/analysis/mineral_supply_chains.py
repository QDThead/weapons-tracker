"""Mineral supply chain data module for CesiumJS 3D Supply Chain Globe.

Contains curated USGS MCS 2025 data for 30 defence-critical minerals
with mining, processing, component, and platform linkages plus
geographic coordinates for globe visualisation.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Geographic coordinates — standard centroids (lat, lon)
# ---------------------------------------------------------------------------

COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Argentina": (-38.4, -63.6),
    "Armenia": (40.1, 44.5),
    "Australia": (-25.3, 133.8),
    "Austria": (47.5, 14.6),
    "Belgium": (50.5, 4.5),
    "Brazil": (-14.2, -51.9),
    "Canada": (56.1, -106.3),
    "Chile": (-35.7, -71.5),
    "China": (35.9, 104.2),
    "DRC": (-4.0, 21.8),
    "Estonia": (58.6, 25.0),
    "Finland": (61.9, 25.7),
    "France": (46.2, 2.2),
    "Gabon": (-0.8, 11.6),
    "Germany": (51.2, 10.4),
    "Ghana": (7.9, -1.0),
    "Guinea": (9.9, -11.4),
    "India": (20.6, 79.0),
    "Indonesia": (-0.8, 113.9),
    "Iran": (32.4, 53.7),
    "Israel": (31.0, 34.9),
    "Japan": (36.2, 138.3),
    "Kazakhstan": (48.0, 68.0),
    "Madagascar": (-18.8, 46.9),
    "Malaysia": (4.2, 101.9),
    "Mexico": (23.6, -102.6),
    "Mongolia": (46.9, 103.8),
    "Mozambique": (-18.7, 35.5),
    "Myanmar": (21.9, 96.0),
    "Netherlands": (52.1, 5.3),
    "New Caledonia": (-20.9, 165.6),
    "Nigeria": (9.1, 8.7),
    "Norway": (60.5, 8.5),
    "Peru": (-9.2, -75.0),
    "Philippines": (12.9, 121.8),
    "Poland": (51.9, 19.1),
    "Russia": (61.5, 105.3),
    "Rwanda": (-1.9, 29.9),
    "Senegal": (14.5, -14.5),
    "South Africa": (-30.6, 22.9),
    "South Korea": (35.9, 127.8),
    "Spain": (40.5, -3.7),
    "Tajikistan": (38.9, 71.3),
    "Thailand": (15.9, 100.5),
    "Turkey": (39.0, 35.2),
    "UAE": (23.4, 53.8),
    "UK": (55.4, -3.4),
    "Ukraine": (48.4, 31.2),
    "USA": (37.1, -95.7),
    "Vietnam": (14.1, 108.3),
    "Zimbabwe": (-19.0, 29.2),
}

# ---------------------------------------------------------------------------
# Strategic chokepoints — (lat, lon)
# ---------------------------------------------------------------------------

CHOKEPOINTS: dict[str, tuple[float, float]] = {
    "Strait of Malacca": (2.5, 101.0),
    "Suez Canal": (30.5, 32.3),
    "Cape of Good Hope": (-34.4, 18.5),
    "Strait of Hormuz": (26.6, 56.3),
    "Panama Canal": (9.1, -79.7),
    "Bab-el-Mandeb": (12.6, 43.3),
    "Turkish Straits": (41.1, 29.1),
    "South China Sea": (12.0, 114.0),
    "Lombok Strait": (-8.5, 115.7),
    "Drake Passage": (-60.0, -65.0),
    "Mozambique Channel": (-17.0, 42.0),
    "Korean Strait": (34.0, 129.5),
    "Sea of Japan": (40.0, 135.0),
    "St. Lawrence Seaway": (47.0, -74.0),
    "Gulf of Mexico": (25.0, -90.0),
    "Strait of Gibraltar": (35.9, -5.6),
    "Northern Sea Route": (73.0, 115.0),
    "Norwegian Sea": (67.0, 2.0),
    "North Atlantic": (45.0, -30.0),
    "Pacific shipping lanes": (30.0, -150.0),
    "South Atlantic": (-30.0, -15.0),
    "Indian Ocean": (-10.0, 70.0),
    "Baltic Sea": (58.0, 20.0),
    "Trans-Siberian rail": (56.0, 93.0),
    "Central Asian rail": (41.0, 65.0),
    "Trans-Mongolian rail": (48.0, 107.0),
}

# ---------------------------------------------------------------------------
# Helper functions — build node dicts with injected coordinates
# ---------------------------------------------------------------------------


def _coords(country: str) -> tuple[float, float]:
    """Return (lat, lon) for a country, defaulting to (0, 0) if unknown."""
    return COUNTRY_COORDS.get(country, (0.0, 0.0))


def _cp(name: str) -> dict:
    """Build a chokepoint entry with coordinates."""
    lat, lon = CHOKEPOINTS.get(name, (0.0, 0.0))
    return {"name": name, "lat": lat, "lon": lon}


def _mining(country: str, pct: float) -> dict:
    """Build a mining node entry."""
    lat, lon = _coords(country)
    return {"country": country, "pct": pct, "lat": lat, "lon": lon}


def _processing(country: str, pct: float, note: str = "") -> dict:
    """Build a processing node entry."""
    lat, lon = _coords(country)
    entry: dict = {"country": country, "pct": pct, "lat": lat, "lon": lon}
    if note:
        entry["note"] = note
    return entry


def _component(name: str) -> dict:
    """Build a component entry."""
    return {"name": name}


def _platform(name: str) -> dict:
    """Build a platform entry."""
    return {"name": name}


# ---------------------------------------------------------------------------
# 30 defence-critical minerals — USGS MCS 2025 data
# ---------------------------------------------------------------------------

MINERALS: list[dict] = [
    # 1. Titanium
    {
        "name": "Titanium",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 29),
            _mining("Mozambique", 10),
            _mining("South Africa", 9),
            _mining("Australia", 8),
            _mining("Canada", 5),
        ],
        "processing": [
            _processing("China", 51, "sponge"),
            _processing("Japan", 17),
            _processing("Russia", 13),
            _processing("Kazakhstan", 7),
            _processing("Ukraine", 3),
        ],
        "components": [
            _component("Aircraft frames"),
            _component("Jet engine discs"),
            _component("Submarine hulls"),
            _component("Landing gear"),
            _component("Armor"),
        ],
        "platforms": [
            _platform("F-22"),
            _platform("F-35"),
            _platform("Virginia-class SSN"),
            _platform("CH-148"),
            _platform("Eurofighter"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Suez Canal"), _cp("Cape of Good Hope")],
        "hhi": 1500,
        "risk_level": "high",
        "risk_factors": [
            "Russia sanctions 13% sponge",
            "China 51% processing",
            "Ukraine conflict",
            "Japan single-source",
        ],
        "canada": {
            "platforms": ["CF-188 Hornet", "F-35 Lightning II (on order)", "CH-148 Cyclone", "Victoria-class SSK", "CSC Type 26"],
            "import_pct": 95,
            "domestic": "5% ilmenite mining at Havre-Saint-Pierre QC (Rio Tinto), no sponge processing",
            "strategic_note": "Canada mines ilmenite but ships it abroad for processing. F-35 acquisition will increase titanium dependency — F-35 is 41% titanium by weight.",
        },
        "source": "USGS MCS 2025",
    },
    # 2. Lithium
    {
        "name": "Lithium",
        "category": "Battery Metal",
        "mining": [
            _mining("Australia", 37),
            _mining("Chile", 20),
            _mining("China", 19),
            _mining("Argentina", 9),
            _mining("Zimbabwe", 5),
        ],
        "processing": [
            _processing("China", 65, "hydroxide/carbonate"),
            _processing("Chile", 20),
            _processing("Argentina", 8),
        ],
        "components": [
            _component("Li-ion batteries"),
            _component("Thermal batteries"),
            _component("Torpedo batteries"),
            _component("UAV power"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("MQ-9"),
            _platform("Javelin"),
            _platform("MK-48"),
            _platform("Switchblade"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Panama Canal"), _cp("Cape of Good Hope")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "China 65% refining",
            "Aus ore to China",
            "Price volatility",
            "Chile/Argentina water",
        ],
        "canada": {
            "platforms": ["CF-188 avionics batteries", "soldier portable electronics", "tactical UAV batteries", "Carl Gustaf thermal battery"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "100% import-dependent. Growing demand from military electrification (hybrid vehicles, UAV fleet expansion) will increase exposure.",
        },
        "source": "USGS MCS 2025",
    },
    # 3. Cobalt
    {
        "name": "Cobalt",
        "category": "Battery Metal",
        "mining": [
            _mining("DRC", 76),
            _mining("Indonesia", 10),
            _mining("Russia", 2),
            _mining("Australia", 1.4),
            _mining("Philippines", 1.3),
        ],
        "processing": [
            _processing("China", 80),
            _processing("Finland", 8),
            _processing("Belgium", 5),
        ],
        "components": [
            _component("Superalloy turbine blades"),
            _component("Li-CoO batteries"),
            _component("Cemented carbides"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("F/A-18"),
            _platform("MQ-9"),
            _platform("Tomahawk"),
            _platform("CH-149"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca"), _cp("Suez Canal")],
        "hhi": 5900,
        "risk_level": "critical",
        "risk_factors": [
            "DRC produces 84% of global cobalt; M23 conflict advancing toward Katanga mining region",
            "Chinese firms control ~80% of DRC mining operations (CMOC: TFM/Kisanfu, Jinchuan: Musonoi)",
            "China refines 80% of cobalt metal and 91% of battery-grade cobalt chemicals",
            "DRC imposed export quotas (2025-2026) — less than half of 2024 output authorized",
            "Indonesia's rising output (8%) is entirely Chinese-financed HPAL plants",
            "Artisanal mining (2% of DRC output) carries child labor and conflict mineral risks",
            "Cobalt price crashed 70% (2022-2024) causing mine deferrals — Cobalt Blue Broken Hill shelved",
            "Sherritt's Cuba-Canada pipeline paused Feb 2026 due to Cuban fuel crisis",
            "If China restricts cobalt: Western superalloy production limited to Umicore (15kt) + Sherritt (3.8kt) — insufficient for NATO demand",
            "No substitutes exist for cobalt in high-temperature turbine superalloys (Waspaloy, CMSX-4, Stellite)",
        ],
        "canada": {
            "platforms": [
                "CF-188 Hornet — 2x GE F404 engines (Waspaloy/Rene-class turbine blades, 10-13% Co)",
                "F-35 Lightning II (on order) — P&W F135 engine (CMSX-4 single-crystal blades, 9.5% Co)",
                "CH-148 Cyclone — 2x GE CT7-8A7 (cobalt superalloy HP turbine)",
                "CH-149 Cormorant — 3x GE CT7-8A (cobalt superalloy turbine section)",
                "CH-147F Chinook — 2x Honeywell T55 (Co superalloy turbine blades)",
                "CC-177 Globemaster III — 4x P&W F117 (cobalt HP turbine blades)",
                "Halifax-class frigates — 2x GE LM2500 (Stellite 6 guide vanes, 60% Co)",
                "Leopard 2A6M — MTU MB 873 (Stellite exhaust valve hardfacing)",
                "LAV 6.0 — Caterpillar C7 (Stellite exhaust valve seats)",
                "BB-2590/U soldier batteries — NMC/LCO cathode (cobalt-containing)",
                "AIM-9 Sidewinder / AIM-120 AMRAAM — SmCo fin actuator magnets (52% Co)",
            ],
            "import_pct": 85,
            "domestic": "~4,800t/year: Vale Long Harbour NL (~2,500t), Sherritt Fort Saskatchewan AB (~3,200t, currently paused), Glencore Raglan/Sudbury (~800t exported to Norway). Canada is world's 4th-5th largest cobalt producer.",
            "strategic_note": "Every CAF jet engine, helicopter, frigate gas turbine, and guided missile depends on cobalt superalloys. Sherritt's Cuban pipeline — the only vertically integrated non-Chinese cobalt supply — is paused due to Cuba's energy crisis (Feb 2026). Pentagon named Canada as preferred cobalt supplier for US $500M stockpile program. F-35 acquisition will increase cobalt dependency significantly (CMSX-4 single-crystal blades in F135 engine).",
        },
        "mines": [
            {"name": "Tenke Fungurume (TFM)", "owner": "CMOC Group (China)", "country": "DRC", "lat": -10.6, "lon": 26.1, "production_t": 32000, "note": "World's largest cobalt mine. Freeport-McMoRan sold to CMOC in 2016 for $2.65B"},
            {"name": "Kisanfu (KFM)", "owner": "CMOC + CATL", "country": "DRC", "lat": -10.4, "lon": 25.7, "production_t": 15000, "note": "World's largest undeveloped cobalt deposit at time of acquisition"},
            {"name": "Kamoto (KCC)", "owner": "Glencore (75%) / Gecamines (25%)", "country": "DRC", "lat": -10.8, "lon": 25.4, "production_t": 12000, "note": "2026 DRC quota: 2,775t cobalt"},
            {"name": "Mutanda", "owner": "Glencore (95%)", "country": "DRC", "lat": -10.7, "lon": 25.9, "production_t": 8000, "note": "Suspended 2019-2022 due to low prices; Glencore considering 40% sale"},
            {"name": "Murrin Murrin", "owner": "Glencore/Minara Resources", "country": "Australia", "lat": -29.0, "lon": 121.9, "production_t": 2100, "note": "HPAL plant; >50% of Australian cobalt output"},
            {"name": "Moa JV", "owner": "Sherritt International (50%)", "country": "Cuba", "lat": 20.7, "lon": -75.0, "production_t": 3200, "note": "Mixed sulphide shipped to Fort Saskatchewan AB. Paused Feb 2026 — Cuban fuel crisis"},
            {"name": "Voisey's Bay", "owner": "Vale Base Metals", "country": "Canada", "lat": 56.3, "lon": -62.1, "production_t": 2500, "note": "Concentrate processed at Long Harbour NL hydromet plant"},
            {"name": "Sudbury Basin", "owner": "Vale / Glencore", "country": "Canada", "lat": 46.5, "lon": -81.0, "production_t": 1500, "note": "Ni-Cu-Co sulfide; Glencore sends concentrate to Nikkelverk, Norway"},
            {"name": "Raglan Mine", "owner": "Glencore", "country": "Canada", "lat": 61.7, "lon": -73.6, "production_t": 800, "note": "Nunavik QC; concentrate exported to Norway for refining"},
        ],
        "refineries": [
            {"name": "Huayou Cobalt", "owner": "Zhejiang Huayou Cobalt Co.", "country": "China", "lat": 30.6, "lon": 120.7, "capacity_t": 38000, "products": "Cobalt metal, sulfate, hydroxide", "note": "World's largest cobalt refiner"},
            {"name": "GEM Co.", "owner": "GEM Co. Ltd.", "country": "China", "lat": 22.5, "lon": 114.1, "capacity_t": 15000, "products": "Recycled + refined cobalt", "note": "Major recycler in Shenzhen"},
            {"name": "Jinchuan Group", "owner": "Jinchuan Group (SOE)", "country": "China", "lat": 38.5, "lon": 102.2, "capacity_t": 8000, "products": "Cobalt metal, oxide", "note": "Integrated miner-refiner, Gansu province"},
            {"name": "Umicore Kokkola", "owner": "Umicore", "country": "Finland", "lat": 63.8, "lon": 23.1, "capacity_t": 15000, "products": "Cobalt metal, chemicals, cathode precursors", "note": "Europe's largest cobalt refinery. Acquired from Freeport Cobalt 2019"},
            {"name": "Umicore Hoboken", "owner": "Umicore", "country": "Belgium", "lat": 51.2, "lon": 4.4, "capacity_t": 5000, "products": "Cobalt chemicals, recycled metals", "note": "130+ years operation. EUR 350M EIB financing for battery R&D"},
            {"name": "Fort Saskatchewan", "owner": "Sherritt International", "country": "Canada", "lat": 53.7, "lon": -113.2, "capacity_t": 3800, "products": "99.9% cobalt powder and briquettes", "note": "Refines Cuban mixed sulphides. Only vertically integrated non-Chinese pipeline"},
            {"name": "Long Harbour NPP", "owner": "Vale Base Metals", "country": "Canada", "lat": 47.4, "lon": -53.8, "capacity_t": 2500, "products": "Cobalt rounds/briquettes", "note": "Hydromet plant processing Voisey's Bay concentrate"},
            {"name": "Niihama Nickel Refinery", "owner": "Sumitomo Metal Mining", "country": "Japan", "lat": 33.9, "lon": 133.3, "capacity_t": 4000, "products": "Electrolytic cobalt", "note": "Japan's only cobalt refinery. Feeds from Philippine HPAL"},
            {"name": "Harjavalta", "owner": "Nornickel", "country": "Finland", "lat": 61.3, "lon": 22.1, "capacity_t": 3000, "products": "Cobalt sulfate", "note": "LME suspended nickel brands due to Russian ownership"},
        ],
        "alloys": [
            {"name": "CMSX-4", "cobalt_pct": 9.5, "type": "Single-crystal superalloy", "use": "HP turbine blades in F-35 F135, F-22 F119 engines", "temp": "1150C+"},
            {"name": "Waspaloy", "cobalt_pct": 13.0, "type": "Ni-base wrought", "use": "Turbine discs, combustion chambers, afterburner parts", "temp": "870C"},
            {"name": "MarM-247", "cobalt_pct": 10.0, "type": "Ni-base cast/DS", "use": "HP turbine blades (investment cast)", "temp": "1050C"},
            {"name": "Stellite 6", "cobalt_pct": 60.0, "type": "Co-Cr-W alloy", "use": "Valve seats, wear surfaces in diesel/gas turbine engines", "temp": "800C"},
            {"name": "Inconel 718", "cobalt_pct": 1.0, "type": "Ni-base precipitation hardened", "use": "Turbine discs, compressor blades, shafts, fasteners", "temp": "700C"},
            {"name": "Rene 80", "cobalt_pct": 9.5, "type": "Ni-base cast", "use": "Turbine blades in older-generation engines", "temp": "980C"},
            {"name": "SmCo (Sm2Co17)", "cobalt_pct": 52.0, "type": "Permanent magnet", "use": "Missile fin actuators (AIM-120, Tomahawk, Sidewinder)", "temp": "350C"},
            {"name": "WC-Co", "cobalt_pct": 7.0, "type": "Cemented carbide", "use": "Armor-piercing ammunition, cutting tools, barrel liners", "temp": "N/A"},
        ],
        "shipping_routes": [
            {
                "name": "DRC → China (primary)",
                "description": "Katanga mines → truck to Dar es Salaam or Durban → ship to Shanghai/Ningbo",
                "form": "Cobalt hydroxide (wet paste)",
                "transit_days": 90,
                "waypoints": [
                    [26.0, -10.7], [32.0, -8.0], [39.3, -6.8],
                    [45.0, -2.0], [55.0, 5.0], [70.0, 8.0],
                    [80.0, 6.0], [95.0, 3.0], [101.0, 2.5],
                    [110.0, 5.0], [121.5, 31.2]
                ],
            },
            {
                "name": "China → Vancouver",
                "description": "Chinese refined cobalt metal/sulfate → Pacific → Vancouver BC",
                "form": "Refined cobalt metal, cobalt sulfate",
                "transit_days": 16,
                "waypoints": [
                    [121.5, 31.2], [130.0, 33.5], [140.0, 37.0],
                    [152.0, 40.0], [170.0, 45.0], [-180.0, 48.0],
                    [-170.0, 49.0], [-155.0, 50.0], [-140.0, 50.5],
                    [-130.0, 50.0], [-123.11, 49.29]
                ],
            },
            {
                "name": "Finland → Montreal",
                "description": "Umicore Kokkola refined cobalt → Baltic → North Sea → Atlantic → St. Lawrence",
                "form": "Cobalt metal, chemicals, cathode precursors",
                "transit_days": 16,
                "waypoints": [
                    [23.1, 63.8], [22.0, 58.0], [12.0, 56.0],
                    [4.0, 54.0], [-2.0, 51.0], [-10.0, 50.0],
                    [-20.0, 50.0], [-35.0, 50.0], [-50.0, 48.0],
                    [-55.0, 48.5], [-65.0, 48.0], [-73.55, 45.50]
                ],
            },
            {
                "name": "Belgium → Montreal",
                "description": "Umicore Hoboken → English Channel → Atlantic → St. Lawrence",
                "form": "Cobalt chemicals, recycled metals",
                "transit_days": 12,
                "waypoints": [
                    [4.4, 51.2], [2.0, 51.0], [-5.0, 50.0],
                    [-15.0, 50.0], [-30.0, 49.0], [-45.0, 48.0],
                    [-55.0, 48.5], [-65.0, 48.0], [-73.55, 45.50]
                ],
            },
            {
                "name": "Cuba → Fort Saskatchewan",
                "description": "Moa Bay mixed sulphide → ship to Montreal → rail to Fort Saskatchewan AB",
                "form": "Mixed sulphide precipitate (MSP)",
                "transit_days": 8,
                "waypoints": [
                    [-75.0, 20.7], [-76.0, 22.0], [-73.0, 24.0],
                    [-68.0, 30.0], [-65.0, 38.0], [-62.0, 44.0],
                    [-59.0, 47.0], [-55.0, 48.5], [-65.0, 48.0],
                    [-73.55, 45.50]
                ],
                "onward": "Rail: Montreal → Fort Saskatchewan AB (3,500 km, ~4 days)",
            },
            {
                "name": "DRC → Lobito Corridor (emerging)",
                "description": "Katanga → rail to Lobito, Angola → Atlantic → North America",
                "form": "Cobalt hydroxide, copper-cobalt concentrate",
                "transit_days": 25,
                "waypoints": [
                    [26.0, -10.7], [22.0, -11.0], [18.0, -12.0],
                    [13.8, -12.3], [5.0, -8.0], [-5.0, 0.0],
                    [-20.0, 10.0], [-40.0, 25.0], [-55.0, 35.0],
                    [-63.57, 44.65]
                ],
                "note": "Under construction. First shipments 2026. Could break Chinese logistics control.",
            },
        ],
        "source": "USGS MCS 2025",
    },
    # 4. Rare Earth Elements
    {
        "name": "Rare Earth Elements",
        "category": "Electronic Material",
        "mining": [
            _mining("China", 69),
            _mining("USA", 12),
            _mining("Myanmar", 8),
            _mining("Australia", 4),
            _mining("Thailand", 3),
        ],
        "processing": [
            _processing("China", 90, "separation/magnets"),
            _processing("Malaysia", 3),
            _processing("Estonia", 1),
        ],
        "components": [
            _component("NdFeB magnets"),
            _component("PGM fin actuators"),
            _component("Satellite reaction wheels"),
            _component("Sonar"),
            _component("Lasers"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("F-22"),
            _platform("Virginia SSN"),
            _platform("DDG-51"),
            _platform("THAAD"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("South China Sea"), _cp("Suez Canal")],
        "hhi": 5100,
        "risk_level": "critical",
        "risk_factors": [
            "China 90% monopoly",
            "2024 export controls",
            "Myanmar border trade",
            "78% US weapons use REE",
            "China 2025 ban",
        ],
        "canada": {
            "platforms": ["CF-188 guided munitions", "F-35 (on order, 920 lbs REE)", "Halifax-class radar/sonar", "Victoria-class sonar", "AIM-9/AIM-120 missiles"],
            "import_pct": 100,
            "domestic": "Vital Metals Nechalacho mine (NWT) in early production, not yet significant",
            "strategic_note": "F-35 program requires 920 lbs of REE per aircraft. Canada has no separation/magnet capacity. China's 2025 export ban directly threatens CAF modernization.",
        },
        "source": "USGS MCS 2025",
    },
    # 5. Tungsten
    {
        "name": "Tungsten",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 83),
            _mining("Vietnam", 5),
            _mining("Russia", 2.5),
            _mining("Austria", 1.5),
            _mining("Spain", 1),
        ],
        "processing": [
            _processing("China", 82, "APT/carbide"),
            _processing("Austria", 5),
            _processing("Vietnam", 3),
        ],
        "components": [
            _component("AP penetrators"),
            _component("APFSDS rounds"),
            _component("Carbide tools"),
            _component("Shaped charges"),
        ],
        "platforms": [
            _platform("M1A2 Abrams"),
            _platform("Leopard 2"),
            _platform("Challenger 3"),
            _platform("A-10"),
            _platform("CIWS Phalanx"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Trans-Siberian rail")],
        "hhi": 6900,
        "risk_level": "critical",
        "risk_factors": [
            "China 83% monopoly",
            "2024 export controls",
            "No substitutes for AP",
            "Russia sanctions",
            "Austria only Western processor",
        ],
        "canada": {
            "platforms": ["Leopard 2A6M 120mm APFSDS rounds", "C7/C8 rifle 5.56mm AP", "M777 155mm shells", "LAV 6.0 ammunition", ".50 cal AP"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Canada has zero tungsten production. All AP ammunition for CAF tanks, rifles, and artillery depends on Chinese-controlled supply. No substitutes exist.",
        },
        "source": "USGS MCS 2025",
    },
    # 6. Gallium
    {
        "name": "Gallium",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 99),
            _mining("Japan", 0.5),
            _mining("South Korea", 0.3),
            _mining("Russia", 0.2),
        ],
        "processing": [
            _processing("China", 98, "high-purity"),
            _processing("Japan", 1),
            _processing("South Korea", 0.5),
        ],
        "components": [
            _component("GaN AESA radar"),
            _component("EW jammers"),
            _component("Missile seeker GaAs"),
            _component("Satcom"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("F-22"),
            _platform("EA-18G"),
            _platform("Patriot PAC-3"),
            _platform("AN/SPY-6"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Pacific shipping lanes")],
        "hhi": 9800,
        "risk_level": "critical",
        "risk_factors": [
            "China 98-99%",
            "2023 export controls",
            "No non-Chinese production",
            "All radar/EW depends on it",
            "Single failure point",
        ],
        "canada": {
            "platforms": ["CF-188 AN/APG-73 radar", "F-35 AN/APG-81 AESA radar (on order)", "Halifax-class radar systems", "electronic warfare suites"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "China's 2023 export controls directly threaten Canada's F-35 acquisition and Halifax-class radar upgrades. No non-Chinese supply exists.",
        },
        "source": "USGS MCS 2025",
    },
    # 7. Germanium
    {
        "name": "Germanium",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 68),
            _mining("Canada", 4),
            _mining("Belgium", 3),
            _mining("Russia", 3),
            _mining("USA", 1),
        ],
        "processing": [
            _processing("China", 68),
            _processing("Belgium", 10),
            _processing("Canada", 8),
            _processing("Russia", 5),
            _processing("Japan", 3),
        ],
        "components": [
            _component("IR optics"),
            _component("Fiber optics"),
            _component("Night vision"),
            _component("IR missile seekers"),
        ],
        "platforms": [
            _platform("Apache AH-64"),
            _platform("F-35"),
            _platform("Javelin"),
            _platform("Stinger"),
            _platform("LITENING pod"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Suez Canal")],
        "hhi": 4800,
        "risk_level": "critical",
        "risk_factors": [
            "China 2023 export controls",
            "Essential for thermal imaging",
            "No substitute for IR windows",
            "Umicore main Western refiner",
        ],
        "canada": {
            "platforms": ["Leopard 2A6M thermal sights", "LAV 6.0 thermal imaging", "CF-188 targeting pods", "sniper optics", "Victoria-class periscopes"],
            "import_pct": 96,
            "domestic": "~4% from Teck Resources zinc refining at Trail BC",
            "strategic_note": "Teck's Trail smelter provides partial hedge, but insufficient for military-grade IR optics. All CAF thermal imaging depends on germanium.",
        },
        "source": "USGS MCS 2025",
    },
    # 8. Antimony
    {
        "name": "Antimony",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 48),
            _mining("Tajikistan", 25),
            _mining("Turkey", 7),
            _mining("Myanmar", 5),
            _mining("Russia", 5),
        ],
        "processing": [
            _processing("China", 55, "trioxide"),
            _processing("Tajikistan", 15),
            _processing("Belgium", 5),
        ],
        "components": [
            _component("Lead-hardened ammo"),
            _component("AP rounds"),
            _component("Primers"),
            _component("Flame retardant"),
        ],
        "platforms": [
            _platform("Small arms ammo"),
            _platform("Mk 211 Raufoss"),
            _platform("Artillery"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Central Asian rail"), _cp("Turkish Straits")],
        "hhi": 3100,
        "risk_level": "high",
        "risk_factors": [
            "China Dec 2024 ban",
            "Tajikistan limited capacity",
            "Russia sanctions",
            "Critical for all ammo",
            "US 85% import-reliant",
        ],
        "canada": {
            "platforms": ["All CAF small arms ammunition (5.56mm, 7.62mm, .50 cal)", "155mm artillery shells", "LAV 6.0 fire suppression", "body armor flame resistance"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "China's December 2024 export ban is existential — antimony hardens every bullet the CAF fires. No domestic source, no substitute.",
        },
        "source": "USGS MCS 2025",
    },
    # 9. Beryllium
    {
        "name": "Beryllium",
        "category": "Strategic Metal",
        "mining": [
            _mining("USA", 58),
            _mining("China", 22),
            _mining("Mozambique", 5),
            _mining("Madagascar", 3),
            _mining("Brazil", 3),
        ],
        "processing": [
            _processing("USA", 65, "Materion"),
            _processing("China", 20),
            _processing("Kazakhstan", 8),
        ],
        "components": [
            _component("Satellite structures"),
            _component("Nuclear reflectors"),
            _component("Gyroscope bearings"),
            _component("X-ray windows"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("F-22"),
            _platform("Trident D5"),
            _platform("GPS III"),
        ],
        "chokepoints": [_cp("Suez Canal")],
        "hhi": 4000,
        "risk_level": "medium",
        "risk_factors": [
            "US advantage (58%/65%)",
            "Materion single point",
            "Toxicity limits expansion",
            "Nuclear weapons critical",
        ],
        "canada": {
            "platforms": ["F-35 structural connectors (on order)", "satellite components (CSA RADARSAT)", "precision instrumentation"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Low volume but critical. US controls 65% of supply — allied source is favorable for Canada.",
        },
        "source": "USGS MCS 2025",
    },
    # 10. Chromium
    {
        "name": "Chromium",
        "category": "Strategic Metal",
        "mining": [
            _mining("South Africa", 48),
            _mining("Kazakhstan", 14),
            _mining("Turkey", 14),
            _mining("India", 8),
            _mining("Finland", 4),
        ],
        "processing": [
            _processing("South Africa", 43),
            _processing("China", 25),
            _processing("Kazakhstan", 12),
            _processing("India", 8),
        ],
        "components": [
            _component("SS armor plate"),
            _component("Chrome gun barrels"),
            _component("Jet combustion chambers"),
            _component("Naval components"),
        ],
        "platforms": [
            _platform("M1A2"),
            _platform("Leopard 2"),
            _platform("CVN-78 Ford"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Turkish Straits"), _cp("Strait of Hormuz")],
        "hhi": 2900,
        "risk_level": "high",
        "risk_factors": [
            "S.Africa Eskom disruptions",
            "Rail logistics",
            "Kazakhstan risk",
            "No NA mining",
            "100% US import",
        ],
        "canada": {
            "platforms": ["Leopard 2A6M armor plate", "LAV 6.0 armor", "Halifax-class hull steel", "C7/C8 barrel chrome lining", "CSC Type 26 structural steel"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Every CAF armored vehicle and naval vessel requires chromium steel. 100% import-reliant with South Africa as primary source.",
        },
        "source": "USGS MCS 2025",
    },
    # 11. Manganese
    {
        "name": "Manganese",
        "category": "Strategic Metal",
        "mining": [
            _mining("South Africa", 36),
            _mining("Gabon", 23),
            _mining("Australia", 16),
            _mining("China", 7),
            _mining("Ghana", 5),
        ],
        "processing": [
            _processing("China", 90, "EMM"),
            _processing("South Africa", 5),
            _processing("India", 2),
        ],
        "components": [
            _component("HSLA steel"),
            _component("Mn-Li batteries"),
            _component("Aircraft Al alloys"),
        ],
        "platforms": [
            _platform("All armored vehicles"),
            _platform("Naval vessels"),
            _platform("M777"),
            _platform("Submarine hulls"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "China 90% processing vs 7% mining",
            "S.Africa logistics",
            "Gabon coup 2023",
            "Essential for military steel",
            "US 100% import-reliant",
        ],
        "canada": {
            "platforms": ["LAV 6.0 hull steel", "Leopard 2A6M steel", "Halifax-class structural steel", "Victoria-class HY-80 hull", "M777 barrel steel", "CSC Type 26"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Essential for all military-grade steel. Canada has zero domestic production. China processes 90% despite mining only 7%.",
        },
        "source": "USGS MCS 2025",
    },
    # 12. Niobium
    {
        "name": "Niobium",
        "category": "Strategic Metal",
        "mining": [
            _mining("Brazil", 92),
            _mining("Canada", 7),
        ],
        "processing": [
            _processing("Brazil", 90, "CBMM integrated"),
            _processing("Canada", 7),
            _processing("China", 2),
        ],
        "components": [
            _component("HSLA steel"),
            _component("Inconel 718 turbine blades"),
            _component("Superconducting magnets"),
            _component("Rocket nozzles"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("F/A-18"),
            _platform("Virginia SSN"),
        ],
        "chokepoints": [_cp("South Atlantic"), _cp("St. Lawrence Seaway")],
        "hhi": 8500,
        "risk_level": "critical",
        "risk_factors": [
            "Brazil 92% CBMM monopoly",
            "Canada only alternative",
            "No substitutes in superalloys",
            "CBMM disruption halts global supply",
        ],
        "canada": {
            "platforms": ["CF-188 F404 engine Inconel 718", "F-35 F135 engine (on order)", "CH-148 engine components", "Victoria-class reactor-grade steel"],
            "import_pct": 0,
            "domestic": "7% of global production — Niobec mine, Saguenay QC (Magris Resources)",
            "strategic_note": "Rare strategic advantage — Canada is world's #2 niobium producer. Domestic supply secures jet engine superalloy chain.",
        },
        "source": "USGS MCS 2025",
    },
    # 13. Tantalum
    {
        "name": "Tantalum",
        "category": "Electronic Material",
        "mining": [
            _mining("DRC", 41),
            _mining("Rwanda", 15),
            _mining("Nigeria", 8),
            _mining("Brazil", 7),
            _mining("China", 5),
        ],
        "processing": [
            _processing("China", 40),
            _processing("Germany", 15),
            _processing("USA", 10),
            _processing("Kazakhstan", 8),
            _processing("Japan", 7),
        ],
        "components": [
            _component("Ta capacitors (avionics)"),
            _component("Rocket combustion chambers"),
            _component("Shaped charge liners"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("Patriot"),
            _platform("JDAM"),
            _platform("Tomahawk"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Suez Canal"), _cp("Strait of Malacca")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "DRC/Rwanda 56% conflict zones",
            "Smuggling",
            "Dodd-Frank",
            "China 40% processing",
        ],
        "canada": {
            "platforms": ["CF-188 avionics capacitors", "Halifax-class electronic warfare suite", "CP-140 Aurora electronics", "F-35 avionics (on order)"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "All CAF avionics depend on tantalum capacitors. Conflict mineral sourcing (DRC/Rwanda) creates ethical and supply risks.",
        },
        "source": "USGS MCS 2025",
    },
    # 14. Vanadium
    {
        "name": "Vanadium",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 70),
            _mining("Russia", 21),
            _mining("South Africa", 8),
            _mining("Brazil", 5),
        ],
        "processing": [
            _processing("China", 73),
            _processing("Russia", 19),
            _processing("South Africa", 6),
        ],
        "components": [
            _component("HSLA armor steel"),
            _component("Ti-6Al-4V alloy"),
            _component("V redox batteries"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("NATO armored vehicles"),
            _platform("Submarine hull steel"),
            _platform("Landing gear"),
        ],
        "chokepoints": [_cp("Trans-Siberian rail"), _cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 5500,
        "risk_level": "critical",
        "risk_factors": [
            "China+Russia 91%",
            "Russia sanctions -21%",
            "Byproduct (inelastic)",
            "Ti-6Al-4V most important military aerospace alloy",
            "S.Africa only Western source",
        ],
        "canada": {
            "platforms": ["CF-188 Ti-6Al-4V structural alloy", "F-35 primary structural alloy (on order)", "LAV 6.0 armor steel", "Victoria-class hull steel"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Ti-6Al-4V is the most critical alloy in military aerospace. China+Russia control 91%. F-35 program is extremely exposed.",
        },
        "source": "USGS MCS 2025",
    },
    # 15. Molybdenum
    {
        "name": "Molybdenum",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 46),
            _mining("Peru", 14),
            _mining("Chile", 13),
            _mining("USA", 11),
            _mining("Mexico", 5),
        ],
        "processing": [
            _processing("China", 50),
            _processing("Chile", 15),
            _processing("USA", 12),
            _processing("Netherlands", 5),
        ],
        "components": [
            _component("Superalloy turbine blades"),
            _component("Armor steel"),
            _component("Reactor vessel steel"),
            _component("Missile heat shields"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("M1A2"),
            _platform("CVN-78"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Pacific shipping lanes"), _cp("Strait of Malacca")],
        "hhi": 2700,
        "risk_level": "high",
        "risk_factors": [
            "China 46% growing",
            "Peru/Chile instability",
            "Copper byproduct (inelastic)",
            "US 11% hedge",
        ],
        "canada": {
            "platforms": ["CF-188 F404 engine hot section", "Leopard 2A6M armor steel", "Halifax-class structural steel", "Victoria-class hull"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Required for all high-temperature engine components and armor-grade steel in CAF inventory.",
        },
        "source": "USGS MCS 2025",
    },
    # 16. Nickel
    {
        "name": "Nickel",
        "category": "Strategic Metal",
        "mining": [
            _mining("Indonesia", 55),
            _mining("Philippines", 9),
            _mining("Russia", 5),
            _mining("Canada", 4),
            _mining("New Caledonia", 3),
        ],
        "processing": [
            _processing("Indonesia", 43),
            _processing("China", 30),
            _processing("Japan", 7),
            _processing("Russia", 5),
            _processing("Finland", 3),
        ],
        "components": [
            _component("Inconel turbine blades"),
            _component("SS naval"),
            _component("HY-80 submarine hull"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("Virginia SSN"),
            _platform("DDG-51"),
            _platform("F/A-18"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Lombok Strait"), _cp("South China Sea")],
        "hhi": 3200,
        "risk_level": "high",
        "risk_factors": [
            "Indonesia 55% w/ Chinese control of 80% refining",
            "Russia sanctions",
            "Indonesia ore export ban",
            "New Caledonia collapse",
            "Jet engines+submarine hulls",
        ],
        "canada": {
            "platforms": ["CF-188 F404 engine Inconel", "Victoria-class HY-80 hull steel", "Halifax-class gas turbine engines", "CSC Type 26 hull", "F-35 F135 engine (on order)"],
            "import_pct": 50,
            "domestic": "4% of global mining — Sudbury ON, Thompson MB, Voisey's Bay NL (Vale, Glencore)",
            "strategic_note": "Canada is a significant nickel miner — strategic advantage. But Indonesian supply (55%) is under Chinese refining control, threatening global pricing.",
        },
        "source": "USGS MCS 2025",
    },
    # 17. Copper
    {
        "name": "Copper",
        "category": "Industrial Metal",
        "mining": [
            _mining("Chile", 23),
            _mining("DRC", 14),
            _mining("Peru", 11),
            _mining("China", 8),
            _mining("USA", 5),
        ],
        "processing": [
            _processing("China", 48),
            _processing("Chile", 8),
            _processing("Japan", 6),
            _processing("DRC", 5),
            _processing("USA", 4),
        ],
        "components": [
            _component("Brass cartridge cases"),
            _component("Shaped charges"),
            _component("Electrical wiring"),
            _component("Motor windings"),
        ],
        "platforms": [
            _platform("All guided munitions"),
            _platform("Naval vessels"),
            _platform("Rail guns"),
            _platform("EMALS"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 1200,
        "risk_level": "medium",
        "risk_factors": [
            "China 48% refining",
            "Peru/Chile political risk",
            "DRC instability",
            "Most used defense metal by weight",
            "Electrification demand",
        ],
        "canada": {
            "platforms": ["All CAF ammunition brass casings", "Halifax-class/CSC wiring and plumbing", "all platform electrical systems", "LAV 6.0 wiring"],
            "import_pct": 70,
            "domestic": "Minor mining (Highland Valley BC, Sudbury ON byproduct)",
            "strategic_note": "Copper is in every CAF platform and every round of ammunition. Growing electrification demand will compete with defence needs.",
        },
        "source": "USGS MCS 2025",
    },
    # 18. Aluminum
    {
        "name": "Aluminum",
        "category": "Industrial Metal",
        "mining": [
            _mining("Guinea", 31),
            _mining("Australia", 24),
            _mining("China", 22),
            _mining("Brazil", 8),
            _mining("India", 8),
        ],
        "processing": [
            _processing("China", 59),
            _processing("India", 6),
            _processing("Russia", 5),
            _processing("Canada", 5),
            _processing("UAE", 4),
        ],
        "components": [
            _component("Aircraft skins"),
            _component("Lightweight armor"),
            _component("Missile airframes"),
            _component("Vehicle hulls"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("C-17"),
            _platform("LAV 6.0"),
            _platform("Stryker"),
            _platform("RQ-4"),
        ],
        "chokepoints": [
            _cp("Strait of Malacca"),
            _cp("Suez Canal"),
            _cp("Bab-el-Mandeb"),
            _cp("Cape of Good Hope"),
        ],
        "hhi": 2000,
        "risk_level": "high",
        "risk_factors": [
            "China 59% smelting",
            "Guinea coup",
            "Russia sanctions",
            "Indonesia bauxite ban",
            "Military aircraft+armor",
        ],
        "canada": {
            "platforms": ["CF-188 structural skins", "CC-177 Globemaster fuselage", "LAV 6.0 hull", "Halifax-class superstructure", "TAPV hull", "CSC Type 26 superstructure"],
            "import_pct": 40,
            "domestic": "5% of global smelting — Rio Tinto Alcan (Kitimat BC, Jonquière QC, others)",
            "strategic_note": "Canada has significant aluminum smelting — one of the few minerals with domestic processing capacity. Strategic advantage for vehicle and aircraft production.",
        },
        "source": "USGS MCS 2025",
    },
    # 19. Zinc
    {
        "name": "Zinc",
        "category": "Industrial Metal",
        "mining": [
            _mining("China", 33),
            _mining("Peru", 12),
            _mining("Australia", 9),
            _mining("India", 7),
            _mining("USA", 6),
        ],
        "processing": [
            _processing("China", 48),
            _processing("South Korea", 7),
            _processing("India", 6),
            _processing("Japan", 5),
            _processing("Canada", 4),
        ],
        "components": [
            _component("Brass cartridge cases"),
            _component("Galvanized steel"),
            _component("Zinc-air batteries"),
            _component("Naval anodes"),
        ],
        "platforms": [
            _platform("Small arms ammo"),
            _platform("Artillery casings"),
            _platform("Naval hulls"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Strait of Malacca"), _cp("Cape of Good Hope")],
        "hhi": 1500,
        "risk_level": "medium",
        "risk_factors": [
            "China 48% refining",
            "Peru political risk",
            "Essential for brass ammo (no substitute)",
            "Declining grades",
        ],
        "canada": {
            "platforms": ["All CAF small arms brass casings (5.56mm, 7.62mm)", "artillery shell casings", "Halifax-class sacrificial anodes", "galvanized vehicle chassis"],
            "import_pct": 60,
            "domestic": "~4% global refining — Teck Trail BC, Hudbay Flin Flon MB",
            "strategic_note": "Canada has zinc refining capacity at Trail BC. But all brass ammunition requires zinc — no substitute exists for cartridge cases.",
        },
        "source": "USGS MCS 2025",
    },
    # 20. Tin
    {
        "name": "Tin",
        "category": "Industrial Metal",
        "mining": [
            _mining("China", 23),
            _mining("Indonesia", 23),
            _mining("Myanmar", 11),
            _mining("Peru", 9),
            _mining("DRC", 7),
        ],
        "processing": [
            _processing("China", 50),
            _processing("Indonesia", 18),
            _processing("Malaysia", 8),
            _processing("Thailand", 4),
            _processing("Belgium", 3),
        ],
        "components": [
            _component("Solder (all mil electronics)"),
            _component("Tin plate (ammo packaging)"),
            _component("Bearing alloys"),
            _component("Bronze naval"),
        ],
        "platforms": [
            _platform("All electronic weapons"),
            _platform("AN/APG-81 radar"),
            _platform("Submarine sonar"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("South China Sea"), _cp("Lombok Strait")],
        "hhi": 1500,
        "risk_level": "medium",
        "risk_factors": [
            "China+Indonesia 46%/68% refining",
            "Myanmar militia trade",
            "DRC conflict",
            "Tin-lead solder military standard",
        ],
        "canada": {
            "platforms": ["All CAF electronic systems circuit board solder", "CF-188 radar solder joints", "Halifax-class sonar electronics", "Victoria-class combat systems"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Every military electronic system uses tin-lead solder. RoHS exemption keeps military on leaded solder — China+Indonesia control 68% of refining.",
        },
        "source": "USGS MCS 2025",
    },
    # 21. Platinum Group Metals
    {
        "name": "Platinum Group Metals",
        "category": "Precious Metal",
        "mining": [
            _mining("South Africa", 72),
            _mining("Russia", 12),
            _mining("Zimbabwe", 8),
            _mining("Canada", 3),
            _mining("USA", 2),
        ],
        "processing": [
            _processing("South Africa", 65),
            _processing("Russia", 15),
            _processing("UK", 8, "Johnson Matthey"),
            _processing("Japan", 5),
        ],
        "components": [
            _component("Catalytic converters"),
            _component("Fuel cell membranes"),
            _component("Turbine coatings"),
            _component("Jet igniters"),
        ],
        "platforms": [
            _platform("All ground vehicles"),
            _platform("H2 UAVs"),
            _platform("F-35"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Northern Sea Route"), _cp("Suez Canal")],
        "hhi": 5600,
        "risk_level": "critical",
        "risk_factors": [
            "S.Africa+Russia=84%",
            "Eskom crisis",
            "Russia sanctions (Pd#1)",
            "Deeply concentrated no alternatives",
        ],
        "canada": {
            "platforms": ["All CAF ground vehicles (catalytic converters)", "Leopard 2A6M", "LAV 6.0", "TAPV", "future hydrogen fuel cell programs"],
            "import_pct": 70,
            "domestic": "3% of global mining — Sudbury ON (Vale, Glencore) as nickel byproduct",
            "strategic_note": "Canada has modest PGM production as nickel byproduct. South Africa+Russia control 84% of global supply. Critical for future hydrogen military applications.",
        },
        "source": "USGS MCS 2025",
    },
    # 22. Graphite
    {
        "name": "Graphite",
        "category": "Industrial Mineral",
        "mining": [
            _mining("China", 78),
            _mining("Mozambique", 5),
            _mining("Madagascar", 5),
            _mining("Brazil", 3),
            _mining("India", 2),
        ],
        "processing": [
            _processing("China", 90, "spherical/synthetic"),
            _processing("Japan", 3),
            _processing("India", 2),
        ],
        "components": [
            _component("Nuclear reactor moderators"),
            _component("Missile nose cones (C-C)"),
            _component("Rocket nozzle liners"),
            _component("Li-ion anodes"),
            _component("Stealth RAM"),
        ],
        "platforms": [
            _platform("Nuclear submarines"),
            _platform("Trident D5"),
            _platform("F-35"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Mozambique Channel"), _cp("South China Sea")],
        "hhi": 6200,
        "risk_level": "critical",
        "risk_factors": [
            "China 78%/90% extreme",
            "Dec 2023 export controls",
            "Mozambique insurgency",
            "Nuclear moderators+battery anodes",
        ],
        "canada": {
            "platforms": ["Victoria-class submarine batteries", "future Li-ion battery programs", "stealth coatings research", "nuclear-related programs"],
            "import_pct": 100,
            "domestic": "Emerging — Nouveau Monde Graphite (QC), Northern Graphite (ON) in development",
            "strategic_note": "Canada has graphite deposits under development in Quebec and Ontario. If brought online, could reduce dependency on China's 90% processing monopoly.",
        },
        "source": "USGS MCS 2025",
    },
    # 23. Fluorspar
    {
        "name": "Fluorspar",
        "category": "Industrial Mineral",
        "mining": [
            _mining("China", 56),
            _mining("Mexico", 10),
            _mining("Mongolia", 7),
            _mining("Vietnam", 4),
            _mining("South Africa", 3),
        ],
        "processing": [
            _processing("China", 60, "HF acid"),
            _processing("Mexico", 15),
            _processing("Mongolia", 5),
        ],
        "components": [
            _component("UF6 (uranium enrichment)"),
            _component("Fluoropolymer stealth coatings"),
            _component("Precision optics"),
        ],
        "platforms": [
            _platform("Nuclear subs/carriers"),
            _platform("F-35"),
            _platform("All nuclear weapons"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Gulf of Mexico"), _cp("Trans-Mongolian rail")],
        "hhi": 3500,
        "risk_level": "high",
        "risk_factors": [
            "China 56%/60%",
            "Essential for uranium enrichment (no substitute)",
            "US 100% import",
            "Mexico 63% of US imports (single corridor)",
            "Nuclear deterrent vulnerability",
        ],
        "canada": {
            "platforms": ["Nuclear submarine programs (if pursued)", "F-35 fluoropolymer coatings (on order)", "military optics"],
            "import_pct": 100,
            "domestic": "Canada Fluorspar Inc. (NL) — small scale, restarting production",
            "strategic_note": "Essential for uranium enrichment. Canada is a major uranium producer (Cameco) but depends on imported fluorspar for UF6 conversion.",
        },
        "source": "USGS MCS 2025",
    },
    # 24. Magnesium
    {
        "name": "Magnesium",
        "category": "Light Metal",
        "mining": [
            _mining("China", 85),
            _mining("Russia", 2),
            _mining("Israel", 2),
            _mining("Kazakhstan", 2),
            _mining("Turkey", 2),
        ],
        "processing": [
            _processing("China", 87),
            _processing("USA", 3),
            _processing("Israel", 3),
        ],
        "components": [
            _component("Lightweight aerospace alloys"),
            _component("Helicopter transmissions"),
            _component("Incendiary munitions"),
            _component("Military flares"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("AH-64 Apache"),
            _platform("LAV III"),
            _platform("Countermeasure flares"),
        ],
        "chokepoints": [_cp("South China Sea")],
        "hhi": 7300,
        "risk_level": "critical",
        "risk_factors": [
            "China 85% monopoly",
            "2021 curtailment caused 600% spike",
            "No Western capacity",
            "Lightest structural metal (no substitute)",
            "Essential for flares",
        ],
        "canada": {
            "platforms": ["CH-148 Cyclone transmission housing", "LAV III/6.0 alloy components", "all CAF countermeasure flares", "illumination rounds"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "China's 85% monopoly is an acute risk. 2021 curtailment caused 600% price spike. All CAF aircraft countermeasure flares require magnesium.",
        },
        "source": "USGS MCS 2025",
    },
    # 25. Silicon
    {
        "name": "Silicon",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 78),
            _mining("Brazil", 4),
            _mining("Norway", 3),
            _mining("France", 2),
            _mining("Russia", 1),
        ],
        "processing": [
            _processing("China", 80, "semiconductor-grade"),
            _processing("USA", 3),
            _processing("Germany", 3),
            _processing("Japan", 3),
        ],
        "components": [
            _component("Semiconductor chips"),
            _component("Al-Si alloys"),
            _component("SiC ceramic armor"),
        ],
        "platforms": [
            _platform("F-35"),
            _platform("JDAM"),
            _platform("All satellites"),
            _platform("M1A2"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Norwegian Sea")],
        "hhi": 6200,
        "risk_level": "critical",
        "risk_factors": [
            "China 78% monopoly",
            "Foundation of all semiconductor electronics",
            "Export controls could paralyze defense",
            "Norway/Brazil only Western sources",
        ],
        "canada": {
            "platforms": ["All CAF electronics (every platform)", "CF-188 avionics", "F-35 avionics (on order)", "RADARSAT satellites", "all guided munitions"],
            "import_pct": 95,
            "domestic": "Minor ferrosilicon production (QC)",
            "strategic_note": "Foundation of all semiconductor electronics. Every CAF platform depends on silicon chips. China controls 78% of metallurgical-grade production.",
        },
        "source": "USGS MCS 2025",
    },
    # 26. Strontium
    {
        "name": "Strontium",
        "category": "Industrial Mineral",
        "mining": [
            _mining("Spain", 30),
            _mining("Iran", 25),
            _mining("China", 20),
            _mining("Mexico", 15),
            _mining("Argentina", 3),
        ],
        "processing": [
            _processing("China", 45),
            _processing("Germany", 25),
            _processing("Mexico", 20),
        ],
        "components": [
            _component("Military signal flares (red)"),
            _component("Tracer ammo"),
            _component("Ceramic ferrite magnets"),
            _component("Sonar ceramics"),
        ],
        "platforms": [
            _platform("Aircraft flares"),
            _platform("Tracer rounds"),
            _platform("Sonobuoys"),
        ],
        "chokepoints": [_cp("Strait of Gibraltar"), _cp("Strait of Hormuz"), _cp("Gulf of Mexico")],
        "hhi": 2400,
        "risk_level": "high",
        "risk_factors": [
            "Iran 25% under sanctions",
            "China 20% export controls",
            "No US production since 2006",
            "No substitute for red flares",
        ],
        "canada": {
            "platforms": ["All CAF aircraft countermeasure flares (IR)", "tracer ammunition (5.56mm, 7.62mm)", "mortar illumination rounds", "sonobuoys"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "No domestic production since forever. Strontium nitrate is the only compound that produces red military flares — no substitute.",
        },
        "source": "USGS MCS 2025",
    },
    # 27. Zirconium
    {
        "name": "Zirconium",
        "category": "Nuclear Material",
        "mining": [
            _mining("Australia", 28),
            _mining("South Africa", 27),
            _mining("Mozambique", 10),
            _mining("Senegal", 8),
            _mining("China", 5),
        ],
        "processing": [
            _processing("China", 88, "unwrought"),
            _processing("France", 15, "nuclear-grade Framatome"),
            _processing("USA", 5, "Westinghouse"),
        ],
        "components": [
            _component("Nuclear fuel cladding"),
            _component("Naval reactor fuel assemblies"),
            _component("Ceramic armor"),
        ],
        "platforms": [
            _platform("Virginia SSN"),
            _platform("CVN-78 Ford"),
            _platform("Astute SSN"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca"), _cp("Indian Ocean")],
        "hhi": 1800,
        "risk_level": "high",
        "risk_factors": [
            "China 88% processing",
            "France/USA captive nuclear-grade",
            "Diversified mining but concentrated processing",
            "Critical for nuclear submarine fleet",
        ],
        "canada": {
            "platforms": ["Victoria-class submarine (potential nuclear upgrade)", "CSC Type 26 nuclear considerations", "ceramic body armor inserts"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Critical if Canada pursues nuclear-powered submarines (AUKUS-adjacent). China processes 88% of unwrought zirconium.",
        },
        "source": "USGS MCS 2025",
    },
    # 28. Hafnium
    {
        "name": "Hafnium",
        "category": "Nuclear Material",
        "mining": [
            _mining("Australia", 28),
            _mining("South Africa", 27),
            _mining("Mozambique", 10),
        ],
        "processing": [
            _processing("France", 49, "Framatome"),
            _processing("USA", 22),
            _processing("China", 15),
            _processing("Russia", 5),
        ],
        "components": [
            _component("Nuclear reactor control rods"),
            _component("Single-crystal turbine blades"),
            _component("Rocket nozzles"),
        ],
        "platforms": [
            _platform("Virginia SSN"),
            _platform("Suffren SSN"),
            _platform("F-35"),
        ],
        "chokepoints": [_cp("Suez Canal"), _cp("North Atlantic")],
        "hhi": 3200,
        "risk_level": "high",
        "risk_factors": [
            "Only ~90t/yr globally",
            "France Framatome 49% single facility",
            "65% used in nuclear control rods",
            "US maintains strategic reserves",
        ],
        "canada": {
            "platforms": ["Victoria-class (nuclear control rods if upgraded)", "F-35 F135 engine superalloy blades (on order)"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Only 90 tonnes produced globally per year. France controls 49%. Critical for any Canadian nuclear submarine ambitions.",
        },
        "source": "USGS MCS 2025",
    },
    # 29. Rhenium
    {
        "name": "Rhenium",
        "category": "Superalloy Metal",
        "mining": [
            _mining("Chile", 55),
            _mining("USA", 15),
            _mining("Poland", 10),
            _mining("Kazakhstan", 5),
            _mining("Armenia", 3),
        ],
        "processing": [
            _processing("Chile", 50),
            _processing("USA", 18),
            _processing("Germany", 10),
            _processing("Poland", 8),
            _processing("UK", 5),
        ],
        "components": [
            _component("Single-crystal superalloy turbine blades"),
            _component("Rocket thrust chambers"),
            _component("Catalytic reformers"),
        ],
        "platforms": [
            _platform("F-35 (F135)"),
            _platform("F-22 (F119)"),
            _platform("F/A-18 (F414)"),
            _platform("Eurofighter"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Drake Passage"), _cp("North Atlantic")],
        "hhi": 3400,
        "risk_level": "high",
        "risk_factors": [
            "Chile 55% concentration",
            "Copper-Mo byproduct (inelastic)",
            "Only 62kg/yr globally",
            "No substitute in single-crystal superalloys",
            "Every modern fighter depends on it",
        ],
        "canada": {
            "platforms": ["CF-188 F404 engine single-crystal turbine blades", "F-35 F135 engine (on order)", "CH-148 T700 engine"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "Every CAF fighter jet engine depends on rhenium in turbine blades. Global production only 62,000 kg/year — tiny market with no substitutes.",
        },
        "source": "USGS MCS 2025",
    },
    # 30. Indium
    {
        "name": "Indium",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 66),
            _mining("South Korea", 20),
            _mining("Japan", 7),
            _mining("Canada", 3),
            _mining("Belgium", 2),
        ],
        "processing": [
            _processing("China", 60),
            _processing("South Korea", 20),
            _processing("Japan", 10),
            _processing("Canada", 4),
            _processing("Belgium", 3),
        ],
        "components": [
            _component("ITO stealth canopy coatings"),
            _component("IR detectors (InSb)"),
            _component("Military displays"),
            _component("Windshield de-icing"),
        ],
        "platforms": [
            _platform("F-22"),
            _platform("F-35"),
            _platform("Sidewinder AIM-9X"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Korean Strait")],
        "hhi": 4900,
        "risk_level": "critical",
        "risk_factors": [
            "China 66% from zinc byproduct",
            "Inelastic supply",
            "ITO no substitute for stealth canopy",
            "InSb critical for IR seekers",
            "Only ~990t/yr globally",
        ],
        "canada": {
            "platforms": ["CF-188 cockpit displays", "F-35 stealth canopy coating (on order)", "LAV 6.0 displays", "targeting system IR detectors"],
            "import_pct": 100,
            "domestic": None,
            "strategic_note": "F-35 stealth canopy requires ITO coating — indium has no proven substitute. China controls 66% as zinc byproduct.",
        },
        "source": "USGS MCS 2025",
    },
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_all_minerals() -> list[dict]:
    """Return all 30 defence-critical minerals with supply chain data."""
    return MINERALS


def get_mineral_by_name(name: str) -> dict | None:
    """Case-insensitive lookup of a mineral by name.

    Returns the mineral dict or None if not found.
    """
    name_lower = name.lower()
    for mineral in MINERALS:
        if mineral["name"].lower() == name_lower:
            return mineral
    return None
