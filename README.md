# Weapons Tracker — Defence Supply Chain Intelligence Platform

Geopolitical intelligence platform tracking global weapons sales, military spending, and force deployments using open-source intelligence (OSINT). Built for the Canadian Department of National Defence (DND/CAF) to answer: who is arming whom, where are the threats, and how vulnerable is Canada's defence supply chain.

**95.3% compliant** with the DND DMPP 11 Defence Supply Chain Control Tower RFI (22 questions, 137 sub-requirements).

## What It Does

- **57 active OSINT data feeds** — live flights to annual SIPRI transfers, across 24 connector files
- **10-tab interactive dashboard** with maps, charts, 3D globe (CesiumJS), and intelligence briefings
- **Arctic security assessment** with 25 mapped military bases and 3 shipping routes
- **Russia/China tracking** via buyer-side import mirrors, flight pattern analysis, and sanctions overlay
- **Supply chain knowledge graph** — 90 nodes, 96 edges, BOM explosion from raw materials to weapon platforms
- **30 critical minerals** tracked with USGS production data and concentration indices
- **DND Annex B risk taxonomy** — all 13 categories, 121 sub-categories scored with confidence levels
- **191-entry COA playbook** — auto-generated courses of action with Action Centre status tracking
- **10 Canadian defence suppliers** with 6-dimension risk scoring (Irving Shipbuilding, GD Land Systems, CAE, etc.)
- **Cyber threat intelligence** — APT groups, Tor exit nodes, CISA KEV, NVD CVEs, breach registry
- **PDF intelligence briefing** — one-click 7-page export for decision-makers
- **150+ API endpoints** with CSV/Excel/JSON export, OpenAPI docs
- **EN/FR bilingual interface** with language toggle
- **RBAC security** — 3 roles (viewer, analyst, admin), CORS, TLS, audit logging
- **9,311 arms transfers** across 26 seller countries and 186 buyers

## Dashboard

Open `http://localhost:8000` after starting the server:

| Tab | What Analysts See |
|-----|------------------|
| **Insights** | Intelligence briefing: 13-category risk taxonomy, 6 threat indicators, live news, DSCA sales, adversary flows, Canada's NATO position, shifting alliances |
| **Overview** | Trade flow network (D3.js), top exporters/importers, weapon types, volume timeline |
| **World Map** | Leaflet map with trade arcs, country bubbles, real USD values from UN Comtrade |
| **Arctic** | Force balance map with 25 bases (8 Russian, 15 NATO, 2 Chinese), 3 shipping routes, weapon timeline, live airspace |
| **Live Flights** | Real-time military aircraft positions worldwide (auto-refreshes 30s) with context banner |
| **Deals** | Searchable table of 9,311 individual arms transfers (2000-2025) |
| **Canada Intel** | Supplier risk ranking, ally vs adversary flows, threat watchlist, Arctic monitor, Action Centre |
| **Supply Chain** | 12 sub-tabs: Overview, 3D Supply Map, Knowledge Graph, Risk Matrix, Scenarios, Risk Taxonomy, **Forecasting** (live FRED data), **BOM Explorer**, **Supplier Dossier**, **Alerts**, **Risk Register**, **Analyst Feedback** — all Cobalt-focused |
| **Data Feeds** | 57 active feeds with health indicators, freshness, and sample data |
| **Compliance** | DMPP 11 compliance matrix — 22 RFI questions, 137 requirements with traceability |

## Data Sources (57 active + 2 inactive)

| Category | Sources | Update Frequency |
|----------|---------|-----------------|
| **Live** | Military flights (ADS-B), Defense RSS (4 feeds), GDELT news, Tor exit nodes | Seconds to 15 min |
| **Near-Real-Time** | DSCA arms sales, GDACS disasters, USGS earthquakes, NOAA weather, NASA EONET, space launches, NIST CVEs | Hours to days |
| **Monthly Trade** | US Census, UK HMRC, Eurostat, StatCan, FRED commodities, exchange rates | Monthly |
| **Annual** | SIPRI transfers, SIPRI MILEX, NATO spending, World Bank, Comtrade, CIA Factbook, UNROCA, nuclear arsenals, armed forces, IMF outlook | Annual |
| **Enrichment** | WGI governance, economic indicators, US fiscal, conflict deaths, UNHCR, USASpending, DND procurement, defence research | Various |
| **Supply Chain** | USGS mineral deposits, critical minerals, Wikidata corporate graph, IMF PortWatch chokepoints | Various |
| **Cyber** | APT registry, MITRE ATT&CK, CISA KEV, breach registry, supplier cyber risk, IOC summary | Live to static |
| **Infrastructure** | Celestrak satellites, submarine cables, RIPE internet infra, connectivity probes, OpenSky Arctic | Daily to real-time |
| **Analysis** | Sanctions (OFAC/EU/UN), buyer-side mirror, flight patterns | On-demand |

## Intelligence Features

| Feature | Why Canada Cares |
|---------|-----------------|
| **Situation Report** | 6 red/yellow/green threat indicators — instant assessment |
| **Arctic Base Registry** | Russia's 8 expanding bases surrounding Canada's north |
| **Buyer-side Mirror** | Reveals Russia/China arms deliveries by querying buyer-reported imports |
| **Supplier Shift Detection** | Poland switched US→South Korea; Egypt switched Russia→Italy |
| **Supply Chain BOM Explosion** | Trace F-35 → engine → turbine blades → titanium → China/Russia |
| **3D Supply Chain Globe** | CesiumJS globe: 30 minerals, mine-level markers, refinery markers, risk-colored shipping routes to Canadian ports, per-entity 13-category DND risk taxonomy scorecards |
| **Cobalt Deep Intelligence** | 9 named mines with ownership risk, 9 refineries, 8 defence alloys (Waspaloy, CMSX-4, Stellite), 6 shipping corridors, 13-category taxonomy + KPIs per entity |
| **191 Courses of Action** | Auto-generated mitigation playbook across all 13 DND risk categories |
| **Confidence Scoring** | Glass Box source triangulation — shows how many independent sources agree |
| **Disinformation Detection** | Flags articles from known state-media, extreme tone, sensationalist patterns |
| **Anomaly Detection + RLHF** | Adaptive thresholds trained by analyst feedback |
| **Canadian Supplier Exposure** | 6-dimension risk scoring: is Irving Shipbuilding a single point of failure? |
| **Nuclear Arsenal Tracking** | 9 nuclear states, 12,121 warheads with deployed/reserve breakdown |

## Getting Started

```bash
git clone https://github.com/QDThead/weapons-tracker.git
cd weapons-tracker

python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # macOS/Linux

pip install -r requirements.txt

# Seed the database (one-time, ~5 min)
python -m scripts.seed_database

# Start the server
python -m src.main
```

Open `http://localhost:8000` for the dashboard. API docs at `http://localhost:8000/docs`.

### Quick API Examples

```bash
# Intelligence briefing
curl http://localhost:8000/insights/all

# Arctic security assessment
curl http://localhost:8000/arctic/assessment
curl http://localhost:8000/arctic/bases

# Canadian defence suppliers
curl http://localhost:8000/dashboard/suppliers

# DND risk taxonomy (13 categories, 121 sub-categories)
curl http://localhost:8000/psi/taxonomy

# Supply chain scenario modeling
curl -X POST http://localhost:8000/psi/scenario \
  -H "Content-Type: application/json" \
  -d '{"type":"sanctions_expansion","parameters":{"country":"Russia"}}'

# COA playbook (191 entries)
curl http://localhost:8000/mitigation/playbook

# Export transfers as CSV
curl http://localhost:8000/export/transfers/csv -o transfers.csv

# PDF intelligence briefing
curl http://localhost:8000/briefing/pdf -o briefing.pdf

# ML anomaly detection with adaptive thresholds
curl http://localhost:8000/ml/thresholds

# Compliance matrix data
curl http://localhost:8000/psi/taxonomy/summary

# 3D Globe mineral supply chains
curl http://localhost:8000/globe/minerals
curl http://localhost:8000/globe/minerals/Cobalt
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///weapons_tracker.db` | Database connection string |
| `ENVIRONMENT` | `development` | Set to `production` for HTTPS redirect |
| `AUTH_ENABLED` | `false` | Enable API key authentication |
| `API_KEYS_JSON` | (dev defaults) | JSON dict of API keys → roles |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ALLOWED_HOSTS` | `*` | Comma-separated trusted hostnames |

## Project Stats

- **60+ Python files**, ~24,000 lines
- **1 HTML dashboard**, ~6,500 lines
- **118+ API endpoints** (REST, CSV, Excel, PDF)
- **57 active data sources** spanning live to annual
- **10 dashboard tabs** + EN/FR bilingual
- **18 database tables**
- **50 automated tests**
- **13 risk categories**, 121 sub-categories (DND Annex B)
- **191 COA playbook entries** across all risk categories
- **30 critical minerals** tracked
- **90 supply chain nodes**, 96 edges
- **25 Arctic bases** mapped
- **10 Canadian defence suppliers** scored
- **9,311 arms transfers** in database
- **95.3% RFI compliance** (137 requirements)

## Deployment

```bash
# Docker
docker-compose up --build

# Azure Container Apps (Canada Central)
cd deploy/azure && bash deploy.sh
```

## License

MIT
