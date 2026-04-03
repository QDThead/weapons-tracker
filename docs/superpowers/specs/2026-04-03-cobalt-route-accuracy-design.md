# Design Spec: Accurate Cobalt Supply Chain Routes (Sea + Overland)

**Date:** 2026-04-03
**Scope:** Cobalt mineral only on the 3D Supply Map (CesiumJS globe)

## Goal

Replace the current 6 approximate sea routes with a comprehensive, geographically accurate route network covering all cobalt logistics corridors — both maritime shipping lanes and overland truck/rail corridors. Each route category is a separate toggleable layer.

## Layer System

Three new layer IDs replace the single `shipping` layer:

| Layer ID | Name | Color | Style | Altitude | Default |
|----------|------|-------|-------|----------|---------|
| `sea-routes` | Sea Routes | `#5a7a9b` (steel blue) | Dashed polyline | 5,000m | ON |
| `overland-routes` | Overland Routes | `#a89060` (ochre) | Solid polyline | 500m | ON |
| `route-labels` | Route Labels | `#999` | Midpoint text | 8,000m (sea) / 2,000m (overland) | ON |

The existing `shipping` layer ID is retired. `chokepoints` and `ports` layers remain unchanged.

## Route Rendering

### Sea Routes
- `PolylineDashMaterialProperty` with risk-based color override:
  - CRITICAL: `#D80621` (DND red), width 4, dash 8
  - HIGH: `#a89060` (ochre), width 3, dash 12
  - MEDIUM: `#eab308` (amber), width 2.5, dash 14
  - LOW: `#6b9080` (sage), width 2, dash 16
- Alpha: 0.85
- Altitude: 5,000m (above terrain, below flow arcs)

### Overland Routes
- `PolylineGlowMaterialProperty` with `glowPower: 0.15` for subtle ground glow:
  - Truck/Road: `#a89060` (ochre), width 3
  - Rail: `#5a7a9b` (steel blue), width 2.5
- Alpha: 0.8
- Altitude: 500m (hugs terrain)

### Route Labels
- Placed at the geographic midpoint of each route
- Format: `ROUTE NAME | XX days`
- Font: `9px JetBrains Mono`, muted color
- `disableDepthTestDistance: POSITIVE_INFINITY` so always visible

### Connected Routes
Where an overland segment feeds into a sea segment (e.g., DRC truck → Durban → ship to China), both are rendered independently. The overland route ends at the port and the sea route starts at the same port — they share the junction point so they appear connected on the globe.

## Complete Route Inventory

### Sea Routes (10)

#### SR-1: Durban to Shanghai (DRC primary to China)
- **Risk:** CRITICAL
- **Transit:** ~30 days sea
- **Form:** Cobalt hydroxide (wet paste)
- **Volume:** ~50-55% of global cobalt
- **Risk reason:** Malacca Strait chokepoint, South China Sea tensions, Chinese-controlled at both ends
- **Chokepoints:** Mozambique Channel, Strait of Malacca, South China Sea
- **Waypoints:** Durban → south of Madagascar → across Indian Ocean → Malacca Strait → Singapore → South China Sea → Shanghai/Ningbo
- **Coordinates (approx 15 pts):**
  ```
  [31.03, -29.87], [35.0, -27.0], [40.0, -20.0], [45.0, -12.0],
  [50.0, -5.0], [60.0, 0.0], [72.0, 5.0], [80.0, 5.5],
  [90.0, 4.0], [98.0, 3.0], [103.5, 1.3], [105.0, 2.5],
  [110.0, 7.0], [115.0, 15.0], [120.0, 25.0], [122.0, 31.2]
  ```

#### SR-2: Dar es Salaam to Shanghai (eastern DRC corridor to China)
- **Risk:** HIGH
- **Transit:** ~25 days sea
- **Form:** Cobalt hydroxide
- **Volume:** ~10-15% of global cobalt
- **Risk reason:** TAZARA feeds this, Malacca chokepoint, Dar port congestion
- **Chokepoints:** Strait of Malacca, South China Sea
- **Waypoints:** Dar es Salaam → Mozambique Channel → Indian Ocean → Malacca → Shanghai
- **Coordinates (~14 pts):**
  ```
  [39.29, -6.82], [42.0, -5.0], [48.0, -2.0], [55.0, 2.0],
  [65.0, 4.0], [75.0, 5.5], [85.0, 5.0], [93.0, 3.5],
  [98.0, 3.0], [103.5, 1.3], [105.0, 2.5], [110.0, 7.0],
  [117.0, 18.0], [122.0, 31.2]
  ```

#### SR-3: Durban to Antwerp (DRC to Europe via Cape)
- **Risk:** CRITICAL
- **Transit:** ~28-35 days (Cape route, avoiding Red Sea since 2024 Houthi disruptions)
- **Form:** Cobalt hydroxide, concentrate
- **Risk reason:** Houthi Red Sea attacks forced Cape routing (+10-14 days), DRC origin risk
- **Chokepoints:** Cape of Good Hope (weather), English Channel
- **Waypoints:** Durban → south tip of Africa → up West African coast → Bay of Biscay → English Channel → Antwerp
- **Coordinates (~16 pts):**
  ```
  [31.03, -29.87], [28.0, -33.0], [18.5, -34.4], [14.0, -30.0],
  [10.0, -20.0], [5.0, -10.0], [0.0, 0.0], [-5.0, 10.0],
  [-10.0, 20.0], [-12.0, 30.0], [-10.0, 40.0], [-5.0, 47.0],
  [-2.0, 49.0], [1.0, 50.5], [2.5, 51.0], [4.4, 51.23]
  ```

#### SR-4: Lobito to Halifax (emerging Atlantic corridor)
- **Risk:** MEDIUM
- **Transit:** ~20 days
- **Form:** Cobalt hydroxide, copper-cobalt concentrate
- **Risk reason:** New corridor (first shipments 2026), bypasses Chinese logistics and Malacca, DRC origin risk remains
- **Chokepoints:** None (open Atlantic — strategic value)
- **Waypoints:** Lobito → up West African coast → mid-Atlantic → Nova Scotia → Halifax
- **Coordinates (~12 pts):**
  ```
  [13.54, -12.35], [10.0, -8.0], [5.0, 0.0], [-5.0, 10.0],
  [-15.0, 20.0], [-25.0, 28.0], [-35.0, 34.0], [-45.0, 38.0],
  [-52.0, 41.0], [-58.0, 43.0], [-62.0, 44.0], [-63.57, 44.65]
  ```

#### SR-5: Shanghai to Vancouver (refined cobalt to Canada)
- **Risk:** CRITICAL
- **Transit:** ~16 days
- **Form:** Refined cobalt metal, cobalt sulfate
- **Risk reason:** Single-country processing dependency (China 80%), export controls risk, Taiwan Strait
- **Chokepoints:** Taiwan Strait vicinity, open Pacific
- **Waypoints:** Shanghai → East China Sea → North Pacific Great Circle → Vancouver
- **Coordinates (~12 pts):**
  ```
  [121.5, 31.2], [125.0, 33.0], [132.0, 35.0], [140.0, 38.0],
  [152.0, 42.0], [165.0, 46.0], [180.0, 48.5], [-170.0, 49.5],
  [-155.0, 50.5], [-140.0, 50.5], [-130.0, 49.5], [-123.11, 49.29]
  ```

#### SR-6: Kokkola/Hoboken to Montreal (European refined to Canada)
- **Risk:** LOW
- **Transit:** ~14 days
- **Form:** Cobalt metal, chemicals, cathode precursors
- **Risk reason:** NATO-allied sources, open Atlantic, seasonal St. Lawrence ice
- **Chokepoints:** St. Lawrence Seaway (seasonal ice Dec-Mar)
- **Two origin branches merge in the North Sea:**
  - Finland branch: Kokkola [23.13, 63.84] → Baltic → Skagerrak → North Sea
  - Belgium branch: Hoboken [4.34, 51.16] → English Channel → North Sea
- **Merged coordinates (~14 pts, Finland branch shown):**
  ```
  [23.13, 63.84], [20.0, 58.0], [12.0, 56.0], [5.0, 54.0],
  [0.0, 52.0], [-5.0, 50.5], [-12.0, 50.0], [-22.0, 49.5],
  [-35.0, 49.0], [-48.0, 48.0], [-55.0, 48.0], [-62.0, 47.5],
  [-68.0, 47.0], [-73.55, 45.50]
  ```
- **Belgium branch coordinates (~10 pts):**
  ```
  [4.34, 51.16], [2.0, 51.0], [0.0, 51.5], [-5.0, 50.5],
  [-12.0, 50.0], [-22.0, 49.5], [-35.0, 49.0], [-48.0, 48.0],
  [-55.0, 48.0], [-62.0, 47.5], [-68.0, 47.0], [-73.55, 45.50]
  ```

#### SR-7: Esperance to Shanghai (Australian cobalt to China)
- **Risk:** MEDIUM
- **Transit:** ~22 days
- **Form:** Mixed hydroxide precipitate (MHP)
- **Risk reason:** Malacca chokepoint, remote origin
- **Chokepoints:** Strait of Malacca
- **Waypoints:** Esperance → Indian Ocean → Sunda/Malacca Strait → Shanghai
- **Coordinates (~12 pts):**
  ```
  [121.89, -33.86], [115.0, -30.0], [108.0, -22.0],
  [105.0, -12.0], [103.0, -5.0], [103.5, 1.3],
  [105.0, 3.0], [108.0, 8.0], [112.0, 15.0],
  [117.0, 22.0], [120.0, 28.0], [122.0, 31.2]
  ```

#### SR-8: Moa to Montreal (Cuban MSP to Canada)
- **Risk:** HIGH
- **Transit:** ~12 days sea
- **Form:** Mixed sulphide precipitate (MSP)
- **Risk reason:** US sanctions (Helms-Burton), Cuban instability, hurricane corridor, no US port access
- **Chokepoints:** Florida Strait (cannot dock US), St. Lawrence Seaway
- **Waypoints:** Moa Bay → Windward Passage → up US east coast (offshore) → Gulf of St. Lawrence → Montreal
- **Coordinates (~12 pts):**
  ```
  [-74.94, 20.62], [-74.0, 21.5], [-73.0, 24.0],
  [-72.0, 28.0], [-70.0, 32.0], [-68.0, 36.0],
  [-65.0, 40.0], [-62.0, 43.0], [-59.0, 46.0],
  [-57.0, 47.5], [-62.0, 48.0], [-68.0, 47.5],
  [-73.55, 45.50]
  ```

#### SR-9: Voisey's Bay to Long Harbour (Labrador coastal)
- **Risk:** MEDIUM
- **Transit:** ~3-4 days
- **Form:** Nickel-copper-cobalt concentrate
- **Risk reason:** Ice/icebergs Nov-Jun, harsh weather, remote
- **Chokepoints:** Labrador Sea ice (seasonal)
- **Waypoints:** Edwards Cove → down Labrador coast → around Newfoundland → Placentia Bay
- **Coordinates (~8 pts):**
  ```
  [-62.10, 56.33], [-60.0, 54.0], [-56.0, 51.5],
  [-53.5, 49.5], [-52.5, 48.0], [-53.0, 47.5],
  [-53.82, 47.42]
  ```

#### SR-10: Raglan to Sorel-Tracy (Arctic to St. Lawrence)
- **Risk:** MEDIUM-HIGH
- **Transit:** ~7-10 days
- **Form:** Nickel-cobalt concentrate
- **Risk reason:** 4-month shipping window (Jul-Oct), Hudson Strait ice, extreme remoteness
- **Chokepoints:** Hudson Strait (ice)
- **Waypoints:** Deception Bay → Hudson Strait → Labrador Sea → Gulf of St. Lawrence → Sorel-Tracy
- **Coordinates (~10 pts):**
  ```
  [-74.70, 62.15], [-72.0, 61.5], [-67.0, 60.5],
  [-62.0, 58.0], [-58.0, 55.0], [-55.0, 51.0],
  [-57.0, 49.0], [-60.0, 48.5], [-66.0, 48.0],
  [-71.0, 46.5], [-73.12, 46.05]
  ```

### Overland Routes (5)

#### OL-1: DRC Mine Corridor (Kolwezi to Kasumbalesa)
- **Risk:** HIGH
- **Transit:** 2-3 days truck
- **Mode:** Truck (N1/N39 national roads)
- **Risk reason:** Poor road infrastructure, rainy season degradation, security risk, artisanal mining material enters chain here
- **Waypoints:** Kolwezi → Likasi → Lubumbashi → Kasumbalesa border
- **Coordinates (~8 pts):**
  ```
  [25.47, -10.71], [25.80, -10.78], [26.10, -10.62],
  [26.73, -10.98], [27.10, -11.20], [27.48, -11.66],
  [28.10, -12.10], [28.52, -12.62]
  ```
- **Connects:** All 4 DRC mines → feeds SR-1 (via Durban) and SR-2 (via Dar es Salaam)

#### OL-2: Zambia-South Africa Corridor (Kasumbalesa to Durban)
- **Risk:** MEDIUM
- **Transit:** 7-10 days road/rail
- **Mode:** Mixed road + rail (Zambia Railways → Transnet rail to Durban)
- **Risk reason:** Kasumbalesa border bottleneck (multi-day queues), Zambian fuel shortages, long distance
- **Waypoints:** Kasumbalesa → Ndola → Kapiri Mposhi → Lusaka → Harare corridor → Johannesburg → Durban
- **Coordinates (~12 pts):**
  ```
  [28.52, -12.62], [28.63, -12.98], [28.68, -14.97],
  [28.32, -15.39], [28.50, -18.0], [29.0, -20.0],
  [29.80, -22.0], [29.50, -24.0], [28.50, -25.5],
  [28.04, -26.20], [29.50, -28.0], [31.03, -29.87]
  ```
- **Connects:** OL-1 terminus → SR-1 origin (Durban)

#### OL-3: TAZARA Eastern Rail (Kapiri Mposhi to Dar es Salaam)
- **Risk:** MEDIUM-HIGH
- **Transit:** 4-6 days rail
- **Mode:** Rail (TAZARA railway)
- **Risk reason:** Chronic TAZARA underinvestment, low speeds, maintenance issues, Dar es Salaam port congestion
- **Waypoints:** Kapiri Mposhi → Serenje → Mpika → Mbeya → Dodoma corridor → Dar es Salaam
- **Coordinates (~10 pts):**
  ```
  [28.68, -14.97], [29.20, -13.20], [30.50, -11.80],
  [31.50, -10.50], [32.77, -9.34], [33.50, -8.90],
  [34.80, -8.00], [36.00, -7.50], [38.00, -7.00],
  [39.29, -6.82]
  ```
- **Connects:** Branches off OL-2 at Kapiri Mposhi → feeds SR-2 origin (Dar es Salaam)

#### OL-4: Chinese Inland Rail (Tianjin to Jinchang)
- **Risk:** LOW
- **Transit:** 3-5 days rail
- **Mode:** Rail (China Rail heavy freight, Lanzhou-Xinjiang corridor)
- **Risk reason:** World-class rail infrastructure, but 2,000km inland adds cost
- **Waypoints:** Tianjin port → Zhengzhou → Xi'an → Lanzhou → Jinchang
- **Coordinates (~8 pts):**
  ```
  [117.73, 38.99], [114.40, 36.50], [113.65, 34.75],
  [110.50, 34.50], [108.94, 34.26], [105.70, 35.60],
  [103.83, 36.06], [102.19, 38.50]
  ```
- **Connects:** Chinese ports (SR-1/SR-2 terminus) → Jinchuan Group refinery

#### OL-5: Canadian Transcontinental Rail (Montreal to Fort Saskatchewan)
- **Risk:** LOW
- **Transit:** 4-5 days rail
- **Mode:** Rail (CN Rail)
- **Risk reason:** Well-established infrastructure, labour disputes can disrupt
- **Waypoints:** Montreal → Ottawa → Sudbury → Sault Ste. Marie → Winnipeg → Saskatoon → Edmonton → Fort Saskatchewan
- **Coordinates (~10 pts):**
  ```
  [-73.55, 45.50], [-75.70, 45.42], [-79.40, 43.65],
  [-81.00, 46.50], [-84.30, 46.50], [-89.20, 48.40],
  [-97.14, 49.90], [-106.67, 52.13], [-113.49, 53.54],
  [-113.21, 53.72]
  ```
- **Connects:** SR-6/SR-8 terminus (Montreal) → Fort Saskatchewan refinery; also passes through Sudbury Basin

## Data Architecture

### Backend: `mineral_supply_chains.py`
- Replace existing `shipping_routes` array with two arrays: `sea_routes` and `overland_routes`
- Each route object includes: `name`, `description`, `form`, `transit_days`, `risk`, `risk_reason`, `mode` (sea/truck/rail/mixed), `waypoints` (lon/lat pairs), `chokepoints` (list), `volume_pct` (optional), `connects_to` (route IDs that this feeds into), `note` (optional)
- All waypoints stored as `[lon, lat]` (matching CesiumJS convention)

### API: `globe_routes.py`
- No changes needed — `sea_routes` and `overland_routes` are served as part of the mineral response

### Frontend: `index.html`
- Update `GLOBE_LAYERS` array: remove `shipping`, add `sea-routes`, `overland-routes`, `route-labels`
- Sea route renderer: reads `m.sea_routes`, draws dashed polylines at 5km altitude
- Overland route renderer: reads `m.overland_routes`, draws solid glow polylines at 500m
- Route label renderer: places midpoint labels for each route
- Route menu (upper-left panel): shows all routes grouped by sea/overland with risk badges
- Layer toggle: each category independently toggleable

## Migration
- Existing `shipping_routes` key in cobalt data → split into `sea_routes` and `overland_routes`
- Frontend code that reads `m.shipping_routes` → updated to read both new arrays
- Other minerals (non-cobalt) still use the old `shipping_routes` key and SEA_ROUTES fallback — no change needed for them
- The old `shipping` layer toggle is removed from GLOBE_LAYERS and replaced with the two new ones

## Testing
- Existing 266 unit tests should still pass (route data is structural, not tested by unit tests)
- Visual verification: load Cobalt on the 3D globe and confirm all 15 routes render with correct geography
- Layer toggles: verify sea routes, overland routes, and labels each toggle independently
