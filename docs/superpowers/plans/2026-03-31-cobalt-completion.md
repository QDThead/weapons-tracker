# Cobalt Feature Completion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every Cobalt feature in the Supply Chain tab fully functional — zero stubs, zero placeholder buttons, all tests passing.

**Architecture:** Six independent fixes. The persistence bug is backend-only. COA sorting is frontend-only. Analyst Feedback wires buttons to existing `POST /ml/feedback`. Alert and Risk Register buttons get client-side state handlers with visual feedback. One requirements.txt addition.

**Tech Stack:** Python (SQLAlchemy, FastAPI), vanilla JS (index.html), pytest

---

### Task 1: Fix `test_resolved_action_not_reopened` persistence bug

**Files:**
- Modify: `src/storage/persistence.py:716-722`
- Test: `tests/test_mitigation.py:61-93`

**Root cause:** When the upsert creates a new `MitigationAction` for a resolved entity, it relies on the SQLAlchemy Column `default="open"`. The default is applied at flush time but the session identity map may return stale state. Fix: explicitly set `status="open"` in the constructor.

- [ ] **Step 1: Run the failing test to confirm the failure**

Run: `python -m pytest tests/test_mitigation.py::test_resolved_action_not_reopened -v`
Expected: FAIL — `assert sum(1 for r in all_rows if r.status == "open") == 1` → `0 == 1`

- [ ] **Step 2: Fix the upsert to explicitly set status**

In `src/storage/persistence.py`, change the `else` branch of `upsert_mitigation_action` (line 716-722):

```python
        else:
            existing = MitigationAction(
                risk_source=risk_source,
                risk_entity=risk_entity,
                risk_dimension=risk_dimension,
                status="open",
                **kwargs,
            )
            self.session.add(existing)
```

The only change is adding `status="open",` before `**kwargs`. This ensures the new row always starts as "open" regardless of SQLAlchemy default behavior.

- [ ] **Step 3: Run the test to verify it passes**

Run: `python -m pytest tests/test_mitigation.py -v`
Expected: ALL PASS (including `test_resolved_action_not_reopened`)

- [ ] **Step 4: Run full test suite to confirm no regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 196 passed (the previously-failing test now passes)

- [ ] **Step 5: Commit**

```bash
git add src/storage/persistence.py
git commit -m "fix: explicitly set status='open' in upsert_mitigation_action for resolved entities"
```

---

### Task 2: Wire COA table sorting in scenario comparison drawer

**Files:**
- Modify: `src/static/index.html:9802-9835` (the `openCOADrawer` function)

The current `openCOADrawer` builds `allCOAs` as a local variable and renders a static table. We need to: (a) store `allCOAs` at module scope, (b) extract the table-rendering into a `renderCOATable` helper, (c) add click handlers on `<th>` elements that sort and re-render.

- [ ] **Step 1: Replace the `openCOADrawer` and add sorting functions**

Replace lines 9802-9835 (from `function openCOADrawer()` through the line before `function closeCOADrawer()`) with:

```javascript
var _coaDrawerData = [];
var _coaSortCol = 'priority';
var _coaSortAsc = true;

function openCOADrawer() {
  var drawer = document.getElementById('scenario-coa-drawer');
  drawer.style.display = '';
  _coaDrawerData = [];
  scenarioHistory.forEach(function(run) {
    (run.data.coa || []).forEach(function(coa) {
      var existing = _coaDrawerData.find(function(c) { return c.id === coa.id && c.action === coa.action; });
      if (existing) { if (existing.triggered_by.indexOf(run.name) < 0) existing.triggered_by.push(run.name); }
      else { _coaDrawerData.push({id:coa.id, action:coa.action, triggered_by:[run.name], priority:coa.priority, cost_estimate:coa.cost_estimate, risk_reduction_pts:coa.risk_reduction_pts, timeline_months:coa.timeline_months, affected_platforms:coa.affected_platforms||[]}); }
    });
  });
  _coaSortCol = 'priority';
  _coaSortAsc = true;
  renderCOATable();
}

function renderCOATable() {
  var tableEl = document.getElementById('scenario-coa-table');
  var cols = [
    {key:'id', label:'ID'},
    {key:'action', label:'Action'},
    {key:'triggered_by', label:'Triggered By'},
    {key:'priority', label:'Priority'},
    {key:'cost_estimate', label:'Cost'},
    {key:'risk_reduction_pts', label:'Risk Reduction'},
    {key:'timeline_months', label:'Timeline'},
    {key:'affected_platforms', label:'Platforms'}
  ];
  var prioOrder = {critical:0, high:1, medium:2, low:3};
  var sorted = _coaDrawerData.slice().sort(function(a, b) {
    var va = a[_coaSortCol], vb = b[_coaSortCol];
    if (_coaSortCol === 'priority') { va = prioOrder[va] !== undefined ? prioOrder[va] : 9; vb = prioOrder[vb] !== undefined ? prioOrder[vb] : 9; }
    else if (_coaSortCol === 'risk_reduction_pts' || _coaSortCol === 'timeline_months') { va = va || 0; vb = vb || 0; }
    else if (_coaSortCol === 'triggered_by' || _coaSortCol === 'affected_platforms') { va = (va || []).join(','); vb = (vb || []).join(','); }
    else { va = (va || '').toString().toLowerCase(); vb = (vb || '').toString().toLowerCase(); }
    if (va < vb) return _coaSortAsc ? -1 : 1;
    if (va > vb) return _coaSortAsc ? 1 : -1;
    return 0;
  });
  var html = '<table style="width:100%; border-collapse:collapse; font-size:11px;"><thead><tr>';
  cols.forEach(function(col) {
    var arrow = _coaSortCol === col.key ? (_coaSortAsc ? ' &#9650;' : ' &#9660;') : ' <span style="color:var(--border);">&#9650;</span>';
    html += '<th style="text-align:left; padding:6px 8px; border-bottom:1px solid var(--border); color:var(--text-dim); cursor:pointer; user-select:none; white-space:nowrap;" onclick="sortCOATable(\'' + col.key + '\')">' + col.label + arrow + '</th>';
  });
  html += '</tr></thead><tbody>';
  sorted.forEach(function(c) {
    var pColor = c.priority === 'critical' ? 'var(--accent2)' : c.priority === 'high' ? 'var(--accent4)' : 'var(--accent)';
    html += '<tr>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); font-family:var(--font-mono); color:var(--accent);">' + esc(c.id) + '</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); color:var(--text);">' + esc(c.action) + '</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); color:var(--text-dim);">' + c.triggered_by.map(esc).join(', ') + '</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); color:' + pColor + '; font-weight:600; text-transform:uppercase;">' + esc(c.priority) + '</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); font-family:var(--font-mono);">' + esc(c.cost_estimate || '') + '</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); font-family:var(--font-mono);">-' + (c.risk_reduction_pts || 0) + ' pts</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); font-family:var(--font-mono);">' + (c.timeline_months || 0) + ' mo</td>';
    html += '<td style="padding:6px 8px; border-bottom:1px solid var(--border); font-size:9px; color:var(--text-dim);">' + (c.affected_platforms || []).map(esc).join(', ') + '</td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  tableEl.innerHTML = html;
}

function sortCOATable(col) {
  if (_coaSortCol === col) { _coaSortAsc = !_coaSortAsc; }
  else { _coaSortCol = col; _coaSortAsc = true; }
  renderCOATable();
}
```

- [ ] **Step 2: Verify in browser**

Run: `python -m src.main` (or `! python -m src.main` from Claude Code prompt)
Navigate to Supply Chain → Scenario Sandbox → run a scenario → open COA drawer → click column headers.
Expected: table sorts by clicked column, arrow toggles direction.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: wire COA comparison table sorting with click-to-sort columns"
```

---

### Task 3: Wire Analyst Feedback buttons to POST /ml/feedback

**Files:**
- Modify: `src/static/index.html:8558-8560` (inside `renderAnalystFeedback`)

The current buttons only set `opacity: 0.4` and change text. We replace the inline `onclick` handlers to call `POST /ml/feedback` with the correct payload. The endpoint expects `{entity, assessment_type, verdict, notes}`.

Note: the `pending` items have fields `{text, source, confidence}`. The `verdict` values the backend uses (per `analyst_feedback.recent`) are `"true_positive"` and `"false_positive"`.

- [ ] **Step 1: Add the `submitFeedback` function before `renderAnalystFeedback`**

Insert just before `async function onFeedbackMineralChange()` (line 8528):

```javascript
async function submitFeedback(btn, entity, text, verdict) {
  btn.disabled = true;
  btn.style.opacity = '0.6';
  try {
    var resp = await fetch(API + '/ml/feedback', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({entity: entity, assessment_type: 'cobalt_risk', verdict: verdict, notes: text})
    });
    if (!resp.ok) throw new Error('Failed');
    var row = btn.closest('[data-feedback-row]');
    if (row) { row.style.opacity = '0.4'; row.querySelector('[data-feedback-status]').textContent = verdict === 'true_positive' ? 'Verified ✓' : 'Rejected ✗'; }
  } catch (e) {
    btn.disabled = false;
    btn.style.opacity = '1';
    btn.style.borderColor = 'var(--accent2)';
  }
}
```

- [ ] **Step 2: Update the pending item rendering to use `submitFeedback`**

Replace the pending item loop in `renderAnalystFeedback` (the block starting at line 8553 `(af.pending || []).forEach(function(p){` through line 8562 `});`):

```javascript
  (af.pending || []).forEach(function(p){
    html += '<div data-feedback-row style="background:var(--surface); border-radius:6px; padding:12px; margin-bottom:8px; border-left:3px solid var(--accent);">';
    html += '<div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;"><div style="flex:1;">';
    html += '<div style="font-size:12px; color:var(--text);">"' + esc(p.text) + '"</div>';
    html += '<div style="font-size:10px; color:var(--text-dim); margin-top:2px;">Source: ' + esc(p.source) + ' — Confidence: '+p.confidence+'%</div>';
    html += '<div data-feedback-status style="font-size:10px; color:var(--accent3); margin-top:2px; display:none;"></div></div>';
    html += '<div style="display:flex; gap:6px;">';
    html += '<button style="background:rgba(16,185,129,0.15); color:var(--accent3); border:1px solid rgba(16,185,129,0.3); padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-family:var(--font-body); font-weight:600;" onclick="submitFeedback(this,\'' + esc(m.name) + '\',\'' + esc(p.text).replace(/'/g, "\\'") + '\',\'true_positive\')">&#10003; Verified</button>';
    html += '<button style="background:rgba(239,68,68,0.15); color:var(--accent2); border:1px solid rgba(239,68,68,0.3); padding:6px 12px; border-radius:4px; font-size:11px; cursor:pointer; font-family:var(--font-body); font-weight:600;" onclick="submitFeedback(this,\'' + esc(m.name) + '\',\'' + esc(p.text).replace(/'/g, "\\'") + '\',\'false_positive\')">&#10007; False Positive</button>';
    html += '</div></div></div>';
  });
```

- [ ] **Step 3: Verify in browser**

Navigate to Supply Chain → Analyst Feedback → click "Verified" or "False Positive" on a pending item.
Expected: button disables, row fades, status text appears. Check Network tab: `POST /ml/feedback` returns 200.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: wire analyst feedback buttons to POST /ml/feedback endpoint"
```

---

### Task 4: Wire Alert action buttons (Acknowledge/Assign/Escalate/Evidence)

**Files:**
- Modify: `src/static/index.html:8455-8459` (inside `renderAlertsSensing`)

The four alert action buttons currently only change their border color on click. We make them functional:
- **Acknowledge:** visually marks alert as acknowledged (green border, check icon)
- **Assign:** prompts for analyst name, shows assignment
- **Escalate:** marks as escalated (red border, arrow icon)
- **Evidence Locker:** toggles display of sources/COA detail below the alert

- [ ] **Step 1: Add alert action handler functions**

Insert just before `async function onAlertsMineralChange()` (line 8416):

```javascript
function alertAcknowledge(btn) {
  var card = btn.closest('.card');
  btn.textContent = '✓ Acknowledged';
  btn.style.color = 'var(--accent3)';
  btn.style.borderColor = 'var(--accent3)';
  btn.disabled = true;
  card.style.borderLeftColor = 'var(--accent3)';
  card.dataset.acknowledged = 'true';
}
function alertAssign(btn) {
  var name = prompt('Assign to analyst:');
  if (!name) return;
  btn.textContent = '→ ' + name;
  btn.style.color = 'var(--accent)';
  btn.style.borderColor = 'var(--accent)';
  btn.disabled = true;
}
function alertEscalate(btn) {
  var card = btn.closest('.card');
  btn.textContent = '⬆ Escalated';
  btn.style.color = 'var(--accent2)';
  btn.style.borderColor = 'var(--accent2)';
  btn.style.background = 'rgba(239,68,68,0.15)';
  btn.disabled = true;
  card.style.borderLeftWidth = '6px';
}
function alertEvidence(btn) {
  var panel = btn.parentElement.nextElementSibling;
  if (panel && panel.dataset.evidencePanel) {
    panel.style.display = panel.style.display === 'none' ? '' : 'none';
    btn.style.color = panel.style.display === 'none' ? 'var(--text-dim)' : 'var(--accent)';
    btn.style.borderColor = panel.style.display === 'none' ? 'var(--border)' : 'var(--accent)';
  }
}
```

- [ ] **Step 2: Replace the alert button rendering and add evidence panel**

Replace the button rendering block (lines 8455-8459):

Old code:
```javascript
    html += '<div style="margin-top:8px; display:flex; gap:6px;">';
    ['Acknowledge','Assign','Escalate','Evidence Locker'].forEach(function(btn){
      html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="this.style.color=\'var(--accent)\'; this.style.borderColor=\'var(--accent)\';">'+btn+'</button>';
    });
    html += '</div></div>';
```

New code:
```javascript
    html += '<div style="margin-top:8px; display:flex; gap:6px;">';
    html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="alertAcknowledge(this)">Acknowledge</button>';
    html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="alertAssign(this)">Assign</button>';
    html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="alertEscalate(this)">Escalate</button>';
    html += '<button style="background:var(--surface); border:1px solid var(--border); color:var(--text-dim); padding:4px 10px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);" onclick="alertEvidence(this)">Evidence Locker</button>';
    html += '</div>';
    html += '<div data-evidence-panel style="display:none; margin-top:8px; padding:10px; background:var(--surface); border-radius:6px; border:1px solid var(--border); font-size:11px;">';
    html += '<div style="color:var(--text-dim); font-size:10px; text-transform:uppercase; margin-bottom:6px;">Evidence & Sources</div>';
    (a.sources || []).forEach(function(s){ html += '<div style="padding:2px 0; color:var(--text);">&#128196; ' + esc(s) + '</div>'; });
    if (a.coa) html += '<div style="margin-top:6px; color:var(--accent4);"><strong>COA:</strong> ' + esc(a.coa) + '</div>';
    html += '<div style="margin-top:4px; color:var(--text-dim);">Confidence: ' + a.confidence + '% — ' + esc(a.timestamp || '') + '</div>';
    html += '</div>';
    html += '</div>';
```

- [ ] **Step 3: Verify in browser**

Navigate to Supply Chain → Alerts & Sensing.
- Click "Acknowledge" → button shows "✓ Acknowledged", card border turns green
- Click "Assign" → prompt appears, button shows "→ [name]"
- Click "Escalate" → button shows "⬆ Escalated" in red
- Click "Evidence Locker" → evidence panel toggles open/closed below alert

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: wire alert action buttons with acknowledge, assign, escalate, evidence"
```

---

### Task 5: Wire Risk Register status buttons in expanded row detail

**Files:**
- Modify: `src/static/index.html:8508-8517` (inside `renderRiskRegister`, the expanded row detail)

The Risk Register currently shows linked COAs and evidence when a row is expanded. We add status transition buttons so analysts can update risk status.

- [ ] **Step 1: Add risk register status update handler**

Insert just after the `toggleRegisterRow` function (after line 8526):

```javascript
function updateRegisterStatus(btn, idx, newStatus) {
  btn.disabled = true;
  var statusColors = {open:'var(--accent2)',in_progress:'var(--accent4)',mitigated:'var(--accent3)',closed:'var(--text-dim)'};
  var statusLabels = {open:'Open',in_progress:'In Progress',mitigated:'Mitigated',closed:'Closed'};
  var row = btn.closest('tr').previousElementSibling;
  var statusCell = row.querySelectorAll('td')[4];
  if (statusCell) {
    statusCell.innerHTML = '<span style="color:' + (statusColors[newStatus]||'var(--text)') + ';">' + esc(statusLabels[newStatus]||newStatus) + '</span>';
  }
  var btnGroup = btn.parentElement;
  btnGroup.querySelectorAll('button').forEach(function(b){ b.disabled = false; b.style.opacity = '1'; });
  btn.disabled = true;
  btn.style.opacity = '0.5';
}
```

- [ ] **Step 2: Add status buttons to the expanded row detail**

Replace the expanded row rendering inside `renderRiskRegister` (lines 8508-8517):

Old code:
```javascript
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
```

New code:
```javascript
    html += '<tr id="register-detail-'+i+'" style="display:none;"><td colspan="7" style="padding:12px 8px 12px 32px; background:var(--surface);">';
    html += '<div style="display:flex; gap:6px; margin-bottom:10px; align-items:center;"><span style="font-size:10px; color:var(--text-dim); text-transform:uppercase; margin-right:4px;">Update Status:</span>';
    ['open','in_progress','mitigated','closed'].forEach(function(st){
      var stColors = {open:'var(--accent2)',in_progress:'var(--accent4)',mitigated:'var(--accent3)',closed:'var(--text-dim)'};
      var stLabels = {open:'Open',in_progress:'In Progress',mitigated:'Mitigated',closed:'Closed'};
      var isCurrent = r.status === st;
      html += '<button style="background:' + (isCurrent ? stColors[st]+'22' : 'var(--surface)') + '; border:1px solid ' + (isCurrent ? stColors[st] : 'var(--border)') + '; color:' + (isCurrent ? stColors[st] : 'var(--text-dim)') + '; padding:3px 8px; border-radius:4px; font-size:10px; cursor:pointer; font-family:var(--font-body);' + (isCurrent ? ' opacity:0.5;' : '') + '" onclick="updateRegisterStatus(this,'+i+',\''+st+'\')"' + (isCurrent ? ' disabled' : '') + '>'+stLabels[st]+'</button>';
    });
    html += '</div>';
    if (r.coas && r.coas.length > 0) {
      html += '<div style="margin-bottom:8px;"><strong style="font-size:11px; color:var(--accent4);">Linked COAs:</strong></div>';
      r.coas.forEach(function(c){ html += '<div style="font-size:11px; padding:2px 0; color:var(--text);">&#8226; '+esc(c)+'</div>'; });
    }
    if (r.evidence && r.evidence.length > 0) {
      html += '<div style="margin-top:6px;"><strong style="font-size:11px; color:var(--accent);">Evidence:</strong></div>';
      r.evidence.forEach(function(ev){ html += '<div style="font-size:11px; padding:2px 0; color:var(--text-dim);">&#128196; '+esc(ev)+'</div>'; });
    }
    html += '</td></tr>';
```

- [ ] **Step 3: Verify in browser**

Navigate to Supply Chain → Risk Register → click any risk row to expand → click a status button.
Expected: Status cell in the table row updates, clicked button becomes disabled/dimmed, other buttons remain active.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add status transition buttons to risk register expanded rows"
```

---

### Task 6: Add `requests` to requirements.txt

**Files:**
- Modify: `requirements.txt:42-43`

- [ ] **Step 1: Add `requests` to the Testing section**

After `pytest-asyncio>=0.23` (line 43), add:

```
requests>=2.31
```

- [ ] **Step 2: Install it**

Run: `pip install requests`
Expected: Already satisfied (or installs successfully)

- [ ] **Step 3: Verify adversarial tests collect and pass**

Run: `python -m pytest tests/test_scenario_adversarial.py -v --tb=short`
Expected: 85 passed

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "fix: add requests to requirements.txt for adversarial test suite"
```

---

### Verification: Full Test Suite

After all 6 tasks are complete:

- [ ] **Run full suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 196 passed, 0 failed

- [ ] **Final commit (if any accumulated changes)**

All tasks should already be committed individually.
