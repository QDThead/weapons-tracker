# Design Spec: Production Verification Sub-Tab

**Date:** 2026-04-03
**Status:** Draft
**Depends on:** FIRMS thermal (done), Sentinel-5P NO2 (done)

## Problem

We now have two independent satellite signals for each cobalt facility — thermal (FIRMS) and NO2 emissions (Sentinel-5P). We also have rated production capacity from USGS/company IR filings. But these three data streams live in separate sections of the UI. There's no single view that overlays satellite activity against reported production to answer: **"Is this facility producing what it claims?"**

Enclosed refineries that report full capacity but show no thermal or NO2 signature are suspicious. Mines that show high satellite activity during a "reported pause" are suspicious. This sub-tab makes those discrepancies visible.

## Goals

1. New "Verification" sub-tab (#13) under Supply Chain showing all 18 cobalt facilities
2. Per-facility overlay chart: thermal FRP + NO2 ratio + rated capacity reference line
3. Per-facility verification scorecard: computed consistency score + one-line verdict
4. Scan-friendly grid layout for rapid analyst triage across all 18 facilities

## Non-Goals

- Country-level or company-level aggregation (facility-level only)
- Automated alerting on discrepancies (analysts interpret the data)
- New API endpoints (all data already available from `/globe/minerals/Cobalt`)

## Data Sources (All Existing)

Each facility in the `/globe/minerals/Cobalt` API response already contains:

| Signal | Field | Cadence | Source |
|--------|-------|---------|--------|
| Thermal activity | `facility.thermal.history[]` | 6hr snapshots | FIRMS VIIRS |
| NO2 emissions | `facility.no2.history[]` | Daily snapshots | Sentinel-5P TROPOMI |
| Rated capacity | `facility.production_t` (mines) or `facility.capacity_t` (refineries) | Annual | USGS MCS / Company IR |
| Figure provenance | `facility.figure_type` + `facility.figure_source` + `facility.figure_year` | — | Dossier metadata |
| Operational verdict | `facility.operational_verdict` | Live | Combined thermal+NO2 |
| Owner | `facility.owner` | Static | Dossier |
| Country | `facility.country` | Static | Dossier |

No new API endpoints or backend changes needed. The sub-tab fetches `/globe/minerals/Cobalt` (same call the 3D Supply Map already makes) and renders verification cards client-side.

## Verification Score Algorithm

For each facility, compute a consistency score (0-100%) based on how well satellite signals match reported capacity:

```
Inputs:
  thermal_active_days  = count of days with ACTIVE status in last 30 days
  no2_emitting_days    = count of days with EMITTING status in last 30 days  
  total_days           = 30
  capacity_status      = "operating" | "paused" | "unknown"
    - "operating" if production_t > 0 and no pause note
    - "paused" if note contains "paused" or "suspended"
    - "unknown" otherwise

Score computation:
  satellite_activity_pct = max(thermal_active_days, no2_emitting_days) / total_days

  If capacity_status == "operating":
    // Expect high satellite activity
    score = satellite_activity_pct * 100
    // Clamp: if both signals agree on active, boost confidence
    if thermal_active_days > 0 AND no2_emitting_days > 0:
      score = min(100, score + 10)
  
  If capacity_status == "paused":
    // Expect low satellite activity
    score = (1 - satellite_activity_pct) * 100
    // If satellite shows activity during claimed pause, score drops
  
  If capacity_status == "unknown":
    score = 50  // neutral, no expectation to compare against

Verdict (derived from score):
  >= 80  → "CONSISTENT"     (green)   — satellite matches claims
  50-79  → "INCONCLUSIVE"   (ochre)   — partial data or mixed signals  
  < 50   → "DISCREPANCY"    (red)     — satellite contradicts claims
```

### Special Cases

- **Moa JV (Cuba):** Reported "paused Feb 2026" — if satellite shows NO2 or thermal, that's a discrepancy flag worth investigating
- **Raglan Mine:** Arctic location, 4-month shipping window — seasonal activity pattern is expected, not a discrepancy
- **New facilities (Kisanfu Phase 2):** Ramp-up period means partial activity is expected — use capacity utilization estimate if available

## UI Design

### Sub-Tab Registration

New entry in the PSI sub-tab bar (position 13, after "Analyst Feedback"):

```
Tab ID: psi-verification
Label: "Verification" (EN) / "Verification" (FR)
```

Add to `PSI_EN_TABS` and `PSI_FR_TABS` translation maps.

### Layout

The sub-tab renders as a **card grid** — 3 columns on desktop (1200px+), 2 on tablet, 1 on mobile.

Each card represents one facility:

```
┌──────────────────────────────────────────┐
│ TENKE FUNGURUME (TFM)                    │
│ CMOC Group (China) · DRC                 │
│ ┌──────────────────────────────────────┐ │
│ │          OVERLAY CHART (30d)         │ │
│ │  [red bars: thermal FRP]             │ │
│ │  [purple bars: NO2 ratio]            │ │
│ │  [------- capacity ref line -------] │ │
│ └──────────────────────────────────────┘ │
│ Rated: 32,000 t/yr (USGS MCS 2025)      │
│                                          │
│ ┌──────────────────────────────────────┐ │
│ │ 87% CONSISTENT          [green bar] │ │
│ │ Thermal: 24/30 days ACTIVE          │ │
│ │ NO2: 28/30 days EMITTING            │ │
│ │ Satellite activity aligns with      │ │
│ │ reported operating status.           │ │
│ └──────────────────────────────────────┘ │
└──────────────────────────────────────────┘
```

### Overlay Chart (Chart.js)

Each card contains a small Chart.js chart (~260x120px) with:

- **X axis:** dates (last 30 days)
- **Left Y axis:** FRP (MW) — thermal intensity
- **Right Y axis:** NO2 ratio (x background)
- **Red bars:** daily thermal FRP (aggregated from flyby data)
- **Purple bars:** daily NO2 ratio
- **Dashed horizontal line:** normalized "expected activity" reference based on capacity
  - For a 32kt/yr mine operating at full capacity, draw the line at the 30-day average to show the baseline
  - Label: "Rated: 32kt/yr"
- **Chart type:** mixed bar chart (grouped red + purple bars per day)

If history data is empty (no satellite key configured), show a placeholder: "Satellite data unavailable — configure NASA_FIRMS_MAP_KEY and SENTINEL_CLIENT_ID"

### Scorecard Section

Below each chart, a compact scorecard:

- **Score bar:** horizontal progress bar (0-100%) colored by verdict (green/ochre/red)
- **Score label:** "87% CONSISTENT" or "32% DISCREPANCY" 
- **Detail lines** (monospace, 10px):
  - "Thermal: X/30 days ACTIVE"
  - "NO2: X/30 days EMITTING"
- **One-line verdict:** human-readable interpretation
  - CONSISTENT: "Satellite activity aligns with reported operating status."
  - INCONCLUSIVE: "Partial satellite coverage — insufficient data for verification."
  - DISCREPANCY: "WARNING: Satellite shows [activity/inactivity] but facility reports [operating/paused]."

### Sort/Filter Controls

Above the card grid:

- **Sort by:** Score (ascending — worst first for triage), Name, Country, Capacity
- **Filter:** All / Discrepancy only / Consistent only
- Default sort: Score ascending (discrepancies bubble to top)

### Color Scheme

- Thermal: existing red palette (`#ff4444`, `#cc0000`)
- NO2: existing purple palette (`#a050dc`, `#c878ff`)  
- Consistent: sage green (`#6b9080`)
- Inconclusive: ochre (`#a89060`)
- Discrepancy: DND red (`#D80621`)
- Capacity reference line: white dashed (`rgba(255,255,255,0.3)`)

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/static/index.html` | MODIFY | Add sub-tab button, panel div, rendering function, chart logic, scorecard computation |
| `CLAUDE.md` | MODIFY | Add Verification sub-tab to feature list, update sub-tab count from 12 to 13 |

No backend changes. No new Python files. No new tests (frontend-only, data already tested via NO2 and FIRMS test suites).

## Dependencies

- Chart.js (already loaded via CDN)
- `/globe/minerals/Cobalt` API (already exists, already returns thermal + NO2 + capacity data)
- Existing PSI sub-tab system (`switchPsiTab()`, `psi-nav-box`)
