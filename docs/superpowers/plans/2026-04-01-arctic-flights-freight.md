# Arctic Flights + Freight Estimation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge Live Flights into the Arctic 3D globe with transport freight estimation and destination projection lines, then delete the standalone Live Flights tab.

**Architecture:** Single file change (index.html). Enhance `renderArcticFlights()` with aircraft classification, payload lookup, and destination estimation. Add projected lines and trails for transports. Add freight stats bar. Delete Live Flights tab HTML, JS, and nav button.

**Tech Stack:** CesiumJS 1.119, existing `/tracking/flights/military` API endpoint

**Design spec:** `docs/superpowers/specs/2026-04-01-arctic-flights-freight-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/static/index.html` | Modify | All changes in this single file |

---

### Task 1: Add Payload Lookup + Helpers + Freight Stats Bar

**Files:**
- Modify: `src/static/index.html` — add constants after TANKER_TYPES (~line 3001), add helpers near Arctic functions, add HTML stats bar

- [ ] **Step 1: Add payload lookup table and bearing helper**

After `TANKER_TYPES` (line 3001), add:

```javascript
var TRANSPORT_PAYLOAD_TONNES = {
  'C17': 77, 'C5': 122, 'C5M': 122,
  'IL76': 48, 'A124': 150,
  'A400': 37, 'C130': 19, 'C30J': 19,
  'Y20': 66, 'KC39': 26, 'C2': 30,
};
```

After `_haversineJS()` function (around line 4890), add:

```javascript
function _bearingJS(lat1, lon1, lat2, lon2) {
  var dLon = (lon2 - lon1) * Math.PI / 180;
  var y = Math.sin(dLon) * Math.cos(lat2 * Math.PI / 180);
  var x = Math.cos(lat1 * Math.PI / 180) * Math.sin(lat2 * Math.PI / 180) -
          Math.sin(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) * Math.cos(dLon);
  var brng = Math.atan2(y, x) * 180 / Math.PI;
  return (brng + 360) % 360;
}

function _destPointJS(lat, lon, bearing, distKm) {
  var R = 6371;
  var d = distKm / R;
  var brng = bearing * Math.PI / 180;
  var lat1 = lat * Math.PI / 180;
  var lon1 = lon * Math.PI / 180;
  var lat2 = Math.asin(Math.sin(lat1) * Math.cos(d) + Math.cos(lat1) * Math.sin(d) * Math.cos(brng));
  var lon2 = lon1 + Math.atan2(Math.sin(brng) * Math.sin(d) * Math.cos(lat1), Math.cos(d) - Math.sin(lat1) * Math.sin(lat2));
  return { lat: lat2 * 180 / Math.PI, lon: lon2 * 180 / Math.PI };
}

function estimateFlightDestination(flight, bases) {
  if (!flight.heading && flight.heading !== 0) return null;
  var heading = flight.heading;
  var bestBase = null;
  var bestDist = Infinity;

  bases.forEach(function(base) {
    var dist = _haversineJS(flight.latitude, flight.longitude, base.lat, base.lon);
    if (dist > 4000 || dist < 50) return; // too far or already there
    var bearing = _bearingJS(flight.latitude, flight.longitude, base.lat, base.lon);
    var diff = Math.abs(heading - bearing);
    if (diff > 180) diff = 360 - diff;
    if (diff <= 30 && dist < bestDist) {
      bestDist = dist;
      bestBase = base;
    }
  });

  return bestBase ? { name: bestBase.name, lat: bestBase.lat, lon: bestBase.lon, dist: Math.round(bestDist) } : null;
}
```

- [ ] **Step 2: Add freight stats bar to HTML**

In the Arctic globe card, after the legend div (after line ~1492, before the `arctic-main-map` div), add:

```html
      <div id="arctic-freight-stats" style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim); margin-bottom:6px; min-height:14px;">Arctic freight: awaiting data...</div>
```

- [ ] **Step 3: Add `updateArcticFreightStats()` function**

Add after the `estimateFlightDestination` function:

```javascript
function updateArcticFreightStats(flights) {
  var el = document.getElementById('arctic-freight-stats');
  if (!el) return;
  if (!flights || !flights.flights) { el.textContent = 'Arctic freight: No flight data'; return; }

  var arcticTransports = flights.flights.filter(function(f) {
    return f.latitude > 55 && TRANSPORT_TYPES.includes(f.aircraft_type) && !TANKER_TYPES.includes(f.aircraft_type);
  });

  if (arcticTransports.length === 0) {
    el.innerHTML = 'Arctic freight: <span style="color:var(--text-muted);">No transport aircraft detected above 55\u00b0N</span>';
    return;
  }

  var byNation = {};
  arcticTransports.forEach(function(f) {
    var nation = f.nation || 'unknown';
    if (!byNation[nation]) byNation[nation] = { count: 0, tonnes: 0, types: {} };
    var payload = TRANSPORT_PAYLOAD_TONNES[f.aircraft_type] || 0;
    byNation[nation].count++;
    byNation[nation].tonnes += payload;
    byNation[nation].types[f.aircraft_type] = (byNation[nation].types[f.aircraft_type] || 0) + 1;
  });

  var nationColors = { russian: '#ef4444', chinese: '#f59e0b', nato: '#3b82f6', unknown: '#64748b' };
  var nationLabels = { russian: 'Russia', chinese: 'China', nato: 'NATO', unknown: 'Other' };
  var parts = [];
  Object.keys(byNation).forEach(function(nation) {
    var n = byNation[nation];
    var typeStr = Object.keys(n.types).map(function(t) { return n.types[t] + '\u00d7 ' + t; }).join(', ');
    var color = nationColors[nation] || '#64748b';
    parts.push('<span style="color:' + color + ';">' + esc(nationLabels[nation] || nation) + ': ' + typeStr + ' = ' + n.tonnes + 't</span>');
  });

  el.innerHTML = 'Arctic freight (est. max): ' + parts.join(' | ');
}
```

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): add payload lookup, destination estimation, and freight stats bar"
```

---

### Task 2: Enhance renderArcticFlights with Classification + Projection Lines

**Files:**
- Modify: `src/static/index.html` — replace `renderArcticFlights()` function (~line 5274-5317)

- [ ] **Step 1: Replace the entire `renderArcticFlights()` function**

Find the existing `renderArcticFlights()` function (starts ~line 5274) and replace it entirely with:

```javascript
function renderArcticFlights(flights) {
  arcticLayerEntities.flights.forEach(function(e) { arcticCesiumViewer.entities.remove(e); });
  arcticLayerEntities.flights = [];

  if (!flights || !flights.flights) return;

  var nationColors = {
    russian: '#ef4444',
    chinese: '#f59e0b',
    nato: '#3b82f6',
    unknown: '#64748b',
  };

  var bases = (arcticBasesData && arcticBasesData.bases) ? arcticBasesData.bases : [];

  flights.flights.forEach(function(f) {
    var nationColor = Cesium.Color.fromCssColorString(nationColors[f.nation] || '#64748b');
    var altMeters = (f.altitude_ft || 35000) * 0.3048;
    var isTransport = TRANSPORT_TYPES.includes(f.aircraft_type) && !TANKER_TYPES.includes(f.aircraft_type);
    var isTanker = TANKER_TYPES.includes(f.aircraft_type);

    // Aircraft type classification colors
    var dotColor = nationColor;
    var pixelSize = 6;
    if (isTransport) {
      dotColor = Cesium.Color.fromCssColorString('#10b981');
      pixelSize = 8;
    } else if (isTanker) {
      dotColor = Cesium.Color.fromCssColorString('#8b5cf6');
      pixelSize = 7;
    }

    // Build label text
    var labelText = (f.callsign || '?');
    if (f.aircraft_description) labelText += ' ' + f.aircraft_description;
    var payload = TRANSPORT_PAYLOAD_TONNES[f.aircraft_type] || 0;

    // Destination estimation for transports
    var dest = null;
    if (isTransport && bases.length > 0) {
      dest = estimateFlightDestination(f, bases);
    }

    if (isTransport && payload > 0) {
      labelText = f.aircraft_type + ' ' + (f.callsign || '?');
      if (dest) {
        labelText += ' \u2192 ' + dest.name.split(',')[0] + ' (' + payload + 't)';
      } else {
        labelText += ' (' + payload + 't)';
      }
    }

    // Aircraft point entity
    var entity = arcticCesiumViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, altMeters),
      point: {
        pixelSize: pixelSize,
        color: dotColor.withAlpha(0.85),
        outlineColor: dotColor,
        outlineWidth: 1,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: labelText,
        font: '9px JetBrains Mono, monospace',
        fillColor: (isTransport ? Cesium.Color.fromCssColorString('#10b981') : dotColor).withAlpha(0.8),
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        outlineWidth: 2,
        outlineColor: Cesium.Color.BLACK,
        pixelOffset: new Cesium.Cartesian2(10, 0),
        horizontalOrigin: Cesium.HorizontalOrigin.LEFT,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 5000000),
      },
      properties: { type: 'arctic-flight', nation: f.nation, isTransport: isTransport },
      show: arcticLayerVisible.flights,
    });
    arcticLayerEntities.flights.push(entity);

    // Transport-only: projected line to destination + trail behind
    if (isTransport && f.heading != null) {
      var lineColor = nationColor.withAlpha(0.4);

      // Projected line forward to estimated destination
      if (dest) {
        var projEntity = arcticCesiumViewer.entities.add({
          polyline: {
            positions: [
              Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, altMeters),
              Cesium.Cartesian3.fromDegrees(dest.lon, dest.lat, 0),
            ],
            width: 1.5,
            material: new Cesium.PolylineDashMaterialProperty({
              color: lineColor,
              dashLength: 10,
            }),
          },
          show: arcticLayerVisible.flights,
        });
        arcticLayerEntities.flights.push(projEntity);
      }

      // Trail behind (~500km in opposite direction)
      var behindHeading = (f.heading + 180) % 360;
      var trailPt = _destPointJS(f.latitude, f.longitude, behindHeading, 500);
      var trailEntity = arcticCesiumViewer.entities.add({
        polyline: {
          positions: [
            Cesium.Cartesian3.fromDegrees(trailPt.lon, trailPt.lat, altMeters),
            Cesium.Cartesian3.fromDegrees(f.longitude, f.latitude, altMeters),
          ],
          width: 1,
          material: nationColor.withAlpha(0.15),
        },
        show: arcticLayerVisible.flights,
      });
      arcticLayerEntities.flights.push(trailEntity);
    }
  });

  // Update freight stats
  updateArcticFreightStats(flights);
}
```

- [ ] **Step 2: Verify flights render with classification and projection lines**

Open http://localhost:8000 → Arctic tab. Expected:
- Transport aircraft are green dots with payload labels
- Tankers are purple
- Fighters/other are amber
- Transport aircraft show dashed projected lines to estimated destination bases
- Transport aircraft show fading trails behind them
- Freight stats bar shows per-nation breakdown

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): enhance flights with classification, freight estimation, and projection lines"
```

---

### Task 3: Delete Live Flights Tab

**Files:**
- Modify: `src/static/index.html` — remove nav button, page HTML, JS functions, globals

- [ ] **Step 1: Delete the Live Flights nav button**

Find and delete this line (~line 1125):
```html
  <button class="nav-tab" data-page="live-flights" role="tab" id="tab-live-flights" aria-selected="false" aria-controls="page-live-flights">Live Flights</button>
```

- [ ] **Step 2: Delete the Live Flights page HTML**

Find and delete the entire page container (lines ~1703-1727):
```html
  <!-- ════ LIVE FLIGHTS PAGE ════ -->
  <div id="page-live-flights" class="page" role="tabpanel" aria-labelledby="tab-live-flights">
    ...entire content...
  </div>
```

- [ ] **Step 3: Delete Live Flights global variables**

Find and delete these lines (~2454-2456):
```javascript
let flightsMap = null;
let flightMarkers = [];
let flightRefreshTimer = null;
```

- [ ] **Step 4: Remove Live Flights tab switching logic**

Find the tab switching section (~line 2571-2578). Delete these lines:
```javascript
    // Stop flight refresh when leaving flights tab
    if (tab.dataset.page !== 'live-flights') clearTimeout(flightRefreshTimer);
```

And delete:
```javascript
    if (tab.dataset.page === 'live-flights') loadFlights();
```

- [ ] **Step 5: Delete the `loadFlights()` function**

Find and delete the entire function (lines ~3003-3076), including the comment header:
```javascript
// ══════════════════════════════════════════════
// ── LIVE FLIGHTS ──
// ══════════════════════════════════════════════

const TRANSPORT_TYPES = ...
const TANKER_TYPES = ...

async function loadFlights() {
  ...entire function...
}
```

**IMPORTANT:** Keep `TRANSPORT_TYPES` and `TANKER_TYPES` constants — move them up above the deleted section or leave them in place. They are used by the Arctic flight rendering. Also keep `TRANSPORT_PAYLOAD_TONNES` (added in Task 1).

Actually, the cleanest approach: move the 3 constants to just before the Arctic section. Delete everything else.

- [ ] **Step 6: Verify no console errors and other tabs work**

Open http://localhost:8000:
- "Live Flights" tab should be gone from the nav bar
- Arctic tab still shows flights with freight estimation
- All other tabs work (Insights, Overview, World Map, Deals, Canada Intel, Supply Chain, Data Feeds, Compliance)
- No JavaScript console errors

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): delete standalone Live Flights tab (merged into Arctic 3D globe)"
```

---

## Final Verification

After all 3 tasks:

- [ ] Live Flights tab is gone from nav
- [ ] Arctic globe shows classified flights (green transport, purple tanker, amber other)
- [ ] Transport aircraft have payload labels (e.g., "C17 RCH482 → Pituffik (77t)")
- [ ] Projected dashed lines from transports to estimated destinations
- [ ] Fading trails behind transport aircraft
- [ ] Freight stats bar shows per-nation breakdown
- [ ] 60-second auto-refresh still works
- [ ] Layer toggle for "Flights" still hides/shows all flight entities
- [ ] All other tabs unaffected
- [ ] No console errors
