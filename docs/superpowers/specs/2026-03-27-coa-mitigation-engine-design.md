# COA/Mitigation Engine — Decision Support for OODA "Decide/Act"

**Date:** 2026-03-27
**Status:** Approved
**Goal:** Add automated Course of Action (COA) recommendations with a lightweight action tracker, addressing DND Q13 (Decision Support & Mitigation Capabilities) — the "Decide/Act" phases of the OODA loop.

## Context

The bid promises a "Mitigation Recommendation Engine" with pre-configured SOPs for 150+ risk types, closed-loop governance (assignment, tracking, escalation), and a risk register. The current platform scores risks but doesn't recommend actions or track resolution. This is the #1 bid compliance gap.

## Approach

Rule-based playbook mapping ~40 risk patterns to deterministic COA recommendations. Each risk above threshold gets a recommended action, priority, timeline, and responsible party. A lightweight status tracker (Open → In Progress → Resolved) with notes closes the loop. No LLM — DND values repeatability over creativity.

## Data Model

### Table: `mitigation_actions`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | Integer PK | Auto-increment | |
| risk_source | String(50) | Not null | "supplier", "taxonomy", "psi", "arctic" |
| risk_entity | String(500) | Not null | What's at risk: supplier name, category key, alert title, etc. (500 to match SupplyChainAlert.title length) |
| risk_dimension | String(100) | Not null | Specific dimension: "single_source", "1a", etc. |
| risk_score | Float | Not null | Score that triggered this COA |
| coa_action | Text | Not null | Recommended course of action |
| coa_priority | String(10) | Not null | "critical", "high", "medium", "low" |
| coa_timeline | String(50) | | "Immediate", "30 days", "90 days" |
| coa_responsible | String(100) | | "DSCRO", "Procurement", "Security", "Program Office" |
| status | String(15) | Not null, default "open" | "open", "in_progress", "resolved" |
| notes | Text | | Analyst notes |
| created_at | DateTime | default=datetime.utcnow | |
| updated_at | DateTime | default=datetime.utcnow, onupdate | |

**Constraints:** `UniqueConstraint("risk_source", "risk_entity", "risk_dimension", "status", name="uq_mitigation_risk_active")` — includes `status` so a new "open" COA can be created after a previous one was "resolved" for the same risk triple.
**Index:** `Index("ix_mitigation_status", "status")`

**Persistence:** The `upsert_mitigation_action` method takes positional args `(risk_source, risk_entity, risk_dimension)` as the lookup key, plus `**kwargs` for remaining fields. Follows the `upsert_taxonomy_score(subcategory_key, **kwargs)` pattern. When upserting, it queries for existing rows with status != "resolved". If found, updates score/action/priority. If not found, creates new row with status="open".

## Playbook Engine

### File: `src/analysis/mitigation_playbook.py`

A `MitigationPlaybook` class with:

**`PLAYBOOK` constant dict** — ~40 entries keyed by `(risk_source, dimension_pattern)`. Each entry:
```python
{
    "action": "Recommended course of action text",
    "priority_threshold": {"critical": 85, "high": 70, "medium": 50},
    "timeline": "90 days",
    "responsible": "Procurement",
}
```

**Playbook coverage:**

| Risk Source | Dimensions | COA Examples |
|---|---|---|
| supplier / foreign_ownership | score >50 | "Initiate National Security Review; suspend new PO issuance pending FOCI assessment" |
| supplier / customer_concentration | score >60 | "Engage supplier on revenue diversification plan; assess business continuity risk" |
| supplier / single_source | score >60 | "Qualify alternate supplier; estimated qualification time: 90 days" |
| supplier / contract_activity | score >60 | "Engage supplier for business continuity review; activate safety stock" |
| supplier / sanctions_proximity | score >40 | "Conduct sanctions compliance audit; review sub-tier material sourcing" |
| supplier / contract_performance | score >50 | "Issue corrective action request; increase inspection frequency" |
| taxonomy / 1* (FOCI) | score >50 | FOCI-specific: security review, ownership audit, CI referral |
| taxonomy / 2* (Political) | score >60 | "Monitor political situation; assess trade route alternatives" |
| taxonomy / 3* (Manufacturing) | score >50 | "Initiate dual-source qualification; purchase safety stock" |
| taxonomy / 4* (Cyber) | score >50 | "Request supplier cyber posture assessment; review incident response" |
| taxonomy / 5* (Infrastructure) | score >50 | "Assess facility vulnerability; activate continuity plan" |
| taxonomy / 7* (Transport) | score >50 | "Activate alternate shipping route; pre-position safety stock" |
| taxonomy / 9* (Environmental) | score >50 | "Monitor hazard status; ensure supplier disaster recovery plan current" |
| taxonomy / 10* (Compliance) | score >50 | "Initiate compliance review; flag for legal assessment" |
| taxonomy / 12* (Financial) | score >50 | "Request financial health update; assess payment performance" |
| psi / chokepoint_blocked | any alert | "Divert shipments to alternate port; impact: +N days transit" |
| psi / material_shortage | any alert | "Purchase safety stock from secondary supplier to cover 6-month gap" |
| psi / sanctions_risk | any alert | "Initiate supply chain re-sourcing; flag affected items" |
| psi / concentration_risk | any alert | "Identify alternate sources; begin qualification process" |

**Generic fallback:** If no specific playbook entry matches AND score > 70, generate a generic COA: "Review risk assessment and determine appropriate mitigation. Assign to responsible officer for evaluation." Scores between 50-70 without a specific playbook match are suppressed to avoid low-value noise in the Action Centre.

### COA Generation Logic

`generate_all_coas()` method:

1. **Query supplier risks:** All `SupplierRiskScore` rows with score > 50. Filter using `RiskDimension` enum values (e.g., `RiskDimension.SINGLE_SOURCE`), NOT raw strings — SQLAlchemy `SQLEnum` columns require enum comparison. Group by supplier + dimension.
2. **Query taxonomy risks:** All `RiskTaxonomyScore` rows with score > 50.
3. **Query PSI alerts:** All `SupplyChainAlert` rows.
4. For each risk, match to playbook by `(risk_source, dimension_pattern)`.
5. Compute priority from score: >85 = critical, >70 = high, >50 = medium, else low.
6. Upsert into `mitigation_actions` (on unique constraint). If existing action is "resolved", skip it (don't reopen).
7. Return count of new + updated actions.

### Scheduler

Call `generate_all_coas()` at the tail of the existing `score_taxonomy()` async function in `scheduler.py`. This ensures COAs are regenerated immediately after taxonomy scores update, with no race condition. No separate scheduler job needed. Also callable on-demand via POST endpoint.

**Cache note:** When called from the scheduler (not via HTTP), the mitigation GET cache is not explicitly cleared. The 5-minute TTL handles staleness naturally — acceptable for a 6-hour scoring cycle.

## API Endpoints

### File: `src/api/mitigation_routes.py`

Router prefix: `/mitigation`, tags: `["Mitigation"]`

### `GET /mitigation/actions`

Query params: `status` (optional filter: "open", "in_progress", "resolved", "all"), `priority` (optional), `source` (optional).

Default: returns open + in_progress, sorted by priority (critical first) using Python-side sort with priority map `{"critical": 0, "high": 1, "medium": 2, "low": 3}` — same pattern as `supplier_routes.py`.

**`by_status` always counts ALL statuses** regardless of the filter applied to `actions`, so the UI stat badges show accurate totals including resolved count.

```json
{
  "actions": [...],
  "total": 15,
  "by_priority": {"critical": 3, "high": 5, "medium": 7, "low": 0},
  "by_status": {"open": 12, "in_progress": 3, "resolved": 5}
}
```

Cached 5 minutes. Cache cleared on PATCH/POST.

### `PATCH /mitigation/actions/{id}`

Body: `{"status": "in_progress", "notes": "Assigned to Maj. Smith, procurement review initiated"}`

Returns updated action. Clears GET cache.

### `POST /mitigation/generate`

Triggers on-demand COA generation. Returns:
```json
{"generated": 12, "updated": 3, "skipped_resolved": 2}
```

Clears GET cache.

### Registration

Add to `src/main.py`: `from src.api.mitigation_routes import router as mitigation_router` and `app.include_router(mitigation_router)`.

## UI: Two Locations

### 1. Insights Tab — Action Centre

Inserted between the Risk Taxonomy strip and Section 1 (Situation Report).

**Header row:** "Action Centre" with 3 stat badges:
- Open count (red background)
- In Progress count (amber background)
- Resolved count (green background)
- "Generate COAs" button (btn-primary, calls POST /mitigation/generate)

**Action list:** Max 10 rows, sorted by priority. Each row:
- Left: Priority badge (critical/high/medium/low colored pill)
- Center: Risk entity name, dimension label, COA action text (truncated to 1 line)
- Right: Responsible party tag, timeline, status dropdown (Open/In Progress/Resolved)

Status dropdown fires PATCH immediately on change. Success shows brief confirmation.

### 2. Inline COA on Existing Alert Cards

**Supplier alerts** (Canada Intel → Defence Supply Base → alerts section):
Each `.insight-alert` card gets an additional line: `Recommended: [COA action text] — [timeline] — [responsible]`

**PSI alerts** (Supply Chain → Overview → alerts):
Same pattern — append COA line to each alert card.

**Taxonomy accordion** (Supply Chain → Risk Taxonomy):
Sub-categories with score >60 show a small "COA" badge that expands to show the recommended action on click.

Inline COAs are read-only. Full status management is in the Action Centre.

**Data sourcing for inline COAs:** The UI fetches `/mitigation/actions` once on page load (alongside other data), then joins client-side by matching `risk_entity` and `risk_source` to the alert cards. The Action Centre data load is triggered on Insights page load and cached in a JS variable. Alert-rendering functions check this cache to append COA lines. No changes to existing alert endpoints needed.

### Design System Compliance

- Priority pills: critical=`--accent2`, high=`--accent4`, medium=`#eab308`, low=`--accent3`
- Status dropdown: styled as compact `.tab`-like selector
- Responsible tags: `.seller-tag` style (pill, colored background)
- Action text: `--font-body`, 13px
- Card styling: existing `.insight-alert` pattern

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `src/storage/models.py` | Modified | Add `MitigationAction` model |
| `src/analysis/mitigation_playbook.py` | New | Playbook definitions + COA generation engine. Must include `from __future__ import annotations` |
| `src/storage/persistence.py` | Modified | Add `upsert_mitigation_action` method |
| `src/api/mitigation_routes.py` | New | 3 endpoints (GET, PATCH, POST). Must include `from __future__ import annotations` |
| `src/ingestion/scheduler.py` | Modified | Add COA generation to 6-hour cycle |
| `src/main.py` | Modified | Register mitigation_routes router |
| `src/static/index.html` | Modified | Action Centre on Insights + inline COAs on alerts |
| `tests/test_mitigation.py` | New | Tests for playbook, endpoints, status updates |

## Out of Scope

- LLM-generated recommendations (future enhancement)
- Email/Teams notifications on status changes
- Escalation rules (auto-escalate overdue actions)
- Assignment to specific users (no user system yet)
- Historical action analytics / resolution time metrics
