# Per-Mineral Knowledge Graph — Design Spec

**Date:** 2026-03-30
**Location:** Supply Chain tab → Knowledge Graph sub-tab
**Scope:** Cobalt prototype only (other 29 minerals fall back to existing "All" view)

---

## Overview

Add a mineral selector dropdown to the Knowledge Graph sub-tab. When "Cobalt" is selected, the graph switches from the existing force-directed layout to a 5-tier left-to-right layered graph showing the full dependency chain: mines → refineries → alloys → engines → platforms. Clicking a node highlights upstream suppliers and downstream dependents. Hovering shows a tooltip. All data comes from the existing `/globe/minerals/Cobalt` endpoint — no new API endpoints or Python changes needed.

---

## Section 1: Mineral Selector & Graph Switching

A dropdown added to the existing Knowledge Graph controls bar (next to type filter and risk slider). Populated from `/globe/minerals` (30 minerals). Defaults to "All" showing the current force-directed full graph.

When "Cobalt" is selected:
- Graph container clears and rebuilds as a 5-tier layered layout
- Type filter and risk slider still work as additional filters
- Minerals with deep data (mines/refineries/alloys) get a star indicator in the dropdown

When "All" is selected:
- Reverts to the existing force-directed graph from `/psi/graph`

Only Cobalt has the layered view for now. Selecting any other mineral reverts to "All" until deep data is built.

---

## Section 2: Per-Mineral Graph Data

Graph builds from Cobalt mineral dict data (`/globe/minerals/Cobalt`). ~45 nodes across 5 tiers:

| Tier | Column | Node Source | Count | Shape |
|------|--------|-------------|:-----:|-------|
| 1 - Mining | Left | `m.mines[]` | 9 | Circle |
| 2 - Refining | Center-left | `m.refineries[]` | 9 | Square |
| 3 - Alloys | Center | `m.alloys[]` | 8 | Diamond |
| 4 - Engines | Center-right | `m.sufficiency.demand[]` indirect entries (unique `engine` values) | 8 | Hexagon |
| 5 - Platforms | Right | `m.sufficiency.demand[]` (all 16 entries) | 16 | Star |

**Edge inference:**
- Mine → Refinery: by country match (DRC mines → Chinese refineries) and known ownership chains
- Refinery → Alloy: all refineries connect to all alloys (cobalt is feedstock for all)
- Alloy → Engine: from `sufficiency.demand[].alloy` field matching alloy name
- Engine → Platform: from `sufficiency.demand[].engine` and `sufficiency.demand[].platform` fields

---

## Section 3: Node Styling & Risk Visualization

**Fill color = risk level:**
- Critical: `#ef4444` (red)
- High: `#f59e0b` (amber)
- Medium: `#eab308` (yellow)
- Low: `#10b981` (green)

Risk level source:
- Mines/Refineries: composite average of `taxonomy_scores`
- Alloys: inherited from highest-risk refinery feeding them
- Engines/Platforms: from `sufficiency.demand[].threshold_ratio` (lower threshold = higher risk)

**Border color = country control:**
- Adversary-controlled (China, Russia, DRC): `#ef4444` red border, 3px
- NATO-allied (US, Canada, UK, Finland, Belgium, Germany, Australia, Japan): `#3b82f6` blue border, 2px
- Neutral: `#64748b` gray border, 1px

**Node labels:** Name below each node, truncated to 15 chars, full name on hover.

**Edge styling:**
- Sole-source / critical path: solid red, 2px
- Normal: dashed gray, 1px
- Highlighted (on click): glowing cyan (#00d4ff), 3px

---

## Section 4: Click Interaction — Dependency Path Highlighting

**On node click:**

1. **Upstream trace** — all nodes and edges feeding INTO the clicked node highlight in cyan. Clicking "P&W F135 Engine" highlights ← CMSX-4 ← refineries ← mines.

2. **Downstream trace** — all nodes and edges depending ON the clicked node highlight in amber. Clicking "Huayou Cobalt" highlights → alloys → engines → platforms.

3. **Info panel** — detail card appears to the right of the graph:
   - Node name, tier, country, owner
   - Risk level color badge
   - `🔗 INDIRECT` or `🍁 DIRECT` badge (for platforms)
   - Key stats: production tonnage (mines), capacity (refineries), Co% (alloys), fleet size (platforms)
   - "Upstream: X nodes" / "Downstream: Y nodes"

4. **Click elsewhere** or same node again to clear highlights.

**Hover:** tooltip with name, type, country, risk level. Lightweight — no info panel.

---

## Section 5: Layout Algorithm

5-tier left-to-right layout using D3 with fixed x-positions per tier:

```
x positions (as % of container width):
  Tier 1 (Mines):     10%
  Tier 2 (Refineries): 30%
  Tier 3 (Alloys):     50%
  Tier 4 (Engines):    70%
  Tier 5 (Platforms):  90%

y positions: evenly spaced within each tier column, centered vertically
```

Nodes within each tier are sorted by risk level (highest risk at top). Edges rendered as curved bezier paths (D3 `linkHorizontal`) to avoid overlap.

Container height adjusts to fit the tallest column (Platforms with 16 nodes needs ~600px minimum).

---

## Scope

- **In scope:** Cobalt per-mineral graph, mineral dropdown, layered layout, click interaction, info panel
- **Out of scope:** Deep data for other 29 minerals, new API endpoints, Python changes, tests
- **Files modified:** `src/static/index.html` only (CSS + HTML + JS)
