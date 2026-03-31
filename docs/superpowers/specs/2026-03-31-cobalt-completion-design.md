# Cobalt Feature Completion — Design Spec

**Date:** 2026-03-31
**Goal:** Make all Cobalt sub-tab features fully functional (zero stubs/placeholders)

## Items

1. **Fix `test_resolved_action_not_reopened`** — persistence bug where upsert creates new row without explicit `status="open"`
2. **COA table sorting** — add click-to-sort on all 8 column headers in the COA comparison drawer
3. **Analyst Feedback buttons** — wire Verified/False Positive to `POST /ml/feedback`
4. **Alert action buttons** — wire Acknowledge/Assign/Escalate/Evidence to functional handlers
5. **Risk Register status buttons** — add status transition buttons in expanded row detail
6. **Add `requests` to requirements.txt** — needed by adversarial tests

## Approach: Wire to existing infrastructure

All backend endpoints already exist:
- `POST /ml/feedback` — accepts `{entity, assessment_type, verdict, notes}`
- `PATCH /mitigation/actions/{id}` — accepts `{status, notes}`
- `GET /ml/thresholds` — returns feedback stats

Alerts and Risk Register data comes from `mineral_supply_chains.py` static data via `/globe/minerals/{name}`. We keep this as the data source (no database migration needed for read-only display). Status changes use client-side state with visual feedback, since these are intelligence alerts, not CRUD records.

BOM Explorer is already implemented (`renderBomExplorer` at line 8227). No work needed.
