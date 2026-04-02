# tests/test_scheduler_feeds.py
"""Tests for scheduler feed registration and configuration."""
from __future__ import annotations


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
    """SIPRI tracks at least 50 countries."""
    from src.ingestion.sipri_transfers import SIPRI_COUNTRY_CODES
    assert len(SIPRI_COUNTRY_CODES) >= 50, (
        f"Expected >= 50 countries, got {len(SIPRI_COUNTRY_CODES)}"
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
        "GDELT should fetch 100+ records per query"
    )


def test_cobalt_fallback_detection_logs_error():
    """refresh_cobalt_feeds function includes fallback detection logic."""
    import inspect
    from src.ingestion.scheduler import refresh_cobalt_feeds
    source = inspect.getsource(refresh_cobalt_feeds)
    assert "COBALT FALLBACK ALERT" in source, "Missing fallback alert message"
    assert "fallbacks.append" in source or "fallbacks +" in source, "Missing fallback tracking"
