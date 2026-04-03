# Globe Layer Control System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a collapsible layer control panel to the CesiumJS 3D Supply Map so each supply chain tier (mining, processing, routes, etc.) can be toggled independently.

**Architecture:** All changes are in `src/static/index.html`. A `GLOBE_LAYERS` config array drives both the panel UI and the entity tagging. Each Cesium entity gets a `layerId` property during rendering. Toggling a layer just sets `entity.show = true/false` — no API re-fetch. Layer state persists across mineral switches.

**Tech Stack:** CesiumJS (existing), vanilla JS, CSS variables (existing theme)

---

### Task 1: Add GLOBE_LAYERS config and layer state

**Files:**
- Modify: `src/static/index.html` — JS section, insert before `initCesiumGlobe()` (line ~7280)

- [ ] **Step 1: Add the config array and state object**

Find the line `async function initCesiumGlobe() {` (around line 7280) and insert this block immediately BEFORE it:

```javascript
/* ── Globe Layer System ── */
var GLOBE_LAYERS = [
  { id: 'mining',      name: 'Mining',           color: '#6b9080', defaultOn: true },
  { id: 'processing',  name: 'Processing',       color: '#6b6b8a', defaultOn: true },
  { id: 'components',  name: 'Components',        color: '#a89060', defaultOn: true },
  { id: 'platforms',   name: 'Platforms',          color: '#00d4ff', defaultOn: true },
  { id: 'shipping',    name: 'Shipping Routes',   color: '#D80621', defaultOn: true },
  { id: 'chokepoints', name: 'Chokepoints',       color: '#D80621', defaultOn: true },
  { id: 'ports',       name: 'Canadian Ports',     color: '#ff2d2d', defaultOn: true },
  { id: 'arcs',        name: 'Flow Arcs',          color: '#00d4ff', defaultOn: true },
];
var layerVisibility = {};
GLOBE_LAYERS.forEach(function(l) { layerVisibility[l.id] = l.defaultOn; });
```

- [ ] **Step 2: Add toggleGlobeLayer and applyLayerVisibility functions**

Insert immediately after the config block:

```javascript
function toggleGlobeLayer(layerId, visible) {
  layerVisibility[layerId] = visible;
  cesiumViewer.entities.values.forEach(function(e) {
    if (e.properties && e.properties.layerId &&
        e.properties.layerId.getValue() === layerId) {
      e.show = visible;
    }
  });
  cesiumViewer.scene.requestRender();
}

function applyLayerVisibility() {
  cesiumViewer.entities.values.forEach(function(e) {
    if (e.properties && e.properties.layerId) {
      var lid = e.properties.layerId.getValue();
      if (layerVisibility[lid] !== undefined) {
        e.show = layerVisibility[lid];
      }
    }
  });
  cesiumViewer.scene.requestRender();
}
```

- [ ] **Step 3: Verify no syntax errors**

Run: Open `http://localhost:8000/dashboard` in browser, open console, navigate to Supply Chain > 3D Supply Map. Confirm no JS errors on load.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add GLOBE_LAYERS config and toggle functions"
```

---

### Task 2: Tag all entities with layerId in renderGlobeEntities()

**Files:**
- Modify: `src/static/index.html` — `renderGlobeEntities()` function (lines ~7736-8001)

Every `cesiumViewer.entities.add()` call needs a `layerId` added to its `properties` object. There are 11 entity-creation blocks to update.

- [ ] **Step 1: Tag deep-dive mines with layerId 'mining'**

In `renderGlobeEntities()`, find the deep-dive mines block (starts with `m.mines.forEach`). In the `properties` object of the `entities.add()` call, add `layerId: 'mining'` at the beginning:

```javascript
          properties: { layerId: 'mining', type: 'mine', mineral: m.name, name: mine.name, owner: mine.owner, country: mine.country, production: mine.production_t || 0, note: mine.note || '', flags: (mine.flags || []).join(', '), risks: JSON.stringify(mine.risks || []), foci_assessment: (mine.dossier && mine.dossier.foci_assessment) || '', z_score: (mine.dossier && mine.dossier.z_score != null) ? mine.dossier.z_score : -1 },
```

- [ ] **Step 2: Tag country-level mining markers with layerId 'mining'**

Find the country-level mining block (starts with `m.mining.forEach`). Add `layerId: 'mining'` to properties:

```javascript
          properties: { layerId: 'mining', type: 'mining', mineral: m.name, country: site.country, pct: site.pct },
```

- [ ] **Step 3: Tag deep-dive refineries with layerId 'processing'**

Find the refineries block (starts with `m.refineries.forEach`). Add `layerId: 'processing'` to properties:

```javascript
          properties: { layerId: 'processing', type: 'refinery', mineral: m.name, name: ref.name, owner: ref.owner, country: ref.country, capacity: ref.capacity_t || 0, products: ref.products || '', note: ref.note || '', flags: (ref.flags || []).join(', '), risks: JSON.stringify(ref.risks || []), foci_assessment: (ref.dossier && ref.dossier.foci_assessment) || '', z_score: (ref.dossier && ref.dossier.z_score != null) ? ref.dossier.z_score : -1 },
```

- [ ] **Step 4: Tag country-level processing markers with layerId 'processing'**

Find the country-level processing block (starts with `m.processing.forEach` inside the else). Add `layerId: 'processing'` to properties:

```javascript
          properties: { layerId: 'processing', type: 'processing', mineral: m.name, country: site.country, pct: site.pct, processType: site.type },
```

- [ ] **Step 5: Tag component markers with layerId 'components'**

Find the components block (starts with `m.components.forEach`). Add `layerId: 'components'` to properties:

```javascript
        properties: { layerId: 'components', type: 'component', mineral: m.name, name: comp.name, country: comp.manufacturer_country },
```

- [ ] **Step 6: Tag platform markers with layerId 'platforms'**

Find the platforms block (starts with `m.platforms.forEach`). Add `layerId: 'platforms'` to properties:

```javascript
        properties: { layerId: 'platforms', type: 'platform', mineral: m.name, name: plat.name, country: plat.assembly_country },
```

- [ ] **Step 7: Tag chokepoint markers with layerId 'chokepoints'**

Find the chokepoints block (starts with `(m.chokepoints || []).forEach`). Add `layerId: 'chokepoints'` to properties:

```javascript
        properties: { layerId: 'chokepoints', type: 'chokepoint', mineral: m.name, name: cp.name },
```

- [ ] **Step 8: Tag shipping route polylines with layerId 'shipping'**

There are two places shipping routes are created:

**8a.** In the deep-dive shipping routes block (`m.shipping_routes.forEach`), update the route polyline properties:

```javascript
          properties: {
            layerId: 'shipping', type: 'searoute', mineral: m.name, risk: sr.risk || 'unknown',
            description: sr.name + ' (' + sr.transit_days + ' days) — ' + (sr.form || '') + (sr.risk_reason ? ' | RISK: ' + sr.risk_reason : '') + (sr.note ? ' | ' + sr.note : ''),
          },
```

**8b.** In the same block, the endpoint port markers need `layerId: 'ports'`:

```javascript
            properties: { layerId: 'ports', type: 'port', mineral: m.name, name: sr.name, desc: sr.description + (sr.onward ? ' | Onward: ' + sr.onward : '') },
```

**8c.** In the fallback single-route block (`} else if (m.processing.length > 0) {`), update the route polyline properties:

```javascript
            properties: { layerId: 'shipping', type: 'searoute', mineral: m.name, description: m.name + ': ' + source.country + ' \u2192 ' + port.name },
```

**8d.** In the same fallback block, the `addFlowArc` call should be tagged as shipping — but `addFlowArc` creates entities internally. We'll handle this in Step 10.

**8e.** In the fallback block, the port marker needs `layerId: 'ports'`:

```javascript
        properties: { layerId: 'ports', type: 'port', mineral: m.name, name: port.name, desc: port.desc },
```

- [ ] **Step 9: Tag Canadian ports context markers with layerId 'ports'**

Find the `CANADA_PORTS.forEach` block at the bottom of `renderGlobeEntities()`. Add `layerId: 'ports'` to properties:

```javascript
      properties: { layerId: 'ports', type: 'port', name: port.name, desc: port.desc },
```

- [ ] **Step 10: Update addFlowArc to accept and tag layerId**

Find `function addFlowArc(lon1, lat1, lon2, lat2, color, description)` (around line 8003).

Change the function signature to accept an optional `layerId` parameter:

```javascript
function addFlowArc(lon1, lat1, lon2, lat2, color, description, layerId) {
```

Then in the `cesiumViewer.entities.add()` call inside `addFlowArc`, add `layerId` to properties. Find the properties line and replace it:

```javascript
      properties: { layerId: layerId || 'arcs', type: 'flowarc', description: description },
```

Now update the two existing `addFlowArc` calls in `renderGlobeEntities()`:

**10a.** Mining → Processing arcs (around line 7887):
```javascript
        addFlowArc(topMiner.lon, topMiner.lat, proc.lon, proc.lat, arcColor, m.name + ': ' + topMiner.country + ' \u2192 ' + proc.country, 'arcs');
```

**10b.** Processing → Component arcs (around line 7896):
```javascript
        addFlowArc(topProc.lon, topProc.lat, comp.lon, comp.lat, arcColor.withAlpha(0.6), m.name + ': ' + topProc.country + ' \u2192 ' + comp.manufacturer_country, 'arcs');
```

**10c.** Fallback route arc (around line 7967):
```javascript
          addFlowArc(source.lon, source.lat, port.lon, port.lat, canadaRouteColor.withAlpha(0.5), m.name + ': ' + source.country + ' \u2192 ' + port.name, 'shipping');
```

- [ ] **Step 11: Call applyLayerVisibility at end of renderGlobeEntities**

At the very end of `renderGlobeEntities()`, just before the closing `}`, add:

```javascript
  applyLayerVisibility();
```

- [ ] **Step 12: Verify entities are tagged**

Open browser, navigate to Supply Chain > 3D Supply Map > Cobalt. Open console and run:
```javascript
cesiumViewer.entities.values.forEach(function(e) { if (e.properties && e.properties.layerId) console.log(e.properties.layerId.getValue(), e.properties.type.getValue()); });
```
Expected: Each entity logs its layerId and type. Should see `mining`, `processing`, `components`, `platforms`, `shipping`, `chokepoints`, `ports`, `arcs`.

- [ ] **Step 13: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): tag all entities with layerId for layer control"
```

---

### Task 3: Add layer panel CSS

**Files:**
- Modify: `src/static/index.html` — CSS section, add before `</style>` (near the atmosphere/side-nav CSS)

- [ ] **Step 1: Add layer panel CSS**

Find the `/* ── Right Side Nav ── */` comment in the CSS and insert this block BEFORE it:

```css
/* ── Globe Layer Panel ── */
.globe-layer-btn{
  position:absolute;top:12px;right:12px;z-index:10;
  width:32px;height:32px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
  background:var(--surface);border:1px solid var(--border);cursor:pointer;transition:all .25s;
}
.globe-layer-btn:hover{border-color:var(--accent);color:var(--accent);}
.globe-layer-btn svg{width:16px;height:16px;stroke:var(--text-dim);fill:none;stroke-width:1.6;}
.globe-layer-btn:hover svg{stroke:var(--accent);}
.globe-layer-btn .glb-label{font-family:var(--font-mono);font-size:6px;letter-spacing:1.5px;color:var(--text-muted);text-transform:uppercase;margin-top:1px;}
.globe-layer-panel{
  position:absolute;top:12px;right:12px;z-index:10;width:220px;
  background:var(--surface);border:1px solid var(--border);
  display:none;flex-direction:column;
}
.globe-layer-panel.open{display:flex;}
.glp-header{
  display:flex;align-items:center;justify-content:space-between;
  padding:8px 12px;border-bottom:1px solid var(--border);
}
.glp-title{font-family:var(--font-mono);font-size:8px;letter-spacing:2.5px;color:var(--text-muted);text-transform:uppercase;}
.glp-close{background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:14px;line-height:1;padding:0 2px;}
.glp-close:hover{color:var(--accent);}
.glp-row{
  display:flex;align-items:center;gap:8px;padding:7px 12px;
  border-bottom:1px solid var(--border);transition:background .15s;
}
.glp-row:last-child{border-bottom:none;}
.glp-row:hover{background:rgba(0,212,255,0.03);}
.glp-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.glp-name{font-family:var(--font-mono);font-size:10px;letter-spacing:1.5px;color:var(--text-dim);text-transform:uppercase;flex:1;}
.glp-toggle{
  position:relative;width:28px;height:14px;border-radius:7px;
  background:var(--border-hover);cursor:pointer;flex-shrink:0;transition:background .25s;
}
.glp-toggle.on{background:var(--accent);}
.glp-toggle::after{
  content:'';position:absolute;top:2px;left:2px;width:10px;height:10px;
  border-radius:50%;background:#fff;transition:left .25s;
}
.glp-toggle.on::after{left:16px;}
```

- [ ] **Step 2: Verify CSS loads without errors**

Refresh the dashboard. No visual change yet (HTML not added), but confirm no CSS parse errors in console.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add layer panel CSS"
```

---

### Task 4: Add layer panel HTML and render function

**Files:**
- Modify: `src/static/index.html` — JS section, add `renderLayerPanel()` function after `applyLayerVisibility()`

- [ ] **Step 1: Add renderLayerPanel function**

Insert immediately after the `applyLayerVisibility()` function (from Task 1):

```javascript
function renderLayerPanel() {
  var container = document.getElementById('cesium-globe');
  // Remove existing panel elements if re-rendering
  var old = container.querySelector('.globe-layer-btn');
  if (old) old.remove();
  var oldPanel = container.querySelector('.globe-layer-panel');
  if (oldPanel) oldPanel.remove();

  // Icon button (collapsed state)
  var btn = document.createElement('div');
  btn.className = 'globe-layer-btn';
  btn.setAttribute('title', 'Toggle layers');
  btn.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg><span class="glb-label">Layers</span>';
  container.appendChild(btn);

  // Panel (expanded state)
  var panel = document.createElement('div');
  panel.className = 'globe-layer-panel';
  var html = '<div class="glp-header"><span class="glp-title">Layers</span><button class="glp-close">&times;</button></div>';
  GLOBE_LAYERS.forEach(function(l) {
    var on = layerVisibility[l.id] !== false;
    html += '<div class="glp-row" data-layer="' + l.id + '">'
      + '<span class="glp-dot" style="background:' + l.color + ';"></span>'
      + '<span class="glp-name">' + l.name + '</span>'
      + '<div class="glp-toggle' + (on ? ' on' : '') + '" data-layer="' + l.id + '"></div>'
      + '</div>';
  });
  panel.innerHTML = html;
  container.appendChild(panel);

  // Wire up: button opens panel, hides button
  btn.addEventListener('click', function() {
    btn.style.display = 'none';
    panel.classList.add('open');
  });
  // Wire up: close button hides panel, shows button
  panel.querySelector('.glp-close').addEventListener('click', function() {
    panel.classList.remove('open');
    btn.style.display = '';
  });
  // Wire up: toggle switches
  panel.querySelectorAll('.glp-toggle').forEach(function(tog) {
    tog.addEventListener('click', function() {
      var lid = this.dataset.layer;
      var isOn = this.classList.toggle('on');
      toggleGlobeLayer(lid, isOn);
    });
  });
}
```

- [ ] **Step 2: Call renderLayerPanel from initCesiumGlobe**

In `initCesiumGlobe()`, find the line `renderMineralLayerPanel();` (around line 7365) and add `renderLayerPanel();` right after it:

```javascript
  renderMineralLayerPanel();
  renderLayerPanel();
  setupGlobeClickHandler();
```

- [ ] **Step 3: Verify the layer panel works**

Open browser, navigate to Supply Chain > 3D Supply Map. You should see:
1. A small layers icon button in the top-right of the globe
2. Click it — the panel expands showing 8 layers, all toggled ON
3. Toggle "Mining" OFF — all mine markers disappear from the globe
4. Toggle "Mining" back ON — they reappear
5. Toggle "Shipping Routes" OFF — sea lane polylines disappear
6. Close the panel (X) — icon button reappears
7. Switch from Cobalt to another mineral — layer toggle states persist (if Mining was OFF, it stays OFF)

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat(globe): add collapsible layer control panel with 8 toggleable layers"
```

---

### Task 5: Final polish and push

**Files:**
- Modify: `src/static/index.html` — minor adjustments

- [ ] **Step 1: Ensure the globe container has position:relative**

The layer panel uses `position:absolute`, so its parent needs `position:relative`. Find the `#cesium-globe` styling. It's set inline in the HTML around line 2040. Check if it already has `position:relative`. If not, find:

```html
<div id="cesium-globe" style="flex:1; min-height:500px;">
```

And add `position:relative;`:

```html
<div id="cesium-globe" style="flex:1; min-height:500px; position:relative;">
```

- [ ] **Step 2: Test all 8 layers independently**

For each layer, toggle it OFF and verify ONLY those entities disappear:

| Layer | What should disappear |
|-------|----------------------|
| Mining | Green/red mine circles |
| Processing | Purple/red refinery circles |
| Components | Small ochre markers |
| Platforms | Cyan markers with white outline |
| Shipping Routes | Dashed polylines (sea lanes) |
| Chokepoints | Red triangles |
| Canadian Ports | Red port circles + labels |
| Flow Arcs | Curved glow lines between tiers |

- [ ] **Step 3: Test layer persistence across mineral switches**

1. Toggle Mining OFF and Shipping Routes OFF
2. Switch from Cobalt to Lithium (or any other mineral)
3. Verify Mining and Shipping Routes are still hidden
4. Toggle them back ON — they should appear with the new mineral's data

- [ ] **Step 4: Push to GitHub**

```bash
git push
```
