# Weapons Tracker

Geopolitical intelligence platform tracking global weapons sales and trade using open-source intelligence (OSINT). Features an interactive dashboard with real-time military flight tracking, trade flow visualization, and Canada-focused threat analysis.

## Mission

Answer the fundamental questions of the global arms trade:
- **Who is selling weapons to whom?** (SIPRI Arms Transfers Database)
- **How much money is changing hands?** (UN Comtrade real USD values)
- **What systems are being traded?** (deal-level weapon designation, quantity, value)
- **How much is each country spending?** (World Bank military expenditure data)
- **Are deliveries happening right now?** (military flight tracking)
- **What's breaking in the news?** (GDELT arms trade news monitoring)
- **How is the geopolitical landscape shifting?** (alliance analysis, threat watchlist)

## Dashboard

Interactive web dashboard at `http://localhost:8000` with 5 tabs:

| Tab | What It Shows |
|-----|--------------|
| **Overview** | Trade flow network graph, top exporters/importers, weapon type breakdown, trade volume timeline |
| **World Map** | Interactive map with trade arcs, country bubbles sized by volume, regional breakdown, real USD values from UN Comtrade |
| **Live Flights** | Real-time military aircraft positions on a map (auto-refreshes every 30s), transport aircraft detection, aircraft list with callsigns |
| **Deals** | Searchable/filterable table of all 3,786+ individual arms transfers with seller/buyer/weapon/TIV data |
| **Canada Intel** | Ally vs adversary arms flows, threat watchlist (Russia/China/Iran/Myanmar), Arctic monitor, supply chain analysis, shifting alliances detector |

## Data Sources

| Source | What It Tracks | Update Frequency | Cost | Status |
|--------|---------------|-----------------|------|--------|
| **SIPRI Arms Transfers** | Every major arms deal since 1950 (buyer, seller, weapon, quantity, TIV value) | Annual (March) | Free | Working |
| **UN Comtrade** | Real USD trade values for arms & ammunition (HS Chapter 93) | Annual | Free | Working |
| **World Bank** | Arms imports/exports TIV + military expenditure (% GDP) per country | Annual | Free | Working |
| **GDELT** | Global news articles about arms deals, deliveries, procurement | Every 15 min | Free | Working |
| **adsb.lol** | Live military transport aircraft positions (C-17, Il-76, An-124, etc.) | Seconds | Free | Working |
| **aisstream.io** | Live vessel positions at key chokepoints (Hormuz, Suez, etc.) | Real-time | Free | Not tested |

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

# Start the server (dashboard + API + scheduler)
python -m src.main
```

Open `http://localhost:8000` for the dashboard. API docs at `http://localhost:8000/docs`.

### Quick API Examples

```bash
# Canada's arms imports since 2015
curl "http://localhost:8000/transfers/imports/Canada?low_year=2015"

# US arms exports to Saudi Arabia
curl "http://localhost:8000/transfers/bilateral/United%20States/Saudi%20Arabia"

# Aggregated trade flows from the database
curl "http://localhost:8000/dashboard/flows?min_tiv=100"

# Real USD arms export values (UN Comtrade)
curl "http://localhost:8000/dashboard/comtrade/exports?years=2022,2023"

# Military transport aircraft currently in the air
curl "http://localhost:8000/tracking/flights/transports"

# Country profile with top trade partners
curl "http://localhost:8000/trends/country/Russia/profile"
```

## Architecture

```
              OSINT DATA SOURCES
 ┌─────────────────────────────────────────────┐
 │  SIPRI ─── World Bank ─── GDELT ─── adsb   │
 │  (deals)   (indicators)   (news)    (flights)│
 │  UN Comtrade ─── aisstream.io               │
 │  (USD values)    (vessels)                   │
 └────────────────────┬────────────────────────┘
                      │
                      ▼
 ┌─────────────────────────────────────────────┐
 │           WEAPONS TRACKER DB                 │
 │  Arms Transfers ── Weapon Systems            │
 │  Countries ── Trade Indicators               │
 │  Defense Companies ── Delivery Tracking      │
 │  Arms Trade News                             │
 └────────────────────┬────────────────────────┘
                      │
           ┌──────────┴──────────┐
           ▼                     ▼
 ┌───────────────────┐ ┌───────────────────────┐
 │    REST API        │ │    DASHBOARD UI        │
 │  27+ endpoints     │ │  5 tabs (HTML/JS)      │
 │  /transfers/*      │ │  Overview              │
 │  /trends/*         │ │  World Map             │
 │  /dashboard/*      │ │  Live Flights          │
 │  /tracking/*       │ │  Deals                 │
 │  /indicators/*     │ │  Canada Intel          │
 └───────────────────┘ └───────────────────────┘
```

## Project Structure

```
weapons-tracker/
├── src/
│   ├── ingestion/
│   │   ├── sipri_transfers.py   # SIPRI Arms Transfers (atbackend.sipri.org API)
│   │   ├── comtrade.py          # UN Comtrade (real USD values, HS 93)
│   │   ├── worldbank.py         # World Bank arms trade indicators
│   │   ├── gdelt_news.py        # GDELT arms trade news monitor
│   │   ├── flight_tracker.py    # Military flight tracking (adsb.lol)
│   │   ├── maritime_tracker.py  # Maritime vessel tracking (aisstream.io)
│   │   ├── sipri_companies.py   # SIPRI Top 100 defense companies
│   │   └── scheduler.py         # APScheduler ingestion pipeline
│   ├── storage/
│   │   ├── models.py            # SQLAlchemy models (7 tables)
│   │   ├── database.py          # Database connection management
│   │   └── persistence.py       # Upsert/dedup logic for all entity types
│   ├── analysis/
│   │   └── trends.py            # Historical trend analysis engine
│   ├── api/
│   │   ├── routes.py            # Core API endpoints (live external sources)
│   │   ├── trend_routes.py      # Trend analysis endpoints (DB-backed)
│   │   └── dashboard_routes.py  # Dashboard endpoints (DB-backed + cached Comtrade)
│   ├── static/
│   │   └── index.html           # Dashboard UI (Chart.js, D3.js, Leaflet.js)
│   └── main.py                  # App entry point (API + scheduler + dashboard)
├── scripts/
│   └── seed_database.py         # Initial full data load
├── config/
│   └── .env.example             # API key template
├── tests/
├── requirements.txt
├── CLAUDE.md                    # Dev context for AI-assisted development
└── README.md
```

## License

MIT
