# Arctic Flight Integration + Freight Estimation Design Spec

**Date**: 2026-04-01
**Goal**: Merge Live Flights tab into the Arctic 3D globe with transport freight estimation and destination projection, then delete the standalone Live Flights tab.
**Scope**: Frontend only (index.html). No new API endpoints. No Python changes.

---

## Part 1: Enhanced Flight Layer on Arctic Globe

The existing `renderArcticFlights()` currently renders all flights as identical colored dots by nation. Enhance to classify aircraft and show freight data.

### Aircraft Classification

Use existing constants `TRANSPORT_TYPES` and `TANKER_TYPES` (already defined in index.html):

| Category | Types | Color | Icon Size |
|----------|-------|-------|-----------|
| Transport | C17, IL76, A124, A400, C130, C30J, C5, C5M, Y20, KC39, C2 | `#10b981` (green) | 8px |
| Tanker | KC10, KC46, A310, A330, KC39 | `#8b5cf6` (purple) | 7px |
| Fighter/Other | Everything else | `#f59e0b` (amber) | 6px |

### Label Format

- **Transport**: `C17 RCH482 → Pituffik (77t)` — type, callsign, destination, payload
- **Tanker**: `KC46 PACK11` — type, callsign
- **Fighter/Other**: `callsign` only (existing behavior)

---

## Part 2: Freight Estimation + Destination Projection

### Payload Lookup Table

```javascript
var TRANSPORT_PAYLOAD_TONNES = {
  'C17': 77, 'C5': 122, 'C5M': 122,
  'IL76': 48, 'A124': 150,
  'A400': 37, 'C130': 19, 'C30J': 19,
  'Y20': 66, 'KC39': 26, 'C2': 30,
};
```

### Destination Estimation Algorithm

For each transport aircraft with `lat > 55`:

1. Compute a ray from aircraft position along its `heading`
2. For each of the 25 Arctic bases, compute:
   - Distance from aircraft to base (haversine)
   - Bearing from aircraft to base
   - Angular difference between aircraft heading and bearing to base
3. Filter: base must be within **±30°** of heading AND within **4,000km**
4. Select the **closest** matching base as estimated destination
5. If no match: label as "Heading: [N/NE/E/etc.] (destination unknown)"

Uses existing `_haversineJS()` function. New helper `_bearingJS(lat1, lon1, lat2, lon2)` computes initial bearing between two points.

### Visual Rendering (Transport Aircraft Only)

**Projected line forward** (to estimated destination):
- Dashed polyline from aircraft position to destination base
- Color matches nation (red=Russia, blue=NATO, amber=China)
- Width: 1.5px, alpha 0.4
- Only drawn when destination is identified

**Trail behind** (~500km):
- Compute position 500km behind aircraft (opposite of heading)
- Fading polyline from trail point to aircraft position
- Same nation color, alpha 0.2
- Gives visual sense of direction/origin

**Freight label** at aircraft position:
- Transport: `[type] [callsign] → [dest] ([payload]t)`
- Font: 9px JetBrains Mono
- Color: green (#10b981) for readability

### Freight Stats Summary

Add a compact stats bar inside the Arctic globe controls area (below the layer toggle buttons):

```html
<div id="arctic-freight-stats" style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim); margin-top:4px;">
  Arctic freight: loading...
</div>
```

Updated on every flight refresh (60s). Format:
```
Arctic freight (est. max): Russia 2× Il-76 = 96t | NATO 3× C-17 = 231t | China 1× Y-20 = 66t
```

If no transports detected: `Arctic freight: No transport aircraft detected above 55°N`

---

## Part 3: Delete Live Flights Tab

### Remove from HTML

- Nav button: `<button class="nav-tab" data-page="live-flights" ...>Live Flights</button>` (line ~1125)
- Page container: `<div id="page-live-flights" class="page">...</div>` (lines ~1703-1727)

### Remove from JavaScript

- Global variables: `flightsMap`, `flightMarkers`, `flightRefreshTimer` (lines ~2454-2456)
- Tab switch case: `if (tab.dataset.page === 'live-flights') loadFlights();` (line ~2578)
- Timer cleanup: `if (flightRefreshTimer) clearTimeout(flightRefreshTimer);` (lines ~2571-2575)
- `loadFlights()` function (lines ~3003-3076)

### Keep (reused by Arctic)

- `TRANSPORT_TYPES` constant (line ~3000)
- `TANKER_TYPES` constant (line ~3001)
- `/tracking/flights/military` API endpoint (called by Arctic tab)
- `/tracking/flights/transports` API endpoint (may be useful)
- `flight_tracker.py`, `flight_patterns.py` — unchanged

---

## Files Modified

| File | Changes |
|------|---------|
| `src/static/index.html` | Enhanced `renderArcticFlights()`, add freight estimation, add destination projection lines/trails, add freight stats bar, delete Live Flights tab + functions |

## Files NOT Modified

- All Python files — no backend changes
- `src/api/routes.py` — flight endpoints stay (used by Arctic)
- `src/ingestion/flight_tracker.py` — unchanged
- `src/analysis/flight_patterns.py` — unchanged

---

## New Functions

| Function | Purpose |
|----------|---------|
| `_bearingJS(lat1, lon1, lat2, lon2)` | Compute initial bearing between two points (degrees) |
| `estimateFlightDestination(flight, bases)` | Find likely destination base within ±30° heading cone, <4000km |
| `updateArcticFreightStats(flights)` | Compute per-nation freight totals, update stats bar |

### Modified Functions

| Function | Changes |
|----------|---------|
| `renderArcticFlights(flights)` | Classify aircraft type, add projected lines + trails for transports, use freight labels, call `updateArcticFreightStats()` |

---

## Test Plan

- Existing tests must pass (no Python changes)
- Manual verification:
  - Arctic tab shows flights with correct classification colors
  - Transport aircraft have projected destination lines + trailing lines
  - Freight labels show payload estimates
  - Stats bar updates with per-nation freight breakdown
  - Clicking Live Flights tab no longer possible (removed from nav)
  - Other tabs unaffected
  - 60-second auto-refresh still works for Arctic flights
