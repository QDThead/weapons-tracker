# Cobalt Demand vs Supply Sufficiency UI — Design Spec

**Date:** 2026-03-29
**Location:** Supply Chain tab → 3D Supply Map sub-tab → Globe detail panel (new row below existing content)

---

## Overview

Add a "Demand & Supply Sufficiency" row to the Cobalt globe detail panel that shows Canada's dependency on foreign OEM supply chains, lets analysts simulate disruption scenarios with a continuous slider, and surfaces recommended courses of action on demand.

**Core insight this UI communicates:** Canada's military cobalt demand is 0.0003% of global production. The vulnerability is not volume — it is supply chain architecture. Canada does not manufacture jet engines or cast superalloy components. These come from US OEMs who depend on a global supply chain where China controls 80% of refining.

---

## Layout

New full-width row appended below the existing Route/Risk/Canada row in the globe detail panel. Three components side by side:

```
┌─────────────────────────────────────────────────────────────┐
│  [Header: Cobalt | CRITICAL | HHI 5900]          existing  │
│  [Mining | Processing | Components | Platforms]   existing  │
│  [Route to Canada | Risk Assessment | Canada Impact] exist. │
│                                                             │
│  ── DEMAND & SUPPLY SUFFICIENCY (new) ───────────────────  │
│  [Radial Gauge ~25%] [Platform Cards ~50%] [Slider ~25%]   │
│  [              📋 View Recommended Actions               ] │
└─────────────────────────────────────────────────────────────┘
```

Only appears for minerals that have `sufficiency` data (Cobalt first, others later).

---

## Component 1: Radial Supply Gauge (~25% width)

Speedometer-style half-circle gauge.

**Color zones:**
- Red (0–0.5x ratio) — critical deficit
- Amber (0.5–0.9x) — supply stress
- Green (0.9x+) — sufficient

**Display elements:**
- Large center number: ratio (e.g., `0.23x`)
- Verdict text below: "77% DEFICIT — CRITICAL" (color-matched to zone)
- Current scenario name in muted text
- Supply and demand numbers: "Supply: 12,500 t/yr | Demand: 54,000 t/yr"

Gauge needle animates smoothly as the scenario slider moves. Ratio, verdict, and supply/demand numbers update in sync.

---

## Component 2: Platform Dependency Cards (~50% width)

Scrollable vertical list of CAF platform cards showing direct vs indirect dependency chains.

**Each card contains:**
- Header row: platform name + dependency badge (`🔗 INDIRECT` purple or `🍁 DIRECT` cyan)
- Subtext: fleet size, engine type
- Dependency chain breadcrumb: colored pill badges
  - Cyan pill: mineral (e.g., `Cobalt`)
  - Purple pills: OEM steps (e.g., `CMSX-4 (9.5% Co)` → `P&W F135 Engine`)
  - Green pill: Canada endpoint (e.g., `🍁 CAF`)
- Risk note: amber warning for indirect chains, green checkmark for direct

**Example indirect card:**
```
F-35A Lightning II                               🔗 INDIRECT
88 aircraft on order (2026-2032)
[Cobalt] → [CMSX-4 (9.5% Co)] → [P&W F135 Engine] → [🍁 CAF]
⚠ China controls 80% of cobalt refining in this chain
```

**Example direct card:**
```
BB-2590 Soldier Batteries                        🍁 DIRECT
~800 batteries/yr — Li-ion NMC/LCO chemistry
[Cobalt] → [NMC Cathode] → [🍁 Canadian MRO]
✓ Domestic procurement — shorter supply chain
```

**Scenario interaction — cards react to slider:**
- When supply drops below a platform's threshold ratio, the card gets a red left border and amber/red background tint
- Risk note updates: "⛔ GROUNDED — cobalt refining unavailable at this disruption level"
- At-risk platforms re-sort to the top of the list
- Platforms that remain supplied keep normal styling

**Threshold logic:** Each platform has a `threshold_ratio` below which it's at risk. Indirect/OEM platforms have higher thresholds (break earlier — they depend on global supply chains). Direct/domestic platforms have lower thresholds (survive longer — shorter chains, Canadian sources).

---

## Component 3: Scenario Slider (~25% width)

Vertical continuous slider, 0–100% disruption level. Five preset snap points with labels:

| Position | Scenario | Supply | Demand | Ratio | Verdict |
|----------|----------|--------|--------|-------|---------|
| 0% | Normal operations | 237,000 t/yr | 237,000 t/yr | 1.0x | Balanced |
| 25% | China export ban | 31,500 t/yr | 54,000 t/yr | 0.73x | 27% deficit |
| 50% | China + DRC collapse | 12,500 t/yr | 54,000 t/yr | 0.23x | 77% deficit — CRITICAL |
| 65% | Defence priority allocation | 31,500 t/yr | 8,000 t/yr | 4.9x | Sufficient if govts intervene |
| 100% | Canada sovereign only | 2,500 t/yr | 0.74 t/yr | 3,400x | Volume not the problem |

**Interaction:**
- Dragging between presets interpolates supply/demand values linearly
- Clicking a preset label snaps to that position
- Current scenario name and supply/demand values displayed above the slider
- All three components (gauge, cards, slider label) update in real-time as the slider moves

---

## Component 4: COA Recommendations (on-demand toggle)

Button below the sufficiency row: **"📋 View Recommended Actions"**

Clicking expands a panel with 6 course-of-action cards:

| COA | Action | Cost | Impact |
|-----|--------|------|--------|
| COA-1 | Sovereign cobalt stockpile (500t refined metal) | ~$15M | 60 years CAF demand; bridges any disruption |
| COA-2 | Increase engine overhaul parts buffer to 24 months | ~$100M | Eliminates grounding risk regardless of cause |
| COA-3 | Restart Sherritt Fort Saskatchewan with non-Cuban feedstock | $50-150M | 6,300 t/yr sovereign refining capacity |
| COA-4 | Formalize allied cobalt allocation under DPSA with US DoD | $0 | Guaranteed access to US superalloy components |
| COA-5 | Superalloy scrap recycling at Canadian MRO depots | $5-10M | ~200 kg/yr cobalt recovered |
| COA-6 | Engine health monitoring to extend overhaul intervals 15-25% | ~$20M | Reduces parts consumption + improves availability |

Each COA card highlights based on relevance to the current scenario slider position (e.g., at "China export ban," COA-1, COA-3, and COA-4 highlight as most impactful).

Clicking the button again collapses the panel. Cards styled with glass-morphism matching the existing design system.

---

## Data Architecture

New `sufficiency` key added to the Cobalt dict in `src/analysis/mineral_supply_chains.py`:

```python
"sufficiency": {
    "demand": [
        {
            "platform": "CF-188 Hornet",
            "kg_yr": 56,
            "type": "indirect",
            "oem": "GE Aviation",
            "oem_country": "US",
            "alloy": "Waspaloy",
            "alloy_co_pct": 13.0,
            "engine": "GE F404",
            "fleet_size": 76,
            "fleet_note": "76 aircraft — 2x GE F404 engines each",
            "threshold_ratio": 0.7,
            "risk_note": "Engine overhaul parts sourced through US OEM"
        },
        {
            "platform": "BB-2590 Soldier Batteries",
            "kg_yr": 50,
            "type": "direct",
            "use": "Li-ion NMC/LCO",
            "qty_yr": 800,
            "fleet_note": "~800 batteries/yr — Li-ion NMC/LCO chemistry",
            "threshold_ratio": 0.3,
            "risk_note": "Domestic procurement — shorter supply chain"
        },
        ...all 16 platforms from HANDOVER.md
    ],
    "scenarios": [
        {
            "name": "Normal operations",
            "position": 0,
            "supply_t": 237000,
            "demand_t": 237000,
            "ratio": 1.0,
            "verdict": "Balanced"
        },
        {
            "name": "China export ban",
            "position": 25,
            "supply_t": 31500,
            "demand_t": 54000,
            "ratio": 0.73,
            "verdict": "27% deficit"
        },
        {
            "name": "China + DRC collapse",
            "position": 50,
            "supply_t": 12500,
            "demand_t": 54000,
            "ratio": 0.23,
            "verdict": "77% deficit — CRITICAL"
        },
        {
            "name": "Defence priority allocation",
            "position": 65,
            "supply_t": 31500,
            "demand_t": 8000,
            "ratio": 4.9,
            "verdict": "Sufficient if governments intervene"
        },
        {
            "name": "Canada sovereign only",
            "position": 100,
            "supply_t": 2500,
            "demand_t": 0.74,
            "ratio": 3400,
            "verdict": "Volume not the problem"
        }
    ],
    "coa": [
        {
            "id": "COA-1",
            "action": "Sovereign cobalt stockpile (500t refined metal)",
            "cost": "~$15M",
            "impact": "60 years CAF demand; bridges any disruption",
            "relevant_scenarios": [25, 50]
        },
        {
            "id": "COA-2",
            "action": "Increase engine overhaul parts buffer to 24 months",
            "cost": "~$100M",
            "impact": "Eliminates grounding risk regardless of cause",
            "relevant_scenarios": [25, 50, 65]
        },
        {
            "id": "COA-3",
            "action": "Restart Sherritt Fort Saskatchewan with non-Cuban feedstock",
            "cost": "$50-150M",
            "impact": "6,300 t/yr sovereign refining capacity",
            "relevant_scenarios": [25, 50]
        },
        {
            "id": "COA-4",
            "action": "Formalize allied cobalt allocation under DPSA with US DoD",
            "cost": "$0",
            "impact": "Guaranteed access to US superalloy components",
            "relevant_scenarios": [25, 50, 65]
        },
        {
            "id": "COA-5",
            "action": "Superalloy scrap recycling at Canadian MRO depots",
            "cost": "$5-10M",
            "impact": "~200 kg/yr cobalt recovered",
            "relevant_scenarios": [50, 65, 100]
        },
        {
            "id": "COA-6",
            "action": "Engine health monitoring to extend overhaul intervals 15-25%",
            "cost": "~$20M",
            "impact": "Reduces parts consumption + improves availability",
            "relevant_scenarios": [25, 50, 65]
        }
    ],
    "totals": {
        "steady_state_kg": 298,
        "f35_ramp_kg": 740,
        "direct_kg": 138,
        "indirect_kg": 160
    }
}
```

**No new API endpoints needed.** The existing `GET /globe/minerals/Cobalt` returns this data as part of the mineral dict. All rendering logic lives in `src/static/index.html`.

**No new database tables needed.** Sufficiency data is static research baked into the mineral dict, same as mines/refineries/alloys.

---

## Styling

- Follows existing design system: glass-morphism cards, Outfit/IBM Plex Sans/JetBrains Mono fonts
- Color coding:
  - Cyan (`#00d4ff`): direct dependency, mineral pills
  - Purple (`#8b5cf6`): indirect/OEM dependency, OEM pills
  - Green (`#10b981`): Canada endpoint, sufficient supply
  - Amber (`#f59e0b`): supply stress, warning notes
  - Red (`#ef4444`): critical deficit, grounded platforms
- Platform cards use existing `.card` pattern with colored left border for risk state
- COA cards use glass-morphism with highlight glow when relevant to current scenario
- Gauge uses CSS conic-gradient for color zones, animated with CSS transitions

---

## Scope

- **In scope:** Cobalt sufficiency UI (data, rendering, slider interaction, COA toggle)
- **Out of scope:** Sufficiency data for other 29 minerals (future work, same structure)
- **Out of scope:** PDF export of sufficiency view (future enhancement)
- **Files modified:** `src/analysis/mineral_supply_chains.py` (add sufficiency data), `src/static/index.html` (add rendering + interaction)
- **Files created:** None
- **Tests:** Add tests for sufficiency data structure integrity in `tests/test_globe.py`
