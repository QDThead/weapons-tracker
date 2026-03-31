# Scenario Sandbox Rework — Design Spec

**Date:** 2026-03-31
**Status:** Approved
**Scope:** Full rewrite of Supply Chain Scenario Sandbox to meet DMPP 11 RFI requirements (Q1, Q12, Q13)

---

## Problem

The current Scenario Sandbox has two disconnected modes: a generic 5-scenario form (`POST /psi/scenario`) and a Cobalt-specific sufficiency slider. Neither supports multi-variable scenarios, cascade visualization, side-by-side comparison, dollar-value impact estimates, Likelihood × Impact scoring, scenario history, COA comparison, or export — all promised in the RFI (Q12, Q13).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Unified vs split modes | Unified mineral-first | Supply Chain tab is organized around minerals; two modes creates confusion |
| Multi-variable approach | Preset combos + custom layer stacking | Quick access for common scenarios, full flexibility for analysts |
| Cascade visualization | Sankey / Impact Waterfall | Shows volume proportionally; matches "Rocks to Rockets" RFI language |
| Scenario history | Up to 4 saved runs per session | Good balance of flexibility vs UI complexity |
| COA comparison | Inline summary + dedicated bottom drawer | Quick view inline, deep dive available |
| Export formats | PDF + CSV + JSON | Leadership (PDF), analysts (CSV), system integration (JSON) |
| Implementation approach | Full rewrite | Current code is small (~160 JS + ~300 Python); RFI requirements are fundamentally different from existing |

---

## Layout: Three-Zone Design

```
┌──────────────┬─────────────────────────────────┬───────────────┐
│              │                                 │               │
│  SCENARIO    │     RESULTS + CASCADE           │   HISTORY     │
│  BUILDER     │                                 │   PANEL       │
│  (280px)     │     (flexible)                  │   (240px)     │
│              │                                 │               │
│  - Presets   │  - 4 Impact summary cards       │  - Up to 4    │
│  - Layers    │  - Sankey cascade (4-tier)      │    saved runs │
│  - Params    │  - Inline COA grid              │  - Checkboxes │
│  - Run btn   │  - "Compare All COAs" link      │  - Compare    │
│  - Reset     │                                 │  - Export     │
│  - Export    │                                 │    PDF/CSV/   │
│              │                                 │    JSON       │
└──────────────┴─────────────────────────────────┴───────────────┘
```

Grid: `grid-template-columns: 280px 1fr 240px`

---

## Zone 1: Scenario Builder (Left Panel)

### Quick Presets

5 named compound scenarios as clickable chips. Selecting one populates the disruption layers automatically.

| Preset | Layers |
|--------|--------|
| Indo-Pacific Conflict | Sanctions: China + Route: Strait of Malacca + Demand: +50% |
| Arctic Escalation | Sanctions: Russia + Route: Northern Sea Route + Demand: +30% |
| Global Recession | Demand: -20% + Material shortage: all minerals -15% |
| DRC Collapse | Material shortage: Cobalt -73% (DRC mining loss) |
| Suez Closure | Route: Suez Canal 180 days |

Presets can be modified after loading (edit any layer, add/remove layers).

### Disruption Layers

Stackable layers, each represented as a collapsible card with a colored left border and an "x" to remove. Layer types:

| Layer Type | Parameters |
|------------|-----------|
| `sanctions_expansion` | Country (dropdown from mineral's source countries) |
| `material_shortage` | Reduction % (slider, 10-100%) |
| `route_disruption` | Chokepoint (dropdown from mineral's shipping routes), Duration days (slider) |
| `supplier_failure` | Entity (dropdown from mineral's mines/refineries), Failure type (insolvency/nationalization/force majeure) |
| `demand_surge` | Region (NATO/Global/Canada), Increase % (slider) |

"+ Add Disruption Layer" button adds a new layer with type dropdown.

### Global Parameters

- **Demand surge %** — slider, -50% to +200%, default 0%
- **Time horizon** — slider, 3-24 months, default 12 months

### Actions

- **Run Scenario** — primary button (cyan), calls `POST /psi/scenario/v2`
- **Reset** — clears all layers and results
- **Export** — dropdown with PDF/CSV/JSON (exports current scenario or all saved)

---

## Zone 2: Results + Cascade (Center Panel)

### Impact Summary Cards

4 stat cards in a row:

| Card | Value | Derivation |
|------|-------|-----------|
| Value at Risk | Dollar amount (USD) | Sum of affected platform program values + material cost impact |
| Platforms Affected | Count | Platforms with supply ratio < 0.9 after disruption |
| Risk Score | 0-100 + rating | Composite: (likelihood × 0.4) + (supply_reduction × 0.3) + (platform_impact × 0.3), normalized to 0-100 |
| Likelihood | 0.0-1.0 | Based on layer types: sanctions (0.6), route disruption (0.5 × duration/365), material shortage (0.7), supplier failure (0.4), demand surge (0.8) — multiplicative across layers |

Risk rating thresholds: 0-39 LOW (green), 40-69 HIGH (amber), 70-100 CRITICAL (red).

### Sankey Cascade Visualization

4-tier "Rocks to Rockets" flow:

```
MINING → PROCESSING → ALLOYS → PLATFORMS
```

Each tier is a vertical column of blocks. Block height is proportional to that node's share of total volume. Colors:
- Red (#ef4444): disrupted (capacity loss > 50%)
- Amber (#f59e0b): degraded (capacity loss 20-50%)
- Green (#10b981): unaffected

Below the Sankey, a summary line:
```
Mining: -73% capacity → Refining: -68% throughput → Alloys: -45% output → Platforms: 7 at risk
```

Built with HTML/CSS (no D3 dependency needed — the tiers are fixed at 4 and node counts are small enough for CSS flex layout). If node count exceeds ~15 per tier in future minerals, can upgrade to D3/Canvas.

### Inline COA Grid

2-column grid of COA cards below the Sankey. Each card shows:
- Priority badge (CRITICAL red / HIGH amber / MEDIUM cyan)
- Action description (one line)
- Cost estimate + Risk reduction points

"Compare All COAs →" link at bottom opens the COA comparison drawer.

---

## Zone 3: History Panel (Right Panel)

### Saved Runs

Up to 4 scenario run cards. Each card shows:
- Scenario name (preset name or "Custom")
- Layer count
- Risk score
- Value at Risk (large number)
- Checkbox for comparison selection

Active/current run highlighted with cyan border. Empty slots shown as dashed outline.

### Compare Button

"Compare Selected (N)" — enabled when 2+ runs are checked. Opens the comparison view replacing the center panel.

### Export Buttons

Row of 3 buttons: PDF | CSV | JSON. Exports all selected scenarios (or current if none selected).

---

## Comparison View

Replaces the center panel when 2+ scenarios are selected for comparison. Shows:

### Side-by-Side Metrics Table

Columns: one per selected scenario. Rows:
- Value at Risk
- Platforms Affected
- Risk Score (with color-coded rating)
- Likelihood
- Supply Reduction %
- Lead Time Impact (days)

Cells highlighted: worst value in red, best in green.

### Mini Sankey Per Scenario

Each column gets a compact Sankey (half-height) showing that scenario's cascade.

### Back Button

"← Back to Builder" returns to the normal 3-zone view.

---

## COA Comparison Drawer

Bottom slide-up panel (40% viewport height, `max-height: 400px`). Triggered by "Compare All COAs" link.

### Sortable Table

Columns:
- COA ID
- Action
- Triggered By (which scenarios)
- Priority (sortable: critical > high > medium)
- Cost (sortable)
- Risk Reduction (points, sortable)
- Timeline (months, sortable)
- Platforms Protected

Duplicate COAs across scenarios are merged — "Triggered By" shows all scenario names.

Click column headers to sort. Close button (x) at top right.

---

## Backend: New Scenario Engine

### New File: `src/analysis/scenario_engine.py`

New `ScenarioEngine` class that replaces the 5 `_scenario_*` methods in `supply_chain.py`.

#### `POST /psi/scenario/v2` Request

```python
class ScenarioLayer(BaseModel):
    type: str  # sanctions_expansion | material_shortage | route_disruption | supplier_failure | demand_surge
    params: dict

class ScenarioRequest(BaseModel):
    mineral: str
    layers: list[ScenarioLayer]
    demand_surge_pct: float = 0
    time_horizon_months: int = 12
```

#### `POST /psi/scenario/v2` Response

```python
class ScenarioResponse(BaseModel):
    scenario_id: str
    mineral: str
    layers: list[ScenarioLayer]
    impact: ImpactSummary       # value_at_risk_usd, platforms_affected, risk_score, risk_rating, likelihood, supply_reduction_pct, lead_time_increase_days
    cascade: CascadeData        # tiers (list of tier objects with nodes), flows (list of from/to/volume/status)
    coa: list[COAEntry]         # id, action, priority, cost_usd, risk_reduction_pts, timeline_months, affected_platforms
    sufficiency: SufficiencyData  # supply_t, demand_t, ratio, verdict
```

#### Computation Pipeline

1. **Load mineral data** — from `mineral_supply_chains.py` (mines, refineries, alloys, platforms, shipping routes)
2. **Apply layers sequentially** — each layer modifies a working copy of the supply chain state:
   - `sanctions_expansion`: Zero out capacity for all nodes in the sanctioned country
   - `material_shortage`: Reduce mining capacity by specified %
   - `route_disruption`: Add delay and loss % to affected shipping routes
   - `supplier_failure`: Zero out specific entity capacity
   - `demand_surge`: Multiply demand by (1 + surge_pct/100)
3. **Propagate cascade** — walk the BOM top-down: mining capacity → refining throughput (limited by input) → alloy output (limited by refined input) → platform supply ratio
4. **Compute impact metrics** — aggregate across all tiers
5. **Generate COAs** — match active disruption types to playbook entries, compute risk reduction estimates
6. **Compute sufficiency** — supply_t / demand_t ratio after all layers applied

#### Dollar Value Derivation

- **Platform values**: estimated program costs from existing data (e.g., CF-18 fleet ~$500M/yr sustainment, F-35 ~$1.2B program value)
- **Material values**: current price × volume at risk (from cobalt_forecasting.py price data)
- **Route delay costs**: estimated delay cost per day × transit days added

### New Route in `psi_routes.py`

```python
@router.post("/scenario/v2")
async def run_scenario_v2(request: ScenarioRequestV2):
    engine = ScenarioEngine(mineral_data)
    return engine.run(request)
```

### PDF Export Endpoint

```python
@router.post("/scenario/export/pdf")
async def export_scenario_pdf(request: ScenarioExportRequest):
    # Accepts 1-4 scenario responses, generates fpdf2 PDF
```

### Migration

- Keep old `POST /psi/scenario` endpoint for backward compatibility
- Frontend switches entirely to `/psi/scenario/v2`
- Old endpoint can be deprecated and removed later

---

## Frontend Changes

### Files Modified

- `src/static/index.html` — replace `psi-scenarios` div contents, replace `updateScenarioFields()`, `runScenario()`, `renderScenarioResults()`, `renderMineralScenarios()`, `onScenarioMineralChange()` with new unified functions

### New JS Functions

| Function | Purpose |
|----------|---------|
| `initScenarioSandbox()` | Initialize 3-zone layout, load presets |
| `loadPreset(name)` | Populate layers from preset definition |
| `addDisruptionLayer()` | Add a new layer card to the builder |
| `removeLayer(index)` | Remove a layer card |
| `runScenarioV2()` | Collect layers + params, POST to `/psi/scenario/v2`, render results |
| `renderImpactCards(impact)` | Render the 4 summary stat cards |
| `renderSankeyCascade(cascade)` | Render the 4-tier Sankey waterfall |
| `renderInlineCOAs(coas)` | Render the 2-column COA grid |
| `saveScenarioRun(response)` | Save to history (max 4), update right panel |
| `renderHistoryPanel()` | Render saved runs with checkboxes |
| `openComparisonView(selectedRuns)` | Replace center with side-by-side comparison |
| `closeComparisonView()` | Return to normal 3-zone view |
| `openCOADrawer()` | Slide up COA comparison table |
| `closeCOADrawer()` | Slide down COA drawer |
| `exportScenario(format)` | Trigger PDF/CSV/JSON download |
| `sortCOATable(column)` | Sort COA drawer by column |

### Removed JS Functions

- `updateScenarioFields()` — replaced by layer-based builder
- `runScenario()` — replaced by `runScenarioV2()`
- `renderScenarioResults()` — replaced by `renderImpactCards()` + `renderSankeyCascade()` + `renderInlineCOAs()`
- `renderMineralScenarios()` — merged into unified view
- `onScenarioMineralChange()` — no longer needed (always mineral-first)
- `populateScenarioMineralDropdown()` — no longer needed (uses global mineral selector)
- `renderSufficiencyGauge()` — replaced by sufficiency data in impact cards
- `renderSufficiencySlider()` — replaced by layer-based approach
- `interpolateScenario()` — no longer needed

### CSS

No new classes needed — uses existing `.card`, `.stat-box`, `.stat-num`, `.btn-primary` plus inline styles consistent with the rest of index.html. COA drawer uses `position: fixed; bottom: 0` with transition.

---

## Preset Definitions

Stored as a JS object in `index.html`:

```javascript
const SCENARIO_PRESETS = {
  'Indo-Pacific Conflict': {
    layers: [
      {type: 'sanctions_expansion', params: {country: 'China'}},
      {type: 'route_disruption', params: {chokepoint: 'Strait of Malacca', duration_days: 180}},
    ],
    demand_surge_pct: 50,
  },
  'Arctic Escalation': {
    layers: [
      {type: 'sanctions_expansion', params: {country: 'Russia'}},
      {type: 'route_disruption', params: {chokepoint: 'Northern Sea Route', duration_days: 365}},
    ],
    demand_surge_pct: 30,
  },
  'Global Recession': {
    layers: [
      {type: 'material_shortage', params: {reduction_pct: 15}},
    ],
    demand_surge_pct: -20,
  },
  'DRC Collapse': {
    layers: [
      {type: 'material_shortage', params: {reduction_pct: 73}},
    ],
    demand_surge_pct: 0,
  },
  'Suez Closure': {
    layers: [
      {type: 'route_disruption', params: {chokepoint: 'Suez Canal', duration_days: 180}},
    ],
    demand_surge_pct: 0,
  },
};
```

---

## Test Plan

| Test | What It Validates |
|------|------------------|
| Single-layer sanctions scenario | Correct nodes zeroed, cascade propagates, COAs generated |
| Single-layer route disruption | Correct routes affected, delay calculated, lead time impact |
| Multi-layer compound scenario | Layers compose correctly (multiplicative supply reduction) |
| Preset loading | All 5 presets produce valid responses |
| Empty layers | Returns baseline (no disruption) |
| Unknown mineral | Returns appropriate error |
| Scenario history save/load | Up to 4 runs stored, 5th overwrites oldest |
| Comparison view | 2-4 scenarios rendered side-by-side with correct data |
| COA deduplication | Same COA from multiple scenarios merged in drawer |
| COA sorting | All columns sortable ascending/descending |
| PDF export | Valid PDF generated with scenario data |
| CSV export | Valid CSV with correct columns |
| JSON export | Raw response JSON matches API response |
| Likelihood calculation | Multiplicative across layers, clamped 0-1 |
| Dollar value calculation | Platform values + material costs + delay costs sum correctly |
| Risk score thresholds | 0-39 LOW, 40-69 HIGH, 70-100 CRITICAL |

---

## Out of Scope

- Real D3.js Sankey (CSS flex sufficient for current node counts; upgrade path noted)
- Persisting scenario history to database (session-only for now; noted as future work)
- Non-Cobalt minerals (shows "not yet available" message, same as other sub-tabs)
- Real-time collaborative scenarios (single-user for now)
