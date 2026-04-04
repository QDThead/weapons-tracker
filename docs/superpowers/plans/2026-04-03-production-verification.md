# Production Verification Sub-Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Verification" sub-tab (#13) under Supply Chain that overlays satellite signals (thermal FRP + NO2 ratio) against reported production capacity for all 18 cobalt facilities, computing a verification score to flag discrepancies.

**Architecture:** Frontend-only feature. Fetches existing `/globe/minerals/Cobalt` API (already returns thermal history, NO2 history, and production/capacity per facility). Renders a card grid with Chart.js overlay charts and computed verification scorecards. No new Python files, no new API endpoints.

**Tech Stack:** Chart.js (already loaded), existing PSI sub-tab system, `/globe/minerals/Cobalt` API.

---

### Task 1: Register Sub-Tab (HTML + JS Hooks)

**Files:**
- Modify: `src/static/index.html`

- [ ] **Step 1: Add sub-tab button**

Find the PSI sub-tab bar (line ~2063, the line with `psi-feedback` button). After the Analyst Feedback button and before the closing `</div>`, add:

```html
        <button class="tab psi-tab-btn" role="tab" aria-selected="false" data-psi-tab="psi-verification" onclick="switchPsiTab(this)">Verification</button>
```

- [ ] **Step 2: Add sub-tab panel div**

Find the Analyst Feedback panel div (line ~2477-2482). After its closing `</div>` and before the `</div>` that closes the Supply Chain page (the line `<!-- ════ DATA FEEDS PAGE ════ -->`), add:

```html
    <!-- PSI Production Verification -->
    <div id="psi-verification" class="psi-sub" style="display:none;">
      <div id="psi-verification-content">
        <div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view production verification.</div>
      </div>
    </div>
```

- [ ] **Step 3: Add translation entries**

Find `PSI_EN_TABS` (line ~2649). Add `'psi-verification':'Verification'` to the end of the object.
Find `PSI_FR_TABS` (line ~2648). Add `'psi-verification':'Vérification'` to the end of the object.

- [ ] **Step 4: Add mineral change hook**

Find `onGlobalMineralChange()` (line ~7322). Inside it, find the line `if (tabId === 'psi-feedback') onFeedbackMineralChange();` and add after it:

```javascript
  if (tabId === 'psi-verification') onVerificationMineralChange();
```

Find `switchPsiTab()` (line ~7346). Inside it, find the line `if (btn.dataset.psiTab === 'psi-feedback') onFeedbackMineralChange();` and add after it:

```javascript
    if (btn.dataset.psiTab === 'psi-verification') onVerificationMineralChange();
```

- [ ] **Step 5: Add stub rendering function**

At the end of the JavaScript section (before the closing `</script>` tag), add:

```javascript
/* ── Production Verification Sub-Tab ── */
async function onVerificationMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-verification-content');
  if (!mineral || mineral.toLowerCase() !== 'cobalt') {
    container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Production verification is currently available for Cobalt only.</div>';
    return;
  }
  container.innerHTML = '<div style="text-align:center; padding:40px; color:var(--text-dim);">Loading verification data...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/Cobalt');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    var m = await resp.json();
    renderVerificationTab(m, container);
  } catch (e) {
    container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Failed to load verification data: ' + esc(e.message) + '</div>';
  }
}

function renderVerificationTab(m, container) {
  container.innerHTML = '<div style="padding:20px; color:var(--text-dim);">Verification tab loaded — rendering coming next task.</div>';
}
```

- [ ] **Step 6: Verify the tab appears**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m src.main`

Open http://localhost:8000/dashboard → Supply Chain. Verify "Verification" tab appears in the sub-tab bar and clicking it shows the placeholder text.

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat(psi): register Verification sub-tab (#13) with stub rendering"
```

---

### Task 2: Verification Score Computation + Card Grid Rendering

**Files:**
- Modify: `src/static/index.html` (replace the `renderVerificationTab` stub from Task 1)

- [ ] **Step 1: Replace the stub `renderVerificationTab` function**

Find the line `function renderVerificationTab(m, container) {` and replace the entire function with:

```javascript
function computeVerificationScore(facility) {
  var thermal = facility.thermal || {};
  var no2 = facility.no2 || {};
  var thermalHistory = thermal.history || [];
  var no2History = no2.history || [];
  var capacity = facility.production_t || facility.capacity_t || 0;
  var note = (facility.note || '').toLowerCase();

  // Determine reported status
  var reportedStatus = 'operating';
  if (note.indexOf('paused') >= 0 || note.indexOf('suspended') >= 0 || note.indexOf('shut down') >= 0 || note.indexOf('closed') >= 0) {
    reportedStatus = 'paused';
  }
  if (capacity === 0) reportedStatus = 'unknown';

  // Count active days in last 30
  var thermalActiveDays = thermalHistory.filter(function(h) { return h.count > 0; }).length;
  var no2EmittingDays = no2History.filter(function(h) { return (h.ratio || 0) >= 2.0; }).length;
  var totalDays = Math.max(thermalHistory.length, no2History.length, 1);

  var satelliteActivityPct = Math.max(thermalActiveDays, no2EmittingDays) / totalDays;

  var score;
  if (reportedStatus === 'operating') {
    score = satelliteActivityPct * 100;
    if (thermalActiveDays > 0 && no2EmittingDays > 0) score = Math.min(100, score + 10);
  } else if (reportedStatus === 'paused') {
    score = (1 - satelliteActivityPct) * 100;
  } else {
    score = 50;
  }
  score = Math.round(Math.max(0, Math.min(100, score)));

  var verdict, verdictColor;
  if (score >= 80) { verdict = 'CONSISTENT'; verdictColor = '#6b9080'; }
  else if (score >= 50) { verdict = 'INCONCLUSIVE'; verdictColor = '#a89060'; }
  else { verdict = 'DISCREPANCY'; verdictColor = '#D80621'; }

  var verdictText;
  if (verdict === 'CONSISTENT') {
    verdictText = 'Satellite activity aligns with reported ' + reportedStatus + ' status.';
  } else if (verdict === 'INCONCLUSIVE') {
    verdictText = 'Partial satellite coverage \u2014 insufficient data for verification.';
  } else {
    if (reportedStatus === 'paused') {
      verdictText = 'WARNING: Satellite shows activity but facility reports paused.';
    } else {
      verdictText = 'WARNING: Satellite shows inactivity but facility reports operating.';
    }
  }

  return {
    score: score,
    verdict: verdict,
    verdictColor: verdictColor,
    verdictText: verdictText,
    reportedStatus: reportedStatus,
    thermalActiveDays: thermalActiveDays,
    no2EmittingDays: no2EmittingDays,
    totalDays: totalDays,
    capacity: capacity,
    figureType: facility.figure_type || '',
    figureSource: facility.figure_source || '',
    figureYear: facility.figure_year || '',
  };
}

function renderVerificationTab(m, container) {
  var facilities = (m.mines || []).concat(m.refineries || []);
  if (facilities.length === 0) {
    container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">No facility data available.</div>';
    return;
  }

  // Compute scores and attach
  facilities.forEach(function(f) { f._vScore = computeVerificationScore(f); });

  // Sort controls state
  var currentSort = 'score-asc';

  function sortFacilities(sortKey) {
    if (sortKey === 'score-asc') facilities.sort(function(a,b) { return a._vScore.score - b._vScore.score; });
    else if (sortKey === 'score-desc') facilities.sort(function(a,b) { return b._vScore.score - a._vScore.score; });
    else if (sortKey === 'name') facilities.sort(function(a,b) { return a.name.localeCompare(b.name); });
    else if (sortKey === 'country') facilities.sort(function(a,b) { return (a.country||'').localeCompare(b.country||''); });
    else if (sortKey === 'capacity') facilities.sort(function(a,b) { return (b._vScore.capacity||0) - (a._vScore.capacity||0); });
  }

  function renderGrid(filterVerdict) {
    var filtered = filterVerdict === 'all' ? facilities : facilities.filter(function(f) { return f._vScore.verdict === filterVerdict; });

    var html = '';
    // Header
    html += '<div style="margin-bottom:16px;">';
    html += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-muted); text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">SECTION 13</div>';
    html += '<h3 style="margin:0 0 8px 0;">Production Verification \u2014 Satellite vs Reported Output</h3>';
    html += '<div style="font-size:12px; color:var(--text-dim); margin-bottom:12px;">Cross-references FIRMS thermal + Sentinel-5P NO2 satellite signals against reported facility production capacity. Discrepancies may indicate unreported shutdowns, covert operations, or data integrity issues.</div>';
    html += '</div>';

    // Sort + filter controls
    html += '<div style="display:flex; gap:8px; align-items:center; margin-bottom:14px; flex-wrap:wrap;">';
    html += '<span style="font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">SORT:</span>';
    ['score-asc', 'score-desc', 'name', 'country', 'capacity'].forEach(function(key) {
      var labels = {'score-asc':'Score \u2191','score-desc':'Score \u2193','name':'Name','country':'Country','capacity':'Capacity'};
      var active = key === currentSort;
      html += '<button class="vf-sort-btn" data-sort="' + key + '" style="font-size:10px; font-family:var(--font-mono); padding:3px 8px; border:1px solid ' + (active ? 'var(--accent)' : 'var(--border)') + '; background:' + (active ? 'rgba(0,212,255,0.08)' : 'transparent') + '; color:' + (active ? 'var(--accent)' : 'var(--text-dim)') + '; cursor:pointer;">' + labels[key] + '</button>';
    });
    html += '<span style="margin-left:12px; font-size:10px; font-family:var(--font-mono); color:var(--text-muted);">FILTER:</span>';
    ['all', 'DISCREPANCY', 'INCONCLUSIVE', 'CONSISTENT'].forEach(function(key) {
      var fColors = {'all':'var(--text-dim)', 'DISCREPANCY':'#D80621', 'INCONCLUSIVE':'#a89060', 'CONSISTENT':'#6b9080'};
      var activeF = key === filterVerdict;
      html += '<button class="vf-filter-btn" data-filter="' + key + '" style="font-size:10px; font-family:var(--font-mono); padding:3px 8px; border:1px solid ' + (activeF ? fColors[key] : 'var(--border)') + '; background:' + (activeF ? fColors[key] + '18' : 'transparent') + '; color:' + fColors[key] + '; cursor:pointer;">' + (key === 'all' ? 'All' : key) + '</button>';
    });
    html += '<span style="margin-left:auto; font-size:11px; color:var(--text-dim);">' + filtered.length + ' / ' + facilities.length + ' facilities</span>';
    html += '</div>';

    // Card grid
    html += '<div style="display:grid; grid-template-columns:repeat(auto-fill, minmax(360px, 1fr)); gap:12px;">';
    filtered.forEach(function(f, idx) {
      var v = f._vScore;
      var isMine = f.production_t !== undefined;
      var capLabel = isMine ? 'Production' : 'Capacity';
      var capValue = v.capacity ? v.capacity.toLocaleString() + ' t/yr' : 'Unknown';
      var cardId = 'vf-card-' + idx;

      html += '<div class="card" style="padding:14px;">';
      // Header row
      html += '<div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">';
      html += '<div>';
      html += '<div style="font-family:var(--font-mono); font-size:12px; font-weight:700; color:var(--text);">' + esc(f.name) + '</div>';
      html += '<div style="font-size:10px; color:var(--text-dim);">' + esc(f.owner || '') + ' \u00b7 ' + esc(f.country || '') + '</div>';
      html += '</div>';
      html += '<span style="display:inline-block; padding:2px 8px; font-family:var(--font-mono); font-size:10px; font-weight:700; color:' + v.verdictColor + '; border:1px solid ' + v.verdictColor + '; background:' + v.verdictColor + '18;">' + v.verdict + '</span>';
      html += '</div>';

      // Chart canvas
      html += '<canvas id="' + cardId + '-chart" width="340" height="120" style="width:100%; height:120px; margin-bottom:8px;"></canvas>';

      // Capacity line
      html += '<div style="font-size:10px; color:var(--text-dim); margin-bottom:6px;">';
      html += '<span style="font-family:var(--font-mono);">' + capLabel + ':</span> ' + capValue;
      if (v.figureSource) html += ' <span style="color:var(--text-muted);">(' + esc(v.figureSource) + (v.figureYear ? ' ' + v.figureYear : '') + ')</span>';
      if (v.reportedStatus === 'paused') html += ' <span style="color:#D80621; font-weight:600;"> \u2014 REPORTED PAUSED</span>';
      html += '</div>';

      // Score bar
      html += '<div style="margin-bottom:6px;">';
      html += '<div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">';
      html += '<div style="flex:1; height:6px; background:rgba(255,255,255,0.06); position:relative;">';
      html += '<div style="position:absolute; left:0; top:0; height:100%; width:' + v.score + '%; background:' + v.verdictColor + ';"></div>';
      html += '</div>';
      html += '<span style="font-family:var(--font-mono); font-size:12px; font-weight:700; color:' + v.verdictColor + ';">' + v.score + '%</span>';
      html += '</div>';

      // Detail lines
      html += '<div style="font-size:10px; font-family:var(--font-mono); color:var(--text-dim);">';
      html += 'Thermal: ' + v.thermalActiveDays + '/' + v.totalDays + ' days ACTIVE';
      html += ' &nbsp;\u00b7&nbsp; NO2: ' + v.no2EmittingDays + '/' + v.totalDays + ' days EMITTING';
      html += '</div>';
      html += '</div>';

      // Verdict text
      html += '<div style="font-size:10px; color:' + v.verdictColor + '; padding:4px 6px; background:' + v.verdictColor + '0a; border-left:2px solid ' + v.verdictColor + ';">' + esc(v.verdictText) + '</div>';

      html += '</div>';
    });
    html += '</div>';

    container.innerHTML = html;

    // Attach sort/filter handlers
    container.querySelectorAll('.vf-sort-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        currentSort = btn.dataset.sort;
        sortFacilities(currentSort);
        var activeFilter = container.querySelector('.vf-filter-btn[style*="background:"]');
        var fv = 'all';
        container.querySelectorAll('.vf-filter-btn').forEach(function(fb) {
          if (fb.style.background && fb.style.background !== 'transparent') fv = fb.dataset.filter;
        });
        renderGrid(fv);
      });
    });
    container.querySelectorAll('.vf-filter-btn').forEach(function(btn) {
      btn.addEventListener('click', function() { renderGrid(btn.dataset.filter); });
    });

    // Render charts (deferred so canvases exist in DOM)
    setTimeout(function() {
      filtered.forEach(function(f, idx) {
        var cardId = 'vf-card-' + idx;
        renderVerificationChart(cardId + '-chart', f);
      });
    }, 50);
  }

  sortFacilities(currentSort);
  renderGrid('all');
}
```

- [ ] **Step 2: Verify the grid renders**

Start server, go to Supply Chain → Verification. Should see 18 facility cards with score bars and verdict badges. Charts will be empty placeholders until Task 3.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(psi): verification score computation + card grid with sort/filter"
```

---

### Task 3: Overlay Charts (Thermal + NO2 + Capacity Reference)

**Files:**
- Modify: `src/static/index.html` (add `renderVerificationChart` function)

- [ ] **Step 1: Add the chart rendering function**

Add this function right after `renderVerificationTab`:

```javascript
function renderVerificationChart(canvasId, facility) {
  var canvas = document.getElementById(canvasId);
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (canvas._chartInstance) canvas._chartInstance.destroy();

  var thermalHistory = (facility.thermal || {}).history || [];
  var no2History = (facility.no2 || {}).history || [];

  // Build unified date axis from both histories
  var dateSet = {};
  thermalHistory.forEach(function(h) { dateSet[h.date] = dateSet[h.date] || {}; dateSet[h.date].frp = h.total_frp_mw || 0; });
  no2History.forEach(function(h) { dateSet[h.date] = dateSet[h.date] || {}; dateSet[h.date].ratio = h.ratio || 0; });

  var dates = Object.keys(dateSet).sort();
  if (dates.length < 2) {
    ctx.fillStyle = '#4B5567';
    ctx.font = '11px JetBrains Mono';
    ctx.textAlign = 'center';
    ctx.fillText('Insufficient satellite history', canvas.width / 2, canvas.height / 2);
    return;
  }

  var frpData = dates.map(function(d) { return (dateSet[d].frp || 0); });
  var ratioData = dates.map(function(d) { return (dateSet[d].ratio || 0); });
  var labels = dates.map(function(d) { return d.slice(5); }); // MM-DD

  // Capacity reference: normalize to a visible level on the FRP axis
  var maxFrp = Math.max.apply(null, frpData.concat([1]));
  var capacity = facility.production_t || facility.capacity_t || 0;
  // Draw reference at 60% of max FRP axis height as a "expected" baseline
  var refLevel = capacity > 0 ? maxFrp * 0.6 : null;

  var datasets = [
    {
      label: 'Thermal FRP (MW)',
      data: frpData,
      backgroundColor: 'rgba(255,68,68,0.5)',
      borderColor: '#ff4444',
      borderWidth: 1,
      borderRadius: 2,
      barPercentage: 0.45,
      categoryPercentage: 0.8,
      yAxisID: 'y',
      order: 2,
    },
    {
      label: 'NO2 Ratio (\u00d7bg)',
      data: ratioData,
      backgroundColor: 'rgba(160,80,220,0.5)',
      borderColor: '#a050dc',
      borderWidth: 1,
      borderRadius: 2,
      barPercentage: 0.45,
      categoryPercentage: 0.8,
      yAxisID: 'y1',
      order: 2,
    },
  ];

  // Capacity reference line (annotation via dataset)
  if (refLevel !== null) {
    datasets.push({
      label: 'Rated: ' + capacity.toLocaleString() + ' t/yr',
      data: dates.map(function() { return refLevel; }),
      type: 'line',
      borderColor: 'rgba(255,255,255,0.3)',
      borderWidth: 1,
      borderDash: [6, 3],
      pointRadius: 0,
      fill: false,
      yAxisID: 'y',
      order: 1,
    });
  }

  canvas._chartInstance = new Chart(ctx, {
    type: 'bar',
    data: { labels: labels, datasets: datasets },
    options: {
      responsive: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: { font: { size: 8, family: 'JetBrains Mono' }, color: '#4B5567', boxWidth: 10, padding: 6 },
        },
        tooltip: {
          callbacks: {
            title: function(items) { return items[0].label; },
            label: function(c) {
              if (c.datasetIndex === 0) return c.parsed.y.toFixed(2) + ' MW FRP';
              if (c.datasetIndex === 1) return c.parsed.y.toFixed(1) + '\u00d7 background';
              return c.dataset.label;
            }
          }
        },
      },
      scales: {
        x: {
          display: true,
          ticks: { font: { size: 7, family: 'JetBrains Mono' }, color: '#4B5567', maxRotation: 45, maxTicksLimit: 10 },
          grid: { display: false },
        },
        y: {
          display: true,
          position: 'left',
          title: { display: true, text: 'FRP (MW)', font: { size: 8, family: 'JetBrains Mono' }, color: '#ff4444' },
          beginAtZero: true,
          ticks: { font: { size: 8 }, color: '#4B5567', maxTicksLimit: 4 },
          grid: { color: 'rgba(255,255,255,0.04)' },
        },
        y1: {
          display: true,
          position: 'right',
          title: { display: true, text: 'NO2 (\u00d7bg)', font: { size: 8, family: 'JetBrains Mono' }, color: '#a050dc' },
          beginAtZero: true,
          ticks: { font: { size: 8 }, color: '#4B5567', maxTicksLimit: 4 },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
}
```

- [ ] **Step 2: Verify charts render**

Start server, go to Supply Chain → Verification. Each card should now have a bar chart with red thermal bars (left Y axis) and purple NO2 bars (right Y axis). Facilities with capacity should show a white dashed reference line.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(psi): overlay charts with thermal FRP + NO2 ratio + capacity reference"
```

---

### Task 4: Documentation Updates

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Add to the Intelligence Features table (after the Satellite NO2 Verification row):

```
| **Production Verification** | index.html (client-side) | Verification sub-tab (#13) cross-referencing FIRMS thermal + Sentinel-5P NO2 satellite signals against reported facility production capacity. 18 cobalt facilities in card grid with overlay charts (30-day thermal FRP + NO2 ratio + capacity reference line). Verification score (0-100%) with CONSISTENT/INCONCLUSIVE/DISCREPANCY verdicts. Sort by score/name/country/capacity, filter by verdict. |
```

Update the Dashboard UI table — change Supply Chain tab description from "12 sub-tabs" to "13 sub-tabs" and add "Production Verification" to the list.

Update Next Steps if the verification sub-tab was mentioned.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Production Verification sub-tab to CLAUDE.md"
```

---

### Task 5: Visual Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Start server and test**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m src.main`

Open http://localhost:8000/dashboard → Supply Chain → Verification.

Verify:
1. 18 facility cards render in a grid
2. Default sort is Score ascending (discrepancies first)
3. Sort buttons work (Score/Name/Country/Capacity)
4. Filter buttons work (All/DISCREPANCY/INCONCLUSIVE/CONSISTENT)
5. Each card has: facility name, owner, country, verdict badge, overlay chart, capacity line, score bar, detail lines, verdict text
6. Charts show red thermal bars + purple NO2 bars + white dashed capacity line
7. Moa JV shows "REPORTED PAUSED" label
8. Cards with fallback data (no satellite key) show reasonable scores from seed data
9. No console errors

- [ ] **Step 2: Run full test suite**

Run: `cd "C:\Users\William Dennis\weapons-tracker" && python -m pytest tests/ --ignore=tests/adversarial -q --tb=no`

Expected: 364 passed (no new tests — frontend-only feature, all data already tested).

- [ ] **Step 3: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "feat: Production Verification sub-tab — complete"
```
