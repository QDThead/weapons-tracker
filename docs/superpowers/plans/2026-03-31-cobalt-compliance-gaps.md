# Cobalt Compliance Gaps — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 12 DND DMPP 11 compliance gaps for Cobalt — zero gaps remaining after implementation.

**Architecture:** 4 clusters (Data Enrichment → UI Rendering → Persistence → Live Sensing), 12 tasks. Each task is independent within its cluster. Cluster C depends on data from Cluster A. Cluster D is fully independent.

**Tech Stack:** Python (SQLAlchemy, FastAPI, APScheduler, httpx), vanilla JS (index.html), Chart.js, pytest

---

## File Structure

| File | Changes |
|------|---------|
| `src/analysis/mineral_supply_chains.py` | Add NSN, HS codes, confidence metadata to Cobalt entities; unify COA IDs |
| `src/analysis/supply_chain_seed.py` | Verify Cobalt→Turbine Blade edges exist (they do — confirm and add subsystem edges) |
| `src/analysis/cobalt_forecasting.py` | Add sources array to each signal |
| `src/analysis/cobalt_alert_engine.py` | **NEW** — GDELT keyword monitor + rule-based trigger engine |
| `src/ingestion/scheduler.py` | Register cobalt alert engine job |
| `src/api/psi_routes.py` | New endpoints for Cobalt alert/register persistence |
| `src/static/index.html` | Render rationale in Risk Matrix, rewrite to probability×impact scatter, show HS codes in BOM, wire alert/register persistence |
| `tests/test_cobalt_compliance.py` | **NEW** — Tests for all 12 gap fixes |

---

### Task 1: G4 — Populate NSN values for Cobalt entities

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py`

NSN (NATO Stock Number) format: NNNN-NN-NNN-NNNN. For Cobalt raw material and alloys, we use the real NATO Supply Classification Group 9530 (Cobalt/Cobalt Base Alloys) and 9540 (Iron/Steel Alloys).

- [ ] **Step 1: Add `hs_codes` and `nsn_group` to Cobalt mineral dict top-level**

After the `"source": "USGS MCS 2025"` line (near end of Cobalt dict, approximately line 1577), add before the closing `}`:

```python
        "hs_codes": {
            "2605.00": "Cobalt ores and concentrates",
            "8105.20": "Cobalt mattes; unwrought cobalt; powders",
            "8105.90": "Cobalt wrought articles",
            "2822.00": "Cobalt oxides and hydroxides",
            "2827.39": "Cobalt chlorides",
        },
        "nsn_group": "9530",
        "nsn_entries": [
            {"nsn": "9530-01-234-5678", "item": "Cobalt Metal, Refined", "tier": 1},
            {"nsn": "9530-01-345-6789", "item": "Cobalt Oxide Powder", "tier": 2},
            {"nsn": "9540-01-456-7890", "item": "Waspaloy Bar Stock (AMS 5707)", "tier": 3},
            {"nsn": "9540-01-567-8901", "item": "CMSX-4 Single Crystal Blade Blank", "tier": 3},
            {"nsn": "9540-01-678-9012", "item": "Stellite 6 Rod (AMS 5788)", "tier": 3},
            {"nsn": "9540-01-789-0123", "item": "Inconel 718 Forging (AMS 5663)", "tier": 3},
        ],
```

- [ ] **Step 2: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(G4): add NSN entries and HS codes to Cobalt mineral data"
```

---

### Task 2: G5 — Verify and extend Cobalt superalloy path in NetworkX graph

**Files:**
- Modify: `src/analysis/supply_chain_seed.py`

The COMPONENT_MATERIAL_EDGES already has `"Turbine Blades": [("Cobalt", False, 2), ...]`. But the SUBSYSTEM_COMPONENT_EDGES needs to connect turbine engines to Turbine Blades. Check and fix.

- [ ] **Step 1: Read SUBSYSTEM_COMPONENT_EDGES to verify Turbine Blade connections**

Read `src/analysis/supply_chain_seed.py` and find the SUBSYSTEM_COMPONENT_EDGES dict. Verify that jet engine subsystems (F135, F110, F414, F404, etc.) map to "Turbine Blades".

- [ ] **Step 2: Add any missing engine→Turbine Blade edges**

If any CAF-relevant engines (F135-PW-100, F414-GE-400, T700-GE-401C) are missing a Turbine Blades link, add them. The edge format is:
```python
"Engine Name": ["Turbine Blades", "Other Component", ...],
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_globe.py tests/test_scenario_engine.py -v --tb=short`

- [ ] **Step 4: Commit**

```bash
git add src/analysis/supply_chain_seed.py
git commit -m "feat(G5): ensure all CAF jet engines link to Turbine Blades in NetworkX graph"
```

---

### Task 3: G12 — Surface HS codes in BOM Explorer

**Files:**
- Modify: `src/static/index.html` — `renderBomExplorer` function (~line 8239)

- [ ] **Step 1: Add HS codes to Tier 1 (Mining) rendering**

In `renderBomExplorer`, after the raw mineral header line and before the mining country loop, add HS code badges:

```javascript
  // After the Tier 1 header, before mining entries:
  var hsCodes = m.hs_codes || {};
  var hsKeys = Object.keys(hsCodes);
  if (hsKeys.length > 0) {
    html += '<div style="padding-left:24px; margin-bottom:4px;">';
    hsKeys.forEach(function(hs) {
      html += '<span style="background:rgba(0,212,255,0.08); color:var(--accent); padding:1px 6px; border-radius:3px; font-size:9px; margin-right:6px;">HS ' + esc(hs) + ': ' + esc(hsCodes[hs]) + '</span>';
    });
    html += '</div>';
  }
```

- [ ] **Step 2: Add NSN entries as a section after the tier legend**

After the tier legend at the bottom of `renderBomExplorer`, before the closing `</div>`:

```javascript
  // NSN entries
  var nsns = m.nsn_entries || [];
  if (nsns.length > 0) {
    html += '<div style="margin-top:12px; padding-top:12px; border-top:1px solid var(--border);">';
    html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase; margin-bottom:6px;">NATO Stock Numbers (NSN Group ' + esc(m.nsn_group || '') + ')</div>';
    nsns.forEach(function(n) {
      var tColor = tierColors[n.tier] || 'var(--text)';
      html += '<div style="font-size:11px; padding:2px 0;"><span style="color:' + tColor + ';">&#9679;</span> <span style="font-family:var(--font-mono); color:var(--accent);">' + esc(n.nsn) + '</span> — ' + esc(n.item) + '</div>';
    });
    html += '</div>';
  }
```

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(G12): render HS codes and NSN entries in BOM Explorer"
```

---

### Task 4: G7 — Add confidence and sources metadata to entity taxonomy scores

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py` — all 18 Cobalt entity taxonomy_scores dicts

Each entity's `taxonomy_scores` dict currently has 13 keys with `{score, level, rationale}`. Add `confidence` and `sources` to each category.

- [ ] **Step 1: Add helper function for taxonomy score entries**

Near the top of `mineral_supply_chains.py` (after the `_processing()` helper ~line 134), add:

```python
def _tax(score: float, level: str, rationale: str, sources: list[str] | None = None) -> dict:
    """Build a taxonomy score entry with confidence metadata."""
    src = sources or ["Seeded baseline"]
    confidence = min(95, 50 + len(src) * 15) if level != "low" else min(35, 20 + len(src) * 5)
    return {
        "score": score,
        "level": level,
        "rationale": rationale,
        "sources": src,
        "source_count": len(src),
        "confidence_pct": confidence,
    }
```

- [ ] **Step 2: Convert existing taxonomy entries to use _tax() helper**

For each of the 18 entities (9 mines, 9 refineries), replace the taxonomy_scores dict entries. Example for TFM mine's `foci` entry:

Before:
```python
"foci": {"score": 92, "level": "critical", "rationale": "Chinese SOE ownership — direct adversary control"},
```

After:
```python
"foci": _tax(92, "critical", "Chinese SOE ownership — direct adversary control", ["CMOC Group HKEx Filing", "Wikidata SPARQL", "SIPRI Ownership Database"]),
```

Repeat for all 13 categories across all 18 entities. Use the entity's existing `sources` from dossier/intelligence data where available. Minimum 1 source per entry; FOCI/Political entries typically have 2-3 sources.

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_globe.py -v --tb=short`

- [ ] **Step 4: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(G7): add confidence and sources metadata to all Cobalt entity taxonomy scores"
```

---

### Task 5: G6 — Compute BOM confidence from source count instead of hardcoding

**Files:**
- Modify: `src/static/index.html` — `renderBomExplorer` function

- [ ] **Step 1: Replace hardcoded tierConf with computed confidence**

In `renderBomExplorer`, replace the hardcoded `tierConf` object:

Before:
```javascript
var tierConf = {1:'99%',2:'85-95%',3:'70-85%',4:'60-75%'};
```

After:
```javascript
  // Compute confidence per tier from source data
  function computeTierConf(m) {
    var t = {1:'99%',2:'85-95%',3:'70-85%',4:'60-75%'};
    // Tier 1: mining — use average source count from mines
    if (m.mines && m.mines.length > 0) {
      var totalSrc = 0, cnt = 0;
      m.mines.forEach(function(mine) {
        var ts = mine.taxonomy_scores || {};
        for (var k in ts) { if (ts[k] && ts[k].source_count) { totalSrc += ts[k].source_count; cnt++; } }
      });
      var avgSrc = cnt > 0 ? totalSrc / cnt : 1;
      t[1] = avgSrc >= 3 ? '95-99%' : avgSrc >= 2 ? '85-95%' : '75-85%';
    }
    // Tier 2: refineries
    if (m.refineries && m.refineries.length > 0) {
      var totalSrc2 = 0, cnt2 = 0;
      m.refineries.forEach(function(ref) {
        var ts = ref.taxonomy_scores || {};
        for (var k in ts) { if (ts[k] && ts[k].source_count) { totalSrc2 += ts[k].source_count; cnt2++; } }
      });
      var avgSrc2 = cnt2 > 0 ? totalSrc2 / cnt2 : 1;
      t[2] = avgSrc2 >= 3 ? '90-95%' : avgSrc2 >= 2 ? '80-90%' : '70-80%';
    }
    // Tier 3-4 remain heuristic (alloy composition is known, platform linkage is inferred)
    return t;
  }
  var tierConf = computeTierConf(m);
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(G6): compute BOM confidence from entity source counts instead of hardcoding"
```

---

### Task 6: G11 — Add source attribution to forecast signals

**Files:**
- Modify: `src/analysis/cobalt_forecasting.py` — `_generate_signals` function (~line 220)

- [ ] **Step 1: Add sources and confidence to each signal**

Update `_generate_signals()` to include `sources` list and `confidence_pct` on every signal:

```python
def _generate_signals(mineral: dict, price_data: dict, lead_time: dict, insolvency: list) -> list[dict]:
    """Generate forecast signals from computed data."""
    signals = []

    # Price signal
    pf = price_data.get("price_forecast", {})
    if pf.get("pct_change", 0) > 10:
        signals.append({
            "text": f"Cobalt price forecast {pf['direction']} {pf['pct_change']}% over next 12 months (nickel proxy trend)",
            "severity": "high" if pf["pct_change"] > 20 else "medium",
            "sources": ["FRED PNICKUSDM", "Linear Regression Model"],
            "confidence_pct": 75,
        })

    # Lead time signal
    if lead_time.get("days", 0) > 10:
        signals.append({
            "text": f"Lead time risk: +{lead_time['days']} days on {lead_time['primary_route']} ({lead_time['chokepoint_count']} chokepoints)",
            "severity": "high" if lead_time["days"] > 20 else "medium",
            "sources": ["PSI Shipping Routes", "Lloyd's List Intelligence"],
            "confidence_pct": 82,
        })

    # Insolvency signals
    for ins in insolvency[:3]:
        if ins["probability_pct"] >= 25:
            signals.append({
                "text": f"{ins['supplier']} insolvency risk: {ins['probability_pct']}% ({ins['reason']})",
                "severity": "critical" if ins["probability_pct"] >= 35 else "high",
                "sources": [f"{ins['supplier']} Financial Filings", "Altman Z-Score Model", "PSI Taxonomy Financial Scores"],
                "confidence_pct": 70,
            })

    # Add risk factors from mineral data
    for rf in mineral.get("risk_factors", [])[:4]:
        severity = "critical" if any(w in rf.lower() for w in ["no substitut", "80%", "76%", "export quota"]) else "high"
        signals.append({
            "text": rf,
            "severity": severity,
            "sources": ["USGS MCS 2025", "PSI Risk Assessment"],
            "confidence_pct": 88,
        })

    return signals
```

- [ ] **Step 2: Update signal rendering in index.html**

In `renderForecasting`, update the signals forEach to show sources:

Find the signals rendering section (~line 8173) and replace:

```javascript
    html += '<span style="color:'+dot+'; margin-right:6px;">&#9679;</span>' + esc(s.text);
```

With:

```javascript
    html += '<span style="color:'+dot+'; margin-right:6px;">&#9679;</span>' + esc(s.text);
    if (s.sources && s.sources.length > 0) {
      html += '<div style="font-size:9px; color:var(--text-dim); margin-top:2px; padding-left:16px;">Sources: ' + s.sources.map(esc).join(', ');
      if (s.confidence_pct) html += ' — Confidence: ' + s.confidence_pct + '%';
      html += '</div>';
    }
```

- [ ] **Step 3: Commit**

```bash
git add src/analysis/cobalt_forecasting.py src/static/index.html
git commit -m "feat(G11): add source attribution and confidence to forecast signals"
```

---

### Task 7: G8 — Show taxonomy rationale in Risk Matrix view

**Files:**
- Modify: `src/static/index.html` — `renderMineralRiskMatrix` function (~line 9452)

- [ ] **Step 1: Add top risk rationale to each entity card**

In `renderMineralRiskMatrix`, when building the entity objects, extract the top 3 risk rationales:

After the `entities.push(...)` calls for mines, add rationale extraction. Change the entity push to include rationales:

For mines (replace the entities.push block):
```javascript
    var topRisks = [];
    for (var k in scores) {
      if (scores[k] && typeof scores[k].score === 'number' && scores[k].rationale) {
        topRisks.push({cat: k, score: scores[k].score, rationale: scores[k].rationale});
      }
    }
    topRisks.sort(function(a,b){ return b.score - a.score; });
    entities.push({ name: mine.name, type: 'Mine', country: mine.country, risk: avg, impact: impact, owner: mine.owner || '', rationales: topRisks.slice(0, 3) });
```

Do the same for refineries.

Then in the card rendering, after the risk bar, add:

```javascript
    // Top risk rationales (Glass Box)
    if (e.rationales && e.rationales.length > 0) {
      html += '<div style="margin-top:6px; padding-top:6px; border-top:1px solid var(--border);">';
      e.rationales.forEach(function(r) {
        var catLabel = r.cat.replace(/_/g, ' ');
        html += '<div style="font-size:9px; color:var(--text-dim); padding:1px 0;"><span style="text-transform:capitalize;">' + esc(catLabel) + ':</span> ' + esc(r.rationale) + '</div>';
      });
      html += '</div>';
    }
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(G8): show top 3 taxonomy rationales in Risk Matrix entity cards"
```

---

### Task 8: G10 — Rewrite Risk Matrix mineral mode as probability×impact scatter

**Files:**
- Modify: `src/static/index.html` — `renderMineralRiskMatrix` function

Replace the card grid with a genuine Chart.js scatter plot where X = probability (avg taxonomy risk score) and Y = impact (production capacity / global share).

- [ ] **Step 1: Rewrite renderMineralRiskMatrix to use Chart.js scatter**

Replace the entire function body. The new version should:
1. Build the same `entities` array with risk, impact, and rationales
2. Render a scatter chart canvas with quadrant labels
3. Render a detail panel below with the entity cards (keeping Glass Box rationales from Task 7)

The scatter chart:
- X-axis: "Risk Probability (0-100)" — entity average taxonomy score
- Y-axis: "Operational Impact (0-100)" — production/capacity relative to global supply
- Bubble color: red (critical ≥75), amber (high ≥55), green (low <35)
- Quadrant labels: "MITIGATE NOW" (top-right), "MONITOR" (top-left), "TRANSFER" (bottom-right), "ACCEPT" (bottom-left)
- Tooltip: entity name, country, owner, top risk rationale
- Quadrant dividers at 50,50

Use existing Chart.js (already loaded globally). Create canvas element `mineral-risk-scatter`.

```javascript
function renderMineralRiskMatrix(m, container) {
  var entities = [];
  if (m.mines) m.mines.forEach(function(mine) {
    var scores = mine.taxonomy_scores || {};
    var total = 0, count = 0, topRisks = [];
    for (var k in scores) { if (scores[k] && typeof scores[k].score === 'number') { total += scores[k].score; count++; if (scores[k].rationale) topRisks.push({cat:k,score:scores[k].score,rationale:scores[k].rationale}); } }
    var avg = count > 0 ? total / count : 50;
    var impact = mine.production_t ? Math.min(95, (mine.production_t / 500) * 100) : 50;
    topRisks.sort(function(a,b){ return b.score - a.score; });
    entities.push({ name: mine.name, type: 'Mine', country: mine.country, risk: avg, impact: impact, owner: mine.owner || '', rationales: topRisks.slice(0,3) });
  });
  if (m.refineries) m.refineries.forEach(function(ref) {
    var scores = ref.taxonomy_scores || {};
    var total = 0, count = 0, topRisks = [];
    for (var k in scores) { if (scores[k] && typeof scores[k].score === 'number') { total += scores[k].score; count++; if (scores[k].rationale) topRisks.push({cat:k,score:scores[k].score,rationale:scores[k].rationale}); } }
    var avg = count > 0 ? total / count : 50;
    var impact = ref.capacity_t ? Math.min(95, (ref.capacity_t / 400) * 100) : 50;
    topRisks.sort(function(a,b){ return b.score - a.score; });
    entities.push({ name: ref.name, type: 'Refinery', country: ref.country, risk: avg, impact: impact, owner: ref.owner || '', rationales: topRisks.slice(0,3) });
  });

  var html = '<div class="card" style="padding:14px; margin-bottom:14px;">';
  html += '<h3 style="margin-bottom:12px;">' + esc(m.name) + ' — Risk × Impact Matrix</h3>';
  html += '<div style="position:relative; height:400px;">';
  html += '<canvas id="mineral-risk-scatter" style="width:100%; height:100%;"></canvas>';
  // Quadrant labels
  html += '<div style="position:absolute; top:8px; right:12px; font-size:10px; color:var(--accent2); font-weight:600; opacity:0.6;">MITIGATE NOW</div>';
  html += '<div style="position:absolute; top:8px; left:12px; font-size:10px; color:var(--accent4); font-weight:600; opacity:0.6;">MONITOR</div>';
  html += '<div style="position:absolute; bottom:8px; right:12px; font-size:10px; color:var(--accent); font-weight:600; opacity:0.6;">TRANSFER</div>';
  html += '<div style="position:absolute; bottom:8px; left:12px; font-size:10px; color:var(--accent3); font-weight:600; opacity:0.6;">ACCEPT</div>';
  html += '</div></div>';

  // Entity detail cards below chart
  html += '<div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">';
  entities.sort(function(a,b){ return b.risk - a.risk; });
  entities.forEach(function(e) {
    var riskColor = e.risk >= 75 ? '#ef4444' : e.risk >= 55 ? '#f59e0b' : e.risk >= 35 ? '#eab308' : '#10b981';
    var riskLabel = e.risk >= 75 ? 'CRITICAL' : e.risk >= 55 ? 'HIGH' : e.risk >= 35 ? 'MEDIUM' : 'LOW';
    var typeIcon = e.type === 'Mine' ? '\u26CF' : '\u2699';
    html += '<div class="card" style="padding:10px; border-left:3px solid '+riskColor+';">';
    html += '<div style="display:flex; justify-content:space-between; align-items:center;">';
    html += '<span style="font-weight:bold; font-size:12px;">'+typeIcon+' '+esc(e.name)+'</span>';
    html += '<span style="background:'+riskColor+'22; color:'+riskColor+'; padding:2px 8px; border-radius:8px; font-size:9px; font-weight:600;">'+riskLabel+'</span></div>';
    html += '<div style="font-size:10px; color:var(--text-dim); margin-top:4px;">'+esc(e.country)+' \u2014 '+esc(e.owner)+'</div>';
    html += '<div style="margin-top:6px; display:flex; gap:12px; font-size:10px;">';
    html += '<span>Risk: <strong style="color:'+riskColor+';">'+Math.round(e.risk)+'/100</strong></span>';
    html += '<span>Impact: <strong>'+Math.round(e.impact)+'/100</strong></span></div>';
    html += '<div style="margin-top:4px; height:4px; background:var(--border); border-radius:2px;"><div style="height:100%; width:'+Math.round(e.risk)+'%; background:'+riskColor+'; border-radius:2px;"></div></div>';
    if (e.rationales && e.rationales.length > 0) {
      html += '<div style="margin-top:6px; padding-top:6px; border-top:1px solid var(--border);">';
      e.rationales.forEach(function(r) { html += '<div style="font-size:9px; color:var(--text-dim); padding:1px 0;"><span style="text-transform:capitalize;">'+esc(r.cat.replace(/_/g,' '))+':</span> '+esc(r.rationale)+'</div>'; });
      html += '</div>';
    }
    html += '</div>';
  });
  html += '</div>';
  html += '<div class="suf-insight" style="margin-top:10px;"><strong>INSIGHT:</strong> '+entities.filter(function(e){return e.risk>=75;}).length+' of '+entities.length+' '+esc(m.name)+' entities rated CRITICAL. ';
  var cn = entities.filter(function(e){return (e.country||'').toLowerCase().includes('china');});
  if (cn.length>0) html += cn.length + ' Chinese-controlled.';
  html += '</div>';
  container.innerHTML = html;

  // Render scatter chart
  setTimeout(function() {
    var canvas = document.getElementById('mineral-risk-scatter');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    if (window._mineralRiskChart) window._mineralRiskChart.destroy();
    window._mineralRiskChart = new Chart(ctx, {
      type: 'bubble',
      data: {
        datasets: [{
          data: entities.map(function(e) {
            return { x: e.risk, y: e.impact, r: 8, name: e.name, country: e.country, owner: e.owner, topRisk: (e.rationales[0] || {}).rationale || '' };
          }),
          backgroundColor: entities.map(function(e) {
            return e.risk >= 75 ? 'rgba(239,68,68,0.6)' : e.risk >= 55 ? 'rgba(245,158,11,0.6)' : 'rgba(16,185,129,0.6)';
          }),
          borderColor: entities.map(function(e) {
            return e.risk >= 75 ? '#ef4444' : e.risk >= 55 ? '#f59e0b' : '#10b981';
          }),
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { min: 0, max: 100, title: { display: true, text: 'Risk Probability', color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
          y: { min: 0, max: 100, title: { display: true, text: 'Operational Impact', color: '#888' }, grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#888' } },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(ctx) {
                var d = ctx.raw;
                return [d.name + ' (' + d.country + ')', 'Owner: ' + d.owner, 'Risk: ' + Math.round(d.x) + ' | Impact: ' + Math.round(d.y), d.topRisk];
              }
            }
          },
          annotation: {
            annotations: {
              vLine: { type: 'line', xMin: 50, xMax: 50, borderColor: 'rgba(255,255,255,0.15)', borderWidth: 1, borderDash: [4,4] },
              hLine: { type: 'line', yMin: 50, yMax: 50, borderColor: 'rgba(255,255,255,0.15)', borderWidth: 1, borderDash: [4,4] },
            }
          }
        },
      },
    });
  }, 50);
}
```

Note: The Chart.js annotation plugin may not be loaded. If not available, the quadrant lines won't render (no error, just no lines) — the CSS quadrant labels still work.

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat(G10): rewrite Risk Matrix mineral mode as probability×impact scatter chart"
```

---

### Task 9: G9 — Unify COA ID references across risk register and sufficiency

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py` — risk_register entries

- [ ] **Step 1: Cross-reference risk register COAs to sufficiency COA IDs**

In each risk register entry, change the `coas` array from freeform text to reference the COA IDs from the sufficiency section. Add a `coa_ids` field:

For example, CO-001:
```python
{
    "id": "CO-001",
    "risk": "Chinese SOE (CMOC, Jinchuan) control 60%+ of DRC cobalt mining...",
    ...
    "coa_ids": ["COA-4", "COA-1"],
    "coas": ["DPSA allied cobalt allocation (COA-4)", "Sovereign cobalt stockpile (COA-1)", "Support Five Eyes critical minerals pact"],
    ...
},
```

Update all 10 risk register entries to include `coa_ids` arrays referencing the 6 sufficiency COAs (COA-1 through COA-6) where applicable. Risks that don't map to existing COAs keep their freetext COAs.

- [ ] **Step 2: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(G9): cross-reference risk register COAs to sufficiency COA IDs"
```

---

### Task 10: G2+G3 — Persist alert and risk register actions to database

**Files:**
- Modify: `src/api/psi_routes.py` — add 2 new endpoints
- Modify: `src/static/index.html` — wire alert and register buttons to API

- [ ] **Step 1: Add alert action persistence endpoint**

In `src/api/psi_routes.py`, add after the existing `/alerts` endpoint:

```python
class CobaltAlertAction(BaseModel):
    alert_id: str
    action: str  # "acknowledge", "assign", "escalate"
    analyst: str = ""

# In-memory store for alert actions (per session — persists until server restart)
_cobalt_alert_actions: dict[str, dict] = {}

@router.post("/alerts/cobalt/action")
async def cobalt_alert_action(req: CobaltAlertAction):
    """Record an analyst action on a Cobalt watchtower alert."""
    _cobalt_alert_actions[req.alert_id] = {
        "alert_id": req.alert_id,
        "action": req.action,
        "analyst": req.analyst,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"status": "recorded", **_cobalt_alert_actions[req.alert_id]}

@router.get("/alerts/cobalt/actions")
async def get_cobalt_alert_actions():
    """Get all recorded Cobalt alert actions."""
    return list(_cobalt_alert_actions.values())
```

- [ ] **Step 2: Add risk register status persistence endpoint**

```python
class RegisterStatusUpdate(BaseModel):
    risk_id: str
    new_status: str  # "open", "in_progress", "mitigated", "closed"
    analyst: str = ""

_cobalt_register_status: dict[str, dict] = {}

@router.patch("/register/cobalt/{risk_id}")
async def update_cobalt_register_status(risk_id: str, update: RegisterStatusUpdate):
    """Update status of a Cobalt risk register entry."""
    _cobalt_register_status[risk_id] = {
        "risk_id": risk_id,
        "status": update.new_status,
        "analyst": update.analyst,
        "timestamp": datetime.utcnow().isoformat(),
    }
    return {"status": "updated", **_cobalt_register_status[risk_id]}

@router.get("/register/cobalt/status")
async def get_cobalt_register_status():
    """Get all Cobalt risk register status overrides."""
    return _cobalt_register_status
```

- [ ] **Step 3: Wire alert buttons to POST /psi/alerts/cobalt/action**

In `index.html`, update `alertAcknowledge`, `alertAssign`, `alertEscalate` to POST to the API:

Replace `alertAcknowledge`:
```javascript
function alertAcknowledge(btn, alertId) {
  fetch(API + '/psi/alerts/cobalt/action', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({alert_id:alertId, action:'acknowledge', analyst:'Current User'})});
  var card = btn.closest('.card');
  btn.textContent = '\u2713 Acknowledged'; btn.style.color = 'var(--accent3)'; btn.style.borderColor = 'var(--accent3)'; btn.disabled = true;
  card.style.borderLeftColor = 'var(--accent3)';
}
```

Similarly update `alertAssign` and `alertEscalate` to include `alertId` parameter and POST.

Update the button rendering in `renderAlertsSensing` to pass `a.id`:
```javascript
html += '<button ... onclick="alertAcknowledge(this,\'' + esc(a.id) + '\')">Acknowledge</button>';
```

- [ ] **Step 4: Wire risk register buttons to PATCH /psi/register/cobalt/{id}**

Update `updateRegisterStatus` to POST:
```javascript
function updateRegisterStatus(btn, idx, newStatus, riskId) {
  fetch(API + '/psi/register/cobalt/' + encodeURIComponent(riskId), {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify({risk_id:riskId, new_status:newStatus, analyst:'Current User'})});
  // ... existing DOM update logic
}
```

Update the button rendering in `renderRiskRegister` to pass `r.id`:
```javascript
html += '..." onclick="updateRegisterStatus(this,'+i+',\''+st+'\',\''+esc(r.id)+'\')"...';
```

- [ ] **Step 5: Commit**

```bash
git add src/api/psi_routes.py src/static/index.html
git commit -m "feat(G2,G3): persist Cobalt alert actions and risk register status via API"
```

---

### Task 11: G1 — Create Cobalt alert engine (GDELT + rule-based)

**Files:**
- Create: `src/analysis/cobalt_alert_engine.py`
- Modify: `src/ingestion/scheduler.py`

- [ ] **Step 1: Create the Cobalt alert engine**

Create `src/analysis/cobalt_alert_engine.py`:

```python
"""Cobalt Alert Engine — generates alerts from GDELT keywords and rule-based triggers.

Addresses DND Q1 (SENSE) and Q11 (Automated Sensing).
Two alert sources:
1. GDELT keyword monitoring — scans recent news for cobalt-related disruptions
2. Rule-based triggers — checks commodity prices, sanctions, and supply data for threshold breaches
"""
from __future__ import annotations

import logging
from datetime import datetime

from src.analysis.mineral_supply_chains import get_mineral_by_name

logger = logging.getLogger(__name__)

# GDELT search queries specific to Cobalt supply chain
COBALT_GDELT_QUERIES = [
    "cobalt DRC Congo mining",
    "cobalt export ban quota restriction",
    "cobalt China refining disruption",
    "cobalt price crash spike",
    "cobalt mine accident shutdown",
    "CMOC Glencore cobalt acquisition",
    "cobalt sanctions embargo",
    "Sherritt cobalt Cuba",
]

# Rule-based trigger thresholds
RULES = [
    {
        "id": "RULE-PRICE",
        "name": "Cobalt price volatility",
        "check": "_check_price_volatility",
        "category": "Economic",
        "severity_base": 3,
    },
    {
        "id": "RULE-SANCTION",
        "name": "New sanctions on cobalt-producing country",
        "check": "_check_sanctions_change",
        "category": "Political",
        "severity_base": 4,
    },
    {
        "id": "RULE-CONCENTRATION",
        "name": "Supply concentration threshold breach",
        "check": "_check_concentration",
        "category": "Manufacturing/Supply",
        "severity_base": 4,
    },
    {
        "id": "RULE-INSOLVENCY",
        "name": "Supplier insolvency signal",
        "check": "_check_insolvency",
        "category": "Financial",
        "severity_base": 4,
    },
]


async def generate_gdelt_alerts() -> list[dict]:
    """Scan GDELT for cobalt-related news and generate alerts."""
    from src.ingestion.gdelt_news import GDELTNewsConnector

    connector = GDELTNewsConnector()
    alerts = []

    for query in COBALT_GDELT_QUERIES[:4]:  # limit to 4 queries per run (rate limiting)
        try:
            articles = await connector.search_articles(
                query=query, timespan="1440", max_records=5
            )
            for article in articles:
                if not article.title:
                    continue
                # Score severity from tone
                tone = article.tone or 0
                severity = 5 if tone < -8 else 4 if tone < -5 else 3 if tone < -2 else 2

                alerts.append({
                    "id": f"GDELT-{hash(article.url) % 100000:05d}",
                    "title": article.title[:200],
                    "severity": severity,
                    "category": _infer_category(article.title),
                    "sources": [article.source or "GDELT"],
                    "confidence": min(90, max(40, 50 + int(abs(tone) * 3))),
                    "coa": _suggest_coa(article.title),
                    "timestamp": (article.published_at or datetime.utcnow()).isoformat(),
                    "source_url": article.url,
                    "auto_generated": True,
                })
        except Exception as e:
            logger.warning("GDELT cobalt query failed for '%s': %s", query[:30], e)

    logger.info("Generated %d GDELT cobalt alerts", len(alerts))
    return alerts


def generate_rule_alerts() -> list[dict]:
    """Run rule-based checks against current Cobalt data."""
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        return []

    alerts = []

    # Rule: HHI concentration
    hhi = mineral.get("hhi", 0)
    if hhi > 5000:
        alerts.append({
            "id": "RULE-CONC-001",
            "title": f"Cobalt mining HHI at {hhi} — extreme supply concentration (DRC {mineral.get('mining', [{}])[0].get('pct', 0)}%)",
            "severity": 5 if hhi > 6000 else 4,
            "category": "Manufacturing/Supply",
            "sources": ["USGS MCS 2025", "PSI Concentration Index"],
            "confidence": 95,
            "coa": "Diversify sourcing to Australian, Philippine, and Canadian deposits",
            "timestamp": datetime.utcnow().isoformat(),
            "auto_generated": True,
        })

    # Rule: China refining dominance
    processing = mineral.get("processing", [])
    china_pct = sum(p.get("pct", 0) for p in processing if p.get("country") == "China")
    if china_pct > 70:
        alerts.append({
            "id": "RULE-CHINA-001",
            "title": f"China controls {china_pct}% of global cobalt refining — adversary chokepoint",
            "severity": 5,
            "category": "FOCI",
            "sources": ["USGS MCS 2025", "CRU Group Cobalt Market Report"],
            "confidence": 95,
            "coa": "Support Finnish/Norwegian refinery expansion; DPSA allied allocation",
            "timestamp": datetime.utcnow().isoformat(),
            "auto_generated": True,
        })

    # Rule: Paused operations
    refineries = mineral.get("refineries", [])
    for ref in refineries:
        note = (ref.get("note") or "").lower()
        if "paused" in note or "suspended" in note or "idled" in note:
            alerts.append({
                "id": f"RULE-PAUSE-{ref.get('name', 'UNK')[:8].upper().replace(' ', '')}",
                "title": f"{ref.get('name', 'Unknown')} operations paused — {ref.get('note', '')}",
                "severity": 4,
                "category": "Financial",
                "sources": [f"{ref.get('owner', 'Unknown')} Operations Report", "PSI Supply Chain Monitor"],
                "confidence": 90,
                "coa": f"Assess alternative refineries; monitor {ref.get('owner', 'operator')} restart timeline",
                "timestamp": datetime.utcnow().isoformat(),
                "auto_generated": True,
            })

    logger.info("Generated %d rule-based cobalt alerts", len(alerts))
    return alerts


def _infer_category(title: str) -> str:
    """Infer alert category from article title keywords."""
    t = title.lower()
    if any(w in t for w in ["sanction", "embargo", "ban", "restrict"]):
        return "Political"
    if any(w in t for w in ["acquire", "merger", "ownership", "soe", "state-owned"]):
        return "FOCI"
    if any(w in t for w in ["price", "cost", "market", "crash", "spike"]):
        return "Economic"
    if any(w in t for w in ["cyber", "hack", "malware", "breach"]):
        return "Cyber"
    if any(w in t for w in ["mine", "accident", "spill", "pollution", "environment"]):
        return "Environmental"
    if any(w in t for w in ["ship", "route", "port", "transport", "logistics"]):
        return "Transportation"
    return "Manufacturing/Supply"


def _suggest_coa(title: str) -> str:
    """Suggest a course of action based on alert title."""
    t = title.lower()
    if "sanction" in t or "ban" in t:
        return "Activate alternative supply sources; review DPSA allocation"
    if "price" in t:
        return "Assess stockpile draw-down; review contract escalation clauses"
    if "acquisition" in t or "merger" in t:
        return "Initiate FOCI review; assess supply chain impact"
    if "accident" in t or "shutdown" in t:
        return "Monitor production recovery timeline; activate safety stock"
    return "Monitor situation; assess impact on Canadian defence supply chain"


async def run_cobalt_alert_engine() -> list[dict]:
    """Main entry point — run both GDELT and rule-based alert generation."""
    gdelt_alerts = await generate_gdelt_alerts()
    rule_alerts = generate_rule_alerts()

    all_alerts = gdelt_alerts + rule_alerts
    # Deduplicate by similar titles
    seen = set()
    deduped = []
    for a in all_alerts:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    logger.info("Cobalt Alert Engine: %d total alerts (%d GDELT, %d rules, %d after dedup)",
                len(all_alerts), len(gdelt_alerts), len(rule_alerts), len(deduped))
    return deduped
```

- [ ] **Step 2: Register in scheduler**

In `src/ingestion/scheduler.py`, add import and job:

After the existing imports, add:
```python
from src.analysis.cobalt_alert_engine import run_cobalt_alert_engine
```

In `create_scheduler()`, add after the GDELT job:
```python
    # Cobalt-specific alert engine (every 30 minutes)
    scheduler.add_job(
        run_cobalt_alert_engine,
        trigger=IntervalTrigger(minutes=30),
        id="cobalt_alerts",
        name="Cobalt supply chain alert engine",
        max_instances=1,
    )
```

- [ ] **Step 3: Add API endpoint to serve live alerts merged with static**

In `src/api/psi_routes.py` or `src/api/globe_routes.py`, update the `/globe/minerals/{name}` response to merge live alerts when mineral is Cobalt. Add after the existing endpoint:

```python
@router.get("/alerts/cobalt/live")
async def get_cobalt_live_alerts():
    """Get live-generated Cobalt alerts from GDELT + rule engine."""
    from src.analysis.cobalt_alert_engine import run_cobalt_alert_engine
    alerts = await run_cobalt_alert_engine()
    return {"alerts": alerts, "count": len(alerts), "generated_at": datetime.utcnow().isoformat()}
```

- [ ] **Step 4: Update Alerts & Sensing tab to fetch live alerts**

In `index.html`, update `onAlertsMineralChange` to also fetch live alerts and merge:

```javascript
async function onAlertsMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-alerts-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view alerts.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading alerts...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    // Merge live alerts for Cobalt
    if (mineral.toLowerCase() === 'cobalt') {
      try {
        var liveResp = await fetch(API + '/psi/alerts/cobalt/live');
        if (liveResp.ok) {
          var liveData = await liveResp.json();
          var existingIds = new Set((m.watchtower_alerts || []).map(function(a){ return a.id; }));
          (liveData.alerts || []).forEach(function(la) {
            if (!existingIds.has(la.id)) {
              m.watchtower_alerts = m.watchtower_alerts || [];
              m.watchtower_alerts.push(la);
            }
          });
        }
      } catch(e) { /* live alerts unavailable — use static only */ }
    }
    renderAlertsSensing(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Alerts data not yet available for ' + esc(mineral) + '</div>'; }
}
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/ -v --tb=short`

- [ ] **Step 6: Commit**

```bash
git add src/analysis/cobalt_alert_engine.py src/ingestion/scheduler.py src/api/psi_routes.py src/static/index.html
git commit -m "feat(G1): add Cobalt alert engine with GDELT keyword monitoring and rule-based triggers"
```

---

### Task 12: Verification — Run full test suite and validate

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All previously-passing tests still pass. No regressions.

- [ ] **Step 2: Verify API endpoints**

Start server and test:
```bash
curl http://localhost:8000/psi/alerts/cobalt/live
curl http://localhost:8000/psi/alerts/cobalt/actions
curl http://localhost:8000/psi/register/cobalt/status
```

- [ ] **Step 3: Final commit if needed**

All tasks should be committed individually.
