# Handover Document — Weapons Tracker Platform
# Session: 2026-03-31 (Afternoon — Scenario Sandbox Rework)

**Timestamp:** 2026-03-31 16:30 EDT / 2026-03-31 20:30 UTC
**Prepared by:** Claude Opus 4.6 + William Dennis
**Session duration:** ~5 hours
**Commits this session:** 10
**Platform:** PSI Control Tower — Defence Supply Chain Intelligence

---

## Executive Summary

This session focused on a complete rewrite of the Supply Chain Scenario Sandbox to meet all DMPP 11 RFI requirements (Q1, Q12, Q13). The old sandbox had two disconnected modes (a generic 5-scenario form and a Cobalt sufficiency slider). The new sandbox is a unified, mineral-first "Digital Twin" with multi-variable scenario composition, Sankey cascade visualization, scenario comparison, COA comparison, and PDF/CSV/JSON export. Additionally, the 3D Supply Map was fixed to default to Cobalt instead of multiple minerals.

---

## What Was Built This Session

### 1. ScenarioEngine (New Backend)

**New file: `src/analysis/scenario_engine.py`** (520 lines)

Multi-variable disruption simulation engine that replaces the 5 separate scenario methods in `supply_chain.py`.

| Capability | How It Works |
|-----------|-------------|
| **Layer Composition** | Stackable disruption layers applied sequentially: sanctions, shortages, route disruptions, supplier failures, demand surges |
| **Cascade Propagation** | 4-tier BOM walk: Mining → Processing → Alloys → Platforms. Each tier's output constrains the next. |
| **Impact Metrics** | Value at Risk ($), Platforms Affected, Risk Score (0-100), Risk Rating (LOW/HIGH/CRITICAL), Likelihood (0-1), Supply Reduction %, Lead Time +Days |
| **Dollar Values** | Platform program values ($80M-$1.2B per platform) + material cost impact |
| **Likelihood** | Union probability formula across layer types (adding layers never decreases risk) |
| **COA Generation** | Merges mineral's existing playbook + layer-specific actions (sanctions → "find alternatives", route → "reroute shipments", etc.) |
| **Sufficiency** | Supply/demand ratio scaled by disruption, with deficit verdict |

### 2. New API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /psi/scenario/v2` | Multi-variable scenario simulation with consistent response shape |
| `POST /psi/scenario/export/pdf` | PDF briefing export (fpdf2) with impact summary, cascade table, COAs, multi-scenario comparison page |

### 3. Frontend: 3-Zone Scenario Sandbox

Replaced ~300 lines of old HTML/JS with ~500 lines of new code.

| Zone | Contents |
|------|----------|
| **Left (280px): Scenario Builder** | 5 preset compound scenarios (Indo-Pacific Conflict, Arctic Escalation, Global Recession, DRC Collapse, Suez Closure), stackable disruption layer cards with type dropdowns and parameter inputs, demand surge slider (-50% to +200%), time horizon slider (3-24 months), Run/Reset/Export buttons |
| **Center (flex): Results + Cascade** | 4 impact summary cards (Value at Risk, Platforms Affected, Risk Score, Likelihood), Sankey cascade visualization (4-tier Rocks→Rockets with color-coded disruption status), inline COA grid (2-column, priority-coded), "Compare All COAs" link |
| **Right (240px): History Panel** | Up to 4 saved scenario runs with checkboxes, side-by-side comparison view (metrics table + mini Sankeys), PDF/CSV/JSON export buttons |

Additional: COA Comparison Drawer (bottom slide-up panel with merged, sortable COA table across all saved scenarios).

### 4. 3D Supply Map Default Fix

Changed the globe initialization from "auto-enable top 3 critical minerals" to "default to Cobalt" — matching the global mineral selector and preventing the confusing Rare Earth/Tungsten default.

### 5. Adversarial Test Suite

**New file: `tests/test_scenario_adversarial.py`** (898 lines, 85 tests)

Covers: all 5 presets, all 5 layer types, multi-layer combinations (2-5 layers), edge cases (zero/negative/extreme values, unknown entities), invalid inputs (missing fields, malformed JSON, non-existent minerals), deep response validation (all fields, types, ranges), PDF export, performance benchmarks, monotonicity invariants.

### 6. Bug Fixes Found During Adversarial Testing

| Bug | Fix |
|-----|-----|
| Supply reduction baseline mismatch (named mines 77,100t vs global 237,000t inflating reduction) | Track `node_supply_total` separately; compare disrupted vs undisrupted node totals |
| Supplier failure name matching ("Mutanda Mine" didn't match "Mutanda") | Switched to partial/bidirectional name matching |
| Sufficiency ratio broken after baseline fix | Scale baseline supply by disruption ratio from node-level data |

---

## Files Changed This Session

| File | Lines | Changes |
|------|-------|---------|
| `src/analysis/scenario_engine.py` | 520 | NEW — Multi-variable scenario engine |
| `tests/test_scenario_engine.py` | 224 | NEW — 18 unit tests (single-layer, multi-layer, cascade, COAs) |
| `tests/test_scenario_api.py` | 91 | NEW — 6 API integration tests |
| `tests/test_scenario_adversarial.py` | 898 | NEW — 85 adversarial tests |
| `src/api/psi_routes.py` | +60 | New Pydantic models, `/scenario/v2` and `/scenario/export/pdf` endpoints |
| `src/static/index.html` | 10,738 | Replaced scenario sandbox HTML + JS (~300 old → ~500 new), fixed globe default |
| `docs/superpowers/specs/2026-03-31-scenario-sandbox-design.md` | 404 | NEW — Design spec |
| `docs/superpowers/plans/2026-03-31-scenario-sandbox.md` | 1,984 | NEW — Implementation plan (9 tasks) |
| `CLAUDE.md` | — | Updated stats, features, endpoints, file structure |
| `README.md` | — | Updated Supply Chain tab description |

---

## Commits This Session

| SHA | Message |
|-----|---------|
| 9435680 | docs: add Scenario Sandbox rework design spec |
| f094ea1 | docs: add Scenario Sandbox implementation plan (9 tasks) |
| 59df1d8 | feat: add ScenarioEngine with multi-layer disruption simulation |
| 1d33720 | test: add multi-layer, cascade, and COA generation tests |
| 2ada1c7 | feat: add POST /psi/scenario/v2 endpoint with multi-layer support |
| 7937b13 | feat: add PDF export endpoint for scenario briefings |
| e5362cd | feat: rewrite scenario sandbox with 3-zone layout, Sankey cascade, comparison, export |
| 7d3107c | docs: update CLAUDE.md with new Scenario Sandbox capabilities |
| ac512c2 | fix: default 3D Supply Map to Cobalt instead of top 3 critical minerals |
| e39402a | fix: scenario engine baseline mismatch + supplier name matching |

---

## Known Issues

| Issue | Status | Notes |
|-------|--------|-------|
| test_resolved_action_not_reopened | FAILING | Pre-existing mitigation test failure (not from this session) |
| IMF Cobalt Price API | UNREACHABLE | Using FRED nickel as proxy (from prior session) |
| Suez Closure preset | LOW IMPACT ON COBALT | Cobalt routes don't transit Suez (DRC→China goes via Indian Ocean/Malacca). Preset is valid for other minerals. |
| COA table sorting | STUB | Column headers have sort arrows but sorting not yet wired. Low priority. |
| Non-Cobalt minerals | PLACEHOLDER | Scenario Sandbox shows "not yet available" for non-Cobalt minerals (same as other sub-tabs) |
| Server start in Claude Code | BACKGROUND PROCESS ISSUE | `run_in_background` causes server to appear dead. Use `! python -m src.main` from prompt instead. |

---

## RFI Requirements Now Met by Scenario Sandbox

| RFI Requirement | Question | Implementation |
|----------------|----------|---------------|
| Multi-variable what-if simulations | Q12 | Stackable disruption layers (sanctions + routes + shortages + failures + demand) |
| Preset compound scenarios | Q12 | 5 named presets (Indo-Pacific, Arctic, Recession, DRC, Suez) |
| Downstream cascade visualization | Q12 | 4-tier Sankey waterfall (Mining → Processing → Alloys → Platforms) |
| Dollar-value impact estimates | Q12 | Value at Risk ($) derived from platform program values |
| Likelihood x Impact scoring | Q12 | Risk Score (0-100) with RED/AMBER/GREEN rating |
| Real-time diagnostics | Q12 | Impact cards update on each scenario run |
| Scenario comparison | Q12 | Up to 4 saved runs, side-by-side metrics table + mini Sankeys |
| Side-by-side COA comparison | Q13 | COA comparison drawer with merged, sortable table |
| Risk register integration | Q13 | COAs include risk reduction estimates and affected platforms |
| Export to briefings | Q12 | PDF (fpdf2), CSV, JSON export from any scenario or comparison |
| Course of Action generation | Q13 | Auto-generated COAs from mineral playbook + layer-specific actions |

---

## What's In Progress / Next Steps

### Priority 1: Deep-dive remaining 29 minerals
Cobalt is the complete template. Each mineral needs the same depth for the Scenario Sandbox to work: mines, refineries, alloys, shipping routes with chokepoints, sufficiency scenarios.

### Priority 2: Wire COA table sorting
Column header click handlers in the COA comparison drawer are stubs. Need to store allCOAs in a module-level var and re-render on sort.

### Priority 3: Connect Analyst Feedback to real RLHF loop
Currently placeholder buttons. Wire Verified/False Positive clicks to POST `/ml/feedback` endpoint.

### Priority 4: Connect Risk Register to database
Currently static data in `mineral_supply_chains.py`. Should persist to `mitigation_actions` table.

### Priority 5: Connect Alerts to live OSINT feeds
Currently static placeholder alerts. Wire to GDELT, sanctions, cyber, and environmental feeds.

---

## Project Stats (Post-Session)

| Metric | Value |
|--------|-------|
| Python files | 68 |
| Total Python lines | ~33,000 |
| HTML dashboard | ~10,700 lines |
| API endpoints | 155+ |
| Active data feeds | ~90+ |
| Database tables | 18 |
| Tests | 195 (110 unit/integration + 85 adversarial; 194 passing, 1 pre-existing failure) |
| Minerals tracked | 30 (1 deep: Cobalt) |
| Supply chain sub-tabs | 12 |
| Scenario presets | 5 |
| Scenario layer types | 5 |
| Adversarial test categories | 9 |
| Arms transfers | 9,311 |
| DND compliance | 95.3% (137 sub-requirements) |

---

## How to Run

```bash
cd weapons-tracker
source venv/Scripts/activate  # Windows
python -m scripts.seed_database  # one-time
python -m src.main
# Dashboard: http://localhost:8000
# API docs: http://localhost:8000/docs
```

---

**Quantum Data Technologies (QDT)**
Canadian-owned | No foreign dependency | Data sovereign
