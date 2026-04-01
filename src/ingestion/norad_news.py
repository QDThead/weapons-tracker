"""NORAD Press Releases scraper.

Scrapes press releases from norad.mil/Newsroom/Press-Releases/.
Covers Arctic intercepts, Russian/Chinese activity, joint exercises.
Freshness: days. Auth: none required.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

NORAD_PRESS_URL = "https://www.norad.mil/Newsroom/Press-Releases/"
NORAD_BASE = "https://www.norad.mil"

ARCTIC_TAGS = [
    "arctic", "russian", "china", "chinese", "intercept", "adiz",
    "norad region", "alaskan", "canadian", "north american",
    "aerospace warning", "bomber", "tu-95", "tu-160", "h-6",
    "bear", "backfire", "badger", "exercise", "vigilant",
    "noble defender", "arctic edge",
]

_WHITESPACE_RE = re.compile(r"\s+")


@dataclass
class NORADPressRelease:
    """A NORAD press release."""

    title: str
    url: str
    published_at: str | None
    summary: str
    is_arctic_related: bool

    def to_dict(self) -> dict:
        return asdict(self)


class NORADNewsClient:
    """Async client for NORAD press releases."""

    def __init__(self, timeout: float = 25.0):
        self.timeout = timeout

    async def fetch_press_releases(self, max_items: int = 30) -> list[NORADPressRelease]:
        """Scrape recent NORAD press releases.

        Returns:
            List of press releases sorted by date (newest first).
        """
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "WeaponsTracker/1.0 (OSINT research)"},
        ) as client:
            try:
                response = await client.get(NORAD_PRESS_URL)
                response.raise_for_status()
            except Exception as e:
                logger.error("NORAD press releases fetch failed: %s", e)
                return []

        html = response.text
        releases = self._parse_press_releases(html)
        releases = releases[:max_items]
        logger.info("NORAD: scraped %d press releases", len(releases))
        return releases

    def _parse_press_releases(self, html: str) -> list[NORADPressRelease]:
        """Parse press release listing from HTML without an HTML parser dependency."""
        results: list[NORADPressRelease] = []

        listing_pattern = re.compile(
            r'<a[^>]*href="(/Newsroom/(?:Press-Releases|Article)/[^"]+)"[^>]*>'
            r'\s*<span[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</span>',
            re.DOTALL | re.IGNORECASE,
        )

        date_pattern = re.compile(
            r'<time[^>]*datetime="([^"]*)"[^>]*>|'
            r'<span[^>]*class="[^"]*date[^"]*"[^>]*>(.*?)</span>',
            re.IGNORECASE,
        )

        summary_pattern = re.compile(
            r'<span[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</span>|'
            r'<p[^>]*class="[^"]*summary[^"]*"[^>]*>(.*?)</p>',
            re.DOTALL | re.IGNORECASE,
        )

        link_blocks = re.split(r'(?=<a[^>]*href="/Newsroom/)', html)

        for block in link_blocks:
            link_match = listing_pattern.search(block)
            if not link_match:
                continue

            href = link_match.group(1)
            title = re.sub(r"<[^>]+>", "", link_match.group(2)).strip()
            title = _WHITESPACE_RE.sub(" ", title)

            if not title:
                continue

            url = NORAD_BASE + href if not href.startswith("http") else href

            published: str | None = None
            date_match = date_pattern.search(block)
            if date_match:
                raw = (date_match.group(1) or date_match.group(2) or "").strip()
                published = self._normalize_date(raw)

            summary = ""
            summ_match = summary_pattern.search(block)
            if summ_match:
                raw_summ = (summ_match.group(1) or summ_match.group(2) or "").strip()
                summary = re.sub(r"<[^>]+>", "", raw_summ)[:500]

            is_arctic = self._is_arctic_related(title, summary)

            results.append(NORADPressRelease(
                title=title,
                url=url,
                published_at=published,
                summary=summary,
                is_arctic_related=is_arctic,
            ))

        results.sort(key=lambda r: r.published_at or "", reverse=True)
        return results

    @staticmethod
    def _normalize_date(raw: str) -> str | None:
        if not raw:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(raw.split(".")[0].split("+")[0], fmt).isoformat()
            except ValueError:
                continue
        return raw

    @staticmethod
    def _is_arctic_related(title: str, summary: str) -> bool:
        text = f"{title} {summary}".lower()
        return any(tag in text for tag in ARCTIC_TAGS)
