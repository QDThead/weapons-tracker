# Weapons Tracker

Global weapons systems tracking and risk monitoring platform using open-source intelligence (OSINT) data sources.

## Overview

A multi-layered intelligence platform that monitors global arms transfers, military logistics, and conflict risk by fusing structured databases, real-time physical tracking, satellite imagery, and social media signals.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              INGESTION LAYER                     │
├──────────┬──────────┬──────────┬────────────────┤
│ Streaming│ Polling  │ Scheduled│ Manual/Scraped │
│ aisstream│ adsb.lol │ ACLED    │ SIPRI (annual) │
│ Telegram │ GDELT    │ UCDP     │ UNROCA         │
│          │ OpenSky  │ WGI      │ ODIN/WEG       │
│          │ X API    │ INFORM   │ FSI            │
│          │          │ GPR      │                │
└─────┬────┴─────┬────┴─────┬────┴───────┬────────┘
      │          │          │            │
      ▼          ▼          ▼            ▼
┌─────────────────────────────────────────────────┐
│         STORAGE (PostGIS + TimescaleDB)         │
│  - Geospatial indexing for all location data    │
│  - Time-series for flight/vessel tracks         │
│  - Event store for conflicts/news               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│              ANALYSIS ENGINE                     │
│  - Correlation: flight anomaly + conflict event │
│  - Trend detection: arms buildup patterns       │
│  - Geofencing: alerts for activity in AOIs      │
│  - NLP: GDELT/social media sentiment scoring    │
│  - Satellite change detection pipeline          │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│           PRESENTATION & ALERTING               │
│  - Real-time map (Mapbox/Deck.gl)               │
│  - Dashboard (Grafana or custom)                │
│  - Alert rules → Slack/Email/SMS                │
│  - Weekly/monthly risk digests                  │
│  - Country risk scorecards                      │
└─────────────────────────────────────────────────┘
```

## Data Sources

### Tier 1: Structured Arms & Conflict Databases
| Source | Update Frequency | API | Cost |
|--------|-----------------|-----|------|
| SIPRI Arms Transfers | Annual | Unofficial (CSV/JSON) | Free (non-commercial) |
| SIPRI Top 100 Companies | Annual | Excel download | Free (non-commercial) |
| ACLED | Weekly | REST + Python lib | Free (research) |
| GDELT | Every 15 min | REST + BigQuery | Free |
| UCDP | Annual + monthly | REST (token) | Free |
| World Bank WGI | Annual | REST (open) | Free |
| INFORM Risk Index | Twice yearly | JSON | Free |
| Fragile States Index | Annual | Excel download | Free |
| GPR Index | Monthly | File download | Free |

### Tier 2: Real-Time Physical Tracking
| Source | Update Frequency | API | Cost |
|--------|-----------------|-----|------|
| ADS-B Exchange | 1-20 sec | REST | $10/mo+ |
| adsb.lol | Seconds | REST (no auth) | Free |
| OpenSky Network | 5-10 sec | REST | Free |
| aisstream.io | Real-time | WebSocket | Free |
| VesselFinder | Real-time | REST | EUR 330/10K credits |
| Sentinel Hub | 5-12 day revisit | OGC + REST | EUR 30-1000/mo |
| Planet Labs | Daily | REST | ~$4K+/mo |

### Tier 3: Social Media & OSINT
| Source | Update Frequency | API | Cost |
|--------|-----------------|-----|------|
| X (Twitter) API | Real-time | REST | $200/mo+ |
| Telegram Bot API | Real-time | Bot API | Free |
| ODIN/WEG | Periodic | Web/Excel | Free |

## Project Structure

```
weapons-tracker/
├── src/
│   ├── ingestion/        # Data source connectors
│   ├── storage/           # Database models and migrations
│   ├── analysis/          # Correlation and detection engines
│   ├── api/               # REST API for the platform
│   └── alerts/            # Alerting and notification system
├── config/                # Configuration files
├── tests/                 # Test suite
├── docs/                  # Documentation
└── scripts/               # Utility scripts
```

## Getting Started

```bash
# Clone the repository
git clone https://github.com/QDThead/weapons-tracker.git
cd weapons-tracker

# Set up Python environment
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Copy environment config
cp config/.env.example config/.env
# Edit config/.env with your API keys

# Run the platform
python -m src.main
```

## License

MIT
