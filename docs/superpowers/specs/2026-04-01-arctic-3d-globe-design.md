# Arctic 3D CesiumJS Globe Design Spec

**Date**: 2026-04-01
**Goal**: Replace the 2D Leaflet map in the Arctic tab with a CesiumJS 3D globe showing all 7 intelligence layers, while keeping all existing KPI cards, tables, and charts unchanged.
**Scope**: Arctic tab map replacement only. No new API endpoints. No changes to data below the map.

---

## Architecture

- **Separate Cesium viewer**: New `arcticCesiumViewer` instance, independent from the Supply Chain `cesiumViewer`
- **Container**: Reuse existing `#arctic-main-map` div (currently holds Leaflet map)
- **Lifecycle**: Initialized on first Arctic tab open, persists for session duration
- **Styling**: Dark globe matching Supply Chain globe (CartoDB dark_nolabels tiles, `#0a0e1a` background, `#111827` globe base color)
- **Camera default**: Canadian perspective — position over ~65N, -95W, altitude ~12,000km, tilted ~30 degrees looking north toward Russia

## 7 Intelligence Layers

All layers are toggleable via a compact button bar above the globe.

### Layer 1: Military Bases (25)

**Data source**: `/arctic/bases` (existing endpoint, cached 1hr)

**Rendering**: Billboard entities with color-coded pins:
- Red (`#ef4444`): Russia (8 bases)
- Blue (`#3b82f6`): NATO (13 bases)
- Yellow (`#f59e0b`): China (2 bases)

**Pin sizing**: Pixel size scaled by threat level (1-5):
- Threat 1: 8px
- Threat 2-3: 12px
- Threat 4: 16px
- Threat 5: 20px

**Click popup**: Floating HTML overlay showing:
- Name, country, flag emoji
- Type (naval/air/ground/space/research), status badge
- Capability description
- Personnel count
- Threat level (color-coded badge)
- Distance to Ottawa, nearest Canadian base + distance
- Recent developments

**Labels**: Base name text labels, visible up to 8,000km camera distance. Font: JetBrains Mono 10px, same color as alliance.

### Layer 2: Arctic Shipping Routes (3)

**Data source**: Existing route waypoint arrays in `index.html` (lines 4756-4821)

**Rendering**: `Cesium.PolylineGraphics` following waypoint coordinates as great-circle arcs:

| Route | Color | Width | Style |
|-------|-------|-------|-------|
| Northern Sea Route | `#ef4444` (red) | 3px | Solid |
| Northwest Passage | `#3b82f6` (blue) | 3px | Dashed |
| Transpolar Route | `#a855f7` (purple) | 2px | Dotted |

**Chokepoint labels**: Billboard labels at key straits (Bering Strait, Vilkitsky Strait, Lancaster Sound, etc.) with small diamond markers.

**Route labels**: Floating labels at `labelPos` coordinates with route name + owner.

### Layer 3: Live Military Flights

**Data source**: `/arctic/flights` (existing endpoint, auto-refresh 60s)

**Rendering**: Point entities at reported altitude (or 10,000m default):
- Red: Russian military aircraft
- Blue: NATO/allied aircraft
- Yellow: Chinese aircraft
- Gray: Unclassified

**Labels**: Callsign + aircraft type (e.g., "RFF7710 Tu-95"), visible within 5,000km.

**Auto-refresh**: Clear and re-add flight entities every 60 seconds using existing `scheduleArcticRefresh()` pattern.

### Layer 4: Canadian ADIZ Boundary

**Data source**: Existing ADIZ polygon coordinates in `index.html`

**Rendering**: `Cesium.PolygonGraphics` with:
- Fill: `rgba(59, 130, 246, 0.08)` (very faint blue)
- Outline: `#3b82f6` at 1px, dashed
- Clamped to ground

### Layer 5: Arctic Ice Edge

**Data source**: Existing approximate ice edge coordinates in `index.html`

**Rendering**: `Cesium.PolylineGraphics`:
- Color: `rgba(255, 255, 255, 0.4)` (translucent white)
- Width: 1.5px
- Dash pattern: 12px dash, 8px gap
- Clamped to ground

### Layer 6: Base Network Connections

**Data source**: Computed from base positions at render time

**Rendering**: Great-circle arc polylines between bases of the same alliance:
- Russian network: red arcs (`rgba(239, 68, 68, 0.25)`), 1px
- NATO network: blue arcs (`rgba(59, 130, 246, 0.15)`), 1px
- Cross-alliance threat lines: dashed orange arcs from each adversary base to nearest Canadian base (`rgba(245, 158, 11, 0.3)`), 1px

**Filtering**: Only draw connections between bases within 3,000km of each other (prevents visual clutter from long-range lines).

### Layer 7: Weapon Range Rings

**Data source**: Derived from base capabilities in the base registry. Keyword matching on `capability` field.

**Weapon systems and ranges**:

| System | Range (km) | Color | Found at |
|--------|-----------|-------|----------|
| S-400 SAM | 400 | `rgba(239, 68, 68, 0.12)` | Rogachevo |
| Bastion anti-ship | 500 | `rgba(249, 115, 22, 0.12)` | Temp/Kotelny |
| Kinzhal air-launched | 2,000 | `rgba(239, 68, 68, 0.06)` | Olenya/Olenegorsk |
| Ground-Based Interceptor | 2,000 | `rgba(59, 130, 246, 0.06)` | Fort Greely |

**Rendering**: `Cesium.EllipseGraphics` centered on each base:
- Semi-transparent fill (very faint)
- Outline: same color at 0.4 opacity, 1px
- Clamped to ground
- Label at edge: weapon system name + range

**Overlap**: When multiple range rings overlap, the layered transparency creates natural "threat density" visualization — darker areas = more overlapping weapon coverage.

## Layer Toggle Controls

Compact button bar positioned above the globe (inside the existing card container):

```html
<div id="arctic-globe-controls" style="display:flex; gap:4px; margin-bottom:6px; flex-wrap:wrap;">
  <button class="arctic-layer-btn active" data-layer="bases">Bases</button>
  <button class="arctic-layer-btn active" data-layer="routes">Routes</button>
  <button class="arctic-layer-btn active" data-layer="flights">Flights</button>
  <button class="arctic-layer-btn active" data-layer="adiz">ADIZ</button>
  <button class="arctic-layer-btn active" data-layer="ice">Ice Edge</button>
  <button class="arctic-layer-btn active" data-layer="connections">Networks</button>
  <button class="arctic-layer-btn active" data-layer="ranges">Ranges</button>
</div>
```

Styling: Small pill buttons matching existing PSI sub-tab style. `active` class = filled cyan, inactive = outlined.

All layers ON by default. Click to toggle.

## Camera Configuration

**Initial view** (Canadian perspective looking north):
```javascript
arcticCesiumViewer.camera.setView({
    destination: Cesium.Cartesian3.fromDegrees(-95, 65, 12000000),
    orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-60),
        roll: 0,
    }
});
```

**Reset button**: Small "Reset View" button in the controls bar that flies back to the default camera position.

## Code Changes

### Files Modified

| File | Changes |
|------|---------|
| `src/static/index.html` | Replace Leaflet map init + rendering with CesiumJS globe init + 7 layer renderers. Add layer toggle controls. Remove Leaflet-specific Arctic code. Keep all non-map content unchanged. |

### Files NOT Modified

- `src/api/arctic_routes.py` — no changes, existing endpoints provide all needed data
- All other Python files — no backend changes

### Functions to Replace

| Current Function | Action |
|-----------------|--------|
| `renderArcticMainMap()` (~line 5015) | Replace entirely with `renderArcticGlobe()` |
| Leaflet map init (`L.map('arctic-main-map')`) | Replace with `new Cesium.Viewer('arctic-main-map')` |
| Leaflet marker/polyline code | Replace with Cesium entity code |

### Functions to Keep

| Function | Why |
|----------|-----|
| `loadArctic()` | Still fetches data from same endpoints |
| `renderArcticIntelTable()` | Table below map — unchanged |
| `renderArcticNatoBars()` | Chart below map — unchanged |
| `renderArcticVsChart()` | Chart below map — unchanged |
| `renderArcticNavalList()` | Panel below map — unchanged |
| `renderArcticTimeline()` | Chart below map — unchanged |
| `scheduleArcticRefresh()` | Still refreshes flights every 60s |

### Global Variables

| Variable | Change |
|----------|--------|
| `arcticMainMap` | Rename to `arcticCesiumViewer` — now a Cesium.Viewer instance |
| `arcticMainMarkers` | Remove — Cesium manages entities differently |
| `arcticMainLayers` | Replace with `arcticLayerEntities` — object keyed by layer name, each value is an array of Cesium entity references |

### New Functions

| Function | Purpose |
|----------|---------|
| `initArcticGlobe()` | Create Cesium.Viewer, configure dark styling, set camera |
| `renderArcticBases(bases)` | Add 25 base billboard entities with popups |
| `renderArcticRoutes()` | Add 3 shipping route polylines with chokepoint labels |
| `renderArcticFlights(flights)` | Add/refresh flight point entities |
| `renderArcticADIZ()` | Add ADIZ polygon |
| `renderArcticIceEdge()` | Add ice edge polyline |
| `renderArcticConnections(bases)` | Compute and draw base network arcs |
| `renderArcticRangeRings(bases)` | Add weapon range ellipses |
| `toggleArcticLayer(layerName)` | Show/hide all entities for a layer |
| `resetArcticCamera()` | Fly to default Canadian perspective |
| `setupArcticClickHandler()` | Handle click on base entities to show popup |

## Popup Design

Base click popup (HTML overlay positioned near clicked entity):

```
┌─────────────────────────────────────┐
│ 🇷🇺 Severomorsk              [×]    │
│ Naval Base • Active • Expanding     │
│─────────────────────────────────────│
│ Threat Level: ████████░░ 5/5        │
│                                     │
│ Northern Fleet HQ. Nuclear          │
│ submarine force. 6 Borei-A SSBNs... │
│                                     │
│ Personnel: ~15,000                  │
│ Distance to Ottawa: 6,800 km        │
│ Nearest Canadian: CFB Goose Bay     │
│ Distance: 4,200 km                  │
│─────────────────────────────────────│
│ Recent: MiG-31 deployments to       │
│ Nagurskoye for Arctic air patrols   │
└─────────────────────────────────────┘
```

Glass-morphism styling matching Supply Chain globe popups (`backdrop-filter: blur(16px)`, dark background).

## Test Plan

- Existing 283 tests must continue to pass (no Python changes)
- Manual verification:
  - Arctic tab opens, globe renders with dark styling
  - All 25 bases visible with correct colors and positions
  - 3 shipping routes render as arcs with labels
  - Live flights appear and refresh every 60s
  - ADIZ polygon visible as faint blue boundary
  - Ice edge line visible
  - Base connections drawn between allied bases
  - Range rings visible around equipped bases
  - Layer toggles show/hide each layer independently
  - Click on base shows popup with correct data
  - Reset View button returns to Canadian perspective
  - All content below map (tables, charts) still renders correctly
