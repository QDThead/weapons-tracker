# CesiumJS 3D Supply Chain Globe — Design Spec

**Date:** 2026-03-29
**Status:** Approved
**RFP Alignment:** Q2 (Supply Chain Illumination), Q3 (Multi-Tier Visibility), Q4 (Item-Based Illumination), Q10 (Visualization)

## Overview

A 3D interactive globe within the Supply Chain tab showing the complete "Rocks to Rockets" supply chain for 30 defence-critical minerals. Each mineral is a toggleable layer showing the 4-tier flow from mines to weapon platforms, with risk-colored arcs and real USGS/EU production data.

## Data Requirements

All data must be real, sourced from:
- **USGS Mineral Commodity Summaries 2024/2025** — mining production by country
- **EU Critical Raw Materials Assessment 2023** — processing concentration
- **Published defence industry BOMs** — component and platform dependencies
- **SIPRI/Jane's** — weapon platform material composition

No fabricated data. Every percentage must be traceable to a public source.

## Architecture

### New Files
- `src/api/globe_routes.py` — API endpoint serving mineral supply chain data
- `src/analysis/mineral_supply_chains.py` — Real mineral data (30 minerals, 4 tiers each)

### Modified Files
- `src/static/index.html` — CesiumJS loaded from CDN, new "3D Supply Map" sub-tab in Supply Chain
- `src/main.py` — Register globe router

### No New Dependencies
CesiumJS loaded from CDN (`https://cesium.com/downloads/cesiumjs/releases/1.119/Build/Cesium/Cesium.js`). No npm, no build step.

## Data Model

```python
@dataclass
class MineralSupplyChain:
    name: str                           # "Titanium"
    category: str                       # "Strategic Metal"
    mining: list[dict]                  # [{country, lat, lon, pct, production_tonnes}]
    processing: list[dict]              # [{country, lat, lon, pct, type}]
    components: list[dict]              # [{name, manufacturer_country, lat, lon}]
    platforms: list[dict]               # [{name, assembly_country, lat, lon, pct_by_weight}]
    chokepoints: list[dict]             # [{name, lat, lon}]
    hhi: int                            # Herfindahl-Hirschman Index
    risk_level: str                     # "critical" | "high" | "medium" | "low"
    risk_factors: list[str]             # ["China 60% processing dominance", ...]
    source: str                         # "USGS MCS 2024"
```

## API Endpoint

`GET /globe/minerals` — Returns all 30 mineral supply chains
`GET /globe/minerals/{name}` — Returns single mineral with full chain

Response includes geo-coordinates for every node so the globe can render without geocoding.

## Globe UI

### Layout
- Supply Chain tab gets a new sub-tab button: "3D Supply Map"
- Globe fills the content area (100% width, 600px height)
- Left panel (280px): mineral layer toggles with risk indicators
- Bottom bar: legend showing tier colors and risk levels

### Layer Toggle Panel
```
[search box]
-- CRITICAL RISK --
[x] Rare Earth Elements    [red dot]
[x] Gallium                [red dot]
[x] Germanium              [red dot]
-- HIGH RISK --
[ ] Cobalt                  [amber dot]
[ ] Titanium                [amber dot]
...
-- MEDIUM RISK --
[ ] Copper                  [yellow dot]
...
```

### Visual Encoding
- **Mining sites**: Pulsing spheres sized by production %, colored by risk
- **Processing plants**: Diamond markers
- **Component factories**: Square markers
- **Weapon platforms**: Star markers (at assembly country centroid)
- **Flow arcs**: Animated dashed lines with particle flow direction
  - Green = low risk path
  - Amber = moderate risk (passes through chokepoint or unstable country)
  - Red = high risk (sanctioned country, >60% concentration)
- **Chokepoints**: Flashing triangle markers with labels

### Interactions
- **Click mineral in panel**: Globe rotates to show that mineral's primary source, arcs animate in sequence (mine → process → component → platform)
- **Click any node**: Popup with details (country, production %, dependent platforms, risk factors)
- **Hover arc**: Show route details (origin → destination, volume, chokepoints traversed)
- **Toggle multiple minerals**: Overlay multiple chains to see convergence points

## Tier Color Scheme
- Tier 1 Mining: `#10b981` (green)
- Tier 2 Processing: `#8b5cf6` (purple)
- Tier 3 Components: `#f59e0b` (amber)
- Tier 4 Platforms: `#00d4ff` (cyan)

## Risk Classification
For each mineral, risk level determined by:
- **Critical**: HHI > 5000 OR single country > 70% of processing
- **High**: HHI > 3000 OR sanctioned country in top 3 producers
- **Medium**: HHI > 1500 OR chokepoint dependency
- **Low**: HHI < 1500, diversified sources

## Implementation Sequence
1. Research and compile real data for all 30 minerals (research agent)
2. Create `mineral_supply_chains.py` with the data
3. Create `globe_routes.py` API
4. Add CesiumJS to index.html with the layer panel and globe
5. Wire up the data and interactions
6. Test with real data
