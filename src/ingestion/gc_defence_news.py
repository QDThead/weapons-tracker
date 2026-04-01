"""Government of Canada Defence News connector.

Fetches official press releases and news from 4 Canada.ca Atom feeds:
  - Department of National Defence (DND/CAF)
  - Global Affairs Canada (GAC)
  - Defence & Security topic feed
  - Public Safety Canada

Uses the official GC News API at api.io.canada.ca (Atom format).
Freshness: hours (same-day press releases). Auth: none required.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

ATOM_NS = "{http://www.w3.org/2005/Atom}"

GC_NEWS_FEEDS: dict[str, str] = {
    "DND": (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?dept=departmentnationaldefense"
        "&sort=publishedDate&orderBy=desc&pick=50&format=atom"
    ),
    "GAC": (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?dept=departmentofforeignaffairstradeanddevelopment"
        "&sort=publishedDate&orderBy=desc&pick=50&format=atom"
    ),
    "Defence & Security": (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?topic=nationalsecurityanddefence"
        "&sort=publishedDate&orderBy=desc&pick=50&format=atom"
    ),
    "Public Safety": (
        "https://api.io.canada.ca/io-server/gc/news/en/v2"
        "?dept=publicsafetycanada"
        "&sort=publishedDate&orderBy=desc&pick=50&format=atom"
    ),
}

DEFENCE_KEYWORDS = [
    "defence", "defense", "military", "armed forces", "caf",
    "norad", "nato", "arctic", "sovereignty", "procurement",
    "fighter", "frigate", "submarine", "shipbuilding",
    "cybersecurity", "intelligence", "threat", "sanctions",
    "russia", "china", "iran", "north korea", "weapons",
    "ammunition", "missile", "drone", "uav", "rcaf", "rcn",
    "special operations", "deployment", "exercise",
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class GCNewsArticle:
    """A single news article from a Government of Canada feed."""

    title: str
    url: str
    department: str
    published_at: str | None
    summary: str

    def to_dict(self) -> dict:
        return asdict(self)


class GCDefenceNewsClient:
    """Async client for Government of Canada defence news feeds."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch_all(self, filter_defence: bool = True) -> list[GCNewsArticle]:
        """Fetch articles from all 4 GC news feeds, deduplicated by URL.

        Args:
            filter_defence: If True, keep only defence/security-relevant articles.

        Returns:
            List of articles sorted by published date (newest first).
        """
        seen_urls: dict[str, GCNewsArticle] = {}

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for dept, url in GC_NEWS_FEEDS.items():
                try:
                    articles = await self._fetch_feed(client, dept, url)
                    for article in articles:
                        if article.url not in seen_urls:
                            seen_urls[article.url] = article
                    logger.info("GC News [%s]: %d articles", dept, len(articles))
                except Exception as e:
                    logger.warning("GC News feed failed for %s: %s", dept, e)

        results = list(seen_urls.values())

        if filter_defence:
            results = [a for a in results if self._is_defence_relevant(a)]

        results.sort(key=lambda a: a.published_at or "", reverse=True)
        logger.info(
            "GC Defence News total: %d unique (%d after filtering)",
            len(seen_urls),
            len(results),
        )
        return results

    async def _fetch_feed(
        self, client: httpx.AsyncClient, dept: str, url: str
    ) -> list[GCNewsArticle]:
        """Fetch and parse a single Atom feed."""
        response = await client.get(url)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles: list[GCNewsArticle] = []

        for entry in root.findall(f"{ATOM_NS}entry"):
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
            link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{ATOM_NS}link")
            link = (link_el.get("href", "") if link_el is not None else "").strip()

            if not title or not link:
                continue

            published = (entry.findtext(f"{ATOM_NS}published") or
                         entry.findtext(f"{ATOM_NS}updated") or "").strip()

            summary_raw = (entry.findtext(f"{ATOM_NS}summary") or
                           entry.findtext(f"{ATOM_NS}content") or "").strip()
            summary = _HTML_TAG_RE.sub("", summary_raw)[:500]

            articles.append(GCNewsArticle(
                title=title,
                url=link,
                department=dept,
                published_at=published or None,
                summary=summary,
            ))

        return articles

    @staticmethod
    def _is_defence_relevant(article: GCNewsArticle) -> bool:
        text = f"{article.title} {article.summary}".lower()
        return any(kw in text for kw in DEFENCE_KEYWORDS)
