# Cobalt Route Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace 6 approximate cobalt sea routes with 15 geographically accurate routes (10 sea, 5 overland) as separate toggleable layers on the CesiumJS 3D globe.

**Architecture:** Backend defines `sea_routes` and `overland_routes` arrays in `mineral_supply_chains.py`. Frontend reads both arrays and renders sea routes as dashed polylines at 5km altitude and overland routes as glowing solid polylines at 500m. Three new layer IDs (`sea-routes`, `overland-routes`, `route-labels`) replace the single `shipping` layer.

**Tech Stack:** Python (data), CesiumJS 1.119 (rendering), Chart.js (existing)

**Spec:** `docs/superpowers/specs/2026-04-03-cobalt-route-accuracy-design.md`

---

### Task 1: Replace `shipping_routes` with `sea_routes` and `overland_routes` in backend

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py:1507-1593`

- [ ] **Step 1: Replace the `shipping_routes` key with `sea_routes` containing all 10 sea routes**

In `src/analysis/mineral_supply_chains.py`, replace lines 1507-1593 (the entire `"shipping_routes": [...]` block) with:

```python
        "sea_routes": [
            {
                "id": "SR-1",
                "name": "Durban \u2192 Shanghai",
                "description": "DRC cobalt via southern Africa to Chinese refineries (primary global route)",
                "form": "Cobalt hydroxide (wet paste)",
                "mode": "sea",
                "transit_days": 30,
                "risk": "critical",
                "risk_reason": "Malacca Strait chokepoint, South China Sea tensions, Chinese-controlled at both ends, 50-55% of global cobalt",
                "chokepoints": ["Mozambique Channel", "Strait of Malacca", "South China Sea"],
                "volume_pct": 52,
                "waypoints": [
                    [31.03, -29.87], [35.0, -27.0], [40.0, -20.0], [45.0, -12.0],
                    [50.0, -5.0], [60.0, 0.0], [72.0, 5.0], [80.0, 5.5],
                    [90.0, 4.0], [98.0, 3.0], [103.5, 1.3], [105.0, 2.5],
                    [110.0, 7.0], [115.0, 15.0], [120.0, 25.0], [122.0, 31.2],
                ],
                "connects_from": "OL-2",
            },
            {
                "id": "SR-2",
                "name": "Dar es Salaam \u2192 Shanghai",
                "description": "Eastern DRC corridor via TAZARA rail to Tanzanian port, then to China",
                "form": "Cobalt hydroxide",
                "mode": "sea",
                "transit_days": 25,
                "risk": "high",
                "risk_reason": "TAZARA rail feeds this route, Malacca chokepoint, Dar es Salaam port congestion",
                "chokepoints": ["Strait of Malacca", "South China Sea"],
                "volume_pct": 12,
                "waypoints": [
                    [39.29, -6.82], [42.0, -5.0], [48.0, -2.0], [55.0, 2.0],
                    [65.0, 4.0], [75.0, 5.5], [85.0, 5.0], [93.0, 3.5],
                    [98.0, 3.0], [103.5, 1.3], [105.0, 2.5], [110.0, 7.0],
                    [117.0, 18.0], [122.0, 31.2],
                ],
                "connects_from": "OL-3",
            },
            {
                "id": "SR-3",
                "name": "Durban \u2192 Antwerp",
                "description": "DRC cobalt to European refineries via Cape of Good Hope (Red Sea avoided since 2024)",
                "form": "Cobalt hydroxide, concentrate",
                "mode": "sea",
                "transit_days": 32,
                "risk": "critical",
                "risk_reason": "Houthi Red Sea attacks forced Cape routing (+10-14 days vs Suez), DRC origin risk, single Western refiner dependency",
                "chokepoints": ["Cape of Good Hope", "English Channel"],
                "volume_pct": 9,
                "waypoints": [
                    [31.03, -29.87], [28.0, -33.0], [18.5, -34.4], [14.0, -30.0],
                    [10.0, -20.0], [5.0, -10.0], [0.0, 0.0], [-5.0, 10.0],
                    [-10.0, 20.0], [-12.0, 30.0], [-10.0, 40.0], [-5.0, 47.0],
                    [-2.0, 49.0], [1.0, 50.5], [2.5, 51.0], [4.4, 51.23],
                ],
                "connects_from": "OL-2",
            },
            {
                "id": "SR-4",
                "name": "Lobito \u2192 Halifax",
                "description": "Emerging Atlantic corridor bypassing Chinese logistics and Malacca Strait",
                "form": "Cobalt hydroxide, copper-cobalt concentrate",
                "mode": "sea",
                "transit_days": 20,
                "risk": "medium",
                "risk_reason": "New corridor (first shipments 2026), bypasses Chinese logistics and Malacca, DRC origin risk remains, Angola political stability uncertain",
                "chokepoints": [],
                "note": "Under construction. First cobalt shipments expected 2026. G7/US/EU-backed.",
                "waypoints": [
                    [13.54, -12.35], [10.0, -8.0], [5.0, 0.0], [-5.0, 10.0],
                    [-15.0, 20.0], [-25.0, 28.0], [-35.0, 34.0], [-45.0, 38.0],
                    [-52.0, 41.0], [-58.0, 43.0], [-62.0, 44.0], [-63.57, 44.65],
                ],
            },
            {
                "id": "SR-5",
                "name": "Shanghai \u2192 Vancouver",
                "description": "Chinese refined cobalt to Canada via North Pacific Great Circle route",
                "form": "Refined cobalt metal, cobalt sulfate",
                "mode": "sea",
                "transit_days": 16,
                "risk": "critical",
                "risk_reason": "Single-country processing dependency (China 80%), export controls risk, Taiwan Strait escalation could sever route",
                "chokepoints": ["Taiwan Strait vicinity"],
                "waypoints": [
                    [121.5, 31.2], [125.0, 33.0], [132.0, 35.0], [140.0, 38.0],
                    [152.0, 42.0], [165.0, 46.0], [180.0, 48.5], [-170.0, 49.5],
                    [-155.0, 50.5], [-140.0, 50.5], [-130.0, 49.5], [-123.11, 49.29],
                ],
            },
            {
                "id": "SR-6a",
                "name": "Kokkola \u2192 Montreal",
                "description": "Finnish refined cobalt via Baltic, North Sea, and North Atlantic to St. Lawrence",
                "form": "Cobalt metal, chemicals, cathode precursors",
                "mode": "sea",
                "transit_days": 16,
                "risk": "low",
                "risk_reason": "NATO-allied source (Finland), reliable Umicore supply chain, open Atlantic, seasonal St. Lawrence ice only constraint",
                "chokepoints": ["St. Lawrence Seaway (ice Dec-Mar)"],
                "waypoints": [
                    [23.13, 63.84], [20.0, 58.0], [12.0, 56.0], [5.0, 54.0],
                    [0.0, 52.0], [-5.0, 50.5], [-12.0, 50.0], [-22.0, 49.5],
                    [-35.0, 49.0], [-48.0, 48.0], [-55.0, 48.0], [-62.0, 47.5],
                    [-68.0, 47.0], [-73.55, 45.50],
                ],
            },
            {
                "id": "SR-6b",
                "name": "Hoboken \u2192 Montreal",
                "description": "Belgian refined cobalt via English Channel and North Atlantic to St. Lawrence",
                "form": "Cobalt chemicals, recycled metals",
                "mode": "sea",
                "transit_days": 12,
                "risk": "low",
                "risk_reason": "NATO-allied source (Belgium), established Umicore supply chain, open Atlantic, shortest transit time",
                "chokepoints": ["St. Lawrence Seaway (ice Dec-Mar)"],
                "waypoints": [
                    [4.34, 51.16], [2.0, 51.0], [0.0, 51.5], [-5.0, 50.5],
                    [-12.0, 50.0], [-22.0, 49.5], [-35.0, 49.0], [-48.0, 48.0],
                    [-55.0, 48.0], [-62.0, 47.5], [-68.0, 47.0], [-73.55, 45.50],
                ],
            },
            {
                "id": "SR-7",
                "name": "Esperance \u2192 Shanghai",
                "description": "Australian cobalt (Murrin Murrin) via Indian Ocean and Malacca Strait to China",
                "form": "Mixed hydroxide precipitate (MHP)",
                "mode": "sea",
                "transit_days": 22,
                "risk": "medium",
                "risk_reason": "Malacca chokepoint, remote origin, Glencore operational status fluctuates",
                "chokepoints": ["Strait of Malacca"],
                "waypoints": [
                    [121.89, -33.86], [115.0, -30.0], [108.0, -22.0],
                    [105.0, -12.0], [103.0, -5.0], [103.5, 1.3],
                    [105.0, 3.0], [108.0, 8.0], [112.0, 15.0],
                    [117.0, 22.0], [120.0, 28.0], [122.0, 31.2],
                ],
            },
            {
                "id": "SR-8",
                "name": "Moa \u2192 Montreal",
                "description": "Cuban MSP via Caribbean and US east coast (offshore, no US port access) to St. Lawrence",
                "form": "Mixed sulphide precipitate (MSP)",
                "mode": "sea",
                "transit_days": 12,
                "risk": "high",
                "risk_reason": "US sanctions (Helms-Burton Act), Cuban energy crisis, hurricane corridor (Jun-Nov), no US port access, single-source Sherritt JV",
                "chokepoints": ["Florida Strait (no docking)", "St. Lawrence Seaway"],
                "waypoints": [
                    [-74.94, 20.62], [-74.0, 21.5], [-73.0, 24.0],
                    [-72.0, 28.0], [-70.0, 32.0], [-68.0, 36.0],
                    [-65.0, 40.0], [-62.0, 43.0], [-59.0, 46.0],
                    [-57.0, 47.5], [-62.0, 48.0], [-68.0, 47.5],
                    [-73.55, 45.50],
                ],
                "connects_to": "OL-5",
            },
            {
                "id": "SR-9",
                "name": "Voisey\u2019s Bay \u2192 Long Harbour",
                "description": "Labrador coastal shipping — Vale concentrate to Long Harbour NPP, Newfoundland",
                "form": "Nickel-copper-cobalt concentrate",
                "mode": "sea",
                "transit_days": 4,
                "risk": "medium",
                "risk_reason": "Ice and icebergs Nov-Jun, harsh weather, remote, single mine-to-refinery link",
                "chokepoints": ["Labrador Sea ice (seasonal)"],
                "waypoints": [
                    [-62.10, 56.33], [-60.0, 54.0], [-56.0, 51.5],
                    [-53.5, 49.5], [-52.5, 48.0], [-53.0, 47.5],
                    [-53.82, 47.42],
                ],
            },
            {
                "id": "SR-10",
                "name": "Raglan \u2192 Sorel-Tracy",
                "description": "Arctic concentrate via Hudson Strait and Gulf of St. Lawrence (4-month shipping window)",
                "form": "Nickel-cobalt concentrate",
                "mode": "sea",
                "transit_days": 8,
                "risk": "high",
                "risk_reason": "4-month shipping window (Jul-Oct only), Hudson Strait ice, extreme remoteness, Glencore Nikkelverk alternative",
                "chokepoints": ["Hudson Strait (ice)"],
                "waypoints": [
                    [-74.70, 62.15], [-72.0, 61.5], [-67.0, 60.5],
                    [-62.0, 58.0], [-58.0, 55.0], [-55.0, 51.0],
                    [-57.0, 49.0], [-60.0, 48.5], [-66.0, 48.0],
                    [-71.0, 46.5], [-73.12, 46.05],
                ],
            },
        ],
        "overland_routes": [
            {
                "id": "OL-1",
                "name": "DRC Mine Corridor",
                "description": "Kolwezi \u2192 Likasi \u2192 Lubumbashi \u2192 Kasumbalesa border (N1/N39 national roads)",
                "form": "Cobalt hydroxide, ore, concentrate",
                "mode": "truck",
                "transit_days": 3,
                "risk": "high",
                "risk_reason": "Poor road infrastructure, rainy season degradation (Oct-Apr), security risk from armed groups, artisanal mining material enters chain at Kolwezi/Lubumbashi",
                "waypoints": [
                    [25.47, -10.71], [25.80, -10.78], [26.10, -10.62],
                    [26.73, -10.98], [27.10, -11.20], [27.48, -11.66],
                    [28.10, -12.10], [28.52, -12.62],
                ],
                "connects_to": "OL-2",
            },
            {
                "id": "OL-2",
                "name": "Zambia \u2192 Durban Corridor",
                "description": "Kasumbalesa border \u2192 Lusaka \u2192 Johannesburg \u2192 Durban port via road and Transnet rail",
                "form": "Cobalt hydroxide (containerised)",
                "mode": "mixed",
                "transit_days": 9,
                "risk": "medium",
                "risk_reason": "Kasumbalesa border bottleneck (multi-day queues), Zambian fuel shortages, 2,500km distance, but well-established corridor",
                "waypoints": [
                    [28.52, -12.62], [28.63, -12.98], [28.68, -14.97],
                    [28.32, -15.39], [28.50, -18.0], [29.0, -20.0],
                    [29.80, -22.0], [29.50, -24.0], [28.50, -25.5],
                    [28.04, -26.20], [29.50, -28.0], [31.03, -29.87],
                ],
                "connects_to": "SR-1",
            },
            {
                "id": "OL-3",
                "name": "TAZARA Eastern Rail",
                "description": "Kapiri Mposhi \u2192 Nakonde \u2192 Dar es Salaam via TAZARA railway",
                "form": "Cobalt hydroxide",
                "mode": "rail",
                "transit_days": 5,
                "risk": "high",
                "risk_reason": "Chronic TAZARA underinvestment, low speeds, maintenance issues, Dar es Salaam port congestion, branches off Zambia corridor at Kapiri Mposhi",
                "waypoints": [
                    [28.68, -14.97], [29.20, -13.20], [30.50, -11.80],
                    [31.50, -10.50], [32.77, -9.34], [33.50, -8.90],
                    [34.80, -8.00], [36.00, -7.50], [38.00, -7.00],
                    [39.29, -6.82],
                ],
                "connects_to": "SR-2",
            },
            {
                "id": "OL-4",
                "name": "Chinese Inland Rail",
                "description": "Tianjin port \u2192 Zhengzhou \u2192 Xi\u2019an \u2192 Lanzhou \u2192 Jinchang via China Rail freight",
                "form": "Cobalt hydroxide, intermediates",
                "mode": "rail",
                "transit_days": 4,
                "risk": "low",
                "risk_reason": "World-class rail infrastructure (Lanzhou-Xinjiang corridor), but 2,000km inland adds cost and time. Jinchuan primarily uses domestic ore.",
                "waypoints": [
                    [117.73, 38.99], [114.40, 36.50], [113.65, 34.75],
                    [110.50, 34.50], [108.94, 34.26], [105.70, 35.60],
                    [103.83, 36.06], [102.19, 38.50],
                ],
            },
            {
                "id": "OL-5",
                "name": "Canadian Transcontinental Rail",
                "description": "Montreal \u2192 Sudbury \u2192 Winnipeg \u2192 Fort Saskatchewan via CN Rail",
                "form": "Mixed sulphide precipitate, refined intermediates",
                "mode": "rail",
                "transit_days": 5,
                "risk": "low",
                "risk_reason": "Well-established CN Rail infrastructure, but labour disputes can disrupt (2023 port/rail strikes). Passes through Sudbury Basin.",
                "waypoints": [
                    [-73.55, 45.50], [-75.70, 45.42], [-79.40, 43.65],
                    [-81.00, 46.50], [-84.30, 46.50], [-89.20, 48.40],
                    [-97.14, 49.90], [-106.67, 52.13], [-113.49, 53.54],
                    [-113.21, 53.72],
                ],
            },
        ],
```

- [ ] **Step 2: Verify the Python file parses cleanly**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && source venv/Scripts/activate && python -c "from src.analysis.mineral_supply_chains import get_mineral_supply_chains; d = get_mineral_supply_chains(); co = [m for m in d if m['name']=='Cobalt'][0]; print('sea:', len(co['sea_routes']), 'overland:', len(co['overland_routes']))"`

Expected: `sea: 11 overland: 5`

(11 because SR-6 is split into SR-6a and SR-6b)

- [ ] **Step 3: Verify API serves the new keys**

Run: `curl -s http://localhost:8000/globe/minerals/Cobalt | python -c "import sys,json; d=json.load(sys.stdin); print('sea_routes:', len(d.get('sea_routes',[])), 'overland_routes:', len(d.get('overland_routes',[])))"`

Expected: `sea_routes: 11 overland_routes: 5`

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/ -q --ignore=tests/test_scenario_adversarial.py`

Expected: All pass (route data is structural, not unit-tested)

- [ ] **Step 5: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(data): replace shipping_routes with sea_routes + overland_routes for Cobalt

11 sea routes and 5 overland routes with accurate waypoints covering
DRC mine corridors, Zambia-Durban, TAZARA rail, Lobito, Chinese inland
rail, Canadian transcontinental, and all major maritime lanes."
```

---

### Task 2: Update GLOBE_LAYERS and layer toggle in frontend

**Files:**
- Modify: `src/static/index.html:7369-7380` (GLOBE_LAYERS array)

- [ ] **Step 1: Replace the `shipping` layer with `sea-routes`, `overland-routes`, and `route-labels`**

In `src/static/index.html`, find the GLOBE_LAYERS array (line 7369) and replace the `shipping` entry:

Replace:
```javascript
  { id: 'shipping',    name: 'Shipping Routes',   color: '#D80621', defaultOn: true },
```

With:
```javascript
  { id: 'sea-routes',      name: 'Sea Routes',      color: '#5a7a9b', defaultOn: true },
  { id: 'overland-routes', name: 'Overland Routes',  color: '#a89060', defaultOn: true },
  { id: 'route-labels',    name: 'Route Labels',     color: '#999999', defaultOn: true },
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add sea-routes, overland-routes, route-labels layer toggles"
```

---

### Task 3: Replace sea route rendering code in frontend

**Files:**
- Modify: `src/static/index.html:8274-8348` (route rendering section)

- [ ] **Step 1: Replace the shipping route rendering block**

Find the block starting at line 8274 (`// ── Shipping routes to Canada ──`) through the end of the `else if (m.processing.length > 0)` fallback block (through line ~8348). Replace the entire section with code that renders `sea_routes` and `overland_routes` separately.

Replace lines 8274-8354 (the entire shipping route rendering + fallback section, up to and including the fallback port marker) with:

```javascript
    // ── Sea routes ──
    var riskRouteColors = { critical: '#D80621', high: '#a89060', medium: '#eab308', low: '#6b9080' };
    var portsRendered = {};

    if (m.sea_routes && m.sea_routes.length > 0) {
      m.sea_routes.forEach(function(sr) {
        if (!sr.waypoints || sr.waypoints.length < 2) return;
        var lineColor = Cesium.Color.fromCssColorString(riskRouteColors[sr.risk] || '#5a7a9b');
        var lineWidth = sr.risk === 'critical' ? 4 : sr.risk === 'high' ? 3 : sr.risk === 'medium' ? 2.5 : 2;
        var dashLen = sr.risk === 'critical' ? 8 : sr.risk === 'high' ? 12 : sr.risk === 'medium' ? 14 : 16;
        var routeCoords = [];
        sr.waypoints.forEach(function(wp) { routeCoords.push(wp[0], wp[1], 5000); });
        cesiumViewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights(routeCoords),
            width: lineWidth,
            material: new Cesium.PolylineDashMaterialProperty({
              color: lineColor.withAlpha(0.85),
              dashLength: dashLen,
            }),
          },
          properties: {
            layerId: 'sea-routes', type: 'searoute', mineral: m.name, risk: sr.risk || 'unknown',
            description: sr.name + ' (' + sr.transit_days + ' days) \u2014 ' + (sr.form || '')
              + (sr.chokepoints && sr.chokepoints.length ? ' | Chokepoints: ' + sr.chokepoints.join(', ') : '')
              + (sr.risk_reason ? ' | RISK: ' + sr.risk_reason : '')
              + (sr.note ? ' | ' + sr.note : ''),
          },
        });
        // Route midpoint label
        var midIdx = Math.floor(sr.waypoints.length / 2);
        var midWp = sr.waypoints[midIdx];
        cesiumViewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(midWp[0], midWp[1], 8000),
          label: {
            text: sr.name + ' | ' + sr.transit_days + 'd',
            font: '9px JetBrains Mono',
            fillColor: Cesium.Color.fromCssColorString(riskRouteColors[sr.risk] || '#999').withAlpha(0.9),
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 25000000),
          },
          properties: { layerId: 'route-labels', type: 'route-label', mineral: m.name },
        });
        // Mark endpoint port if not already rendered
        var lastWp = sr.waypoints[sr.waypoints.length - 1];
        var portKey = lastWp[0].toFixed(1) + ',' + lastWp[1].toFixed(1);
        if (!portsRendered[portKey]) {
          portsRendered[portKey] = true;
          var portName = sr.name.split('\u2192').pop().trim();
          cesiumViewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(lastWp[0], lastWp[1], 30000),
            point: { pixelSize: 12, color: Cesium.Color.fromCssColorString('#ff2d2d'), outlineColor: Cesium.Color.WHITE, outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
            label: {
              text: portName, font: 'bold 10px JetBrains Mono',
              fillColor: Cesium.Color.fromCssColorString('#ff2d2d'),
              style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
              verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 14),
              distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            properties: { layerId: 'ports', type: 'port', mineral: m.name, name: portName, desc: sr.description },
          });
        }
        // Also mark origin port
        var firstWp = sr.waypoints[0];
        var originKey = firstWp[0].toFixed(1) + ',' + firstWp[1].toFixed(1);
        if (!portsRendered[originKey]) {
          portsRendered[originKey] = true;
          var originName = sr.name.split('\u2192')[0].trim();
          cesiumViewer.entities.add({
            position: Cesium.Cartesian3.fromDegrees(firstWp[0], firstWp[1], 30000),
            point: { pixelSize: 10, color: Cesium.Color.fromCssColorString(riskRouteColors[sr.risk] || '#5a7a9b').withAlpha(0.8), outlineColor: Cesium.Color.WHITE, outlineWidth: 2, disableDepthTestDistance: Number.POSITIVE_INFINITY },
            label: {
              text: originName, font: '9px JetBrains Mono',
              fillColor: Cesium.Color.fromCssColorString(riskRouteColors[sr.risk] || '#5a7a9b'),
              style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
              verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 12),
              distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 15000000),
              disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
            properties: { layerId: 'ports', type: 'port', mineral: m.name, name: originName, desc: sr.description },
          });
        }
      });
    } else if (m.shipping_routes && m.shipping_routes.length > 0) {
      // Legacy fallback for non-cobalt minerals with old shipping_routes key
      m.shipping_routes.forEach(function(sr) {
        if (!sr.waypoints || sr.waypoints.length < 2) return;
        var lineColor = Cesium.Color.fromCssColorString(riskRouteColors[sr.risk] || '#5a7a9b');
        var routeCoords = [];
        sr.waypoints.forEach(function(wp) { routeCoords.push(wp[0], wp[1], 5000); });
        cesiumViewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights(routeCoords),
            width: sr.risk === 'critical' ? 4 : 2,
            material: new Cesium.PolylineDashMaterialProperty({ color: lineColor.withAlpha(0.85), dashLength: 14 }),
          },
          properties: { layerId: 'sea-routes', type: 'searoute', mineral: m.name, risk: sr.risk || 'unknown', description: sr.name },
        });
      });
    } else if (m.processing.length > 0) {
      // Fallback: single route from top processor to Canada
      var source = m.processing[0];
      var port = getCanadaPort(source.country);
      if (source.country !== 'Canada') {
        var route = getSeaRoute(source.country, port);
        if (route && route.length >= 2) {
          var routeCoords = [];
          route.forEach(function(wp) { routeCoords.push(wp[0], wp[1], 5000); });
          cesiumViewer.entities.add({
            polyline: {
              positions: Cesium.Cartesian3.fromDegreesArrayHeights(routeCoords),
              width: 3,
              material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.fromCssColorString('#ff2d2d').withAlpha(0.7), dashLength: 16 }),
            },
            properties: { layerId: 'sea-routes', type: 'searoute', mineral: m.name, description: m.name + ': ' + source.country + ' \u2192 ' + port.name },
          });
        } else {
          addFlowArc(source.lon, source.lat, port.lon, port.lat, Cesium.Color.fromCssColorString('#ff2d2d').withAlpha(0.5), m.name + ': ' + source.country + ' \u2192 ' + port.name, 'sea-routes');
        }
      }
      cesiumViewer.entities.add({
        position: Cesium.Cartesian3.fromDegrees(port.lon, port.lat, 30000),
        point: { pixelSize: 14, color: Cesium.Color.fromCssColorString('#ff2d2d'), outlineColor: Cesium.Color.WHITE, outlineWidth: 3, disableDepthTestDistance: Number.POSITIVE_INFINITY },
        label: {
          text: port.name + ' \u{1F341}', font: 'bold 12px JetBrains Mono', fillColor: Cesium.Color.fromCssColorString('#ff2d2d'),
          style: Cesium.LabelStyle.FILL_AND_OUTLINE, outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
          verticalOrigin: Cesium.VerticalOrigin.TOP, pixelOffset: new Cesium.Cartesian2(0, 16),
          distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 20000000),
          disableDepthTestDistance: Number.POSITIVE_INFINITY,
        },
        properties: { layerId: 'ports', type: 'port', mineral: m.name, name: port.name, desc: 'Canadian import port' },
      });
    }

    // ── Overland routes ──
    if (m.overland_routes && m.overland_routes.length > 0) {
      var modeColors = { truck: '#a89060', rail: '#5a7a9b', mixed: '#8a7a6b' };
      m.overland_routes.forEach(function(ol) {
        if (!ol.waypoints || ol.waypoints.length < 2) return;
        var olColor = Cesium.Color.fromCssColorString(modeColors[ol.mode] || '#a89060');
        var olWidth = ol.mode === 'truck' ? 3 : ol.mode === 'rail' ? 2.5 : 2.5;
        var routeCoords = [];
        ol.waypoints.forEach(function(wp) { routeCoords.push(wp[0], wp[1], 500); });
        cesiumViewer.entities.add({
          polyline: {
            positions: Cesium.Cartesian3.fromDegreesArrayHeights(routeCoords),
            width: olWidth,
            material: new Cesium.PolylineGlowMaterialProperty({
              glowPower: 0.15,
              color: olColor.withAlpha(0.8),
            }),
          },
          properties: {
            layerId: 'overland-routes', type: 'overland-route', mineral: m.name, risk: ol.risk || 'unknown',
            description: ol.name + ' (' + ol.transit_days + ' days, ' + ol.mode + ') \u2014 ' + (ol.form || '')
              + (ol.risk_reason ? ' | RISK: ' + ol.risk_reason : ''),
          },
        });
        // Overland route midpoint label
        var midIdx = Math.floor(ol.waypoints.length / 2);
        var midWp = ol.waypoints[midIdx];
        cesiumViewer.entities.add({
          position: Cesium.Cartesian3.fromDegrees(midWp[0], midWp[1], 2000),
          label: {
            text: ol.name + ' | ' + ol.transit_days + 'd ' + ol.mode,
            font: '9px JetBrains Mono',
            fillColor: Cesium.Color.fromCssColorString(modeColors[ol.mode] || '#a89060').withAlpha(0.9),
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            outlineWidth: 2, outlineColor: Cesium.Color.BLACK,
            disableDepthTestDistance: Number.POSITIVE_INFINITY,
            distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 12000000),
          },
          properties: { layerId: 'route-labels', type: 'route-label', mineral: m.name },
        });
      });
    }
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): render sea and overland routes as separate layers

Sea routes: dashed polylines at 5km, risk-colored, with midpoint labels.
Overland routes: glowing solid polylines at 500m, mode-colored (truck/rail).
Legacy shipping_routes fallback preserved for non-cobalt minerals."
```

---

### Task 4: Update route menu panel to show both route types

**Files:**
- Modify: `src/static/index.html:8476-8502` (route menu population)

- [ ] **Step 1: Update the route menu to group sea and overland routes**

Replace lines 8476-8502 (the `// Populate shipping route menu` block) with:

```javascript
  // Populate route menu with sea + overland routes
  var routeMenu = document.getElementById('globe-route-menu');
  var routeList = document.getElementById('globe-route-list');
  var allSeaRoutes = m.sea_routes || m.shipping_routes || [];
  var allOverlandRoutes = m.overland_routes || [];
  if (allSeaRoutes.length > 0 || allOverlandRoutes.length > 0) {
    var riskRouteColors = { critical: '#D80621', high: '#a89060', medium: '#eab308', low: '#6b9080' };
    var riskLabels = { critical: 'CRITICAL', high: 'HIGH', medium: 'MEDIUM', low: 'LOW' };
    var modeIcons = { sea: '\u2693', truck: '\u{1F69A}', rail: '\u{1F682}', mixed: '\u{1F504}' };
    var rhtml = '';
    if (allSeaRoutes.length > 0) {
      rhtml += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em; margin-bottom:4px;">Sea Routes (' + allSeaRoutes.length + ')</div>';
      allSeaRoutes.forEach(function(sr) {
        var rc = riskRouteColors[sr.risk] || '#64748b';
        rhtml += '<div style="margin-bottom:6px; padding:4px 8px; border-left:3px solid ' + rc + '; background:' + rc + '0a;">'
          + '<div style="display:flex; justify-content:space-between; align-items:center;">'
          + '<span style="font-size:10px; font-weight:600; color:var(--text);">\u2693 ' + esc(sr.name) + '</span>'
          + '<span style="font-size:8px; font-family:var(--font-mono); padding:1px 5px; background:' + rc + '22; color:' + rc + ';">' + (riskLabels[sr.risk] || '?') + '</span>'
          + '</div>'
          + '<div style="font-size:9px; color:var(--text-dim); margin-top:2px;">' + sr.transit_days + ' days \u2014 ' + esc(sr.form || '') + '</div>'
          + (sr.chokepoints && sr.chokepoints.length ? '<div style="font-size:8px; color:var(--text-muted); margin-top:2px;">Chokepoints: ' + sr.chokepoints.map(esc).join(', ') + '</div>' : '')
          + (sr.note ? '<div style="font-size:8px; color:var(--accent); margin-top:2px;">' + esc(sr.note) + '</div>' : '')
          + '</div>';
      });
    }
    if (allOverlandRoutes.length > 0) {
      rhtml += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em; margin:8px 0 4px;">Overland Routes (' + allOverlandRoutes.length + ')</div>';
      allOverlandRoutes.forEach(function(ol) {
        var rc = riskRouteColors[ol.risk] || '#64748b';
        var icon = modeIcons[ol.mode] || '\u{1F6E4}';
        rhtml += '<div style="margin-bottom:6px; padding:4px 8px; border-left:3px solid ' + rc + '; background:' + rc + '0a;">'
          + '<div style="display:flex; justify-content:space-between; align-items:center;">'
          + '<span style="font-size:10px; font-weight:600; color:var(--text);">' + icon + ' ' + esc(ol.name) + '</span>'
          + '<span style="font-size:8px; font-family:var(--font-mono); padding:1px 5px; background:' + rc + '22; color:' + rc + ';">' + (riskLabels[ol.risk] || '?') + '</span>'
          + '</div>'
          + '<div style="font-size:9px; color:var(--text-dim); margin-top:2px;">' + ol.transit_days + ' days ' + ol.mode + ' \u2014 ' + esc(ol.form || '') + '</div>'
          + (ol.connects_to ? '<div style="font-size:8px; color:var(--accent); margin-top:2px;">Feeds \u2192 ' + esc(ol.connects_to) + '</div>' : '')
          + '</div>';
      });
    }
    routeList.innerHTML = rhtml;
    routeMenu.style.display = '';
    routeList.style.display = 'none';
    document.getElementById('globe-route-toggle').style.transform = 'rotate(-90deg)';
  } else {
    routeMenu.style.display = 'none';
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): update route menu to show sea + overland grouped with icons"
```

---

### Task 5: Update overland route click handler and legend

**Files:**
- Modify: `src/static/index.html` (click handler for `overland-route` type, legend entries)

- [ ] **Step 1: Add overland-route click handler**

In the globe click handler (search for `} else if (type === 'searoute') {`), add an overland-route handler immediately after the searoute block:

```javascript
    } else if (type === 'overland-route') {
      var riskVal = props.risk ? props.risk.getValue() : 'unknown';
      var riskClr = {critical:'#D80621',high:'#a89060',medium:'#eab308',low:'#6b9080'}[riskVal] || '#64748b';
      title.textContent = 'Overland Route';
      html = '<div>' + esc(props.description ? props.description.getValue() : '') + '</div>'
           + '<div style="margin-top:6px;"><span style="font-family:var(--font-mono); padding:2px 8px; background:' + riskClr + '22; color:' + riskClr + '; font-size:10px; font-weight:600;">' + riskVal.toUpperCase() + ' RISK</span></div>';
```

- [ ] **Step 2: Update the globe legend**

In the legend section (search for the `Shipping Route Risk` section heading), update to include overland route legend entries. Find the existing legend section that shows shipping route risk colors and add overland entries:

After the existing sea route risk legend items, add:
```html
<div style="margin-top:6px; border-top:1px solid var(--border); padding-top:4px; font-size:9px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.03em;">Overland Routes</div>
<div><span style="display:inline-block; width:20px; height:3px; background:#a89060; vertical-align:middle; margin-right:6px; box-shadow:0 0 4px #a89060;"></span><span style="color:#a89060;">Truck/Road</span></div>
<div><span style="display:inline-block; width:20px; height:3px; background:#5a7a9b; vertical-align:middle; margin-right:6px; box-shadow:0 0 4px #5a7a9b;"></span><span style="color:#5a7a9b;">Rail</span></div>
```

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add overland route click handler and legend entries"
```

---

### Task 6: Run full tests and visual verification

**Files:** None (verification only)

- [ ] **Step 1: Run full test suite**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && source venv/Scripts/activate && python -m pytest tests/ -q --ignore=tests/test_scenario_adversarial.py`

Expected: 266 passed

- [ ] **Step 2: Start server and verify API**

Run: `python -m src.main`

Then verify: `curl -s http://localhost:8000/globe/minerals/Cobalt | python -c "import sys,json; d=json.load(sys.stdin); print('sea:', len(d.get('sea_routes',[])), 'overland:', len(d.get('overland_routes',[]))); [print(f'  {r[\"id\"]}: {r[\"name\"]} ({len(r[\"waypoints\"])} pts)') for r in d['sea_routes']+d['overland_routes']]"`

Expected: 11 sea routes + 5 overland routes with waypoint counts

- [ ] **Step 3: Visual verification checklist**

Open http://localhost:8000/dashboard → Supply Chain → 3D Supply Map → select Cobalt:

1. Sea routes visible as dashed lines at altitude, risk-colored
2. Overland routes visible as glowing solid lines hugging terrain
3. DRC mine corridor (OL-1) connects visually to Zambia-Durban (OL-2) at Kasumbalesa
4. OL-2 connects to SR-1 (Durban → Shanghai) at Durban port
5. TAZARA rail (OL-3) branches off at Kapiri Mposhi, connects to SR-2 at Dar es Salaam
6. Chinese inland rail (OL-4) connects from coastal ports to Jinchang
7. Canadian rail (OL-5) connects from Montreal to Fort Saskatchewan
8. Layer toggles work: sea routes, overland routes, and labels each hide/show independently
9. Route menu shows both sections with icons and risk badges
10. Clicking a route shows popup with details

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat(globe): complete cobalt route accuracy — 15 routes (10 sea, 5 overland)

Accurate waypoints following real shipping lanes, highways, and rail
corridors for the entire cobalt supply chain from DRC mines to Canadian
refineries. Sea and overland routes as separate toggleable layers."
git push
```
