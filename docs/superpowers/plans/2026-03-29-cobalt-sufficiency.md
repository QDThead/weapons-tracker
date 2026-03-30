# Cobalt Demand vs Supply Sufficiency UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive sufficiency analysis row to the Cobalt globe detail panel — radial gauge, platform dependency cards with direct/indirect OEM chains, continuous scenario slider, and on-demand COA panel.

**Architecture:** All sufficiency data is static research baked into the Cobalt mineral dict in `mineral_supply_chains.py`. The existing `/globe/minerals/Cobalt` API endpoint returns it automatically — no new endpoints needed. All UI rendering and interaction logic lives in `index.html` as JavaScript functions appended to the existing `renderMineralDetail()` flow.

**Tech Stack:** Python (data dict), HTML/CSS/JS (rendering), Chart.js not used (custom CSS gauge + HTML cards), pytest (data integrity tests)

**Spec:** `docs/superpowers/specs/2026-03-29-cobalt-sufficiency-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/analysis/mineral_supply_chains.py` | Modify (insert at line 1005) | Add `sufficiency` key to Cobalt dict with demand, scenarios, COA, totals |
| `src/static/index.html` (CSS) | Modify (insert before line 901) | Add sufficiency row styles, gauge, cards, slider, COA panel |
| `src/static/index.html` (HTML) | Modify (insert after line 1917) | Add sufficiency row container divs to globe detail panel |
| `src/static/index.html` (JS) | Modify (insert after line 6823) | Add `renderSufficiency(m)` function and call it from `renderMineralDetail()` |
| `tests/test_globe.py` | Modify (append after line 147) | Add `TestCobaltSufficiency` class validating data structure |

---

### Task 1: Add Sufficiency Data to Cobalt Dict

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py:1005` (insert before `"source"` line)
- Test: `tests/test_globe.py` (append new test class)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_globe.py` after line 147:

```python


class TestCobaltSufficiency:
    """Verify Cobalt sufficiency data structure integrity."""

    def test_cobalt_has_sufficiency_key(self):
        cobalt = get_mineral_by_name("Cobalt")
        assert cobalt is not None
        assert "sufficiency" in cobalt, "Cobalt missing 'sufficiency' key"

    def test_sufficiency_has_required_sections(self):
        suf = get_mineral_by_name("Cobalt")["sufficiency"]
        assert "demand" in suf
        assert "scenarios" in suf
        assert "coa" in suf
        assert "totals" in suf

    def test_demand_entries_have_required_fields(self):
        demand = get_mineral_by_name("Cobalt")["sufficiency"]["demand"]
        assert len(demand) == 16, f"Expected 16 demand entries, got {len(demand)}"
        for d in demand:
            assert "platform" in d, f"Demand entry missing 'platform'"
            assert "kg_yr" in d, f"{d.get('platform','?')} missing 'kg_yr'"
            assert "type" in d, f"{d.get('platform','?')} missing 'type'"
            assert d["type"] in ("direct", "indirect"), (
                f"{d['platform']} type must be 'direct' or 'indirect', got '{d['type']}'"
            )
            assert "threshold_ratio" in d, f"{d['platform']} missing 'threshold_ratio'"
            assert "fleet_note" in d, f"{d['platform']} missing 'fleet_note'"
            assert "risk_note" in d, f"{d['platform']} missing 'risk_note'"
            assert isinstance(d["kg_yr"], (int, float)), (
                f"{d['platform']} kg_yr must be numeric"
            )

    def test_indirect_entries_have_oem_fields(self):
        demand = get_mineral_by_name("Cobalt")["sufficiency"]["demand"]
        indirect = [d for d in demand if d["type"] == "indirect"]
        assert len(indirect) >= 9, f"Expected at least 9 indirect entries, got {len(indirect)}"
        for d in indirect:
            assert "oem" in d, f"{d['platform']} indirect entry missing 'oem'"
            assert "oem_country" in d, f"{d['platform']} indirect entry missing 'oem_country'"
            assert "engine" in d, f"{d['platform']} indirect entry missing 'engine'"

    def test_scenarios_structure(self):
        scenarios = get_mineral_by_name("Cobalt")["sufficiency"]["scenarios"]
        assert len(scenarios) == 5, f"Expected 5 scenarios, got {len(scenarios)}"
        for s in scenarios:
            assert "name" in s
            assert "position" in s
            assert "supply_t" in s
            assert "demand_t" in s
            assert "ratio" in s
            assert "verdict" in s
            assert 0 <= s["position"] <= 100, (
                f"Scenario '{s['name']}' position {s['position']} out of 0-100 range"
            )

    def test_scenarios_sorted_by_position(self):
        scenarios = get_mineral_by_name("Cobalt")["sufficiency"]["scenarios"]
        positions = [s["position"] for s in scenarios]
        assert positions == sorted(positions), "Scenarios must be sorted by position"

    def test_coa_entries_structure(self):
        coas = get_mineral_by_name("Cobalt")["sufficiency"]["coa"]
        assert len(coas) == 6, f"Expected 6 COA entries, got {len(coas)}"
        for c in coas:
            assert "id" in c
            assert "action" in c
            assert "cost" in c
            assert "impact" in c
            assert "relevant_scenarios" in c
            assert isinstance(c["relevant_scenarios"], list)

    def test_totals_structure(self):
        totals = get_mineral_by_name("Cobalt")["sufficiency"]["totals"]
        assert totals["steady_state_kg"] == 298
        assert totals["f35_ramp_kg"] == 740
        assert totals["direct_kg"] == 138
        assert totals["indirect_kg"] == 160
        assert totals["direct_kg"] + totals["indirect_kg"] == totals["steady_state_kg"]

    def test_demand_kg_sums_match_totals(self):
        suf = get_mineral_by_name("Cobalt")["sufficiency"]
        demand = suf["demand"]
        total_kg = sum(d["kg_yr"] for d in demand)
        direct_kg = sum(d["kg_yr"] for d in demand if d["type"] == "direct")
        indirect_kg = sum(d["kg_yr"] for d in demand if d["type"] == "indirect")
        assert abs(total_kg - suf["totals"]["steady_state_kg"]) <= 1, (
            f"Demand sum {total_kg} != steady_state_kg {suf['totals']['steady_state_kg']}"
        )
        assert abs(direct_kg - suf["totals"]["direct_kg"]) <= 1, (
            f"Direct sum {direct_kg} != direct_kg {suf['totals']['direct_kg']}"
        )
        assert abs(indirect_kg - suf["totals"]["indirect_kg"]) <= 1, (
            f"Indirect sum {indirect_kg} != indirect_kg {suf['totals']['indirect_kg']}"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_globe.py::TestCobaltSufficiency -v`
Expected: FAIL with `KeyError: 'sufficiency'` or `AssertionError: Cobalt missing 'sufficiency' key`

- [ ] **Step 3: Add sufficiency data to Cobalt dict**

In `src/analysis/mineral_supply_chains.py`, replace the line:

```python
        "source": "USGS MCS 2025",
```

(at line 1005, inside the Cobalt dict — the one that comes after the `shipping_routes` array ending at line 1004)

with:

```python
        "sufficiency": {
            "demand": [
                # --- INDIRECT: Through Foreign OEM Supply Chain ---
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
                    "fleet_note": "76 aircraft \u2014 2x GE F404 engines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "Engine overhaul parts sourced through US OEM",
                },
                {
                    "platform": "F-35A Lightning II",
                    "kg_yr": 29,
                    "type": "indirect",
                    "oem": "Pratt & Whitney",
                    "oem_country": "US",
                    "alloy": "CMSX-4",
                    "alloy_co_pct": 9.5,
                    "engine": "P&W F135",
                    "fleet_size": 88,
                    "fleet_note": "88 on order (2026\u20132032)",
                    "threshold_ratio": 0.7,
                    "risk_note": "China controls 80% of cobalt refining in this chain",
                },
                {
                    "platform": "CC-177 Globemaster III",
                    "kg_yr": 15,
                    "type": "indirect",
                    "oem": "Pratt & Whitney",
                    "oem_country": "US",
                    "alloy": "Waspaloy",
                    "alloy_co_pct": 13.0,
                    "engine": "P&W F117",
                    "fleet_size": 5,
                    "fleet_note": "5 aircraft \u2014 4x P&W F117 engines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "Strategic airlift \u2014 engine overhaul parts via US OEM",
                },
                {
                    "platform": "Halifax-class Frigates",
                    "kg_yr": 15,
                    "type": "indirect",
                    "oem": "GE Marine",
                    "oem_country": "US",
                    "alloy": "Waspaloy",
                    "alloy_co_pct": 13.0,
                    "engine": "GE LM2500",
                    "fleet_size": 12,
                    "fleet_note": "12 ships \u2014 2x GE LM2500 gas turbines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "Naval gas turbine overhaul via US OEM",
                },
                {
                    "platform": "CH-148 Cyclone",
                    "kg_yr": 12,
                    "type": "indirect",
                    "oem": "GE Aviation",
                    "oem_country": "US",
                    "alloy": "Waspaloy",
                    "alloy_co_pct": 13.0,
                    "engine": "GE CT7",
                    "fleet_size": 28,
                    "fleet_note": "28 helicopters \u2014 2x GE CT7 engines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "Engine overhaul parts sourced through US OEM",
                },
                {
                    "platform": "CH-149 Cormorant",
                    "kg_yr": 12,
                    "type": "indirect",
                    "oem": "GE Aviation",
                    "oem_country": "US",
                    "alloy": "Waspaloy",
                    "alloy_co_pct": 13.0,
                    "engine": "GE CT7",
                    "fleet_size": 14,
                    "fleet_note": "14 helicopters \u2014 3x GE CT7 engines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "SAR helicopter \u2014 engine overhaul via US OEM",
                },
                {
                    "platform": "CH-147F Chinook",
                    "kg_yr": 10,
                    "type": "indirect",
                    "oem": "Honeywell",
                    "oem_country": "US",
                    "alloy": "Waspaloy",
                    "alloy_co_pct": 13.0,
                    "engine": "Honeywell T55",
                    "fleet_size": 15,
                    "fleet_note": "15 helicopters \u2014 2x Honeywell T55 engines each",
                    "threshold_ratio": 0.7,
                    "risk_note": "Heavy-lift helicopter \u2014 engine parts via US OEM",
                },
                {
                    "platform": "LAV 6.0",
                    "kg_yr": 5.4,
                    "type": "indirect",
                    "oem": "Caterpillar",
                    "oem_country": "US",
                    "alloy": "Stellite",
                    "alloy_co_pct": 60.0,
                    "engine": "Caterpillar C7",
                    "fleet_size": 550,
                    "fleet_note": "550 vehicles \u2014 Caterpillar C7 diesel",
                    "threshold_ratio": 0.5,
                    "risk_note": "Diesel engine \u2014 lower cobalt intensity than gas turbines",
                },
                {
                    "platform": "Leopard 2A6M",
                    "kg_yr": 3.5,
                    "type": "indirect",
                    "oem": "MTU",
                    "oem_country": "Germany",
                    "alloy": "Stellite",
                    "alloy_co_pct": 60.0,
                    "engine": "MTU MB 873",
                    "fleet_size": 80,
                    "fleet_note": "80 tanks \u2014 MTU MB 873 engine",
                    "threshold_ratio": 0.5,
                    "risk_note": "Tank engine \u2014 German OEM, NATO-allied supply chain",
                },
                {
                    "platform": "Victoria-class SSK",
                    "kg_yr": 2,
                    "type": "indirect",
                    "oem": "UK MoD",
                    "oem_country": "UK",
                    "alloy": "n/a",
                    "alloy_co_pct": 0,
                    "engine": "Diesel-electric",
                    "fleet_size": 4,
                    "fleet_note": "4 submarines \u2014 diesel-electric propulsion",
                    "threshold_ratio": 0.4,
                    "risk_note": "Submarine \u2014 minimal cobalt, UK-allied supply",
                },
                # --- DIRECT: Canadian Domestic Consumption ---
                {
                    "platform": "BB-2590 Soldier Batteries",
                    "kg_yr": 50,
                    "type": "direct",
                    "use": "Li-ion NMC/LCO",
                    "qty_yr": 800,
                    "fleet_note": "~800 batteries/yr \u2014 Li-ion NMC/LCO chemistry",
                    "threshold_ratio": 0.3,
                    "risk_note": "Domestic procurement \u2014 shorter supply chain",
                },
                {
                    "platform": "Spare Parts Buffer (15%)",
                    "kg_yr": 38,
                    "type": "direct",
                    "use": "Depot stock",
                    "fleet_note": "15% safety buffer across all cobalt-bearing parts",
                    "threshold_ratio": 0.2,
                    "risk_note": "Buffer stock \u2014 already held in Canadian depots",
                },
                {
                    "platform": "WC-Co Cutting Tools",
                    "kg_yr": 20,
                    "type": "direct",
                    "use": "Depot maintenance",
                    "fleet_note": "Tungsten-carbide cobalt tooling for MRO depots",
                    "threshold_ratio": 0.3,
                    "risk_note": "Domestic depot maintenance \u2014 substitutes available",
                },
                {
                    "platform": "Guided Munitions (SmCo)",
                    "kg_yr": 15,
                    "type": "direct",
                    "use": "SmCo permanent magnets",
                    "fleet_note": "AIM-9/AIM-120 fin actuators \u2014 SmCo magnets (52% Co)",
                    "threshold_ratio": 0.4,
                    "risk_note": "Munitions procurement \u2014 US-manufactured but Canadian stock",
                },
                {
                    "platform": "Magnetic Components",
                    "kg_yr": 10,
                    "type": "direct",
                    "use": "Sensors, generators",
                    "fleet_note": "Sensors, generators, and magnetic assemblies",
                    "threshold_ratio": 0.3,
                    "risk_note": "Domestic procurement \u2014 shorter supply chain",
                },
                {
                    "platform": "Stellite Wear Parts",
                    "kg_yr": 5,
                    "type": "direct",
                    "use": "Valves, pumps",
                    "fleet_note": "Non-engine Stellite wear parts \u2014 valves, pumps, seats",
                    "threshold_ratio": 0.3,
                    "risk_note": "Depot maintenance \u2014 long shelf life, substitutes exist",
                },
            ],
            "scenarios": [
                {
                    "name": "Normal operations",
                    "position": 0,
                    "supply_t": 237000,
                    "demand_t": 237000,
                    "ratio": 1.0,
                    "verdict": "Balanced",
                },
                {
                    "name": "China export ban",
                    "position": 25,
                    "supply_t": 31500,
                    "demand_t": 54000,
                    "ratio": 0.73,
                    "verdict": "27% deficit",
                },
                {
                    "name": "China + DRC collapse",
                    "position": 50,
                    "supply_t": 12500,
                    "demand_t": 54000,
                    "ratio": 0.23,
                    "verdict": "77% deficit \u2014 CRITICAL",
                },
                {
                    "name": "Defence priority allocation",
                    "position": 65,
                    "supply_t": 31500,
                    "demand_t": 8000,
                    "ratio": 4.9,
                    "verdict": "Sufficient if governments intervene",
                },
                {
                    "name": "Canada sovereign only",
                    "position": 100,
                    "supply_t": 2500,
                    "demand_t": 0.74,
                    "ratio": 3400,
                    "verdict": "Volume not the problem",
                },
            ],
            "coa": [
                {
                    "id": "COA-1",
                    "action": "Sovereign cobalt stockpile (500t refined metal)",
                    "cost": "~$15M",
                    "impact": "60 years CAF demand; bridges any disruption",
                    "relevant_scenarios": [25, 50],
                },
                {
                    "id": "COA-2",
                    "action": "Increase engine overhaul parts buffer to 24 months",
                    "cost": "~$100M",
                    "impact": "Eliminates grounding risk regardless of cause",
                    "relevant_scenarios": [25, 50, 65],
                },
                {
                    "id": "COA-3",
                    "action": "Restart Sherritt Fort Saskatchewan with non-Cuban feedstock",
                    "cost": "$50\u2013150M",
                    "impact": "6,300 t/yr sovereign refining capacity",
                    "relevant_scenarios": [25, 50],
                },
                {
                    "id": "COA-4",
                    "action": "Formalize allied cobalt allocation under DPSA with US DoD",
                    "cost": "$0",
                    "impact": "Guaranteed access to US superalloy components",
                    "relevant_scenarios": [25, 50, 65],
                },
                {
                    "id": "COA-5",
                    "action": "Superalloy scrap recycling at Canadian MRO depots",
                    "cost": "$5\u201310M",
                    "impact": "~200 kg/yr cobalt recovered",
                    "relevant_scenarios": [50, 65, 100],
                },
                {
                    "id": "COA-6",
                    "action": "Engine health monitoring to extend overhaul intervals 15\u201325%",
                    "cost": "~$20M",
                    "impact": "Reduces parts consumption + improves availability",
                    "relevant_scenarios": [25, 50, 65],
                },
            ],
            "totals": {
                "steady_state_kg": 298,
                "f35_ramp_kg": 740,
                "direct_kg": 138,
                "indirect_kg": 160,
            },
        },
        "source": "USGS MCS 2025",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_globe.py::TestCobaltSufficiency -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/mineral_supply_chains.py tests/test_globe.py
git commit -m "feat: add Cobalt sufficiency data (demand, scenarios, COA, totals)"
```

---

### Task 2: Add Sufficiency Row HTML Containers

**Files:**
- Modify: `src/static/index.html:1917` (insert new row after bottom row closing `</div>`)

- [ ] **Step 1: Add the sufficiency row containers**

In `src/static/index.html`, find this block (the end of the bottom row, around line 1917-1918):

```html
        </div>
      </div>
```

The first `</div>` closes the 3-column bottom row (Route/Risk/Canada). The second `</div>` closes the entire `globe-detail-panel`. Insert the sufficiency row HTML between them:

```html
        </div>

        <!-- Sufficiency Analysis Row (only shown for minerals with sufficiency data) -->
        <div id="globe-sufficiency-row" style="display:none; margin-top:10px;">
          <div class="card" style="padding:14px;">
            <h4 style="font-size:13px; margin:0 0 12px; color:var(--accent);">
              Demand &amp; Supply Sufficiency
              <span style="font-size:10px; color:var(--text-muted); font-weight:normal; margin-left:8px;">
                Canada&rsquo;s dependency on foreign OEM supply chains
              </span>
            </h4>
            <div style="display:grid; grid-template-columns:1fr 2fr 1fr; gap:14px; align-items:start;">
              <!-- Radial Gauge -->
              <div id="sufficiency-gauge" style="text-align:center;"></div>
              <!-- Platform Dependency Cards -->
              <div id="sufficiency-platforms" style="max-height:340px; overflow-y:auto;"></div>
              <!-- Scenario Slider -->
              <div id="sufficiency-slider"></div>
            </div>
          </div>
          <!-- COA Toggle -->
          <div style="text-align:center; margin-top:8px;">
            <button id="sufficiency-coa-toggle" onclick="toggleSufficiencyCOA()" style="
              background:var(--surface-glass); border:1px solid var(--border); border-radius:8px;
              color:var(--text-dim); padding:8px 20px; cursor:pointer; font-size:12px;
              font-family:var(--font-body); backdrop-filter:blur(16px);
              transition:border-color 0.3s, color 0.3s;
            ">&#x1F4CB; View Recommended Actions</button>
          </div>
          <!-- COA Panel (hidden by default) -->
          <div id="sufficiency-coa-panel" style="display:none; margin-top:8px;">
            <div class="card" style="padding:14px;">
              <h4 style="font-size:13px; margin:0 0 10px; color:var(--accent3);">Courses of Action</h4>
              <div id="sufficiency-coa-cards" style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px;"></div>
            </div>
          </div>
        </div>
      </div>
```

- [ ] **Step 2: Verify the page loads without errors**

Run: `python -m src.main` and open `http://localhost:8000`. Navigate to Supply Chain → 3D Supply Map. The new containers should be hidden (they only show when sufficiency data exists). Check browser console for no errors.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency row HTML containers to globe detail panel"
```

---

### Task 3: Add Sufficiency CSS Styles

**Files:**
- Modify: `src/static/index.html` (CSS section, insert before the `@media (max-width: 1200px)` block at line 901)

- [ ] **Step 1: Add the CSS styles**

In `src/static/index.html`, find this line in the CSS section:

```css
@media (max-width: 1200px) {
```

Insert the following styles immediately before it:

```css
/* Sufficiency Analysis */
.suf-gauge-ring {
  position: relative; width: 160px; height: 85px; margin: 0 auto;
}
.suf-gauge-bg {
  width: 160px; height: 80px; border-radius: 80px 80px 0 0; overflow: hidden;
  background: conic-gradient(from 180deg, #ef4444 0deg, #ef4444 60deg, #f59e0b 60deg, #f59e0b 108deg, #10b981 108deg, #10b981 180deg);
}
.suf-gauge-inner {
  position: absolute; top: 8px; left: 8px; width: 144px; height: 72px;
  border-radius: 72px 72px 0 0; background: var(--bg);
}
.suf-gauge-value {
  position: absolute; bottom: 0; left: 50%; transform: translateX(-50%);
  font-family: var(--font-mono); font-size: 1.6rem; font-weight: bold;
}
.suf-gauge-verdict {
  font-size: 11px; font-weight: 600; margin-top: 2px; text-align: center;
}
.suf-gauge-scenario {
  font-size: 10px; color: var(--text-muted); text-align: center; margin-top: 2px;
}
.suf-gauge-numbers {
  font-size: 9px; color: var(--text-muted); text-align: center; margin-top: 4px;
  font-family: var(--font-mono);
}
.suf-platform-card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 6px;
  padding: 10px; margin-bottom: 6px; border-left: 3px solid var(--border);
  transition: background 0.3s, border-color 0.3s;
}
.suf-platform-card.at-risk {
  border-left-color: #ef4444; background: rgba(239, 68, 68, 0.06);
}
.suf-platform-card .suf-badge-indirect {
  background: rgba(139, 92, 246, 0.15); color: #8b5cf6; font-size: 9px;
  padding: 2px 8px; border-radius: 10px; font-weight: 600;
}
.suf-platform-card .suf-badge-direct {
  background: rgba(0, 212, 255, 0.12); color: #00d4ff; font-size: 9px;
  padding: 2px 8px; border-radius: 10px; font-weight: 600;
}
.suf-chain {
  display: flex; align-items: center; gap: 3px; flex-wrap: wrap;
  margin-top: 6px; font-size: 9px;
}
.suf-pill { padding: 2px 6px; border-radius: 3px; white-space: nowrap; }
.suf-pill-mineral { background: rgba(0, 212, 255, 0.12); color: #00d4ff; }
.suf-pill-oem { background: rgba(139, 92, 246, 0.12); color: #a78bfa; }
.suf-pill-canada { background: rgba(16, 185, 129, 0.12); color: #10b981; }
.suf-chain-arrow { color: var(--text-muted); }
.suf-risk-note {
  font-size: 10px; margin-top: 5px;
}
.suf-risk-note.warning { color: #f59e0b; }
.suf-risk-note.ok { color: #10b981; }
.suf-risk-note.critical { color: #ef4444; }
.suf-slider-wrap {
  display: flex; flex-direction: column; align-items: center;
}
.suf-slider-label {
  font-size: 11px; font-weight: 600; color: var(--text); margin-bottom: 4px; text-align: center;
}
.suf-slider-sublabel {
  font-size: 9px; color: var(--text-muted); margin-bottom: 10px; text-align: center;
}
.suf-range-vertical {
  writing-mode: vertical-lr; direction: rtl;
  width: 28px; height: 260px; cursor: pointer;
  accent-color: var(--accent);
}
.suf-preset {
  font-size: 9px; color: var(--text-muted); cursor: pointer; padding: 3px 6px;
  border-radius: 4px; text-align: left; transition: color 0.2s;
}
.suf-preset:hover { color: var(--text); }
.suf-preset.active { color: var(--accent); font-weight: 600; }
.suf-coa-card {
  background: var(--surface-glass); backdrop-filter: blur(16px);
  border: 1px solid var(--border); border-radius: 8px; padding: 10px;
  transition: border-color 0.3s, box-shadow 0.3s;
}
.suf-coa-card.relevant {
  border-color: rgba(16, 185, 129, 0.4);
  box-shadow: 0 0 12px rgba(16, 185, 129, 0.1);
}
.suf-coa-id {
  font-size: 10px; font-weight: 700; color: var(--accent3); margin-bottom: 4px;
}
.suf-coa-action { font-size: 11px; color: var(--text); margin-bottom: 6px; }
.suf-coa-meta {
  display: flex; justify-content: space-between; font-size: 9px; color: var(--text-muted);
}
.suf-insight {
  background: rgba(139, 92, 246, 0.08); border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 6px; padding: 8px 10px; margin-top: 8px; font-size: 10px; color: #c4b5fd;
}
.suf-insight strong { color: #8b5cf6; }

```

Also add to the `@media (max-width: 1200px)` block:

Find:
```css
@media (max-width: 1200px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
```

Replace with:
```css
@media (max-width: 1200px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
  #globe-sufficiency-row .card > div[style*="grid-template-columns"] { grid-template-columns: 1fr; }
  #sufficiency-coa-cards { grid-template-columns: 1fr !important; }
```

- [ ] **Step 2: Verify styles don't break existing layout**

Run: `python -m src.main` and navigate through all 10 tabs. Verify no visual regressions.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency CSS styles (gauge, cards, slider, COA)"
```

---

### Task 4: Add Radial Gauge Renderer

**Files:**
- Modify: `src/static/index.html` (JS section, insert after the `renderMineralDetail` function closing brace at line 6824)

- [ ] **Step 1: Add the gauge rendering function**

In `src/static/index.html`, find the closing `}` of `renderMineralDetail` at line 6824. Insert after it:

```javascript

// ── Sufficiency Analysis ──────────────────────────────────────────
var currentSufficiencyMineral = null;
var currentScenarioPosition = 0;

function renderSufficiencyGauge(ratio, verdict, scenarioName, supplyT, demandT) {
  var gaugeColor = ratio >= 0.9 ? '#10b981' : ratio >= 0.5 ? '#f59e0b' : '#ef4444';
  var verdictClass = ratio >= 0.9 ? 'ok' : ratio >= 0.5 ? 'warning' : 'critical';
  var displayRatio = ratio >= 100 ? ratio.toFixed(0) + 'x' : ratio.toFixed(2) + 'x';
  // Needle angle: 0x = full left (0deg), 1.0x = full right (180deg), cap at 180
  var needleAngle = Math.min(Math.max(ratio / 1.5, 0), 1) * 180;

  var html = '<div class="suf-gauge-ring">'
    + '<div class="suf-gauge-bg"></div>'
    + '<div class="suf-gauge-inner"></div>'
    + '<div class="suf-gauge-value" style="color:' + gaugeColor + ';">' + displayRatio + '</div>'
    + '</div>'
    + '<div class="suf-gauge-verdict" style="color:' + gaugeColor + ';">' + esc(verdict) + '</div>'
    + '<div class="suf-gauge-scenario">' + esc(scenarioName) + '</div>'
    + '<div class="suf-gauge-numbers">Supply: ' + supplyT.toLocaleString() + ' t/yr | Demand: ' + demandT.toLocaleString() + ' t/yr</div>';

  document.getElementById('sufficiency-gauge').innerHTML = html;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency radial gauge renderer"
```

---

### Task 5: Add Platform Dependency Cards Renderer

**Files:**
- Modify: `src/static/index.html` (JS section, insert after the gauge function from Task 4)

- [ ] **Step 1: Add the platform cards rendering function**

Insert after the `renderSufficiencyGauge` function:

```javascript

function renderSufficiencyPlatforms(demand, mineralName, currentRatio) {
  // Sort: at-risk platforms first, then by kg_yr descending
  var sorted = demand.slice().sort(function(a, b) {
    var aRisk = currentRatio < a.threshold_ratio ? 1 : 0;
    var bRisk = currentRatio < b.threshold_ratio ? 1 : 0;
    if (aRisk !== bRisk) return bRisk - aRisk;
    return b.kg_yr - a.kg_yr;
  });

  var html = '';
  for (var i = 0; i < sorted.length; i++) {
    var d = sorted[i];
    var atRisk = currentRatio < d.threshold_ratio;
    var isIndirect = d.type === 'indirect';
    var cardClass = 'suf-platform-card' + (atRisk ? ' at-risk' : '');

    html += '<div class="' + cardClass + '">';
    // Header row
    html += '<div style="display:flex; justify-content:space-between; align-items:center;">';
    html += '<span style="color:var(--text); font-weight:bold; font-size:12px;">' + esc(d.platform) + '</span>';
    if (isIndirect) {
      html += '<span class="suf-badge-indirect">\uD83D\uDD17 INDIRECT</span>';
    } else {
      html += '<span class="suf-badge-direct">\uD83C\uDF41 DIRECT</span>';
    }
    html += '</div>';
    // Subtext
    html += '<div style="color:var(--text-muted); font-size:10px; margin-top:2px;">'
      + esc(d.fleet_note) + ' \u2014 ' + d.kg_yr + ' kg/yr</div>';
    // Dependency chain
    html += '<div class="suf-chain">';
    html += '<span class="suf-pill suf-pill-mineral">' + esc(mineralName) + '</span>';
    html += '<span class="suf-chain-arrow">\u2192</span>';
    if (isIndirect) {
      if (d.alloy && d.alloy !== 'n/a') {
        html += '<span class="suf-pill suf-pill-oem">' + esc(d.alloy) + ' (' + d.alloy_co_pct + '% Co)</span>';
        html += '<span class="suf-chain-arrow">\u2192</span>';
      }
      html += '<span class="suf-pill suf-pill-oem">' + esc(d.engine) + ' \u2014 ' + esc(d.oem) + ' (' + esc(d.oem_country) + ')</span>';
      html += '<span class="suf-chain-arrow">\u2192</span>';
      html += '<span class="suf-pill suf-pill-canada">\uD83C\uDF41 CAF</span>';
    } else {
      if (d.use) {
        html += '<span class="suf-pill suf-pill-mineral">' + esc(d.use) + '</span>';
        html += '<span class="suf-chain-arrow">\u2192</span>';
      }
      html += '<span class="suf-pill suf-pill-canada">\uD83C\uDF41 Canadian MRO</span>';
    }
    html += '</div>';
    // Risk note
    if (atRisk) {
      html += '<div class="suf-risk-note critical">\u26D4 GROUNDED \u2014 cobalt supply unavailable at this disruption level</div>';
    } else if (isIndirect) {
      html += '<div class="suf-risk-note warning">\u26A0 ' + esc(d.risk_note) + '</div>';
    } else {
      html += '<div class="suf-risk-note ok">\u2713 ' + esc(d.risk_note) + '</div>';
    }
    html += '</div>';
  }

  // Insight callout
  var totalIndirect = 0, totalDirect = 0;
  for (var j = 0; j < demand.length; j++) {
    if (demand[j].type === 'indirect') totalIndirect += demand[j].kg_yr;
    else totalDirect += demand[j].kg_yr;
  }
  var pctIndirect = Math.round(totalIndirect / (totalIndirect + totalDirect) * 100);
  html += '<div class="suf-insight">'
    + '<strong>INSIGHT:</strong> ' + pctIndirect + '% of Canada\u2019s cobalt demand flows through foreign OEMs. '
    + 'The vulnerability is supply chain architecture \u2014 not volume.'
    + '</div>';

  document.getElementById('sufficiency-platforms').innerHTML = html;
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency platform dependency cards renderer"
```

---

### Task 6: Add Scenario Slider with Interpolation

**Files:**
- Modify: `src/static/index.html` (JS section, insert after platform cards function from Task 5)

- [ ] **Step 1: Add the slider rendering and interpolation functions**

Insert after the `renderSufficiencyPlatforms` function:

```javascript

function interpolateScenario(scenarios, position) {
  // Find bracketing scenarios
  if (position <= scenarios[0].position) return { supply_t: scenarios[0].supply_t, demand_t: scenarios[0].demand_t, ratio: scenarios[0].ratio, verdict: scenarios[0].verdict, name: scenarios[0].name };
  if (position >= scenarios[scenarios.length - 1].position) {
    var last = scenarios[scenarios.length - 1];
    return { supply_t: last.supply_t, demand_t: last.demand_t, ratio: last.ratio, verdict: last.verdict, name: last.name };
  }
  var lower = scenarios[0], upper = scenarios[1];
  for (var i = 0; i < scenarios.length - 1; i++) {
    if (position >= scenarios[i].position && position <= scenarios[i + 1].position) {
      lower = scenarios[i];
      upper = scenarios[i + 1];
      break;
    }
  }
  var t = (position - lower.position) / (upper.position - lower.position);
  var supply = lower.supply_t + t * (upper.supply_t - lower.supply_t);
  var demand = lower.demand_t + t * (upper.demand_t - lower.demand_t);
  var ratio = demand > 0 ? supply / demand : 9999;
  // Use nearest preset name if within 3 units, otherwise interpolate label
  var nearestPreset = null;
  for (var k = 0; k < scenarios.length; k++) {
    if (Math.abs(position - scenarios[k].position) <= 3) { nearestPreset = scenarios[k]; break; }
  }
  var name = nearestPreset ? nearestPreset.name : Math.round(position) + '% disruption';
  var verdict = nearestPreset ? nearestPreset.verdict : (ratio >= 0.9 ? 'Sufficient' : ratio >= 0.5 ? 'Supply stress' : 'Critical deficit');
  return { supply_t: Math.round(supply), demand_t: Math.round(demand), ratio: ratio, verdict: verdict, name: name };
}

function renderSufficiencySlider(scenarios) {
  var html = '<div class="suf-slider-wrap">';
  html += '<div class="suf-slider-label">Disruption Scenario</div>';
  html += '<div class="suf-slider-sublabel">Drag to simulate supply chain disruption</div>';
  html += '<input type="range" min="0" max="100" value="' + currentScenarioPosition + '" '
    + 'class="suf-range-vertical" id="sufficiency-range" '
    + 'oninput="onSufficiencySliderChange(this.value)">';
  // Preset buttons
  html += '<div style="margin-top:10px; width:100%;">';
  for (var i = 0; i < scenarios.length; i++) {
    var s = scenarios[i];
    var activeClass = Math.abs(currentScenarioPosition - s.position) <= 3 ? ' active' : '';
    html += '<div class="suf-preset' + activeClass + '" onclick="snapSufficiencyPreset(' + s.position + ')">'
      + s.position + '% \u2014 ' + esc(s.name)
      + '</div>';
  }
  html += '</div></div>';
  document.getElementById('sufficiency-slider').innerHTML = html;
}

function onSufficiencySliderChange(value) {
  currentScenarioPosition = parseInt(value);
  if (!currentSufficiencyMineral || !currentSufficiencyMineral.sufficiency) return;
  var suf = currentSufficiencyMineral.sufficiency;
  var result = interpolateScenario(suf.scenarios, currentScenarioPosition);
  renderSufficiencyGauge(result.ratio, result.verdict, result.name, result.supply_t, result.demand_t);
  renderSufficiencyPlatforms(suf.demand, currentSufficiencyMineral.name, result.ratio);
  // Update preset highlights
  var presets = document.querySelectorAll('.suf-preset');
  for (var i = 0; i < presets.length; i++) {
    presets[i].classList.remove('active');
  }
  for (var j = 0; j < suf.scenarios.length; j++) {
    if (Math.abs(currentScenarioPosition - suf.scenarios[j].position) <= 3) {
      presets[j].classList.add('active');
      break;
    }
  }
  // Update COA relevance if panel is open
  updateCOARelevance(suf.coa, currentScenarioPosition);
}

function snapSufficiencyPreset(position) {
  currentScenarioPosition = position;
  var slider = document.getElementById('sufficiency-range');
  if (slider) slider.value = position;
  onSufficiencySliderChange(position);
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency scenario slider with interpolation"
```

---

### Task 7: Add COA Panel Toggle and Renderer

**Files:**
- Modify: `src/static/index.html` (JS section, insert after slider functions from Task 6)

- [ ] **Step 1: Add the COA rendering and toggle functions**

Insert after the `snapSufficiencyPreset` function:

```javascript

function renderSufficiencyCOA(coas, currentPosition) {
  var html = '';
  for (var i = 0; i < coas.length; i++) {
    var c = coas[i];
    var isRelevant = false;
    for (var j = 0; j < c.relevant_scenarios.length; j++) {
      if (Math.abs(currentPosition - c.relevant_scenarios[j]) <= 15) { isRelevant = true; break; }
    }
    var cardClass = 'suf-coa-card' + (isRelevant ? ' relevant' : '');
    html += '<div class="' + cardClass + '" data-coa-id="' + c.id + '">';
    html += '<div class="suf-coa-id">' + esc(c.id) + (isRelevant ? ' \u2014 RECOMMENDED' : '') + '</div>';
    html += '<div class="suf-coa-action">' + esc(c.action) + '</div>';
    html += '<div class="suf-coa-meta">';
    html += '<span>Cost: ' + esc(c.cost) + '</span>';
    html += '<span>' + esc(c.impact) + '</span>';
    html += '</div></div>';
  }
  document.getElementById('sufficiency-coa-cards').innerHTML = html;
}

function toggleSufficiencyCOA() {
  var panel = document.getElementById('sufficiency-coa-panel');
  var btn = document.getElementById('sufficiency-coa-toggle');
  if (panel.style.display === 'none') {
    panel.style.display = '';
    btn.textContent = '\u25B2 Hide Recommended Actions';
    if (currentSufficiencyMineral && currentSufficiencyMineral.sufficiency) {
      renderSufficiencyCOA(currentSufficiencyMineral.sufficiency.coa, currentScenarioPosition);
    }
  } else {
    panel.style.display = 'none';
    btn.textContent = '\uD83D\uDCCB View Recommended Actions';
  }
}

function updateCOARelevance(coas, currentPosition) {
  var cards = document.querySelectorAll('.suf-coa-card');
  if (cards.length === 0) return;
  for (var i = 0; i < coas.length; i++) {
    var c = coas[i];
    var isRelevant = false;
    for (var j = 0; j < c.relevant_scenarios.length; j++) {
      if (Math.abs(currentPosition - c.relevant_scenarios[j]) <= 15) { isRelevant = true; break; }
    }
    if (cards[i]) {
      cards[i].className = 'suf-coa-card' + (isRelevant ? ' relevant' : '');
      var idEl = cards[i].querySelector('.suf-coa-id');
      if (idEl) idEl.textContent = c.id + (isRelevant ? ' \u2014 RECOMMENDED' : '');
    }
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add sufficiency COA panel toggle and renderer"
```

---

### Task 8: Wire Sufficiency into renderMineralDetail

**Files:**
- Modify: `src/static/index.html` (JS section — add orchestrator function and hook it into `renderMineralDetail`)

- [ ] **Step 1: Add the orchestrator function**

Insert after the `updateCOARelevance` function (from Task 7):

```javascript

function renderSufficiency(m) {
  var row = document.getElementById('globe-sufficiency-row');
  if (!m.sufficiency) {
    row.style.display = 'none';
    currentSufficiencyMineral = null;
    return;
  }
  currentSufficiencyMineral = m;
  currentScenarioPosition = 0;
  var suf = m.sufficiency;
  var initial = suf.scenarios[0];

  renderSufficiencyGauge(initial.ratio, initial.verdict, initial.name, initial.supply_t, initial.demand_t);
  renderSufficiencyPlatforms(suf.demand, m.name, initial.ratio);
  renderSufficiencySlider(suf.scenarios);

  // Reset COA panel
  document.getElementById('sufficiency-coa-panel').style.display = 'none';
  document.getElementById('sufficiency-coa-toggle').textContent = '\uD83D\uDCCB View Recommended Actions';

  row.style.display = '';
}
```

- [ ] **Step 2: Hook renderSufficiency into renderMineralDetail**

Find the last line of `renderMineralDetail` (the line that sets Canada Impact innerHTML):

```javascript
  document.getElementById('globe-detail-canada').innerHTML = canadaHtml;
}
```

Replace with:

```javascript
  document.getElementById('globe-detail-canada').innerHTML = canadaHtml;

  // Render sufficiency analysis row (if data exists for this mineral)
  renderSufficiency(m);
}
```

- [ ] **Step 3: Verify the full flow works**

Run: `python -m src.main` and open `http://localhost:8000`. Navigate to Supply Chain → 3D Supply Map → click Cobalt. Verify:
1. The new "Demand & Supply Sufficiency" row appears below Canada Impact
2. Radial gauge shows "1.00x" with "Balanced" verdict
3. Platform cards show all 16 platforms with dependency badges and chain breadcrumbs
4. Slider is at 0% with all 5 preset labels
5. Dragging slider updates gauge and card styling (at-risk cards float up with red border)
6. "View Recommended Actions" button toggles the COA panel
7. Clicking a different mineral (e.g., Titanium) hides the sufficiency row
8. No console errors

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: wire sufficiency renderer into globe detail panel"
```

---

### Task 9: Run Full Test Suite

**Files:**
- Test: `tests/test_globe.py` and full suite

- [ ] **Step 1: Run the globe tests**

Run: `pytest tests/test_globe.py -v`
Expected: All tests pass including the 9 new `TestCobaltSufficiency` tests

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests continue to pass

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Cobalt demand-vs-supply sufficiency UI

Adds interactive sufficiency analysis to the 3D globe detail panel:
- Radial supply gauge with color-coded zones
- Platform dependency cards with direct/indirect OEM chain visualization
- Continuous scenario slider with 5 presets and interpolation
- On-demand COA recommendations panel (6 courses of action)

Data: 16 CAF platforms, 5 disruption scenarios, 6 COAs
Tests: 9 new tests for data structure integrity"
```
