# Cobalt Supply Chain Sub-Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 6 new sub-tabs (Forecasting, BOM Explorer, Supplier Dossier, Alerts & Sensing, Risk Register, Analyst Feedback) to the Supply Chain page, all defaulting to Cobalt with realistic placeholder data.

**Architecture:** All data lives in the Cobalt dict in `mineral_supply_chains.py`, served via the existing `/globe/minerals/Cobalt` endpoint. Each tab is a `psi-sub` div with a render function wired into `switchPsiTab()` and `onGlobalMineralChange()`. No new API endpoints.

**Tech Stack:** Python (data), vanilla JS (rendering), existing CSS design system (`.card`, `.stat-box`, `.tab`, `.psi-sub`)

---

### Task 1: Add Cobalt placeholder data to mineral_supply_chains.py

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py:1297-1299` (insert before `"source"` key)
- Test: `tests/test_globe.py` (add new test class)

- [ ] **Step 1: Write failing tests for new Cobalt data keys**

Add to `tests/test_globe.py` at the end of the file:

```python
class TestCobaltNewData:
    """Verify new Cobalt sub-tab data structures."""

    def test_forecasting_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "forecasting" in m
        f = m["forecasting"]
        assert "price_forecast" in f
        assert "lead_time" in f
        assert "insolvency_risks" in f
        assert isinstance(f["insolvency_risks"], list)
        assert len(f["insolvency_risks"]) >= 1
        assert "signals" in f
        assert isinstance(f["signals"], list)
        assert len(f["signals"]) >= 3
        assert "price_history" in f
        assert isinstance(f["price_history"], list)

    def test_forecasting_signals_structure(self):
        signals = get_mineral_by_name("Cobalt")["forecasting"]["signals"]
        for s in signals:
            assert "text" in s
            assert "severity" in s
            assert s["severity"] in ("critical", "high", "medium", "low")

    def test_alerts_exist(self):
        m = get_mineral_by_name("Cobalt")
        assert "watchtower_alerts" in m
        alerts = m["watchtower_alerts"]
        assert isinstance(alerts, list)
        assert len(alerts) >= 6

    def test_alerts_structure(self):
        alerts = get_mineral_by_name("Cobalt")["watchtower_alerts"]
        for a in alerts:
            assert "id" in a
            assert "title" in a
            assert "severity" in a and 1 <= a["severity"] <= 5
            assert "category" in a
            assert "sources" in a and isinstance(a["sources"], list)
            assert "confidence" in a and 0 <= a["confidence"] <= 100
            assert "coa" in a
            assert "timestamp" in a

    def test_risk_register_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "risk_register" in m
        rr = m["risk_register"]
        assert isinstance(rr, list)
        assert len(rr) >= 8

    def test_risk_register_structure(self):
        rr = get_mineral_by_name("Cobalt")["risk_register"]
        valid_statuses = {"open", "in_progress", "mitigated", "closed"}
        valid_severities = {"critical", "high", "medium", "low"}
        for r in rr:
            assert "id" in r
            assert "risk" in r
            assert "category" in r
            assert "severity" in r and r["severity"] in valid_severities
            assert "status" in r and r["status"] in valid_statuses
            assert "owner" in r
            assert "due_date" in r
            assert "coas" in r and isinstance(r["coas"], list)

    def test_analyst_feedback_exists(self):
        m = get_mineral_by_name("Cobalt")
        assert "analyst_feedback" in m
        af = m["analyst_feedback"]
        assert "accuracy" in af and 0 <= af["accuracy"] <= 100
        assert "fp_rate" in af and 0 <= af["fp_rate"] <= 100
        assert "threshold" in af
        assert "pending" in af and isinstance(af["pending"], list)
        assert len(af["pending"]) >= 3
        assert "recent" in af and isinstance(af["recent"], list)
        assert len(af["recent"]) >= 5

    def test_analyst_feedback_pending_structure(self):
        pending = get_mineral_by_name("Cobalt")["analyst_feedback"]["pending"]
        for p in pending:
            assert "text" in p
            assert "source" in p
            assert "confidence" in p and 0 <= p["confidence"] <= 100

    def test_mine_dossier_exists(self):
        m = get_mineral_by_name("Cobalt")
        tfm = m["mines"][0]
        assert "dossier" in tfm
        d = tfm["dossier"]
        assert "z_score" in d
        assert "insolvency_prob" in d
        assert "ubo_chain" in d and isinstance(d["ubo_chain"], list)
        assert "recent_intel" in d and isinstance(d["recent_intel"], list)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_globe.py::TestCobaltNewData -v`
Expected: FAIL — KeyError on `forecasting`, `watchtower_alerts`, etc.

- [ ] **Step 3: Add forecasting data to Cobalt entry**

In `src/analysis/mineral_supply_chains.py`, insert before `"source": "USGS MCS 2025"` (line ~1298) in the Cobalt dict:

```python
        "forecasting": {
            "price_forecast": {"pct_change": 18, "period": "12 months", "direction": "up"},
            "lead_time": {"days": 14, "period": "Q3 2026", "component": "Cobalt hydroxide"},
            "insolvency_risks": [
                {"supplier": "Sherritt International", "probability_pct": 35, "horizon": "6 months", "reason": "Cuba pipeline paused, cobalt price crash, debt load"},
                {"supplier": "Cobalt Blue (ASX:COB)", "probability_pct": 22, "horizon": "12 months", "reason": "Broken Hill project shelved, cash burn"},
            ],
            "price_history": [
                {"quarter": "Q1 2025", "usd_lb": 13.20, "type": "actual"},
                {"quarter": "Q2 2025", "usd_lb": 12.80, "type": "actual"},
                {"quarter": "Q3 2025", "usd_lb": 11.50, "type": "actual"},
                {"quarter": "Q4 2025", "usd_lb": 10.90, "type": "actual"},
                {"quarter": "Q1 2026", "usd_lb": 11.20, "type": "actual"},
                {"quarter": "Q2 2026", "usd_lb": 11.80, "type": "actual"},
                {"quarter": "Q3 2026", "usd_lb": 12.50, "type": "forecast"},
                {"quarter": "Q4 2026", "usd_lb": 13.10, "type": "forecast"},
                {"quarter": "Q1 2027", "usd_lb": 13.80, "type": "forecast"},
                {"quarter": "Q2 2027", "usd_lb": 14.20, "type": "forecast"},
                {"quarter": "Q3 2027", "usd_lb": 14.60, "type": "forecast"},
                {"quarter": "Q4 2027", "usd_lb": 15.00, "type": "forecast"},
            ],
            "signals": [
                {"text": "DRC export quotas cut authorized output by >50%", "severity": "critical"},
                {"text": "Sherritt Cuba pipeline paused since Feb 2026", "severity": "critical"},
                {"text": "F-35 delivery ramp increases CAF cobalt demand 2.5x", "severity": "high"},
                {"text": "China considering cobalt export controls", "severity": "high"},
                {"text": "Indonesia HPAL capacity expanding (Chinese-financed)", "severity": "medium"},
                {"text": "Pentagon $500M cobalt stockpile program — Canada preferred supplier", "severity": "low"},
            ],
        },
```

- [ ] **Step 4: Add watchtower_alerts to Cobalt entry**

Insert after the `forecasting` block:

```python
        "watchtower_alerts": [
            {"id": "COA-001", "title": "FOCI: CMOC acquires additional DRC cobalt concession", "severity": 5, "category": "FOCI", "sources": ["Reuters", "SEC EDGAR", "DRC Corporate Registry"], "confidence": 92, "coa": "Initiate National Security Review; assess impact on CAF platform supply chain", "timestamp": "2026-03-28T14:30:00Z"},
            {"id": "COA-002", "title": "Export Controls: DRC cobalt export ban extended to Q4 2026", "severity": 5, "category": "Political", "sources": ["DRC Ministry of Mines", "GDELT", "Mining.com"], "confidence": 88, "coa": "Activate alternate supplier qualification; increase safety stock from Umicore", "timestamp": "2026-03-25T09:15:00Z"},
            {"id": "COA-003", "title": "Financial: Sherritt International credit downgrade to CCC+", "severity": 4, "category": "Financial", "sources": ["S&P Global", "TMX Group", "Financial Post"], "confidence": 95, "coa": "Assess Sherritt contract exposure; pre-qualify Vale Long Harbour as backup", "timestamp": "2026-03-20T11:00:00Z"},
            {"id": "COA-004", "title": "Cyber: Ransomware incident at Umicore Belgium refinery", "severity": 4, "category": "Cyber", "sources": ["Malpedia", "Umicore IR", "BleepingComputer"], "confidence": 78, "coa": "Request incident report from Umicore; assess data exposure for DND supply data", "timestamp": "2026-03-18T16:45:00Z"},
            {"id": "COA-005", "title": "Environmental: Flooding at Kolwezi mining district (DRC)", "severity": 3, "category": "Environmental", "sources": ["NASA FIRMS", "GDACS", "Reuters Africa"], "confidence": 82, "coa": "Monitor production impact; assess 30-day supply buffer adequacy", "timestamp": "2026-03-15T08:20:00Z"},
            {"id": "COA-006", "title": "Logistics: Port strike at Dar es Salaam delays cobalt shipments", "severity": 3, "category": "Transportation", "sources": ["PortWatch", "AIS data", "Tanzania Daily News"], "confidence": 75, "coa": "Divert shipments via Durban (+4 days transit); notify downstream OEMs", "timestamp": "2026-03-10T13:00:00Z"},
        ],
```

- [ ] **Step 5: Add risk_register to Cobalt entry**

Insert after `watchtower_alerts`:

```python
        "risk_register": [
            {"id": "CO-001", "risk": "Chinese SOE (CMOC) controls 76% of global cobalt mining", "category": "FOCI", "severity": "critical", "status": "in_progress", "owner": "DMPP 11", "due_date": "2026-06-30", "coas": ["Diversify sourcing to Five Eyes suppliers", "Support Pentagon cobalt stockpile partnership"], "evidence": ["CMOC annual report", "SIPRI ownership data"]},
            {"id": "CO-002", "risk": "DRC export quotas cut authorized cobalt output >50%", "category": "Political", "severity": "critical", "status": "open", "owner": "DSCRO", "due_date": "2026-05-15", "coas": ["Engage DRC embassy", "Pre-position inventory from alternate sources"], "evidence": ["DRC Ministry decree", "Mining.com analysis"]},
            {"id": "CO-003", "risk": "Sherritt Cuba cobalt pipeline paused (Feb 2026)", "category": "Manufacturing", "severity": "high", "status": "in_progress", "owner": "ADM(Mat)", "due_date": "2026-09-01", "coas": ["Monitor Cuba energy crisis", "Pre-qualify Vale Long Harbour as replacement"], "evidence": ["Sherritt IR release", "Cuba energy ministry"]},
            {"id": "CO-004", "risk": "No substitutes exist for cobalt in turbine superalloys", "category": "Technology", "severity": "high", "status": "mitigated", "owner": "DG Sci&Tech", "due_date": "2026-12-01", "coas": ["Fund NRC cobalt-free alloy research", "Track DARPA alternatives program"], "evidence": ["NRC metallurgy report", "DARPA program brief"]},
            {"id": "CO-005", "risk": "China refines 80% of global cobalt — single chokepoint", "category": "Manufacturing", "severity": "critical", "status": "open", "owner": "DMPP 11", "due_date": "2026-07-31", "coas": ["Support Finnish/Belgian refinery expansion", "Advocate NATO critical minerals agreement"], "evidence": ["USGS MCS 2025", "EU CRM Act"]},
            {"id": "CO-006", "risk": "Cobalt price crashed 70% (2022-2024) causing mine deferrals", "category": "Economic", "severity": "high", "status": "in_progress", "owner": "CFO/DFin", "due_date": "2026-08-15", "coas": ["Establish long-term offtake agreements", "Support Canadian mine subsidies via CRTC"], "evidence": ["LME price data", "Cobalt Blue shelving announcement"]},
            {"id": "CO-007", "risk": "M23 conflict advancing toward Katanga cobalt mining region", "category": "Political", "severity": "critical", "status": "open", "owner": "CDI", "due_date": "2026-04-30", "coas": ["Activate OSINT monitoring of DRC conflict zone", "Pre-position 90-day cobalt safety stock"], "evidence": ["UN OCHA sitrep", "ACLED conflict data"]},
            {"id": "CO-008", "risk": "Artisanal mining (ASM) child labor risk in Kolwezi area", "category": "Compliance", "severity": "high", "status": "in_progress", "owner": "JAG/Legal", "due_date": "2026-10-01", "coas": ["Require RMI chain-of-custody certification", "Audit Tier 1 suppliers for ASM contamination"], "evidence": ["Amnesty International report", "IPIS DRC mine data"]},
            {"id": "CO-009", "risk": "F-35 acquisition will increase cobalt dependency significantly", "category": "Planning", "severity": "high", "status": "open", "owner": "DAPA", "due_date": "2027-03-01", "coas": ["Model F-35 cobalt demand curve", "Negotiate cobalt clause in F-35 MOU"], "evidence": ["F-35 JPO logistics data", "P&W F135 BOM"]},
            {"id": "CO-010", "risk": "Strait of Malacca disruption could halt DRC-China cobalt flow", "category": "Transportation", "severity": "high", "status": "mitigated", "owner": "DSCRO", "due_date": "2026-11-30", "coas": ["Map alternate Cape of Good Hope routing", "Pre-negotiate rerouting with shipping partners"], "evidence": ["IMF PortWatch", "AIS chokepoint data"]},
        ],
```

- [ ] **Step 6: Add analyst_feedback to Cobalt entry**

Insert after `risk_register`:

```python
        "analyst_feedback": {
            "accuracy": 87,
            "fp_rate": 18,
            "fp_trend": "down",
            "threshold": {"current_z": 2.5, "rlhf_adjusted": 2.3, "last_retrain": "2026-03-15"},
            "pending": [
                {"text": "Indonesia cobalt output may surpass DRC by 2028", "source": "GDELT — Mining Weekly", "confidence": 62},
                {"text": "Cobalt price manipulation by Chinese refiners suspected", "source": "Reuters, FT", "confidence": 71},
                {"text": "New cobalt deposit discovered in Zambia — pre-feasibility stage", "source": "Mining.com", "confidence": 55},
                {"text": "CATL developing cobalt-free LFP batteries for military use", "source": "Nikkei Asia, CATL IR", "confidence": 68},
            ],
            "recent": [
                {"text": "CMOC production target raised for 2026", "verdict": "verified", "analyst": "J. Smith", "date": "2026-03-28"},
                {"text": "Russian cobalt exports increasing via Turkey", "verdict": "verified", "analyst": "M. Chen", "date": "2026-03-26"},
                {"text": "Cobalt shortage predicted for Q4 2026", "verdict": "false_positive", "analyst": "J. Smith", "date": "2026-03-24"},
                {"text": "Glencore Raglan mine closure rumor", "verdict": "false_positive", "analyst": "A. Roy", "date": "2026-03-22"},
                {"text": "DRC nationalizing CMOC assets", "verdict": "false_positive", "analyst": "M. Chen", "date": "2026-03-20"},
                {"text": "Umicore expanding Hoboken refinery capacity 20%", "verdict": "verified", "analyst": "A. Roy", "date": "2026-03-18"},
            ],
        },
```

- [ ] **Step 7: Add dossier data to the first 3 Cobalt mines**

In the Cobalt `mines` array, add a `"dossier"` key to the first mine entry (Tenke Fungurume, starts around line 307). Insert after the `"kpis"` block closing `}`:

```python
             "dossier": {
                 "z_score": 2.8,
                 "insolvency_prob": 8,
                 "credit_trend": "stable",
                 "ubo_chain": ["CMOC Group (HK:3993)", "China Molybdenum Co. Ltd.", "Luoyang Mining Group", "State Council of the PRC"],
                 "recent_intel": [
                     {"text": "DRC export quota cuts TFM authorized output by 50%", "severity": "critical", "date": "2026-03-01"},
                     {"text": "CATL partnership deepens mine-to-battery vertical integration", "severity": "high", "date": "2026-02-15"},
                     {"text": "Community water contamination lawsuit filed in Kolwezi court", "severity": "medium", "date": "2026-01-20"},
                 ],
                 "contracts": [
                     {"id": "DND-CO-2024-001", "description": "Cobalt hydroxide supply (indirect via Umicore)", "value_cad": 2400000, "status": "active", "end_date": "2027-12-31"},
                 ],
             },
```

Add similar `dossier` blocks to Kisanfu (mine index 1) and Mutanda (mine index 2) with appropriate z_score, UBO chains, and intel. Use these values:

Kisanfu dossier:
```python
             "dossier": {
                 "z_score": 2.5,
                 "insolvency_prob": 10,
                 "credit_trend": "declining",
                 "ubo_chain": ["CMOC Group 75%", "CATL 25%", "Luoyang Mining Group", "State Council of the PRC"],
                 "recent_intel": [
                     {"text": "CATL 25% stake creates mine-to-EV-battery vertical integration", "severity": "critical", "date": "2026-02-28"},
                     {"text": "Production ramp-up behind schedule — power grid constraints", "severity": "high", "date": "2026-01-15"},
                 ],
                 "contracts": [],
             },
```

Mutanda dossier (mine index 2 — check the actual mine name and adapt):
```python
             "dossier": {
                 "z_score": 3.1,
                 "insolvency_prob": 5,
                 "credit_trend": "stable",
                 "ubo_chain": ["Glencore plc (LSE:GLEN)", "Glencore International AG", "Public shareholders (no state control)"],
                 "recent_intel": [
                     {"text": "Mutanda restart at 60% capacity after 2020-2023 suspension", "severity": "medium", "date": "2026-03-10"},
                     {"text": "Glencore exploring partial sale of DRC cobalt assets", "severity": "high", "date": "2026-02-01"},
                 ],
                 "contracts": [
                     {"id": "DND-CO-2025-003", "description": "Cobalt metal supply via Sudbury refinery", "value_cad": 1800000, "status": "active", "end_date": "2028-06-30"},
                 ],
             },
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/test_globe.py -v`
Expected: ALL PASS (existing 23 + new ~10 tests)

- [ ] **Step 9: Commit**

```bash
git add src/analysis/mineral_supply_chains.py tests/test_globe.py
git commit -m "feat: add Cobalt forecasting, alerts, risk register, feedback, dossier data"
```

---

### Task 2: Add 6 tab buttons and empty containers to index.html

**Files:**
- Modify: `src/static/index.html:1886-1891` (tab bar)
- Modify: `src/static/index.html` (add 6 psi-sub divs after existing ones, before `</div>` closing page-supply-chain)

- [ ] **Step 1: Add 6 new tab buttons to the psi-tab-bar**

Find the tab bar (line ~1891, after the Risk Taxonomy button, before the mineral selector div):

Replace:
```html
      <button class="tab" data-psi-tab="psi-taxonomy" onclick="switchPsiTab(this)">Risk Taxonomy</button>
      <div style="margin-left:auto; display:flex; align-items:center; gap:6px;">
```

With:
```html
      <button class="tab" data-psi-tab="psi-taxonomy" onclick="switchPsiTab(this)">Risk Taxonomy</button>
      <button class="tab" data-psi-tab="psi-forecasting" onclick="switchPsiTab(this)">Forecasting</button>
      <button class="tab" data-psi-tab="psi-bom" onclick="switchPsiTab(this)">BOM Explorer</button>
      <button class="tab" data-psi-tab="psi-dossier" onclick="switchPsiTab(this)">Supplier Dossier</button>
      <button class="tab" data-psi-tab="psi-alerts" onclick="switchPsiTab(this)">Alerts</button>
      <button class="tab" data-psi-tab="psi-register" onclick="switchPsiTab(this)">Risk Register</button>
      <button class="tab" data-psi-tab="psi-feedback" onclick="switchPsiTab(this)">Analyst Feedback</button>
      <div style="margin-left:auto; display:flex; align-items:center; gap:6px;">
```

- [ ] **Step 2: Add 6 empty psi-sub container divs**

Find the closing `</div>` of the last existing psi-sub (psi-taxonomy section). After the Risk Taxonomy `</div>`, before `</div>` that closes `page-supply-chain`, insert:

```html
    <!-- PSI Forecasting -->
    <div id="psi-forecasting" class="psi-sub" style="display:none;">
      <div id="psi-forecasting-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view forecasting data.</div>
      </div>
    </div>

    <!-- PSI BOM Explorer -->
    <div id="psi-bom" class="psi-sub" style="display:none;">
      <div id="psi-bom-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view BOM explosion.</div>
      </div>
    </div>

    <!-- PSI Supplier Dossier -->
    <div id="psi-dossier" class="psi-sub" style="display:none;">
      <div id="psi-dossier-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view supplier dossiers.</div>
      </div>
    </div>

    <!-- PSI Alerts & Sensing -->
    <div id="psi-alerts" class="psi-sub" style="display:none;">
      <div id="psi-alerts-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view alerts.</div>
      </div>
    </div>

    <!-- PSI Risk Register -->
    <div id="psi-register" class="psi-sub" style="display:none;">
      <div id="psi-register-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view risk register.</div>
      </div>
    </div>

    <!-- PSI Analyst Feedback -->
    <div id="psi-feedback" class="psi-sub" style="display:none;">
      <div id="psi-feedback-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view analyst feedback.</div>
      </div>
    </div>
```

- [ ] **Step 3: Wire new tabs into onGlobalMineralChange()**

In the `onGlobalMineralChange()` function, add after the `psi-taxonomy` line:

```javascript
  if (tabId === 'psi-forecasting') onForecastingMineralChange();
  if (tabId === 'psi-bom') onBomMineralChange();
  if (tabId === 'psi-dossier') onDossierMineralChange();
  if (tabId === 'psi-alerts') onAlertsMineralChange();
  if (tabId === 'psi-register') onRegisterMineralChange();
  if (tabId === 'psi-feedback') onFeedbackMineralChange();
```

- [ ] **Step 4: Wire new tabs into switchPsiTab()**

In the `switchPsiTab()` function, inside the `if (mineral)` block, add after the `psi-taxonomy` line:

```javascript
    if (btn.dataset.psiTab === 'psi-forecasting') onForecastingMineralChange();
    if (btn.dataset.psiTab === 'psi-bom') onBomMineralChange();
    if (btn.dataset.psiTab === 'psi-dossier') onDossierMineralChange();
    if (btn.dataset.psiTab === 'psi-alerts') onAlertsMineralChange();
    if (btn.dataset.psiTab === 'psi-register') onRegisterMineralChange();
    if (btn.dataset.psiTab === 'psi-feedback') onFeedbackMineralChange();
```

- [ ] **Step 5: Add 6 stub mineral-change functions**

Add after the existing `onOverviewMineralChange` / `renderMineralOverview` functions (around line ~7870), before `async function loadPsiGraph()`:

```javascript
// ── New Sub-Tab Mineral Change Stubs ──

async function onForecastingMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-forecasting-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view forecasting data.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderForecasting(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Forecasting data not yet available for ' + esc(mineral) + '</div>'; }
}
function renderForecasting(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Forecasting placeholder</div>'; }

async function onBomMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-bom-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view BOM explosion.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderBomExplorer(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">BOM data not yet available for ' + esc(mineral) + '</div>'; }
}
function renderBomExplorer(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">BOM Explorer placeholder</div>'; }

async function onDossierMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-dossier-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view supplier dossiers.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderDossier(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Dossier data not yet available for ' + esc(mineral) + '</div>'; }
}
function renderDossier(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Supplier Dossier placeholder</div>'; }

async function onAlertsMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-alerts-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view alerts.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderAlertsSensing(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Alert data not yet available for ' + esc(mineral) + '</div>'; }
}
function renderAlertsSensing(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Alerts placeholder</div>'; }

async function onRegisterMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-register-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view risk register.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderRiskRegister(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Risk register not yet available for ' + esc(mineral) + '</div>'; }
}
function renderRiskRegister(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Risk Register placeholder</div>'; }

async function onFeedbackMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-feedback-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view analyst feedback.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    renderAnalystFeedback(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Analyst feedback not yet available for ' + esc(mineral) + '</div>'; }
}
function renderAnalystFeedback(m, container) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Analyst Feedback placeholder</div>'; }
```

- [ ] **Step 6: Verify tabs appear and switch correctly**

Run: `python -m src.main` and open http://localhost:8000
Expected: 12 sub-tabs visible. Clicking each shows its container. Cobalt selected by default.

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add 6 new Supply Chain sub-tab buttons and wiring"
```

---

### Task 3: Implement renderForecasting()

**Files:**
- Modify: `src/static/index.html` (replace `renderForecasting` stub)

- [ ] **Step 1: Replace the renderForecasting stub**

Find `function renderForecasting(m, container)` and replace the entire function with:

```javascript
function renderForecasting(m, container) {
  var f = m.forecasting;
  if (!f) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Forecasting data not yet available for ' + esc(m.name) + '</div>'; return; }
  var suf = m.sufficiency || {};
  var scenario0 = (suf.scenarios || [])[0] || {};
  var html = '';

  // Stat cards
  html += '<div style="display:grid; grid-template-columns:repeat(4, 1fr); gap:10px; margin-bottom:14px;">';
  var pf = f.price_forecast || {};
  var lt = f.lead_time || {};
  var topInsol = (f.insolvency_risks || [])[0] || {};
  var stats = [
    {label:'Price Forecast', value:(pf.direction==='up'?'+':'-')+pf.pct_change+'%', sub:pf.period||'', color:pf.direction==='up'?'var(--accent2)':'var(--accent3)'},
    {label:'Lead Time Risk', value:'+'+lt.days+' days', sub:lt.period||'', color:'var(--accent4)'},
    {label:'Supplier Insolvency', value:topInsol.probability_pct+'%', sub:esc(topInsol.supplier||'').split('(')[0], color:topInsol.probability_pct>25?'var(--accent2)':'var(--accent4)'},
    {label:'Supply Adequacy', value:(scenario0.ratio||'--')+'x', sub:'steady-state', color:(scenario0.ratio||0)>=1?'var(--accent3)':'var(--accent2)'},
  ];
  stats.forEach(function(s){
    html += '<div class="card" style="text-align:center; padding:16px; border-top:3px solid '+s.color+';">';
    html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.5px;">'+s.label+'</div>';
    html += '<div class="stat-num" style="font-size:28px; color:'+s.color+'; margin:4px 0;">'+s.value+'</div>';
    html += '<div style="font-size:10px; color:var(--text-dim);">'+s.sub+'</div>';
    html += '</div>';
  });
  html += '</div>';

  // Two columns: chart + signals
  html += '<div style="display:grid; grid-template-columns:1.2fr 1fr; gap:14px; margin-bottom:14px;">';

  // Price chart
  html += '<div class="card" style="padding:18px;">';
  html += '<h3 style="margin-bottom:12px;">' + esc(m.name) + ' Price Forecast (USD/lb)</h3>';
  var prices = f.price_history || [];
  if (prices.length > 0) {
    var maxP = Math.max.apply(null, prices.map(function(p){return p.usd_lb;}));
    html += '<div style="display:flex; align-items:flex-end; gap:3px; height:180px; padding:0 4px;">';
    prices.forEach(function(p){
      var h = Math.round((p.usd_lb / maxP) * 100);
      var isForecast = p.type === 'forecast';
      var bg = isForecast ? 'rgba(245,158,11,0.15); border:1px dashed var(--accent4)' : 'var(--accent); opacity:0.7';
      html += '<div style="flex:1; height:'+h+'%; background:'+bg+'; border-radius:3px 3px 0 0; position:relative;" title="'+esc(p.quarter)+': $'+p.usd_lb+'/lb">';
      html += '<div style="position:absolute; top:-16px; left:50%; transform:translateX(-50%); font-size:9px; color:var(--text-dim); white-space:nowrap;">'+p.usd_lb+'</div>';
      html += '</div>';
    });
    html += '</div>';
    html += '<div style="display:flex; justify-content:space-between; margin-top:4px; font-size:9px; color:var(--text-dim);">';
    prices.forEach(function(p){ html += '<span>'+esc(p.quarter)+'</span>'; });
    html += '</div>';
    html += '<div style="display:flex; gap:16px; margin-top:8px; font-size:10px; color:var(--text-dim);">';
    html += '<span><span style="display:inline-block;width:10px;height:10px;background:var(--accent);opacity:0.7;border-radius:2px;margin-right:4px;vertical-align:middle;"></span>Historical</span>';
    html += '<span><span style="display:inline-block;width:10px;height:10px;border:1px dashed var(--accent4);border-radius:2px;margin-right:4px;vertical-align:middle;"></span>Forecast</span>';
    html += '</div>';
  }
  html += '</div>';

  // Signals
  html += '<div class="card" style="padding:18px;">';
  html += '<h3 style="margin-bottom:12px;">Forecast Signals</h3>';
  (f.signals || []).forEach(function(s){
    var dot = s.severity === 'critical' ? 'var(--accent2)' : s.severity === 'high' ? 'var(--accent4)' : s.severity === 'medium' ? 'var(--accent)' : 'var(--accent3)';
    html += '<div style="padding:8px 0; border-bottom:1px solid var(--border); font-size:12px; color:var(--text);">';
    html += '<span style="color:'+dot+'; margin-right:6px;">&#9679;</span>' + esc(s.text);
    html += '</div>';
  });
  html += '</div>';

  html += '</div>';

  // Insolvency risks table
  if (f.insolvency_risks && f.insolvency_risks.length > 0) {
    html += '<div class="card" style="padding:18px;">';
    html += '<h3 style="margin-bottom:12px;">Supplier Insolvency Watch</h3>';
    f.insolvency_risks.forEach(function(r){
      var c = r.probability_pct > 30 ? 'var(--accent2)' : r.probability_pct > 15 ? 'var(--accent4)' : 'var(--accent3)';
      html += '<div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid var(--border);">';
      html += '<div><div style="font-weight:600; font-size:13px;">' + esc(r.supplier) + '</div>';
      html += '<div style="font-size:11px; color:var(--text-dim);">' + esc(r.reason) + '</div></div>';
      html += '<div style="text-align:right;"><div class="stat-num" style="font-size:22px; color:'+c+';">'+r.probability_pct+'%</div>';
      html += '<div style="font-size:10px; color:var(--text-dim);">'+esc(r.horizon)+'</div></div>';
      html += '</div>';
    });
    html += '</div>';
  }

  container.innerHTML = html;
}
```

- [ ] **Step 2: Verify in browser**

Reload http://localhost:8000, go to Supply Chain → Forecasting tab.
Expected: 4 stat cards, price chart with historical+forecast bars, signals list, insolvency table.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement Forecasting sub-tab render for Cobalt"
```

---

### Task 4: Implement renderBomExplorer()

**Files:**
- Modify: `src/static/index.html` (replace `renderBomExplorer` stub)

- [ ] **Step 1: Replace the renderBomExplorer stub**

```javascript
function renderBomExplorer(m, container) {
  if (!m.mining || m.mining.length === 0) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">BOM data not yet available for ' + esc(m.name) + '</div>'; return; }
  var html = '';
  var tierColors = {1:'var(--accent3)',2:'var(--accent5)',3:'var(--accent4)',4:'var(--accent)'};
  var tierLabels = {1:'Mining / Extraction',2:'Processing / Refining',3:'Components / Alloys',4:'Platforms'};
  var tierConf = {1:'99%',2:'85-95%',3:'70-85%',4:'60-75%'};

  html += '<div class="card" style="padding:18px; margin-bottom:14px; border-left:4px solid var(--accent);">';
  html += '<div style="display:flex; justify-content:space-between; align-items:center;">';
  html += '<h3>' + esc(m.name) + ' — Bill of Materials Explosion</h3>';
  html += '<div style="font-size:11px; color:var(--text-dim);">RFI Q3-4: Multi-Tier Item Illumination</div>';
  html += '</div></div>';

  html += '<div class="card" style="padding:18px;">';
  html += '<div style="font-family:var(--font-mono); font-size:12px; line-height:2.4; color:var(--text);">';

  // Tier 1: Mining
  html += '<div><span style="color:'+tierColors[1]+';">&#9679;</span> <strong style="color:'+tierColors[1]+';">' + esc(m.name) + ' (Raw Mineral)</strong> <span style="background:rgba(16,185,129,0.1); color:var(--accent3); padding:1px 6px; border-radius:3px; font-size:9px; margin-left:6px;">Confidence: '+tierConf[1]+'</span></div>';
  (m.mining || []).forEach(function(entry){
    html += '<div style="padding-left:24px;"><span style="color:var(--text-dim);">&#9500;&#9472;</span> ' + esc(entry.country) + ' <span style="color:var(--text-dim);">(' + entry.pct + '% share)</span></div>';
  });

  // Tier 2: Processing
  html += '<div style="padding-left:24px; margin-top:4px;"><span style="color:'+tierColors[2]+';">&#9679;</span> <strong style="color:'+tierColors[2]+';">Refined '+esc(m.name)+' Metal</strong> <span style="background:rgba(139,92,246,0.1); color:var(--accent5); padding:1px 6px; border-radius:3px; font-size:9px; margin-left:6px;">Confidence: '+tierConf[2]+'</span></div>';
  (m.processing || []).forEach(function(entry){
    html += '<div style="padding-left:48px;"><span style="color:var(--text-dim);">&#9500;&#9472;</span> ' + esc(entry.country) + ' <span style="color:var(--text-dim);">(' + entry.pct + '% share)</span></div>';
  });

  // Tier 3: Alloys/Components → Tier 4: Platforms
  var alloys = m.alloys || [];
  var demand = (m.sufficiency || {}).demand || [];
  if (alloys.length > 0) {
    alloys.forEach(function(alloy){
      var coPct = alloy.cobalt_pct || alloy.co_pct || 0;
      html += '<div style="padding-left:48px; margin-top:4px;"><span style="color:'+tierColors[3]+';">&#9679;</span> <strong style="color:'+tierColors[3]+';">' + esc(alloy.name) + '</strong> <span style="color:var(--text-dim);">— ' + coPct + '% Co, ' + esc(alloy.type || '') + '</span> <span style="background:rgba(245,158,11,0.1); color:var(--accent4); padding:1px 6px; border-radius:3px; font-size:9px; margin-left:6px;">Confidence: '+tierConf[3]+'</span></div>';
      // Find platforms using this alloy
      var linkedPlatforms = demand.filter(function(d){ return d.alloy === alloy.name; });
      linkedPlatforms.forEach(function(lp){
        html += '<div style="padding-left:72px;"><span style="color:'+tierColors[4]+';">&#9679;</span> ' + esc(lp.engine || '') + ' <span style="color:var(--text-dim);">&#8594;</span> <strong style="color:'+tierColors[4]+';">' + esc(lp.platform) + '</strong>';
        if (lp.fleet_size) html += ' <span style="color:var(--accent2); font-size:10px;">[' + lp.fleet_size + (lp.fleet_note ? '' : '') + ']</span>';
        html += '</div>';
      });
      // If no linked platforms through demand, show from alloy.use
      if (linkedPlatforms.length === 0 && alloy.use) {
        html += '<div style="padding-left:72px; color:var(--text-dim); font-size:11px;"><span style="color:'+tierColors[4]+';">&#9679;</span> ' + esc(alloy.use) + '</div>';
      }
    });
  } else {
    (m.components || []).forEach(function(comp){
      html += '<div style="padding-left:48px;"><span style="color:'+tierColors[3]+';">&#9679;</span> <strong style="color:'+tierColors[3]+';">' + esc(comp.name) + '</strong></div>';
    });
    (m.platforms || []).forEach(function(plat){
      html += '<div style="padding-left:72px;"><span style="color:'+tierColors[4]+';">&#9679;</span> <strong style="color:'+tierColors[4]+';">' + esc(plat.name) + '</strong></div>';
    });
  }

  html += '</div>';

  // Legend
  html += '<div style="margin-top:16px; padding-top:12px; border-top:1px solid var(--border); display:flex; gap:20px; flex-wrap:wrap;">';
  [1,2,3,4].forEach(function(t){
    html += '<span style="font-size:11px;"><span style="color:'+tierColors[t]+'; margin-right:4px;">&#9679;</span>Tier '+t+': '+tierLabels[t]+' <span style="color:var(--text-dim);">('+tierConf[t]+')</span></span>';
  });
  html += '</div>';
  html += '</div>';

  container.innerHTML = html;
}
```

- [ ] **Step 2: Verify in browser**

Expected: Indented tree from Cobalt → processing → 8 alloys → linked CAF platforms. Confidence badges per tier.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement BOM Explorer sub-tab render for Cobalt"
```

---

### Task 5: Implement renderDossier()

**Files:**
- Modify: `src/static/index.html` (replace `renderDossier` stub)

- [ ] **Step 1: Replace the renderDossier stub**

```javascript
function renderDossier(m, container) {
  var entities = (m.mines || []).concat(m.refineries || []);
  if (entities.length === 0) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Supplier dossier data not yet available for ' + esc(m.name) + '</div>'; return; }

  var html = '';
  // Supplier selector
  html += '<div class="card" style="padding:14px; margin-bottom:14px; display:flex; align-items:center; gap:12px;">';
  html += '<span style="font-size:12px; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.5px;">Entity:</span>';
  html += '<select id="dossier-entity-select" onchange="renderDossierEntity()" style="background:var(--bg); color:var(--accent); border:1px solid var(--border); padding:6px 12px; border-radius:6px; font-family:var(--font-body); font-size:12px; font-weight:600; flex:1; max-width:400px;">';
  entities.forEach(function(e, i){
    html += '<option value="'+i+'">' + esc(e.name) + ' (' + esc(e.country) + ')</option>';
  });
  html += '</select>';
  html += '<span style="font-size:11px; color:var(--text-dim);">' + entities.length + ' tracked entities</span>';
  html += '</div>';
  html += '<div id="dossier-entity-detail"></div>';

  container.innerHTML = html;

  // Store entities for later use and render first
  window._dossierEntities = entities;
  window._dossierMineral = m;
  renderDossierEntity();
}

function renderDossierEntity() {
  var select = document.getElementById('dossier-entity-select');
  var detail = document.getElementById('dossier-entity-detail');
  if (!select || !detail || !window._dossierEntities) return;
  var idx = parseInt(select.value);
  var e = window._dossierEntities[idx];
  if (!e) return;

  var d = e.dossier || {};
  var kpis = e.kpis || {};
  var flags = e.flags || [];
  var ts = e.taxonomy_scores || {};
  var html = '';

  // Header row: 3 cards
  html += '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:14px;">';

  // Entity info
  html += '<div class="card" style="padding:14px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">Entity</div>';
  html += '<div style="font-size:16px; font-weight:700; margin:4px 0;">' + esc(e.name) + '</div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">' + esc(e.owner || '') + ' — ' + esc(e.country) + '</div>';
  var fociScore = ts.foci ? ts.foci.score : 0;
  var fociColor = fociScore >= 80 ? 'var(--accent2)' : fociScore >= 50 ? 'var(--accent4)' : 'var(--accent3)';
  html += '<div style="margin-top:6px;"><span style="background:'+fociColor+'22; color:'+fociColor+'; padding:2px 8px; border-radius:4px; font-size:10px; font-weight:600;">FOCI: '+(ts.foci ? ts.foci.level.toUpperCase() : 'N/A')+'</span></div>';
  flags.forEach(function(f){ html += ' <span style="background:rgba(239,68,68,0.1); color:var(--accent2); padding:2px 6px; border-radius:3px; font-size:9px; margin-top:4px; display:inline-block;">'+esc(f)+'</span>'; });
  html += '</div>';

  // Financial health
  html += '<div class="card" style="padding:14px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">Financial Health</div>';
  if (d.z_score != null) {
    var zColor = d.z_score < 1.8 ? 'var(--accent2)' : d.z_score < 2.7 ? 'var(--accent4)' : 'var(--accent3)';
    html += '<div style="font-size:16px; font-weight:700; color:'+zColor+'; margin:4px 0;">Z-Score: '+d.z_score+'</div>';
    html += '<div style="font-size:11px; color:var(--text-dim);">Credit trend: '+(d.credit_trend||'N/A')+'</div>';
    html += '<div style="margin-top:6px;"><span style="background:rgba(245,158,11,0.1); color:var(--accent4); padding:2px 8px; border-radius:4px; font-size:10px;">INSOLVENCY: '+(d.insolvency_prob||0)+'%</span></div>';
  } else {
    html += '<div style="font-size:13px; color:var(--text-dim); margin-top:8px;">Financial data placeholder</div>';
  }
  html += '</div>';

  // Operations
  html += '<div class="card" style="padding:14px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">Operations</div>';
  if (e.production_t) html += '<div style="font-size:16px; font-weight:700; margin:4px 0;">' + e.production_t.toLocaleString() + 't/yr</div>';
  if (e.note) html += '<div style="font-size:11px; color:var(--text-dim);">' + esc(e.note) + '</div>';
  if (kpis.employees_est) html += '<div style="font-size:11px; color:var(--text-dim); margin-top:4px;">~' + kpis.employees_est.toLocaleString() + ' employees</div>';
  html += '</div>';
  html += '</div>';

  // Two columns: UBO + Intel
  html += '<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-bottom:14px;">';

  // UBO chain
  html += '<div class="card" style="padding:14px;">';
  html += '<h3 style="font-size:13px; margin-bottom:8px;">Ownership Chain (UBO)</h3>';
  if (d.ubo_chain && d.ubo_chain.length > 0) {
    html += '<div style="font-size:12px; color:var(--text); line-height:2;">';
    d.ubo_chain.forEach(function(u, i){
      var isLast = i === d.ubo_chain.length - 1;
      var color = isLast && (u.toLowerCase().includes('state') || u.toLowerCase().includes('prc')) ? 'var(--accent2)' : 'var(--text)';
      html += '<span style="color:'+color+';font-weight:'+(isLast?'700':'400')+';">'+esc(u)+'</span>';
      if (!isLast) html += ' <span style="color:var(--text-dim);">&#8594;</span> ';
    });
    html += '</div>';
  } else {
    html += '<div style="color:var(--text-dim); font-size:12px;">Ownership data not yet available</div>';
  }
  html += '</div>';

  // Recent intel
  html += '<div class="card" style="padding:14px;">';
  html += '<h3 style="font-size:13px; margin-bottom:8px;">Recent Intelligence</h3>';
  if (d.recent_intel && d.recent_intel.length > 0) {
    d.recent_intel.forEach(function(intel){
      var dot = intel.severity === 'critical' ? 'var(--accent2)' : intel.severity === 'high' ? 'var(--accent4)' : 'var(--accent3)';
      html += '<div style="padding:6px 0; border-bottom:1px solid var(--border); font-size:12px;">';
      html += '<span style="color:'+dot+'; margin-right:4px;">&#9679;</span>' + esc(intel.text);
      if (intel.date) html += ' <span style="color:var(--text-dim); font-size:10px;">(' + esc(intel.date) + ')</span>';
      html += '</div>';
    });
  } else {
    html += '<div style="color:var(--text-dim); font-size:12px;">No recent intelligence</div>';
  }
  html += '</div>';
  html += '</div>';

  // Contracts
  html += '<div class="card" style="padding:14px;">';
  html += '<h3 style="font-size:13px; margin-bottom:8px;">DND Contract Summary</h3>';
  if (d.contracts && d.contracts.length > 0) {
    html += '<table style="width:100%; font-size:11px; border-collapse:collapse;">';
    html += '<thead><tr style="color:var(--text-dim); text-transform:uppercase; font-size:10px; border-bottom:1px solid var(--border);"><th style="padding:6px; text-align:left;">ID</th><th style="padding:6px; text-align:left;">Description</th><th style="padding:6px; text-align:right;">Value (CAD)</th><th style="padding:6px; text-align:left;">Status</th><th style="padding:6px; text-align:left;">End Date</th></tr></thead><tbody>';
    d.contracts.forEach(function(c){
      html += '<tr style="border-bottom:1px solid var(--border);">';
      html += '<td style="padding:6px; color:var(--text-dim);">'+esc(c.id)+'</td>';
      html += '<td style="padding:6px;">'+esc(c.description)+'</td>';
      html += '<td style="padding:6px; text-align:right; font-family:var(--font-mono);">$'+(c.value_cad||0).toLocaleString()+'</td>';
      html += '<td style="padding:6px;"><span style="color:var(--accent3);">'+esc(c.status)+'</span></td>';
      html += '<td style="padding:6px; color:var(--text-dim);">'+esc(c.end_date)+'</td>';
      html += '</tr>';
    });
    html += '</tbody></table>';
  } else {
    html += '<div style="color:var(--text-dim); font-size:12px;">No direct DND contracts — supply is through OEM intermediaries</div>';
  }
  html += '</div>';

  detail.innerHTML = html;
}
```

- [ ] **Step 2: Verify in browser**

Expected: Dropdown with 18 entities (9 mines + 9 refineries). First entity (TFM) shows FOCI critical, Z-Score, UBO chain ending at PRC State Council, contracts table.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement Supplier Dossier sub-tab render for Cobalt"
```

---

### Task 6: Implement renderAlertsSensing()

**Files:**
- Modify: `src/static/index.html` (replace `renderAlertsSensing` stub)

- [ ] **Step 1: Replace the renderAlertsSensing stub**

```javascript
function renderAlertsSensing(m, container) {
  var alerts = m.watchtower_alerts || [];
  if (alerts.length === 0) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">No active alerts for ' + esc(m.name) + '</div>'; return; }

  var html = '';
  // Summary bar
  var counts = {5:0,4:0,3:0,2:0,1:0};
  alerts.forEach(function(a){ counts[a.severity] = (counts[a.severity]||0) + 1; });
  html += '<div class="card" style="padding:14px; margin-bottom:14px; display:flex; align-items:center; gap:12px; flex-wrap:wrap;">';
  html += '<h3 style="margin:0; font-size:14px;">' + esc(m.name) + ' — Active Alerts (Watchtower)</h3>';
  html += '<div style="display:flex; gap:6px; margin-left:auto;">';
  var sevLabels = {5:'Critical',4:'High',3:'Medium',2:'Low',1:'Info'};
  var sevColors = {5:'var(--accent2)',4:'#f97316',3:'var(--accent4)',2:'var(--accent)',1:'var(--accent3)'};
  [5,4,3,2,1].forEach(function(s){
    if (counts[s] > 0) html += '<span style="background:'+sevColors[s]+'22; color:'+sevColors[s]+'; padding:4px 10px; border-radius:4px; font-size:11px; font-weight:600;">'+counts[s]+' '+sevLabels[s]+'</span>';
  });
  html += '</div></div>';

  // Alert cards
  alerts.sort(function(a,b){ return b.severity - a.severity; });
  alerts.forEach(function(a){
    var c = sevColors[a.severity] || 'var(--text-dim)';
    html += '<div class="card" style="padding:14px; margin-bottom:8px; border-left:4px solid '+c+';">';
    html += '<div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">';
    html += '<div style="flex:1;">';
    html += '<div style="font-size:13px; font-weight:600;">' + esc(a.title) + '</div>';
    html += '<div style="font-size:11px; color:var(--text-dim); margin-top:4px;">Source: ' + esc((a.sources||[]).join(', ')) + ' — <strong>Confidence: '+a.confidence+'%</strong></div>';
    html += '<div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Category: <span style="color:'+c+';">' + esc(a.category) + '</span> — ' + esc(a.timestamp || '') + '</div>';
    html += '</div>';
    html += '<span style="background:'+c+'; color:#fff; padding:3px 10px; border-radius:4px; font-size:10px; font-weight:700; white-space:nowrap;">SEV '+a.severity+'</span>';
    html += '</div>';
    if (a.coa) {
      html += '<div style="margin-top:10px; padding:8px 10px; background:rgba(245,158,11,0.06); border:1px solid rgba(245,158,11,0.15); border-radius:6px; font-size:11px;">';
      html += '<strong style="color:var(--accent4);">Recommended COA:</strong> ' + esc(a.coa);
      html += '</div>';
    }
    html += '<div style="margin-top:8px; display:flex; gap:6px;">';
    ['Acknowledge','Assign','Escalate','Evidence Locker'].forEach(function(btn){
      html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="this.style.color=\'var(--accent)\'; this.style.borderColor=\'var(--accent)\';">'+btn+'</button>';
    });
    html += '</div>';
    html += '</div>';
  });

  container.innerHTML = html;
}
```

- [ ] **Step 2: Verify in browser**

Expected: 6 alert cards sorted by severity. Each has title, sources, confidence, category, recommended COA, action buttons.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement Alerts & Sensing sub-tab render for Cobalt"
```

---

### Task 7: Implement renderRiskRegister()

**Files:**
- Modify: `src/static/index.html` (replace `renderRiskRegister` stub)

- [ ] **Step 1: Replace the renderRiskRegister stub**

```javascript
function renderRiskRegister(m, container) {
  var rr = m.risk_register || [];
  if (rr.length === 0) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Risk register not yet available for ' + esc(m.name) + '</div>'; return; }

  var html = '';
  // Summary stats
  var byStatus = {open:0, in_progress:0, mitigated:0, closed:0};
  var overdue = 0;
  var now = new Date().toISOString().slice(0,10);
  rr.forEach(function(r){ byStatus[r.status] = (byStatus[r.status]||0) + 1; if (r.due_date < now && r.status !== 'closed' && r.status !== 'mitigated') overdue++; });

  html += '<div style="display:grid; grid-template-columns:repeat(5, 1fr); gap:10px; margin-bottom:14px;">';
  var summaryStats = [
    {label:'Total Risks', value:rr.length, color:'var(--accent)'},
    {label:'Open', value:byStatus.open, color:'var(--accent2)'},
    {label:'In Progress', value:byStatus.in_progress, color:'var(--accent4)'},
    {label:'Mitigated', value:byStatus.mitigated, color:'var(--accent3)'},
    {label:'Overdue', value:overdue, color:overdue>0?'var(--accent2)':'var(--accent3)'},
  ];
  summaryStats.forEach(function(s){
    html += '<div class="card" style="text-align:center; padding:12px;">';
    html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">'+s.label+'</div>';
    html += '<div class="stat-num" style="font-size:24px; color:'+s.color+';">'+s.value+'</div>';
    html += '</div>';
  });
  html += '</div>';

  // Table
  html += '<div class="card" style="padding:14px;">';
  html += '<h3 style="margin-bottom:12px;">' + esc(m.name) + ' Risk Register</h3>';
  html += '<table style="width:100%; font-size:11px; border-collapse:collapse;">';
  html += '<thead><tr style="color:var(--text-dim); text-transform:uppercase; font-size:10px; border-bottom:1px solid var(--border);">';
  html += '<th style="padding:8px; text-align:left;">ID</th><th style="padding:8px; text-align:left;">Risk</th><th style="padding:8px; text-align:left;">Category</th><th style="padding:8px; text-align:left;">Severity</th><th style="padding:8px; text-align:left;">Status</th><th style="padding:8px; text-align:left;">Owner</th><th style="padding:8px; text-align:left;">Due</th></tr></thead><tbody>';

  var sevColors = {critical:'var(--accent2)', high:'var(--accent4)', medium:'var(--accent)', low:'var(--accent3)'};
  var statusColors = {open:'var(--accent2)', in_progress:'var(--accent4)', mitigated:'var(--accent3)', closed:'var(--text-dim)'};
  var statusLabels = {open:'Open', in_progress:'In Progress', mitigated:'Mitigated', closed:'Closed'};

  rr.forEach(function(r, i){
    var isOverdue = r.due_date < now && r.status !== 'closed' && r.status !== 'mitigated';
    html += '<tr style="border-bottom:1px solid var(--border); cursor:pointer;" onclick="toggleRegisterRow('+i+')">';
    html += '<td style="padding:8px; color:var(--text-dim); font-family:var(--font-mono);">'+esc(r.id)+'</td>';
    html += '<td style="padding:8px; max-width:300px;">'+esc(r.risk)+'</td>';
    html += '<td style="padding:8px;"><span style="color:'+(sevColors[r.severity]||'var(--text)')+';">'+esc(r.category)+'</span></td>';
    html += '<td style="padding:8px;"><span style="background:'+(sevColors[r.severity]||'var(--text-dim)')+'33; color:'+(sevColors[r.severity]||'var(--text)')+'; padding:2px 8px; border-radius:3px; font-size:10px; font-weight:600;">'+esc(r.severity).toUpperCase()+'</span></td>';
    html += '<td style="padding:8px;"><span style="color:'+(statusColors[r.status]||'var(--text)')+';">'+esc(statusLabels[r.status]||r.status)+'</span></td>';
    html += '<td style="padding:8px;">'+esc(r.owner)+'</td>';
    html += '<td style="padding:8px;'+(isOverdue?' color:var(--accent2); font-weight:600;':'')+'">'+esc(r.due_date)+(isOverdue?' &#9888;':'')+'</td>';
    html += '</tr>';
    // Expandable detail row
    html += '<tr id="register-detail-'+i+'" style="display:none;"><td colspan="7" style="padding:12px 8px 12px 32px; background:var(--surface);">';
    if (r.coas && r.coas.length > 0) {
      html += '<div style="margin-bottom:8px;"><strong style="font-size:11px; color:var(--accent4);">Linked COAs:</strong></div>';
      r.coas.forEach(function(c){ html += '<div style="font-size:11px; padding:2px 0; color:var(--text);">&#8226; '+esc(c)+'</div>'; });
    }
    if (r.evidence && r.evidence.length > 0) {
      html += '<div style="margin-top:6px;"><strong style="font-size:11px; color:var(--accent);">Evidence:</strong></div>';
      r.evidence.forEach(function(ev){ html += '<div style="font-size:11px; padding:2px 0; color:var(--text-dim);">&#128196; '+esc(ev)+'</div>'; });
    }
    html += '</td></tr>';
  });
  html += '</tbody></table></div>';

  container.innerHTML = html;
}

function toggleRegisterRow(idx) {
  var row = document.getElementById('register-detail-' + idx);
  if (row) row.style.display = row.style.display === 'none' ? '' : 'none';
}
```

- [ ] **Step 2: Verify in browser**

Expected: 5 summary stat cards, 10-row table with expandable details showing COAs and evidence.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement Risk Register sub-tab render for Cobalt"
```

---

### Task 8: Implement renderAnalystFeedback()

**Files:**
- Modify: `src/static/index.html` (replace `renderAnalystFeedback` stub)

- [ ] **Step 1: Replace the renderAnalystFeedback stub**

```javascript
function renderAnalystFeedback(m, container) {
  var af = m.analyst_feedback;
  if (!af) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Analyst feedback not yet available for ' + esc(m.name) + '</div>'; return; }

  var html = '';
  // Stat cards
  html += '<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:14px;">';
  var accColor = af.accuracy >= 85 ? 'var(--accent3)' : af.accuracy >= 70 ? 'var(--accent4)' : 'var(--accent2)';
  var fpColor = af.fp_rate <= 15 ? 'var(--accent3)' : af.fp_rate <= 25 ? 'var(--accent4)' : 'var(--accent2)';
  html += '<div class="card" style="text-align:center; padding:16px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">Model Accuracy</div>';
  html += '<div class="stat-num" style="font-size:32px; color:'+accColor+';">'+af.accuracy+'%</div>';
  html += '<div style="font-size:10px; color:var(--text-dim);">last 90 days</div></div>';
  html += '<div class="card" style="text-align:center; padding:16px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">False Positive Rate</div>';
  html += '<div class="stat-num" style="font-size:32px; color:'+fpColor+';">'+af.fp_rate+'%</div>';
  html += '<div style="font-size:10px; color:var(--text-dim);">trending '+(af.fp_trend==='down'?'&#8595; down':'&#8593; up')+'</div></div>';
  html += '<div class="card" style="text-align:center; padding:16px;">';
  html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase;">Pending Review</div>';
  html += '<div class="stat-num" style="font-size:32px; color:var(--accent);">'+(af.pending||[]).length+'</div>';
  html += '<div style="font-size:10px; color:var(--text-dim);">awaiting analyst</div></div>';
  html += '</div>';

  // Pending adjudication
  html += '<div class="card" style="padding:18px; margin-bottom:14px;">';
  html += '<h3 style="margin-bottom:12px;">Pending Adjudication</h3>';
  (af.pending || []).forEach(function(p, i){
    html += '<div style="background:var(--surface); border-radius:6px; padding:12px; margin-bottom:8px; border-left:3px solid var(--accent);">';
    html += '<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">';
    html += '<div style="flex:1;">';
    html += '<div style="font-size:12px; color:var(--text);">"' + esc(p.text) + '"</div>';
    html += '<div style="font-size:10px; color:var(--text-dim); margin-top:2px;">Source: ' + esc(p.source) + ' — Confidence: '+p.confidence+'%</div>';
    html += '</div>';
    html += '<div style="display:flex; gap:6px;">';
    html += '<button style="background:rgba(16,185,129,0.15); color:var(--accent3); border:1px solid rgba(16,185,129,0.3); padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-family:var(--font-body); font-weight:600;" onclick="this.parentElement.parentElement.parentElement.style.opacity=\'0.4\'; this.textContent=\'Verified &#10003;\';">&#10003; Verified</button>';
    html += '<button style="background:rgba(239,68,68,0.15); color:var(--accent2); border:1px solid rgba(239,68,68,0.3); padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-family:var(--font-body); font-weight:600;" onclick="this.parentElement.parentElement.parentElement.style.opacity=\'0.4\'; this.textContent=\'Rejected &#10007;\';">&#10007; False Positive</button>';
    html += '</div></div></div>';
  });
  html += '</div>';

  // Two columns: threshold config + recent history
  html += '<div style="display:grid; grid-template-columns:1fr 1fr; gap:14px;">';

  // Threshold
  html += '<div class="card" style="padding:18px;">';
  html += '<h3 style="margin-bottom:12px;">Threshold Configuration</h3>';
  var th = af.threshold || {};
  html += '<div style="font-size:12px; line-height:2.2;">';
  html += '<div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border); padding:4px 0;"><span style="color:var(--text-dim);">Current Z-Score Threshold</span><span style="font-family:var(--font-mono); color:var(--accent);">'+( th.current_z||'--')+'</span></div>';
  html += '<div style="display:flex; justify-content:space-between; border-bottom:1px solid var(--border); padding:4px 0;"><span style="color:var(--text-dim);">RLHF-Adjusted Threshold</span><span style="font-family:var(--font-mono); color:var(--accent3);">'+(th.rlhf_adjusted||'--')+'</span></div>';
  html += '<div style="display:flex; justify-content:space-between; padding:4px 0;"><span style="color:var(--text-dim);">Last Retrain</span><span style="font-family:var(--font-mono); color:var(--text);">'+(th.last_retrain||'--')+'</span></div>';
  html += '</div>';
  html += '<div style="margin-top:10px; font-size:10px; color:var(--text-dim);">FP rate &gt;30% raises threshold automatically. &lt;10% lowers it. Manual override available.</div>';
  html += '</div>';

  // Recent feedback
  html += '<div class="card" style="padding:18px;">';
  html += '<h3 style="margin-bottom:12px;">Recent Feedback History</h3>';
  (af.recent || []).forEach(function(r){
    var vColor = r.verdict === 'verified' ? 'var(--accent3)' : 'var(--accent2)';
    var vLabel = r.verdict === 'verified' ? '&#10003; Verified' : '&#10007; False Positive';
    html += '<div style="display:flex; justify-content:space-between; align-items:center; padding:6px 0; border-bottom:1px solid var(--border); font-size:11px;">';
    html += '<div style="flex:1; color:var(--text);">' + esc(r.text) + '</div>';
    html += '<span style="color:'+vColor+'; font-size:10px; white-space:nowrap; margin:0 8px;">'+vLabel+'</span>';
    html += '<span style="color:var(--text-dim); font-size:10px; white-space:nowrap;">'+esc(r.analyst)+' ('+esc(r.date)+')</span>';
    html += '</div>';
  });
  html += '</div>';

  html += '</div>';

  container.innerHTML = html;
}
```

- [ ] **Step 2: Verify in browser**

Expected: 3 stat cards (87% accuracy, 18% FP, 4 pending). Adjudication queue with Verified/False Positive buttons. Threshold config and feedback history.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: implement Analyst Feedback sub-tab render for Cobalt"
```

---

### Task 9: Run full test suite and final verification

**Files:**
- No new files

- [ ] **Step 1: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: All tests pass (73+ existing + ~10 new = 83+)

- [ ] **Step 2: Start server and verify all 12 tabs**

Run: `python -m src.main`
Open http://localhost:8000, navigate to Supply Chain. Verify:
1. All 12 sub-tabs visible in single row
2. Cobalt selected by default
3. Each tab shows Cobalt-specific content
4. Switching minerals shows "not yet available" for non-Cobalt minerals
5. Switching back to Cobalt re-renders correctly

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete 6 new Supply Chain sub-tabs for Cobalt (Forecasting, BOM, Dossier, Alerts, Register, Feedback)"
```
