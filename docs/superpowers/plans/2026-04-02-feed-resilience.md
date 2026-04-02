# Feed Resilience & Self-Healing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all 25 data feeds self-healing with retry/backoff, add per-job timeouts, expand USGS mineral data (CSV-first with PDF fallback), and surface feed health prominently on the Data Feeds dashboard.

**Architecture:** A `resilient_job` decorator in `scheduler.py` wraps every scheduled job with 3-attempt retry, exponential backoff, per-job timeout, and health state tracking. A new `/feeds/health` endpoint exposes this state. The Data Feeds tab merges this with `/validation/health` to show a failure banner and per-card status badges. USGS expansion adds CSV+PDF parsing to `critical_minerals.py`.

**Tech Stack:** Python 3.9+, APScheduler, asyncio, pdfplumber (new dep), httpx, FastAPI, Chart.js dashboard

---

### Task 1: `@resilient_job` Decorator + Feed Health State

**Files:**
- Modify: `src/ingestion/scheduler.py` (add decorator, `feed_health` dict, `FeedHealthState` dataclass at top of file)

- [ ] **Step 1: Add imports and FeedHealthState dataclass**

Add after the existing imports (line 50) in `src/ingestion/scheduler.py`:

```python
import functools
import time
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
```

Add after `logger = logging.getLogger(__name__)` (line 52):

```python
@dataclass
class FeedHealthState:
    """Tracks health of a single scheduled feed."""
    status: str = "ok"              # "ok" | "degraded" | "failed"
    last_success: str | None = None # ISO timestamp
    last_failure: str | None = None # ISO timestamp
    failure_count: int = 0
    last_error: str = ""            # truncated to 200 chars
    retry_count: int = 0            # retries since last success
    timeout_s: int = 120

feed_health: dict[str, FeedHealthState] = {}
```

- [ ] **Step 2: Implement the `resilient_job` decorator**

Add after the `feed_health` dict:

```python
def resilient_job(name: str, timeout_s: int = 120, max_retries: int = 3):
    """Decorator that wraps a scheduler job with retry, timeout, and health tracking.

    - 3 retry attempts with exponential backoff (15s, 30s, 60s)
    - Per-job timeout via asyncio.wait_for
    - Tracks success/failure in feed_health dict
    - Self-healing: clears degraded state on next success
    """
    backoff_delays = [15, 30, 60]

    def decorator(func):
        # Initialize health state
        feed_health[name] = FeedHealthState(timeout_s=timeout_s)

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            state = feed_health[name]
            last_err = None

            for attempt in range(1, max_retries + 1):
                try:
                    await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_s)
                    # Success — self-heal
                    state.status = "ok"
                    state.last_success = datetime.now(timezone.utc).isoformat()
                    state.failure_count = 0
                    state.retry_count = 0
                    state.last_error = ""
                    return
                except asyncio.TimeoutError:
                    last_err = f"Timeout after {timeout_s}s"
                    logger.warning(
                        "[resilient] %s attempt %d/%d timed out after %ds",
                        name, attempt, max_retries, timeout_s,
                    )
                except Exception as e:
                    last_err = str(e)[:200]
                    logger.warning(
                        "[resilient] %s attempt %d/%d failed: %s",
                        name, attempt, max_retries, last_err,
                    )

                state.retry_count = attempt
                if attempt < max_retries:
                    delay = backoff_delays[attempt - 1] if attempt - 1 < len(backoff_delays) else 60
                    await asyncio.sleep(delay)

            # All retries exhausted
            state.failure_count += 1
            state.last_failure = datetime.now(timezone.utc).isoformat()
            state.last_error = last_err or "Unknown error"
            state.status = "failed" if state.failure_count >= 3 else "degraded"
            logger.critical(
                "[resilient] %s FAILED after %d attempts (consecutive failures: %d): %s",
                name, max_retries, state.failure_count, last_err,
            )

        return wrapper
    return decorator
```

- [ ] **Step 3: Remove try/except wrappers from all job functions**

Each job function (e.g., `ingest_gdelt_news`, `ingest_military_flights`, etc.) currently has its own `try/except` that swallows errors. The decorator now handles retry and error tracking, so these wrappers must be removed so errors propagate to the decorator.

For every `async def ingest_*` and `async def refresh_*` and `async def score_*` and `async def enrich_*` function, remove the outer `try/except Exception as e: logger.error(...)` block. Keep the function body (the `try` block contents). Keep any inner try/finally blocks for session cleanup.

Example — `ingest_gdelt_news` changes from:

```python
async def ingest_gdelt_news():
    """Fetch and store latest arms trade news."""
    try:
        client = GDELTArmsNewsClient()
        articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=100)

        session = SessionLocal()
        try:
            svc = PersistenceService(session)
            count = svc.store_news_articles(articles)
            logger.info("[scheduler] GDELT: stored %d new articles", count)
        finally:
            session.close()
    except Exception as e:
        logger.error("[scheduler] GDELT ingestion failed: %s", e)
```

to:

```python
async def ingest_gdelt_news():
    """Fetch and store latest arms trade news."""
    client = GDELTArmsNewsClient()
    articles = await client.fetch_latest_arms_news(timespan_minutes=30, max_per_query=100)

    session = SessionLocal()
    try:
        svc = PersistenceService(session)
        count = svc.store_news_articles(articles)
        logger.info("[scheduler] GDELT: stored %d new articles", count)
    finally:
        session.close()
```

Apply this same pattern to ALL job functions:
- `ingest_gdelt_news`
- `ingest_military_flights`
- `ingest_sipri_transfers` (keep inner try/except per-country, remove outer)
- `ingest_worldbank_indicators`
- `refresh_supply_chain`
- `ingest_procurement`
- `enrich_suppliers`
- `score_suppliers`
- `score_taxonomy`
- `refresh_cobalt_feeds`
- `ingest_gc_defence_news`
- `ingest_nato_news`
- `ingest_norad_news`
- `ingest_canadian_sanctions`
- `ingest_arctic_osint`
- `ingest_parliament_nddn`
- `ingest_census_trade`
- `ingest_uk_hmrc_trade`
- `ingest_eurostat_trade`
- `ingest_statcan_trade`
- `ingest_defense_news_rss`
- `ingest_sanctions_ofac`
- `ingest_cia_factbook`
- `refresh_comtrade_cobalt` (the inline async def)

- [ ] **Step 4: Wrap all `scheduler.add_job` calls with `resilient_job`**

In `create_scheduler()`, wrap each job function. Replace each `scheduler.add_job(func, ...)` with `scheduler.add_job(resilient_job(name, timeout_s=N)(func), ...)`.

The job name should match the `id` parameter. Timeout values per the spec:

```python
def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

    scheduler.add_job(
        resilient_job("flights", timeout_s=30)(ingest_military_flights),
        trigger=IntervalTrigger(minutes=5),
        id="flights",
        name="Military flight tracker",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("gdelt", timeout_s=60)(ingest_gdelt_news),
        trigger=IntervalTrigger(minutes=15),
        id="gdelt",
        name="GDELT arms trade news",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("cobalt_alerts", timeout_s=90)(run_cobalt_alert_engine),
        trigger=IntervalTrigger(minutes=30),
        id="cobalt_alerts",
        name="Cobalt supply chain alert engine",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("sipri", timeout_s=120)(ingest_sipri_transfers),
        trigger=CronTrigger(hour=2, minute=0),
        id="sipri",
        name="SIPRI arms transfers",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("worldbank", timeout_s=120)(ingest_worldbank_indicators),
        trigger=CronTrigger(hour=3, minute=0),
        id="worldbank",
        name="World Bank indicators",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("psi_supply_chain", timeout_s=120)(refresh_supply_chain),
        trigger=CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="psi_supply_chain",
        name="PSI supply chain refresh",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("procurement_scraper", timeout_s=120)(ingest_procurement),
        CronTrigger(day_of_week="sun", hour=2),
        id="procurement_scraper",
        name="DND procurement scraper",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("supplier_enrichment", timeout_s=120)(enrich_suppliers),
        CronTrigger(day_of_week="sun", hour=3),
        id="supplier_enrichment",
        name="Supplier ownership enrichment",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("supplier_scoring", timeout_s=120)(score_suppliers),
        CronTrigger(day_of_week="sun", hour=5),
        id="supplier_scoring",
        name="Supplier risk scoring",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("taxonomy_scoring", timeout_s=120)(score_taxonomy),
        IntervalTrigger(hours=6),
        id="taxonomy_scoring",
        name="DND risk taxonomy scoring",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("cobalt_feeds", timeout_s=180)(refresh_cobalt_feeds),
        CronTrigger(hour=5, minute=0),
        id="cobalt_feeds",
        name="Cobalt supply chain data feeds (BGS, NRCan, USGS, Sherritt, Glencore, CMOC)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("gc_defence_news", timeout_s=60)(ingest_gc_defence_news),
        trigger=IntervalTrigger(minutes=30),
        id="gc_defence_news",
        name="GC Defence News (DND/GAC/Public Safety)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("nato_news", timeout_s=60)(ingest_nato_news),
        trigger=IntervalTrigger(hours=1),
        id="nato_news",
        name="NATO News RSS",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("norad_news", timeout_s=60)(ingest_norad_news),
        trigger=IntervalTrigger(hours=6),
        id="norad_news",
        name="NORAD Press Releases",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("canadian_sanctions", timeout_s=120)(ingest_canadian_sanctions),
        trigger=CronTrigger(hour=6, minute=0),
        id="canadian_sanctions",
        name="Canadian Sanctions (GAC SEMA)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("arctic_osint", timeout_s=60)(ingest_arctic_osint),
        trigger=IntervalTrigger(hours=2),
        id="arctic_osint",
        name="Arctic OSINT News (3 feeds)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("parliament_nddn", timeout_s=120)(ingest_parliament_nddn),
        trigger=CronTrigger(hour=8, minute=0),
        id="parliament_nddn",
        name="Parliament NDDN Committee",
        replace_existing=True,
        max_instances=1,
    )

    # Comtrade cobalt bilateral — inline async def, wrap it too
    async def _comtrade_cobalt_inner():
        import os
        from src.ingestion.comtrade import ComtradeMaterialsClient
        key = os.getenv("UN_COMTRADE_API_KEY")
        if not key:
            logger.error(
                "[scheduler] UN_COMTRADE_API_KEY not set — Comtrade cobalt bilateral "
                "queries DISABLED. Set the env var to enable."
            )
            return
        client = ComtradeMaterialsClient(subscription_key=key)
        records = await client.fetch_cobalt_bilateral_flows()
        logger.info("Comtrade cobalt bilateral: fetched %d records", len(records))

    scheduler.add_job(
        resilient_job("comtrade_cobalt", timeout_s=180)(_comtrade_cobalt_inner),
        trigger=CronTrigger(day=1, hour=6, minute=0),
        id="comtrade_cobalt",
        name="Comtrade cobalt bilateral flows",
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("census_trade", timeout_s=120)(ingest_census_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="census_trade",
        name="US Census monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("uk_hmrc_trade", timeout_s=120)(ingest_uk_hmrc_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=15),
        id="uk_hmrc_trade",
        name="UK HMRC monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("eurostat_trade", timeout_s=120)(ingest_eurostat_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=30),
        id="eurostat_trade",
        name="Eurostat EU monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("statcan_trade", timeout_s=120)(ingest_statcan_trade),
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=45),
        id="statcan_trade",
        name="Statistics Canada monthly arms trade",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("defense_news_rss", timeout_s=60)(ingest_defense_news_rss),
        trigger=IntervalTrigger(minutes=30),
        id="defense_news_rss",
        name="Defense News RSS (4 feeds)",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("ofac_sdn", timeout_s=120)(ingest_sanctions_ofac),
        trigger=CronTrigger(hour=6, minute=30),
        id="ofac_sdn",
        name="OFAC SDN sanctions list",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.add_job(
        resilient_job("cia_factbook", timeout_s=120)(ingest_cia_factbook),
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="cia_factbook",
        name="CIA World Factbook military data",
        replace_existing=True,
        max_instances=1,
    )

    return scheduler
```

- [ ] **Step 5: Verify server starts**

Run: `python -m src.main`
Expected: Server starts, logs "25 jobs configured", no import errors.

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/scheduler.py
git commit -m "feat: add @resilient_job decorator — retry, timeout, self-healing for all 25 feeds"
```

---

### Task 2: `/feeds/health` API Endpoint

**Files:**
- Modify: `src/api/routes.py` (add endpoint)

- [ ] **Step 1: Add the endpoint**

Add after the existing `/config/map-key` endpoint in `src/api/routes.py`:

```python
@router.get("/feeds/health")
async def get_feeds_health():
    """Return health state of all scheduled data feeds."""
    from src.ingestion.scheduler import feed_health
    feeds = {}
    ok = degraded = failed = 0
    for name, state in feed_health.items():
        feeds[name] = {
            "status": state.status,
            "last_success": state.last_success,
            "last_failure": state.last_failure,
            "failure_count": state.failure_count,
            "last_error": state.last_error,
            "retry_count": state.retry_count,
            "timeout_s": state.timeout_s,
        }
        if state.status == "ok":
            ok += 1
        elif state.status == "degraded":
            degraded += 1
        else:
            failed += 1
    return {
        "feeds": feeds,
        "summary": {"total": len(feeds), "ok": ok, "degraded": degraded, "failed": failed},
    }
```

- [ ] **Step 2: Verify endpoint**

Run: `curl -s http://localhost:8000/feeds/health | python -m json.tool | head -20`
Expected: JSON with `feeds` dict (25 entries, all status "ok") and `summary`.

- [ ] **Step 3: Commit**

```bash
git add src/api/routes.py
git commit -m "feat: add /feeds/health endpoint exposing retry state for all scheduled jobs"
```

---

### Task 3: USGS MCS CSV + PDF Expansion

**Files:**
- Modify: `src/ingestion/critical_minerals.py` (add CSV fetcher, PDF parser)
- Modify: `requirements.txt` (add pdfplumber)

- [ ] **Step 1: Add pdfplumber to requirements.txt**

Add to the `# PDF / Templating` section of `requirements.txt`:

```
pdfplumber>=0.10
```

- [ ] **Step 2: Install the dependency**

Run: `pip install pdfplumber`

- [ ] **Step 3: Add CSV+PDF fetch methods to CriticalMineralsClient**

Add these methods to the `CriticalMineralsClient` class in `src/ingestion/critical_minerals.py`, after the existing `fetch_all_summaries` method:

```python
    # ── Mineral slug mapping (mineral name → USGS URL slug) ──
    MINERAL_SLUGS: dict[str, str] = {
        "Cobalt": "cobalt",
        "Lithium": "lithium",
        "Rare Earth Elements": "rare-earths",
        "Titanium": "titanium",
        "Tungsten": "tungsten",
        "Chromium": "chromium",
        "Manganese": "manganese",
        "Nickel": "nickel",
        "Tantalum": "tantalum",
        "Niobium": "niobium",
        "Beryllium": "beryllium",
        "Germanium": "germanium",
        "Gallium": "gallium",
        "Copper": "copper",
        "Uranium": "uranium",
        "Vanadium": "vanadium",
        "Antimony": "antimony",
        "Rhenium": "rhenium",
        "Indium": "indium",
        "Hafnium": "hafnium",
        "Platinum Group Metals": "platinum",
        "Zirconium": "zirconium",
        "Molybdenum": "molybdenum",
        "Magnesium": "magnesium",
        "Silicon": "silicon",
        "Graphite": "graphite",
        "Tin": "tin",
        "Lead": "lead",
        "Bismuth": "bismuth",
        "Fluorite": "fluorspar",
    }

    async def fetch_mineral_csv(self, mineral: str) -> list[dict] | None:
        """Try to fetch USGS CSV data for a mineral.

        Checks two known URL patterns. Returns list of
        {country, year, production_t} dicts, or None if not available.
        """
        slug = self.MINERAL_SLUGS.get(mineral, mineral.lower().replace(" ", "-"))
        urls = [
            f"https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-{slug}-production.csv",
            f"https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/atoms/files/mcs2025-{slug}.csv",
        ]
        client = await self._get_client()
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue
                text = resp.text
                if not text.strip() or "<!DOCTYPE" in text[:100]:
                    continue
                return self._parse_usgs_csv(text, mineral)
            except httpx.HTTPError:
                continue
        return None

    @staticmethod
    def _parse_usgs_csv(text: str, mineral: str) -> list[dict]:
        """Parse USGS CSV: header row has year columns, data rows are countries."""
        import csv
        import io
        import re

        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if len(rows) < 2:
            return []

        header = rows[0]
        # Find year columns (4-digit numbers)
        year_cols = {}
        for i, col in enumerate(header):
            match = re.search(r"(20\d{2})", col)
            if match:
                year_cols[i] = int(match.group(1))

        if not year_cols:
            return []

        results = []
        for row in rows[1:]:
            if not row or not row[0].strip():
                continue
            country = row[0].strip()
            if country.lower() in ("total", "world total", "grand total", "world"):
                continue
            for col_idx, year in year_cols.items():
                if col_idx >= len(row):
                    continue
                val = row[col_idx].strip().replace(",", "").replace(" ", "")
                # Strip USGS footnote markers (e, p, r, W, --, NA)
                val = re.sub(r"[eprW]$", "", val).strip()
                if not val or val in ("--", "NA", "W", "—", "XX"):
                    continue
                try:
                    tonnes = float(val)
                    results.append({"country": country, "year": year, "production_t": tonnes})
                except ValueError:
                    continue
        return results

    async def fetch_mineral_pdf(self, mineral: str) -> list[dict] | None:
        """Download USGS MCS PDF and extract production table using pdfplumber.

        Returns list of {country, year, production_t} dicts, or None on failure.
        """
        try:
            import pdfplumber
        except ImportError:
            logger.warning("pdfplumber not installed — PDF parsing disabled")
            return None

        slug = self.MINERAL_SLUGS.get(mineral, mineral.lower().replace(" ", "-"))
        url = f"{self.base_url}mcs2025-{slug}.pdf"
        client = await self._get_client()
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return None
        except httpx.HTTPError:
            return None

        import io
        import re

        results = []
        try:
            with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table or len(table) < 2:
                            continue
                        header = [str(c or "").strip() for c in table[0]]
                        # Look for year columns
                        year_cols = {}
                        for i, col in enumerate(header):
                            match = re.search(r"(20\d{2})", col)
                            if match:
                                year_cols[i] = int(match.group(1))
                        if not year_cols:
                            continue

                        for row in table[1:]:
                            if not row or not row[0]:
                                continue
                            country = str(row[0]).strip()
                            if country.lower() in ("total", "world total", "grand total", "world", ""):
                                continue
                            for col_idx, year in year_cols.items():
                                if col_idx >= len(row) or not row[col_idx]:
                                    continue
                                val = str(row[col_idx]).strip().replace(",", "").replace(" ", "")
                                val = re.sub(r"[eprW]$", "", val).strip()
                                if not val or val in ("--", "NA", "W", "—", "XX"):
                                    continue
                                try:
                                    tonnes = float(val)
                                    results.append({"country": country, "year": year, "production_t": tonnes})
                                except ValueError:
                                    continue
                        if results:
                            return results
        except Exception as e:
            logger.warning("PDF parse failed for %s: %s", mineral, e)
        return results if results else None

    async def fetch_live_production(self, mineral: str) -> list[dict]:
        """Fetch production data for a mineral: CSV first, PDF fallback, seeded last.

        Returns list of {country, year, production_t, source} dicts.
        """
        # Try CSV first
        data = await self.fetch_mineral_csv(mineral)
        if data:
            for d in data:
                d["source"] = "USGS MCS 2025 CSV"
            logger.info("USGS CSV: %s — %d records", mineral, len(data))
            return data

        # Try PDF fallback
        data = await self.fetch_mineral_pdf(mineral)
        if data:
            for d in data:
                d["source"] = "USGS MCS 2025 PDF (pdfplumber)"
            logger.info("USGS PDF: %s — %d records", mineral, len(data))
            return data

        # Seeded fallback
        logger.info("USGS: %s — using seeded fallback", mineral)
        return []

    async def fetch_all_live_production(self) -> dict[str, list[dict]]:
        """Fetch production data for all 30 minerals.

        Returns dict mapping mineral name to list of production records.
        Only includes minerals where live data was found.
        """
        results = {}
        for mineral in self.MINERAL_SLUGS:
            data = await self.fetch_live_production(mineral)
            if data:
                results[mineral] = data
        logger.info(
            "USGS live production: %d/%d minerals with live data",
            len(results), len(self.MINERAL_SLUGS),
        )
        return results
```

- [ ] **Step 4: Add USGS minerals job to scheduler**

In `src/ingestion/scheduler.py`, add an import and job function after `refresh_cobalt_feeds`:

```python
async def refresh_usgs_minerals():
    """Fetch live USGS production data for all 30 defense minerals."""
    from src.ingestion.critical_minerals import CriticalMineralsClient
    client = CriticalMineralsClient()
    try:
        results = await client.fetch_all_live_production()
        logger.info("[scheduler] USGS minerals: %d minerals with live data", len(results))
    finally:
        await client.close()
```

In `create_scheduler()`, add after the cobalt_feeds job:

```python
    scheduler.add_job(
        resilient_job("usgs_minerals", timeout_s=300)(refresh_usgs_minerals),
        CronTrigger(hour=5, minute=30),
        id="usgs_minerals",
        name="USGS mineral production (30 minerals, CSV+PDF)",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 5: Verify pdfplumber import**

Run: `python -c "import pdfplumber; print(pdfplumber.__version__)"`
Expected: Version number (e.g., `0.11.4`)

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/critical_minerals.py src/ingestion/scheduler.py requirements.txt
git commit -m "feat: USGS MCS expansion — CSV-first + pdfplumber PDF fallback for 30 minerals"
```

---

### Task 4: Data Feeds Dashboard — Alert Banner + Status Badges

**Files:**
- Modify: `src/static/index.html` (Data Feeds tab: banner, badge colors, sort)

- [ ] **Step 1: Add CSS for feed health banner**

Add after the existing `.feeds-header` CSS block (around line 450) in `src/static/index.html`:

```css
.feeds-health-banner { padding:14px 20px; border-radius:8px; margin-bottom:16px; font-size:13px; display:none; }
.feeds-health-banner.has-issues { display:block; }
.feeds-health-banner.has-failed { background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3); color:#fca5a5; }
.feeds-health-banner.has-degraded { background:rgba(245,158,11,0.1); border:1px solid rgba(245,158,11,0.3); color:#fcd34d; }
.feeds-health-banner strong { color:#fff; }
.feeds-health-banner .banner-feed { display:inline-block; background:rgba(255,255,255,0.08); padding:2px 8px; border-radius:4px; margin:2px 4px; font-family:var(--font-mono); font-size:11px; }
```

- [ ] **Step 2: Add health banner HTML**

In the Data Feeds page section (around line 2309), add a banner div right after the opening `<div id="page-data-feeds" ...>` and before the `<div class="feeds-header" ...>`:

```html
    <div id="feeds-health-banner" class="feeds-health-banner"></div>
```

- [ ] **Step 3: Update `renderDataFeeds` to fetch `/feeds/health` and render banner + sort**

In the `renderDataFeeds` function (around line 6804), modify the parallel fetch to also get `/feeds/health`:

Change:
```javascript
  var [freshnessResult, enrichmentResult] = await Promise.allSettled([
    fetch(API + '/insights/freshness').then(r => r.ok ? r.json() : []),
    fetch(API + '/enrichment/sources').then(r => r.ok ? r.json() : { sources: [] }),
  ]);
```

To:
```javascript
  var [freshnessResult, enrichmentResult, feedHealthResult] = await Promise.allSettled([
    fetch(API + '/insights/freshness').then(r => r.ok ? r.json() : []),
    fetch(API + '/enrichment/sources').then(r => r.ok ? r.json() : { sources: [] }),
    fetch(API + '/feeds/health').then(r => r.ok ? r.json() : { feeds: {}, summary: {} }),
  ]);
```

After the existing `dataFeedsEnrichmentSources = ...` line, add:

```javascript
  var feedHealthData = feedHealthResult.status === 'fulfilled' ? feedHealthResult.value : { feeds: {}, summary: {} };

  // Render health banner
  var banner = document.getElementById('feeds-health-banner');
  var issues = [];
  Object.entries(feedHealthData.feeds || {}).forEach(function(entry) {
    var fname = entry[0], fstate = entry[1];
    if (fstate.status === 'failed' || fstate.status === 'degraded') {
      var ago = fstate.last_success ? timeAgo(new Date(fstate.last_success)) : 'never';
      issues.push({ name: fname, status: fstate.status, error: fstate.last_error, ago: ago });
    }
  });
  if (issues.length > 0) {
    var hasFailed = issues.some(function(i) { return i.status === 'failed'; });
    banner.className = 'feeds-health-banner has-issues ' + (hasFailed ? 'has-failed' : 'has-degraded');
    banner.innerHTML = '<strong>' + (hasFailed ? '&#9888; Feed Failures Detected' : '&#9888; Degraded Feeds') + '</strong> — ' +
      issues.length + ' feed' + (issues.length > 1 ? 's' : '') + ' with issues:<br>' +
      issues.map(function(i) {
        return '<span class="banner-feed">' + esc(i.name) + ' (' + esc(i.status) + ', last OK: ' + esc(i.ago) + ')</span>';
      }).join(' ');
  } else {
    banner.className = 'feeds-health-banner';
    banner.innerHTML = '';
  }
```

- [ ] **Step 4: Update feed card dot color to use `/feeds/health` data**

In the `renderDataFeeds` function, inside the `sec.feeds.map` callback where `dotClass` is computed (around line 6837), add a health override after the existing `dotClass` computation:

```javascript
      // Override dot color with /feeds/health retry state
      var feedState = feedHealthData.feeds[fd.id] || feedHealthData.feeds[fd.name] || null;
      if (feedState) {
        if (feedState.status === 'failed') dotClass = 'red';
        else if (feedState.status === 'degraded') dotClass = 'orange';
      }
```

- [ ] **Step 5: Sort failed feeds to top of each section**

In the `renderDataFeeds` function, after `sectionMap[fd.section].feeds.push(fd);` (around line 6830), before rendering, add a sort:

```javascript
  // Sort: failed feeds first, then degraded, then by original order
  sections.forEach(function(sec) {
    sec.feeds.sort(function(a, b) {
      var aState = (feedHealthData.feeds || {})[a.id] || {};
      var bState = (feedHealthData.feeds || {})[b.id] || {};
      var aPri = aState.status === 'failed' ? 0 : aState.status === 'degraded' ? 1 : 2;
      var bPri = bState.status === 'failed' ? 0 : bState.status === 'degraded' ? 1 : 2;
      return aPri - bPri;
    });
  });
```

- [ ] **Step 6: Verify the Data Feeds tab renders**

Refresh the browser, navigate to the Data Feeds tab.
Expected: Feed cards render with status dots. No banner if all feeds are ok. If any feed has failed, red/amber banner appears at top.

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat: Data Feeds dashboard — health banner + status badges + failed-first sort"
```

---

### Task 5: Final Integration Test + Push

- [ ] **Step 1: Restart server and verify all endpoints**

```bash
# Kill existing server, restart
cd weapons-tracker && source venv/Scripts/activate && python -m src.main
```

Verify in another terminal:
```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/feeds/health | python -m json.tool | head -10
```

Expected: `/health` returns ok, `/feeds/health` returns 25+ feeds all status "ok".

- [ ] **Step 2: Wait for a scheduled job to fire and verify self-healing tracking**

Wait ~5 minutes for the flight tracker to run. Then:
```bash
curl -s http://localhost:8000/feeds/health | python -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['feeds']['flights'], indent=2))"
```

Expected: `last_success` is populated, `status` is "ok".

- [ ] **Step 3: Push all commits**

```bash
git push
```
