# Globe Layer Control System — Design Spec

**Date:** 2026-04-02
**Scope:** 3D Supply Map sub-tab (Supply Chain page), CesiumJS globe

## Problem

The globe currently renders all entity types (mines, refineries, routes, etc.) in a single flat pass when a mineral is selected. There is no way to toggle individual tiers on/off. This makes the display cluttered and limits analytical utility.

## Solution

Add a collapsible layer control panel overlaid on the globe (top-right corner). Each supply chain tier becomes an independent, toggleable layer. The mineral selector on the left panel remains unchanged.

## Layer Panel UX

### Collapsed State
- Small layers-stack icon button, top-right of the globe container
- Sharp edges, dark surface background, matches military theme
- Monospace "LAYERS" micro-label below the icon

### Expanded State
- Click icon to expand a ~220px panel listing all 8 layers
- Each row: color dot + layer name (monospace, uppercase, 10px) + toggle switch
- Click icon again or X button to collapse
- Panel has dark surface bg with border, same as other dashboard cards

## The 8 Layers

| # | Layer ID | Display Name | Default | Color Dot | Entities Covered |
|---|----------|-------------|---------|-----------|-----------------|
| 1 | `mining` | Mining | ON | `#6b9080` | Mine site circles (scaled by production_t) |
| 2 | `processing` | Processing | ON | `#6b6b8a` | Refinery circles (scaled by capacity_t) |
| 3 | `components` | Components | ON | `#a89060` | Alloy/material small markers |
| 4 | `platforms` | Platforms | ON | `#00d4ff` | Weapon system markers with white outline |
| 5 | `shipping` | Shipping Routes | ON | `#D80621` | Sea lane polylines with risk coloring |
| 6 | `chokepoints` | Chokepoints | ON | `#D80621` | Triangle markers at strategic straits |
| 7 | `ports` | Canadian Ports | ON | `#ff2d2d` | Destination port circles |
| 8 | `arcs` | Flow Arcs | ON | `#00d4ff` | Curved polylines connecting tiers |

## Interaction Model

1. User selects a mineral from the left panel (unchanged)
2. All 8 layers render with entities tagged by `layerId`
3. User clicks the layers icon (top-right) to expand the panel
4. Toggling a layer off hides all Cesium entities with that `layerId`
5. Toggling back on shows them — no API re-fetch, just `entity.show = true/false`
6. Layer visibility state persists across mineral switches (if Shipping Routes is hidden, it stays hidden when switching from Cobalt to Lithium)

## Extensibility

Adding a new layer requires:
1. Add one entry to the `GLOBE_LAYERS` config array: `{ id, name, color, defaultOn }`
2. Tag new entities with that `layerId` during rendering
3. No other code changes — the panel auto-renders from the config array

## Code Changes

### New: `GLOBE_LAYERS` config (top of globe JS section)
```javascript
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
```

### New: `layerVisibility` state object
```javascript
var layerVisibility = {};
GLOBE_LAYERS.forEach(function(l) { layerVisibility[l.id] = l.defaultOn; });
```

### Modified: `renderGlobeEntities()`
- Every `viewer.entities.add()` call must include `layerId` in the entity properties
- After all entities are added, call `applyLayerVisibility()` to respect current toggle state

### New: `toggleGlobeLayer(layerId, visible)`
```javascript
function toggleGlobeLayer(layerId, visible) {
  layerVisibility[layerId] = visible;
  viewer.entities.values.forEach(function(e) {
    if (e.properties && e.properties.layerId &&
        e.properties.layerId.getValue() === layerId) {
      e.show = visible;
    }
  });
  viewer.scene.requestRender();
}
```

### New: `applyLayerVisibility()`
Called after `renderGlobeEntities()` to hide any layers the user has already toggled off.

### New: Layer panel HTML/CSS
- Injected into the `#cesium-globe` container div as an overlay
- CSS: absolute positioned, top-right, z-index above globe but below popups
- Toggle switches styled with the existing theme (sharp edges, monospace, dark surface)

### New: `renderLayerPanel()`
Builds the panel HTML from `GLOBE_LAYERS` config array. Wires up click handlers that call `toggleGlobeLayer()`.

## Entity-to-Layer Mapping

Current `renderGlobeEntities()` code sections and their layer assignments:

| Code Section | Current Lines | Layer ID |
|-------------|--------------|----------|
| Deep-dive mines (`m.mines` array) | 7759-7776 | `mining` |
| Country-level mining aggregates | 7778-7795 | `mining` |
| Deep-dive refineries (`m.refineries`) | 7797-7815 | `processing` |
| Country-level processing aggregates | 7817-7834 | `processing` |
| Components markers | 7836-7849 | `components` |
| Platform markers | 7852-7865 | `platforms` |
| Chokepoint triangles | 7868-7880 | `chokepoints` |
| Flow arcs (tier connections) | 7882-7898 | `arcs` |
| Shipping route polylines | 7906-7948 | `shipping` |
| Fallback single route | 7949-7981 | `shipping` |
| Canadian port markers | 7984-8000 | `ports` |

## Styling

- Panel background: `var(--surface)` with `1px solid var(--border)`
- No border-radius (sharp military edges)
- Layer name: `font-family: var(--font-mono)`, `font-size: 10px`, `letter-spacing: 1.5px`, `text-transform: uppercase`, `color: var(--text-dim)`
- Color dot: 8px circle with the layer's signature color
- Toggle: small custom switch (16px track, matching theme)
- Panel header: "LAYERS" in `var(--font-mono)`, 8px, `letter-spacing: 2.5px`, `color: var(--text-muted)`
- Icon button: 32x32px, layers-stack SVG icon in `var(--text-dim)`, hover cyan
