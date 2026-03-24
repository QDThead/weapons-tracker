"""Critical defense minerals data connector.

Tracks global production concentration of minerals essential to defense
manufacturing. Data sourced from USGS Mineral Commodity Summaries (annual)
with hardcoded fallback for ~30 materials when the USGS site is unavailable.

Provides supply-chain risk assessment: which countries control materials
needed for weapons, aircraft, electronics, and nuclear systems.

Reference: https://pubs.usgs.gov/periodicals/mcs2025/
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import httpx

from src.storage.models import MaterialCategory

logger = logging.getLogger(__name__)

USGS_MCS_BASE_URL = "https://pubs.usgs.gov/periodicals/mcs2025/"


@dataclass
class MineralRecord:
    """A single critical mineral with production and strategic data."""

    name: str
    category: str
    top_producers: str  # JSON string of [{country, pct, tonnes}, ...]
    concentration_index: float  # 0-1 Herfindahl-Hirschman Index
    strategic_importance: int  # 1-5
    defense_applications: str
    notes: str = ""


@dataclass
class CriticalMineralsClient:
    """Client for fetching critical defense minerals data.

    Primary source is USGS Mineral Commodity Summaries. Falls back to
    hardcoded seed data covering ~30 materials with real production figures.
    """

    base_url: str = USGS_MCS_BASE_URL
    timeout: float = 30.0
    _client: httpx.AsyncClient | None = field(default=None, repr=False)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"User-Agent": "weapons-tracker/1.0"},
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def fetch_usgs_summary(self, mineral: str) -> dict | None:
        """Fetch a single mineral commodity summary page from USGS.

        Returns parsed data dict on success, None on failure.
        The USGS publishes PDFs and HTML pages per mineral; this attempts
        to retrieve the HTML summary. If the format changes or the site
        is unreachable, callers should fall back to seeded data.
        """
        client = await self._get_client()
        url = f"{self.base_url}mcs2025-{mineral.lower().replace(' ', '-')}.pdf"
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                logger.info(
                    "Fetched USGS summary for %s (%d bytes)",
                    mineral,
                    len(resp.content),
                )
                # USGS publishes PDFs; full parsing is not yet implemented.
                # Return raw content reference for future PDF extraction.
                return {
                    "mineral": mineral,
                    "url": url,
                    "size_bytes": len(resp.content),
                    "status": "fetched",
                }
            logger.warning(
                "USGS returned %d for %s", resp.status_code, mineral
            )
        except httpx.HTTPError as exc:
            logger.warning("Failed to fetch USGS data for %s: %s", mineral, exc)
        return None

    async def fetch_all_summaries(self) -> list[dict]:
        """Attempt to fetch USGS summaries for all seeded materials.

        Returns a list of successfully fetched summary metadata dicts.
        Materials that fail to fetch are silently skipped; callers should
        use get_seeded_materials() as the authoritative fallback.
        """
        materials = self.get_seeded_materials()
        results = []
        for mat in materials:
            summary = await self.fetch_usgs_summary(mat["name"])
            if summary is not None:
                results.append(summary)
        logger.info(
            "Fetched %d/%d USGS mineral summaries",
            len(results),
            len(materials),
        )
        return results

    @classmethod
    def get_seeded_materials(cls) -> list[dict]:
        """Return hardcoded critical defense materials data.

        Contains ~30 minerals with real production percentages, HHI
        concentration indices, strategic importance ratings, and defense
        application descriptions. Used when the USGS API is unavailable
        or as the primary data source for the dashboard.

        Each dict has keys: name, category, top_producers (JSON string),
        concentration_index (HHI), strategic_importance (1-5),
        defense_applications, notes.
        """
        return [
            # --- 1. Cobalt ---
            {
                "name": "Cobalt",
                "category": MaterialCategory.COBALT.value,
                "top_producers": json.dumps([
                    {"country": "DRC", "pct": 73.0, "tonnes": 130000},
                    {"country": "Russia", "pct": 4.0, "tonnes": 7100},
                    {"country": "Australia", "pct": 3.0, "tonnes": 5300},
                ]),
                "concentration_index": 0.535,
                "strategic_importance": 4,
                "defense_applications": (
                    "Jet engine superalloys (turbine blades), battery cathodes "
                    "for military EVs and drone swarms, cemented carbides for "
                    "cutting tools"
                ),
                "notes": (
                    "DRC dominance creates single-point-of-failure; artisanal "
                    "mining raises ESG concerns for allied procurement"
                ),
            },
            # --- 2. Lithium ---
            {
                "name": "Lithium",
                "category": MaterialCategory.LITHIUM.value,
                "top_producers": json.dumps([
                    {"country": "Australia", "pct": 47.0, "tonnes": 86000},
                    {"country": "Chile", "pct": 30.0, "tonnes": 44000},
                    {"country": "China", "pct": 15.0, "tonnes": 33000},
                ]),
                "concentration_index": 0.333,
                "strategic_importance": 3,
                "defense_applications": (
                    "Lithium-ion batteries for drones, UPS for C4ISR systems, "
                    "military EV fleets, submarine battery banks, portable "
                    "soldier power systems"
                ),
                "notes": (
                    "Australia is a Five Eyes ally, reducing supply risk; "
                    "Chile's lithium nationalization debate adds uncertainty"
                ),
            },
            # --- 3. Rare Earth Elements ---
            {
                "name": "Rare Earth Elements",
                "category": MaterialCategory.RARE_EARTH.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 70.0, "tonnes": 240000},
                    {"country": "Myanmar", "pct": 12.0, "tonnes": 38000},
                    {"country": "Australia", "pct": 6.0, "tonnes": 18000},
                ]),
                "concentration_index": 0.508,
                "strategic_importance": 5,
                "defense_applications": (
                    "Nd-Fe-B permanent magnets for precision-guided munitions, "
                    "F-35 actuators, satellite reaction wheels; yttrium for "
                    "laser range-finders; lanthanum for night-vision optics"
                ),
                "notes": (
                    "China has imposed export controls on REE processing "
                    "technology; Myanmar supply routed through Chinese refiners"
                ),
            },
            # --- 4. Titanium ---
            {
                "name": "Titanium",
                "category": MaterialCategory.TITANIUM.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 57.0, "tonnes": 220000},
                    {"country": "Japan", "pct": 15.0, "tonnes": 56000},
                    {"country": "Russia", "pct": 6.0, "tonnes": 22000},
                ]),
                "concentration_index": 0.351,
                "strategic_importance": 4,
                "defense_applications": (
                    "Airframe structures (F-22 42% Ti, F-35 27% Ti, Su-57), "
                    "submarine pressure hulls, helicopter rotor hubs, "
                    "armor plating, jet engine compressor blades"
                ),
                "notes": (
                    "VSMPO-AVISMA (Russia) was a major Western supplier "
                    "pre-2022; sanctions forced supply chain diversification"
                ),
            },
            # --- 5. Tungsten ---
            {
                "name": "Tungsten",
                "category": MaterialCategory.TUNGSTEN.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 84.0, "tonnes": 71000},
                    {"country": "Vietnam", "pct": 5.0, "tonnes": 4300},
                    {"country": "Russia", "pct": 2.0, "tonnes": 1800},
                ]),
                "concentration_index": 0.708,
                "strategic_importance": 5,
                "defense_applications": (
                    "Armor-piercing ammunition and kinetic energy penetrators, "
                    "tungsten carbide tooling for munitions manufacturing, "
                    "counterweights in guided missiles"
                ),
                "notes": (
                    "China's 84% share is an acute vulnerability; no viable "
                    "substitute for kinetic penetrators at comparable density"
                ),
            },
            # --- 6. Chromium ---
            {
                "name": "Chromium",
                "category": MaterialCategory.CHROMIUM.value,
                "top_producers": json.dumps([
                    {"country": "South Africa", "pct": 44.0, "tonnes": 18000000},
                    {"country": "Turkey", "pct": 15.0, "tonnes": 6200000},
                    {"country": "Kazakhstan", "pct": 12.0, "tonnes": 5000000},
                ]),
                "concentration_index": 0.230,
                "strategic_importance": 3,
                "defense_applications": (
                    "Stainless and high-alloy steel for naval vessels, "
                    "chromium plating on gun barrels, armor hardening, "
                    "jet engine superalloy constituent"
                ),
                "notes": (
                    "Relatively diversified production; South Africa is "
                    "non-aligned but stable exporter"
                ),
            },
            # --- 7. Manganese ---
            {
                "name": "Manganese",
                "category": MaterialCategory.MANGANESE.value,
                "top_producers": json.dumps([
                    {"country": "South Africa", "pct": 37.0, "tonnes": 7200000},
                    {"country": "Gabon", "pct": 18.0, "tonnes": 3500000},
                    {"country": "Australia", "pct": 17.0, "tonnes": 3300000},
                ]),
                "concentration_index": 0.198,
                "strategic_importance": 2,
                "defense_applications": (
                    "Essential steel alloying element for armor plate, "
                    "submarine hull steel, Hadfield manganese steel for "
                    "tank tracks and earthmoving equipment"
                ),
                "notes": (
                    "Well-diversified supply; Australia provides Five Eyes "
                    "allied source"
                ),
            },
            # --- 8. Nickel ---
            {
                "name": "Nickel",
                "category": MaterialCategory.NICKEL.value,
                "top_producers": json.dumps([
                    {"country": "Indonesia", "pct": 49.0, "tonnes": 1800000},
                    {"country": "Philippines", "pct": 10.0, "tonnes": 370000},
                    {"country": "Russia", "pct": 5.0, "tonnes": 190000},
                ]),
                "concentration_index": 0.253,
                "strategic_importance": 2,
                "defense_applications": (
                    "Jet engine superalloys (Inconel, Waspaloy), stainless "
                    "steel for naval vessels, nickel-cadmium batteries, "
                    "armor plating alloys"
                ),
                "notes": (
                    "Indonesian production largely Chinese-financed; "
                    "Nornickel (Russia) under partial sanctions"
                ),
            },
            # --- 9. Tantalum ---
            {
                "name": "Tantalum",
                "category": MaterialCategory.TANTALUM.value,
                "top_producers": json.dumps([
                    {"country": "DRC", "pct": 33.0, "tonnes": 700},
                    {"country": "Rwanda", "pct": 17.0, "tonnes": 360},
                    {"country": "Brazil", "pct": 12.0, "tonnes": 250},
                ]),
                "concentration_index": 0.152,
                "strategic_importance": 4,
                "defense_applications": (
                    "Tantalum capacitors in every guided weapon, radar, and "
                    "military communications system; chemical-resistant "
                    "linings for shaped-charge warheads"
                ),
                "notes": (
                    "Conflict mineral sourcing from DRC/Rwanda requires "
                    "Dodd-Frank Section 1502 compliance"
                ),
            },
            # --- 10. Niobium ---
            {
                "name": "Niobium",
                "category": MaterialCategory.NIOBIUM.value,
                "top_producers": json.dumps([
                    {"country": "Brazil", "pct": 88.0, "tonnes": 79000},
                    {"country": "Canada", "pct": 8.0, "tonnes": 7100},
                    {"country": "DRC", "pct": 2.0, "tonnes": 1500},
                ]),
                "concentration_index": 0.781,
                "strategic_importance": 3,
                "defense_applications": (
                    "HSLA steel for jet engine alloys and gas turbines, "
                    "superconducting magnets for MRI and directed-energy "
                    "weapons research, rocket nozzle alloys"
                ),
                "notes": (
                    "Brazil's CBMM controls ~80% of global supply; Canada's "
                    "Niobec mine provides allied alternative"
                ),
            },
            # --- 11. Beryllium ---
            {
                "name": "Beryllium",
                "category": MaterialCategory.BERYLLIUM.value,
                "top_producers": json.dumps([
                    {"country": "USA", "pct": 65.0, "tonnes": 170},
                    {"country": "China", "pct": 15.0, "tonnes": 40},
                    {"country": "Mozambique", "pct": 5.0, "tonnes": 13},
                ]),
                "concentration_index": 0.448,
                "strategic_importance": 4,
                "defense_applications": (
                    "Satellite structural components, nuclear weapon pits "
                    "and reflectors, inertial guidance gyroscopes, X-ray "
                    "window material, F-35 brake components"
                ),
                "notes": (
                    "USA dominance via Materion Corp is strategically "
                    "favorable; classified as strategic material since 1940s"
                ),
            },
            # --- 12. Germanium ---
            {
                "name": "Germanium",
                "category": MaterialCategory.GERMANIUM.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 68.0, "tonnes": 96},
                    {"country": "Belgium", "pct": 10.0, "tonnes": 15},
                    {"country": "Russia", "pct": 5.0, "tonnes": 7},
                ]),
                "concentration_index": 0.475,
                "strategic_importance": 4,
                "defense_applications": (
                    "Infrared optics for thermal weapon sights and "
                    "missile seekers, fiber-optic cables for secure "
                    "military communications, satellite solar cells"
                ),
                "notes": (
                    "China imposed germanium export controls in July 2023; "
                    "direct retaliation tool against Western tech restrictions"
                ),
            },
            # --- 13. Gallium ---
            {
                "name": "Gallium",
                "category": MaterialCategory.GALLIUM.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 98.0, "tonnes": 600},
                    {"country": "Japan", "pct": 1.0, "tonnes": 6},
                ]),
                "concentration_index": 0.960,
                "strategic_importance": 5,
                "defense_applications": (
                    "GaAs and GaN semiconductors for AESA radar (F-35, "
                    "Patriot), electronic warfare jammers, 5G military "
                    "communications, laser diodes"
                ),
                "notes": (
                    "Highest concentration risk of any defense material; "
                    "China export controls since July 2023 threaten all "
                    "Western radar and EW production"
                ),
            },
            # --- 14. Copper ---
            {
                "name": "Copper",
                "category": MaterialCategory.COPPER.value,
                "top_producers": json.dumps([
                    {"country": "Chile", "pct": 24.0, "tonnes": 5200000},
                    {"country": "Peru", "pct": 10.0, "tonnes": 2200000},
                    {"country": "DRC", "pct": 10.0, "tonnes": 2200000},
                ]),
                "concentration_index": 0.078,
                "strategic_importance": 2,
                "defense_applications": (
                    "Ammunition cartridge cases and rotating bands, "
                    "electrical wiring in all military systems, heat "
                    "exchangers for naval vessels, shaped-charge liners"
                ),
                "notes": (
                    "Widely diversified global production; price volatility "
                    "is main concern rather than supply concentration"
                ),
            },
            # --- 15. Uranium ---
            {
                "name": "Uranium",
                "category": MaterialCategory.URANIUM.value,
                "top_producers": json.dumps([
                    {"country": "Kazakhstan", "pct": 43.0, "tonnes": 21227},
                    {"country": "Namibia", "pct": 11.0, "tonnes": 5613},
                    {"country": "Canada", "pct": 8.0, "tonnes": 4039},
                ]),
                "concentration_index": 0.203,
                "strategic_importance": 3,
                "defense_applications": (
                    "Nuclear propulsion for submarines and carriers, "
                    "nuclear warheads, depleted uranium armor-piercing "
                    "rounds (M829 series), DU armor on M1 Abrams"
                ),
                "notes": (
                    "Enrichment capacity more critical than ore; Russia's "
                    "Rosatom controls ~46% of global enrichment"
                ),
            },
            # --- 16. Vanadium ---
            {
                "name": "Vanadium",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 67.0, "tonnes": 73000},
                    {"country": "South Africa", "pct": 10.0, "tonnes": 10600},
                    {"country": "Russia", "pct": 5.0, "tonnes": 5500},
                ]),
                "concentration_index": 0.461,
                "strategic_importance": 3,
                "defense_applications": (
                    "High-strength low-alloy (HSLA) steel for armor and "
                    "structural components, titanium-vanadium alloys for "
                    "jet engines, vanadium redox flow batteries for base "
                    "energy storage"
                ),
                "notes": (
                    "China dominates; vanadium steel alloys critical for "
                    "armored vehicle and ship hulls"
                ),
            },
            # --- 17. Antimony ---
            {
                "name": "Antimony",
                "category": MaterialCategory.EXPLOSIVE_PRECURSOR.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 55.0, "tonnes": 83000},
                    {"country": "Tajikistan", "pct": 15.0, "tonnes": 23000},
                    {"country": "Russia", "pct": 5.0, "tonnes": 7500},
                ]),
                "concentration_index": 0.328,
                "strategic_importance": 3,
                "defense_applications": (
                    "Lead-antimony alloy for ammunition hardening, antimony "
                    "trioxide flame retardant in military vehicle interiors, "
                    "night-vision goggle semiconductor compounds"
                ),
                "notes": (
                    "China + Russia + Tajikistan control 75%; antimony "
                    "classified as critical by USGS since 2018"
                ),
            },
            # --- 18. Rhenium ---
            {
                "name": "Rhenium",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "Chile", "pct": 52.0, "tonnes": 28},
                    {"country": "USA", "pct": 16.0, "tonnes": 9},
                    {"country": "Poland", "pct": 9.0, "tonnes": 5},
                ]),
                "concentration_index": 0.304,
                "strategic_importance": 3,
                "defense_applications": (
                    "Single-crystal superalloy turbine blades for F-22 "
                    "and F-35 engines (F119/F135), rhenium-tungsten "
                    "thermocouples in missile systems"
                ),
                "notes": (
                    "Tiny global production (~54 tonnes/yr); F-35 engine "
                    "program alone consumes significant share"
                ),
            },
            # --- 19. Indium ---
            {
                "name": "Indium",
                "category": MaterialCategory.SEMICONDUCTOR.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 57.0, "tonnes": 520},
                    {"country": "South Korea", "pct": 15.0, "tonnes": 140},
                    {"country": "Japan", "pct": 10.0, "tonnes": 90},
                ]),
                "concentration_index": 0.357,
                "strategic_importance": 3,
                "defense_applications": (
                    "Indium tin oxide (ITO) for flat-panel displays in "
                    "cockpits and targeting systems, InSb infrared "
                    "detectors, solders for military electronics"
                ),
                "notes": (
                    "Byproduct of zinc refining; supply linked to zinc "
                    "market dynamics"
                ),
            },
            # --- 20. Hafnium ---
            {
                "name": "Hafnium",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "France", "pct": 45.0, "tonnes": 32},
                    {"country": "USA", "pct": 42.0, "tonnes": 30},
                    {"country": "Russia", "pct": 5.0, "tonnes": 4},
                ]),
                "concentration_index": 0.381,
                "strategic_importance": 3,
                "defense_applications": (
                    "Nuclear reactor control rods (submarine/carrier "
                    "reactors), jet engine superalloy turbine blades, "
                    "plasma arc cutting tips"
                ),
                "notes": (
                    "Allied nations (France + USA) control 87%; low "
                    "supply-chain risk for NATO"
                ),
            },
            # --- 21. Platinum Group Metals ---
            {
                "name": "Platinum Group Metals",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "South Africa", "pct": 72.0, "tonnes": 300},
                    {"country": "Russia", "pct": 12.0, "tonnes": 50},
                    {"country": "Zimbabwe", "pct": 6.0, "tonnes": 25},
                ]),
                "concentration_index": 0.536,
                "strategic_importance": 3,
                "defense_applications": (
                    "Catalytic converters for military vehicle emissions, "
                    "hydrogen fuel cell catalysts, electrical contacts in "
                    "high-reliability military electronics, spark plugs "
                    "for jet engines"
                ),
                "notes": (
                    "Russia's Nornickel is world's largest palladium "
                    "producer; sanctions impact global auto and defense "
                    "catalyst supply"
                ),
            },
            # --- 22. Zirconium ---
            {
                "name": "Zirconium",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "Australia", "pct": 37.0, "tonnes": 370000},
                    {"country": "South Africa", "pct": 14.0, "tonnes": 140000},
                    {"country": "Mozambique", "pct": 11.0, "tonnes": 110000},
                ]),
                "concentration_index": 0.169,
                "strategic_importance": 2,
                "defense_applications": (
                    "Nuclear fuel rod cladding (Zircaloy) for submarine "
                    "and carrier reactors, zirconia armor ceramics, "
                    "chemical-resistant coatings"
                ),
                "notes": (
                    "Australia (Five Eyes) is top producer; well-diversified "
                    "global supply"
                ),
            },
            # --- 23. Molybdenum ---
            {
                "name": "Molybdenum",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 44.0, "tonnes": 110000},
                    {"country": "Chile", "pct": 18.0, "tonnes": 44000},
                    {"country": "USA", "pct": 13.0, "tonnes": 32000},
                ]),
                "concentration_index": 0.243,
                "strategic_importance": 2,
                "defense_applications": (
                    "High-strength steel alloys for armor and gun tubes, "
                    "nuclear reactor pressure vessels, missile motor "
                    "casings, high-temperature furnace elements"
                ),
                "notes": (
                    "USA is third-largest producer; byproduct of copper "
                    "mining provides secondary supply"
                ),
            },
            # --- 24. Magnesium ---
            {
                "name": "Magnesium",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 84.0, "tonnes": 910000},
                    {"country": "Russia", "pct": 6.0, "tonnes": 65000},
                    {"country": "Israel", "pct": 3.0, "tonnes": 32000},
                ]),
                "concentration_index": 0.710,
                "strategic_importance": 3,
                "defense_applications": (
                    "Illumination flares and infrared countermeasure "
                    "decoy flares, incendiary munitions, lightweight "
                    "alloys for helicopter gearboxes and missile bodies"
                ),
                "notes": (
                    "China's 84% share mirrors tungsten risk; 2021 "
                    "Chinese supply disruption nearly halted EU auto "
                    "and defense production"
                ),
            },
            # --- 25. Silicon ---
            {
                "name": "Silicon",
                "category": MaterialCategory.SEMICONDUCTOR.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 69.0, "tonnes": 5600000},
                    {"country": "Russia", "pct": 6.0, "tonnes": 490000},
                    {"country": "Brazil", "pct": 5.0, "tonnes": 390000},
                ]),
                "concentration_index": 0.482,
                "strategic_importance": 3,
                "defense_applications": (
                    "Base material for all semiconductor chips used in "
                    "guidance systems, radar processing, communications; "
                    "solar cells for military satellites"
                ),
                "notes": (
                    "Metallurgical-grade silicon is China-dominated; "
                    "semiconductor-grade wafer production led by allies "
                    "(Japan, Germany, USA)"
                ),
            },
            # --- 26. Graphite ---
            {
                "name": "Graphite",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 65.0, "tonnes": 890000},
                    {"country": "Mozambique", "pct": 11.0, "tonnes": 150000},
                    {"country": "Brazil", "pct": 8.0, "tonnes": 110000},
                ]),
                "concentration_index": 0.441,
                "strategic_importance": 3,
                "defense_applications": (
                    "Nuclear reactor moderators, lithium-ion battery "
                    "anodes for military systems, radar-absorbent stealth "
                    "coatings, lubricants for weapons mechanisms"
                ),
                "notes": (
                    "China controls mining and 90%+ of processing/coating; "
                    "anode-grade graphite is a critical battery bottleneck"
                ),
            },
            # --- 27. Tin ---
            {
                "name": "Tin",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 31.0, "tonnes": 85000},
                    {"country": "Indonesia", "pct": 18.0, "tonnes": 49000},
                    {"country": "Myanmar", "pct": 12.0, "tonnes": 33000},
                ]),
                "concentration_index": 0.143,
                "strategic_importance": 1,
                "defense_applications": (
                    "Lead-free solder for all military electronics "
                    "assembly, tin-lead bearing alloys, tin plate for "
                    "corrosion-resistant ammunition packaging"
                ),
                "notes": (
                    "Moderately diversified; Myanmar production often "
                    "channeled through Chinese refiners"
                ),
            },
            # --- 28. Lead ---
            {
                "name": "Lead",
                "category": MaterialCategory.EXPLOSIVE_PRECURSOR.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 44.0, "tonnes": 2200000},
                    {"country": "Australia", "pct": 12.0, "tonnes": 580000},
                    {"country": "USA", "pct": 8.0, "tonnes": 380000},
                ]),
                "concentration_index": 0.214,
                "strategic_importance": 1,
                "defense_applications": (
                    "Conventional ammunition projectiles, radiation "
                    "shielding for nuclear systems, lead-acid batteries "
                    "for military vehicles, ballast and counterweights"
                ),
                "notes": (
                    "Highly recyclable (>60% from secondary sources in "
                    "Western nations); low supply-chain risk"
                ),
            },
            # --- 29. Bismuth ---
            {
                "name": "Bismuth",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 80.0, "tonnes": 16000},
                    {"country": "Laos", "pct": 8.0, "tonnes": 1600},
                    {"country": "Mexico", "pct": 3.0, "tonnes": 600},
                ]),
                "concentration_index": 0.647,
                "strategic_importance": 1,
                "defense_applications": (
                    "Non-toxic ammunition replacement for lead shot "
                    "(training ranges), fusible alloys for fire-suppression "
                    "in military facilities, pharmaceutical applications "
                    "for field medicine"
                ),
                "notes": (
                    "Niche defense role; primary importance is as lead "
                    "substitute for environmental compliance on bases"
                ),
            },
            # --- 30. Fluorite (Fluorspar) ---
            {
                "name": "Fluorite",
                "category": MaterialCategory.OTHER.value,
                "top_producers": json.dumps([
                    {"country": "China", "pct": 64.0, "tonnes": 5200000},
                    {"country": "Mexico", "pct": 14.0, "tonnes": 1100000},
                    {"country": "Mongolia", "pct": 5.0, "tonnes": 400000},
                ]),
                "concentration_index": 0.432,
                "strategic_importance": 2,
                "defense_applications": (
                    "Hydrofluoric acid feedstock for aluminum smelting "
                    "(aircraft) and uranium hexafluoride production "
                    "(enrichment), fluoropolymer coatings, optical "
                    "components for targeting systems"
                ),
                "notes": (
                    "Gateway material for uranium enrichment chain; "
                    "also critical for semiconductor etching gases"
                ),
            },
        ]
