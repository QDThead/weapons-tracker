# Feed Resilience & Self-Healing Design

**Date:** 2026-04-02
**Scope:** Self-healing retry wrapper, per-job timeouts, USGS MCS expansion, Data Feeds dashboard integration

---

## 1. Self-Healing Retry Wrapper (`@resilient_job`)

### Location
`src/ingestion/scheduler.py` — new decorator applied to all 25 scheduled jobs.

### Behavior
- **3 retry attempts** with exponential backoff: 15s → 30s → 60s.
- Each retry logs at WARNING level with attempt number and error.
- On final failure (attempt 3): log at CRITICAL level, mark feed as **degraded** in shared `feed_health` dict.
- On next successful run: auto-clear degraded state and reset failure count. This is the self-healing mechanism.

### `feed_health` Dict
Module-level dict in `scheduler.py`, keyed by job name:
```python
feed_health: dict[str, FeedHealthState] = {}

@dataclass
class FeedHealthState:
    status: str          # "ok" | "degraded" | "failed"
    last_success: str    # ISO timestamp
    last_failure: str    # ISO timestamp
    failure_count: int
    last_error: str      # truncated error message (max 200 chars)
    retry_count: int     # retries since last success
    timeout_s: int       # configured timeout
```

### Decorator Signature
```python
def resilient_job(name: str, timeout_s: int = 120, max_retries: int = 3):
```
Wraps both sync and async callables. For async: uses `asyncio.wait_for`. For sync: uses `concurrent.futures.ThreadPoolExecutor` with timeout.

### Application
Every `scheduler.add_job(...)` call wraps its target function:
```python
scheduler.add_job(resilient_job("flights", timeout_s=30)(fetch_flights), ...)
```

### Per-Job Timeouts
| Job | Timeout |
|-----|---------|
| Military flights | 30s |
| GDELT news | 60s |
| Defense RSS | 60s |
| GC Defence News | 60s |
| Cobalt alert engine | 90s |
| Cobalt feeds (7 sources) | 180s |
| DND Procurement | 120s |
| Comtrade bilateral | 180s |
| All others | 120s (default) |

---

## 2. Feed Health API Endpoint

### Location
`src/api/routes.py` — new endpoint.

### Endpoint
`GET /feeds/health` — returns the `feed_health` dict as JSON. No auth required (internal monitoring).

### Response
```json
{
  "feeds": {
    "flights": {
      "status": "ok",
      "last_success": "2026-04-02T21:15:00Z",
      "last_failure": null,
      "failure_count": 0,
      "last_error": null,
      "retry_count": 0,
      "timeout_s": 30
    },
    "gdelt": {
      "status": "degraded",
      "last_success": "2026-04-02T20:00:00Z",
      "last_failure": "2026-04-02T21:00:00Z",
      "failure_count": 3,
      "last_error": "HTTPError: 429 Too Many Requests",
      "retry_count": 3,
      "timeout_s": 60
    }
  },
  "summary": {
    "total": 25,
    "ok": 23,
    "degraded": 2,
    "failed": 0
  }
}
```

---

## 3. USGS MCS Data Expansion

### Location
`src/ingestion/critical_minerals.py` — expand `CriticalMineralsClient`.

### Strategy: CSV-first, PDF fallback, seeded last
1. For each of the 30 minerals, check for a USGS CSV at known URL patterns:
   - `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-{mineral_slug}-production.csv`
   - `https://d9-wret.s3.us-west-2.amazonaws.com/assets/palladium/production/atoms/files/mcs2025-{mineral_slug}.csv`
2. If CSV found: parse it (same pattern as existing `USGSCobaltDataClient`).
3. If no CSV: download the PDF from `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-{mineral_slug}.pdf` and extract tables using `pdfplumber`.
4. If PDF parsing fails: fall back to existing seeded data, mark source as `(fallback)`.

### PDF Parsing (pdfplumber)
- Extract all tables from both pages of each MCS commodity PDF.
- Look for the "World Mine Production" table (typically page 2).
- Parse country names and production values for latest 2 years.
- Handle footnotes (e, p, W, — markers) by stripping them from numeric values.

### Dependency
Add `pdfplumber` to `requirements.txt`.

### Schedule
Run as part of the existing daily cobalt feeds job at 5 AM, expanded to cover all 30 minerals. Job name: `usgs_minerals`. Timeout: 300s (PDF downloads are slow).

### Output
Update `CriticalMineralsClient` to return enriched data with `live_production` field alongside existing seeded data. The `get_all_minerals()` and `get_mineral_by_name()` functions in `mineral_supply_chains.py` merge live data when available.

---

## 4. Data Feeds Dashboard Integration

### Location
`src/static/index.html` — Data Feeds tab (`page-data-feeds`).

### Alert Banner
At the top of the Data Feeds tab, a red/amber banner appears when any feeds are degraded or failed:
```
[!] 2 feeds degraded: GDELT News (last success 3h ago), BGS Minerals (fallback data)
```
- Red background for failed feeds (3+ consecutive failures).
- Amber background for degraded feeds (1-2 failures, or stale data).
- Hidden when all feeds are healthy.

### Per-Feed Status Badges
Each feed card in the Data Feeds tab gets a status badge:
- **GREEN** dot + "FRESH" — last fetch within expected TTL.
- **AMBER** dot + "STALE" — last fetch > TTL but < 2x TTL, or 1-2 retry failures.
- **RED** dot + "FAILED" — last fetch > 2x TTL, or 3+ consecutive failures.

### Data Source
Merge two endpoints:
- `/validation/health` — cache freshness per connector.
- `/feeds/health` — retry state and failure counts from `@resilient_job`.

### Sort Order
Failed feeds sort to top of their section, then stale, then fresh.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/ingestion/scheduler.py` | Add `@resilient_job` decorator, `feed_health` dict, wrap all 25 jobs |
| `src/api/routes.py` | Add `GET /feeds/health` endpoint |
| `src/ingestion/critical_minerals.py` | CSV-first USGS fetcher, pdfplumber PDF parser, expanded to 30 minerals |
| `src/static/index.html` | Data Feeds tab: alert banner, status badges, sort by health |
| `requirements.txt` | Add `pdfplumber` |

## Files Not Modified
- Individual connector files (retry logic is in the decorator, not per-connector)
- Database models (no schema changes)
- Other tabs/pages (Data Feeds tab only)
