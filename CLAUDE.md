# CLAUDE.md — Weapons Tracker Project Context

## Project Goal
Geopolitical intelligence platform tracking global weapons sales, military spending, and force deployments
using OSINT data sources. Built for the Canadian government (DND) to understand: who is arming whom,
where are the threats, what's happening in the Arctic, and how is the world reshaping geopolitically.

## Tech Stack
- **Language:** Python 3.9+ (use `from __future__ import annotations` in all files)
- **API Framework:** FastAPI + Uvicorn (65 API endpoints)
- **Database:** SQLite (dev) / PostgreSQL + PostGIS (prod)
- **ORM:** SQLAlchemy 2.0 (declarative models)
- **HTTP Client:** httpx (async)
- **Scheduling:** APScheduler (AsyncIOScheduler)
- **Data Processing:** pandas, geopandas, openpyxl
- **Graph Analysis:** NetworkX (supply chain knowledge graph)
- **Frontend:** Single-page HTML dashboard (Chart.js, D3.js, Leaflet.js — no build step, ~5,300 lines)
- **Design System:** Outfit (display), IBM Plex Sans (body), JetBrains Mono (numbers); cyan accent (#00d4ff); glass-morphism cards
- **Codebase:** 44 Python files, ~15,000 total lines
- **Tests:** 28 tests (pytest) covering models, persistence, risk scoring, API endpoints, scraper utilities

## Project Structure
```
weapons-tracker/
├── src/
│   ├── ingestion/              # 16 data source connectors
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
│   │   └── scheduler.py              # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py                 # SQLAlchemy models (15 tables)
│   │   ├── database.py               # DB connection + session management
│   │   └── persistence.py            # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   ├── trends.py                 # Historical trend analysis (14 query methods)
│   │   ├── flight_patterns.py        # Russian/Chinese flight pattern analyzer
│   │   ├── supply_chain.py          # PSI: 6-dimension risk scoring + scenarios
│   │   ├── supply_chain_graph.py    # PSI: NetworkX knowledge graph engine
│   │   ├── supply_chain_seed.py     # PSI: BOM seed data for 20 platforms
│   │   └── supplier_risk.py         # Canadian supplier 6-dimension exposure scoring
│   ├── api/
│   │   ├── routes.py                 # Core API endpoints (live external sources)
│   │   ├── trend_routes.py           # Trend analysis endpoints (/trends/*)
│   │   ├── dashboard_routes.py       # Dashboard endpoints (DB-backed + cached)
│   │   ├── insights_routes.py        # Intelligence insights + situation report
│   │   ├── arctic_routes.py          # Arctic security assessment + bases
│   │   ├── psi_routes.py            # Predictive Supplier Insights (10 endpoints)
│   │   └── supplier_routes.py       # Canadian supplier exposure (6 endpoints)
│   ├── static/
│   │   └── index.html                # Dashboard UI (9 tabs, 5,317 lines)
│   ├── alerts/                       # (placeholder — not yet implemented)
│   └── main.py                       # App entry point
├── scripts/
│   └── seed_database.py              # Initial data load
├── config/
│   └── .env.example                  # API key template
├── tests/                            # 28 tests (models, persistence, risk scoring, routes, scraper)
├── docs/superpowers/                 # Design specs and implementation plans
├── requirements.txt
└── README.md
```

## Data Sources (13 active + 2 inactive)

| # | Source | Connector | Freshness | Auth | Status |
|---|--------|-----------|-----------|------|--------|
| 1 | Defense News RSS | `defense_news_rss.py` | Hours (4 feeds) | None | Working |
| 2 | Military Flights | `flight_tracker.py` | Live (5 min) | None | Working |
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
| - | Maritime (AIS) | `maritime_tracker.py` | Live | API key | Needs key |
| - | SIPRI Companies | `sipri_companies.py` | Annual | None | Needs URL |

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
| **PSI: Scenario Modeling** | supply_chain.py | 5 what-if simulations: sanctions expansion, material shortage, route disruption, demand surge, supplier substitution |
| **PSI: Critical Minerals** | critical_minerals.py | 30 defense-critical materials with USGS production data, HHI concentration indices |
| **PSI: Material Trade** | comtrade.py | 27 expanded HS codes: ores, rare earths, specialty metals, semiconductors, propellants |
| **Supplier Exposure** | supplier_risk.py | 6-dimension risk scoring for Canadian defence suppliers (foreign ownership, concentration, single-source, contract activity, sanctions, performance) |
| **Procurement Intel** | procurement_scraper.py | DND contracts from Open Canada disclosure portal, vendor normalization, sector classification |
| **Ownership Enrichment** | corporate_graph.py | Wikidata SPARQL lookup for company parent chains and country of origin |

## Dashboard UI (9 tabs)

| Tab | Purpose |
|-----|---------|
| **Insights** | Intelligence briefing: situation report, live news, DSCA sales, alerts, adversary flows, Canada position, shifting alliances, what to watch |
| **Overview** | Trade flow network (D3), top exporters/importers, weapon types, timeline |
| **World Map** | Leaflet map with trade arcs, country bubbles, Comtrade USD values, regional breakdown |
| **Arctic** | Force balance map with 25 bases, 3 shipping routes, Northern Sea Route threats, weapon timeline, live airspace |
| **Live Flights** | Real-time military aircraft positions (auto-refreshes 30s) |
| **Deals** | Searchable/filterable table of all 4,623 transfers |
| **Canada Intel** | Ally vs adversary flows, threat watchlist, Arctic monitor, supply chain, shifting alliances, **defence supply base exposure** (risk ranking, sector concentration, ownership) |
| **Supply Chain** | PSI: Risk overview (radar chart, material risks, alerts), Knowledge Graph (D3.js force-directed), Risk Matrix (scatter plot), Scenario Sandbox (what-if simulations) |
| **Data Feeds** | Operations view: 16 feed status cards with freshness, sample data, health indicators |

## API Endpoints (65 total)

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
- `POST /psi/scenario` — What-if simulation (5 scenario types)
- `GET /psi/graph` — Knowledge graph as D3.js-ready JSON
- `GET /psi/suppliers/{name}` — Company profile, alternatives
- `GET /psi/alerts` — Active supply chain disruption alerts
- `GET /psi/chokepoints` — Strategic chokepoint status
- `GET /psi/propagation` — Disruption cascade analysis

### Supplier Exposure (src/api/supplier_routes.py)
- `GET /dashboard/suppliers` — All Canadian defence suppliers with 6-dimension risk scores
- `GET /dashboard/suppliers/{name}/profile` — Single supplier detail with contracts and risk dimensions
- `GET /dashboard/suppliers/concentration` — Sector-level analysis, sole-source detection
- `GET /dashboard/suppliers/risk-matrix` — Scatter plot data (contract value vs risk score)
- `GET /dashboard/suppliers/ownership` — Ownership type breakdown, foreign subsidiary list
- `GET /dashboard/suppliers/alerts` — Suppliers with any risk dimension >70

## Database
- **15 tables:** countries, weapon_systems, arms_transfers, defense_companies, trade_indicators, arms_trade_news, delivery_tracking, supply_chain_materials, supply_chain_nodes, supply_chain_edges, supply_chain_routes, supply_chain_alerts, **defence_suppliers, supplier_contracts, supplier_risk_scores**
- **Current data:** 4,623 transfers, 5,110 indicators, 2,217 flight positions, 157 news articles, 30 materials, 90 supply chain nodes, 97 edges, 20 routes, 8 alerts
- **Coverage:** 26 seller countries, 174 buyer countries, 256 countries total

## How to Run
```bash
cd /Users/billdennis/weapons-tracker
source venv/bin/activate

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

## Known Code Quality Items
- `routes.py` endpoints hit live external APIs per-request; dashboard routes serve from DB instead
- Sync SQLAlchemy sessions in async endpoints — acceptable for SQLite, needs async for PostgreSQL
- `main.py` uses deprecated `@app.on_event` instead of lifespan context manager
- 5 large files (>500 lines): arctic_routes, dashboard_routes, insights_routes, sanctions, trends

## UI Design System
- **Fonts:** Outfit (display/headings), IBM Plex Sans (body), JetBrains Mono (numbers/stats)
- **Colors:** `--accent` #00d4ff (cyan), `--accent2` #ef4444 (red), `--accent3` #10b981 (green), `--accent4` #f59e0b (amber), `--accent5` #8b5cf6 (purple)
- **Surfaces:** Glass-morphism cards (`backdrop-filter: blur(16px)`), gradient header, cyan glow on hover
- **Components:** `.card`, `.stat-box`, `.stat-num`, `.stat-label`, `.insight-alert`, `.btn-primary`, `.nav-tab`
- **Responsive:** Breakpoints at 1200px and 768px

## Next Steps (Priority Order)
1. Build PDF briefing export for decision-makers
2. Build automated alerting system (unusual pattern detection)
3. Activate maritime tracker (needs aisstream.io API key)
4. Migrate to async SQLAlchemy sessions for production
5. Add satellite imagery integration for base monitoring
6. Add user authentication for multi-tenant deployment
