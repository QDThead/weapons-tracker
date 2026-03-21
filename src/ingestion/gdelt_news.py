"""GDELT arms trade news monitor.

Uses the GDELT DOC 2.0 API to find news articles about arms deals,
weapons deliveries, and defense procurement worldwide.
Updates every 15 minutes. Free, no auth required.

Reference: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Search queries tuned for arms trade coverage
ARMS_TRADE_QUERIES = [
    '("arms deal" OR "arms sale" OR "weapons sale" OR "defense contract")',
    '("weapons delivery" OR "arms delivery" OR "military equipment delivery")',
    '("defense procurement" OR "military procurement" OR "arms procurement")',
    '("fighter jet deal" OR "tank deal" OR "missile deal" OR "submarine deal")',
    '("arms embargo" OR "weapons embargo" OR "arms sanctions")',
    '("arms export" OR "arms import" OR "weapons transfer")',
]


@dataclass
class ArmsNewsArticle:
    """A news article related to arms trade."""
    title: str
    url: str
    source: str
    source_country: str
    language: str
    published_at: datetime | None
    tone: float | None
    image_url: str | None


class GDELTArmsNewsClient:
    """Client for monitoring arms trade news via GDELT DOC 2.0 API."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def search_articles(
        self,
        query: str,
        mode: str = "ArtList",
        max_records: int = 75,
        timespan: str = "1440",  # minutes (24 hours)
        source_country: str | None = None,
        source_lang: str | None = None,
        sort: str = "DateDesc",
    ) -> list[ArmsNewsArticle]:
        """Search GDELT for news articles matching a query.

        Args:
            query: Search query string.
            mode: "ArtList" for article list, "TimelineVol" for volume timeline.
            max_records: Max articles to return (max 250).
            timespan: Time window in minutes to search.
            source_country: Filter by source country (FIPS code, e.g., "CA" for Canada).
            source_lang: Filter by language (e.g., "English").
            sort: Sort order — "DateDesc", "DateAsc", "ToneDesc", "ToneAsc".

        Returns:
            List of ArmsNewsArticle.
        """
        params = {
            "query": query,
            "mode": mode,
            "maxrecords": max_records,
            "timespan": f"{timespan}min",
            "format": "json",
            "sort": sort,
        }

        if source_country:
            params["sourcecountry"] = source_country
        if source_lang:
            params["sourcelang"] = source_lang

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Searching GDELT: %s", query[:80])
            response = await client.get(GDELT_DOC_API, params=params)
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if not response.content or "application/json" not in content_type:
            logger.warning("GDELT returned non-JSON response: %s", response.content[:200])
            return []

        data = response.json()
        articles = data.get("articles", [])

        results = []
        for article in articles:
            published = None
            if article.get("seendate"):
                try:
                    published = datetime.strptime(article["seendate"], "%Y%m%dT%H%M%SZ")
                except ValueError:
                    pass

            results.append(ArmsNewsArticle(
                title=article.get("title", ""),
                url=article.get("url", ""),
                source=article.get("domain", ""),
                source_country=article.get("sourcecountry", ""),
                language=article.get("language", ""),
                published_at=published,
                tone=self._safe_float(article.get("tone")),
                image_url=article.get("socialimage"),
            ))

        logger.info("Found %d articles for query: %s", len(results), query[:50])
        return results

    async def fetch_latest_arms_news(
        self, timespan_minutes: int = 1440, max_per_query: int = 50
    ) -> list[ArmsNewsArticle]:
        """Fetch latest arms trade news across all predefined queries.

        Args:
            timespan_minutes: How far back to look (default 24 hours).
            max_per_query: Max articles per query.

        Returns:
            Deduplicated list of articles sorted by date.
        """
        all_articles: dict[str, ArmsNewsArticle] = {}

        for i, query in enumerate(ARMS_TRADE_QUERIES):
            # GDELT enforces a 5-second rate limit between requests
            if i > 0:
                await asyncio.sleep(5)
            try:
                articles = await self.search_articles(
                    query=query,
                    timespan=str(timespan_minutes),
                    max_records=max_per_query,
                )
                for article in articles:
                    if article.url not in all_articles:
                        all_articles[article.url] = article
            except Exception as e:
                logger.warning("GDELT query failed for '%s': %s", query[:40], e)

        results = list(all_articles.values())
        results.sort(key=lambda a: a.published_at or datetime.min, reverse=True)
        logger.info("Total unique arms trade articles: %d", len(results))
        return results

    async def search_country_arms_news(
        self, country_name: str, timespan_minutes: int = 4320
    ) -> list[ArmsNewsArticle]:
        """Search for arms trade news mentioning a specific country.

        Args:
            country_name: Country to search for (e.g., "Canada").
            timespan_minutes: How far back (default 72 hours).
        """
        query = f'("{country_name}" AND ("arms" OR "weapons" OR "defense" OR "military")) AND ("sale" OR "deal" OR "delivery" OR "contract" OR "export" OR "import")'
        return await self.search_articles(
            query=query,
            timespan=str(timespan_minutes),
            max_records=100,
        )

    @staticmethod
    def _safe_float(value) -> float | None:
        try:
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None
