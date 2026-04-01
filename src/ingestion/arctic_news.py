"""Arctic OSINT News aggregator.

Aggregates RSS feeds from Arctic-focused news outlets:
  - High North News (Norway) — Arctic geopolitics, security, policy
  - Arctic Today (USA) — pan-Arctic news and analysis
  - The Barents Observer (Norway) — Russia/Arctic relations, Northern Fleet

Freshness: hours/daily. Auth: none required.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from email.utils import parsedate_to_datetime

import httpx

logger = logging.getLogger(__name__)

ARCTIC_RSS_FEEDS: dict[str, str] = {
    "High North News": "https://www.highnorthnews.com/en/rss.xml",
    "Arctic Today": "https://www.arctictoday.com/feed/",
    "Barents Observer": "https://thebarentsobserver.com/en/rss.xml",
}

SECURITY_KEYWORDS = [
    "military", "security", "defense", "defence", "nato", "russia",
    "china", "arctic", "northern fleet", "icebreaker", "submarine",
    "bomber", "intercept", "sovereignty", "border", "missile",
    "nuclear", "base", "exercise", "norad", "saami", "indigenous",
    "shipping", "nsr", "northern sea route", "northwest passage",
    "oil", "gas", "mineral", "rare earth", "climate", "ice",
    "svalbard", "greenland", "alaska", "nunavut", "yukon",
    "murmansk", "severomorsk", "kola", "norway", "canada",
    "coast guard", "patrol", "surveillance", "radar",
]

_HTML_TAG_RE = re.compile(r"<[^>]+>")

ATOM_NS = "{http://www.w3.org/2005/Atom}"


@dataclass
class ArcticNewsArticle:
    """A single Arctic news article."""

    title: str
    url: str
    source: str
    published_at: str | None
    summary: str
    is_security_related: bool

    def to_dict(self) -> dict:
        return asdict(self)


class ArcticNewsClient:
    """Async client for Arctic OSINT news feeds."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def fetch_all(
        self, filter_security: bool = False, max_articles: int = 60
    ) -> list[ArcticNewsArticle]:
        """Fetch articles from all Arctic RSS feeds, deduplicated by URL.

        Args:
            filter_security: If True, keep only security/geopolitics articles.
            max_articles: Maximum number of articles to return.

        Returns:
            Deduplicated list sorted by published date (newest first).
        """
        seen_urls: dict[str, ArcticNewsArticle] = {}

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for source_name, url in ARCTIC_RSS_FEEDS.items():
                try:
                    articles = await self._fetch_feed(client, source_name, url)
                    for article in articles:
                        if article.url not in seen_urls:
                            seen_urls[article.url] = article
                    logger.info("Arctic [%s]: %d articles", source_name, len(articles))
                except Exception as e:
                    logger.warning("Arctic feed failed for %s: %s", source_name, e)

        results = list(seen_urls.values())

        if filter_security:
            results = [a for a in results if a.is_security_related]

        results.sort(key=lambda a: a.published_at or "", reverse=True)
        results = results[:max_articles]
        logger.info(
            "Arctic News total: %d unique, returning %d",
            len(seen_urls),
            len(results),
        )
        return results

    async def _fetch_feed(
        self, client: httpx.AsyncClient, source_name: str, url: str
    ) -> list[ArcticNewsArticle]:
        """Fetch and parse a single RSS or Atom feed."""
        response = await client.get(url)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        articles: list[ArcticNewsArticle] = []

        rss_items = root.findall(".//item")
        if rss_items:
            articles = self._parse_rss(rss_items, source_name)
        else:
            atom_entries = root.findall(f"{ATOM_NS}entry")
            if atom_entries:
                articles = self._parse_atom(atom_entries, source_name)

        return articles

    def _parse_rss(
        self, items: list[ET.Element], source_name: str
    ) -> list[ArcticNewsArticle]:
        results: list[ArcticNewsArticle] = []
        for item in items:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue

            published: str | None = None
            pub_str = item.findtext("pubDate") or ""
            if pub_str:
                try:
                    published = parsedate_to_datetime(pub_str.strip()).isoformat()
                except Exception:
                    published = pub_str.strip()

            summary = self._clean_summary(
                item.findtext("description") or ""
            )

            is_sec = self._is_security_related(title, summary)

            results.append(ArcticNewsArticle(
                title=title,
                url=link,
                source=source_name,
                published_at=published,
                summary=summary,
                is_security_related=is_sec,
            ))
        return results

    def _parse_atom(
        self, entries: list[ET.Element], source_name: str
    ) -> list[ArcticNewsArticle]:
        results: list[ArcticNewsArticle] = []
        for entry in entries:
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip()
            link_el = entry.find(f"{ATOM_NS}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{ATOM_NS}link")
            link = (link_el.get("href", "") if link_el is not None else "").strip()
            if not title or not link:
                continue

            published = (
                entry.findtext(f"{ATOM_NS}published")
                or entry.findtext(f"{ATOM_NS}updated")
                or ""
            ).strip() or None

            summary = self._clean_summary(
                entry.findtext(f"{ATOM_NS}summary")
                or entry.findtext(f"{ATOM_NS}content")
                or ""
            )

            is_sec = self._is_security_related(title, summary)

            results.append(ArcticNewsArticle(
                title=title,
                url=link,
                source=source_name,
                published_at=published,
                summary=summary,
                is_security_related=is_sec,
            ))
        return results

    @staticmethod
    def _clean_summary(raw: str) -> str:
        text = _HTML_TAG_RE.sub("", raw.strip())
        return text[:500]

    @staticmethod
    def _is_security_related(title: str, summary: str) -> bool:
        text = f"{title} {summary}".lower()
        return any(kw in text for kw in SECURITY_KEYWORDS)
