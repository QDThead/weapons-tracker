# CLAUDE.md — Weapons Tracker Project Context

## Project Goal
Geopolitical intelligence platform tracking global weapons sales and trade using OSINT data sources.
Built for the Canadian government (DND) to answer: who is selling what to whom, when, for how much,
and can we detect shifts in alliances and deliveries in real-time.

## Tech Stack
- **Language:** Python 3.9+ (use `from __future__ import annotations` in all files)
- **API Framework:** FastAPI + Uvicorn
- **Database:** SQLite (dev) / PostgreSQL + PostGIS (prod)
- **ORM:** SQLAlchemy 2.0 (declarative models)
- **HTTP Client:** httpx (async)
- **Scheduling:** APScheduler (AsyncIOScheduler)
- **Data Processing:** pandas, geopandas
- **Frontend:** Single-page HTML dashboard (Chart.js, D3.js, Leaflet.js — no build step)

## Project Structure
```
weapons-tracker/
├── src/
│   ├── ingestion/          # Data source connectors
│   │   ├── sipri_transfers.py    # SIPRI Arms Transfers DB (atbackend.sipri.org API)
│   │   ├── sipri_companies.py    # SIPRI Top 100 defense companies (Excel parser)
│   │   ├── worldbank.py          # World Bank arms trade indicators (REST API)
│   │   ├── gdelt_news.py         # GDELT arms trade news (REST API, 15-min updates)
│   │   ├── flight_tracker.py     # Military flight tracking via adsb.lol (live)
│   │   ├── maritime_tracker.py   # Maritime vessel tracking via aisstream.io (WebSocket)
│   │   ├── comtrade.py           # UN Comtrade real USD trade values (HS Chapter 93)
│   │   └── scheduler.py          # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py             # SQLAlchemy models (7 tables)
│   │   ├── database.py           # DB connection + session management
│   │   └── persistence.py        # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   └── trends.py             # Historical trend analysis engine (14 query methods)
│   ├── api/
│   │   ├── routes.py             # Core API endpoints (transfers, indicators, news, flights)
│   │   ├── trend_routes.py       # Trend analysis endpoints (/trends/*)
│   │   └── dashboard_routes.py   # Dashboard-specific DB-backed + Comtrade endpoints
│   ├── static/
│   │   └── index.html            # Dashboard UI (5 tabs, ~1500 lines)
│   ├── alerts/                   # (placeholder — not yet implemented)
│   └── main.py                   # App entry point (starts API + scheduler + serves dashboard)
├── scripts/
│   └── seed_database.py          # Initial full data load script
├── config/
│   └── .env.example              # API key template
├── tests/                        # (placeholder — no tests yet)
├── requirements.txt
└── README.md
```

## Data Sources

| Source | Connector | Data Type | Auth | Status |
|--------|-----------|-----------|------|--------|
| SIPRI Arms Transfers | `sipri_transfers.py` | Deal-level transfers (TIV) | None | Working |
| UN Comtrade | `comtrade.py` | Real USD trade values (HS 93) | None (preview) | Working |
| World Bank | `worldbank.py` | Aggregate TIV, mil. spending | None | Working |
| GDELT | `gdelt_news.py` | Arms trade news articles | None | Working |
| adsb.lol | `flight_tracker.py` | Live military aircraft positions | None | Working |
| AIS Stream | `maritime_tracker.py` | Maritime vessel tracking | API key | Not tested |
| SIPRI Companies | `sipri_companies.py` | Top 100 defense companies | None | Not tested |

## Dashboard UI (src/static/index.html)

5-tab single-page application served by FastAPI at `/`:

| Tab | Description |
|-----|-------------|
| **Overview** | Trade flow network (D3), top exporters/importers, weapon types, timeline |
| **World Map** | Leaflet choropleth with trade arcs, regional breakdown, UN Comtrade USD values |
| **Live Flights** | Real-time military aircraft map (auto-refreshes 30s), transport detection |
| **Deals** | Searchable/filterable table of all transfers with seller/buyer dropdowns |
| **Canada Intel** | Ally vs adversary flows, threat watchlist, Arctic monitor, supply chain, shifting alliances |

## API Endpoints

### Core (src/api/routes.py)
- `GET /transfers/exports/{country}` — SIPRI arms exports (live API)
- `GET /transfers/imports/{country}` — SIPRI arms imports (live API)
- `GET /transfers/bilateral/{seller}/{buyer}` — bilateral trade (live API)
- `GET /indicators/{country_iso3}` — World Bank indicators
- `GET /indicators/top/importers` and `/exporters`
- `GET /news/latest` and `/news/country/{country}` — GDELT news
- `GET /tracking/flights/military` and `/transports` — live flights

### Dashboard (src/api/dashboard_routes.py) — fast, DB-backed
- `GET /dashboard/transfers` — all transfers from DB (paginated)
- `GET /dashboard/flows` — aggregated seller→buyer trade flows
- `GET /dashboard/country-totals` — per-country export/import totals
- `GET /dashboard/weapon-types` — weapon type breakdown
- `GET /dashboard/comtrade/exports` — UN Comtrade USD values (cached 1hr)
- `GET /dashboard/comtrade/country/{name}` — country-specific Comtrade data (cached 1hr)

### Trends (src/api/trend_routes.py)
- `GET /trends/summary` — DB stats
- `GET /trends/global/volume` — global TIV by year
- `GET /trends/global/categories` — by weapon type
- `GET /trends/global/top-pairs` — seller→buyer pairs
- `GET /trends/country/{name}/profile` — full country profile
- `GET /trends/country/{name}/exports` and `/imports`
- `GET /trends/changes/imports` — biggest YoY changes
- `GET /trends/companies/{name}` and `/top/{year}`
- `GET /trends/activity/flights` and `/news`

## Scheduler (src/ingestion/scheduler.py)
| Job | Interval |
|-----|----------|
| Military flights (adsb.lol) | Every 5 min |
| GDELT arms news | Every 15 min |
| SIPRI transfers | Daily 2 AM |
| World Bank indicators | Daily 3 AM |

## Known Issues (as of March 2026)

### FIXED: SIPRI Export URL (March 2026)
- **Resolution:** Connector rewritten to use SIPRI's new backend API at `https://atbackend.sipri.org/api/p/`
- **How it works:** POST filter-based queries to `/trades/trade-register-csv/`, response is base64-encoded CSV
- **Country lookup:** Entity IDs fetched from `/countries/getAllCountriesTrimmed` (385 countries/entities)
- **Weapon categories:** Fetched from `/typelists/getAllArmamentCategories` (13 categories)
- **Note:** "Turkey" renamed to "Turkiye" in SIPRI's database

### TESTED & FIXED (March 2026)
- World Bank connector (`worldbank.py`) — works; minor: `country_iso3` stores 2-letter codes, top importers/exporters include aggregate regions
- GDELT connector (`gdelt_news.py`) — works after fixes: added 5s rate limit delay between queries, fixed OR query parentheses, guarded non-JSON responses
- adsb.lol flight tracker (`flight_tracker.py`) — works after fix: defensive float parsing for `alt_baro="ground"`

### NOT YET TESTED
- Maritime tracker (`maritime_tracker.py`) — requires `AISSTREAM_API_KEY` env var
- SIPRI Top 100 companies (`sipri_companies.py`) — needs valid Excel download URL

### NOT YET BUILT
- Alerting system (`src/alerts/`) — notifications for unusual patterns
- PDF briefing export for decision-makers
- Tests — no test suite yet
- SIPRI Top 100 ingestion in scheduler (only transfers and World Bank are scheduled)
- Maritime ingestion in scheduler (WebSocket streaming not integrated yet)

### Known Code Quality Items
- `routes.py` endpoints hit live external APIs per-request (no caching); dashboard routes serve from DB instead
- Sync SQLAlchemy sessions in async endpoints — acceptable for SQLite dev, needs async sessions for PostgreSQL prod
- `main.py` uses deprecated `@app.on_event` instead of lifespan context manager
- Multiple `_safe_float`/`_safe_int` implementations across connectors could be consolidated

## How to Run
```bash
cd /Users/billdennis/weapons-tracker
source venv/bin/activate          # venv already created with all deps installed

# Seed database
python -m scripts.seed_database

# Start API server (includes scheduler + dashboard)
python -m src.main
# Dashboard at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## Key Design Decisions
- SQLite for dev (zero config), PostgreSQL+PostGIS for prod
- All connectors are async (httpx + asyncio)
- Persistence layer handles deduplication via unique constraints
- Flight/vessel data stored as time-series snapshots (not deduplicated — intentional for trend analysis)
- `from __future__ import annotations` required in all files (Python 3.9 compat)
- Dashboard served as static HTML by FastAPI — no build step, CDN-loaded libs
- Comtrade API responses cached in-memory (1hr TTL) since data is annual
- Canada Intel tab provides geopolitical framing for DND analysts

## Next Steps (Priority Order)
1. ~~Fix SIPRI connector~~ — DONE
2. ~~Test remaining connectors~~ — DONE
3. ~~Build dashboard/UI~~ — DONE (5 tabs including Canada Intel)
4. ~~Add UN Comtrade~~ — DONE (real USD values)
5. Build PDF briefing export for decision-makers
6. Build alerting system (unusual pattern detection)
7. Add sanctions/embargo overlay
8. Add test suite
9. Migrate to async SQLAlchemy sessions for production
