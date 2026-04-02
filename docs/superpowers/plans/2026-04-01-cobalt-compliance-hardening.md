# Cobalt Compliance Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix stale compliance data, add cobalt-specific evidence to the compliance page, and harden alert/confidence/scenario/forecast code for honest compliance claims.

**Architecture:** 8 tasks across 4 tiers. Tiers 1-2 are data/HTML fixes. Tier 3 is Python code fixes with TDD. Tier 4 is stretch enhancements. Each task is independently committable.

**Tech Stack:** Python 3.9+ (FastAPI, pytest), JavaScript (inline in index.html), Markdown (compliance-matrix.md)

**Spec:** `docs/superpowers/specs/2026-04-01-cobalt-compliance-hardening-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `docs/compliance-matrix.md` | External-facing compliance matrix — stats, Q1-Q22, data feeds, taxonomy, over-delivery |
| `src/static/index.html` (lines 11726-11946) | COMPLIANCE_DATA + COMPLIANCE_EXTRAS arrays, renderCompliance() |
| `src/analysis/cobalt_alert_engine.py` | GDELT + rule-based cobalt alert generation |
| `src/analysis/confidence.py` | Glass Box confidence scoring + triangulation |
| `src/analysis/scenario_engine.py` (line 435) | Likelihood scaling in _compute_impact() |
| `src/analysis/cobalt_forecasting.py` (lines 246-247) | Forecast confidence formula in _compute_price_forecast() |
| `tests/test_alert_engine.py` | NEW — alert engine tests |
| `tests/test_confidence_triangulation.py` | EXTEND — temporal decay tests |
| `tests/test_scenario_engine.py` | EXTEND — likelihood scaling tests |
| `tests/test_cobalt_forecasting.py` | NEW — forecast confidence tests |

---

### Task 1: Update compliance-matrix.md Stats and Stale References

**Files:**
- Modify: `docs/compliance-matrix.md`

- [ ] **Step 1: Update header stats**

Change line 6:
```markdown
**Status:** 155+ API Endpoints | 57 Active Data Sources | 310 Automated Tests
```

- [ ] **Step 2: Fix Q10 row**

In the Q10 row of the requirements table (Section 1), change:
```
| **Q10** | **Visualization & UI** — COP, Risk-Impact Matrix, 10-second rule | Strategic COP, Tactical Risk-Impact, Operational Dossier, 10-Second Rule | 9-tab dashboard, Leaflet maps, D3.js knowledge graph, Chart.js charts, taxonomy strip on landing page, Action Centre, live UTC clock | **GOOD** |
```
to:
```
| **Q10** | **Visualization & UI** — COP, Risk-Impact Matrix, 10-second rule | Strategic COP, Tactical Risk-Impact, Operational Dossier, 10-Second Rule | 7-tab dashboard, CesiumJS 3D globes (Arctic + Supply Chain), D3.js knowledge graph, Chart.js charts, taxonomy strip on landing page, Action Centre, live UTC clock | **GOOD** |
```

- [ ] **Step 3: Fix Q13 COA count**

In the Q13 row, change `41-entry COA playbook` to `191-entry COA playbook` and `129+ active recommendations` to `191-entry playbook with active recommendations`.

- [ ] **Step 4: Fix Q7 feed counts**

Search for all occurrences of `45 active` in the file and replace with `57 active`. There are approximately 3 occurrences (header area, Q7 row, summary).

- [ ] **Step 5: Fix over-delivery items**

Item #3: Change `Live worldwide military flight tracking (529 unique aircraft)` to `Live worldwide military flight tracking (4 ADS-B sources, parallel fetch)`.

Item #5: Change `Arms trade flow network visualization (D3.js interactive)` to `Arms trade flow visualization (CesiumJS globe arcs, Arctic + Supply Chain globes)`.

- [ ] **Step 6: Fix PDF page count**

Search for `7-page` and change to `8-page` (Q20 row and over-delivery #6).

- [ ] **Step 7: Fix data feed table row 32**

Change `adsb.lol + OpenSky Network (Arctic)` to `adsb.lol + adsb.fi + Airplanes.live + ADSB One (4 sources)`.

- [ ] **Step 8: Fix data feed summary total**

Update the summary table at the bottom of Section 2 to show correct totals. Update the line:
```
| **TOTAL** | **40 feeds** | **39 live + 4 deferred + 2 partial** | **97% of external feeds operational** |
```
to:
```
| **TOTAL** | **45 feeds** | **43 live + 4 deferred + 2 partial** | **96% of external feeds operational** |
```

- [ ] **Step 9: Commit**

```bash
git add docs/compliance-matrix.md
git commit -m "fix: update compliance-matrix.md to current stats (155+ endpoints, 310 tests, 57 sources, 7 tabs)"
```

---

### Task 2: Fix COMPLIANCE_DATA Stale References in index.html

**Files:**
- Modify: `src/static/index.html` (lines 11726-11930)

- [ ] **Step 1: Fix Q1 feed count**

Line 11731 — change `56 active feeds` to `57 active feeds`:
```javascript
{item:'Sense-Make Sense-Decide-Act workflow',status:'compliant',component:'insights_routes.py, mitigation_playbook.py',note:'Automated sensing (57 active feeds) → analysis (risk taxonomy) → COA generation → action tracking'},
```

- [ ] **Step 2: Fix Q4 NSN status to partial**

Line 11756 — change `status:'compliant'` to `status:'partial'` and update the note:
```javascript
{item:'NATO Stock Number (NSN) support',status:'partial',component:'models.py, persistence.py',note:'NSN column (String 13-digit, indexed) on SupplyChainNode. Illustrative NSNs in demo — real data requires NMCRL access at DND deployment. Architecture ready.'},
```

- [ ] **Step 3: Fix Q9 PDF page count**

Line 11816 — change `7-page PDF` to `8-page PDF`:
```javascript
{item:'Exportable briefing templates',status:'compliant',component:'briefing_generator.py',note:'8-page PDF export with customizable sections'},
```

- [ ] **Step 4: Fix Q11 scheduler job count**

Line 11835 — change `9 jobs` to `25 jobs`:
```javascript
{item:'24/7 automated monitoring',status:'compliant',component:'scheduler.py',note:'APScheduler: 25 jobs running continuously (5min to weekly intervals)'},
```

- [ ] **Step 5: Fix Q20 PDF page count and endpoint count**

Line 11909 — change `7-page` to `8-page`:
```javascript
{item:'PDF export',status:'compliant',component:'briefing_generator.py',note:'8-page intelligence briefing PDF with one-click download'},
```

Line 11912 — change `118 endpoints` to `155+ endpoints`:
```javascript
{item:'JSON/API access',status:'compliant',component:'src/api/ (155+ endpoints)',note:'155+ RESTful API endpoints with OpenAPI/Swagger docs at /docs',tab:'/docs'},
```

- [ ] **Step 6: Commit**

```bash
git add src/static/index.html
git commit -m "fix: update COMPLIANCE_DATA stale stats (NSN partial, 57 feeds, 25 jobs, 155+ endpoints)"
```

---

### Task 3: Add Cobalt Evidence to COMPLIANCE_DATA and COMPLIANCE_EXTRAS

**Files:**
- Modify: `src/static/index.html` (lines 11726-11946)

- [ ] **Step 1: Add cobalt sub-items to Q2**

After line 11740 (the last sub in Q2), add a new cobalt-specific sub:
```javascript
      {item:'Cobalt: Mine-to-platform network mapping',status:'compliant',component:'mineral_supply_chains.py',note:'9 mines → 9 refineries → 8 alloys → 7 CAF platforms with ownership chains traced via FOCI scoring',tab:'supply-chain'},
```

- [ ] **Step 2: Add cobalt sub-items to Q3**

After line 11747 (the last sub in Q3), add:
```javascript
      {item:'Cobalt: Per-tier confidence with source counts',status:'compliant',component:'confidence.py, mineral_supply_chains.py',note:'Mining=HIGH (BGS+USGS+NRCan+Comtrade), Processing=HIGH (USGS+Cobalt Institute+filings), Alloy=HIGH (AMS specs), Platform=MEDIUM (DND fleet data, derived)',tab:'supply-chain'},
```

- [ ] **Step 3: Add cobalt sub-items to Q4**

After line 11756 (the NSN sub in Q4), add:
```javascript
      {item:'Cobalt: 4 HS codes with bilateral trade',status:'compliant',component:'comtrade.py',note:'HS 2605 (ore), 810520 (unwrought), 810590 (wrought), 282200 (oxides) — 10 bilateral corridors, buyer-side mirror for DRC',tab:'supply-chain'},
```

- [ ] **Step 4: Add cobalt sub-items to Q5**

After line 11776 (the last sub in Q5), add:
```javascript
      {item:'Cobalt: 13-cat taxonomy scored per entity',status:'compliant',component:'mineral_supply_chains.py',note:'All 18 cobalt mines + refineries have entity-level DND taxonomy scores with KPIs (FOCI 8-98, financial, political, manufacturing)',tab:'supply-chain'},
```

- [ ] **Step 5: Add cobalt sub-items to Q8**

After line 11808 (the last sub in Q8), add:
```javascript
      {item:'Cobalt: Active triangulation (BGS vs USGS vs NRCan vs Comtrade)',status:'compliant',component:'confidence.py',note:'Pairwise cross-check with discrepancy detection (>25% warning, >50% critical). Live HHI computation from BGS data.',tab:'supply-chain'},
```

- [ ] **Step 6: Add cobalt sub-items to Q11**

After line 11838 (the last sub in Q11), add:
```javascript
      {item:'Cobalt: GDELT + rule-based alert engine',status:'compliant',component:'cobalt_alert_engine.py',note:'8 GDELT keyword queries + 4 rule triggers (HHI concentration, China refining dominance, paused ops, data discrepancies). 30-min cache cycle.',tab:'supply-chain'},
```

- [ ] **Step 7: Add cobalt sub-items to Q12**

After line 11846 (the last sub in Q12), add:
```javascript
      {item:'Cobalt: Live IMF PCOBALT price forecasting',status:'compliant',component:'cobalt_forecasting.py',note:'Linear regression on IMF quarterly data, R² goodness-of-fit, 90% prediction intervals, volatility bands, optimistic/baseline/pessimistic fan chart',tab:'supply-chain'},
      {item:'Cobalt: Multi-variable scenario sandbox',status:'compliant',component:'scenario_engine.py',note:'5 stackable disruption layers, 4-tier Sankey cascade, 5 preset compound scenarios, Likelihood x Impact scoring, COA comparison',tab:'supply-chain'},
```

- [ ] **Step 8: Add cobalt sub-items to Q13**

After line 11855 (the last sub in Q13), add:
```javascript
      {item:'Cobalt: 10-entry risk register with COA links',status:'compliant',component:'mineral_supply_chains.py, psi_routes.py',note:'Status lifecycle (Open → In Progress → Mitigated → Closed), DB-persisted, linked to sufficiency COAs, CSV export',tab:'supply-chain'},
```

- [ ] **Step 9: Add Cobalt Deep Intelligence to COMPLIANCE_EXTRAS**

After line 11945 (the last entry in COMPLIANCE_EXTRAS, before the closing `];`), add:
```javascript
  {name:'Cobalt Supply Chain Deep Intelligence', desc:'Full Rocks-to-Rockets cobalt coverage: 9 named mines with FOCI/Z-score dossiers (FOCI 8-98), 9 refineries, 8 defence alloys (Waspaloy/CMSX-4/Stellite), 6 shipping corridors, live IMF PCOBALT forecasting with R² and prediction intervals, GDELT + rule-based alert engine, active BGS/USGS/NRCan triangulation, 10 bilateral Comtrade corridors (4 HS codes), DND 13-category risk taxonomy per entity. Demonstrates full DMPP 11 compliance at the individual mineral level.', component:'mineral_supply_chains.py, cobalt_forecasting.py, cobalt_alert_engine.py, confidence.py', tab:'supply-chain'},
```

- [ ] **Step 10: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add cobalt-specific compliance evidence to COMPLIANCE_DATA and COMPLIANCE_EXTRAS"
```

---

### Task 4: Add Data Freshness to Compliance Page

**Files:**
- Modify: `src/static/index.html` (renderCompliance function, ~line 12039)

- [ ] **Step 1: Add freshness rendering after compliance stats**

After the compliance stats are rendered (after line 12039 which closes the stats HTML), add a freshness fetch block. Insert after the line ending `'</div>';` that closes the Beyond Contract stat:

```javascript
  // Cobalt data freshness
  fetch('/validation/health').then(function(r) { return r.json(); }).then(function(health) {
    var freshRow = document.getElementById('compliance-freshness');
    if (!freshRow) return;
    var keys = ['imf_cobalt', 'bgs_minerals', 'gdelt_news', 'comtrade'];
    var labels = {'imf_cobalt':'IMF PCOBALT', 'bgs_minerals':'BGS Minerals', 'gdelt_news':'GDELT News', 'comtrade':'UN Comtrade'};
    var html = '<span style="color:var(--text-dim);margin-right:12px;">Cobalt Data Freshness:</span>';
    keys.forEach(function(k) {
      var h = health[k] || {};
      var ts = h.last_fetch || h.last_updated || 'N/A';
      if (ts && ts.length > 10) ts = ts.substring(0, 10);
      var color = h.status === 'ok' ? 'var(--accent3)' : 'var(--accent4)';
      html += '<span style="margin-right:16px;"><span style="color:' + color + ';">\u25CF</span> ' + (labels[k]||k) + ' <span style="color:var(--text-dim);">(' + esc(ts) + ')</span></span>';
    });
    freshRow.innerHTML = html;
  }).catch(function() {});
```

- [ ] **Step 2: Add the freshness container HTML**

Find the compliance summary container in the HTML (search for `id="compliance-summary"`). After the summary div, add:
```html
<div id="compliance-freshness" style="padding:8px 16px;font-size:0.82rem;font-family:var(--font-mono);"></div>
```

To find the right location, search for `compliance-summary` in the HTML template section (not the JS). It will be in the compliance tab HTML structure. Add the freshness div right after the summary div closes.

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat: add cobalt data freshness indicators to compliance page"
```

---

### Task 5: Alert Engine — Run All 8 GDELT Queries + Alert Aging

**Files:**
- Modify: `src/analysis/cobalt_alert_engine.py`
- Create: `tests/test_alert_engine.py`

- [ ] **Step 1: Write failing test for all 8 queries**

Create `tests/test_alert_engine.py`:
```python
"""Tests for cobalt alert engine."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.analysis.cobalt_alert_engine import (
    COBALT_GDELT_QUERIES,
    generate_gdelt_alerts,
    generate_rule_alerts,
    run_cobalt_alert_engine,
)


class TestGDELTQueryCoverage:
    """Verify all 8 GDELT queries are executed."""

    @pytest.mark.asyncio
    async def test_all_8_queries_executed(self):
        """All 8 COBALT_GDELT_QUERIES must be passed to search_articles."""
        queries_called = []

        async def mock_search(query, timespan="1440", max_records=5):
            queries_called.append(query)
            return []

        with patch("src.analysis.cobalt_alert_engine.GDELTArmsNewsClient") as MockClient:
            instance = MockClient.return_value
            instance.search_articles = mock_search
            await generate_gdelt_alerts()

        assert len(queries_called) == 8, f"Expected 8 queries, got {len(queries_called)}: {queries_called}"
        for q in COBALT_GDELT_QUERIES:
            assert q in queries_called, f"Query not called: {q}"

    @pytest.mark.asyncio
    async def test_query_count_matches_constant(self):
        assert len(COBALT_GDELT_QUERIES) == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_alert_engine.py::TestGDELTQueryCoverage::test_all_8_queries_executed -v`
Expected: FAIL — only 4 queries called (due to `[:4]` slice on line 36)

- [ ] **Step 3: Fix the GDELT query loop**

In `src/analysis/cobalt_alert_engine.py`, line 36, change:
```python
    for query in COBALT_GDELT_QUERIES[:4]:
```
to:
```python
    for query in COBALT_GDELT_QUERIES:
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_alert_engine.py::TestGDELTQueryCoverage -v`
Expected: PASS

- [ ] **Step 5: Write failing test for alert aging**

Add to `tests/test_alert_engine.py`:
```python
class TestAlertAging:
    """Verify alert severity is reduced for old alerts."""

    def test_fresh_alert_keeps_severity(self):
        """Alert from today should keep its original severity."""
        from src.analysis.cobalt_alert_engine import _apply_aging
        alert = {"severity": 5, "timestamp": datetime.now(timezone.utc).isoformat()}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 5
        assert result.get("aged") is not True

    def test_8_day_old_alert_reduced(self):
        """Alert >7 days old should have severity reduced by 1."""
        from src.analysis.cobalt_alert_engine import _apply_aging
        old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 4
        assert result["aged"] is True

    def test_35_day_old_alert_capped_at_1(self):
        """Alert >30 days old should be capped at severity 1."""
        from src.analysis.cobalt_alert_engine import _apply_aging
        old_ts = (datetime.now(timezone.utc) - timedelta(days=35)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is not None
        assert result["severity"] == 1
        assert result["aged"] is True

    def test_95_day_old_alert_excluded(self):
        """Alert >90 days old should return None (excluded)."""
        from src.analysis.cobalt_alert_engine import _apply_aging
        old_ts = (datetime.now(timezone.utc) - timedelta(days=95)).isoformat()
        alert = {"severity": 5, "timestamp": old_ts}
        result = _apply_aging(alert)
        assert result is None
```

- [ ] **Step 6: Run aging tests to verify they fail**

Run: `python -m pytest tests/test_alert_engine.py::TestAlertAging -v`
Expected: FAIL — `_apply_aging` does not exist

- [ ] **Step 7: Implement _apply_aging and wire into run_cobalt_alert_engine**

Add the `_apply_aging` function before `run_cobalt_alert_engine` in `cobalt_alert_engine.py`:

```python
def _apply_aging(alert: dict) -> dict | None:
    """Apply age-based severity demotion to an alert.

    Returns None if alert should be excluded (>90 days old).
    """
    ts_str = alert.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return alert  # Can't parse — keep as-is

    age_days = (datetime.now(timezone.utc) - ts).days

    if age_days > 90:
        return None
    elif age_days > 30:
        alert = {**alert, "severity": min(alert.get("severity", 1), 1), "aged": True}
    elif age_days > 7:
        alert = {**alert, "severity": max(1, alert.get("severity", 1) - 1), "aged": True}

    return alert
```

Then in `run_cobalt_alert_engine`, after deduplication (the `deduped` list is built), apply aging:

Replace the section that sets `_cached_alerts = deduped` with:
```python
        aged: list[dict] = []
        for a in deduped:
            result = _apply_aging(a)
            if result is not None:
                aged.append(result)

        logger.info("Cobalt Alert Engine: %d total (%d GDELT, %d rules, %d deduped, %d after aging)",
                    len(all_alerts), len(gdelt_alerts), len(rule_alerts), len(deduped), len(aged))
        _cached_alerts = aged
        _cache_timestamp = datetime.now(timezone.utc)
        return aged
```

- [ ] **Step 8: Run all alert tests**

Run: `python -m pytest tests/test_alert_engine.py -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add src/analysis/cobalt_alert_engine.py tests/test_alert_engine.py
git commit -m "feat: alert engine runs all 8 GDELT queries + alert aging (7/30/90 day demotion)"
```

---

### Task 6: Confidence Temporal Decay

**Files:**
- Modify: `src/analysis/confidence.py`
- Modify: `tests/test_confidence_triangulation.py`

- [ ] **Step 1: Write failing test for temporal decay**

Add to `tests/test_confidence_triangulation.py`:
```python
from datetime import datetime


class TestTemporalDecay:
    """Verify old sources are down-weighted in triangulation."""

    def test_recent_sources_full_weight(self):
        """Sources from current or last year should not be penalized."""
        current_year = datetime.now().year
        sources = [
            SourceDataPoint("USGS MCS", 170000, current_year, "live"),
            SourceDataPoint("BGS WMS", 168000, current_year, "live"),
            SourceDataPoint("NRCan", 165000, current_year - 1, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["confidence_score"] >= 80  # No penalty

    def test_old_sources_reduce_confidence(self):
        """Sources >2 years old should reduce confidence score."""
        current_year = datetime.now().year
        sources = [
            SourceDataPoint("USGS MCS", 170000, current_year - 3, "live"),
            SourceDataPoint("BGS WMS", 168000, current_year - 4, "live"),
            SourceDataPoint("NRCan", 165000, current_year - 5, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        # Should be lower than 3 fresh sources which would be 85+
        assert result["confidence_score"] < 80

    def test_very_old_sources_heavy_penalty(self):
        """Sources >5 years old should get heavy penalty."""
        current_year = datetime.now().year
        sources = [
            SourceDataPoint("Old Source A", 170000, current_year - 6, "live"),
            SourceDataPoint("Old Source B", 168000, current_year - 7, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["confidence_score"] < 60
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_confidence_triangulation.py::TestTemporalDecay -v`
Expected: FAIL — old sources still get full scores

- [ ] **Step 3: Add temporal decay to triangulate_cobalt_production**

In `src/analysis/confidence.py`, in the `triangulate_cobalt_production` function, after the pairwise comparison loop (after line ~266) and before the "Best estimate" section, add freshness calculation:

Find the line `# Best estimate: median of most recent same-year group, else all values` and add before it:

```python
    # Temporal decay — down-weight old sources
    current_year = datetime.now().year
    freshness_penalties = []
    for s in sources:
        age = current_year - s.year
        if age <= 2:
            freshness_penalties.append(1.0)
        elif age <= 5:
            freshness_penalties.append(0.5)
        else:
            freshness_penalties.append(0.25)
    avg_freshness = sum(freshness_penalties) / len(freshness_penalties) if freshness_penalties else 1.0
```

Add `from datetime import datetime` at the top of the file (after the existing imports, around line 8). Check if it's already imported — if so, skip.

Then in the confidence scoring section (around line 277), apply the freshness multiplier. Replace:
```python
    if triangulated and not has_critical_disc:
        confidence_level = "high"
        confidence_score = min(80 + source_count * 5, 95)
    elif source_count >= 2 and not has_critical_disc:
        confidence_level = "medium"
        confidence_score = 60 + source_count * 5
```
with:
```python
    if triangulated and not has_critical_disc:
        confidence_level = "high"
        confidence_score = min(80 + source_count * 5, 95)
    elif source_count >= 2 and not has_critical_disc:
        confidence_level = "medium"
        confidence_score = 60 + source_count * 5
```
Then after `confidence_score = min(confidence_score, 95)` (line ~285), add:
```python
    # Apply freshness penalty
    confidence_score = round(confidence_score * avg_freshness)
    if avg_freshness < 0.7:
        confidence_level = "low" if confidence_level == "medium" else confidence_level
```

- [ ] **Step 4: Run temporal decay tests**

Run: `python -m pytest tests/test_confidence_triangulation.py::TestTemporalDecay -v`
Expected: PASS

- [ ] **Step 5: Run ALL existing confidence tests to check for regressions**

Run: `python -m pytest tests/test_confidence_triangulation.py tests/test_confidence.py -v`
Expected: ALL PASS (existing tests use year=2024 which is within 2 years of 2026)

- [ ] **Step 6: Commit**

```bash
git add src/analysis/confidence.py tests/test_confidence_triangulation.py
git commit -m "feat: add temporal decay to confidence triangulation (>2yr penalty, >5yr heavy penalty)"
```

---

### Task 7: Fix Scenario Likelihood Scaling + Forecast Confidence

**Files:**
- Modify: `src/analysis/scenario_engine.py` (line 435)
- Modify: `src/analysis/cobalt_forecasting.py` (lines 246-247)
- Modify: `tests/test_scenario_engine.py`
- Create: `tests/test_cobalt_forecasting.py`

- [ ] **Step 1: Write failing test for likelihood (no 2x scaling)**

Add to `tests/test_scenario_engine.py`:
```python
class TestLikelihoodScaling:
    """Verify likelihood uses raw probability without artificial scaling."""

    def setup_method(self):
        self.engine = ScenarioEngine("Cobalt")

    def test_single_sanctions_layer_likelihood(self):
        """Single sanctions layer at base 0.60 should produce ~0.60 likelihood, not ~0.96."""
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        likelihood = result["impact"]["likelihood"]
        # Without 2x scaling, single 0.60 layer should give ~0.60
        assert likelihood <= 0.70, f"Likelihood {likelihood} is too high — 2x scaling still active?"
        assert likelihood >= 0.50, f"Likelihood {likelihood} is too low"

    def test_two_layer_compound_likelihood(self):
        """Two layers should compound: 1 - (1-0.6)(1-0.7) = 0.88."""
        result = self.engine.run(
            layers=[
                {"type": "sanctions_expansion", "params": {"country": "China"}},
                {"type": "material_shortage", "params": {"pct": 50}},
            ],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        likelihood = result["impact"]["likelihood"]
        # 1 - (0.4 * 0.3) = 0.88
        assert 0.80 <= likelihood <= 0.95, f"Expected ~0.88, got {likelihood}"

    def test_likelihood_method_field_present(self):
        """Response should include likelihood_method field."""
        result = self.engine.run(
            layers=[{"type": "sanctions_expansion", "params": {"country": "China"}}],
            demand_surge_pct=0,
            time_horizon_months=12,
        )
        assert result["impact"].get("likelihood_method") == "combined_independent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_scenario_engine.py::TestLikelihoodScaling::test_single_sanctions_layer_likelihood -v`
Expected: FAIL — likelihood is ~0.96 due to 2x scaling

- [ ] **Step 3: Remove 2x scaling from scenario engine**

In `src/analysis/scenario_engine.py`, line 435, change:
```python
        likelihood = round(min(raw_likelihood * 2, 1.0), 2)  # Scale up to make single layers meaningful
```
to:
```python
        likelihood = round(raw_likelihood, 2)
```

Also find where `impact` dict is built (a few lines below line 435) and add the `likelihood_method` field. Find the line that starts building the impact dict (search for `"likelihood": likelihood`) and add after it:
```python
            "likelihood_method": "combined_independent",
```

- [ ] **Step 4: Run likelihood tests**

Run: `python -m pytest tests/test_scenario_engine.py::TestLikelihoodScaling -v`
Expected: PASS

- [ ] **Step 5: Run ALL scenario tests to check for regressions**

Run: `python -m pytest tests/test_scenario_engine.py -v`
Expected: ALL PASS (existing tests check `>0` or presence of fields, not exact likelihood values)

- [ ] **Step 6: Write failing test for conservative forecast confidence**

Create `tests/test_cobalt_forecasting.py`:
```python
"""Tests for cobalt forecasting confidence formula."""
from __future__ import annotations

from src.analysis.cobalt_forecasting import _compute_price_forecast


class TestForecastConfidence:
    """Verify forecast confidence is conservative and honest."""

    def _make_prices(self, n_months: int, base: float = 30000, slope: float = 100) -> list[dict]:
        """Generate synthetic monthly price data."""
        prices = []
        for i in range(n_months):
            year = 2024 + i // 12
            month = (i % 12) + 1
            prices.append({
                "date": f"{year}-{month:02d}",
                "usd_mt": base + slope * i,
            })
        return prices

    def test_mediocre_fit_low_confidence(self):
        """R²=~0.5 with 8 quarters should NOT give 70%+ confidence."""
        # Generate noisy data (mediocre fit)
        import random
        random.seed(42)
        prices = []
        for i in range(24):  # 24 months = 8 quarters
            year = 2024 + i // 12
            month = (i % 12) + 1
            noise = random.uniform(-5000, 5000)
            prices.append({"date": f"{year}-{month:02d}", "usd_mt": 30000 + 200 * i + noise})

        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf < 55, f"Confidence {conf}% is too high for mediocre R² fit"

    def test_strong_fit_reasonable_confidence(self):
        """Strong linear trend (R²≈1.0) with 12 quarters should give good confidence."""
        prices = self._make_prices(36, base=30000, slope=200)
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert 50 <= conf <= 85, f"Confidence {conf}% out of expected range for strong fit"

    def test_few_quarters_low_confidence(self):
        """Only 2 quarters of data should give low confidence regardless of fit."""
        prices = self._make_prices(6, base=30000, slope=200)  # 6 months = 2 quarters
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf < 40, f"Confidence {conf}% is too high for only 2 quarters of data"

    def test_confidence_never_exceeds_85(self):
        """Confidence should cap at 85% (linear regression has inherent limits)."""
        prices = self._make_prices(60, base=30000, slope=200)  # 20 quarters perfect data
        result = _compute_price_forecast(prices, source="Test")
        conf = result["price_forecast"]["confidence_pct"]
        assert conf <= 85, f"Confidence {conf}% exceeds 85% cap"
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `python -m pytest tests/test_cobalt_forecasting.py -v`
Expected: FAIL — old formula gives inflated confidence

- [ ] **Step 8: Fix forecast confidence formula**

In `src/analysis/cobalt_forecasting.py`, find the confidence rating block (around line 246). Replace:
```python
    if r_squared >= 0.7 and n_quarters >= 8:
        forecast_confidence = "high"
        forecast_confidence_pct = min(90, round(r_squared * 85 + n_quarters))
    elif r_squared >= 0.4 and n_quarters >= 4:
        forecast_confidence = "medium"
        forecast_confidence_pct = min(75, round(r_squared * 60 + n_quarters))
    else:
        forecast_confidence = "low"
        forecast_confidence_pct = min(50, round(r_squared * 40 + n_quarters))
```

with:
```python
    # Conservative confidence: R² must be >0.3 to contribute meaningfully
    r2_component = max(0, (r_squared - 0.3)) * 100  # 0-70 range
    data_component = min(15, n_quarters * 1.5)       # 0-15 range
    forecast_confidence_pct = int(min(85, r2_component + data_component))
    if forecast_confidence_pct >= 60:
        forecast_confidence = "high"
    elif forecast_confidence_pct >= 35:
        forecast_confidence = "medium"
    else:
        forecast_confidence = "low"
```

- [ ] **Step 9: Run forecast tests**

Run: `python -m pytest tests/test_cobalt_forecasting.py -v`
Expected: ALL PASS

- [ ] **Step 10: Run full test suite for regressions**

Run: `python -m pytest tests/ -x --timeout=60 -q`
Expected: 310+ pass (any pre-existing `test_generate_coas_from_supplier_risks` failure is known)

- [ ] **Step 11: Commit**

```bash
git add src/analysis/scenario_engine.py src/analysis/cobalt_forecasting.py tests/test_scenario_engine.py tests/test_cobalt_forecasting.py
git commit -m "fix: remove 2x likelihood scaling + conservative forecast confidence formula"
```

---

### Task 8: Forecast Accuracy Tracking Stub

**Files:**
- Modify: `src/analysis/cobalt_forecasting.py`
- Modify: `tests/test_cobalt_forecasting.py`

- [ ] **Step 1: Write failing test for snapshot storage**

Add to `tests/test_cobalt_forecasting.py`:
```python
import json
import os
import tempfile


class TestForecastSnapshot:
    """Verify forecast snapshots are saved for future backtesting."""

    def test_snapshot_writes_json(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            forecast = {
                "price_forecast": {
                    "pct_change": 5.0,
                    "direction": "up",
                    "confidence_pct": 45,
                    "r_squared": 0.6,
                },
                "price_history": [{"quarter": "Q1 2026", "usd_mt": 30000, "type": "forecast"}],
            }
            _store_forecast_snapshot(forecast, path=path)
            assert os.path.exists(path)
            with open(path) as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert "snapshot_date" in data[0]
            assert data[0]["price_forecast"]["r_squared"] == 0.6

    def test_snapshot_appends_not_overwrites(self):
        from src.analysis.cobalt_forecasting import _store_forecast_snapshot
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "forecast_history.json")
            forecast = {"price_forecast": {"pct_change": 5.0, "r_squared": 0.6}, "price_history": []}
            _store_forecast_snapshot(forecast, path=path)
            _store_forecast_snapshot(forecast, path=path)
            with open(path) as f:
                data = json.load(f)
            assert len(data) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cobalt_forecasting.py::TestForecastSnapshot -v`
Expected: FAIL — `_store_forecast_snapshot` does not exist

- [ ] **Step 3: Implement _store_forecast_snapshot**

Add to `src/analysis/cobalt_forecasting.py`, before the `compute_cobalt_forecast` function:

```python
import json
import os


FORECAST_HISTORY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "cobalt_forecast_history.json"
)


def _store_forecast_snapshot(
    forecast: dict,
    path: str | None = None,
) -> None:
    """Save a forecast snapshot for future backtesting.

    Appends to a JSON array file. Each entry has a snapshot_date
    and the forecast predictions for comparison against actuals.
    """
    path = path or FORECAST_HISTORY_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)

    existing: list[dict] = []
    if os.path.exists(path):
        try:
            with open(path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    snapshot = {
        "snapshot_date": datetime.utcnow().isoformat(),
        "price_forecast": forecast.get("price_forecast", {}),
        "predictions": [
            p for p in forecast.get("price_history", []) if p.get("type") == "forecast"
        ],
    }
    existing.append(snapshot)

    with open(path, "w") as f:
        json.dump(existing, f, indent=2)
```

- [ ] **Step 4: Wire snapshot into compute_cobalt_forecast**

In the `compute_cobalt_forecast` function, just before the `return` statement at the end, add:

```python
    # Store snapshot for future backtesting
    try:
        _store_forecast_snapshot(result)
    except Exception:
        logger.warning("Failed to store forecast snapshot", exc_info=True)
```

Where `result` is the dict being returned (it's built inline — assign it to a variable first if needed, or just call `_store_forecast_snapshot` with the same dict structure).

- [ ] **Step 5: Run snapshot tests**

Run: `python -m pytest tests/test_cobalt_forecasting.py::TestForecastSnapshot -v`
Expected: PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -x --timeout=60 -q`
Expected: ALL PASS (plus pre-existing known failure)

- [ ] **Step 7: Commit**

```bash
git add src/analysis/cobalt_forecasting.py tests/test_cobalt_forecasting.py
git commit -m "feat: add forecast accuracy tracking stub (JSON snapshot for backtesting)"
```

---

## Verification

After all 8 tasks are complete:

1. Run full test suite: `python -m pytest tests/ --timeout=60 -q`
2. Start server: `python -m src.main` and verify:
   - Compliance tab shows updated stats and cobalt evidence sub-items
   - Data freshness row appears on compliance page
   - Supply Chain → Alerts shows alerts from all 8 GDELT queries
3. Verify `docs/compliance-matrix.md` has no remaining stale references
