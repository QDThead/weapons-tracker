# Weapons Tracker

Geopolitical intelligence platform tracking global weapons sales, military spending, and force deployments using open-source intelligence (OSINT). Built for government analysts to understand who is arming whom, where the threats are, and how alliances are shifting — with a focus on Canadian Arctic security.

## What It Does

- **12 live data sources** from hours-old defense news to annual SIPRI transfers
- **8-tab interactive dashboard** with maps, charts, and intelligence briefings
- **Arctic security assessment** with 25 mapped military bases and 3 shipping routes
- **Russia/China tracking** via buyer-side import mirrors, flight pattern analysis, and sanctions overlay
- **52 API endpoints** serving pre-computed intelligence and live data
- **4,623 arms transfers** across 26 seller countries and 174 buyers

## Dashboard

Open `http://localhost:8000` after starting the server:

| Tab | What Analysts See |
|-----|------------------|
| **Insights** | Intelligence briefing: 6 threat indicators, live defense news, DSCA arms sales, adversary flows, Canada's NATO position, shifting alliances |
| **Overview** | Interactive trade flow network, top exporters/importers, weapon types, volume timeline |
| **World Map** | Global map with trade arcs, country bubbles, real USD values from UN Comtrade |
| **Arctic** | Force balance map with 25 bases (8 Russian, 15 NATO, 2 Chinese), 3 shipping routes with ownership, weapon accumulation timeline, live airspace monitoring |
| **Live Flights** | Real-time military aircraft positions worldwide (auto-refreshes every 30s) |
| **Deals** | Searchable table of all 4,623 individual arms transfers |
| **Canada Intel** | Ally vs adversary arms flows, threat watchlist, Arctic monitor, supply chain risk, shifting alliances |
| **Data Feeds** | Operations view showing health/freshness of all 16 data sources |

## Data Sources

| # | Source | Latest Data | Update Frequency | Coverage |
|---|--------|------------|-----------------|----------|
| 1 | **Defense News RSS** | Today | 4 feeds, 15min cache | Global defense news (50+ articles) |
| 2 | **Military Flights** | Now | Live, every 5 min | Global military aircraft positions |
| 3 | **GDELT News** | Today | Every 15 min | Arms trade news articles |
| 4 | **DSCA Arms Sales** | Days ago | Federal Register API | US Congressional arms sale notifications |
| 5 | **Statistics Canada** | Jan 2026 | Monthly (~6 week lag) | Canadian arms imports/exports (CAD) |
| 6 | **US Census Trade** | Jan 2026 | Monthly (~2 month lag) | US arms imports/exports (USD) |
| 7 | **UK HMRC Trade** | Jan 2026 | Monthly (~2 month lag) | UK arms imports/exports (GBP) |
| 8 | **Eurostat Comext** | Jan 2026 | Monthly (~2 month lag) | EU 27 arms trade (EUR) |
| 9 | **NATO Spending** | 2025 estimates | Annual (Excel download) | 32 NATO members, spending + % GDP |
| 10 | **SIPRI Transfers** | 2025 deals | Annual (March) | Global deal-level arms transfers (TIV) |
| 11 | **World Bank** | 2024 | Annual | Aggregate TIV + military spending % GDP |
| 12 | **UN Comtrade** | 2023 | Annual (~6mo lag) | Detailed USD values by HS subcode |

Plus: **Sanctions/embargo overlay** (17 countries, OFAC SDN, EU sanctions), **buyer-side Comtrade mirror** (tracks Russia/China via their buyers' import data), **flight pattern analyzer** (identifies adversary aircraft).

## Intelligence Features

| Feature | What It Does | Why Canada Cares |
|---------|-------------|-----------------|
| **Situation Report** | 6 red/yellow/green threat indicators updated on every page load | Instant threat assessment at a glance |
| **Arctic Base Registry** | 25 bases mapped with threat levels and distance to Canada | Shows Russia's 8 expanding bases surrounding Canada's north |
| **Northern Sea Route Analysis** | 3 Arctic shipping routes with ownership and status | Russia controls the NSR; Canada's Northwest Passage sovereignty is contested |
| **Buyer-side Mirror** | Queries buyer countries to reveal Russia/China arms deliveries | Circumvents adversary data opacity |
| **Sanctions Compliance** | Cross-references Canada's trade partners against embargo lists | Flags that Canada trades with 2 embargoed countries (Lebanon, Mali) |
| **NATO Spending Comparison** | Canada's defense spending ranked against 32 NATO allies | Shows Canada at 2.01% GDP — barely meeting the 2% target |
| **Supplier Shift Detection** | Identifies countries changing primary arms supplier | Poland switched US→South Korea; Egypt switched Russia→Italy |
| **Russia Weakness Signals** | Tracks what Russia imports (Iranian drones, Chinese engines) | Indicates Russian domestic production collapse |

## Architecture

```
                OSINT DATA SOURCES (12 active)
 ┌─────────────────────────────────────────────────────┐
 │  SIPRI ── Comtrade ── Census ── HMRC ── Eurostat    │
 │  StatCan ── NATO ── World Bank ── DSCA ── GDELT     │
 │  adsb.lol (flights) ── Defense News RSS             │
 │  + Sanctions (OFAC/EU) ── Flight Pattern Analyzer   │
 └──────────────────────┬──────────────────────────────┘
                        │
                        ▼
 ┌─────────────────────────────────────────────────────┐
 │              WEAPONS TRACKER DB                      │
 │  4,623 transfers ── 5,110 indicators                │
 │  2,217 flight positions ── 157 news articles        │
 │  1,329 weapon systems ── 256 countries              │
 └──────────────────────┬──────────────────────────────┘
                        │
            ┌───────────┴───────────┐
            ▼                       ▼
 ┌────────────────────┐  ┌─────────────────────────────┐
 │    REST API (52)    │  │      DASHBOARD (8 tabs)      │
 │  /insights/*        │  │  Insights ── Overview         │
 │  /arctic/*          │  │  World Map ── Arctic          │
 │  /dashboard/*       │  │  Live Flights ── Deals        │
 │  /trends/*          │  │  Canada Intel ── Data Feeds   │
 │  /transfers/*       │  │                               │
 │  /tracking/*        │  │  Chart.js + D3.js + Leaflet   │
 └────────────────────┘  └─────────────────────────────┘
```

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
# Arctic security assessment (force balance, base registry, threats)
curl http://localhost:8000/arctic/assessment
curl http://localhost:8000/arctic/bases

# Intelligence briefing (situation report + 7 insight categories)
curl http://localhost:8000/insights/all

# Canada's monthly arms trade (Statistics Canada)
curl http://localhost:8000/dashboard/canada-trade/monthly

# What buyers report importing from Russia (buyer-side mirror)
curl "http://localhost:8000/dashboard/adversary-trade/buyer-mirror?seller=Russia&years=2022,2023"

# NATO defense spending (2025 estimates for 32 members)
curl "http://localhost:8000/dashboard/nato/spending?year=2025"

# Sanctions check
curl http://localhost:8000/dashboard/sanctions/check/Russia

# Live military flights in the Arctic
curl http://localhost:8000/arctic/flights

# Recent US arms sale notifications (DSCA)
curl "http://localhost:8000/dashboard/dsca/recent?count=10"
```

## Project Stats

- **33 Python files**, ~8,800 lines
- **1 HTML dashboard**, ~4,000 lines
- **52 API endpoints**
- **15 data connectors** (12 active, 2 inactive, 1 scheduler)
- **12 data sources** spanning live to annual
- **8 dashboard tabs**
- **25 Arctic bases** mapped with threat assessments
- **17 embargoed countries** tracked
- **4,623 arms transfers** in database

## License

MIT
