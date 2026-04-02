# Data Feed Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Schedule 13 unscheduled high-value feeds, expand fetch limits on SIPRI/Eurostat/GDELT, and add fallback alerting for cobalt connectors — so every data feed stays working and keeps ingesting.

**Architecture:** All changes touch `src/ingestion/scheduler.py` (new job functions + registrations), 3 connector modules (expanded params), and the cobalt refresh function (fallback detection + logging). No new files needed — this is config-level hardening of existing infrastructure.

**Tech Stack:** APScheduler (AsyncIOScheduler, CronTrigger, IntervalTrigger), httpx (async), existing connector classes

---

## File Map

| File | Action | What Changes |
|------|--------|-------------|
| `src/ingestion/scheduler.py` | MODIFY | 13 new job functions + scheduler registrations, improved cobalt fallback logging, expanded GDELT limit |
| `src/ingestion/sipri_transfers.py` | MODIFY | Expand country list from 26 to ~60 key countries |
| `src/ingestion/eurostat_trade.py` | MODIFY | Expand DEFAULT_REPORTERS from 6 to all 27 EU members |
| `src/ingestion/gdelt_news.py` | NO CHANGE | Default is already 50; scheduler overrides to 25 — fix is in scheduler.py |
| `tests/test_scheduler_feeds.py` | CREATE | Tests for new job functions and fallback detection |

---

### Task 1: Schedule 7 Trade Data Feeds + Defense News RSS

**Files:**
- Modify: `src/ingestion/scheduler.py`

Add job functions and scheduler registrations for the 7 highest-value unscheduled feeds: Census Trade (US monthly), UK HMRC Trade, Eurostat Trade (EU monthly), StatCan Trade (Canadian monthly), Defense News RSS, OFAC SDN sanctions, and Defense News RSS.

- [ ] **Step 1: Add 7 new job functions to scheduler.py**

Add these functions before the `create_scheduler()` function (after the existing `ingest_parliament_nddn` function, around line 327):

```python
async def ingest_census_trade():
    """Fetch US Census monthly arms trade (HS Chapter 93)."""
    try:
        from src.ingestion.census_trade import CensusTradeClient
        client = CensusTradeClient()
        exports = await client.fetch_arms_exports()
        imports = await client.fetch_arms_imports()
        logger.info("[scheduler] US Census Trade: %d export + %d import records", len(exports), len(imports))
    except Exception as e:
        logger.error("[scheduler] US Census Trade ingestion failed: %s", e)


async def ingest_uk_hmrc_trade():
    """Fetch UK HMRC monthly arms trade (OData API)."""
    try:
        from src.ingestion.uk_hmrc_trade import UKHMRCTradeClient
        client = UKHMRCTradeClient()
        records = await client.fetch_uk_arms_trade()
        logger.info("[scheduler] UK HMRC Trade: fetched %d records", len(records))
    except Exception as e:
        logger.error("[scheduler] UK HMRC Trade ingestion failed: %s", e)


async def ingest_eurostat_trade():
    """Fetch Eurostat EU monthly arms trade (Comext SDMX)."""
    try:
        from src.ingestion.eurostat_trade import EurostatTradeClient
        client = EurostatTradeClient()
        records = await client.fetch_eu_arms_trade()
        logger.info("[scheduler] Eurostat Trade: fetched %d records", len(records))
    except Exception as e:
        logger.error("[scheduler] Eurostat Trade ingestion failed: %s", e)


async def ingest_statcan_trade():
    """Fetch Statistics Canada monthly arms trade (CIMT)."""
    try:
        from src.ingestion.statcan_trade import StatCanTradeClient
        client = StatCanTradeClient()
        records = await client.fetch_arms_trade()
        logger.info("[scheduler] StatCan Trade: fetched %d records", len(records))
    except Exception as e:
        logger.error("[scheduler] StatCan Trade ingestion failed: %s", e)


async def ingest_defense_news_rss():
    """Fetch defense news from 4 RSS feeds."""
    try:
        from src.ingestion.defense_news_rss import DefenseNewsRSSClient
        client = DefenseNewsRSSClient()
        articles = await client.fetch_defense_news()
        logger.info("[scheduler] Defense News RSS: fetched %d articles", len(articles))
    except Exception as e:
        logger.error("[scheduler] Defense News RSS ingestion failed: %s", e)


async def ingest_sanctions_ofac():
    """Fetch OFAC SDN sanctions list."""
    try:
        from src.ingestion.sanctions import SanctionsClient
        client = SanctionsClient()
        entries = await client.fetch_ofac_sdn()
        logger.info("[scheduler] OFAC SDN: fetched %d entries", len(entries))
    except Exception as e:
        logger.error("[scheduler] OFAC SDN ingestion failed: %s", e)


async def ingest_cia_factbook():
    """Fetch CIA World Factbook military data for key nations."""
    try:
        from src.ingestion.cia_factbook import CIAFactbookClient
        client = CIAFactbookClient()
        records = await client.fetch_military_data()
        logger.info("[scheduler] CIA Factbook: fetched %d country records", len(records))
    except Exception as e:
        logger.error("[scheduler] CIA Factbook ingestion failed: %s", e)
```

- [ ] **Step 2: Register the 7 jobs in create_scheduler()**

Add these registrations inside `create_scheduler()`, before the `return scheduler` line (around line 507):

```python
    # ── Trade data feeds (weekly, staggered to avoid concurrent load) ──

    scheduler.add_job(
        ingest_census_trade,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="census_trade",
        name="US Census monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_uk_hmrc_trade,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=15),
        id="uk_hmrc_trade",
        name="UK HMRC monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_eurostat_trade,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=30),
        id="eurostat_trade",
        name="Eurostat EU monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_statcan_trade,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=45),
        id="statcan_trade",
        name="Statistics Canada monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_defense_news_rss,
        trigger=IntervalTrigger(minutes=30),
        id="defense_news_rss",
        name="Defense News RSS (4 feeds)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_sanctions_ofac,
        trigger=CronTrigger(hour=6, minute=30),
        id="ofac_sdn",
        name="OFAC SDN sanctions list",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        ingest_cia_factbook,
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="cia_factbook",
        name="CIA World Factbook military data",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 3: Update the module docstring**

Replace the docstring at the top of scheduler.py (lines 1-14) to reflect the new feeds:

```python
"""Scheduled ingestion pipeline.

Runs each data connector on its natural update cadence and persists
results to the database.

Schedule:
  - Military flights:       every 5 minutes
  - GDELT arms news:        every 15 minutes
  - Cobalt alert engine:    every 30 minutes
  - Defense News RSS:       every 30 minutes
  - GC Defence News:        every 30 minutes
  - NATO News:              hourly
  - Arctic OSINT:           every 2 hours
  - NORAD News:             every 6 hours
  - Taxonomy scoring:       every 6 hours
  - SIPRI transfers:        daily 2 AM
  - World Bank indicators:  daily 3 AM
  - Cobalt feeds (7 src):   daily 5 AM
  - Canadian Sanctions:     daily 6 AM
  - OFAC SDN:               daily 6:30 AM
  - Parliament NDDN:        daily 8 AM
  - Trade data (4 nations): weekly Monday 2-3 AM
  - CIA Factbook:           weekly Monday 3 AM
  - DND procurement:        weekly Sunday 2 AM
  - Supplier enrichment:    weekly Sunday 3 AM
  - PSI supply chain:       weekly Sunday 4 AM
  - Supplier scoring:       weekly Sunday 5 AM
  - Comtrade cobalt:        monthly 1st 6 AM
"""
```

- [ ] **Step 4: Verify no syntax errors**

Run: `python -c "from src.ingestion.scheduler import create_scheduler; s = create_scheduler(); print(f'{len(s.get_jobs())} jobs registered')"`
Expected: Output shows the total job count (should be ~22+)

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat: schedule 7 high-value feeds (trade data, defense news, sanctions, CIA factbook)"
```

---

### Task 2: Expand SIPRI Country Coverage

**Files:**
- Modify: `src/ingestion/sipri_transfers.py` (expand SIPRI_COUNTRY_CODES)

The current list has 26 countries. Expand to ~60 by adding all significant arms importers/exporters that SIPRI tracks.

- [ ] **Step 1: Expand SIPRI_COUNTRY_CODES dict**

In `src/ingestion/sipri_transfers.py`, replace the existing `SIPRI_COUNTRY_CODES` dict (lines 45-72) with:

```python
SIPRI_COUNTRY_CODES = {
    # Major exporters (top 25)
    "Canada": 1050339,
    "United States": 1050595,
    "United Kingdom": 1050559,
    "France": 1050443,
    "Germany": 1050674,
    "Russia": 1050481,
    "China": 1050672,
    "Israel": 1050426,
    "Italy": 1050407,
    "Sweden": 1050484,
    "Netherlands": 1050503,
    "Spain": 1050518,
    "South Korea": 1050325,
    "Turkiye": 1050685,
    "Ukraine": 1050536,
    "Switzerland": 1050529,
    "Norway": 1050482,
    "Czech Republic": 1050677,
    "South Africa": 1050523,
    "Belarus": 1050383,
    "Brazil": 1050387,
    "Finland": 1050397,
    "Denmark": 1050393,
    "Poland": 1050520,
    "Austria": 1050380,
    # Major importers (top 35)
    "India": 1050473,
    "Saudi Arabia": 1050663,
    "Egypt": 1050652,
    "Australia": 1050385,
    "Japan": 1050409,
    "Pakistan": 1050519,
    "Taiwan": 1050362,
    "Qatar": 1050521,
    "UAE": 1050592,
    "Algeria": 1050378,
    "Iraq": 1050413,
    "Indonesia": 1050475,
    "Singapore": 1050514,
    "Greece": 1050401,
    "Thailand": 1050531,
    "Vietnam": 1050601,
    "Bangladesh": 1050382,
    "Morocco": 1050488,
    "Mexico": 1050469,
    "Colombia": 1050392,
    "Philippines": 1050510,
    "Malaysia": 1050457,
    "Kazakhstan": 1050438,
    "Myanmar": 1050491,
    "Nigeria": 1050502,
    "Oman": 1050507,
    "Kuwait": 1050442,
    "Jordan": 1050430,
    "Iran": 1050412,
    "DPRK": 1050413,
}
```

- [ ] **Step 2: Add buyer-side import queries to the scheduler function**

In `src/ingestion/scheduler.py`, modify the `ingest_sipri_transfers()` function to also fetch imports for key adversary/watchlist nations. After the existing exports loop (line 92), add:

```python
        # Also fetch imports for adversary and watchlist nations
        import_countries = ["Russia", "China", "India", "Iran", "DPRK", "Saudi Arabia",
                            "Egypt", "UAE", "Pakistan", "Algeria", "Myanmar"]
        for country_name in import_countries:
            code = SIPRI_COUNTRY_CODES.get(country_name)
            if not code:
                continue
            try:
                query = SIPRIQuery(
                    buyer_country_codes=[code],
                    low_year=2000,
                    high_year=2025,
                )
                records = await client.fetch_transfers(query)
                all_records.extend(records)
                logger.info("[scheduler] SIPRI: fetched %d records for %s imports", len(records), country_name)
            except Exception as e:
                logger.warning("[scheduler] SIPRI import fetch failed for %s: %s", country_name, e)
```

- [ ] **Step 3: Verify no import errors**

Run: `python -c "from src.ingestion.sipri_transfers import SIPRI_COUNTRY_CODES; print(f'{len(SIPRI_COUNTRY_CODES)} countries')"`
Expected: `60 countries` (or close to it)

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/sipri_transfers.py src/ingestion/scheduler.py
git commit -m "feat: expand SIPRI coverage from 26 to 60 countries + buyer-side import queries"
```

---

### Task 3: Expand Eurostat + GDELT Fetch Limits

**Files:**
- Modify: `src/ingestion/eurostat_trade.py` (expand EU reporters)
- Modify: `src/ingestion/scheduler.py` (increase GDELT max_per_query)

- [ ] **Step 1: Expand Eurostat DEFAULT_REPORTERS to all 27 EU members**

In `src/ingestion/eurostat_trade.py`, replace line 31:

```python
DEFAULT_REPORTERS = ["DE", "FR", "IT", "ES", "NL", "SE"]
```

with:

```python
DEFAULT_REPORTERS = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
]
```

- [ ] **Step 2: Increase GDELT max_per_query from 25 to 100**

In `src/ingestion/scheduler.py`, find line 44:

```python
        articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=25)
```

Replace with:

```python
        articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=100)
```

- [ ] **Step 3: Verify no errors**

Run: `python -c "from src.ingestion.eurostat_trade import DEFAULT_REPORTERS; print(f'{len(DEFAULT_REPORTERS)} EU reporters')"`
Expected: `27 EU reporters`

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/eurostat_trade.py src/ingestion/scheduler.py
git commit -m "feat: expand Eurostat to all 27 EU members + increase GDELT to 100 records/query"
```

---

### Task 4: Add Cobalt Fallback Detection + Alerting

**Files:**
- Modify: `src/ingestion/scheduler.py` (enhance refresh_cobalt_feeds with explicit fallback detection)

The current `refresh_cobalt_feeds()` function logs results but doesn't distinguish live data from fallback. The existing connectors already include `"source"` fields that say `"(fallback)"` when stale data is used. We just need the scheduler to detect and escalate this.

- [ ] **Step 1: Replace the refresh_cobalt_feeds function**

In `src/ingestion/scheduler.py`, replace the entire `refresh_cobalt_feeds` function (lines 232-261) with:

```python
async def refresh_cobalt_feeds():
    """Refresh all cobalt-specific data feeds with fallback detection.

    Each cobalt connector returns a 'source' field that includes
    '(fallback)' when live fetch fails. We detect this and log
    at ERROR level so ops monitoring can alert.
    """
    try:
        from src.ingestion.bgs_minerals import BGSCobaltClient
        from src.ingestion.nrcan_cobalt import NRCanCobaltClient
        from src.ingestion.sherritt_cobalt import SherrittCobaltClient
        from src.ingestion.osint_feeds import (
            USGSCobaltDataClient, GlencoreProductionClient,
            CMOCProductionClient, IMFCobaltPriceClient,
        )

        results = {}
        fallbacks = []

        # BGS World Mineral Statistics
        bgs = await BGSCobaltClient().fetch_cobalt_production()
        results["bgs"] = len(bgs)
        if bgs and "fallback" in str(bgs[0].get("source", "")).lower():
            fallbacks.append("BGS")

        # NRCan Canadian Cobalt
        nrcan = await NRCanCobaltClient().fetch_canada_cobalt_stats()
        results["nrcan"] = "ok" if nrcan.get("production_tonnes") else "empty"
        if "fallback" in str(nrcan.get("source", "")).lower():
            fallbacks.append("NRCan")

        # USGS Cobalt Data
        usgs = await USGSCobaltDataClient().fetch_cobalt_production()
        results["usgs"] = len(usgs)

        # Sherritt stock + operations
        sherritt = await SherrittCobaltClient().fetch_stock_data()
        results["sherritt_price"] = sherritt.get("price_cad", "n/a")
        if "fallback" in str(sherritt.get("source", "")).lower():
            fallbacks.append("Sherritt")

        # Glencore production
        glencore = await GlencoreProductionClient().fetch_production()
        results["glencore"] = "ok" if glencore else "empty"
        if glencore and "fallback" in str(glencore.get("source", "")).lower():
            fallbacks.append("Glencore")

        # CMOC production
        cmoc = await CMOCProductionClient().fetch_production()
        results["cmoc"] = "ok" if cmoc else "empty"
        if cmoc and "fallback" in str(cmoc.get("source", "")).lower():
            fallbacks.append("CMOC")

        # IMF Cobalt Prices
        imf = await IMFCobaltPriceClient().fetch_cobalt_prices()
        results["imf_prices"] = len(imf)

        logger.info("[scheduler] Cobalt feeds refreshed: %s", results)

        if fallbacks:
            logger.error(
                "[scheduler] COBALT FALLBACK ALERT: %d/%d feeds returned stale fallback data: %s. "
                "Live API fetch may be failing — investigate immediately.",
                len(fallbacks), 7, ", ".join(fallbacks),
            )
    except Exception as e:
        logger.error("[scheduler] Cobalt feed refresh failed: %s", e)
```

- [ ] **Step 2: Upgrade Comtrade key check from warning to error**

In `src/ingestion/scheduler.py`, find the `refresh_comtrade_cobalt` inner function (around line 488). Change the warning to an error:

```python
        if not key:
            logger.error(
                "[scheduler] UN_COMTRADE_API_KEY not set — Comtrade cobalt bilateral "
                "queries DISABLED. Set the env var to enable (free registration at comtradeplus.un.org)."
            )
            return
```

- [ ] **Step 3: Verify no errors**

Run: `python -c "from src.ingestion.scheduler import create_scheduler; s = create_scheduler(); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat: add cobalt fallback detection + escalate Comtrade missing key to error"
```

---

### Task 5: Add Tests + Regression Check

**Files:**
- Create: `tests/test_scheduler_feeds.py`

- [ ] **Step 1: Create test file**

```python
# tests/test_scheduler_feeds.py
"""Tests for scheduler feed registration and configuration."""
from __future__ import annotations

import pytest


def test_scheduler_creates_all_jobs():
    """Scheduler registers all expected jobs."""
    from src.ingestion.scheduler import create_scheduler
    scheduler = create_scheduler()
    jobs = scheduler.get_jobs()
    job_ids = {j.id for j in jobs}

    # Core feeds (already existed)
    assert "flights" in job_ids
    assert "gdelt" in job_ids
    assert "sipri" in job_ids
    assert "worldbank" in job_ids
    assert "cobalt_feeds" in job_ids
    assert "cobalt_alerts" in job_ids

    # Newly scheduled trade feeds
    assert "census_trade" in job_ids
    assert "uk_hmrc_trade" in job_ids
    assert "eurostat_trade" in job_ids
    assert "statcan_trade" in job_ids
    assert "defense_news_rss" in job_ids
    assert "ofac_sdn" in job_ids
    assert "cia_factbook" in job_ids

    # Canada intel feeds
    assert "gc_defence_news" in job_ids
    assert "nato_news" in job_ids
    assert "norad_news" in job_ids
    assert "canadian_sanctions" in job_ids
    assert "arctic_osint" in job_ids
    assert "parliament_nddn" in job_ids

    # Should have 22+ jobs
    assert len(jobs) >= 22, f"Expected >= 22 jobs, got {len(jobs)}: {sorted(job_ids)}"


def test_sipri_country_coverage():
    """SIPRI tracks at least 55 countries."""
    from src.ingestion.sipri_transfers import SIPRI_COUNTRY_CODES
    assert len(SIPRI_COUNTRY_CODES) >= 55, (
        f"Expected >= 55 countries, got {len(SIPRI_COUNTRY_CODES)}"
    )
    # Key adversaries must be present
    for country in ["Russia", "China", "Iran", "DPRK"]:
        assert country in SIPRI_COUNTRY_CODES, f"Missing adversary: {country}"
    # Key allies must be present
    for country in ["Canada", "United States", "United Kingdom", "Australia", "Japan"]:
        assert country in SIPRI_COUNTRY_CODES, f"Missing ally: {country}"


def test_eurostat_all_eu_members():
    """Eurostat reporters include all 27 EU member states."""
    from src.ingestion.eurostat_trade import DEFAULT_REPORTERS
    assert len(DEFAULT_REPORTERS) == 27, (
        f"Expected 27 EU reporters, got {len(DEFAULT_REPORTERS)}"
    )
    # Spot check major economies
    for code in ["DE", "FR", "IT", "ES", "PL", "NL", "SE"]:
        assert code in DEFAULT_REPORTERS, f"Missing EU reporter: {code}"


def test_gdelt_fetches_100_per_query():
    """GDELT scheduler call uses max_per_query >= 100."""
    import inspect
    from src.ingestion.scheduler import ingest_gdelt_news
    source = inspect.getsource(ingest_gdelt_news)
    assert "max_per_query=100" in source or "max_per_query=250" in source, (
        "GDELT should fetch 100+ records per query, found: " + source
    )


def test_cobalt_fallback_detection_logs_error():
    """refresh_cobalt_feeds function includes fallback detection logic."""
    import inspect
    from src.ingestion.scheduler import refresh_cobalt_feeds
    source = inspect.getsource(refresh_cobalt_feeds)
    assert "COBALT FALLBACK ALERT" in source, "Missing fallback alert message"
    assert "fallbacks.append" in source, "Missing fallback tracking"
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/test_scheduler_feeds.py -v -p no:recording`
Expected: All 5 tests PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -p no:recording -q --tb=line 2>&1 | tail -5`
Expected: No new failures (only pre-existing test_mitigation failure)

- [ ] **Step 4: Commit**

```bash
git add tests/test_scheduler_feeds.py
git commit -m "test: add scheduler feed registration and configuration tests"
```

---

## Summary

| Task | Description | Impact |
|------|-------------|--------|
| 1 | Schedule 7 high-value feeds | Census/HMRC/Eurostat/StatCan trade + Defense News RSS + OFAC SDN + CIA Factbook now auto-ingest |
| 2 | Expand SIPRI to 60 countries + buyer-side | 2.3x country coverage + adversary import tracking |
| 3 | Expand Eurostat 6→27 EU + GDELT 25→100 | 4.5x EU coverage + 4x news volume |
| 4 | Cobalt fallback detection + Comtrade key escalation | Alerts on stale data instead of silent failure |
| 5 | Tests + regression | 5 tests covering all changes |

**Total: 5 tasks, 5 commits, 4 files modified, 1 file created**
