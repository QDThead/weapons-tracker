# Cobalt Compliance Gaps — Design Spec

**Date:** 2026-03-31
**Goal:** Close all 12 DND DMPP 11 compliance gaps identified in the Cobalt audit

## Gaps Addressed

| # | Gap | RFI Q | Fix |
|---|-----|-------|-----|
| G1 | Watchtower alerts static | Q1,Q11 | GDELT keyword monitoring + rule-based trigger engine via APScheduler |
| G2 | Alert action buttons no persistence | Q1,Q11,Q13 | New API endpoints + DB table for Cobalt alert state |
| G3 | Risk Register status no persistence | Q13 | Wire status buttons to PATCH /mitigation/actions via seeding register entries to DB |
| G4 | NSN column empty | Q4 | Populate NSN values for Cobalt alloys and platforms |
| G5 | NetworkX missing superalloy path | Q2 | Add Cobalt→Turbine Blade edges to supply_chain_seed.py (already has Turbine Blades→Cobalt) |
| G6 | BOM confidence hardcoded | Q3,Q8 | Compute from source count per tier using confidence.py pattern |
| G7 | Entity taxonomy no confidence metadata | Q8 | Add sources/confidence fields to each entity taxonomy score |
| G8 | Taxonomy rationale not in Risk Matrix | Q8 | Render rationale text below risk bar in mineral risk matrix cards |
| G9 | Three disconnected COA systems | Q13 | Unify COA IDs: risk register entries reference sufficiency COA IDs |
| G10 | Risk Matrix not entity-specific | Q10 | Rewrite mineral mode to use genuine probability×impact canvas scatter |
| G11 | Forecast signals no source attribution | Q8 | Add sources array and confidence % to each signal |
| G12 | HS codes not in BOM Explorer | Q4 | Add HS codes to mineral data and render in BOM tree |

## Architecture

- **Cluster A (Data):** G4, G5, G6, G7, G11, G12 — enrich existing data structures
- **Cluster B (UI):** G8, G9, G10 — fix how data is displayed
- **Cluster C (Persistence):** G2, G3 — seed Cobalt alerts/risks to DB, wire buttons to API
- **Cluster D (Live Sensing):** G1 — new scheduler job for Cobalt-specific alerts
