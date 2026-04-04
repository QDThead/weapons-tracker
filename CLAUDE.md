# CLAUDE.md — Weapons Tracker Project Context

## Project Goal
Geopolitical intelligence platform tracking global weapons sales, military spending, and force deployments
using OSINT data sources. Built for the Canadian government (DND) to understand: who is arming whom,
where are the threats, what's happening in the Arctic, and how is the world reshaping geopolitically.

## Tech Stack
- **Language:** Python 3.9+ (use `from __future__ import annotations` in all files)
- **API Framework:** FastAPI + Uvicorn (156+ API endpoints)
- **Database:** SQLite (dev) / PostgreSQL + PostGIS (prod)
- **ORM:** SQLAlchemy 2.0 (declarative models)
- **HTTP Client:** httpx (async)
- **Scheduling:** APScheduler (AsyncIOScheduler)
- **Data Processing:** pandas, geopandas, openpyxl
- **Graph Analysis:** NetworkX (supply chain knowledge graph)
- **Frontend:** Single-page HTML dashboard (Chart.js, D3.js, Leaflet.js, CesiumJS — no build step, ~12,900 lines)
- **3D Globes:** CesiumJS 1.119 (CDN) — Arctic globe (Esri satellite imagery, 8 layers) + Supply Chain globe (CartoDB dark tiles)
- **Design System:** Inter (display + body), JetBrains Mono (numbers); military theme with "Signal" desaturated palette; sharp edges, solid surfaces, atmospheric grid overlay + scan line
- **Home Page:** Landing page at `/` with DND branding, OODA framework, capabilities grid, intel ticker, right-side nav menu
- **Routing:** `/` = home.html (landing), `/dashboard` = index.html (7-tab dashboard)
- **Codebase:** 96 Python files
- **Flight Tracking:** 4 ADS-B sources (adsb.lol, adsb.fi, Airplanes.live, ADSB One) — parallel fetch, dedup, position history tracking, freight estimation
- **Tests:** 364 tests (pytest) covering models, persistence, risk scoring, taxonomy, API endpoints, scraper utilities, globe API, cobalt forecasting, scenario engine, cobalt connectors, financial scoring, player monitoring, Comtrade cobalt bilateral, confidence triangulation, dossier completeness, multi-source flights, source validation, scheduler feeds, FIRMS thermal, Sentinel NO2 (238 unit/integration + 85 adversarial)
- **Compliance:** 100% DND DMPP 11 RFI compliance for Cobalt (all 12 original gaps + 14 polish items closed)

## Project Structure
```
weapons-tracker/
├── src/
│   ├── ingestion/              # 46 active data source connectors
│   │   ├── sipri_transfers.py        # SIPRI Arms Transfers (atbackend.sipri.org API)
│   │   ├── comtrade.py               # UN Comtrade USD values + buyer-side mirror
│   │   ├── census_trade.py           # US Census monthly trade (HS 93)
│   │   ├── uk_hmrc_trade.py          # UK HMRC monthly trade (OData API)
│   │   ├── eurostat_trade.py         # EU Eurostat monthly trade (Comext SDMX)
│   │   ├── statcan_trade.py          # Statistics Canada CIMT monthly trade
│   │   ├── nato_spending.py          # NATO defence expenditure (Excel parser)
│   │   ├── worldbank.py              # World Bank arms trade indicators
│   │   ├── gdelt_news.py             # GDELT arms trade news (15-min updates)
│   │   ├── defense_news_rss.py       # Defense news RSS (4 feeds)
│   │   ├── dsca_sales.py             # DSCA arms sales (Federal Register API)
│   │   ├── flight_tracker.py         # Military flights via adsb.lol (live)
│   │   ├── sanctions.py              # OFAC SDN + EU sanctions + 17 embargoes
│   │   ├── maritime_tracker.py       # Maritime vessels via aisstream.io (needs key)
│   │   ├── sipri_companies.py        # SIPRI Top 100 defense companies
│   │   ├── critical_minerals.py     # PSI: USGS/EU critical minerals data
│   │   ├── wikidata_bom.py          # PSI: Wikidata SPARQL BOM connector
│   │   ├── wikipedia_weapons.py     # PSI: Wikipedia weapon infobox parser
│   │   ├── corporate_graph.py       # PSI: Company ownership graph + per-company lookup
│   │   ├── procurement_scraper.py   # Open Canada DND procurement contracts
│   │   ├── osint_feeds.py           # 26 OSINT connector classes + GLEIF LEI + SEC EDGAR XBRL
│   │   ├── bgs_minerals.py         # BGS World Mineral Statistics OGC API (cobalt production by country)
│   │   ├── nrcan_cobalt.py         # NRCan Canadian cobalt facts (production by province)
│   │   ├── sherritt_cobalt.py      # Sherritt International stock + ops + financials
│   │   ├── cobalt_players.py       # 15 cobalt supply chain players via Yahoo Finance
│   │   ├── worldbank_enrichment.py  # Governance + economic indicators (WGI, fragility)
│   │   ├── sipri_milex.py           # SIPRI Military Expenditure Database
│   │   ├── cia_factbook.py          # CIA World Factbook military data
│   │   ├── firms_thermal.py         # NASA FIRMS satellite thermal monitoring (18 cobalt facilities, 6hr polling)
│   │   ├── sentinel_no2.py         # Sentinel-5P TROPOMI NO2 emissions monitoring (18 cobalt facilities, daily polling) + Sentinel-2 thumbnails
│   │   └── scheduler.py              # APScheduler ingestion pipeline (28 scheduled jobs)
│   ├── storage/
│   │   ├── models.py                 # SQLAlchemy models (18 tables)
│   │   ├── database.py               # DB connection + session management
│   │   └── persistence.py            # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   ├── trends.py                 # Historical trend analysis (14 query methods)
│   │   ├── flight_patterns.py        # Russian/Chinese flight pattern analyzer
│   │   ├── supply_chain.py          # PSI: 6-dimension risk scoring + scenarios
│   │   ├── supply_chain_graph.py    # PSI: NetworkX knowledge graph engine
│   │   ├── supply_chain_seed.py     # PSI: BOM seed data for 20 platforms
│   │   ├── supplier_risk.py         # Canadian supplier 6-dimension exposure scoring
│   │   ├── risk_taxonomy.py         # DND Annex B 13-category risk taxonomy (121 sub-cats)
│   │   ├── confidence.py            # Glass Box confidence scoring utility (source triangulation)
│   │   ├── mitigation_playbook.py   # COA playbook (191 entries) + generation engine
│   │   ├── forecasting.py           # Predictive analytics (6 forecast types, 12-18 month horizon)
│   │   ├── ml_engine.py             # Anomaly detection + adaptive RLHF threshold adjustment
│   │   ├── cyber_threat_intel.py    # APT groups, breach registry, Tor nodes, IOC aggregation
│   │   ├── briefing_generator.py    # PDF intelligence briefing (fpdf2, 7-page export)
│   │   ├── source_registry.py       # Universal source validation registry (50 hierarchical keys, 8 source types)
│   │   ├── mineral_supply_chains.py # 30 mineral supply chains (USGS 2025, geo-coords, Canada deps, deep Cobalt data)
│   │   ├── cobalt_forecasting.py    # Live cobalt forecasting: IMF PCOBALT primary + FRED nickel fallback + linear regression + insolvency scoring
│   │   ├── financial_scoring.py    # Altman Z-Score computation from financial filings
│   │   ├── cobalt_alert_engine.py   # Live Cobalt alert engine: GDELT keyword monitoring + rule-based triggers (30-min scheduler)
│   │   └── scenario_engine.py      # Multi-variable scenario sandbox engine: layer composition, cascade propagation, impact metrics
│   ├── api/
│   │   ├── routes.py                 # Core API endpoints (live external sources)
│   │   ├── trend_routes.py           # Trend analysis endpoints (/trends/*)
│   │   ├── dashboard_routes.py       # Dashboard endpoints (DB-backed + cached)
│   │   ├── insights_routes.py        # Intelligence insights + situation report
│   │   ├── arctic_routes.py          # Arctic security assessment + bases
│   │   ├── psi_routes.py            # Predictive Supplier Insights (13 endpoints)
│   │   ├── supplier_routes.py       # Canadian supplier exposure (6 endpoints)
│   │   ├── mitigation_routes.py     # COA endpoints (GET/PATCH/POST /mitigation/*)
│   │   ├── briefing_routes.py       # PDF briefing endpoint (GET /briefing/pdf)
│   │   ├── security_routes.py       # Auth, RBAC, audit log (/security/*)
│   │   ├── ml_routes.py             # Anomaly detection + feedback + thresholds (/ml/*)
│   │   ├── validation_routes.py      # Universal source validation (/validation/sources, /validation/health)
│   │   ├── enrichment_routes.py     # 40+ data enrichment endpoints (/enrichment/*)
│   │   ├── export_routes.py         # CSV/Excel data export (/export/*)
│   │   ├── cyber_routes.py          # Cyber threat intelligence (/cyber/*)
│   │   ├── globe_routes.py          # 3D supply chain globe data (/globe/*)
│   │   └── forecast computed live  # via globe_routes.py /globe/minerals/{name}/forecast
│   ├── static/
│   │   └── index.html                # Dashboard UI (7 tabs, ~11,670 lines, EN/FR bilingual, 2 CesiumJS globes)
│   ├── alerts/                       # (placeholder — not yet implemented)
│   └── main.py                       # App entry point
├── scripts/
│   └── seed_database.py              # Initial data load
├── config/
│   └── .env.example                  # API key template
├── tests/                            # 364 tests (models, persistence, risk scoring, taxonomy, routes, scraper, ML, mitigation, globe, forecasting, scenario engine, source validation, scheduler feeds, FIRMS thermal, Sentinel NO2)
├── docs/superpowers/                 # Design specs and implementation plans
├── Dockerfile                        # Container image definition
├── docker-compose.yml                # Multi-service local orchestration
├── deploy/
│   └── azure/
│       └── deploy.sh                 # Azure Container Apps deployment script
├── requirements.txt
└── README.md
```

## Data Sources (58 active + 2 inactive)

| # | Source | Connector | Freshness | Auth | Status |
|---|--------|-----------|-----------|------|--------|
| 1 | Defense News RSS | `defense_news_rss.py` | Hours (4 feeds) | None | Working |
| 2 | Military Flights (adsb.lol) | `flight_tracker.py` | Live (60s) | None | Working |
| 2b | Military Flights (adsb.fi) | `flight_tracker.py` | Live (60s) | None | Working |
| 2c | Military Flights (Airplanes.live) | `flight_tracker.py` | Live (60s) | None | Working |
| 2d | Military Flights (ADSB One) | `flight_tracker.py` | Live (60s) | None | Working |
| 3 | GDELT News | `gdelt_news.py` | 15 min | None | Working |
| 4 | DSCA Arms Sales | `dsca_sales.py` | Days | None | Working |
| 5 | Statistics Canada | `statcan_trade.py` | Monthly | None | Working |
| 6 | US Census Trade | `census_trade.py` | Monthly | None | Working |
| 7 | UK HMRC Trade | `uk_hmrc_trade.py` | Monthly | None | Working |
| 8 | Eurostat EU Trade | `eurostat_trade.py` | Monthly | None | Working |
| 9 | NATO Spending | `nato_spending.py` | Annual (2025 est.) | None | Working |
| 10 | SIPRI Transfers | `sipri_transfers.py` | Annual (2025) | None | Working |
| 11 | World Bank | `worldbank.py` | Annual (2024) | None | Working |
| 12 | UN Comtrade | `comtrade.py` | Annual (2023) | None | Working |
| 13 | Sanctions/Embargoes | `sanctions.py` | On-demand | None | Working |
| 14 | DND Procurement | `procurement_scraper.py` | Weekly (Sun 02:00) | None | Working |
| 15 | SIPRI Military Expenditure | `sipri_milex.py` | Annual | None | Working |
| 16 | CIA World Factbook | `cia_factbook.py` | Annual | None | Working |
| 17 | World Bank Governance | `worldbank_enrichment.py` | Annual | None | Working |
| 18–43 | 26 OSINT Feeds | `osint_feeds.py` | 15min–Daily | None | Working |
| - | Maritime (AIS) | `maritime_tracker.py` | Live | API key | Needs key |
| - | SIPRI Companies | `sipri_companies.py` | Annual | None | Needs URL |
| 44 | BGS World Minerals | `bgs_minerals.py` | Annual | None | Working |
| 45 | NRCan Cobalt Facts | `nrcan_cobalt.py` | Annual | None | Working |
| 46 | Sherritt International | `sherritt_cobalt.py` | Quarterly | None | Working |
| 47 | Cobalt Players (15 cos.) | `cobalt_players.py` | Hourly | None | Working |
| 48 | GLEIF LEI Ownership | `osint_feeds.py` | On-demand | None | Working |
| 49 | SEC EDGAR XBRL | `osint_feeds.py` | Quarterly | None | Working |
| 50 | IMF Cobalt Prices | `cobalt_forecasting.py` | Monthly | None | Working |
| 51 | Comtrade Cobalt Bilateral | `comtrade.py` | Monthly | API key | Working |
| 52 | NASA FIRMS Thermal | `firms_thermal.py` | 6 hours (18 facilities) | MAP_KEY (free) | Working |
| 53 | Sentinel-5P NO2 | `sentinel_no2.py` | Daily (18 facilities) | OAuth (free) | Working |

## Intelligence Features

| Feature | Source | What It Does |
|---------|--------|-------------|
| **Situation Report** | insights_routes.py | 6 threat indicators (Arctic, supply chain, adversary expansion, NATO rearmament, Canada rank, sanctions) |
| **Buyer-side Mirror** | comtrade.py | Tracks Russia/China exports by querying what buyers report importing |
| **Sanctions Overlay** | sanctions.py | 17 embargoed countries, OFAC SDN list, EU sanctions |
| **Flight Pattern Analysis** | flight_patterns.py | Identifies Russian/Chinese military aircraft, flags suspicious routes |
| **Arctic Base Registry** | arctic_routes.py | 25 Arctic bases with threat levels, distances to Canada |
| **Shift Detection** | insights_routes.py | Detects countries changing primary arms supplier with context |
| **Arctic Routes** | index.html | 3 labeled shipping routes (NSR, NWP, Transpolar) with ownership |
| **PSI: Supply Chain Risk** | supply_chain.py | 6-dimension risk scoring (concentration, sanctions, chokepoints, instability, scarcity, alternatives) |
| **PSI: Knowledge Graph** | supply_chain_graph.py | NetworkX graph: 90 nodes (materials, components, platforms), 97 edges, BOM explosion |
| **PSI: BOM Explosion** | supply_chain_graph.py | Trace weapon platform -> subsystems -> components -> raw materials -> source countries |
| **PSI: Scenario Sandbox** | scenario_engine.py, supply_chain.py | Multi-variable "Digital Twin" sandbox: stackable disruption layers (sanctions, shortages, route disruptions, supplier failures, demand surges), 5 preset compound scenarios (Indo-Pacific Conflict, Arctic Escalation, Global Recession, DRC Collapse, Suez Closure), Sankey cascade visualization (4-tier Rocks-to-Rockets), Likelihood×Impact scoring with dollar values, up to 4 saved runs with side-by-side comparison, COA comparison drawer, PDF/CSV/JSON export |
| **PSI: Critical Minerals** | critical_minerals.py | 30 defense-critical materials with USGS production data, HHI concentration indices |
| **PSI: 3D Supply Globe** | mineral_supply_chains.py, globe_routes.py | CesiumJS 3D globe: 30 minerals with 4-tier flow (mine→process→component→platform), 11 sea routes + 5 overland routes (Cobalt) to 5 Canadian ports, risk-colored sea lanes, entity-level 13-category DND risk taxonomy scorecards |
| **PSI: Cobalt Deep Dive** | mineral_supply_chains.py | 9 named mines, 9 refineries, 8 defence alloys (Waspaloy/CMSX-4/Stellite), 16 logistics routes (11 sea + 5 overland) with risk ratings, 13-cat taxonomy scores + KPIs per entity, Canada platform-engine dependencies |
| **PSI: Live Forecasting** | cobalt_forecasting.py, globe_routes.py | IMF PCOBALT direct cobalt prices (live, monthly) → quarterly linear regression → 12-month price forecast; FRED nickel as fallback; lead time from sea routes + chokepoint risk; supplier insolvency from real Altman Z-scores (financial_scoring.py); auto-generated signals |
| **PSI: BOM Explorer** | index.html | 4-tier Rocks-to-Rockets tree: Mining → Processing → Alloys (8 cobalt alloys with Co%) → CAF Platforms via engines; computed confidence per tier from source counts; HS codes (5 entries) and NSN entries (6 items, illustrative) |
| **PSI: Supplier Dossier** | mineral_supply_chains.py | Per-entity deep dive: 18 entities (mines + refineries), FOCI badges, Altman Z-Score, UBO ownership chains, recent intelligence, DND contract summary |
| **PSI: Watchtower Alerts** | cobalt_alert_engine.py, mineral_supply_chains.py | 6 seed alerts + live GDELT keyword monitoring (8 queries) + rule-based triggers (HHI, China refining, paused ops); SEEDED/LIVE badges; Acknowledge/Assign/Escalate persist to DB; Evidence Locker |
| **PSI: Risk Register** | mineral_supply_chains.py, psi_routes.py | 10 cobalt risks cataloged with ID, category, severity, status lifecycle (Open→In Progress→Mitigated→Closed), owner, due dates, linked COA IDs (cross-referenced to sufficiency COAs), evidence; status persists to DB and survives reload |
| **PSI: Analyst Feedback** | mineral_supply_chains.py, ml_routes.py | RLHF panel: live ML stats overlay (accuracy, FP rate from /ml/thresholds), LIVE/BASELINE badge, 4 pending adjudications (Verified/False Positive POST to /ml/feedback), Z-score threshold synced from live ML engine |
| **PSI: Material Trade** | comtrade.py | 27 expanded HS codes: ores, rare earths, specialty metals, semiconductors, propellants |
| **Supplier Exposure** | supplier_risk.py | 6-dimension risk scoring for Canadian defence suppliers (foreign ownership, concentration, single-source, contract activity, sanctions, performance) |
| **Procurement Intel** | procurement_scraper.py | DND contracts from Open Canada disclosure portal, vendor normalization, sector classification |
| **Ownership Enrichment** | corporate_graph.py | Wikidata SPARQL lookup for company parent chains and country of origin |
| **DND Risk Taxonomy** | risk_taxonomy.py | Full 13-category, 121 sub-category Annex B compliance. Live OSINT scoring for 4 categories, hybrid for 3, seeded with drift for 6. Displayed on Insights landing page (13-card strip) and Supply Chain tab (accordion drill-down) |
| **COA/Mitigation Engine** | mitigation_playbook.py, mitigation_routes.py | 191-entry courses-of-action playbook across all 13 risk categories; auto-generates mitigations from risk scores; Action Centre with status tracking (open/in-progress/closed) |
| **Confidence Scoring** | confidence.py | Glass Box per-indicator confidence levels; source triangulation (number of independent sources agreeing); displayed alongside every risk score. Active cobalt triangulation: pairwise cross-check of BGS + USGS + NRCan + Comtrade with discrepancy detection (>25% = warning, >50% = critical). Live HHI computation from BGS data. |
| **Cobalt Bilateral Trade** | comtrade.py | 10 bilateral corridors queried monthly via Comtrade Plus API (4 HS codes: 2605, 810520, 810590, 282200). Buyer-side mirror for DRC corridors. Real trade values ($2.39B DRC→China 2023) surfaced in globe, BOM, scenario, dossier. |
| **Supplier Dossiers (18)** | mineral_supply_chains.py | All 18 cobalt mines + refineries have real dossiers: Altman Z-score (computed or parent-consolidated), UBO ownership chains, FOCI score (0-100), recent OSINT intel, financial snapshots. FOCI ranges from 8 (Niihama/Japan) to 98 (Jinchuan/PRC SOE). |
| **Predictive Analytics** | forecasting.py | 6 forecast types (spending trajectories, supplier shift probability, material scarcity, threat escalation, alliance drift, procurement lead times); 12–18 month horizon |
| **ML Anomaly Detection** | ml_engine.py | Statistical anomaly detection across all data streams; RLHF feedback loop with adaptive threshold adjustment (FP rate >30% raises threshold, <10% lowers it) |
| **Disinformation Detection** | gdelt_news.py | 3-layer detection: known state-media domains (RT, TASS, PressTV), extreme tone scoring, sensationalist title patterns |
| **Cyber Threat Intelligence** | cyber_threat_intel.py | 13 APT groups, Tor exit nodes, CISA KEV, NVD CVEs, DIB breach registry, supplier cyber risk, IOC aggregation |
| **CSV/Excel Export** | export_routes.py | Transfers, suppliers, news, taxonomy, **Cobalt risk register**, **Cobalt alerts** as CSV or Excel download |
| **PDF Intelligence Briefing** | briefing_generator.py, briefing_routes.py | One-click **8-page** PDF export (fpdf2): executive summary, threat matrix, Arctic assessment, supplier risks, **Cobalt supply chain intelligence**, recommendations |
| **Security / RBAC** | auth.py, security_routes.py | API key authentication (loaded from env); 3 roles enforced (viewer, analyst, admin); CORS, TLS redirect, trusted hosts; full audit log |
| **Universal Source Validation** | source_registry.py, validation_routes.py, index.html | Every card, table, stat box across all 7 tabs has expandable "Sources & Validation" panel showing source citations, type badges, live data health (last fetch, records, cache status), and confidence assessment. 50 hierarchical registry keys with inheritance. |
| **Satellite Thermal Verification** | firms_thermal.py, globe_routes.py, index.html | NASA FIRMS VIIRS NOAA-20 (375m) thermal anomaly detection for all 18 cobalt mines/refineries. Per-facility bounding boxes (2-8km adaptive). Status badges on globe pins (green=ACTIVE, amber=IDLE). Fuzzy red thermal bloom markers. FRP sparkline history (30-day backfill). Click popup with brightness, FRP, detection timestamp. GIBS VIIRS global thermal tile overlay. |
| **Satellite NO2 Verification** | sentinel_no2.py, globe_routes.py, index.html | Sentinel-5P TROPOMI NO2 column density for 18 cobalt facilities. Per-facility vs regional background ratio. Combined thermal+NO2 operational verdict (CONFIRMED ACTIVE / LIKELY ACTIVE / IDLE). Purple plume ellipses on globe. 30-day NO2 ratio history sparklines. |
| **Production Verification** | sentinel_no2.py, globe_routes.py, index.html | Verification sub-tab (#13) cross-referencing FIRMS thermal + Sentinel-5P NO2 satellite signals against reported facility production capacity. 18 cobalt facilities in card grid with Sentinel-2 satellite thumbnails (click to zoom 512px modal), overlay charts (30-day thermal FRP + NO2 ratio + capacity reference line), cloud coverage indicator with scoring adjustment. Verification score (0-100%) with CONSISTENT/INCONCLUSIVE/DISCREPANCY verdicts. Sort by score/name/country/capacity, filter by verdict. Satellite Intelligence summary card on Alerts & Sensing tab (KPIs, anomaly detection, source badges). |
| **Docker/Azure Deployment** | Dockerfile, docker-compose.yml, deploy/azure/deploy.sh | Containerised production deployment; Azure Container Apps deploy script |

## Dashboard UI (7 tabs, EN/FR bilingual)

| Tab | Purpose |
|-----|---------|
| **Insights** | Intelligence briefing: **13-category risk taxonomy strip**, situation report, live news, DSCA sales, alerts, adversary flows, Canada position, shifting alliances, what to watch |
| **Arctic** | **3D CesiumJS globe** (Esri satellite imagery): 8 toggleable layers (25 bases, 3 shipping routes, live flights from 4 ADS-B sources, ADIZ, ice edge, base networks, weapon range rings, trade flows). Transport freight estimation with payload/origin/destination. Base cargo intelligence chart. Top trade routes table + regional breakdown. KPI cards, base intel table, current intelligence panel. |
| **Deals** | Searchable/filterable table of all 9,311 transfers with TIV glossary tooltips |
| **Canada Intel** | Ally vs adversary flows, threat watchlist, Arctic monitor, supply chain, shifting alliances, **defence supply base exposure** (10 suppliers, risk ranking, sector concentration, ownership), **Action Centre** |
| **Supply Chain** | PSI: 13 sub-tabs (Overview, 3D Supply Map, Knowledge Graph, Risk Matrix, Scenario Sandbox, Risk Taxonomy, **Forecasting**, **BOM Explorer**, **Supplier Dossier**, **Alerts & Sensing**, **Risk Register**, **Analyst Feedback**, **Verification**) — all default to Cobalt |
| **Data Feeds** | Operations view: feed status cards across 10 sections with freshness, sample data, health indicators |
| **Compliance** | DMPP 11 compliance matrix: 22 RFI questions, 118 sub-requirements with traceability, evidence, and View buttons |

## API Endpoints (150+ total)

### Core (src/api/routes.py) — live external APIs
- `GET /transfers/exports/{country}`, `/imports/{country}`, `/bilateral/{seller}/{buyer}`
- `GET /indicators/{country_iso3}`, `/top/importers`, `/top/exporters`
- `GET /news/latest`, `/news/country/{country}`
- `GET /tracking/flights/military`, `/transports`

### Dashboard (src/api/dashboard_routes.py) — DB-backed + cached
- `GET /dashboard/transfers`, `/flows`, `/country-totals`, `/weapon-types`
- `GET /dashboard/comtrade/exports`, `/comtrade/country/{name}`
- `GET /dashboard/census/monthly`, `/uk-trade/monthly`, `/eu-trade/monthly`, `/canada-trade/monthly`
- `GET /dashboard/nato/spending`
- `GET /dashboard/news/live`, `/dsca/recent`
- `GET /dashboard/sanctions/embargoes`, `/sanctions/check/{country}`, `/sanctions/ofac-sdn`, `/sanctions/eu`
- `GET /dashboard/adversary-trade/buyer-mirror`
- `GET /dashboard/flights/analysis`

### Insights (src/api/insights_routes.py)
- `GET /insights/all` — 8 insight categories + situation report
- `GET /insights/freshness` — data source freshness for all 14 sources

### Arctic (src/api/arctic_routes.py)
- `GET /arctic/assessment` — force balance, NATO vs Russia, NSR threats, weapon timeline, Russia weakness
- `GET /arctic/bases` — 25-base registry with threat levels + distances
- `GET /arctic/flights` — live Arctic military flights classified by nation

### Trends (src/api/trend_routes.py)
- `GET /trends/summary`, `/global/volume`, `/global/categories`, `/global/top-pairs`
- `GET /trends/country/{name}/profile`, `/exports`, `/imports`
- `GET /trends/changes/imports`
- `GET /trends/companies/{name}`, `/top/{year}`
- `GET /trends/activity/flights`, `/news`

### PSI / Supply Chain (src/api/psi_routes.py)
- `GET /psi/overview` — Global risk summary, top risks, material dependencies, alerts
- `GET /psi/risk/{country}` — 6-dimension risk scores + composite + mitigations
- `GET /psi/material/{name}` — Material scarcity, source countries, dependent platforms
- `GET /psi/platform/{weapon}` — BOM tree with risk at each tier
- `POST /psi/scenario` — What-if simulation (5 scenario types, legacy)
- `POST /psi/scenario/v2` — Multi-variable scenario sandbox (stackable layers, cascade propagation, Likelihood×Impact, COAs)
- `POST /psi/scenario/export/pdf` — PDF briefing export from scenario results (single or multi-scenario comparison)
- `GET /psi/graph` — Knowledge graph as D3.js-ready JSON
- `GET /psi/suppliers/{name}` — Company profile, alternatives
- `GET /psi/alerts` — Active supply chain disruption alerts
- `GET /psi/chokepoints` — Strategic chokepoint status
- `GET /psi/propagation` — Disruption cascade analysis
- `GET /psi/taxonomy` — All 13 DND risk categories with composite scores
- `GET /psi/taxonomy/summary` — Dashboard-ready 13-card summary for Insights strip
- `GET /psi/taxonomy/{category_id}` — Single category drill-down with all sub-categories
- `GET /psi/alerts/cobalt/live` — Live-generated Cobalt alerts (GDELT + rule engine, cached 30min)
- `POST /psi/alerts/cobalt/action` — Record analyst action on Cobalt alert (DB-persisted)
- `GET /psi/alerts/cobalt/actions` — Get all recorded Cobalt alert actions
- `PATCH /psi/register/cobalt/{risk_id}` — Update Cobalt risk register status (DB-persisted)
- `GET /psi/register/cobalt/status` — Get all Cobalt risk register status overrides

### Supplier Exposure (src/api/supplier_routes.py)
- `GET /dashboard/suppliers` — All Canadian defence suppliers with 6-dimension risk scores
- `GET /dashboard/suppliers/{name}/profile` — Single supplier detail with contracts and risk dimensions
- `GET /dashboard/suppliers/concentration` — Sector-level analysis, sole-source detection
- `GET /dashboard/suppliers/risk-matrix` — Scatter plot data (contract value vs risk score)
- `GET /dashboard/suppliers/ownership` — Ownership type breakdown, foreign subsidiary list
- `GET /dashboard/suppliers/alerts` — Suppliers with any risk dimension >70

### Mitigation / COA (src/api/mitigation_routes.py)
- `GET /mitigation/actions` — All active COA entries with status and owner
- `GET /mitigation/actions/{id}` — Single COA detail with playbook entry and evidence
- `PATCH /mitigation/actions/{id}` — Update COA status (open → in-progress → closed)
- `POST /mitigation/generate` — Auto-generate COAs from a risk score payload
- `GET /mitigation/playbook` — Full 191-entry playbook reference

### Briefing (src/api/briefing_routes.py)
- `GET /briefing/pdf` — Generate and download 7-page PDF intelligence briefing

### Security (src/api/security_routes.py)
- `GET /security/whoami` — Current API key identity and role
- `GET /security/roles` — RBAC role definitions (viewer, analyst, admin)
- `GET /security/audit` — Audit log of recent data access and exports
- `GET /security/posture` — Platform security posture summary

### ML / Anomaly Detection (src/api/ml_routes.py)
- `GET /ml/anomalies` — Current detected anomalies across all data streams
- `POST /ml/feedback` — Submit analyst feedback (true/false positive) for RLHF retraining
- `GET /ml/capabilities` — Available ML model descriptions and thresholds
- `GET /ml/thresholds` — Current z-score threshold, RLHF-adjusted threshold, feedback stats
- `POST /ml/thresholds` — Set custom z-score threshold override

### Export (src/api/export_routes.py)
- `GET /export/transfers/csv` — All arms transfers as CSV download
- `GET /export/transfers/excel` — All arms transfers as Excel (.xlsx) download
- `GET /export/suppliers/csv` — Defence suppliers as CSV
- `GET /export/news/csv` — News articles as CSV
- `GET /export/taxonomy/csv` — Risk taxonomy scores as CSV
- `GET /export/cobalt/register/csv` — Cobalt risk register as CSV
- `GET /export/cobalt/alerts/csv` — Cobalt watchtower alerts as CSV

### Globe / 3D Supply Map (src/api/globe_routes.py)
- `GET /globe/minerals` — All 30 mineral supply chains with geo-coordinates, Canada dependencies
- `GET /globe/minerals/{name}` — Single mineral with full chain (deep data for Cobalt: mines, refineries, alloys, sea_routes, overland_routes, taxonomy scores, 18 dossiers, live HHI)
- `GET /globe/minerals/{name}/forecast` — Live computed forecast (FRED nickel proxy, linear regression, insolvency, lead time)
- `GET /globe/facility/thumbnail?lat=&lon=` — Sentinel-2 true-color satellite thumbnail (256x256 PNG, 30-day mosaic, <30% cloud)

### Validation (src/api/validation_routes.py)
- `GET /validation/sources` — Full source registry (50 keys, hierarchical inheritance, cached 1hr)
- `GET /validation/health` — Live connector health (last fetch, records, cache status, cached 60s)

### Enrichment (src/api/enrichment_routes.py)
- `GET /enrichment/sources` — All 53 active source status and metadata
- `GET /enrichment/country/{iso3}` — Full enriched country profile (governance, fragility, military)
- `GET /enrichment/governance/{iso3}` — World Bank WGI governance indicators
- `GET /enrichment/fragility/{iso3}` — State fragility and instability scores
- `GET /enrichment/milex/{iso3}` — SIPRI military expenditure time series
- `GET /enrichment/factbook/{iso3}` — CIA World Factbook military data
- `GET /enrichment/confidence/{entity}` — Glass Box confidence breakdown for any entity
- And 8+ additional enrichment endpoints

## Database
- **18 tables:** countries, weapon_systems, arms_transfers, defense_companies, trade_indicators, arms_trade_news, delivery_tracking, supply_chain_materials, supply_chain_nodes, supply_chain_edges, supply_chain_routes, supply_chain_alerts, defence_suppliers, supplier_contracts, supplier_risk_scores, risk_taxonomy_scores, **mitigation_actions**, **audit_log**
- **Current data:** 9,311 transfers, 5,110 indicators, flight positions (live), 167 news articles, 30 materials, 90 supply chain nodes, 96 edges, 16 cobalt routes (11 sea + 5 overland), 8 alerts, 10 Canadian suppliers, 121 taxonomy scores, 191 COA playbook entries
- **Coverage:** 26 seller countries, 186 buyer countries, 256 countries total

## How to Run
```bash
cd weapons-tracker
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # macOS/Linux

# Seed database (one-time)
python -m scripts.seed_database

# Start server (dashboard + API + scheduler)
python -m src.main
# Dashboard at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Key Design Decisions
- SQLite for dev (zero config), PostgreSQL+PostGIS for prod
- All connectors are async (httpx + asyncio)
- `from __future__ import annotations` required in all files (Python 3.9 compat)
- Dashboard served as static HTML by FastAPI — no build step, CDN-loaded libs
- External API responses cached in-memory (15min–24hr TTL depending on source)
- Insights tab is the default landing page — structured as an intelligence briefing
- Arctic tab provides dedicated northern security assessment with base-level detail
- Buyer-side Comtrade mirror circumvents Russia/China data opacity
- Sanctions overlay flags embargoed trade partners automatically

## Security Controls (Applied 2026-03-29)
- RBAC enforcement with role hierarchy (viewer < analyst < admin)
- API keys loaded from `API_KEYS_JSON` env var (no hardcoded secrets in production)
- Error sanitization: 72 endpoints fixed, no `str(e)` leakage
- XSS prevention: `esc()` applied to all dynamic HTML injection points
- CORS middleware with configurable origins (`CORS_ORIGINS` env var)
- HTTPS redirect in production (`ENVIRONMENT=production`)
- Trusted host middleware (`ALLOWED_HOSTS` env var)
- Disinformation detection on ingested news (3-layer: domain, tone, pattern)
- WCAG 2.1 AA: ARIA roles on all tabs/panels, labels on maps/charts
- NASA FIRMS thermal requires `NASA_FIRMS_MAP_KEY` env var (free from https://firms.modaps.eosdis.nasa.gov/api/area/)
- Sentinel-5P NO2 requires `SENTINEL_CLIENT_ID` + `SENTINEL_CLIENT_SECRET` env vars (free from https://dataspace.copernicus.eu)

## Known Code Quality Items
- `routes.py` endpoints hit live external APIs per-request; dashboard routes serve from DB instead
- Sync SQLAlchemy sessions in async endpoints — acceptable for SQLite, needs async for PostgreSQL
- `main.py` uses deprecated `@app.on_event` instead of lifespan context manager
- `datetime.utcnow()` deprecated — ~20 occurrences should migrate to `datetime.now(timezone.utc)`
- No Alembic migrations — using `create_all()` only
- NASA FIRMS VIIRS 375m resolution detects fire-scale heat — most enclosed refineries show 0 detections. Sentinel-5P TROPOMI NO2 now provides complementary industrial emissions detection for enclosed facilities.

## UI Design System
- **Fonts:** Inter (display + body), JetBrains Mono (numbers/stats/labels)
- **Signal Palette (desaturated):** `--accent` #00d4ff (cyan — primary operational), `--accent2` #D80621 (DND red — identity + threats), `--accent3` #6b9080 (sage — positive/live), `--accent4` #a89060 (ochre — warnings), `--accent5` #6b6b8a (slate — tertiary)
- **Surfaces:** Sharp-edge cards (no border-radius), solid `#111620` backgrounds, white-based borders `rgba(255,255,255,0.06)`
- **Atmosphere:** Fixed 80px grid overlay, red/cyan radial glow, 16s scan line sweep
- **Components:** `.card`, `.stat-box`, `.stat-num`, `.stat-label`, `.insight-alert`, `.btn-primary` (red), `.nav-tab` (monospace underline), `.side-nav` (right-side nav), `.cb` (classification bar)
- **Theme Toggle:** Dark/Light mode via `body.light` class, persists in `localStorage` key `cmct-theme`
- **Section Headers:** Monospace tag (`SECTION 01`) + Inter title pattern
- **Responsive:** Breakpoints at 1200px, 960px (side-nav hides), 768px, 600px

## Next Steps (Priority Order)
1. Continue theme unification to remaining tabs (Arctic, Canada Intel, Supply Chain sub-tabs, Data Feeds, Compliance) — foundation CSS already applied, needs per-tab polish
2. ~~Sentinel-5P TROPOMI NO2 layer~~ (DONE — daily polling, purple plume ellipses, combined verdict)
3. Deep-dive remaining 29 minerals (same depth as Cobalt: mines, refineries, alloys, sea + overland routes, 13-cat taxonomy per entity, HS codes, NSN)
4. Explore diamond/custom markers for globe facilities (CesiumJS 1.119 billboard crashes — needs Cesium upgrade or PointPrimitive approach)
5. Full light theme QA pass across all tabs (Cesium/Leaflet globes don't respond to CSS variables)
6. Full French translation of dynamic content (currently covers nav tabs + PSI sub-tab headers; body content is English-only)
7. Activate maritime tracker (needs aisstream.io API key)
8. Integrate searoute-js or Eurostat maritime routing for dynamic sea route calculation
9. Migrate to async SQLAlchemy sessions for production
10. Migrate `@app.on_event` to lifespan context manager
11. Add Alembic migration framework for production schema evolution
12. Expand ML anomaly detection with time-series models (LSTM/Prophet)
13. Add SAML/OAuth SSO integration for DND Azure AD
14. Formal PBMM / ITSG-33 security certification
