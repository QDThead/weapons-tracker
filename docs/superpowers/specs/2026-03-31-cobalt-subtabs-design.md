# Cobalt Supply Chain Sub-Tabs — Design Spec

**Date:** 2026-03-31
**Status:** Approved
**Scope:** Add 6 new sub-tabs to the Supply Chain page, all defaulting to Cobalt with realistic placeholder data. Covers RFI Q3-4, Q10-13, Q16.

---

## Overview

Add 6 new sub-tabs to the existing Supply Chain PSI tab bar (single row, 12 total):

| # | Tab | RFI Question | Purpose |
|---|-----|-------------|---------|
| 1-6 | Existing | Q1-5 | Overview, 3D Supply Map, Knowledge Graph, Risk Matrix, Scenario Sandbox, Risk Taxonomy |
| 7 | **Forecasting** | Q12 | 12-18 month predictive analytics |
| 8 | **BOM Explorer** | Q3-4 | Rocks-to-Rockets multi-tier item illumination |
| 9 | **Supplier Dossier** | Q10 | Per-entity deep dive (financials, FOCI, ownership, news) |
| 10 | **Alerts & Sensing** | Q11 | Automated alert queue with evidence and COAs |
| 11 | **Risk Register** | Q13 | Risk cataloging, ownership, lifecycle tracking |
| 12 | **Analyst Feedback** | Q16 | RLHF panel, model accuracy, adjudication queue |

All tabs default to Cobalt via the existing global mineral selector. When Cobalt is selected, each tab shows Cobalt-specific content using data from `mineral_supply_chains.py` plus new placeholder data structures.

---

## Tab 7: Forecasting

**RFI Coverage:** Q12 — Real-Time & Predictive Analytics (12-18 month horizon)

### Layout
- **Top row:** 4 stat cards
  - Price Forecast: % change over 12 months (placeholder: +18%)
  - Lead Time Risk: estimated delay in days (placeholder: +14 days Q3 2026)
  - Supplier Insolvency: highest-risk supplier probability (placeholder: Sherritt 35%)
  - Supply Adequacy: supply/demand ratio (from existing sufficiency data)
- **Bottom row:** 2-column
  - Left: Price forecast bar chart — 6 historical quarters + 6 projected quarters, color-coded (blue=historical, dashed amber/red=forecast)
  - Right: Forecast Signals list — bullet points with severity dots showing key drivers

### Data Source
- New `forecasting` key added to Cobalt data in `mineral_supply_chains.py`
- Contains: `price_forecast`, `lead_time`, `insolvency_risks[]`, `signals[]`
- Supply adequacy from existing `sufficiency.scenarios[0].ratio`

---

## Tab 8: BOM Explorer

**RFI Coverage:** Q3-4 — Multi-Tier Mapping & Item-Based Illumination

### Layout
- **Indented tree view** showing the full Cobalt BOM explosion:
  - Tier 1 (green): Cobalt raw mineral — mining countries with % share
  - Tier 2 (purple): Refined cobalt metal — processing countries with % share
  - Tier 3 (amber): Alloys/Components — Waspaloy (13% Co), CMSX-4 (9.5% Co), Stellite 6 (60% Co), SmCo magnets (52% Co), Li-CoO batteries, cemented carbides
  - Tier 4 (cyan): CAF Platforms — linked through engines/components
- **Each node clickable** to show: risk score, confidence level, supplier details
- **Legend** at bottom with tier colors
- **Confidence badges** per tier: Tier 1 (99%), Tier 2 (85-95%), Tier 3 (70-85%), Tier 4 (60-75%)

### Data Source
- Built from existing Cobalt data: `mining[]`, `processing[]`, `alloys[]`, `components[]`, `platforms[]`, `sufficiency.demand[]`
- Tree structure assembled client-side from these arrays
- No new API endpoint needed — uses `/globe/minerals/Cobalt`

---

## Tab 9: Supplier Dossier

**RFI Coverage:** Q10 — Operational View (Supplier Deep Dive)

### Layout
- **Supplier selector dropdown** at top — lists all entities from Cobalt mines + refineries
- **Header row:** 3 cards
  - Entity info: name, type (SOE/private), country, FOCI badge
  - Financial Health: Altman Z-Score, insolvency probability, credit trend
  - Operations: production capacity, key products, flags (ADVERSARY-CONTROLLED, etc.)
- **Two-column below:**
  - Left: Ownership Chain (UBO) — text breadcrumb showing parent → ultimate owner → state
  - Right: Recent Intelligence — news/events with severity dots
- **Bottom sections (placeholder):**
  - Contract Summary: DND contracts linked to this supplier (placeholder table)
  - Risk Timeline: Chronological risk events

### Data Source
- New `dossier` key added to each mine/refinery entry in Cobalt data
- Contains: `z_score`, `insolvency_prob`, `ubo_chain[]`, `recent_intel[]`, `contracts[]`
- Falls back to existing `taxonomy_scores` and `kpis` for basic data

---

## Tab 10: Alerts & Sensing

**RFI Coverage:** Q11 — Automated Sensing & Alert Capabilities (Watchtower)

### Layout
- **Summary bar:** severity counts (Critical/High/Medium/Low)
- **Alert cards** stacked vertically, sorted by severity:
  - Left border color by severity (red=5, orange=4, amber=3, cyan=2, green=1)
  - Title, source attribution, confidence score
  - Recommended COA (from playbook)
  - Action buttons: Acknowledge, Assign, Escalate, Evidence Locker
- **Filter controls:** by category, severity, date range

### Data Source
- New `alerts` array added to Cobalt data in `mineral_supply_chains.py`
- Each alert: `id`, `title`, `severity` (1-5), `category`, `sources[]`, `confidence`, `coa`, `timestamp`
- 6 placeholder alerts covering FOCI, export controls, financial, cyber, environmental, logistics

---

## Tab 11: Risk Register

**RFI Coverage:** Q13 — Decision Support & Mitigation, Risk Register Functionality

### Layout
- **Sortable table** with columns:
  - ID (CO-001 format)
  - Risk description
  - Category (FOCI, Political, Manufacturing, Technology, etc.)
  - Severity badge (Critical/High/Medium/Low)
  - Status (Open → In Progress → Mitigated → Closed) with color coding
  - Owner (DND role/team)
  - Due date
- **Each row expandable** to show:
  - Linked COAs from playbook
  - Evidence references
  - Audit trail (placeholder)
  - Escalation history
- **Summary stats** at top: total risks, by status, overdue count

### Data Source
- New `risk_register` array added to Cobalt data
- 8-10 placeholder risks covering all major Cobalt risk factors
- Each: `id`, `risk`, `category`, `severity`, `status`, `owner`, `due_date`, `coas[]`, `evidence[]`

---

## Tab 12: Analyst Feedback (RLHF)

**RFI Coverage:** Q16 — AI/ML Trainability, Human-in-the-Loop Feedback

### Layout
- **Top row:** 3 stat cards
  - Model Accuracy: % over last 90 days (placeholder: 87%)
  - False Positive Rate: % with trend arrow (placeholder: 18% ↓)
  - Pending Review: count awaiting analyst (placeholder: 4)
- **Pending Adjudication queue:** cards with:
  - Alert/insight text
  - Source and confidence score
  - Two buttons: Verified (green) / False Positive (red)
- **Bottom section:**
  - Threshold configuration: current z-score, RLHF-adjusted threshold
  - Recent feedback history (last 10 adjudications with analyst name and outcome)

### Data Source
- New `analyst_feedback` key in Cobalt data
- Contains: `accuracy`, `fp_rate`, `pending[]`, `recent_feedback[]`, `threshold`
- Placeholder: 4 pending items, 6 recent feedback entries

---

## Implementation Approach

### Files Modified
1. **`src/static/index.html`** — Add 6 tab buttons, 6 `psi-sub` div containers, 6 render functions, wire into `switchPsiTab` and `onGlobalMineralChange`
2. **`src/analysis/mineral_supply_chains.py`** — Add `forecasting`, `dossier` (per entity), `alerts`, `risk_register`, `analyst_feedback` data to Cobalt entry

### No New API Endpoints
All new data served through existing `/globe/minerals/Cobalt` endpoint. The data structures are added to the Cobalt dict in `mineral_supply_chains.py`.

### Mineral-Aware Pattern
All 6 tabs follow the existing pattern:
- Check `getGlobalMineral()` — if empty, show "Select a mineral" message
- If mineral selected, fetch `/globe/minerals/{name}` and render
- Wired into `onGlobalMineralChange()` and `switchPsiTab()` for refresh

### Tab Bar
Single row with all 12 tabs. Existing design system CSS (`.tab`, `.psi-sub`) reused. No new CSS needed beyond what exists.
