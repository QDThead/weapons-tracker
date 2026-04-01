"""NATO News RSS connector.

Fetches the latest news from NATO's official RSS feed.
Freshness: hours. Auth: none required.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

NATO_RSS_URL = "https://www.nato.int/cps/rss/en/natohq/rssFeed.xsl/rssFeed.xml"

_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class NATONewsArticle:
    """A single NATO news article."""

    title: str
    url: str
    published_at: str | None
    summary: str
    category: str | None

    def to_dict(self) -> dict:
        return asdict(self)


class NATONewsClient:
    """Async client for the NATO news RSS feed."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch_latest(self, max_articles: int = 50) -> list[NATONewsArticle]:
        """Fetch latest NATO news articles.

        Returns:
            List of articles sorted by published date (newest first).
        """
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(NATO_RSS_URL)
                response.raise_for_status()
            except Exception as e:
                logger.error("NATO RSS fetch failed: %s", e)
                return []

        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as e:
            logger.error("NATO RSS parse failed: %s", e)
            return []

        articles: list[NATONewsArticle] = []

        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue

            pub_str = item.findtext("pubDate") or ""
            published: str | None = None
            if pub_str:
                try:
                    dt = parsedate_to_datetime(pub_str.strip())
                    published = dt.isoformat()
                except Exception:
                    published = pub_str.strip()

            summary_raw = (item.findtext("description") or "").strip()
            summary = _HTML_TAG_RE.sub("", summary_raw)[:500]

            category = (item.findtext("category") or "").strip() or None

            articles.append(NATONewsArticle(
                title=title,
                url=link,
                published_at=published,
                summary=summary,
                category=category,
            ))

        articles.sort(key=lambda a: a.published_at or "", reverse=True)
        articles = articles[:max_articles]
        logger.info("NATO News: fetched %d articles", len(articles))
        return articles
