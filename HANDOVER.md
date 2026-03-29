# Handover Document — Weapons Tracker Platform

**Date:** 2026-03-29
**Prepared for:** Incoming development team / DND DMPP 11 evaluation
**Platform:** PSI Control Tower — Defence Supply Chain Intelligence

---

## Executive Summary

The Weapons Tracker is a fully operational geopolitical intelligence platform built for the Canadian Department of National Defence (DND). It tracks global weapons sales, military spending, force deployments, and defence supply chain risk using 57 active OSINT data feeds. The platform addresses all 22 questions from the DND/CAF Defence Supply Chain Control Tower RFI, with a 95.3% compliance rate across 137 sub-requirements.

---

## Current State

### What's Running
- **FastAPI server** on port 8000 with 118+ REST API endpoints
- **10-tab interactive dashboard** (Insights, Overview, World Map, Arctic, Live Flights, Deals, Canada Intel, Supply Chain, Data Feeds, Compliance)
- **57 active OSINT data feeds** across 24 Python connector files
- **9 scheduled ingestion jobs** (5min to weekly intervals)
- **SQLite database** with 9,311 transfers, 5,110 indicators, 167 news articles, 30 materials, 90 supply chain nodes, 96 edges, 10 Canadian suppliers, 121 taxonomy scores
- **191-entry COA playbook** covering all 13 DND Annex B risk categories
- **EN/FR bilingual interface** with language toggle

### Database
- **Dev:** SQLite (`weapons_tracker.db` in project root)
- **Prod:** PostgreSQL + PostGIS on Azure Canada Central (deployment script ready)
- **18 tables** covering countries, transfers, weapons, companies, indicators, news, tracking, supply chain (nodes/edges/routes/alerts/materials), suppliers, contracts, risk scores, taxonomy, mitigation actions, audit log

### Authentication
- **Dev mode:** Auth disabled (`AUTH_ENABLED=false`), all endpoints open
- **Production:** API key auth with 3 roles (viewer, analyst, admin), RBAC enforced
- Keys loaded from `API_KEYS_JSON` environment variable
- CORS, TLS redirect, and trusted host middleware configured via env vars

---

## Architecture Overview

```
     57 OSINT DATA SOURCES
     ├── Live (5min): ADS-B flights, Tor exit nodes
     ├── Near-RT (15min-days): GDELT, RSS, DSCA, disasters, CVEs
     ├── Monthly: US Census, UK HMRC, Eurostat, StatCan, commodities
     ├── Annual: SIPRI, NATO, World Bank, Comtrade, CIA, UNROCA
     ├── Enrichment: WGI, IMF, UNHCR, DoD contracts, satellites
     └── Cyber: APT registry, MITRE ATT&CK, CISA KEV, breaches
            │
            ▼
     APScheduler (9 jobs) → Persistence Service → SQLite/PostgreSQL
            │
            ▼
     Analysis Layer
     ├── risk_taxonomy.py      13 categories, 121 sub-categories
     ├── supply_chain_graph.py  NetworkX: 90 nodes, 96 edges
     ├── supply_chain.py        6-dimension risk + 5 scenario types
     ├── confidence.py          Glass Box source triangulation
     ├── mitigation_playbook.py 191-entry COA playbook
     ├── forecasting.py         6 forecast types, 12-18mo horizon
     ├── ml_engine.py           Anomaly detection + RLHF feedback
     ├── briefing_generator.py  7-page PDF export
     └── cyber_threat_intel.py  APT groups, breach registry, IOCs
            │
            ▼
     FastAPI (118+ endpoints) → HTML Dashboard (10 tabs)
```

---

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/main.py` | App entry point, middleware, router registration | ~100 |
| `src/static/index.html` | Complete dashboard (10 tabs, CesiumJS globe pending) | ~6,500 |
| `src/storage/models.py` | 18 SQLAlchemy table definitions | ~630 |
| `src/storage/persistence.py` | Upsert/dedup logic with rollback handling | ~700 |
| `src/analysis/risk_taxonomy.py` | DND Annex B 13-cat/121-subcat scoring | ~450 |
| `src/analysis/supply_chain_graph.py` | NetworkX knowledge graph + BOM explosion | ~400 |
| `src/analysis/mitigation_playbook.py` | 191 COA entries + generation engine | ~800+ |
| `src/api/enrichment_routes.py` | 40+ enrichment endpoints | ~1,200 |
| `src/api/arctic_routes.py` | Arctic security assessment + 25 bases | ~600 |
| `src/ingestion/osint_feeds.py` | 26 OSINT connector classes | ~1,800 |
| `scripts/seed_database.py` | Initial data load (SIPRI, WB, GDELT, flights) | ~190 |

---

## How to Run

```bash
cd weapons-tracker
python -m venv venv

# Windows
source venv/Scripts/activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt

# Seed database (first time — takes ~5 min)
python -m scripts.seed_database

# Start server
python -m src.main
# Dashboard: http://localhost:8000
# API docs:  http://localhost:8000/docs
```

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///weapons_tracker.db` | Database connection |
| `ENVIRONMENT` | `development` | `production` enables HTTPS redirect |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS_JSON` | (dev defaults) | JSON dict of API keys and roles |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ALLOWED_HOSTS` | `*` | Comma-separated trusted hostnames |
| `AISSTREAM_API_KEY` | (none) | Enable maritime AIS tracking |

---

## RFP Compliance Summary

**22 RFI questions mapped, 137 sub-requirements tracked**

| Status | Count | Questions |
|--------|-------|-----------|
| **Compliant** | 109 | Q1-Q4, Q6, Q8-Q9, Q11-Q12, Q14-Q16, Q19 |
| **Exceeds** | 13 | Q5 (Risk Taxonomy), Q7 (Data Feeds), Q10 (UI), Q13 (Mitigation), Q20 (Exports), Q22 (Additional) |
| **Partial** | 1 | Training materials (content, not code) |
| **Planned** | 5 | PBMM, ITSG-33, SAML/OAuth, DND feeds, translation service |
| **N/A** | 9 | Q17 (Support), Q18 (IP), Q21 (Pricing) — contractual |

**Overall: 95.3% of applicable requirements met or exceeded**

Full interactive compliance matrix available at the Compliance tab in the dashboard.

---

## Security Hardening (Applied 2026-03-29)

| Control | Implementation |
|---------|---------------|
| RBAC enforcement | `require_permission` decorator checks role hierarchy |
| API key management | Keys loaded from env var, no hardcoded secrets |
| Error sanitization | 72 endpoints fixed: no `str(e)` leakage, generic 500s |
| XSS prevention | `esc()` applied to all 11 previously-unescaped injection points |
| CORS | `CORSMiddleware` with configurable origins |
| TLS redirect | `HTTPSRedirectMiddleware` active in production |
| Trusted hosts | `TrustedHostMiddleware` with configurable allow list |
| Disinformation detection | 3-layer: known state-media, extreme tone, sensationalist patterns |
| Input validation | Pydantic models on POST bodies, HTTPException for 404/500 |

---

## Recently Completed (2026-03-29)

### CesiumJS 3D Supply Chain Globe
Fully operational in Supply Chain tab → "3D Supply Map" sub-tab. Features:
- **30 minerals** with USGS MCS 2025 data, geo-coordinates, Canada-specific dependencies
- **CesiumJS 3D globe** with CartoDB Dark Matter tiles and global shipping lanes overlay
- **Per-mineral layer toggles** grouped by risk level (critical/high/medium/low)
- **4-tier visualization**: mining → processing → components → weapon platforms
- **5 Canadian ports** (Vancouver, Montreal, Halifax, Hamilton, Sept-Iles) as import destinations
- **20+ pre-computed maritime shipping routes** following real sea lanes
- **Risk-colored shipping routes**: critical (red), high (amber), medium (yellow), low (green) with route menu
- **Rich detail panel**: 4-column supply chain flow + Route to Canada + Risk Assessment + Canada Impact
- **Deep Cobalt dive** (template for remaining 29 minerals):
  - 9 named mines (TFM, Kisanfu, Kamoto, Mutanda, Murrin Murrin, Moa JV, Voisey's Bay, Sudbury, Raglan) with ownership, production tonnage, and geo-coords
  - 9 named refineries (Huayou, GEM, Jinchuan, Umicore Kokkola/Hoboken, Fort Saskatchewan, Long Harbour, Niihama, Harjavalta)
  - 8 defence alloys with cobalt % (CMSX-4 9.5%, Waspaloy 13%, Stellite 6 60%, SmCo 52%)
  - 6 shipping corridors with risk ratings and waypoint arrays
  - **13-category DND Annex B risk taxonomy** scored per mine and refinery (FOCI, Political, Manufacturing, Cyber, Infrastructure, Planning, Transportation, Human Capital, Environmental, Compliance, Economic, Financial, Product Quality)
  - **KPIs per entity**: owner country/type, CPI score, employees, port distance, sanctioned status, Five Eyes/NATO alignment
  - **Flags**: ADVERSARY-CONTROLLED, CONFLICT ZONE, OPERATIONS PAUSED, SANCTIONS EXPOSURE, STRATEGIC ASSET, NATO-ALLIED, etc.
  - Expandable taxonomy scorecards in detail panel (click any mine/refinery)
- **Globe API**: `GET /globe/minerals` (all 30) and `GET /globe/minerals/{name}` (single mineral)
- **14 new tests** covering data integrity and API endpoints

### Files Added
| File | Lines | Purpose |
|------|-------|---------|
| `src/analysis/mineral_supply_chains.py` | 2,263 | 30 mineral supply chains + deep Cobalt data |
| `src/api/globe_routes.py` | 31 | Globe API endpoints |
| `tests/test_globe.py` | 146 | Data + API tests |
| `docs/superpowers/specs/2026-03-29-cesium-globe-design.md` | 120 | Design spec |
| `docs/superpowers/plans/2026-03-29-cesium-globe.md` | ~600 | Implementation plan |

## Cobalt Demand vs Supply Analysis (Research Complete — Not Yet Built Into UI)

Analysis completed 2026-03-29. Data below is ready to be implemented as a supply sufficiency feature on the 3D globe detail panel.

### Canada's Annual Military Cobalt Demand (~0.3 tonnes steady-state, ~0.74 tonnes during F-35 acquisition)

| Platform | Engine | Overhauls/yr | Co per overhaul | Annual Co (kg) |
|----------|--------|-------------|----------------|----------------|
| CF-188 Hornet (76 aircraft) | 2x GE F404 | ~8 | 7 kg | 56 |
| F-35A (88 on order, full fleet) | P&W F135 | ~2.4 | 12 kg | 29 |
| CH-148 Cyclone (28 helos) | 2x GE CT7 | ~3 | 4 kg | 12 |
| CH-149 Cormorant (14 helos) | 3x GE CT7 | ~3 | 4 kg | 12 |
| CH-147F Chinook (15 helos) | 2x Honeywell T55 | ~2 | 5 kg | 10 |
| CC-177 Globemaster (5 aircraft) | 4x P&W F117 | ~1 | 15 kg | 15 |
| Halifax-class frigates (12 ships) | 2x GE LM2500 | ~0.5/yr | 30 kg | 15 |
| Leopard 2A6M (80 tanks) | MTU MB 873 | ~7 | 0.5 kg | 3.5 |
| LAV 6.0 (550 vehicles) | Caterpillar C7 | ~18 | 0.3 kg | 5.4 |
| Victoria-class SSK (4 boats) | Diesel-electric | minimal | — | 2 |
| Guided munitions (SmCo magnets) | AIM-9/AIM-120 | — | — | 15 |
| BB-2590 soldier batteries | Li-ion NMC/LCO | ~800/yr | 0.06 kg | 50 |
| WC-Co cutting tools | Depot maintenance | — | — | 20 |
| Magnetic components | Sensors, generators | — | — | 10 |
| Stellite wear parts (non-engine) | Valves, pumps | — | — | 5 |
| **Spare parts buffer (15%)** | | | | **38** |
| **TOTAL STEADY-STATE** | | | | **~298 kg/yr** |
| **F-35 acquisition (88 engines over 7 years)** | 35 kg Co/engine | | | **+440 kg/yr** |
| **TOTAL DURING F-35 RAMP (2026-2032)** | | | | **~740 kg/yr** |

### Supply Sufficiency Scenarios

| Scenario | Secure Supply | Western Demand | Ratio | Verdict |
|----------|--------------|----------------|-------|---------|
| Normal operations | 237,000 t/yr global | 237,000 | 1.0x | Balanced |
| China export ban | 31,500 t/yr (NATO-allied refiners) | 54,000 (all Western) | **0.73x** | **27% deficit** |
| China + DRC collapse | 12,500 t/yr | 54,000 | **0.23x** | **77% deficit — CRITICAL** |
| Defence superalloys only (priority alloc) | 31,500 | 8,000 | **4.9x** | Sufficient IF govts intervene |
| Canada sovereign only | 2,500 t/yr (Vale Long Harbour) | 0.74 t/yr (CAF) | **3,400x** | Volume not the problem |

### Key Finding
**Canada's military cobalt demand is 0.0003% of global production. The vulnerability is not volume — it is supply chain architecture.** Canada does not manufacture jet engines or cast superalloy components. These come from US OEMs (P&W, GE, Honeywell) who depend on a global supply chain where China controls 80% of refining.

### Recommended Courses of Action

| COA | Action | Cost | Impact |
|-----|--------|------|--------|
| **COA-1** | Sovereign cobalt stockpile (500t refined metal) | ~$15M | 60 years CAF demand; bridges any disruption |
| **COA-2** | Increase engine overhaul parts buffer to 24 months | ~$100M | Eliminates grounding risk regardless of cause |
| **COA-3** | Restart Sherritt Fort Saskatchewan with non-Cuban feedstock | $50-150M | Gives Canada 6,300 t/yr sovereign refining |
| **COA-4** | Formalize allied cobalt allocation under DPSA with US DoD | $0 | Guaranteed access to US superalloy components |
| **COA-5** | Superalloy scrap recycling at Canadian MRO depots | $5-10M | Captures cobalt from engine overhauls (~200 kg/yr) |
| **COA-6** | Engine health monitoring to extend overhaul intervals 15-25% | ~$20M | Reduces parts consumption + improves availability |

### Implementation Target
Build into the Cobalt detail panel on the 3D globe:
- Demand breakdown bar chart by platform
- Supply sufficiency gauge under each scenario
- Interactive "What if China cuts off cobalt?" scenario slider
- COA recommendations with cost/impact matrix
- Exportable to PDF briefing

---

## What's In Progress

1. **Cobalt demand-vs-supply sufficiency UI** — build the analysis above into the 3D globe detail panel (demand chart, supply gauge, scenario simulator, COA matrix)
2. **Deep-dive remaining 29 minerals** — same depth as Cobalt (mines, refineries, alloys, shipping routes, 13-cat taxonomy per entity). Cobalt is the template.
3. **UX Clarity Fixes** — 8 improvements for newcomer clarity: TIV glossary tooltips, flight context banner, dimension labels, radar legend, graph legend, deals context, alliance explainer.

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| Maritime AIS tracking | Needs API key | `AISSTREAM_API_KEY` for aisstream.io |
| SIPRI Companies scraper | Needs URL update | Scrape URL changed |
| Sync SQLAlchemy in async | Tech debt | Works for SQLite; needs async sessions for PostgreSQL |
| `datetime.utcnow()` | Deprecated | ~20 occurrences; should migrate to `datetime.now(timezone.utc)` |
| No Alembic migrations | Tech debt | Using `create_all()`; needs migration framework for prod schema changes |
| EU Comtrade partner breakdown | Limited | Only returns "WORLD" aggregate, no bilateral EU flows |
| Forecasting module | Partial | 1 of 6 forecasts is data-driven; others are analyst-authored narratives |

---

## Test Suite

```bash
pytest tests/ -v
```

50 tests covering: models, persistence upserts, supplier risk scoring, risk taxonomy (121 sub-cats), mitigation lifecycle, procurement scraper normalization, confidence scoring, API routes.

---

## Deployment

### Docker
```bash
docker-compose up --build
```

### Azure Container Apps
```bash
cd deploy/azure
bash deploy.sh
```
Deploys to Azure Canada Central with data sovereignty tags. See `deploy/azure/deploy.sh` for full configuration.

---

## Contact

**Quantum Data Technologies (QDT)**
Canadian-owned | No foreign dependency | Data sovereign
