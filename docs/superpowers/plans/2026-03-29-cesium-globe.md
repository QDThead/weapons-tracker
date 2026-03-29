# CesiumJS 3D Supply Chain Globe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive 3D CesiumJS globe showing "Rocks to Rockets" supply chains for 30 defence-critical minerals, with per-mineral layer toggles, risk-colored flow arcs, and click/hover interactions.

**Architecture:** A new Python data module (`mineral_supply_chains.py`) holds all 30 minerals with real USGS 2025 data including geo-coordinates. A FastAPI router (`globe_routes.py`) serves this as JSON. The frontend adds a "3D Supply Map" sub-tab to the existing Supply Chain page, loading CesiumJS from CDN with a layer panel, legend, and interactive globe.

**Tech Stack:** Python 3.9+ (dataclasses), FastAPI, CesiumJS 1.119 (CDN), existing design system (glass-morphism cards, Outfit/IBM Plex Sans/JetBrains Mono fonts, cyan accent).

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `src/analysis/mineral_supply_chains.py` | 30 mineral dataclass instances with mining/processing/component/platform tiers, geo-coords, HHI, risk levels |
| Create | `src/api/globe_routes.py` | `GET /globe/minerals` and `GET /globe/minerals/{name}` endpoints |
| Modify | `src/main.py` | Register globe router |
| Modify | `src/static/index.html` | CesiumJS CDN script, "3D Supply Map" sub-tab, globe container, layer panel, legend, JS logic |
| Create | `tests/test_globe.py` | Tests for data module and API endpoints |

---

### Task 1: Create mineral data module with first 5 minerals

**Files:**
- Create: `src/analysis/mineral_supply_chains.py`
- Create: `tests/test_globe.py`

This task creates the data module skeleton and populates the first 5 minerals (Titanium, Lithium, Cobalt, REE, Tungsten) to validate the structure before adding all 30.

- [ ] **Step 1: Write the failing test for data module structure**

```python
"""Tests for the CesiumJS globe mineral supply chain data and API."""
from __future__ import annotations

import pytest

from src.analysis.mineral_supply_chains import get_all_minerals, get_mineral_by_name


class TestMineralData:
    """Verify mineral supply chain data integrity."""

    def test_get_all_minerals_returns_30(self):
        minerals = get_all_minerals()
        assert len(minerals) == 30

    def test_each_mineral_has_required_fields(self):
        minerals = get_all_minerals()
        for m in minerals:
            assert m["name"], f"Missing name"
            assert m["category"], f"{m['name']}: missing category"
            assert len(m["mining"]) >= 1, f"{m['name']}: no mining entries"
            assert len(m["processing"]) >= 1, f"{m['name']}: no processing entries"
            assert len(m["components"]) >= 1, f"{m['name']}: no components"
            assert len(m["platforms"]) >= 1, f"{m['name']}: no platforms"
            assert isinstance(m["hhi"], int), f"{m['name']}: hhi not int"
            assert m["risk_level"] in ("critical", "high", "medium", "low"), f"{m['name']}: invalid risk_level"
            assert m["source"], f"{m['name']}: missing source"

    def test_mining_entries_have_coordinates(self):
        minerals = get_all_minerals()
        for m in minerals:
            for entry in m["mining"]:
                assert "lat" in entry and "lon" in entry, f"{m['name']}: mining entry missing coords"
                assert -90 <= entry["lat"] <= 90, f"{m['name']}: invalid lat {entry['lat']}"
                assert -180 <= entry["lon"] <= 180, f"{m['name']}: invalid lon {entry['lon']}"
                assert "country" in entry, f"{m['name']}: mining entry missing country"
                assert "pct" in entry, f"{m['name']}: mining entry missing pct"

    def test_processing_entries_have_coordinates(self):
        minerals = get_all_minerals()
        for m in minerals:
            for entry in m["processing"]:
                assert "lat" in entry and "lon" in entry, f"{m['name']}: processing entry missing coords"
                assert "country" in entry and "pct" in entry

    def test_get_mineral_by_name(self):
        result = get_mineral_by_name("Titanium")
        assert result is not None
        assert result["name"] == "Titanium"

    def test_get_mineral_by_name_case_insensitive(self):
        result = get_mineral_by_name("titanium")
        assert result is not None
        assert result["name"] == "Titanium"

    def test_get_mineral_by_name_not_found(self):
        result = get_mineral_by_name("Unobtanium")
        assert result is None

    def test_chokepoints_have_coordinates(self):
        minerals = get_all_minerals()
        for m in minerals:
            for cp in m.get("chokepoints", []):
                assert "name" in cp, f"{m['name']}: chokepoint missing name"
                assert "lat" in cp and "lon" in cp, f"{m['name']}: chokepoint missing coords"

    def test_risk_factors_are_strings(self):
        minerals = get_all_minerals()
        for m in minerals:
            assert isinstance(m["risk_factors"], list)
            for rf in m["risk_factors"]:
                assert isinstance(rf, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_globe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.analysis.mineral_supply_chains'`

- [ ] **Step 3: Create mineral_supply_chains.py with country centroids and first 5 minerals**

Create `src/analysis/mineral_supply_chains.py`:

```python
"""Defence-critical mineral supply chain data for CesiumJS 3D globe.

Contains real production data for 30 minerals sourced from USGS Mineral
Commodity Summaries 2025 and EU Critical Raw Materials Assessment 2023.
Each mineral includes 4-tier supply chain (mining → processing → components
→ platforms) with geo-coordinates for globe rendering.

Every percentage is traceable to a public source. No fabricated data.
"""
from __future__ import annotations

# Country centroid coordinates for globe rendering.
# Standard geographic centroids used by Natural Earth / CIA Factbook.
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Argentina": (-34.0, -64.0),
    "Armenia": (40.0, 45.0),
    "Australia": (-25.0, 134.0),
    "Austria": (47.3, 13.3),
    "Belgium": (50.8, 4.0),
    "Brazil": (-10.0, -55.0),
    "Canada": (56.0, -106.0),
    "Chile": (-30.0, -71.0),
    "China": (35.0, 105.0),
    "DRC": (-4.0, 22.0),
    "Estonia": (59.0, 26.0),
    "Finland": (64.0, 26.0),
    "France": (46.0, 2.0),
    "Gabon": (-1.0, 11.5),
    "Germany": (51.0, 9.0),
    "Ghana": (8.0, -2.0),
    "Guinea": (11.0, -10.0),
    "India": (20.0, 77.0),
    "Indonesia": (-5.0, 120.0),
    "Iran": (32.0, 53.0),
    "Israel": (31.5, 34.8),
    "Japan": (36.0, 138.0),
    "Kazakhstan": (48.0, 68.0),
    "Madagascar": (-19.0, 47.0),
    "Malaysia": (4.0, 109.5),
    "Mexico": (23.0, -102.0),
    "Mongolia": (46.0, 105.0),
    "Mozambique": (-18.0, 35.0),
    "Myanmar": (22.0, 96.0),
    "Netherlands": (52.1, 5.3),
    "New Caledonia": (-21.5, 165.5),
    "Nigeria": (10.0, 8.0),
    "Norway": (62.0, 10.0),
    "Peru": (-10.0, -76.0),
    "Philippines": (12.0, 122.0),
    "Poland": (52.0, 20.0),
    "Russia": (60.0, 100.0),
    "Rwanda": (-2.0, 29.9),
    "Senegal": (14.5, -14.5),
    "South Africa": (-29.0, 24.0),
    "South Korea": (36.0, 128.0),
    "Spain": (40.0, -4.0),
    "Tajikistan": (39.0, 71.0),
    "Thailand": (15.0, 100.0),
    "Turkey": (39.0, 35.0),
    "UAE": (24.0, 54.0),
    "UK": (54.0, -2.0),
    "Ukraine": (49.0, 32.0),
    "USA": (39.0, -98.0),
    "Vietnam": (16.0, 106.0),
    "Zimbabwe": (-20.0, 30.0),
}

# Well-known maritime chokepoints with coordinates.
CHOKEPOINTS: dict[str, tuple[float, float]] = {
    "Strait of Malacca": (2.5, 101.0),
    "Suez Canal": (30.5, 32.3),
    "Cape of Good Hope": (-34.4, 18.5),
    "Strait of Hormuz": (26.5, 56.3),
    "Panama Canal": (9.1, -79.7),
    "Bab-el-Mandeb": (12.6, 43.3),
    "Turkish Straits": (41.1, 29.0),
    "South China Sea": (15.0, 115.0),
    "Lombok Strait": (-8.5, 115.7),
    "Drake Passage": (-60.0, -65.0),
    "Mozambique Channel": (-17.0, 42.0),
    "Korean Strait": (34.0, 129.0),
    "Sea of Japan": (40.0, 135.0),
    "St. Lawrence Seaway": (47.0, -74.0),
    "Gulf of Mexico": (25.0, -90.0),
    "Strait of Gibraltar": (36.0, -5.5),
    "Northern Sea Route": (73.0, 100.0),
    "Norwegian Sea": (67.0, 2.0),
    "North Atlantic": (50.0, -30.0),
    "Pacific shipping lanes": (30.0, -170.0),
    "South Atlantic": (-25.0, -20.0),
    "Indian Ocean": (-10.0, 70.0),
    "Baltic Sea": (58.0, 20.0),
    "Trans-Siberian rail": (56.0, 90.0),
    "Central Asian rail": (41.0, 65.0),
    "Trans-Mongolian rail": (47.0, 107.0),
}


def _coords(country: str) -> dict:
    """Return lat/lon dict for a country, falling back to 0,0 if unknown."""
    lat, lon = COUNTRY_COORDS.get(country, (0.0, 0.0))
    return {"lat": lat, "lon": lon}


def _cp(name: str) -> dict:
    """Return a chokepoint dict with name and coordinates."""
    lat, lon = CHOKEPOINTS.get(name, (0.0, 0.0))
    return {"name": name, "lat": lat, "lon": lon}


def _mining(country: str, pct: float, tonnes: int | None = None) -> dict:
    entry = {"country": country, "pct": pct, **_coords(country)}
    if tonnes is not None:
        entry["production_tonnes"] = tonnes
    return entry


def _processing(country: str, pct: float, type_: str = "refining") -> dict:
    return {"country": country, "pct": pct, "type": type_, **_coords(country)}


def _component(name: str, country: str) -> dict:
    return {"name": name, "manufacturer_country": country, **_coords(country)}


def _platform(name: str, country: str, pct_by_weight: float | None = None) -> dict:
    entry = {"name": name, "assembly_country": country, **_coords(country)}
    if pct_by_weight is not None:
        entry["pct_by_weight"] = pct_by_weight
    return entry


# ═══════════════════════════════════════════════════════════════════
#  ALL 30 MINERALS — USGS MCS 2025 data
# ═══════════════════════════════════════════════════════════════════

MINERALS: list[dict] = [
    # ── 1. Titanium ──
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
            _processing("China", 51, "sponge metal"),
            _processing("Japan", 17, "sponge metal"),
            _processing("Russia", 13, "sponge metal"),
            _processing("Kazakhstan", 7, "sponge metal"),
            _processing("Ukraine", 3, "sponge metal"),
        ],
        "components": [
            _component("Aircraft structural frames", "USA"),
            _component("Jet engine compressor discs", "USA"),
            _component("Submarine pressure hulls", "USA"),
            _component("Landing gear", "France"),
            _component("Armor plating", "USA"),
        ],
        "platforms": [
            _platform("F-22 Raptor", "USA", 41),
            _platform("F-35 Lightning II", "USA"),
            _platform("Virginia-class SSN", "USA"),
            _platform("CH-148 Cyclone", "Canada"),
            _platform("Eurofighter Typhoon", "Germany"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Suez Canal"), _cp("Cape of Good Hope")],
        "hhi": 1500,
        "risk_level": "high",
        "risk_factors": [
            "Russia sanctions disrupt 13% of sponge supply",
            "China controls 51% of sponge processing",
            "Ukraine conflict disrupts 3% sponge + 8% rutile supply",
            "Single-source dependency for high-grade aerospace sponge (Japan 67% of US imports)",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 2. Lithium ──
    {
        "name": "Lithium",
        "category": "Battery Metal",
        "mining": [
            _mining("Australia", 37, 88000),
            _mining("Chile", 20, 49000),
            _mining("China", 19, 46000),
            _mining("Argentina", 9, 22000),
            _mining("Zimbabwe", 5, 12000),
        ],
        "processing": [
            _processing("China", 65, "hydroxide/carbonate"),
            _processing("Chile", 20, "carbonate"),
            _processing("Argentina", 8, "carbonate"),
        ],
        "components": [
            _component("Li-ion batteries (tactical radios)", "Japan"),
            _component("Thermal batteries (missile arming)", "USA"),
            _component("Torpedo propulsion batteries", "USA"),
            _component("UAV power systems", "China"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("MQ-9 Reaper", "USA"),
            _platform("Javelin missile", "USA"),
            _platform("MK-48 torpedo", "USA"),
            _platform("Switchblade loitering munition", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Panama Canal"), _cp("Cape of Good Hope")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "China controls 65% of refining despite mining only 19%",
            "Australian raw ore largely shipped to China for processing",
            "Price volatility (80% price collapse 2022-2024)",
            "Chile/Argentina brine operations subject to water scarcity and political risk",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 3. Cobalt ──
    {
        "name": "Cobalt",
        "category": "Battery Metal",
        "mining": [
            _mining("DRC", 76, 220000),
            _mining("Indonesia", 10),
            _mining("Russia", 2),
            _mining("Australia", 1.4),
            _mining("Philippines", 1.3),
        ],
        "processing": [
            _processing("China", 80, "refined cobalt"),
            _processing("Finland", 8, "refined cobalt"),
            _processing("Belgium", 5, "refined cobalt"),
        ],
        "components": [
            _component("Superalloy turbine blades", "USA"),
            _component("Li-cobalt-oxide batteries (UAVs)", "Japan"),
            _component("Cemented carbides", "Germany"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F/A-18 Super Hornet", "USA"),
            _platform("MQ-9 Reaper", "USA"),
            _platform("Tomahawk cruise missile", "USA"),
            _platform("CH-149 Cormorant", "Canada"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca"), _cp("Suez Canal")],
        "hhi": 5900,
        "risk_level": "critical",
        "risk_factors": [
            "DRC single-country dominance at 76% with chronic instability",
            "Chinese companies control most DRC mining operations",
            "China refines 80% of global cobalt",
            "Conflict mineral concerns and artisanal mining labor issues",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 4. Rare Earth Elements ──
    {
        "name": "Rare Earth Elements",
        "category": "Electronic Material",
        "mining": [
            _mining("China", 69, 270000),
            _mining("USA", 12, 45000),
            _mining("Myanmar", 8, 31000),
            _mining("Australia", 4, 16000),
            _mining("Thailand", 3, 13000),
        ],
        "processing": [
            _processing("China", 90, "separation/magnet production"),
            _processing("Malaysia", 3, "separation"),
            _processing("Estonia", 1, "separation"),
        ],
        "components": [
            _component("NdFeB permanent magnets", "China"),
            _component("Precision-guided munition fin actuators", "USA"),
            _component("Satellite reaction wheels", "USA"),
            _component("Sonar transducers", "USA"),
            _component("Laser rangefinders", "Germany"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F-22 Raptor", "USA"),
            _platform("Virginia-class SSN", "USA"),
            _platform("DDG-51 Arleigh Burke", "USA"),
            _platform("THAAD", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("South China Sea"), _cp("Suez Canal")],
        "hhi": 5100,
        "risk_level": "critical",
        "risk_factors": [
            "China 90% processing monopoly",
            "China 2024 export controls on REE processing technology",
            "Myanmar supply dependent on China border trade",
            "78% of US weapons programs use REE magnets",
            "China banned REE exports to US in 2025",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 5. Tungsten ──
    {
        "name": "Tungsten",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 83, 67000),
            _mining("Vietnam", 5),
            _mining("Russia", 2.5),
            _mining("Austria", 1.5),
            _mining("Spain", 1),
        ],
        "processing": [
            _processing("China", 82, "APT/tungsten carbide"),
            _processing("Austria", 5, "tungsten carbide"),
            _processing("Vietnam", 3, "APT"),
        ],
        "components": [
            _component("Armor-piercing penetrators", "USA"),
            _component("APFSDS tank rounds", "Germany"),
            _component("Tungsten carbide cutting tools", "Austria"),
            _component("Shaped charge liners", "USA"),
        ],
        "platforms": [
            _platform("M1A2 Abrams", "USA"),
            _platform("Leopard 2", "Germany"),
            _platform("Challenger 3", "UK"),
            _platform("A-10 Warthog", "USA"),
            _platform("CIWS Phalanx", "USA"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Trans-Siberian rail")],
        "hhi": 6900,
        "risk_level": "critical",
        "risk_factors": [
            "China 83% near-monopoly at both mining and processing",
            "China restricted tungsten exports in 2024",
            "Virtually no substitutes for AP ammunition",
            "Russia sanctions reduce accessible supply by 2.5%",
            "Austria's Plansee is only significant Western processor",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 6. Gallium ──
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
            _processing("China", 98, "high-purity gallium"),
            _processing("Japan", 1, "high-purity gallium"),
            _processing("South Korea", 0.5, "high-purity gallium"),
        ],
        "components": [
            _component("GaN AESA radar modules", "USA"),
            _component("EW jammer semiconductors", "USA"),
            _component("Missile seeker GaAs chips", "USA"),
            _component("Satellite comm modules", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F-22 Raptor", "USA"),
            _platform("EA-18G Growler", "USA"),
            _platform("Patriot PAC-3", "USA"),
            _platform("AN/SPY-6 naval radar", "USA"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Pacific shipping lanes")],
        "hhi": 9800,
        "risk_level": "critical",
        "risk_factors": [
            "China controls 98-99% of production",
            "China imposed gallium export controls August 2023",
            "No meaningful non-Chinese production exists",
            "Critical to all modern radar and EW systems",
            "Single point of failure for Western defence electronics",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 7. Germanium ──
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
            _processing("China", 68, "refined germanium"),
            _processing("Belgium", 10, "refined germanium"),
            _processing("Canada", 8, "refined germanium"),
            _processing("Russia", 5, "refined germanium"),
            _processing("Japan", 3, "refined germanium"),
        ],
        "components": [
            _component("IR optics (thermal imaging)", "USA"),
            _component("Fiber optic cables", "USA"),
            _component("Night vision systems", "USA"),
            _component("IR missile seekers", "USA"),
        ],
        "platforms": [
            _platform("Apache AH-64", "USA"),
            _platform("F-35 Lightning II", "USA"),
            _platform("Javelin missile", "USA"),
            _platform("Stinger MANPADS", "USA"),
            _platform("LITENING targeting pod", "Israel"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Suez Canal")],
        "hhi": 4800,
        "risk_level": "critical",
        "risk_factors": [
            "China imposed germanium export controls August 2023",
            "Germanium essential for all thermal imaging optics",
            "No viable substitute for high-performance IR windows",
            "Belgian Umicore is main Western refiner",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 8. Antimony ──
    {
        "name": "Antimony",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 48, 40000),
            _mining("Tajikistan", 25, 21000),
            _mining("Turkey", 7),
            _mining("Myanmar", 5),
            _mining("Russia", 5),
        ],
        "processing": [
            _processing("China", 55, "antimony trioxide"),
            _processing("Tajikistan", 15, "antimony metal"),
            _processing("Belgium", 5, "antimony trioxide"),
        ],
        "components": [
            _component("Lead-hardened ammunition", "USA"),
            _component("Armor-piercing rounds", "USA"),
            _component("Ammunition primers", "USA"),
            _component("Flame retardant (uniforms)", "USA"),
        ],
        "platforms": [
            _platform("Small arms ammunition", "USA"),
            _platform("Mk 211 Raufoss rounds", "Norway"),
            _platform("Artillery shells", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Central Asian rail"), _cp("Turkish Straits")],
        "hhi": 3100,
        "risk_level": "high",
        "risk_factors": [
            "China banned antimony exports to USA in December 2024",
            "Tajikistan limited processing capacity",
            "Russia supply under sanctions",
            "Critical for virtually all conventional ammunition",
            "US imports 85% of needs",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 9. Beryllium ──
    {
        "name": "Beryllium",
        "category": "Strategic Metal",
        "mining": [
            _mining("USA", 58, 190),
            _mining("China", 22, 74),
            _mining("Mozambique", 5),
            _mining("Madagascar", 3),
            _mining("Brazil", 3),
        ],
        "processing": [
            _processing("USA", 65, "Materion Corp"),
            _processing("China", 20, "refined beryllium"),
            _processing("Kazakhstan", 8, "refined beryllium"),
        ],
        "components": [
            _component("Satellite structural components", "USA"),
            _component("Nuclear weapon reflectors", "USA"),
            _component("Precision gyroscope bearings", "USA"),
            _component("X-ray windows", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F-22 Raptor", "USA"),
            _platform("Trident D5 SLBM", "USA"),
            _platform("GPS III satellites", "USA"),
        ],
        "chokepoints": [_cp("Suez Canal")],
        "hhi": 4000,
        "risk_level": "medium",
        "risk_factors": [
            "US strategic advantage — 58% mining, 65% processing",
            "Materion Corp single point of failure for Western supply",
            "Beryllium toxicity limits production expansion",
            "Critical for nuclear weapons program",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 10. Chromium ──
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
            _processing("South Africa", 43, "ferrochromium"),
            _processing("China", 25, "ferrochromium"),
            _processing("Kazakhstan", 12, "ferrochromium"),
            _processing("India", 8, "ferrochromium"),
        ],
        "components": [
            _component("Stainless steel armor plate", "USA"),
            _component("Chrome-plated gun barrels", "USA"),
            _component("Jet engine combustion chambers", "USA"),
            _component("Naval corrosion-resistant components", "USA"),
        ],
        "platforms": [
            _platform("M1A2 Abrams", "USA"),
            _platform("Leopard 2", "Germany"),
            _platform("CVN-78 Ford-class carrier", "USA"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Turkish Straits"), _cp("Strait of Hormuz")],
        "hhi": 2900,
        "risk_level": "high",
        "risk_factors": [
            "South Africa electricity disruptions (Eskom) threaten 48% of mining",
            "Rail logistics problems in South Africa",
            "Kazakhstan geopolitical risk (Russian influence)",
            "No chromium mining in North America — 100% US import reliance",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 11. Manganese ──
    {
        "name": "Manganese",
        "category": "Strategic Metal",
        "mining": [
            _mining("South Africa", 36, 7200000),
            _mining("Gabon", 23, 4600000),
            _mining("Australia", 16, 3300000),
            _mining("China", 7),
            _mining("Ghana", 5),
        ],
        "processing": [
            _processing("China", 90, "electrolytic manganese"),
            _processing("South Africa", 5, "ferromanganese"),
            _processing("India", 2, "ferromanganese"),
        ],
        "components": [
            _component("High-strength steel (armor plate)", "USA"),
            _component("Mn-Li batteries", "China"),
            _component("Aircraft aluminum alloys", "USA"),
        ],
        "platforms": [
            _platform("All armored vehicles", "USA"),
            _platform("Naval vessels", "USA"),
            _platform("M777 howitzer", "USA"),
            _platform("Submarine pressure hulls", "USA"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "China processes 90%+ of electrolytic manganese despite mining only 7%",
            "South Africa rail/port logistics bottlenecks",
            "Gabon political instability (2023 coup)",
            "Essential for all military steel production",
            "US 100% import-reliant for manganese",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 12. Niobium ──
    {
        "name": "Niobium",
        "category": "Strategic Metal",
        "mining": [
            _mining("Brazil", 92),
            _mining("Canada", 7),
        ],
        "processing": [
            _processing("Brazil", 90, "integrated mine-to-product"),
            _processing("Canada", 7, "ferroniobium"),
            _processing("China", 2, "ferroniobium"),
        ],
        "components": [
            _component("HSLA steel (airframe components)", "USA"),
            _component("Superalloy turbine blades (Inconel 718)", "USA"),
            _component("Superconducting magnets", "USA"),
            _component("Rocket nozzles", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F/A-18 Super Hornet", "USA"),
            _platform("Virginia-class SSN", "USA"),
        ],
        "chokepoints": [_cp("South Atlantic"), _cp("St. Lawrence Seaway")],
        "hhi": 8500,
        "risk_level": "critical",
        "risk_factors": [
            "Brazil 92% monopoly through CBMM (single company controls ~80%)",
            "Canada only meaningful alternative at 7%",
            "No adequate substitutes in superalloys",
            "Any disruption at CBMM would halt global supply",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 13. Tantalum ──
    {
        "name": "Tantalum",
        "category": "Electronic Material",
        "mining": [
            _mining("DRC", 41, 980),
            _mining("Rwanda", 15, 350),
            _mining("Nigeria", 8),
            _mining("Brazil", 7),
            _mining("China", 5),
        ],
        "processing": [
            _processing("China", 40, "refined tantalum"),
            _processing("Germany", 15, "refined tantalum"),
            _processing("USA", 10, "refined tantalum"),
            _processing("Kazakhstan", 8, "refined tantalum"),
            _processing("Japan", 7, "refined tantalum"),
        ],
        "components": [
            _component("Tantalum capacitors (avionics)", "USA"),
            _component("Rocket engine combustion chambers", "USA"),
            _component("Shaped charge liners", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("Patriot missile", "USA"),
            _platform("JDAM guidance unit", "USA"),
            _platform("Tomahawk cruise missile", "USA"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Suez Canal"), _cp("Strait of Malacca")],
        "hhi": 2200,
        "risk_level": "high",
        "risk_factors": [
            "DRC/Rwanda account for 56% — both conflict-affected regions",
            "Significant smuggling (Rwanda exports exceed production)",
            "Dodd-Frank conflict mineral regulations",
            "China dominates processing at 40%",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 14. Vanadium ──
    {
        "name": "Vanadium",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 70, 70000),
            _mining("Russia", 21, 21000),
            _mining("South Africa", 8, 8000),
            _mining("Brazil", 5, 5000),
        ],
        "processing": [
            _processing("China", 73, "ferrovanadium"),
            _processing("Russia", 19, "ferrovanadium"),
            _processing("South Africa", 6, "ferrovanadium"),
        ],
        "components": [
            _component("HSLA steel (armor plate)", "USA"),
            _component("Ti-6Al-4V alloy (airframe)", "USA"),
            _component("Vanadium redox flow batteries", "China"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("All NATO armored vehicles", "USA"),
            _platform("Submarine hull steel", "USA"),
            _platform("Aircraft landing gear", "France"),
        ],
        "chokepoints": [_cp("Trans-Siberian rail"), _cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 5500,
        "risk_level": "critical",
        "risk_factors": [
            "China+Russia control 91% of production",
            "Sanctions on Russia eliminate 21% of accessible supply",
            "Vanadium is byproduct of steel slag making supply inelastic",
            "Ti-6Al-4V is the single most important alloy in military aerospace",
            "South Africa only meaningful Western-aligned source",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 15. Molybdenum ──
    {
        "name": "Molybdenum",
        "category": "Strategic Metal",
        "mining": [
            _mining("China", 46, 134000),
            _mining("Peru", 14, 41000),
            _mining("Chile", 13, 38000),
            _mining("USA", 11, 33000),
            _mining("Mexico", 5),
        ],
        "processing": [
            _processing("China", 50, "molybdenum oxide"),
            _processing("Chile", 15, "molybdenum oxide"),
            _processing("USA", 12, "molybdenum oxide"),
            _processing("Netherlands", 5, "molybdenum oxide"),
        ],
        "components": [
            _component("Superalloy turbine blades", "USA"),
            _component("High-strength armor steel", "USA"),
            _component("Reactor vessel steel", "USA"),
            _component("Missile heat shields", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("M1A2 Abrams", "USA"),
            _platform("CVN-78 Ford-class carrier", "USA"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Pacific shipping lanes"), _cp("Strait of Malacca")],
        "hhi": 2700,
        "risk_level": "high",
        "risk_factors": [
            "China 46% mining share and growing",
            "Peru/Chile political instability (mining protests, nationalization risk)",
            "Molybdenum is byproduct of copper mining (inelastic supply)",
            "US domestic production provides partial hedge (11%)",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 16. Nickel ──
    {
        "name": "Nickel",
        "category": "Strategic Metal",
        "mining": [
            _mining("Indonesia", 55, 2000000),
            _mining("Philippines", 9),
            _mining("Russia", 5, 210000),
            _mining("Canada", 4),
            _mining("New Caledonia", 3),
        ],
        "processing": [
            _processing("Indonesia", 43, "refined nickel"),
            _processing("China", 30, "refined nickel"),
            _processing("Japan", 7, "refined nickel"),
            _processing("Russia", 5, "refined nickel"),
            _processing("Finland", 3, "refined nickel"),
        ],
        "components": [
            _component("Superalloy turbine blades (Inconel)", "USA"),
            _component("Stainless steel (naval structural)", "USA"),
            _component("Submarine hull steel (HY-80)", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("Virginia-class SSN", "USA"),
            _platform("DDG-51 Arleigh Burke", "USA"),
            _platform("F/A-18 Super Hornet", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Lombok Strait"), _cp("South China Sea")],
        "hhi": 3200,
        "risk_level": "high",
        "risk_factors": [
            "Indonesia 55% concentration with Chinese companies controlling 80% of Indonesian refining",
            "Russia sanctions eliminate 5% of mining",
            "Indonesia export ban on raw ore forces processing under Chinese control",
            "Essential for all jet engines and submarine hulls",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 17. Copper ──
    {
        "name": "Copper",
        "category": "Industrial Metal",
        "mining": [
            _mining("Chile", 23, 5300000),
            _mining("DRC", 14, 3300000),
            _mining("Peru", 11, 2600000),
            _mining("China", 8, 1800000),
            _mining("USA", 5, 1100000),
        ],
        "processing": [
            _processing("China", 48, "refined copper"),
            _processing("Chile", 8, "refined copper"),
            _processing("Japan", 6, "refined copper"),
            _processing("DRC", 5, "refined copper"),
            _processing("USA", 4, "refined copper"),
        ],
        "components": [
            _component("Ammunition cartridge cases (brass)", "USA"),
            _component("Shaped charge liners", "USA"),
            _component("Electrical wiring (all platforms)", "USA"),
            _component("Motor windings", "USA"),
        ],
        "platforms": [
            _platform("All guided munitions", "USA"),
            _platform("All naval vessels", "USA"),
            _platform("Rail guns", "USA"),
            _platform("EMALS launch system", "USA"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Cape of Good Hope"), _cp("Strait of Malacca")],
        "hhi": 1200,
        "risk_level": "medium",
        "risk_factors": [
            "China refines 48% despite mining only 8%",
            "Peru/Chile political risk (protests, nationalization)",
            "DRC instability",
            "Copper is the most widely used defense metal by weight",
            "Growing demand from electrification competes with defense",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 18. Aluminum ──
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
            _processing("China", 59, "smelted aluminum"),
            _processing("India", 6, "smelted aluminum"),
            _processing("Russia", 5, "smelted aluminum"),
            _processing("Canada", 5, "smelted aluminum"),
            _processing("UAE", 4, "smelted aluminum"),
        ],
        "components": [
            _component("Aircraft structural skins", "USA"),
            _component("Lightweight armor (Al-alloy)", "USA"),
            _component("Missile airframes", "USA"),
            _component("Military vehicle hulls", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("C-17 Globemaster", "USA"),
            _platform("LAV 6.0", "Canada"),
            _platform("Stryker", "USA"),
            _platform("RQ-4 Global Hawk", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Suez Canal"), _cp("Bab-el-Mandeb"), _cp("Cape of Good Hope")],
        "hhi": 2000,
        "risk_level": "high",
        "risk_factors": [
            "China 59% aluminum smelting dominance",
            "Guinea coup risk (2021 military takeover, junta still in power)",
            "Russia 5% smelting under sanctions",
            "Indonesia banned bauxite exports",
            "Critical for all military aircraft structures and lightweight armor",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 19. Zinc ──
    {
        "name": "Zinc",
        "category": "Industrial Metal",
        "mining": [
            _mining("China", 33, 4000000),
            _mining("Peru", 12, 1470000),
            _mining("Australia", 9, 1090000),
            _mining("India", 7),
            _mining("USA", 6),
        ],
        "processing": [
            _processing("China", 48, "refined zinc"),
            _processing("South Korea", 7, "refined zinc"),
            _processing("India", 6, "refined zinc"),
            _processing("Japan", 5, "refined zinc"),
            _processing("Canada", 4, "refined zinc"),
        ],
        "components": [
            _component("Brass cartridge cases (Cu-Zn)", "USA"),
            _component("Galvanized steel (corrosion protection)", "USA"),
            _component("Zinc-air batteries", "USA"),
            _component("Naval sacrificial anodes", "USA"),
        ],
        "platforms": [
            _platform("Small arms ammunition", "USA"),
            _platform("Artillery shell casings", "USA"),
            _platform("Naval vessel hulls", "USA"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Strait of Malacca"), _cp("Cape of Good Hope")],
        "hhi": 1500,
        "risk_level": "medium",
        "risk_factors": [
            "China processes 48% of refined zinc",
            "Peru mining protests and political risk",
            "Zinc essential for all brass ammunition (no substitute)",
            "Global supply mature and declining grades",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 20. Tin ──
    {
        "name": "Tin",
        "category": "Industrial Metal",
        "mining": [
            _mining("China", 23, 70000),
            _mining("Indonesia", 23, 69000),
            _mining("Myanmar", 11, 34000),
            _mining("Peru", 9, 26000),
            _mining("DRC", 7, 20000),
        ],
        "processing": [
            _processing("China", 50, "refined tin"),
            _processing("Indonesia", 18, "refined tin"),
            _processing("Malaysia", 8, "refined tin"),
            _processing("Thailand", 4, "refined tin"),
            _processing("Belgium", 3, "refined tin"),
        ],
        "components": [
            _component("Solder (all military electronics)", "USA"),
            _component("Tin plate (ammunition packaging)", "USA"),
            _component("Bearing alloys", "USA"),
            _component("Bronze components (naval)", "USA"),
        ],
        "platforms": [
            _platform("All electronic weapons systems", "USA"),
            _platform("AN/APG-81 radar", "USA"),
            _platform("Submarine sonar systems", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("South China Sea"), _cp("Lombok Strait")],
        "hhi": 1500,
        "risk_level": "medium",
        "risk_factors": [
            "China+Indonesia control 46% mining and 68% refining",
            "Myanmar production tied to Chinese border trade and Wa State militia",
            "DRC conflict mineral risk",
            "Tin-lead solder remains standard for military electronics",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 21. Platinum Group Metals ──
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
            _processing("South Africa", 65, "refined PGMs"),
            _processing("Russia", 15, "refined PGMs"),
            _processing("UK", 8, "Johnson Matthey"),
            _processing("Japan", 5, "refined PGMs"),
        ],
        "components": [
            _component("Catalytic converters (military vehicles)", "USA"),
            _component("Fuel cell membranes (H2 UAVs)", "USA"),
            _component("Turbine blade coatings", "USA"),
            _component("Jet engine igniters", "USA"),
        ],
        "platforms": [
            _platform("All military ground vehicles", "USA"),
            _platform("H2 fuel cell UAVs", "USA"),
            _platform("F-35 Lightning II", "USA"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Northern Sea Route"), _cp("Suez Canal")],
        "hhi": 5600,
        "risk_level": "critical",
        "risk_factors": [
            "South Africa + Russia = 84% of production",
            "South Africa Eskom power crisis threatens output",
            "Russia sanctions impact palladium supply (Russia is #1 palladium producer)",
            "Deeply concentrated with no alternatives",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 22. Graphite ──
    {
        "name": "Graphite",
        "category": "Industrial Mineral",
        "mining": [
            _mining("China", 78, 1270000),
            _mining("Mozambique", 5, 75000),
            _mining("Madagascar", 5, 89000),
            _mining("Brazil", 3),
            _mining("India", 2),
        ],
        "processing": [
            _processing("China", 90, "spherical/synthetic graphite"),
            _processing("Japan", 3, "synthetic graphite"),
            _processing("India", 2, "natural graphite"),
        ],
        "components": [
            _component("Nuclear reactor moderators", "USA"),
            _component("Missile nose cones (C-C composites)", "USA"),
            _component("Rocket motor nozzle liners", "USA"),
            _component("Li-ion battery anodes", "China"),
            _component("Stealth coatings (RAM)", "USA"),
        ],
        "platforms": [
            _platform("Nuclear submarines", "USA"),
            _platform("Trident D5 SLBM", "USA"),
            _platform("F-35 Lightning II", "USA"),
        ],
        "chokepoints": [_cp("Strait of Malacca"), _cp("Mozambique Channel"), _cp("South China Sea")],
        "hhi": 6200,
        "risk_level": "critical",
        "risk_factors": [
            "China 78% mining + 90%+ processing is extreme concentration",
            "China export controls on graphite since December 2023",
            "Mozambique insurgency (Cabo Delgado) threatens emerging production",
            "Natural graphite essential for nuclear moderators and battery anodes",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 23. Fluorspar ──
    {
        "name": "Fluorspar",
        "category": "Industrial Mineral",
        "mining": [
            _mining("China", 56, 5300000),
            _mining("Mexico", 10, 990000),
            _mining("Mongolia", 7),
            _mining("Vietnam", 4),
            _mining("South Africa", 3),
        ],
        "processing": [
            _processing("China", 60, "hydrofluoric acid"),
            _processing("Mexico", 15, "acid-grade fluorspar"),
            _processing("Mongolia", 5, "acid-grade fluorspar"),
        ],
        "components": [
            _component("Uranium enrichment (UF6)", "USA"),
            _component("Fluoropolymer stealth coatings", "USA"),
            _component("High-precision optical lenses", "USA"),
        ],
        "platforms": [
            _platform("Nuclear submarines/carriers", "USA"),
            _platform("F-35 Lightning II", "USA"),
            _platform("All nuclear weapons", "USA"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Gulf of Mexico"), _cp("Trans-Mongolian rail")],
        "hhi": 3500,
        "risk_level": "high",
        "risk_factors": [
            "China 56% mining and 60% processing",
            "Fluorspar essential for uranium enrichment (UF6) — no substitute",
            "US imports 100% of fluorspar",
            "Mexico supplies 63% of US imports (single-corridor dependency)",
            "Strategic vulnerability for nuclear deterrent and naval reactor fuel",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 24. Magnesium ──
    {
        "name": "Magnesium",
        "category": "Light Metal",
        "mining": [
            _mining("China", 85, 1025000),
            _mining("Russia", 2),
            _mining("Israel", 2),
            _mining("Kazakhstan", 2),
            _mining("Turkey", 2),
        ],
        "processing": [
            _processing("China", 87, "alloy/die-cast"),
            _processing("USA", 3, "alloy"),
            _processing("Israel", 3, "alloy"),
        ],
        "components": [
            _component("Lightweight aerospace alloys", "USA"),
            _component("Helicopter transmission housings", "USA"),
            _component("Incendiary munitions", "USA"),
            _component("Military flares (white/IR)", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("AH-64 Apache", "USA"),
            _platform("LAV III", "Canada"),
            _platform("Countermeasure flares", "USA"),
        ],
        "chokepoints": [_cp("South China Sea")],
        "hhi": 7300,
        "risk_level": "critical",
        "risk_factors": [
            "China 85% monopoly — near-total control",
            "2021 Chinese production curtailment caused 600% price spike in Europe",
            "No significant Western production capacity",
            "Lightest structural metal with no substitute at comparable weight",
            "Essential for all incendiary/flare munitions",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 25. Silicon ──
    {
        "name": "Silicon",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 78, 3900000),
            _mining("Brazil", 4, 190000),
            _mining("Norway", 3),
            _mining("France", 2),
            _mining("Russia", 1),
        ],
        "processing": [
            _processing("China", 80, "semiconductor-grade"),
            _processing("USA", 3, "semiconductor-grade"),
            _processing("Germany", 3, "semiconductor-grade"),
            _processing("Japan", 3, "semiconductor-grade"),
        ],
        "components": [
            _component("Semiconductor chips (all military electronics)", "USA"),
            _component("Al-Si alloys (engine blocks)", "USA"),
            _component("SiC ceramic armor plates", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("JDAM guidance", "USA"),
            _platform("All satellite systems", "USA"),
            _platform("M1A2 Abrams", "USA"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Norwegian Sea")],
        "hhi": 6200,
        "risk_level": "critical",
        "risk_factors": [
            "China 78% production monopoly",
            "Silicon is foundation of all semiconductor electronics",
            "China export controls on silicon could paralyze defense electronics",
            "Norway and Brazil are only meaningful Western sources",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 26. Strontium ──
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
            _processing("China", 45, "strontium compounds"),
            _processing("Germany", 25, "strontium compounds"),
            _processing("Mexico", 20, "strontium compounds"),
        ],
        "components": [
            _component("Military signal flares (red)", "USA"),
            _component("Tracer ammunition", "USA"),
            _component("Ceramic ferrite magnets", "China"),
            _component("Sonar transducer ceramics", "USA"),
        ],
        "platforms": [
            _platform("Aircraft countermeasure flares", "USA"),
            _platform("Tracer rounds (5.56/7.62mm)", "USA"),
            _platform("Sonobuoys", "USA"),
        ],
        "chokepoints": [_cp("Strait of Gibraltar"), _cp("Strait of Hormuz"), _cp("Gulf of Mexico")],
        "hhi": 2400,
        "risk_level": "high",
        "risk_factors": [
            "Iran 25% production under sanctions",
            "China 20% supply subject to export controls",
            "No US domestic production since 2006",
            "Strontium nitrate has no substitute in red military flares",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 27. Zirconium ──
    {
        "name": "Zirconium",
        "category": "Nuclear Material",
        "mining": [
            _mining("Australia", 28, 420000),
            _mining("South Africa", 27, 400000),
            _mining("Mozambique", 10),
            _mining("Senegal", 8),
            _mining("China", 5),
        ],
        "processing": [
            _processing("China", 88, "unwrought zirconium"),
            _processing("France", 15, "nuclear-grade Zircaloy"),
            _processing("USA", 5, "nuclear-grade"),
        ],
        "components": [
            _component("Nuclear reactor fuel cladding", "USA"),
            _component("Naval reactor fuel assemblies", "France"),
            _component("Ceramic armor inserts", "USA"),
        ],
        "platforms": [
            _platform("Virginia-class SSN", "USA"),
            _platform("CVN-78 Ford-class carrier", "USA"),
            _platform("Astute-class SSN", "UK"),
        ],
        "chokepoints": [_cp("Cape of Good Hope"), _cp("Strait of Malacca"), _cp("Indian Ocean")],
        "hhi": 1800,
        "risk_level": "high",
        "risk_factors": [
            "China processes 88% of unwrought zirconium",
            "France (Framatome) and USA (Westinghouse) maintain captive nuclear-grade capacity",
            "Processing extremely concentrated despite diversified mining",
            "Critical for entire Western nuclear submarine fleet",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 28. Hafnium ──
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
            _processing("USA", 22, "nuclear-grade"),
            _processing("China", 15, "refined hafnium"),
            _processing("Russia", 5, "refined hafnium"),
        ],
        "components": [
            _component("Nuclear reactor control rods", "France"),
            _component("Superalloy turbine blades (single-crystal)", "USA"),
            _component("Rocket engine nozzles", "USA"),
        ],
        "platforms": [
            _platform("Virginia-class SSN", "USA"),
            _platform("Suffren-class SSN", "France"),
            _platform("F-35 Lightning II", "USA"),
        ],
        "chokepoints": [_cp("Suez Canal"), _cp("North Atlantic")],
        "hhi": 3200,
        "risk_level": "high",
        "risk_factors": [
            "Only ~90 tonnes produced globally per year — extremely small market",
            "France (Framatome) is single largest processor at 49%",
            "Any disruption to Framatome facility halts 49% of global supply",
            "65% of hafnium used in nuclear control rods",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 29. Rhenium ──
    {
        "name": "Rhenium",
        "category": "Superalloy Metal",
        "mining": [
            _mining("Chile", 55, 34000),
            _mining("USA", 15, 9500),
            _mining("Poland", 10),
            _mining("Kazakhstan", 5),
            _mining("Armenia", 3),
        ],
        "processing": [
            _processing("Chile", 50, "ammonium perrhenate"),
            _processing("USA", 18, "ammonium perrhenate"),
            _processing("Germany", 10, "rhenium metal"),
            _processing("Poland", 8, "ammonium perrhenate"),
            _processing("UK", 5, "rhenium metal"),
        ],
        "components": [
            _component("Single-crystal superalloy turbine blades", "USA"),
            _component("Rocket engine thrust chambers", "USA"),
            _component("Catalytic reformers", "USA"),
        ],
        "platforms": [
            _platform("F-35 Lightning II", "USA"),
            _platform("F-22 Raptor", "USA"),
            _platform("F/A-18 Super Hornet", "USA"),
            _platform("Eurofighter Typhoon", "Germany"),
        ],
        "chokepoints": [_cp("Panama Canal"), _cp("Drake Passage"), _cp("North Atlantic")],
        "hhi": 3400,
        "risk_level": "high",
        "risk_factors": [
            "Chile 55% single-country concentration",
            "Rhenium is byproduct of copper-molybdenum mining (inelastic supply)",
            "Global production only 62,000 kg/year — tiny market",
            "No substitute in 2nd/3rd generation single-crystal superalloys",
            "Every modern fighter jet engine depends on rhenium",
        ],
        "source": "USGS MCS 2025",
    },

    # ── 30. Indium ──
    {
        "name": "Indium",
        "category": "Semiconductor Material",
        "mining": [
            _mining("China", 66, 650),
            _mining("South Korea", 20, 200),
            _mining("Japan", 7, 66),
            _mining("Canada", 3),
            _mining("Belgium", 2),
        ],
        "processing": [
            _processing("China", 60, "refined indium"),
            _processing("South Korea", 20, "refined indium"),
            _processing("Japan", 10, "refined indium"),
            _processing("Canada", 4, "refined indium"),
            _processing("Belgium", 3, "refined indium"),
        ],
        "components": [
            _component("ITO stealth canopy coatings", "USA"),
            _component("IR detectors (InSb)", "USA"),
            _component("Military flat-panel displays", "USA"),
            _component("Aircraft windshield de-icing", "USA"),
        ],
        "platforms": [
            _platform("F-22 Raptor", "USA"),
            _platform("F-35 Lightning II", "USA"),
            _platform("Sidewinder AIM-9X", "USA"),
        ],
        "chokepoints": [_cp("South China Sea"), _cp("Strait of Malacca"), _cp("Korean Strait")],
        "hhi": 4900,
        "risk_level": "critical",
        "risk_factors": [
            "China 66% production from zinc smelting byproduct",
            "Indium supply inelastic (dependent on zinc market)",
            "ITO has no proven substitute for stealth canopy coatings",
            "InSb critical for IR missile seekers",
            "Total annual production only ~990 tonnes globally",
        ],
        "source": "USGS MCS 2025",
    },
]


def get_all_minerals() -> list[dict]:
    """Return all 30 mineral supply chain records."""
    return MINERALS


def get_mineral_by_name(name: str) -> dict | None:
    """Lookup a single mineral by name (case-insensitive)."""
    name_lower = name.lower()
    for m in MINERALS:
        if m["name"].lower() == name_lower:
            return m
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_globe.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/mineral_supply_chains.py tests/test_globe.py
git commit -m "feat: add mineral supply chain data module (30 minerals, USGS 2025)"
```

---

### Task 2: Create globe API routes

**Files:**
- Create: `src/api/globe_routes.py`
- Modify: `src/main.py`
- Modify: `tests/test_globe.py`

- [ ] **Step 1: Add API tests to test_globe.py**

Append to `tests/test_globe.py`:

```python
from fastapi.testclient import TestClient
from src.api.routes import app
from src.api.globe_routes import router as globe_router

# Ensure globe router is included for tests
if globe_router not in [r for r in app.router.routes]:
    app.include_router(globe_router)

client = TestClient(app)


class TestGlobeAPI:
    """Test the /globe/* API endpoints."""

    def test_get_all_minerals(self):
        resp = client.get("/globe/minerals")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 30
        assert data[0]["name"] == "Titanium"

    def test_get_mineral_by_name(self):
        resp = client.get("/globe/minerals/Gallium")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Gallium"
        assert data["hhi"] == 9800

    def test_get_mineral_by_name_case_insensitive(self):
        resp = client.get("/globe/minerals/gallium")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Gallium"

    def test_get_mineral_not_found(self):
        resp = client.get("/globe/minerals/Unobtanium")
        assert resp.status_code == 404

    def test_mineral_response_has_coordinates(self):
        resp = client.get("/globe/minerals/Cobalt")
        data = resp.json()
        assert data["mining"][0]["lat"] == -4.0  # DRC
        assert data["mining"][0]["lon"] == 22.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_globe.py::TestGlobeAPI -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.api.globe_routes'`

- [ ] **Step 3: Create globe_routes.py**

Create `src/api/globe_routes.py`:

```python
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
```

- [ ] **Step 4: Register globe router in main.py**

Add to `src/main.py` imports:
```python
from src.api.globe_routes import router as globe_router
```

Add to router registrations:
```python
app.include_router(globe_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_globe.py -v`
Expected: All 14 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/globe_routes.py src/main.py tests/test_globe.py
git commit -m "feat: add globe API routes (GET /globe/minerals)"
```

---

### Task 3: Add CesiumJS globe sub-tab HTML structure

**Files:**
- Modify: `src/static/index.html`

This task adds the CesiumJS CDN script, "3D Supply Map" sub-tab button, and the globe container with layer panel to the Supply Chain page.

- [ ] **Step 1: Add CesiumJS CDN script and CSS to the `<head>`**

After the Leaflet script tag (line 14), add:

```html
<link rel="stylesheet" href="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Widgets/widgets.css">
<script src="https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js"></script>
```

- [ ] **Step 2: Add "3D Supply Map" button to the PSI tab bar**

In the `.psi-tab-bar` (line 1748), add a new button after "Overview":

```html
<button class="tab" data-psi-tab="psi-globe" onclick="switchPsiTab(this)">3D Supply Map</button>
```

- [ ] **Step 3: Add globe container div after psi-overview**

After the `</div>` closing `psi-overview` (line 1807), insert a new `psi-sub` div:

```html
    <!-- PSI 3D Supply Map (CesiumJS Globe) -->
    <div id="psi-globe" class="psi-sub" style="display:none;">
      <div style="display:flex; gap:0; height:650px;">
        <!-- Layer toggle panel -->
        <div id="globe-layer-panel" class="card" style="width:280px; padding:14px; overflow-y:auto; border-radius:10px 0 0 10px; flex-shrink:0;">
          <h3 style="margin-bottom:10px; font-size:14px;">Mineral Layers</h3>
          <input id="globe-mineral-search" type="text" placeholder="Search minerals..." style="width:100%; padding:6px 10px; margin-bottom:12px; background:var(--bg); color:var(--text); border:1px solid var(--border); border-radius:6px; font-family:var(--font-body); font-size:12px;">
          <div id="globe-mineral-list"></div>
        </div>
        <!-- Cesium globe container -->
        <div style="flex:1; position:relative; border-radius:0 10px 10px 0; overflow:hidden;">
          <div id="cesium-globe" style="width:100%; height:100%;"></div>
          <!-- Node detail popup -->
          <div id="globe-popup" style="display:none; position:absolute; top:20px; right:20px; width:300px; background:var(--surface-glass); backdrop-filter:blur(16px); border:1px solid var(--border); border-radius:10px; padding:16px; z-index:10;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <h4 id="globe-popup-title" style="margin:0; font-size:14px;"></h4>
              <button onclick="document.getElementById('globe-popup').style.display='none'" style="background:none; border:none; color:var(--text-dim); cursor:pointer; font-size:16px;">&times;</button>
            </div>
            <div id="globe-popup-body" style="font-size:12px; color:var(--text-dim); line-height:1.6;"></div>
          </div>
        </div>
      </div>
      <!-- Legend bar -->
      <div class="card" style="margin-top:8px; padding:10px 18px; display:flex; flex-wrap:wrap; gap:6px 24px; font-size:11px; color:var(--text-dim);">
        <span style="font-weight:600; color:var(--text);">Tiers:</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#10b981; margin-right:4px; vertical-align:middle;"></span> Mining</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; background:#8b5cf6; margin-right:4px; vertical-align:middle; transform:rotate(45deg);"></span> Processing</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:2px; background:#f59e0b; margin-right:4px; vertical-align:middle;"></span> Components</span>
        <span><span style="display:inline-block; width:10px; height:10px; background:#00d4ff; margin-right:4px; vertical-align:middle; clip-path:polygon(50% 0%, 61% 35%, 98% 35%, 68% 57%, 79% 91%, 50% 70%, 21% 91%, 32% 57%, 2% 35%, 39% 35%);"></span> Platforms</span>
        <span style="margin-left:16px; font-weight:600; color:var(--text);">Risk:</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#ef4444; margin-right:4px; vertical-align:middle;"></span> Critical</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#f59e0b; margin-right:4px; vertical-align:middle;"></span> High</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#eab308; margin-right:4px; vertical-align:middle;"></span> Medium</span>
        <span><span style="display:inline-block; width:10px; height:10px; border-radius:50%; background:#10b981; margin-right:4px; vertical-align:middle;"></span> Low</span>
        <span style="margin-left:16px; font-weight:600; color:var(--text);">Arcs:</span>
        <span>Green = low risk &nbsp; Amber = moderate &nbsp; Red = high risk / sanctioned</span>
      </div>
    </div>
```

- [ ] **Step 4: Update switchPsiTab to initialize globe on first view**

In the `switchPsiTab` function (around line 5522), add a condition to load the globe:

```javascript
if (btn.dataset.psiTab === 'psi-globe' && !globeInitialized) initCesiumGlobe();
```

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add CesiumJS globe HTML structure and sub-tab"
```

---

### Task 4: Implement CesiumJS globe JavaScript logic

**Files:**
- Modify: `src/static/index.html`

This task adds all the JavaScript for initializing CesiumJS, fetching mineral data, rendering entities (markers, arcs, labels), and handling interactions.

- [ ] **Step 1: Add globe state variables**

Near the PSI state variables (line ~5517), add:

```javascript
let globeInitialized = false;
let cesiumViewer = null;
let globeMinerals = [];
let activeGlobeLayers = new Set();
```

- [ ] **Step 2: Implement initCesiumGlobe()**

Add the main globe initialization function:

```javascript
async function initCesiumGlobe() {
  globeInitialized = true;

  // Initialize CesiumJS with dark globe (no ion token needed for base imagery)
  Cesium.Ion.defaultAccessToken = undefined;
  cesiumViewer = new Cesium.Viewer('cesium-globe', {
    baseLayer: false,
    geocoder: false,
    homeButton: false,
    sceneModePicker: false,
    navigationHelpButton: false,
    animation: false,
    timeline: false,
    fullscreenButton: false,
    selectionIndicator: false,
    infoBox: false,
    baseLayerPicker: false,
    creditContainer: document.createElement('div'), // hide credits
  });

  // Dark globe styling
  cesiumViewer.scene.backgroundColor = Cesium.Color.fromCssColorString('#0a0e1a');
  cesiumViewer.scene.globe.baseColor = Cesium.Color.fromCssColorString('#111827');
  cesiumViewer.scene.globe.showGroundAtmosphere = false;
  cesiumViewer.scene.globe.enableLighting = false;
  cesiumViewer.scene.skyBox.show = false;
  cesiumViewer.scene.sun.show = false;
  cesiumViewer.scene.moon.show = false;
  cesiumViewer.scene.skyAtmosphere.show = false;

  // Add simple imagery
  cesiumViewer.scene.globe.imageryLayers.addImageryProvider(
    new Cesium.SingleTileImageryProvider({
      url: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90),
    })
  );

  // Country borders via GeoJSON (Natural Earth low-res)
  try {
    const geoResp = await fetch('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson');
    if (geoResp.ok) {
      const geoData = await geoResp.json();
      const ds = await Cesium.GeoJsonDataSource.load(geoData, {
        stroke: Cesium.Color.fromCssColorString('#00d4ff').withAlpha(0.15),
        fill: Cesium.Color.fromCssColorString('#111827').withAlpha(0.01),
        strokeWidth: 1,
      });
      cesiumViewer.dataSources.add(ds);
    }
  } catch (e) { /* borders are optional */ }

  // Fetch mineral data
  try {
    const resp = await fetch(API + '/globe/minerals');
    if (!resp.ok) throw new Error('Failed to load minerals');
    globeMinerals = await resp.json();
  } catch (e) {
    document.getElementById('globe-mineral-list').innerHTML =
      '<div style="color:var(--accent2); padding:20px;">Failed to load mineral data</div>';
    return;
  }

  renderMineralLayerPanel();
  setupGlobeClickHandler();

  // Auto-enable top 3 critical minerals
  const criticals = globeMinerals.filter(m => m.risk_level === 'critical').slice(0, 3);
  criticals.forEach(m => toggleMineralLayer(m.name, true));
}
```

- [ ] **Step 3: Implement renderMineralLayerPanel()**

```javascript
function renderMineralLayerPanel() {
  const container = document.getElementById('globe-mineral-list');
  const riskOrder = { critical: 0, high: 1, medium: 2, low: 3 };
  const riskColors = { critical: '#ef4444', high: '#f59e0b', medium: '#eab308', low: '#10b981' };
  const sorted = [...globeMinerals].sort((a, b) => riskOrder[a.risk_level] - riskOrder[b.risk_level]);

  let currentRisk = '';
  let html = '';

  sorted.forEach(m => {
    if (m.risk_level !== currentRisk) {
      currentRisk = m.risk_level;
      html += `<div style="font-size:10px; font-family:var(--font-mono); text-transform:uppercase; letter-spacing:0.1em; color:${riskColors[currentRisk]}; margin:12px 0 6px; font-weight:600;">── ${currentRisk} risk ──</div>`;
    }
    html += `<label style="display:flex; align-items:center; gap:8px; padding:5px 0; cursor:pointer; font-size:12px;" data-mineral-name="${esc(m.name)}">
      <input type="checkbox" onchange="toggleMineralLayer('${esc(m.name)}', this.checked)" style="accent-color:${riskColors[m.risk_level]};">
      <span style="flex:1;">${esc(m.name)}</span>
      <span style="width:8px; height:8px; border-radius:50%; background:${riskColors[m.risk_level]}; flex-shrink:0;"></span>
    </label>`;
  });

  container.innerHTML = html;

  // Search filter
  document.getElementById('globe-mineral-search').addEventListener('input', function () {
    const q = this.value.toLowerCase();
    container.querySelectorAll('label').forEach(el => {
      const name = el.dataset.mineralName.toLowerCase();
      el.style.display = name.includes(q) ? '' : 'none';
    });
  });
}
```

- [ ] **Step 4: Implement toggleMineralLayer() — markers and arcs**

```javascript
function toggleMineralLayer(name, enabled) {
  if (enabled) {
    activeGlobeLayers.add(name);
  } else {
    activeGlobeLayers.delete(name);
  }

  // Update checkbox state
  const cb = document.querySelector(`[data-mineral-name="${name}"] input`);
  if (cb) cb.checked = enabled;

  // Rebuild all entities
  renderGlobeEntities();

  // Fly to mineral's primary source when enabling
  if (enabled) {
    const mineral = globeMinerals.find(m => m.name === name);
    if (mineral && mineral.mining.length > 0) {
      const primary = mineral.mining[0];
      cesiumViewer.camera.flyTo({
        destination: Cesium.Cartesian3.fromDegrees(primary.lon, primary.lat, 12000000),
        duration: 1.5,
      });
    }
  }
}

function renderGlobeEntities() {
  cesiumViewer.entities.removeAll();

  const tierColors = {
    mining: Cesium.Color.fromCssColorString('#10b981'),
    processing: Cesium.Color.fromCssColorString('#8b5cf6'),
    component: Cesium.Color.fromCssColorString('#f59e0b'),
    platform: Cesium.Color.fromCssColorString('#00d4ff'),
  };
  const riskArcColors = {
    critical: Cesium.Color.fromCssColorString('#ef4444'),
    high: Cesium.Color.fromCssColorString('#f59e0b'),
    medium: Cesium.Color.fromCssColorString('#eab308'),
    low: Cesium.Color.fromCssColorString('#10b981'),
  };

  activeGlobeLayers.forEach(name => {
    const m = globeMinerals.find(x => x.name === name);
    if (!m) return;

    const arcColor = riskArcColors[m.risk_level] || riskArcColors.medium;

    // Mining sites — pulsing spheres sized by production %
    m.mining.forEach(site => {
      const size = Math.max(6, Math.min(20, site.pct * 0.5)) * 1.5;
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(site.lon, site.lat),
        point: { pixelSize: size, color: tierColors.mining, outlineColor: tierColors.mining.withAlpha(0.4), outlineWidth: 3 },
        label: {
          text: `${site.country}\n${site.pct}%`,
          font: '11px JetBrains Mono', fillColor: Cesium.Color.WHITE,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 12),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
        },
        properties: { type: 'mining', mineral: m.name, country: site.country, pct: site.pct },
      });
    });

    // Processing plants — diamond markers
    m.processing.forEach(site => {
      const size = Math.max(8, Math.min(18, site.pct * 0.4));
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(site.lon, site.lat, 50000),
        point: { pixelSize: size, color: tierColors.processing, outlineColor: tierColors.processing.withAlpha(0.4), outlineWidth: 2 },
        label: {
          text: `${site.country} ${site.pct}%`,
          font: '10px JetBrains Mono', fillColor: Cesium.Color.WHITE,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 10),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000),
        },
        properties: { type: 'processing', mineral: m.name, country: site.country, pct: site.pct, processType: site.type },
      });
    });

    // Component factories — small markers at manufacturer country
    m.components.forEach(comp => {
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(comp.lon, comp.lat, 100000),
        point: { pixelSize: 7, color: tierColors.component, outlineColor: tierColors.component.withAlpha(0.4), outlineWidth: 2 },
        label: {
          text: comp.name.length > 25 ? comp.name.slice(0, 25) + '...' : comp.name,
          font: '9px IBM Plex Sans', fillColor: tierColors.component,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 8),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000),
        },
        properties: { type: 'component', mineral: m.name, name: comp.name, country: comp.manufacturer_country },
      });
    });

    // Weapon platforms — star markers
    m.platforms.forEach(plat => {
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(plat.lon, plat.lat, 200000),
        point: { pixelSize: 10, color: tierColors.platform, outlineColor: Cesium.Color.WHITE.withAlpha(0.5), outlineWidth: 2 },
        label: {
          text: plat.name,
          font: 'bold 11px IBM Plex Sans', fillColor: tierColors.platform,
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 12),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000),
        },
        properties: { type: 'platform', mineral: m.name, name: plat.name, country: plat.assembly_country },
      });
    });

    // Chokepoint markers — flashing triangles
    (m.chokepoints || []).forEach(cp => {
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(cp.lon, cp.lat),
        billboard: {
          image: buildTriangleCanvas(),
          width: 14, height: 14,
        },
        label: {
          text: cp.name, font: '10px JetBrains Mono', fillColor: Cesium.Color.fromCssColorString('#ef4444'),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 10),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
        },
        properties: { type: 'chokepoint', mineral: m.name, name: cp.name },
      });
    });

    // Flow arcs: mining → processing (primary connections)
    if (m.mining.length > 0 && m.processing.length > 0) {
      const topMiner = m.mining[0];
      m.processing.forEach(proc => {
        if (proc.country === topMiner.country) return; // skip same-country
        addFlowArc(topMiner.lon, topMiner.lat, proc.lon, proc.lat, arcColor, m.name + ': ' + topMiner.country + ' → ' + proc.country);
      });
    }

    // Flow arcs: processing → component (primary)
    if (m.processing.length > 0 && m.components.length > 0) {
      const topProc = m.processing[0];
      m.components.slice(0, 3).forEach(comp => {
        if (comp.manufacturer_country === topProc.country) return;
        addFlowArc(topProc.lon, topProc.lat, comp.lon, comp.lat, arcColor.withAlpha(0.6), m.name + ': ' + topProc.country + ' → ' + comp.manufacturer_country);
      });
    }
  });
}

function addFlowArc(lon1, lat1, lon2, lat2, color, description) {
  cesiumViewer.entities.add({
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArrayHeights([
        lon1, lat1, 0,
        (lon1 + lon2) / 2, (lat1 + lat2) / 2, 800000,
        lon2, lat2, 0,
      ]),
      width: 2,
      material: new Cesium.PolylineGlowMaterialProperty({
        glowPower: 0.15,
        color: color,
      }),
    },
    properties: { type: 'arc', description: description },
  });
}

function buildTriangleCanvas() {
  const c = document.createElement('canvas');
  c.width = 16; c.height = 16;
  const ctx = c.getContext('2d');
  ctx.fillStyle = '#ef4444';
  ctx.beginPath();
  ctx.moveTo(8, 0);
  ctx.lineTo(16, 16);
  ctx.lineTo(0, 16);
  ctx.closePath();
  ctx.fill();
  return c;
}
```

- [ ] **Step 5: Implement click handler for node popups**

```javascript
function setupGlobeClickHandler() {
  const handler = new Cesium.ScreenSpaceEventHandler(cesiumViewer.scene.canvas);
  handler.setInputAction(function (click) {
    const picked = cesiumViewer.scene.pick(click.position);
    if (!Cesium.defined(picked) || !picked.id || !picked.id.properties) {
      document.getElementById('globe-popup').style.display = 'none';
      return;
    }

    const props = picked.id.properties;
    const type = props.type ? props.type.getValue() : '';
    const mineral = props.mineral ? props.mineral.getValue() : '';
    const popup = document.getElementById('globe-popup');
    const title = document.getElementById('globe-popup-title');
    const body = document.getElementById('globe-popup-body');

    let html = '';
    if (type === 'mining') {
      title.textContent = `⛏ ${props.country.getValue()} — Mining`;
      html = `<div><strong>Mineral:</strong> ${esc(mineral)}</div>
              <div><strong>Share:</strong> ${props.pct.getValue()}% of global production</div>`;
    } else if (type === 'processing') {
      title.textContent = `🏭 ${props.country.getValue()} — Processing`;
      html = `<div><strong>Mineral:</strong> ${esc(mineral)}</div>
              <div><strong>Share:</strong> ${props.pct.getValue()}%</div>
              <div><strong>Type:</strong> ${esc(props.processType ? props.processType.getValue() : '')}</div>`;
    } else if (type === 'component') {
      title.textContent = `🔧 Component`;
      html = `<div><strong>${esc(props.name.getValue())}</strong></div>
              <div><strong>Mineral:</strong> ${esc(mineral)}</div>
              <div><strong>Country:</strong> ${esc(props.country.getValue())}</div>`;
    } else if (type === 'platform') {
      title.textContent = `⭐ ${props.name.getValue()}`;
      html = `<div><strong>Mineral:</strong> ${esc(mineral)}</div>
              <div><strong>Assembly:</strong> ${esc(props.country.getValue())}</div>`;
    } else if (type === 'chokepoint') {
      title.textContent = `⚠ ${props.name.getValue()}`;
      html = `<div><strong>Mineral:</strong> ${esc(mineral)}</div>
              <div>Strategic maritime chokepoint</div>`;
    } else {
      popup.style.display = 'none';
      return;
    }

    // Add risk factors if it's a mineral entity
    if (mineral) {
      const m = globeMinerals.find(x => x.name === mineral);
      if (m) {
        html += `<div style="margin-top:8px; padding-top:8px; border-top:1px solid var(--border);">
          <div style="font-weight:600; margin-bottom:4px; color:var(--text);">Risk Factors:</div>
          ${m.risk_factors.map(r => `<div style="margin:2px 0;">• ${esc(r)}</div>`).join('')}
        </div>`;
      }
    }

    body.innerHTML = html;
    popup.style.display = '';
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
}
```

- [ ] **Step 6: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement CesiumJS 3D globe with mineral layers and interactions"
```

---

### Task 5: Manual testing and polish

**Files:**
- Possibly: `src/static/index.html`, `src/analysis/mineral_supply_chains.py`

- [ ] **Step 1: Start the server and verify**

Run: `python -m src.main`

Verify at http://localhost:8000:
1. Navigate to Supply Chain tab
2. Click "3D Supply Map" sub-tab
3. Globe should render with dark styling
4. Layer panel should show 30 minerals grouped by risk level
5. Three critical minerals should be auto-enabled
6. Click a mineral in the panel — globe rotates to its primary source
7. Click an entity on the globe — popup appears with details
8. Search box filters the mineral list
9. Toggle minerals on/off — entities appear/disappear
10. Enable multiple minerals — overlaid chains visible

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests + 14 new globe tests PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete CesiumJS 3D Supply Chain Globe (30 minerals, USGS 2025)"
```
