# Weapons Tracker

Track global weapons sales and trade across countries using open-source intelligence (OSINT).

## Mission

Answer the fundamental questions of the global arms trade:
- **Who is selling weapons to whom?** (SIPRI Arms Transfers Database)
- **What systems are being traded?** (deal-level weapon designation, quantity, value)
- **Which companies are producing them?** (SIPRI Top 100 defense companies)
- **How much is each country spending?** (World Bank military expenditure data)
- **Are deliveries happening right now?** (military flight + maritime vessel tracking)
- **What's breaking in the news?** (GDELT arms trade news monitoring)

## How It Works

```
                    WEAPONS TRADE DATA PIPELINE

 ┌──────────────────────────────────────────────────────┐
 │                  DATA SOURCES                         │
 │                                                       │
 │  SIPRI Arms         World Bank         GDELT News     │
 │  Transfers DB  ───  Arms Trade    ───  Arms Deal      │
 │  (annual)           Indicators         Monitoring      │
 │                     (annual)           (15-min)        │
 │  SIPRI Top 100                                        │
 │  Companies     ───  adsb.lol      ───  aisstream.io   │
 │  (annual)           Military           Maritime        │
 │                     Flights (live)     Vessels (live)  │
 └──────────────┬──────────────────┬─────────────────────┘
                │                  │
                ▼                  ▼
 ┌──────────────────────────────────────────────────────┐
 │              WEAPONS TRACKER DATABASE                  │
 │                                                       │
 │  Arms Transfers ── Weapon Systems ── Countries        │
 │  Defense Companies ── Trade Indicators                │
 │  Delivery Tracking ── Arms Trade News                 │
 └──────────────────────────┬────────────────────────────┘
                            │
                            ▼
 ┌──────────────────────────────────────────────────────┐
 │                   REST API                            │
 │                                                       │
 │  GET /transfers/exports/{country}                     │
 │  GET /transfers/imports/{country}                     │
 │  GET /transfers/bilateral/{seller}/{buyer}            │
 │  GET /indicators/{country_iso3}                       │
 │  GET /indicators/top/importers                        │
 │  GET /indicators/top/exporters                        │
 │  GET /news/latest                                     │
 │  GET /news/country/{country}                          │
 │  GET /tracking/flights/military                       │
 │  GET /tracking/flights/transports                     │
 └──────────────────────────────────────────────────────┘
```

## Data Sources

| Source | What It Tracks | Update Frequency | Cost |
|--------|---------------|-----------------|------|
| **SIPRI Arms Transfers** | Every major arms deal since 1950 (buyer, seller, weapon, quantity, TIV value) | Annual (March) | Free |
| **SIPRI Top 100** | Largest defense companies by arms revenue | Annual | Free |
| **World Bank** | Arms imports/exports TIV + military expenditure (% GDP) per country | Annual | Free |
| **GDELT** | Global news articles about arms deals, deliveries, procurement | Every 15 min | Free |
| **adsb.lol** | Live military transport aircraft positions (C-17, Il-76, An-124, etc.) | Seconds | Free |
| **aisstream.io** | Live vessel positions at key chokepoints (Hormuz, Suez, etc.) | Real-time | Free |

## API Endpoints

### Arms Transfers (SIPRI)
- `GET /transfers/exports/{country}` — All arms exports from a country
- `GET /transfers/imports/{country}` — All arms imports to a country
- `GET /transfers/bilateral/{seller}/{buyer}` — Arms deals between two countries
- `GET /transfers/countries` — List available countries

### Trade Indicators (World Bank)
- `GET /indicators/{country_iso3}` — Arms trade + military spending for a country
- `GET /indicators/top/importers` — Top arms importing countries
- `GET /indicators/top/exporters` — Top arms exporting countries

### Arms Trade News (GDELT)
- `GET /news/latest` — Latest arms trade news globally
- `GET /news/country/{country}` — Arms news for a specific country

### Live Delivery Tracking
- `GET /tracking/flights/military` — All military aircraft currently in the air
- `GET /tracking/flights/transports` — Military transport aircraft (likely carrying weapons/equipment)

### Historical Trends (persisted data)
- `GET /trends/summary` — Database stats
- `GET /trends/global/volume` — Global arms trade TIV by year
- `GET /trends/global/categories` — Trade by weapon type
- `GET /trends/global/top-pairs` — Highest-volume seller→buyer pairs
- `GET /trends/country/{name}/profile` — Full trade profile (partners, categories, totals)
- `GET /trends/country/{name}/exports` — Export volume by year
- `GET /trends/country/{name}/imports` — Import volume by year
- `GET /trends/changes/imports` — Biggest year-over-year import changes
- `GET /trends/companies/{name}` — Defense company revenue trend
- `GET /trends/companies/top/{year}` — Top companies ranked for a year
- `GET /trends/activity/flights` — Military flight detections per day
- `GET /trends/activity/news` — Arms trade news volume + sentiment per day

## Project Structure

```
weapons-tracker/
├── src/
│   ├── ingestion/
│   │   ├── sipri_transfers.py   # SIPRI Arms Transfers Database connector
│   │   ├── sipri_companies.py   # SIPRI Top 100 defense companies connector
│   │   ├── worldbank.py         # World Bank arms trade indicators
│   │   ├── gdelt_news.py        # GDELT arms trade news monitor
│   │   ├── flight_tracker.py    # Military transport flight tracking (adsb.lol)
│   │   ├── maritime_tracker.py  # Maritime vessel tracking (aisstream.io)
│   │   └── scheduler.py         # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py            # SQLAlchemy models (7 tables)
│   │   ├── database.py          # Database connection management
│   │   └── persistence.py       # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   └── trends.py            # Historical trend analysis engine
│   ├── api/
│   │   ├── routes.py            # Core API endpoints
│   │   └── trend_routes.py      # Trend analysis endpoints
│   └── main.py                  # App entry point (API + scheduler)
├── scripts/
│   └── seed_database.py         # Initial full data load
├── config/
│   └── .env.example             # API key template
├── tests/
├── requirements.txt
├── CLAUDE.md                    # Dev context for AI-assisted development
└── README.md
```

## Current Status

**Working:**
- Database models and persistence layer (SQLite)
- World Bank, GDELT, adsb.lol, aisstream.io connectors
- Scheduled ingestion pipeline (APScheduler)
- Historical trend analysis engine (14 query methods)
- Full REST API (27 endpoints)

**Needs Fix:**
- SIPRI Arms Transfers connector — export URL changed, returns 301 redirect to HTML
- SIPRI Top 100 companies — Excel download URL needs verification

**Not Yet Built:**
- Alerting system (unusual pattern notifications)
- Dashboard/UI (map + charts)
- Test suite

## Getting Started

```bash
git clone https://github.com/QDThead/weapons-tracker.git
cd weapons-tracker

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Optional: configure API keys for premium sources
cp config/.env.example config/.env

# Seed the database (one-time full load)
python -m scripts.seed_database

# Start the API server (includes auto-scheduler)
python -m src.main
```

The API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Quick Examples

```bash
# Canada's arms imports since 2015
curl "http://localhost:8000/transfers/imports/Canada?low_year=2015"

# US arms exports to Saudi Arabia
curl "http://localhost:8000/transfers/bilateral/United%20States/Saudi%20Arabia"

# Top arms importers in 2024
curl "http://localhost:8000/indicators/top/importers?year=2024"

# Latest arms trade news
curl "http://localhost:8000/news/latest?hours=48"

# Military transport aircraft currently in the air
curl "http://localhost:8000/tracking/flights/transports"
```

## License

MIT
