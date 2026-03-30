# Per-Mineral Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a mineral selector dropdown to the Knowledge Graph sub-tab that switches from the full force-directed graph to a 5-tier layered Cobalt dependency chain (mines → refineries → alloys → engines → platforms) with click-to-trace highlighting and an info panel.

**Architecture:** All changes in `src/static/index.html`. The mineral dropdown fetches data from the existing `/globe/minerals` endpoint. When "Cobalt" is selected, a new layered D3 renderer draws ~45 nodes in 5 columns with risk-colored fills and adversary/allied border colors. Clicking a node traces upstream/downstream dependencies. The existing force-directed graph is preserved for "All" selection.

**Tech Stack:** D3.js (already loaded via CDN), HTML/CSS/JS inline in index.html

**Spec:** `docs/superpowers/specs/2026-03-30-per-mineral-knowledge-graph-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/static/index.html` (HTML ~line 2067) | Modify | Add mineral dropdown to graph controls |
| `src/static/index.html` (HTML ~line 2083) | Modify | Add legend for layered graph + info panel container |
| `src/static/index.html` (CSS ~line 900) | Modify | Add styles for layered graph, info panel, highlighting |
| `src/static/index.html` (JS ~line 7596) | Modify | Modify `loadPsiGraph()` to check mineral selection, add `loadMineralGraph()`, `renderLayeredGraph()`, click handlers, info panel renderer |

---

### Task 1: Add Mineral Dropdown to Graph Controls + CSS

**Files:**
- Modify: `src/static/index.html` (HTML controls area ~line 2067, CSS ~line 900)

- [ ] **Step 1: Add mineral dropdown HTML**

Find the graph controls div (around line 2067):

```html
          <div class="psi-controls" style="display:flex; gap:8px; align-items:center;">
            <select id="psi-graph-type-filter">
```

Insert a new mineral dropdown BEFORE the type filter:

```html
          <div class="psi-controls" style="display:flex; gap:8px; align-items:center;">
            <select id="psi-graph-mineral-filter" onchange="loadPsiGraph()" style="max-width:160px;">
              <option value="">All Minerals</option>
            </select>
            <select id="psi-graph-type-filter">
```

- [ ] **Step 2: Add info panel container**

Find the legend div after the graph container (around line 2083):

```html
        <div style="margin-top:10px; font-size:11px; color:var(--text-dim); display:flex; flex-wrap:wrap; gap:6px 18px;">
```

Insert an info panel container BEFORE the legend:

```html
        <!-- Mineral graph info panel (shown on node click) -->
        <div id="psi-graph-info-panel" style="display:none; position:absolute; top:20px; right:20px; width:280px; background:var(--surface-glass); backdrop-filter:blur(16px); border:1px solid var(--border); border-radius:10px; padding:14px; z-index:10; font-size:12px;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <h4 id="psi-graph-info-title" style="margin:0; font-size:14px;"></h4>
            <button onclick="document.getElementById('psi-graph-info-panel').style.display='none'; clearGraphHighlights();" style="background:none; border:none; color:var(--text-dim); cursor:pointer; font-size:16px;">&times;</button>
          </div>
          <div id="psi-graph-info-body" style="color:var(--text-dim); line-height:1.6;"></div>
        </div>
        <div id="psi-graph-layered-legend" style="display:none; margin-top:10px; font-size:11px; color:var(--text-dim); display:flex; flex-wrap:wrap; gap:6px 18px;">
          <span><span class="graph-legend-dot circle" style="background:#10b981;"></span> Mine</span>
          <span><span class="graph-legend-dot square" style="background:#10b981;"></span> Refinery</span>
          <span><span class="graph-legend-dot diamond" style="background:#10b981;"></span> Alloy</span>
          <span><span class="graph-legend-dot" style="background:#10b981; clip-path:polygon(50% 0%,100% 25%,100% 75%,50% 100%,0% 75%,0% 25%);"></span> Engine</span>
          <span><span class="graph-legend-dot" style="background:#10b981; clip-path:polygon(50% 0%,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%);"></span> Platform</span>
          <span style="margin-left:12px;"><span style="display:inline-block; width:12px; height:12px; border:3px solid #ef4444; border-radius:50%; vertical-align:middle; margin-right:4px;"></span> Adversary</span>
          <span><span style="display:inline-block; width:12px; height:12px; border:2px solid #3b82f6; border-radius:50%; vertical-align:middle; margin-right:4px;"></span> NATO-Allied</span>
          <span><span style="display:inline-block; width:12px; height:12px; border:1px solid #64748b; border-radius:50%; vertical-align:middle; margin-right:4px;"></span> Neutral</span>
        </div>
        <div style="margin-top:10px; font-size:11px; color:var(--text-dim); display:flex; flex-wrap:wrap; gap:6px 18px;">
```

- [ ] **Step 3: Add CSS styles for layered graph**

Find the line `@media (max-width: 1200px) {` in the CSS section. Insert these styles BEFORE it:

```css
/* Per-Mineral Knowledge Graph */
.mineral-graph-node { cursor: pointer; transition: opacity 0.3s; }
.mineral-graph-node.dimmed { opacity: 0.15; }
.mineral-graph-node.highlighted { opacity: 1; }
.mineral-graph-edge { transition: opacity 0.3s, stroke 0.3s; }
.mineral-graph-edge.dimmed { opacity: 0.05; }
.mineral-graph-edge.highlighted-up { stroke: #00d4ff !important; stroke-width: 3px !important; stroke-dasharray: none !important; opacity: 1; }
.mineral-graph-edge.highlighted-down { stroke: #f59e0b !important; stroke-width: 3px !important; stroke-dasharray: none !important; opacity: 1; }
.mineral-graph-label { font-size: 9px; fill: #94a3b8; text-anchor: middle; pointer-events: none; }

```

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add mineral dropdown + info panel + CSS for per-mineral Knowledge Graph"
```

---

### Task 2: Populate Mineral Dropdown + Modify loadPsiGraph

**Files:**
- Modify: `src/static/index.html` (JS section ~line 7596)

- [ ] **Step 1: Add mineral list loader and modify loadPsiGraph**

Find the `loadPsiGraph` function (around line 7596). Replace the entire function with:

```javascript
async function loadPsiGraph() {
  const mineralFilter = document.getElementById('psi-graph-mineral-filter').value;
  const typeFilter = document.getElementById('psi-graph-type-filter').value;
  const riskMin = parseInt(document.getElementById('psi-graph-risk-slider').value);
  document.getElementById('psi-graph-risk-val').textContent = riskMin;

  const container = document.getElementById('psi-graph-container');
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading graph...</div>';

  // Hide info panel on reload
  document.getElementById('psi-graph-info-panel').style.display = 'none';

  if (mineralFilter) {
    // Per-mineral layered graph
    await loadMineralGraph(mineralFilter, container);
    return;
  }

  // Default: full force-directed graph
  document.getElementById('psi-graph-layered-legend').style.display = 'none';
  let url = API + '/psi/graph?risk_min=' + riskMin;
  if (typeFilter) url += '&node_type=' + typeFilter;

  try {
    const resp = await fetch(url);
    if (!resp.ok) throw new Error('Failed');
    const data = await resp.json();
    renderPsiForceGraph(data, container);
  } catch (e) {
    container.innerHTML = '<div style="color:var(--accent2); text-align:center; padding:40px;">Failed to load graph: ' + esc(e.message) + '</div>';
  }
}
```

- [ ] **Step 2: Add mineral dropdown population function**

Insert AFTER the modified `loadPsiGraph` function (and BEFORE `renderPsiForceGraph`):

```javascript

// Populate mineral dropdown on first load
async function populateMineralDropdown() {
  var select = document.getElementById('psi-graph-mineral-filter');
  if (select.options.length > 1) return; // already populated
  try {
    var resp = await fetch(API + '/globe/minerals');
    if (!resp.ok) return;
    var minerals = await resp.json();
    minerals.forEach(function(m) {
      var opt = document.createElement('option');
      opt.value = m.name;
      var hasDeepl = m.mines && m.mines.length > 0;
      opt.textContent = (hasDeep ? '\u2605 ' : '') + m.name;
      select.appendChild(opt);
    });
  } catch (e) {
    // Dropdown stays with just "All Minerals"
  }
}
```

Wait — there's a typo: `hasDeepl` vs `hasDeep`. Let me fix that in the plan. The variable should be `hasDeep` consistently:

```javascript

// Populate mineral dropdown on first load
async function populateMineralDropdown() {
  var select = document.getElementById('psi-graph-mineral-filter');
  if (select.options.length > 1) return;
  try {
    var resp = await fetch(API + '/globe/minerals');
    if (!resp.ok) return;
    var minerals = await resp.json();
    minerals.forEach(function(m) {
      var opt = document.createElement('option');
      opt.value = m.name;
      var hasDeep = m.mines && m.mines.length > 0;
      opt.textContent = (hasDeep ? '\u2605 ' : '') + m.name;
      select.appendChild(opt);
    });
  } catch (e) {
    // Dropdown stays with just "All Minerals"
  }
}
```

- [ ] **Step 3: Call populateMineralDropdown when graph tab is shown**

Find where `loadPsiGraph()` is first called when the PSI Graph tab is shown. Search for `switchPsiTab` or `psi-graph` tab activation logic. Add `populateMineralDropdown()` call before `loadPsiGraph()`. Find the code that handles PSI tab switching and add:

```javascript
populateMineralDropdown();
```

right before the existing `loadPsiGraph()` call in the graph tab activation path.

- [ ] **Step 4: Commit**

```bash
git add src/static/index.html
git commit -m "feat: populate mineral dropdown + route mineral selection to layered graph"
```

---

### Task 3: Build the Layered Graph Renderer

**Files:**
- Modify: `src/static/index.html` (JS section — insert after `populateMineralDropdown`)

- [ ] **Step 1: Add loadMineralGraph and renderLayeredGraph functions**

Insert after `populateMineralDropdown`:

```javascript

var mineralGraphData = null; // cached mineral graph nodes/edges for click interaction

async function loadMineralGraph(mineralName, container) {
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineralName));
    if (!resp.ok) throw new Error('Mineral not found');
    var m = await resp.json();

    if (!m.mines || !m.refineries || !m.sufficiency) {
      container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:60px;">Deep supply chain data not yet available for ' + esc(mineralName) + '.<br>Showing full graph instead.</div>';
      document.getElementById('psi-graph-mineral-filter').value = '';
      loadPsiGraph();
      return;
    }

    var graphData = buildMineralGraphData(m);
    mineralGraphData = graphData;
    renderLayeredGraph(graphData, container, m.name);

    // Show layered legend, hide default legend
    document.getElementById('psi-graph-layered-legend').style.display = 'flex';

  } catch (e) {
    container.innerHTML = '<div style="color:var(--accent2); text-align:center; padding:40px;">Failed to load mineral graph: ' + esc(e.message) + '</div>';
  }
}

var ADVERSARY_COUNTRIES = ['china', 'russia', 'drc', 'democratic republic of the congo', 'iran', 'north korea'];
var NATO_COUNTRIES = ['united states', 'us', 'usa', 'canada', 'united kingdom', 'uk', 'finland', 'belgium', 'germany', 'australia', 'japan', 'france', 'norway', 'italy', 'netherlands', 'spain', 'poland', 'turkey', 'south korea', 'switzerland'];

function getCountryBorder(country) {
  var c = (country || '').toLowerCase();
  for (var i = 0; i < ADVERSARY_COUNTRIES.length; i++) {
    if (c.includes(ADVERSARY_COUNTRIES[i])) return { color: '#ef4444', width: 3 };
  }
  for (var j = 0; j < NATO_COUNTRIES.length; j++) {
    if (c.includes(NATO_COUNTRIES[j])) return { color: '#3b82f6', width: 2 };
  }
  return { color: '#64748b', width: 1 };
}

function getRiskColor(level) {
  if (level === 'critical') return '#ef4444';
  if (level === 'high') return '#f59e0b';
  if (level === 'medium') return '#eab308';
  return '#10b981';
}

function getCompositeRiskLevel(taxonomyScores) {
  if (!taxonomyScores) return 'medium';
  var total = 0, count = 0;
  for (var k in taxonomyScores) {
    if (taxonomyScores[k] && typeof taxonomyScores[k].score === 'number') {
      total += taxonomyScores[k].score;
      count++;
    }
  }
  var avg = count > 0 ? total / count : 50;
  if (avg >= 75) return 'critical';
  if (avg >= 55) return 'high';
  if (avg >= 35) return 'medium';
  return 'low';
}

function buildMineralGraphData(m) {
  var nodes = [];
  var edges = [];
  var id = 0;

  // Tier 1: Mines
  var mineNodes = [];
  m.mines.forEach(function(mine) {
    var nid = 'mine-' + (id++);
    var riskLevel = getCompositeRiskLevel(mine.taxonomy_scores);
    mineNodes.push({ id: nid, name: mine.name, tier: 0, type: 'mine', country: mine.country,
      owner: mine.owner || '', production: mine.production_t, riskLevel: riskLevel,
      border: getCountryBorder(mine.country), fill: getRiskColor(riskLevel), raw: mine });
    nodes.push(mineNodes[mineNodes.length - 1]);
  });

  // Tier 2: Refineries
  var refNodes = [];
  m.refineries.forEach(function(ref) {
    var nid = 'ref-' + (id++);
    var riskLevel = getCompositeRiskLevel(ref.taxonomy_scores);
    refNodes.push({ id: nid, name: ref.name, tier: 1, type: 'refinery', country: ref.country,
      owner: ref.owner || '', capacity: ref.capacity_t, riskLevel: riskLevel,
      border: getCountryBorder(ref.country), fill: getRiskColor(riskLevel), raw: ref });
    nodes.push(refNodes[refNodes.length - 1]);
  });

  // Tier 3: Alloys
  var alloyNodes = [];
  m.alloys.forEach(function(alloy) {
    var nid = 'alloy-' + (id++);
    alloyNodes.push({ id: nid, name: alloy.name, tier: 2, type: 'alloy',
      cobalt_pct: alloy.cobalt_pct, use: alloy.use, riskLevel: 'medium',
      border: { color: '#64748b', width: 1 }, fill: getRiskColor('medium'), raw: alloy });
    nodes.push(alloyNodes[alloyNodes.length - 1]);
  });

  // Tier 4: Engines (unique from sufficiency.demand indirect entries)
  var engineMap = {};
  var engineNodes = [];
  m.sufficiency.demand.forEach(function(d) {
    if (d.type !== 'indirect' || !d.engine) return;
    if (engineMap[d.engine]) return;
    var nid = 'eng-' + (id++);
    var riskLevel = d.threshold_ratio >= 0.7 ? 'high' : d.threshold_ratio >= 0.5 ? 'medium' : 'low';
    engineMap[d.engine] = nid;
    engineNodes.push({ id: nid, name: d.engine, tier: 3, type: 'engine',
      oem: d.oem, oem_country: d.oem_country, riskLevel: riskLevel,
      border: getCountryBorder(d.oem_country), fill: getRiskColor(riskLevel), raw: d });
    nodes.push(engineNodes[engineNodes.length - 1]);
  });

  // Tier 5: Platforms (all from sufficiency.demand)
  var platNodes = [];
  m.sufficiency.demand.forEach(function(d) {
    var nid = 'plat-' + (id++);
    var riskLevel = d.type === 'indirect' ? 'high' : 'low';
    platNodes.push({ id: nid, name: d.platform, tier: 4, type: 'platform',
      depType: d.type, kg_yr: d.kg_yr, fleet_note: d.fleet_note, riskLevel: riskLevel,
      border: getCountryBorder('Canada'), fill: getRiskColor(riskLevel), raw: d });
    nodes.push(platNodes[platNodes.length - 1]);
  });

  // Edges: Mine → Refinery (by country: DRC mines → Chinese refineries, Canadian mines → Canadian refineries, etc.)
  mineNodes.forEach(function(mine) {
    refNodes.forEach(function(ref) {
      var mineCountry = (mine.country || '').toLowerCase();
      var refCountry = (ref.country || '').toLowerCase();
      var connect = false;
      // DRC/Indonesia mines → Chinese refineries
      if ((mineCountry === 'drc' || mineCountry === 'indonesia') && refCountry === 'china') connect = true;
      // Canadian mines → Canadian refineries
      if (mineCountry === 'canada' && refCountry === 'canada') connect = true;
      // Australian mines → Finnish/Belgian refineries (Glencore/Umicore)
      if (mineCountry === 'australia' && (refCountry === 'finland' || refCountry === 'belgium')) connect = true;
      // DRC mines → Finnish/Belgian refineries (Umicore sources from DRC too)
      if (mineCountry === 'drc' && (refCountry === 'finland' || refCountry === 'belgium')) connect = true;
      // Same owner connection
      if (mine.owner && ref.owner && mine.owner.toLowerCase().includes(ref.owner.split(' ')[0].toLowerCase())) connect = true;
      if (connect) {
        edges.push({ source: mine.id, target: ref.id, type: 'produces' });
      }
    });
  });

  // Edges: Refinery → Alloy (all refineries feed all alloys — cobalt is generic feedstock)
  refNodes.forEach(function(ref) {
    alloyNodes.forEach(function(alloy) {
      edges.push({ source: ref.id, target: alloy.id, type: 'refines_to' });
    });
  });

  // Edges: Alloy → Engine (from sufficiency.demand[].alloy matching alloy name)
  m.sufficiency.demand.forEach(function(d) {
    if (d.type !== 'indirect' || !d.alloy || d.alloy === 'n/a') return;
    var alloyNode = alloyNodes.find(function(a) { return a.name === d.alloy; });
    var engineId = engineMap[d.engine];
    if (alloyNode && engineId) {
      // Avoid duplicate edges
      var exists = edges.some(function(e) { return e.source === alloyNode.id && e.target === engineId; });
      if (!exists) edges.push({ source: alloyNode.id, target: engineId, type: 'cast_into' });
    }
  });

  // Edges: Engine → Platform
  m.sufficiency.demand.forEach(function(d) {
    if (d.type !== 'indirect' || !d.engine) return;
    var engineId = engineMap[d.engine];
    var platNode = platNodes.find(function(p) { return p.name === d.platform; });
    if (engineId && platNode) {
      edges.push({ source: engineId, target: platNode.id, type: 'powers' });
    }
  });

  // Direct platforms: connect directly from alloys (SmCo, WC-Co, NMC) to platforms
  m.sufficiency.demand.forEach(function(d) {
    if (d.type !== 'direct') return;
    var platNode = platNodes.find(function(p) { return p.name === d.platform; });
    if (!platNode) return;
    // Connect from a relevant alloy if one matches, otherwise from all refineries
    var matchAlloy = alloyNodes.find(function(a) {
      return d.use && a.name.toLowerCase().includes(d.use.split(' ')[0].toLowerCase());
    });
    if (matchAlloy) {
      edges.push({ source: matchAlloy.id, target: platNode.id, type: 'used_in' });
    } else {
      // Connect from first refinery as generic supply
      if (refNodes.length > 0) {
        edges.push({ source: refNodes[0].id, target: platNode.id, type: 'supplies' });
      }
    }
  });

  return { nodes: nodes, edges: edges };
}

function renderLayeredGraph(data, container, mineralName) {
  container.innerHTML = '';
  var width = container.clientWidth;
  var tierCounts = [0, 0, 0, 0, 0];
  data.nodes.forEach(function(n) { tierCounts[n.tier]++; });
  var maxTierCount = Math.max.apply(null, tierCounts);
  var height = Math.max(550, maxTierCount * 42 + 60);
  container.style.position = 'relative';

  var svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

  // Tier x positions
  var tierX = [0.08, 0.28, 0.50, 0.70, 0.90];
  var tierLabels = ['Mining', 'Refining', 'Alloys', 'Engines', 'Platforms'];
  var tierShapes = [d3.symbolCircle, d3.symbolSquare, d3.symbolDiamond, d3.symbolHexagonAlt || d3.symbolCircle, d3.symbolStar];

  // Draw tier column headers
  svg.append('g').selectAll('text').data(tierLabels).join('text')
    .attr('x', function(d, i) { return tierX[i] * width; })
    .attr('y', 18)
    .attr('text-anchor', 'middle')
    .attr('fill', '#64748b')
    .attr('font-size', '11px')
    .attr('font-family', 'var(--font-mono)')
    .attr('text-transform', 'uppercase')
    .attr('letter-spacing', '0.5px')
    .text(function(d) { return d; });

  // Assign y positions within each tier
  var tierIdx = [0, 0, 0, 0, 0];
  data.nodes.forEach(function(n) {
    var count = tierCounts[n.tier];
    var idx = tierIdx[n.tier]++;
    n.x = tierX[n.tier] * width;
    n.y = 40 + (idx + 0.5) * ((height - 50) / count);
  });

  // Build node lookup for edges
  var nodeMap = {};
  data.nodes.forEach(function(n) { nodeMap[n.id] = n; });

  // Draw edges
  var edgeGroup = svg.append('g');
  var edgePaths = edgeGroup.selectAll('path').data(data.edges).join('path')
    .attr('class', 'mineral-graph-edge')
    .attr('d', function(e) {
      var s = nodeMap[e.source];
      var t = nodeMap[e.target];
      if (!s || !t) return '';
      var mx = (s.x + t.x) / 2;
      return 'M' + s.x + ',' + s.y + ' C' + mx + ',' + s.y + ' ' + mx + ',' + t.y + ' ' + t.x + ',' + t.y;
    })
    .attr('fill', 'none')
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 1)
    .attr('stroke-dasharray', '4 2');

  // Draw nodes
  var nodeGroup = svg.append('g');
  var nodeEls = nodeGroup.selectAll('g').data(data.nodes).join('g')
    .attr('class', 'mineral-graph-node')
    .attr('transform', function(d) { return 'translate(' + d.x + ',' + d.y + ')'; })
    .style('cursor', 'pointer')
    .on('click', function(event, d) { onMineralNodeClick(d, data); })
    .on('mouseenter', function(event, d) { showGraphTooltip(event, d); })
    .on('mouseleave', function() { hideGraphTooltip(); });

  // Node shape
  nodeEls.append('path')
    .attr('d', function(d) {
      var shape = tierShapes[d.tier] || d3.symbolCircle;
      return d3.symbol().type(shape).size(180)();
    })
    .attr('fill', function(d) { return d.fill; })
    .attr('stroke', function(d) { return d.border.color; })
    .attr('stroke-width', function(d) { return d.border.width; });

  // Node labels
  nodeEls.append('text')
    .attr('class', 'mineral-graph-label')
    .attr('dy', 22)
    .text(function(d) { return d.name.length > 15 ? d.name.slice(0, 13) + '\u2026' : d.name; });
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add layered D3 graph renderer for per-mineral Knowledge Graph"
```

---

### Task 4: Add Click Interaction + Info Panel + Tooltip

**Files:**
- Modify: `src/static/index.html` (JS section — insert after `renderLayeredGraph`)

- [ ] **Step 1: Add click handler, highlight tracing, tooltip, and info panel renderer**

Insert after `renderLayeredGraph`:

```javascript

// Tooltip for mineral graph hover
var graphTooltipEl = null;
function showGraphTooltip(event, d) {
  if (!graphTooltipEl) {
    graphTooltipEl = document.createElement('div');
    graphTooltipEl.style.cssText = 'position:fixed;background:var(--surface-glass);backdrop-filter:blur(16px);border:1px solid var(--border);border-radius:6px;padding:8px 10px;font-size:11px;color:var(--text);z-index:100;pointer-events:none;max-width:220px;';
    document.body.appendChild(graphTooltipEl);
  }
  var html = '<strong>' + esc(d.name) + '</strong><br>';
  html += '<span style="color:var(--text-dim);">' + esc(d.type) + '</span>';
  if (d.country) html += ' &mdash; ' + esc(d.country);
  if (d.riskLevel) html += '<br>Risk: <span style="color:' + getRiskColor(d.riskLevel) + ';">' + d.riskLevel.toUpperCase() + '</span>';
  graphTooltipEl.innerHTML = html;
  graphTooltipEl.style.display = 'block';
  graphTooltipEl.style.left = (event.clientX + 12) + 'px';
  graphTooltipEl.style.top = (event.clientY - 10) + 'px';
}
function hideGraphTooltip() {
  if (graphTooltipEl) graphTooltipEl.style.display = 'none';
}

function clearGraphHighlights() {
  d3.selectAll('.mineral-graph-node').classed('dimmed', false).classed('highlighted', false);
  d3.selectAll('.mineral-graph-edge').classed('dimmed', false).classed('highlighted-up', false).classed('highlighted-down', false);
}

function onMineralNodeClick(clicked, data) {
  // Build adjacency lists
  var upstream = {};   // nodeId → [sourceNodeIds]
  var downstream = {}; // nodeId → [targetNodeIds]
  data.edges.forEach(function(e) {
    if (!downstream[e.source]) downstream[e.source] = [];
    downstream[e.source].push(e.target);
    if (!upstream[e.target]) upstream[e.target] = [];
    upstream[e.target].push(e.source);
  });

  // BFS upstream (trace suppliers)
  var upSet = {};
  var queue = [clicked.id];
  upSet[clicked.id] = true;
  while (queue.length > 0) {
    var curr = queue.shift();
    (upstream[curr] || []).forEach(function(src) {
      if (!upSet[src]) { upSet[src] = true; queue.push(src); }
    });
  }

  // BFS downstream (trace dependents)
  var downSet = {};
  queue = [clicked.id];
  downSet[clicked.id] = true;
  while (queue.length > 0) {
    var curr2 = queue.shift();
    (downstream[curr2] || []).forEach(function(tgt) {
      if (!downSet[tgt]) { downSet[tgt] = true; queue.push(tgt); }
    });
  }

  var allHighlighted = {};
  for (var k in upSet) allHighlighted[k] = true;
  for (var k2 in downSet) allHighlighted[k2] = true;

  // Apply highlights
  d3.selectAll('.mineral-graph-node').classed('dimmed', function(d) {
    return !allHighlighted[d.id];
  }).classed('highlighted', function(d) {
    return !!allHighlighted[d.id];
  });

  d3.selectAll('.mineral-graph-edge').each(function(e) {
    var el = d3.select(this);
    var srcUp = upSet[e.source] && upSet[e.target];
    var srcDown = downSet[e.source] && downSet[e.target];
    el.classed('dimmed', !srcUp && !srcDown);
    el.classed('highlighted-up', srcUp && !srcDown);
    el.classed('highlighted-down', srcDown && !srcUp);
    if (srcUp && srcDown) { el.classed('highlighted-up', true); }
  });

  // Show info panel
  showGraphInfoPanel(clicked, upSet, downSet);
}

function showGraphInfoPanel(node, upSet, downSet) {
  var panel = document.getElementById('psi-graph-info-panel');
  var title = document.getElementById('psi-graph-info-title');
  var body = document.getElementById('psi-graph-info-body');

  title.textContent = node.name;
  title.style.color = node.fill;

  var html = '';
  html += '<div style="margin-bottom:6px;">';
  html += '<span style="background:' + node.fill + '22; color:' + node.fill + '; padding:2px 8px; border-radius:8px; font-size:10px; font-weight:600;">' + node.riskLevel.toUpperCase() + '</span>';
  html += ' <span style="background:' + node.border.color + '22; color:' + node.border.color + '; padding:2px 8px; border-radius:8px; font-size:10px;">' + node.type.toUpperCase() + '</span>';
  if (node.depType) {
    var badge = node.depType === 'indirect' ? '\uD83D\uDD17 INDIRECT' : '\uD83C\uDF41 DIRECT';
    var badgeColor = node.depType === 'indirect' ? '#8b5cf6' : '#00d4ff';
    html += ' <span style="background:' + badgeColor + '22; color:' + badgeColor + '; padding:2px 8px; border-radius:8px; font-size:10px;">' + badge + '</span>';
  }
  html += '</div>';

  if (node.country) html += '<div><strong>Country:</strong> ' + esc(node.country) + '</div>';
  if (node.owner) html += '<div><strong>Owner:</strong> ' + esc(node.owner) + '</div>';
  if (node.oem) html += '<div><strong>OEM:</strong> ' + esc(node.oem) + ' (' + esc(node.oem_country || '') + ')</div>';
  if (node.production) html += '<div><strong>Production:</strong> ' + node.production.toLocaleString() + ' t/yr</div>';
  if (node.capacity) html += '<div><strong>Capacity:</strong> ' + node.capacity.toLocaleString() + ' t/yr</div>';
  if (node.cobalt_pct) html += '<div><strong>Cobalt:</strong> ' + node.cobalt_pct + '%</div>';
  if (node.kg_yr) html += '<div><strong>CAF demand:</strong> ' + node.kg_yr + ' kg/yr</div>';
  if (node.fleet_note) html += '<div><strong>Fleet:</strong> ' + esc(node.fleet_note) + '</div>';
  if (node.use) html += '<div><strong>Use:</strong> ' + esc(node.use) + '</div>';

  var upCount = Object.keys(upSet).length - 1;
  var downCount = Object.keys(downSet).length - 1;
  html += '<div style="margin-top:8px; padding-top:6px; border-top:1px solid var(--border); font-size:11px;">';
  if (upCount > 0) html += '<div style="color:#00d4ff;">\u25B2 Upstream suppliers: ' + upCount + ' nodes</div>';
  if (downCount > 0) html += '<div style="color:#f59e0b;">\u25BC Downstream dependents: ' + downCount + ' nodes</div>';
  html += '</div>';

  body.innerHTML = html;
  panel.style.display = '';
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add click-to-trace highlighting + info panel for mineral Knowledge Graph"
```

---

### Task 5: Verify Full Flow

- [ ] **Step 1: Restart server and test**

```bash
# Kill old processes and start fresh
taskkill //F //IM python.exe; sleep 2
cd "C:/Users/William Dennis/weapons-tracker"
python -m src.main
```

Open http://localhost:8000, navigate to Supply Chain → Knowledge Graph. Verify:
1. Mineral dropdown appears with 30 minerals (Cobalt has a star)
2. Selecting "Cobalt" shows a 5-tier layered graph (mines → refineries → alloys → engines → platforms)
3. Nodes are colored by risk level (red=critical, amber=high, green=low)
4. Node borders show adversary (red border) vs NATO-allied (blue border)
5. Hovering shows tooltip with name, type, country, risk
6. Clicking a node dims unrelated nodes and highlights the upstream (cyan) and downstream (amber) path
7. Info panel appears on the right with node details
8. Selecting "All Minerals" reverts to the existing force-directed graph
9. No console errors

- [ ] **Step 2: Final commit**

```bash
git add src/static/index.html
git commit -m "feat: complete per-mineral Knowledge Graph (Cobalt prototype)

5-tier layered D3 graph: mines → refineries → alloys → engines → platforms
with risk-colored fills, adversary/allied border colors, click-to-trace
upstream/downstream dependency highlighting, and info panel.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```
