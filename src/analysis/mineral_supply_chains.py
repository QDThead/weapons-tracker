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
            "DRC dominance+instability",
            "Chinese control of DRC ops",
            "China 80% refining",
            "Conflict minerals",
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
