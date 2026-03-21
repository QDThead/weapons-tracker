# CLAUDE.md — Weapons Tracker Project Context

## Project Goal
Track global weapons sales and trade across countries using OSINT data sources.
Focused on answering: who is selling what to whom, when, for how much, and can we detect deliveries in real-time.

## Tech Stack
- **Language:** Python 3.9+ (use `from __future__ import annotations` in all files)
- **API Framework:** FastAPI + Uvicorn
- **Database:** SQLite (dev) / PostgreSQL + PostGIS (prod)
- **ORM:** SQLAlchemy 2.0 (declarative models)
- **HTTP Client:** httpx (async)
- **Scheduling:** APScheduler (AsyncIOScheduler)
- **Data Processing:** pandas, geopandas

## Project Structure
```
weapons-tracker/
├── src/
│   ├── ingestion/          # Data source connectors
│   │   ├── sipri_transfers.py    # SIPRI Arms Transfers DB (BROKEN — see Known Issues)
│   │   ├── sipri_companies.py    # SIPRI Top 100 defense companies (Excel parser)
│   │   ├── worldbank.py          # World Bank arms trade indicators (REST API)
│   │   ├── gdelt_news.py         # GDELT arms trade news (REST API, 15-min updates)
│   │   ├── flight_tracker.py     # Military flight tracking via adsb.lol (live)
│   │   ├── maritime_tracker.py   # Maritime vessel tracking via aisstream.io (WebSocket)
│   │   └── scheduler.py          # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py             # SQLAlchemy models (7 tables)
│   │   ├── database.py           # DB connection + session management
│   │   └── persistence.py        # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   └── trends.py             # Historical trend analysis engine (14 query methods)
│   ├── api/
│   │   ├── routes.py             # Core API endpoints (transfers, indicators, news, flights)
│   │   └── trend_routes.py       # Trend analysis endpoints (/trends/*)
│   ├── alerts/                   # (placeholder — not yet implemented)
│   └── main.py                   # App entry point (starts API + scheduler)
├── scripts/
│   └── seed_database.py          # Initial full data load script
├── config/
│   └── .env.example              # API key template
├── tests/                        # (placeholder — no tests yet)
├── requirements.txt
└── README.md
```

## Database Models (src/storage/models.py)
- **Country** — name, ISO codes, region
- **WeaponSystem** — designation, description, category, producer country
- **ArmsTransfer** — seller, buyer, weapon, years, quantities, TIV values (core entity)
- **DefenseCompany** — name, country, rank, year, arms/total revenue
- **TradeIndicator** — country, year, imports TIV, exports TIV, military spending % GDP
- **ArmsTradeNews** — title, URL, source, tone, publish date
- **DeliveryTracking** — flight/vessel positions with confidence scoring

## API Endpoints
### Core (src/api/routes.py)
- `GET /transfers/exports/{country}` — SIPRI arms exports
- `GET /transfers/imports/{country}` — SIPRI arms imports
- `GET /transfers/bilateral/{seller}/{buyer}` — bilateral trade
- `GET /indicators/{country_iso3}` — World Bank indicators
- `GET /indicators/top/importers` and `/exporters`
- `GET /news/latest` and `/news/country/{country}` — GDELT news
- `GET /tracking/flights/military` and `/transports` — live flights

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

### CRITICAL: SIPRI Export URL Broken
- **Problem:** The old SIPRI export endpoint `https://armstrade.sipri.org/armstrade/html/export_trade_register.php` now returns a 301 redirect to an HTML page at `https://www.sipri.org/databases/armstransfers`
- **Impact:** `sipri_transfers.py` cannot fetch CSV data. The seed script skips all SIPRI data.
- **Fix needed:** Find the new SIPRI export URL or scrape their updated web interface. The new site is at `https://armstransfers.sipri.org/` — need to investigate its export mechanism.
- **Workaround:** World Bank mirrors aggregated SIPRI TIV data via indicators `MS.MIL.MPRT.KD` / `MS.MIL.XPRT.KD` (but this is country-level aggregates, not deal-level).

### NOT YET TESTED
- World Bank connector (`worldbank.py`) — likely works (standard REST API, no auth)
- GDELT connector (`gdelt_news.py`) — likely works (standard REST API, no auth)
- adsb.lol flight tracker (`flight_tracker.py`) — likely works (free, no auth)
- Maritime tracker (`maritime_tracker.py`) — requires `AISSTREAM_API_KEY` env var
- SIPRI Top 100 companies (`sipri_companies.py`) — needs valid Excel download URL

### NOT YET BUILT
- Alerting system (`src/alerts/`) — notifications for unusual patterns
- Dashboard/UI — map + charts visualization
- Tests — no test suite yet
- SIPRI Top 100 ingestion in scheduler (only transfers and World Bank are scheduled)
- Maritime ingestion in scheduler (WebSocket streaming not integrated yet)

## How to Run
```bash
cd /Users/billdennis/weapons-tracker
source venv/bin/activate          # venv already created with all deps installed

# Seed database (will skip SIPRI due to broken URL)
python -m scripts.seed_database

# Start API server (includes scheduler)
python -m src.main
# API at http://localhost:8000, docs at http://localhost:8000/docs
```

## Key Design Decisions
- SQLite for dev (zero config), PostgreSQL+PostGIS for prod
- All connectors are async (httpx + asyncio)
- Persistence layer handles deduplication via unique constraints
- Flight/vessel data stored as time-series snapshots (not deduplicated — intentional for trend analysis)
- `from __future__ import annotations` required in all files (Python 3.9 compat)

## Next Steps (Priority Order)
1. Fix SIPRI connector (find new export URL or build scraper)
2. Test remaining connectors (World Bank, GDELT, adsb.lol)
3. Build alerting system
4. Build dashboard/UI
5. Add test suite
