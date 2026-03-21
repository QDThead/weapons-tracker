"""Defense news RSS feed aggregator.

Monitors major defense publications for breaking news about arms deals,
deliveries, military procurement, and defense industry developments.
Updates every 15 minutes. Free, no auth required.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

# Defense publication RSS feeds (verified working March 2026)
DEFENSE_FEEDS = {
    "Defense News": "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    "The War Zone": "https://www.twz.com/feed",
    "Army Technology": "https://www.army-technology.com/feed/",
    "The Aviationist": "https://theaviationist.com/feed/",
}

# Keywords that indicate arms trade relevance (filter out general military news)
ARMS_KEYWORDS = [
    "arms", "weapon", "missile", "deal", "sale", "contract", "procurement",
    "delivery", "export", "import", "billion", "million", "f-35", "f-16",
    "tank", "frigate", "submarine", "helicopter", "drone", "uav",
    "defense contract", "military aid", "ammunition", "artillery",
    "patriot", "himars", "javelin", "stinger", "leopard", "abrams",
    "rafale", "typhoon", "gripen", "supply", "order", "acquisition",
    "lav", "fighter", "bomber", "warship", "corvette", "radar",
    "air defense", "air defence", "s-400", "iron dome", "thaad",
    "nato", "pentagon", "lockheed", "raytheon", "bae", "rheinmetall",
    "boeing", "northrop", "general dynamics", "leonardo", "thales",
    "saab", "dassault", "airbus defence", "colt canada",
    "sanctions", "embargo", "arms race", "rearm",
]


@dataclass
class DefenseNewsArticle:
    """A defense news article from an RSS feed."""
    title: str
    url: str
    source: str
    published_at: datetime | None
    summary: str


class DefenseNewsRSSClient:
    """Client for aggregating defense news from RSS feeds."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_all_feeds(self, filter_arms: bool = True) -> list[DefenseNewsArticle]:
        """Fetch articles from all defense RSS feeds.

        Args:
            filter_arms: If True, only return articles with arms-trade-relevant keywords.

        Returns:
            Deduplicated list of articles sorted by date.
        """
        all_articles: dict[str, DefenseNewsArticle] = {}

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for source_name, url in DEFENSE_FEEDS.items():
                try:
                    articles = await self._fetch_feed(client, source_name, url)
                    for article in articles:
                        if article.url not in all_articles:
                            all_articles[article.url] = article
                    logger.info("RSS: %s — %d articles", source_name, len(articles))
                except Exception as e:
                    logger.warning("RSS feed failed for %s: %s", source_name, e)

        results = list(all_articles.values())

        if filter_arms:
            results = [a for a in results if self._is_arms_relevant(a)]

        results.sort(key=lambda a: a.published_at or datetime.min, reverse=True)
        logger.info("RSS total: %d articles (%d after filtering)", len(all_articles), len(results))
        return results

    async def _fetch_feed(
        self, client: httpx.AsyncClient, source_name: str, url: str
    ) -> list[DefenseNewsArticle]:
        """Fetch and parse a single RSS feed."""
        response = await client.get(url)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles = []

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue

            published = None
            pub_str = item.findtext("pubDate") or ""
            if pub_str:
                try:
                    published = parsedate_to_datetime(pub_str)
                except Exception:
                    pass

            summary = (item.findtext("description") or "").strip()
            # Strip HTML tags from summary
            if "<" in summary:
                import re
                summary = re.sub(r"<[^>]+>", "", summary)
            summary = summary[:500]

            articles.append(DefenseNewsArticle(
                title=title,
                url=link,
                source=source_name,
                published_at=published,
                summary=summary,
            ))

        return articles

    @staticmethod
    def _is_arms_relevant(article: DefenseNewsArticle) -> bool:
        """Check if an article is relevant to arms trade/defense procurement."""
        text = f"{article.title} {article.summary}".lower()
        return any(kw in text for kw in ARMS_KEYWORDS)
