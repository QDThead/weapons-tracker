# Cobalt Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all 14 remaining gaps found in the second compliance audit — persistence, Glass Box, bilingual, exports, accessibility, and data integrity.

**Architecture:** 14 independent tasks grouped by area. Each task modifies 1-2 files. Tasks can be executed in any order except N2 depends on N1.

**Tech Stack:** Python (FastAPI, fpdf2, SQLAlchemy), vanilla JS, ARIA attributes

---

### Task 1: N1 — Persist alert + register actions to database instead of in-memory dicts

**Files:**
- Modify: `src/api/psi_routes.py:870-928`

Replace the in-memory `_cobalt_alert_actions` and `_cobalt_register_status` dicts with database-backed storage using the existing `MitigationAction` table.

- [ ] **Step 1: Rewrite the 4 Cobalt endpoints to use the database**

Replace lines 870-928 in `psi_routes.py` with DB-backed versions. Use `MitigationAction` table for both alert actions and register status — the table already has `risk_source`, `risk_entity`, `risk_dimension`, `status`, `notes`, and `coa_action` fields.

For alert actions, store as: `risk_source="cobalt_alert"`, `risk_entity=alert_id`, `risk_dimension=action_type`, `coa_action=action`, `notes=analyst`, `status=action`.

For register status, store as: `risk_source="cobalt_register"`, `risk_entity=risk_id`, `risk_dimension="status_override"`, `status=new_status`, `notes=analyst`.

```python
class CobaltAlertAction(BaseModel):
    alert_id: str
    action: str
    analyst: str = ""

@router.post("/alerts/cobalt/action")
async def cobalt_alert_action(req: CobaltAlertAction):
    """Record an analyst action on a Cobalt watchtower alert."""
    session = SessionLocal()
    try:
        from src.storage.persistence import PersistenceService
        svc = PersistenceService(session)
        svc.upsert_mitigation_action(
            risk_source="cobalt_alert",
            risk_entity=req.alert_id,
            risk_dimension=req.action,
            risk_score=0.0,
            coa_action=req.action,
            coa_priority="high",
            status=req.action,
            notes=req.analyst,
        )
        return {"status": "recorded", "alert_id": req.alert_id, "action": req.action, "analyst": req.analyst, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("cobalt_alert_action failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()

@router.get("/alerts/cobalt/actions")
async def get_cobalt_alert_actions():
    """Get all recorded Cobalt alert actions."""
    session = SessionLocal()
    try:
        from src.storage.models import MitigationAction
        rows = session.query(MitigationAction).filter_by(risk_source="cobalt_alert").all()
        return [{"alert_id": r.risk_entity, "action": r.risk_dimension, "analyst": r.notes or "", "timestamp": r.updated_at.isoformat() if r.updated_at else ""} for r in rows]
    finally:
        session.close()


class RegisterStatusUpdate(BaseModel):
    risk_id: str
    new_status: str
    analyst: str = ""

@router.patch("/register/cobalt/{risk_id}")
async def update_cobalt_register_status(risk_id: str, update: RegisterStatusUpdate):
    """Update status of a Cobalt risk register entry."""
    session = SessionLocal()
    try:
        from src.storage.persistence import PersistenceService
        svc = PersistenceService(session)
        svc.upsert_mitigation_action(
            risk_source="cobalt_register",
            risk_entity=risk_id,
            risk_dimension="status_override",
            risk_score=0.0,
            coa_action=update.new_status,
            coa_priority="medium",
            status=update.new_status,
            notes=update.analyst,
        )
        return {"status": "updated", "risk_id": risk_id, "new_status": update.new_status, "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error("update_cobalt_register_status failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()

@router.get("/register/cobalt/status")
async def get_cobalt_register_status():
    """Get all Cobalt risk register status overrides."""
    session = SessionLocal()
    try:
        from src.storage.models import MitigationAction
        rows = session.query(MitigationAction).filter_by(risk_source="cobalt_register").all()
        return {r.risk_entity: {"risk_id": r.risk_entity, "status": r.status, "analyst": r.notes or "", "timestamp": r.updated_at.isoformat() if r.updated_at else ""} for r in rows}
    finally:
        session.close()
```

Also remove the old `_cobalt_alert_actions` and `_cobalt_register_status` module-level dicts. Keep the `@router.get("/alerts/cobalt/live")` endpoint unchanged.

- [ ] **Step 2: Run tests and commit**

Run: `python -m pytest tests/test_scenario_api.py tests/test_mitigation.py -v --tb=short`

```bash
git add src/api/psi_routes.py
git commit -m "fix(N1): persist Cobalt alert actions and register status to database"
```

---

### Task 2: N2 — Merge register status overrides on page reload

**Files:**
- Modify: `src/static/index.html` — `onRegisterMineralChange` function (~line 8565)

- [ ] **Step 1: Update onRegisterMineralChange to fetch and merge status overrides**

Replace the function with:

```javascript
async function onRegisterMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-register-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view risk register.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    // Merge persisted status overrides
    if (mineral.toLowerCase() === 'cobalt') {
      try {
        var statusResp = await fetch(API + '/psi/register/cobalt/status');
        if (statusResp.ok) {
          var overrides = await statusResp.json();
          (m.risk_register || []).forEach(function(r) {
            if (overrides[r.id]) r.status = overrides[r.id].status;
          });
        }
      } catch(e) { /* overrides unavailable */ }
    }
    renderRiskRegister(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Risk register data not yet available for ' + esc(mineral) + '</div>'; }
}
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N2): merge persisted register status overrides on page reload"
```

---

### Task 3: N3 — Replace hardcoded "Current User" with prompted analyst name

**Files:**
- Modify: `src/static/index.html` — `alertAcknowledge`, `alertEscalate`, `updateRegisterStatus` functions

- [ ] **Step 1: Add a cached analyst name prompt**

Add before the alert functions:

```javascript
var _analystName = '';
function getAnalystName() {
  if (!_analystName) _analystName = prompt('Enter your analyst name:') || 'Anonymous';
  return _analystName;
}
```

Then in `alertAcknowledge`, replace `analyst:'Current User'` with `analyst:getAnalystName()`.
Same for `alertEscalate` and `updateRegisterStatus`.
`alertAssign` already prompts for a name, so no change needed there.

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N3): prompt for analyst name instead of hardcoded 'Current User'"
```

---

### Task 4: N4 — Cache scheduled alert engine results

**Files:**
- Modify: `src/analysis/cobalt_alert_engine.py` — `run_cobalt_alert_engine` function

- [ ] **Step 1: Add a module-level cache**

At the top of the file (after imports), add:

```python
_cached_alerts: list[dict] = []
_cache_timestamp: datetime | None = None
```

Update `run_cobalt_alert_engine`:

```python
async def run_cobalt_alert_engine() -> list[dict]:
    """Main entry point — run both GDELT and rule-based alert generation."""
    global _cached_alerts, _cache_timestamp
    gdelt_alerts = await generate_gdelt_alerts()
    rule_alerts = generate_rule_alerts()

    all_alerts = gdelt_alerts + rule_alerts
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in all_alerts:
        key = a["title"][:50].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(a)

    _cached_alerts = deduped
    _cache_timestamp = datetime.utcnow()
    logger.info("Cobalt Alert Engine: %d total (%d GDELT, %d rules, %d deduped)",
                len(all_alerts), len(gdelt_alerts), len(rule_alerts), len(deduped))
    return deduped


def get_cached_alerts() -> tuple[list[dict], datetime | None]:
    """Return cached alerts from the last scheduled run."""
    return _cached_alerts, _cache_timestamp
```

Then update the `/alerts/cobalt/live` endpoint in `psi_routes.py` to use cache when available:

```python
@router.get("/alerts/cobalt/live")
async def get_cobalt_live_alerts():
    """Get live-generated Cobalt alerts from GDELT + rule engine."""
    from src.analysis.cobalt_alert_engine import get_cached_alerts, run_cobalt_alert_engine
    cached, ts = get_cached_alerts()
    if cached and ts and (datetime.utcnow() - ts).total_seconds() < 1800:
        return {"alerts": cached, "count": len(cached), "generated_at": ts.isoformat(), "cached": True}
    try:
        alerts = await run_cobalt_alert_engine()
        return {"alerts": alerts, "count": len(alerts), "generated_at": datetime.utcnow().isoformat(), "cached": False}
    except Exception as e:
        logger.error("Cobalt live alerts failed: %s", e)
        return {"alerts": cached or [], "count": len(cached or []), "error": "Live generation failed, showing cached"}
```

- [ ] **Step 2: Commit**

```bash
git add src/analysis/cobalt_alert_engine.py src/api/psi_routes.py
git commit -m "fix(N4): cache scheduled alert engine results for /alerts/cobalt/live"
```

---

### Task 5: N5 — Badge seed alerts as "SEEDED" vs live alerts as "LIVE"

**Files:**
- Modify: `src/static/index.html` — `renderAlertsSensing` function

- [ ] **Step 1: Add a data source badge next to each alert's timestamp**

In `renderAlertsSensing`, find the line that renders the timestamp (line ~8542):

```javascript
html += '<div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Category: <span style="color:'+c+';">' + esc(a.category) + '</span> — ' + esc(a.timestamp || '') + '</div></div>';
```

Replace with:

```javascript
    var srcBadge = a.auto_generated ? '<span style="background:rgba(16,185,129,0.1); color:var(--accent3); padding:1px 6px; border-radius:3px; font-size:9px; margin-left:6px;">LIVE</span>' : '<span style="background:rgba(139,92,246,0.1); color:var(--accent5); padding:1px 6px; border-radius:3px; font-size:9px; margin-left:6px;">SEEDED</span>';
    html += '<div style="font-size:11px; color:var(--text-dim); margin-top:2px;">Category: <span style="color:'+c+';">' + esc(a.category) + '</span> — ' + esc(a.timestamp || '') + srcBadge + '</div></div>';
```

This uses the `auto_generated: true` field that exists on alerts from `cobalt_alert_engine.py`. Static seed alerts don't have this field, so they show "SEEDED".

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N5): badge seed alerts as SEEDED and live alerts as LIVE"
```

---

### Task 6: N6 — Fetch real ML feedback stats for Analyst Feedback panel

**Files:**
- Modify: `src/static/index.html` — `renderAnalystFeedback` function

- [ ] **Step 1: Merge live ML stats into the analyst feedback display**

At the start of `renderAnalystFeedback`, after `var af = m.analyst_feedback;`, add a fetch to get real stats:

Find the `renderAnalystFeedback` function. After the null check and before the stat cards, insert a comment showing that we overlay live stats. Since `renderAnalystFeedback` is synchronous (called from an async loader), we can't await inside it. Instead, update `onFeedbackMineralChange` to fetch ML stats and pass them.

Replace `onFeedbackMineralChange`:

```javascript
async function onFeedbackMineralChange() {
  var mineral = getGlobalMineral();
  var container = document.getElementById('psi-feedback-content');
  if (!mineral) { container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Select a mineral to view analyst feedback.</div>'; return; }
  container.innerHTML = '<div style="color:var(--text-dim); text-align:center; padding:40px;">Loading...</div>';
  try {
    var resp = await fetch(API + '/globe/minerals/' + encodeURIComponent(mineral));
    if (!resp.ok) throw new Error('Not found');
    var m = await resp.json();
    // Overlay live ML stats
    try {
      var mlResp = await fetch(API + '/ml/thresholds');
      if (mlResp.ok) {
        var ml = await mlResp.json();
        if (m.analyst_feedback) {
          if (ml.feedback_count > 0) {
            m.analyst_feedback.fp_rate = Math.round(ml.false_positive_rate * 100);
            m.analyst_feedback.accuracy = Math.round((1 - ml.false_positive_rate) * 100);
          }
          m.analyst_feedback.threshold = m.analyst_feedback.threshold || {};
          m.analyst_feedback.threshold.current_z = ml.z_score_threshold;
          m.analyst_feedback.threshold.rlhf_adjusted = ml.adjusted_threshold;
          m.analyst_feedback._live_stats = true;
        }
      }
    } catch(e) { /* ML stats unavailable, use seed data */ }
    renderAnalystFeedback(m, container);
  } catch (e) { container.innerHTML = '<div class="card" style="padding:40px; text-align:center; color:var(--text-dim);">Analyst feedback data not yet available for ' + esc(mineral) + '</div>'; }
}
```

Then in `renderAnalystFeedback`, after the stat cards, add a data source badge:

After the pending review stat card and before `html += '</div>';`, add:

```javascript
  var statsBadge = af._live_stats ? '<span style="background:rgba(16,185,129,0.1); color:var(--accent3); padding:2px 6px; border-radius:3px; font-size:9px;">LIVE ML DATA</span>' : '<span style="background:rgba(139,92,246,0.1); color:var(--accent5); padding:2px 6px; border-radius:3px; font-size:9px;">BASELINE DATA</span>';
  html += '<div style="text-align:center; margin-top:6px;">' + statsBadge + '</div>';
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N6): overlay live ML feedback stats on Analyst Feedback panel"
```

---

### Task 7: N7 — Show source count per category in taxonomy scorecard

**Files:**
- Modify: `src/static/index.html` — `renderTaxonomyScorecard` function (~line 7086)

- [ ] **Step 1: Add source count badge to each category bar**

In `renderTaxonomyScorecard`, find the line that renders the score number (line ~7110):

```javascript
+ '<span style="font-family:var(--font-mono); color:' + c + '; font-weight:600;">' + s.score + '</span>'
```

Replace with:

```javascript
+ '<span style="font-family:var(--font-mono); color:' + c + '; font-weight:600;">' + s.score + '</span>'
+ (s.source_count ? '<span style="font-size:7px; color:var(--text-muted); margin-left:4px;" title="' + esc((s.sources||[]).join(', ')) + '">(' + s.source_count + ' src)</span>' : '')
```

This shows "(2 src)" next to each score with a tooltip listing the actual source names.

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N7): show source count per category in taxonomy scorecard"
```

---

### Task 8: N8 — Fix fabricated source attribution in forecast signals

**Files:**
- Modify: `src/analysis/cobalt_forecasting.py` — `_generate_signals` function

- [ ] **Step 1: Replace "Lloyd's List Intelligence" with accurate source names**

In `_generate_signals`, find the lead time signal sources:

```python
"sources": ["PSI Shipping Routes", "Lloyd's List Intelligence"],
```

Replace with:

```python
"sources": ["PSI Shipping Routes", "Mineral Supply Chain Data"],
```

- [ ] **Step 2: Commit**

```bash
git add src/analysis/cobalt_forecasting.py
git commit -m "fix(N8): replace fabricated Lloyd's List source with accurate PSI attribution"
```

---

### Task 9: N9 — Add French labels for Supply Chain sub-tab content headers

**Files:**
- Modify: `src/static/index.html` — add FR label mappings and update `toggleLanguage`

Full bilingual translation of all dynamic content is out of scope (would require a translation service for 10,000+ lines). Instead, we translate all visible HEADERS, LABELS, and BUTTON TEXT in the 12 Supply Chain sub-tabs so the FR toggle has meaningful coverage.

- [ ] **Step 1: Add Supply Chain French label mappings**

Find the `FRENCH_LABELS` object (near `toggleLanguage`). Extend it to include sub-tab labels. After the existing nav tab labels, add a `PSI_FR` object:

```javascript
var PSI_FR = {
  'Active Alerts (Watchtower)': 'Alertes actives (Tour de guet)',
  'Evidence & Sources': 'Preuves et sources',
  'Recommended COA': 'Plan d\'action recommandé',
  'Acknowledge': 'Accuser réception',
  'Assign': 'Assigner',
  'Escalate': 'Escalader',
  'Evidence Locker': 'Casier de preuves',
  'Risk Register': 'Registre des risques',
  'Update Status:': 'Mettre à jour le statut :',
  'Open': 'Ouvert',
  'In Progress': 'En cours',
  'Mitigated': 'Atténué',
  'Closed': 'Fermé',
  'Total Risks': 'Risques totaux',
  'Overdue': 'En retard',
  'Pending Adjudication': 'En attente d\'adjudication',
  'Model Accuracy': 'Précision du modèle',
  'False Positive Rate': 'Taux de faux positifs',
  'Pending Review': 'En attente de révision',
  'Threshold Configuration': 'Configuration des seuils',
  'Recent Feedback History': 'Historique récent des rétroactions',
  'Bill of Materials Explosion': 'Décomposition de la nomenclature',
  'NATO Stock Numbers': 'Numéros de stock OTAN',
  'Forecast Signals': 'Signaux prévisionnels',
  'Price Forecast': 'Prévision des prix',
  'Lead Time Risk': 'Risque de délai',
  'Supply Adequacy': 'Adéquation de l\'approvisionnement',
  'Supplier Insolvency Watch': 'Surveillance de l\'insolvabilité des fournisseurs',
  'Risk × Impact Matrix': 'Matrice risque × impact',
  'MITIGATE NOW': 'ATTÉNUER MAINTENANT',
  'MONITOR': 'SURVEILLER',
  'TRANSFER': 'TRANSFÉRER',
  'ACCEPT': 'ACCEPTER',
  'Scenario Builder': 'Constructeur de scénarios',
  'Run Scenario': 'Exécuter le scénario',
  'Value at Risk': 'Valeur à risque',
  'Platforms Affected': 'Plateformes affectées',
  'COA Comparison': 'Comparaison des plans d\'action',
  'INSIGHT:': 'APERÇU :',
  'Sources:': 'Sources :',
  'Confidence:': 'Confiance :',
  'SEEDED': 'DONNÉES DE BASE',
  'LIVE': 'EN DIRECT',
  'LIVE ML DATA': 'DONNÉES ML EN DIRECT',
  'BASELINE DATA': 'DONNÉES DE BASE',
};
```

- [ ] **Step 2: Update toggleLanguage to apply PSI_FR labels**

Extend `toggleLanguage` to also scan and replace text content in the Supply Chain tab:

```javascript
function toggleLanguage() {
  currentLanguage = currentLanguage === 'en' ? 'fr' : 'en';
  const labels = currentLanguage === 'fr' ? FRENCH_LABELS : ENGLISH_LABELS;
  document.querySelectorAll('.nav-tab[data-page]').forEach(function(tab) {
    var page = tab.getAttribute('data-page');
    if (labels[page]) { tab.textContent = labels[page]; }
  });
  // PSI sub-tab buttons
  document.querySelectorAll('.psi-tab-btn').forEach(function(btn) {
    var key = btn.dataset.psiTab;
    var map = {'psi-overview':'Aperçu','psi-globe':'Carte 3D','psi-graph':'Graphe','psi-risks':'Matrice de risque','psi-scenarios':'Scénarios','psi-taxonomy':'Taxonomie','psi-forecasting':'Prévisions','psi-bom':'Nomenclature','psi-dossier':'Dossier','psi-alerts':'Alertes','psi-register':'Registre','psi-feedback':'Rétroaction'};
    var enMap = {'psi-overview':'Overview','psi-globe':'3D Supply Map','psi-graph':'Knowledge Graph','psi-risks':'Risk Matrix','psi-scenarios':'Scenario Sandbox','psi-taxonomy':'Risk Taxonomy','psi-forecasting':'Forecasting','psi-bom':'BOM Explorer','psi-dossier':'Supplier Dossier','psi-alerts':'Alerts & Sensing','psi-register':'Risk Register','psi-feedback':'Analyst Feedback'};
    if (currentLanguage === 'fr' && map[key]) btn.textContent = map[key];
    else if (enMap[key]) btn.textContent = enMap[key];
  });
  var toggle = document.getElementById('lang-toggle');
  if (toggle) { toggle.textContent = currentLanguage === 'fr' ? 'FR | EN' : 'EN | FR'; }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/static/index.html
git commit -m "feat(N9): add French labels for Supply Chain sub-tab headers and key UI elements"
```

---

### Task 10: N10 — Add CSV export for Cobalt risk register and alerts

**Files:**
- Modify: `src/api/export_routes.py`

- [ ] **Step 1: Add two export endpoints**

```python
@router.get("/cobalt/register/csv")
async def export_cobalt_register_csv():
    """Export Cobalt risk register as CSV."""
    from src.analysis.mineral_supply_chains import get_mineral_by_name
    import csv
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        raise HTTPException(status_code=404, detail="Cobalt not found")
    rr = mineral.get("risk_register", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Risk", "Category", "Severity", "Status", "Owner", "Due Date", "COA IDs", "COAs", "Evidence"])
    for r in rr:
        writer.writerow([r.get("id",""), r.get("risk",""), r.get("category",""), r.get("severity",""), r.get("status",""), r.get("owner",""), r.get("due_date",""), ";".join(r.get("coa_ids",[])), ";".join(r.get("coas",[])), ";".join(r.get("evidence",[]))])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cobalt_risk_register.csv"})

@router.get("/cobalt/alerts/csv")
async def export_cobalt_alerts_csv():
    """Export Cobalt watchtower alerts as CSV."""
    from src.analysis.mineral_supply_chains import get_mineral_by_name
    import csv
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        raise HTTPException(status_code=404, detail="Cobalt not found")
    alerts = mineral.get("watchtower_alerts", [])
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Title", "Severity", "Category", "Sources", "Confidence", "COA", "Timestamp"])
    for a in alerts:
        writer.writerow([a.get("id",""), a.get("title",""), a.get("severity",""), a.get("category",""), ";".join(a.get("sources",[])), a.get("confidence",""), a.get("coa",""), a.get("timestamp","")])
    return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cobalt_alerts.csv"})
```

Make sure `import io` and `from starlette.responses import Response` are at the top of the file.

- [ ] **Step 2: Commit**

```bash
git add src/api/export_routes.py
git commit -m "feat(N10): add CSV export for Cobalt risk register and watchtower alerts"
```

---

### Task 11: N11 — Add Cobalt supply chain section to PDF briefing

**Files:**
- Modify: `src/analysis/briefing_generator.py`

- [ ] **Step 1: Add a Cobalt supply chain page to the briefing**

In the `generate_pdf` method, after the existing sections (situation report, transfers, suppliers, taxonomy, Arctic, mitigation), add a new Cobalt section. Find the pattern of existing `_add_*` methods and add:

```python
def _add_cobalt_section(self, pdf: BriefingPDF):
    """Add Cobalt supply chain intelligence section."""
    from src.analysis.mineral_supply_chains import get_mineral_by_name
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        return

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 212, 255)
    pdf.cell(0, 8, _safe_text("COBALT SUPPLY CHAIN INTELLIGENCE"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(0, 212, 255)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 4, _safe_text(f"HHI: {mineral.get('hhi', 'N/A')} | Risk Level: {mineral.get('risk_level', 'N/A')} | Top Miner: DRC ({mineral.get('mining', [{}])[0].get('pct', 0)}%)"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    # Mining concentration
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Mining Concentration", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for m in mineral.get("mining", [])[:5]:
        pdf.cell(0, 4, _safe_text(f"  {m['country']}: {m['pct']}%"), new_x="LMARGIN", new_y="NEXT")

    # Processing concentration
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 5, "Processing Concentration", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    for p in mineral.get("processing", [])[:5]:
        pdf.cell(0, 4, _safe_text(f"  {p['country']}: {p['pct']}%"), new_x="LMARGIN", new_y="NEXT")

    # Risk register summary
    rr = mineral.get("risk_register", [])
    if rr:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, _safe_text(f"Risk Register ({len(rr)} items)"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for r in rr[:5]:
            sev = r.get("severity", "").upper()
            pdf.cell(0, 4, _safe_text(f"  [{sev}] {r.get('id','')}: {r.get('risk','')[:80]}"), new_x="LMARGIN", new_y="NEXT")

    # Watchtower alerts
    alerts = mineral.get("watchtower_alerts", [])
    if alerts:
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5, _safe_text(f"Active Alerts ({len(alerts)})"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 8)
        for a in alerts[:4]:
            pdf.cell(0, 4, _safe_text(f"  [SEV {a.get('severity',0)}] {a.get('title','')[:80]}"), new_x="LMARGIN", new_y="NEXT")
```

Then call `self._add_cobalt_section(pdf)` in the `generate_pdf` method after the existing sections.

- [ ] **Step 2: Run tests and commit**

```bash
git add src/analysis/briefing_generator.py
git commit -m "feat(N11): add Cobalt supply chain section to PDF intelligence briefing"
```

---

### Task 12: N12 — Add ARIA attributes and keyboard support to dynamic controls

**Files:**
- Modify: `src/static/index.html` — multiple rendering functions

- [ ] **Step 1: Add ARIA to alert action buttons in renderAlertsSensing**

Update the 4 button lines to include `aria-label` with alert context:

```javascript
html += '<button role="button" aria-label="Acknowledge alert: '+esc(a.title).substring(0,40)+'" style="'+btnStyle+'" onclick="alertAcknowledge(this,\''+esc(a.id)+'\')">Acknowledge</button>';
html += '<button role="button" aria-label="Assign alert: '+esc(a.title).substring(0,40)+'" style="'+btnStyle+'" onclick="alertAssign(this,\''+esc(a.id)+'\')">Assign</button>';
html += '<button role="button" aria-label="Escalate alert: '+esc(a.title).substring(0,40)+'" style="'+btnStyle+'" onclick="alertEscalate(this,\''+esc(a.id)+'\')">Escalate</button>';
html += '<button role="button" aria-label="Evidence locker for: '+esc(a.title).substring(0,40)+'" style="'+btnStyle+'" onclick="alertEvidence(this)">Evidence Locker</button>';
```

- [ ] **Step 2: Add ARIA to risk register expandable rows**

In `renderRiskRegister`, update the clickable `<tr>` to include accessibility attributes:

```javascript
html += '<tr role="button" tabindex="0" aria-expanded="false" aria-controls="register-detail-'+i+'" style="border-bottom:1px solid var(--border); cursor:pointer;" onclick="toggleRegisterRow('+i+')" onkeydown="if(event.key===\'Enter\')toggleRegisterRow('+i+')">';
```

Update `toggleRegisterRow` to set `aria-expanded`:

```javascript
function toggleRegisterRow(idx) {
  var row = document.getElementById('register-detail-' + idx);
  var trigger = row ? row.previousElementSibling : null;
  if (row) {
    var show = row.style.display === 'none';
    row.style.display = show ? '' : 'none';
    if (trigger) trigger.setAttribute('aria-expanded', show ? 'true' : 'false');
  }
}
```

- [ ] **Step 3: Add ARIA to register status buttons**

In `renderRiskRegister` status buttons, add `aria-pressed`:

```javascript
html += '<button role="button" aria-pressed="'+(isCurrent?'true':'false')+'" style="...' + ...
```

- [ ] **Step 4: Add aria-label to the scatter chart canvas**

In `renderMineralRiskMatrix`, add:

```javascript
html += '<canvas id="mineral-risk-scatter" aria-label="Risk probability versus operational impact scatter chart for '+esc(m.name)+' entities" role="img" style="width:100%; height:100%;"></canvas>';
```

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N12): add ARIA attributes and keyboard support to dynamic Cobalt controls"
```

---

### Task 13: N13 — Add "(illustrative)" disclaimer to fabricated NSN entries

**Files:**
- Modify: `src/static/index.html` — `renderBomExplorer` NSN section

- [ ] **Step 1: Add disclaimer to NSN header**

In the NSN rendering section of `renderBomExplorer`, find:

```javascript
html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase; margin-bottom:6px;">NATO Stock Numbers (NSN Group ' + esc(m.nsn_group || '') + ')</div>';
```

Replace with:

```javascript
html += '<div style="font-size:10px; color:var(--text-dim); text-transform:uppercase; margin-bottom:6px;">NATO Stock Numbers (NSN Group ' + esc(m.nsn_group || '') + ') <span style="text-transform:none; color:var(--accent4); font-size:9px;">(illustrative — actual NSNs from NMCRL)</span></div>';
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N13): add illustrative disclaimer to fabricated NSN entries"
```

---

### Task 14: N14 — Connect Cobalt RLHF thresholds to live ML engine

**Files:**
- Modify: `src/static/index.html` — `renderAnalystFeedback` threshold section

This is already partially addressed by Task 6 (N6) which overlays live ML threshold data. The remaining piece is ensuring the threshold display section reads from the overlaid data.

- [ ] **Step 1: Verify threshold rendering uses overlaid data**

In `renderAnalystFeedback`, the threshold section (around line 8715) already reads `af.threshold.current_z` and `af.threshold.rlhf_adjusted`. Since Task 6 (N6) overlays these from `/ml/thresholds`, this should already work. Verify by reading the code.

If the threshold section still uses the seed data keys, update it to also show a "LIVE" badge when `af._live_stats` is true.

After the threshold rows, add:

```javascript
  if (af._live_stats) {
    html += '<div style="margin-top:6px; font-size:9px; color:var(--accent3);">Thresholds synced from live ML engine</div>';
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/static/index.html
git commit -m "fix(N14): connect Cobalt RLHF threshold display to live ML engine data"
```
