# CLAUDE.md — Weapons Tracker Project Context

## Project Goal
Geopolitical intelligence platform tracking global weapons sales, military spending, and force deployments
using OSINT data sources. Built for the Canadian government (DND) to understand: who is arming whom,
where are the threats, what's happening in the Arctic, and how is the world reshaping geopolitically.

## Tech Stack
- **Language:** Python 3.9+ (use `from __future__ import annotations` in all files)
- **API Framework:** FastAPI + Uvicorn (52 API endpoints)
- **Database:** SQLite (dev) / PostgreSQL + PostGIS (prod)
- **ORM:** SQLAlchemy 2.0 (declarative models)
- **HTTP Client:** httpx (async)
- **Scheduling:** APScheduler (AsyncIOScheduler)
- **Data Processing:** pandas, geopandas, openpyxl
- **Frontend:** Single-page HTML dashboard (Chart.js, D3.js, Leaflet.js — no build step, ~4,000 lines)
- **Codebase:** 33 Python files, ~12,800 total lines

## Project Structure
```
weapons-tracker/
├── src/
│   ├── ingestion/              # 15 data source connectors
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
│   │   └── scheduler.py              # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py                 # SQLAlchemy models (7 tables)
│   │   ├── database.py               # DB connection + session management
│   │   └── persistence.py            # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   ├── trends.py                 # Historical trend analysis (14 query methods)
│   │   └── flight_patterns.py        # Russian/Chinese flight pattern analyzer
│   ├── api/
│   │   ├── routes.py                 # Core API endpoints (live external sources)
│   │   ├── trend_routes.py           # Trend analysis endpoints (/trends/*)
│   │   ├── dashboard_routes.py       # Dashboard endpoints (DB-backed + cached)
│   │   ├── insights_routes.py        # Intelligence insights + situation report
│   │   └── arctic_routes.py          # Arctic security assessment + bases
│   ├── static/
│   │   └── index.html                # Dashboard UI (8 tabs, 4,030 lines)
│   ├── alerts/                       # (placeholder — not yet implemented)
│   └── main.py                       # App entry point
├── scripts/
│   └── seed_database.py              # Initial data load
├── config/
│   └── .env.example                  # API key template
├── tests/                            # (placeholder — no tests yet)
├── requirements.txt
└── README.md
```

## Data Sources (12 active + 2 inactive)

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

## Dashboard UI (8 tabs)

| Tab | Purpose |
|-----|---------|
| **Insights** | Intelligence briefing: situation report, live news, DSCA sales, alerts, adversary flows, Canada position, shifting alliances, what to watch |
| **Overview** | Trade flow network (D3), top exporters/importers, weapon types, timeline |
| **World Map** | Leaflet map with trade arcs, country bubbles, Comtrade USD values, regional breakdown |
| **Arctic** | Force balance map with 25 bases, 3 shipping routes, Northern Sea Route threats, weapon timeline, live airspace |
| **Live Flights** | Real-time military aircraft positions (auto-refreshes 30s) |
| **Deals** | Searchable/filterable table of all 4,623 transfers |
| **Canada Intel** | Ally vs adversary flows, threat watchlist, Arctic monitor, supply chain, shifting alliances |
| **Data Feeds** | Operations view: 16 feed status cards with freshness, sample data, health indicators |

## API Endpoints (52 total)

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

## Database
- **7 tables:** countries, weapon_systems, arms_transfers, defense_companies, trade_indicators, arms_trade_news, delivery_tracking
- **Current data:** 4,623 transfers, 5,110 indicators, 2,217 flight positions, 157 news articles
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

## Next Steps (Priority Order)
1. Build PDF briefing export for decision-makers
2. Build automated alerting system (unusual pattern detection)
3. Add test suite
4. Activate maritime tracker (needs aisstream.io API key)
5. Migrate to async SQLAlchemy sessions for production
6. Add satellite imagery integration for base monitoring
7. Add user authentication for multi-tenant deployment
