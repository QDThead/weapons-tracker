# Arctic 3D CesiumJS Globe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 2D Leaflet map in the Arctic tab with a CesiumJS 3D globe showing 7 intelligence layers (bases, routes, flights, ADIZ, ice edge, connections, range rings).

**Architecture:** Single file change (index.html). Replace `renderArcticMainMap()` and its Leaflet init with a new `initArcticGlobe()` + per-layer render functions using CesiumJS. All data comes from existing endpoints (`/arctic/bases`, `/arctic/flights`). Existing constants (`ARCTIC_ROUTES`, `CADIZ_BOUNDARY`, `ICE_EDGE`, `WATERWAY_LABELS`) are reused. All content below the map (tables, charts, panels) remains unchanged.

**Tech Stack:** CesiumJS 1.119 (already loaded via CDN), existing FastAPI endpoints

**Design spec:** `docs/superpowers/specs/2026-04-01-arctic-3d-globe-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/static/index.html` | Modify | Replace Leaflet Arctic map with CesiumJS globe |

**No Python files modified. No new files created. No new endpoints.**

### Sections within index.html

| Section | Lines (approx) | Action |
|---------|----------------|--------|
| Global variables | 4745-4753 | Replace `arcticMainMap`, `arcticMainMarkers`, `arcticMainLayers` with CesiumJS equivalents |
| HTML container | 1483-1498 | Add layer toggle button bar above map div; keep map div |
| `renderArcticMainMap()` | 5015-5238 | Delete entirely, replace with new functions |
| `updateArcticMainMapFlights()` | 5240-5243 | Replace with CesiumJS flight refresh |
| `loadArctic()` | 4891-4899 | Keep — still fetches from same endpoints. Update call to render function |

### Functions to Create

| Function | Purpose |
|----------|---------|
| `initArcticGlobe()` | Create `arcticCesiumViewer`, configure dark styling, set Canadian perspective camera |
| `renderArcticBases(bases)` | Add 25 base point entities with labels |
| `renderArcticRoutes()` | Add 3 shipping route polylines from `ARCTIC_ROUTES` |
| `renderArcticFlights(flights)` | Add/refresh flight point entities |
| `renderArcticADIZ()` | Add CADIZ polygon from `CADIZ_BOUNDARY` |
| `renderArcticIceEdge()` | Add ice edge polyline from `ICE_EDGE` |
| `renderArcticConnections(bases)` | Draw alliance network arcs + distance lines |
| `renderArcticRangeRings(bases)` | Add weapon range ellipses for equipped bases |
| `toggleArcticLayer(layerName)` | Show/hide entities by layer name |
| `resetArcticCamera()` | Fly back to default Canadian perspective |
| `setupArcticPopupHandler()` | Handle click on base entities to show HTML popup |

---

### Task 1: Globe Init + Base Layer (Bases)

**Files:**
- Modify: `src/static/index.html` — global vars (~line 4745), HTML container (~line 1483), new `initArcticGlobe()` and `renderArcticBases()`, replace call in `loadArctic()`

This is the biggest task — it establishes the CesiumJS viewer and renders the core base markers. All subsequent tasks add layers on top.

- [ ] **Step 1: Update global variables**

Replace the Arctic global variables block (lines 4745-4753):

```javascript
// Old:
let arcticTabLoaded = false;
let arcticMainMap = null;
let arcticMainMarkers = [];
let arcticMainLayers = [];
let arcticAirspaceMap = null;
let arcticAirspaceMarkers = [];
let arcticBasesData = null;
let arcticIntelSortCol = 'threat_level';
let arcticIntelSortAsc = false;

// New:
let arcticTabLoaded = false;
let arcticCesiumViewer = null;
let arcticGlobeInitialized = false;
let arcticLayerEntities = { bases: [], routes: [], flights: [], adiz: [], ice: [], connections: [], ranges: [] };
let arcticLayerVisible = { bases: true, routes: true, flights: true, adiz: true, ice: true, connections: true, ranges: true };
let arcticAirspaceMap = null;
let arcticAirspaceMarkers = [];
let arcticBasesData = null;
let arcticIntelSortCol = 'threat_level';
let arcticIntelSortAsc = false;
```

- [ ] **Step 2: Add layer toggle button bar to HTML**

In the Arctic map card (around line 1483-1497), add a toggle button bar between the legend and the map div. Replace the existing legend div + map div:

```html
    <div class="card" style="margin-bottom:20px;">
      <h2>Arctic Force Balance Map <span id="arctic-map-time" style="float:right;font-size:11px;color:var(--text-dim);text-transform:none;letter-spacing:0"></span></h2>
      <div id="arctic-globe-controls" style="display:flex; gap:4px; margin-bottom:8px; flex-wrap:wrap; align-items:center;">
        <button class="arctic-layer-btn active" data-layer="bases" onclick="toggleArcticLayer('bases',this)">Bases</button>
        <button class="arctic-layer-btn active" data-layer="routes" onclick="toggleArcticLayer('routes',this)">Routes</button>
        <button class="arctic-layer-btn active" data-layer="flights" onclick="toggleArcticLayer('flights',this)">Flights</button>
        <button class="arctic-layer-btn active" data-layer="adiz" onclick="toggleArcticLayer('adiz',this)">ADIZ</button>
        <button class="arctic-layer-btn active" data-layer="ice" onclick="toggleArcticLayer('ice',this)">Ice Edge</button>
        <button class="arctic-layer-btn active" data-layer="connections" onclick="toggleArcticLayer('connections',this)">Networks</button>
        <button class="arctic-layer-btn active" data-layer="ranges" onclick="toggleArcticLayer('ranges',this)">Ranges</button>
        <button class="arctic-layer-btn" onclick="resetArcticCamera()" style="margin-left:auto;">Reset View</button>
      </div>
      <div class="arctic-base-legend" style="font-size:10px; margin-bottom:6px;">
        <div class="leg-item"><div class="leg-dot bg-russia"></div> Russia</div>
        <div class="leg-item"><div class="leg-dot bg-nato"></div> NATO</div>
        <div class="leg-item"><div class="leg-dot bg-china"></div> China</div>
        <div class="leg-item"><div class="leg-dot bg-canada"></div> Canada</div>
        <div class="leg-item"><div class="leg-pulse"></div> Expanding</div>
        <div class="leg-item" style="color:var(--text-dim);">Size = threat level</div>
      </div>
      <div id="arctic-main-map" style="height:600px;border-radius:8px;overflow:hidden;" aria-label="Arctic force balance 3D globe showing military bases, shipping routes, and threat levels"></div>
    </div>
```

- [ ] **Step 3: Add CSS for layer toggle buttons**

Add in the existing `<style>` block (near other Arctic CSS):

```css
.arctic-layer-btn {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 3px 10px;
  border-radius: 12px;
  border: 1px solid rgba(0,212,255,0.3);
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  transition: all 0.2s;
}
.arctic-layer-btn.active {
  background: rgba(0,212,255,0.15);
  color: var(--accent);
  border-color: var(--accent);
}
.arctic-layer-btn:hover {
  border-color: var(--accent);
}
```

- [ ] **Step 4: Write `initArcticGlobe()` function**

Add this function after the existing Arctic constants (after `ICE_EDGE`, around line 4831), before `loadArctic()`:

```javascript
function initArcticGlobe() {
  if (arcticGlobeInitialized) return;
  arcticGlobeInitialized = true;

  try {
    arcticCesiumViewer = new Cesium.Viewer('arctic-main-map', {
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
      requestRenderMode: true,
      maximumRenderTimeChange: Infinity,
      creditContainer: document.createElement('div'),
    });

    arcticCesiumViewer.scene.imageryLayers.addImageryProvider(
      new Cesium.UrlTemplateImageryProvider({
        url: 'https://cartodb-basemaps-{s}.global.ssl.fastly.net/dark_nolabels/{z}/{x}/{y}.png',
        subdomains: 'abcd',
        maximumLevel: 6,
        credit: 'CartoDB Dark Matter',
      })
    );

    var scene = arcticCesiumViewer.scene;
    scene.backgroundColor = Cesium.Color.fromCssColorString('#0a0e1a');
    scene.globe.baseColor = Cesium.Color.fromCssColorString('#111827');
    scene.globe.showGroundAtmosphere = false;
    scene.globe.enableLighting = false;
    if (scene.skyBox) scene.skyBox.show = false;
    if (scene.sun) scene.sun.show = false;
    if (scene.moon) scene.moon.show = false;
    if (scene.skyAtmosphere) scene.skyAtmosphere.show = false;

    // Canadian perspective looking north toward Russia
    arcticCesiumViewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(-95, 65, 12000000),
      orientation: {
        heading: Cesium.Math.toRadians(0),
        pitch: Cesium.Math.toRadians(-60),
        roll: 0,
      }
    });

    setupArcticPopupHandler();
  } catch (e) {
    document.getElementById('arctic-main-map').innerHTML =
      '<div style="color:var(--accent2); text-align:center; padding:60px;">Failed to initialize Arctic 3D globe: ' + esc(e.message) + '</div>';
  }
}
```

- [ ] **Step 5: Write `renderArcticBases()` function**

Add after `initArcticGlobe()`:

```javascript
function renderArcticBases(bases) {
  // Clear old base entities
  arcticLayerEntities.bases.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.bases = [];

  var allianceColors = {
    russia: Cesium.Color.fromCssColorString('#ef4444'),
    nato: Cesium.Color.fromCssColorString('#3b82f6'),
    china: Cesium.Color.fromCssColorString('#f59e0b'),
  };

  bases.forEach(function(base) {
    var color = allianceColors[base.alliance] || Cesium.Color.fromCssColorString('#3b82f6');
    if (base.country === 'Canada') color = Cesium.Color.fromCssColorString('#10b981');
    var threat = base.threat_level || 1;
    var pixelSize = threat <= 1 ? 8 : threat <= 3 ? 12 : threat <= 4 ? 16 : 20;

    var entity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(base.lon, base.lat),
      point: {
        pixelSize: pixelSize,
        color: color.withAlpha(0.6),
        outlineColor: color,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: (base.flag_emoji || '') + ' ' + base.name.split(',')[0],
        font: '11px JetBrains Mono, monospace',
        fillColor: color,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 3,
        outlineColor: Cesium.Color.BLACK,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -(pixelSize + 4)),
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      properties: {
        type: 'arctic-base',
        name: base.name,
        country: base.country,
        alliance: base.alliance,
        baseType: base.type,
        status: base.status,
        capability: base.capability,
        personnel: base.personnel || 0,
        threat_level: threat,
        flag_emoji: base.flag_emoji || '',
        recent_developments: base.recent_developments || '',
        distance_to_ottawa_km: base.distance_to_ottawa_km || 0,
        nearest_canadian_base: base.nearest_canadian_base || '',
        distance_to_nearest_canadian_km: base.distance_to_nearest_canadian_km || 0,
        arms_imports_tiv: base.arms_imports_tiv || 0,
      },
      show: arcticLayerVisible.bases,
    });
    arcticLayerEntities.bases.push(entity);
  });
}
```

- [ ] **Step 6: Write `setupArcticPopupHandler()` function**

Add after `renderArcticBases()`:

```javascript
function setupArcticPopupHandler() {
  var popupDiv = document.createElement('div');
  popupDiv.id = 'arctic-base-popup-overlay';
  popupDiv.style.cssText = 'display:none;position:absolute;z-index:999;max-width:320px;background:rgba(10,14,26,0.92);backdrop-filter:blur(16px);border:1px solid rgba(0,212,255,0.2);border-radius:8px;padding:14px;color:#e2e8f0;font-size:12px;pointer-events:auto;';
  document.getElementById('arctic-main-map').appendChild(popupDiv);

  var handler = new Cesium.ScreenSpaceEventHandler(arcticCesiumViewer.scene.canvas);
  handler.setInputAction(function(click) {
    var picked = arcticCesiumViewer.scene.pick(click.position);
    if (Cesium.defined(picked) && picked.id && picked.id.properties && picked.id.properties.type &&
        picked.id.properties.type.getValue() === 'arctic-base') {
      var p = picked.id.properties;
      var threat = p.threat_level.getValue();
      var threatColor = threat >= 4 ? '#ef4444' : threat >= 3 ? '#fb923c' : '#00d4ff';
      var distStr = p.country.getValue() !== 'Canada'
        ? '<div style="margin-top:4px;">Nearest Canadian base: <b>' + esc(p.nearest_canadian_base.getValue()) + '</b> (' + (p.distance_to_nearest_canadian_km.getValue() || 0).toLocaleString() + ' km)</div>'
        : '';
      var armsStr = p.arms_imports_tiv.getValue() > 0
        ? '<div style="margin-top:2px;color:var(--text-dim);">Country arms imports: ' + p.arms_imports_tiv.getValue().toFixed(0) + ' TIV</div>'
        : '';

      popupDiv.innerHTML =
        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">' +
          '<b style="font-size:14px;">' + esc(p.flag_emoji.getValue()) + ' ' + esc(p.name.getValue()) + '</b>' +
          '<span onclick="document.getElementById(\'arctic-base-popup-overlay\').style.display=\'none\'" style="cursor:pointer;color:var(--text-dim);font-size:16px;">&times;</span>' +
        '</div>' +
        '<div style="color:var(--text-dim);margin-bottom:6px;">' + esc(p.baseType.getValue()) + ' base &mdash; ' + esc(p.country.getValue()) +
          ' &mdash; <span style="text-transform:uppercase;color:' + (p.status.getValue() === 'expanding' ? '#f59e0b' : '#10b981') + ';">' + esc(p.status.getValue()) + '</span></div>' +
        '<div style="margin-bottom:6px;">Threat: <b style="color:' + threatColor + ';">' + threat + '/5</b>' +
          (p.personnel.getValue() > 0 ? ' &mdash; ~' + p.personnel.getValue().toLocaleString() + ' personnel' : '') + '</div>' +
        '<div style="margin-bottom:6px;line-height:1.4;">' + esc(p.capability.getValue()) + '</div>' +
        distStr + armsStr +
        '<div style="margin-top:6px;color:var(--text-dim);font-size:11px;line-height:1.4;">' + esc(p.recent_developments.getValue()) + '</div>';

      var canvasPos = click.position;
      popupDiv.style.left = (canvasPos.x + 15) + 'px';
      popupDiv.style.top = (canvasPos.y - 10) + 'px';
      popupDiv.style.display = 'block';
    } else {
      popupDiv.style.display = 'none';
    }
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
}
```

- [ ] **Step 7: Write `toggleArcticLayer()` and `resetArcticCamera()` functions**

```javascript
function toggleArcticLayer(layerName, btn) {
  arcticLayerVisible[layerName] = !arcticLayerVisible[layerName];
  var show = arcticLayerVisible[layerName];
  if (btn) btn.classList.toggle('active', show);
  (arcticLayerEntities[layerName] || []).forEach(function(e) { e.show = show; });
  if (arcticCesiumViewer) arcticCesiumViewer.scene.requestRender();
}

function resetArcticCamera() {
  if (!arcticCesiumViewer) return;
  arcticCesiumViewer.camera.flyTo({
    destination: Cesium.Cartesian3.fromDegrees(-95, 65, 12000000),
    orientation: {
      heading: Cesium.Math.toRadians(0),
      pitch: Cesium.Math.toRadians(-60),
      roll: 0,
    },
    duration: 1.5,
  });
}
```

- [ ] **Step 8: Update `loadArctic()` to use new globe**

In `loadArctic()` (around line 4960), replace the call to `renderArcticMainMap(arcticBasesData, flights)` with:

```javascript
  // Initialize Arctic 3D globe (first time only)
  initArcticGlobe();

  // Render base layer
  if (arcticBasesData && arcticBasesData.bases) {
    renderArcticBases(arcticBasesData.bases);
  }
```

- [ ] **Step 9: Delete the old `renderArcticMainMap()` function**

Delete the entire `renderArcticMainMap()` function (lines 5015-5238) and `updateArcticMainMapFlights()` (lines 5240-5243). These are replaced by the new CesiumJS functions.

- [ ] **Step 10: Verify the globe renders**

Run the server: `python -m src.main`
Open http://localhost:8000, navigate to Arctic tab.
Expected: 3D globe with dark styling, Canadian perspective, 25 base markers with labels, click popups working.

- [ ] **Step 11: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): replace Leaflet map with CesiumJS 3D globe + base layer"
```

---

### Task 2: Shipping Routes + ADIZ + Ice Edge

**Files:**
- Modify: `src/static/index.html` — add 3 render functions after the base functions

- [ ] **Step 1: Write `renderArcticRoutes()` function**

Add after the Task 1 functions:

```javascript
function renderArcticRoutes() {
  arcticLayerEntities.routes.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.routes = [];

  var routeStyles = {
    'Northern Sea Route': { color: '#ef4444', width: 3, dash: false },
    'Northwest Passage': { color: '#3b82f6', width: 3, dash: true },
    'Transpolar Route': { color: '#a855f7', width: 2, dash: true },
  };

  ARCTIC_ROUTES.forEach(function(route) {
    var style = routeStyles[route.name] || { color: '#64748b', width: 2, dash: true };
    var cesiumColor = Cesium.Color.fromCssColorString(style.color);

    // Build positions array from [lat,lon] waypoints
    var positions = [];
    route.points.forEach(function(pt) {
      positions.push(Cesium.Cartesian3.fromDegrees(pt[1], pt[0]));
    });

    // Route polyline
    var material = style.dash
      ? new Cesium.PolylineDashMaterialProperty({ color: cesiumColor.withAlpha(0.7), dashLength: 14 })
      : cesiumColor.withAlpha(0.7);

    var routeEntity = arcticCesiumViewer.entities.add({
      polyline: {
        positions: positions,
        width: style.width,
        material: material,
        clampToGround: true,
      },
      show: arcticLayerVisible.routes,
    });
    arcticLayerEntities.routes.push(routeEntity);

    // Route name label
    var labelEntity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(route.labelPos[1], route.labelPos[0]),
      label: {
        text: route.flag + ' ' + route.name,
        font: '12px JetBrains Mono, monospace',
        fillColor: cesiumColor,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 3,
        outlineColor: Cesium.Color.BLACK,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
      },
      show: arcticLayerVisible.routes,
    });
    arcticLayerEntities.routes.push(labelEntity);

    // Chokepoint markers
    (route.keyPoints || []).forEach(function(kp) {
      var kpEntity = arcticCesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(kp.lon, kp.lat),
        point: {
          pixelSize: 5,
          color: cesiumColor,
          outlineColor: Cesium.Color.BLACK,
          outlineWidth: 1,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        label: {
          text: kp.name,
          font: '9px JetBrains Mono, monospace',
          fillColor: cesiumColor.withAlpha(0.7),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          outlineWidth: 2,
          outlineColor: Cesium.Color.BLACK,
          pixelOffset: new Cesium.Cartesian2(8, 0),
          horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000),
        },
        show: arcticLayerVisible.routes,
      });
      arcticLayerEntities.routes.push(kpEntity);
    });
  });

  // Waterway labels
  WATERWAY_LABELS.forEach(function(wl) {
    var wlEntity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(wl.lon, wl.lat),
      label: {
        text: wl.name,
        font: 'italic 10px IBM Plex Sans, sans-serif',
        fillColor: Cesium.Color.WHITE.withAlpha(0.35),
        style: Cesium.LabelStyle.FILL,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000),
      },
      show: arcticLayerVisible.routes,
    });
    arcticLayerEntities.routes.push(wlEntity);
  });
}
```

- [ ] **Step 2: Write `renderArcticADIZ()` function**

```javascript
function renderArcticADIZ() {
  arcticLayerEntities.adiz.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.adiz = [];

  // Convert [lat,lon] pairs to Cesium positions
  var positions = CADIZ_BOUNDARY.map(function(pt) {
    return Cesium.Cartesian3.fromDegrees(pt[1], pt[0]);
  });

  var adizEntity = arcticCesiumViewer.entities.add({
    polygon: {
      hierarchy: new Cesium.PolygonHierarchy(positions),
      material: Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.08),
      outline: true,
      outlineColor: Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.4),
      outlineWidth: 1,
    },
    show: arcticLayerVisible.adiz,
  });
  arcticLayerEntities.adiz.push(adizEntity);

  // ADIZ label
  var adizLabel = arcticCesiumViewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(-100, 60),
    label: {
      text: 'Canadian ADIZ',
      font: '10px IBM Plex Sans, sans-serif',
      fillColor: Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.5),
      style: Cesium.LabelStyle.FILL,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
    },
    show: arcticLayerVisible.adiz,
  });
  arcticLayerEntities.adiz.push(adizLabel);
}
```

- [ ] **Step 3: Write `renderArcticIceEdge()` function**

```javascript
function renderArcticIceEdge() {
  arcticLayerEntities.ice.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.ice = [];

  var positions = ICE_EDGE.map(function(pt) {
    return Cesium.Cartesian3.fromDegrees(pt[1], pt[0]);
  });

  var iceEntity = arcticCesiumViewer.entities.add({
    polyline: {
      positions: positions,
      width: 1.5,
      material: new Cesium.PolylineDashMaterialProperty({
        color: Cesium.Color.WHITE.withAlpha(0.3),
        dashLength: 12,
      }),
      clampToGround: true,
    },
    show: arcticLayerVisible.ice,
  });
  arcticLayerEntities.ice.push(iceEntity);

  // Ice edge label
  var iceLabel = arcticCesiumViewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(0, 75.5),
    label: {
      text: 'Approx. ice edge ~75\u00b0N',
      font: 'italic 9px IBM Plex Sans, sans-serif',
      fillColor: Cesium.Color.WHITE.withAlpha(0.3),
      style: Cesium.LabelStyle.FILL,
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
      distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
    },
    show: arcticLayerVisible.ice,
  });
  arcticLayerEntities.ice.push(iceLabel);
}
```

- [ ] **Step 4: Wire into `loadArctic()`**

Add these calls after `renderArcticBases()` in `loadArctic()`:

```javascript
  renderArcticRoutes();
  renderArcticADIZ();
  renderArcticIceEdge();
```

- [ ] **Step 5: Verify routes, ADIZ, and ice edge render**

Open http://localhost:8000 → Arctic tab.
Expected: 3 shipping routes as arcs with labels and chokepoint markers, blue ADIZ polygon, white dashed ice edge line. Toggle buttons work for each.

- [ ] **Step 6: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): add shipping routes, ADIZ polygon, and ice edge to 3D globe"
```

---

### Task 3: Live Flights

**Files:**
- Modify: `src/static/index.html` — add `renderArcticFlights()`, update refresh logic

- [ ] **Step 1: Write `renderArcticFlights()` function**

```javascript
function renderArcticFlights(flights) {
  // Clear old flight entities
  arcticLayerEntities.flights.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.flights = [];

  if (!flights || !flights.flights) return;

  var nationColors = {
    russian: '#ef4444',
    chinese: '#f59e0b',
    nato: '#3b82f6',
    unknown: '#64748b',
  };

  flights.flights.forEach(function(f) {
    var color = Cesium.Color.fromCssColorString(nationColors[f.nation] || '#64748b');
    var altMeters = (f.altitude_ft || 35000) * 0.3048;

    var entity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, altMeters),
      point: {
        pixelSize: 6,
        color: color.withAlpha(0.85),
        outlineColor: color,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: (f.callsign || '?') + (f.aircraft_description ? ' ' + f.aircraft_description : ''),
        font: '9px JetBrains Mono, monospace',
        fillColor: color.withAlpha(0.8),
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 2,
        outlineColor: Cesium.Color.BLACK,
        pixelOffset: new Cesium.Cartesian2(10, 0),
        horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000),
      },
      properties: { type: 'arctic-flight', nation: f.nation },
      show: arcticLayerVisible.flights,
    });
    arcticLayerEntities.flights.push(entity);
  });
}
```

- [ ] **Step 2: Wire into `loadArctic()` and update flight refresh**

In `loadArctic()`, add after the other render calls:

```javascript
  if (flights) {
    renderArcticFlights(flights);
  }
```

Replace the old `updateArcticMainMapFlights()` function (already deleted in Task 1) with:

```javascript
function updateArcticMainMapFlights(flights) {
  if (!arcticCesiumViewer || !flights) return;
  renderArcticFlights(flights);
}
```

- [ ] **Step 3: Verify flights render and auto-refresh**

Open Arctic tab. Expected: Aircraft markers at altitude, colored by nation, with callsign labels. Should auto-refresh every 60 seconds.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): add live military flight tracking to 3D globe"
```

---

### Task 4: Base Connections + Weapon Range Rings

**Files:**
- Modify: `src/static/index.html` — add `renderArcticConnections()` and `renderArcticRangeRings()`

- [ ] **Step 1: Write `renderArcticConnections()` function**

```javascript
function renderArcticConnections(bases) {
  arcticLayerEntities.connections.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.connections = [];

  var russianBases = bases.filter(function(b) { return b.alliance === 'russia'; });
  var natoBases = bases.filter(function(b) { return b.alliance === 'nato'; });

  // Russian network lines (sequential connections)
  for (var i = 0; i < russianBases.length - 1; i++) {
    var dist = _haversineJS(russianBases[i].lat, russianBases[i].lon, russianBases[i+1].lat, russianBases[i+1].lon);
    if (dist > 3000) continue;
    var entity = arcticCesiumViewer.entities.add({
      polyline: {
        positions: [
          Cesium.Cartesian3.fromDegrees(russianBases[i].lon, russianBases[i].lat),
          Cesium.Cartesian3.fromDegrees(russianBases[i+1].lon, russianBases[i+1].lat),
        ],
        width: 1,
        material: Cesium.Color.fromCssColorString('#ef4444').withAlpha(0.25),
        clampToGround: true,
      },
      show: arcticLayerVisible.connections,
    });
    arcticLayerEntities.connections.push(entity);
  }

  // NATO network lines
  for (var j = 0; j < natoBases.length - 1; j++) {
    var natoDist = _haversineJS(natoBases[j].lat, natoBases[j].lon, natoBases[j+1].lat, natoBases[j+1].lon);
    if (natoDist > 3000) continue;
    var natoEntity = arcticCesiumViewer.entities.add({
      polyline: {
        positions: [
          Cesium.Cartesian3.fromDegrees(natoBases[j].lon, natoBases[j].lat),
          Cesium.Cartesian3.fromDegrees(natoBases[j+1].lon, natoBases[j+1].lat),
        ],
        width: 1,
        material: Cesium.Color.fromCssColorString('#3b82f6').withAlpha(0.15),
        clampToGround: true,
      },
      show: arcticLayerVisible.connections,
    });
    arcticLayerEntities.connections.push(natoEntity);
  }

  // Distance lines from key adversary bases to nearest Canadian base
  bases.filter(function(b) { return DISTANCE_LINE_BASES.includes(b.name); }).forEach(function(b) {
    var nearest = _findNearestCanadianBase(b.lat, b.lon, bases);
    if (!nearest) return;

    var distEntity = arcticCesiumViewer.entities.add({
      polyline: {
        positions: [
          Cesium.Cartesian3.fromDegrees(b.lon, b.lat),
          Cesium.Cartesian3.fromDegrees(nearest.lon, nearest.lat),
        ],
        width: 1,
        material: new Cesium.PolylineDashMaterialProperty({
          color: Cesium.Color.fromCssColorString('#f59e0b').withAlpha(0.3),
          dashLength: 10,
        }),
        clampToGround: true,
      },
      show: arcticLayerVisible.connections,
    });
    arcticLayerEntities.connections.push(distEntity);

    // Distance label at midpoint
    var midLon = (b.lon + nearest.lon) / 2;
    var midLat = (b.lat + nearest.lat) / 2;
    var labelEntity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(midLon, midLat),
      label: {
        text: nearest.dist.toLocaleString() + ' km',
        font: '9px JetBrains Mono, monospace',
        fillColor: Cesium.Color.fromCssColorString('#f59e0b').withAlpha(0.6),
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 2,
        outlineColor: Cesium.Color.BLACK,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 10000000),
      },
      show: arcticLayerVisible.connections,
    });
    arcticLayerEntities.connections.push(labelEntity);
  });
}
```

- [ ] **Step 2: Write `renderArcticRangeRings()` function**

```javascript
function renderArcticRangeRings(bases) {
  arcticLayerEntities.ranges.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.ranges = [];

  // Weapon system keywords and their ranges
  var weaponRanges = [
    { keywords: ['S-400', 'S-300'], range_km: 400, color: '#ef4444', label: 'S-400 SAM' },
    { keywords: ['Bastion', 'coastal defense'], range_km: 500, color: '#f97316', label: 'Bastion AShM' },
    { keywords: ['Kinzhal', 'MiG-31', 'bomber', 'Tu-22', 'Tu-95'], range_km: 2000, color: '#ef4444', label: 'Air-launched strike' },
    { keywords: ['interceptor', 'GBI', 'Ground-Based Interceptor'], range_km: 2000, color: '#3b82f6', label: 'GBI intercept' },
  ];

  bases.forEach(function(base) {
    var cap = (base.capability || '').toLowerCase();
    weaponRanges.forEach(function(wr) {
      var match = wr.keywords.some(function(kw) { return cap.indexOf(kw.toLowerCase()) >= 0; });
      if (!match) return;

      var ringColor = Cesium.Color.fromCssColorString(wr.color);
      var entity = arcticCesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(base.lon, base.lat),
        ellipse: {
          semiMajorAxis: wr.range_km * 1000,
          semiMinorAxis: wr.range_km * 1000,
          material: ringColor.withAlpha(0.06),
          outline: true,
          outlineColor: ringColor.withAlpha(0.3),
          outlineWidth: 1,
        },
        show: arcticLayerVisible.ranges,
      });
      arcticLayerEntities.ranges.push(entity);

      // Small label at edge of ring (north)
      var edgeLat = base.lat + (wr.range_km / 111.32);
      var labelEntity = arcticCesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(base.lon, Math.min(edgeLat, 89)),
        label: {
          text: wr.label + ' (' + wr.range_km + 'km)',
          font: '8px JetBrains Mono, monospace',
          fillColor: ringColor.withAlpha(0.5),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE,
          outlineWidth: 2,
          outlineColor: Cesium.Color.BLACK,
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 8000000),
        },
        show: arcticLayerVisible.ranges,
      });
      arcticLayerEntities.ranges.push(labelEntity);
    });
  });
}
```

- [ ] **Step 3: Wire into `loadArctic()`**

Add after the other render calls:

```javascript
  if (arcticBasesData && arcticBasesData.bases) {
    renderArcticConnections(arcticBasesData.bases);
    renderArcticRangeRings(arcticBasesData.bases);
  }
```

- [ ] **Step 4: Verify connections and range rings render**

Open Arctic tab. Expected: Red/blue network lines between allied bases, orange dashed distance lines from Russian bases to nearest Canadian base with km labels, semi-transparent range rings around equipped bases (S-400, Bastion, Kinzhal, GBI).

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): add base network connections and weapon range rings to 3D globe"
```

---

### Task 5: Cleanup + Final Verification

**Files:**
- Modify: `src/static/index.html` — remove dead Leaflet code, verify no regressions

- [ ] **Step 1: Remove dead Leaflet references**

Search for any remaining references to the old Leaflet Arctic map that are now dead code:
- Any `L.map`, `L.marker`, `L.polyline`, `L.polygon`, `L.circleMarker`, `L.divIcon` calls specific to the Arctic map (NOT the Live Flights tab which has its own Leaflet map)
- The old `arcticMainMarkers` and `arcticMainLayers` usage (should already be gone from Task 1)

Be careful NOT to remove Leaflet code used by the Live Flights tab or the World Map tab — only Arctic-map-specific Leaflet code.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -q --ignore=tests/test_routes.py --ignore=tests/test_api_response_validation.py`
Expected: All pass (no Python changes, so no new failures possible)

- [ ] **Step 3: Full manual verification**

Open http://localhost:8000 → Arctic tab:
1. Globe renders with dark styling, Canadian perspective
2. 25 bases with correct colors/sizes
3. Click popup shows full intel for each base
4. 3 shipping routes as arcs with labels and chokepoints
5. Live flights with callsign labels, auto-refresh 60s
6. ADIZ polygon (faint blue)
7. Ice edge line (dashed white)
8. Alliance network connections (red/blue lines)
9. Distance lines (orange dashed with km labels)
10. Weapon range rings (translucent circles)
11. All 7 toggle buttons work (show/hide each layer)
12. Reset View button returns to Canadian perspective
13. All content below the map (tables, charts, panels) still works
14. Other tabs (Supply Chain, Live Flights, World Map) unaffected

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "refactor(arctic): remove dead Leaflet code after CesiumJS migration"
```

---

## Final Verification Checklist

After all 5 tasks:

- [ ] Arctic 3D globe renders on tab open
- [ ] All 7 layers visible and toggleable
- [ ] Base click popups work with full intel
- [ ] Live flights auto-refresh every 60 seconds
- [ ] Weapon range rings show threat coverage
- [ ] Reset View returns to Canadian perspective
- [ ] Supply Chain globe still works independently
- [ ] All test suites pass
- [ ] No console errors
