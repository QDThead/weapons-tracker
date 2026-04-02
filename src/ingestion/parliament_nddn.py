"""Parliament of Canada — NDDN (Standing Committee on National Defence) scraper.

Scrapes the House of Commons NDDN committee page for:
  - Upcoming and recent meeting notices
  - Current study topics
  - Key witness appearances

Source: ourcommons.ca/Committees/en/nddn
Freshness: weekly (when Parliament is in session). Auth: none required.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, asdict
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

NDDN_URL = "https://www.ourcommons.ca/Committees/en/nddn"
NDDN_MEETINGS_URL = "https://www.ourcommons.ca/Committees/en/nddn/Meetings"
NDDN_STUDIES_URL = "https://www.ourcommons.ca/Committees/en/nddn/StudyActivity"

_WHITESPACE_RE = re.compile(r"\s+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class NDDNActivity:
    """A single NDDN committee activity (meeting, study, or notice)."""

    activity_type: str
    title: str
    url: str | None
    date: str | None
    details: str

    def to_dict(self) -> dict:
        return asdict(self)


class ParliamentNDDNClient:
    """Async client for NDDN committee activity."""

    def __init__(self, timeout: float = 25.0):
        self.timeout = timeout

    async def fetch_activities(self) -> list[NDDNActivity]:
        """Fetch NDDN committee activities from multiple pages.

        Returns:
            Combined list of meetings, studies, and notices.
        """
        activities: list[NDDNActivity] = []

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "WeaponsTracker/1.0 (OSINT research)"},
        ) as client:
            main_activities = await self._fetch_main_page(client)
            activities.extend(main_activities)

            meeting_activities = await self._fetch_meetings(client)
            activities.extend(meeting_activities)

            study_activities = await self._fetch_studies(client)
            activities.extend(study_activities)

        seen_titles: set[str] = set()
        deduped: list[NDDNActivity] = []
        for a in activities:
            key = a.title.lower().strip()
            if key not in seen_titles:
                seen_titles.add(key)
                deduped.append(a)

        deduped.sort(key=lambda a: a.date or "", reverse=True)
        logger.info("NDDN: fetched %d activities", len(deduped))
        return deduped

    async def _fetch_main_page(self, client: httpx.AsyncClient) -> list[NDDNActivity]:
        """Parse the main NDDN committee page for recent activity."""
        try:
            response = await client.get(NDDN_URL)
            response.raise_for_status()
        except Exception as e:
            logger.warning("NDDN main page fetch failed: %s", e)
            return []

        return self._parse_generic_page(response.text, "notice")

    async def _fetch_meetings(self, client: httpx.AsyncClient) -> list[NDDNActivity]:
        """Parse NDDN meetings page."""
        try:
            response = await client.get(NDDN_MEETINGS_URL)
            response.raise_for_status()
        except Exception as e:
            logger.warning("NDDN meetings page fetch failed: %s", e)
            return []

        return self._parse_meetings_html(response.text)

    async def _fetch_studies(self, client: httpx.AsyncClient) -> list[NDDNActivity]:
        """Parse NDDN studies page."""
        try:
            response = await client.get(NDDN_STUDIES_URL)
            response.raise_for_status()
        except Exception as e:
            logger.warning("NDDN studies page fetch failed: %s", e)
            return []

        return self._parse_studies_html(response.text)

    def _parse_generic_page(self, html: str, activity_type: str) -> list[NDDNActivity]:
        """Extract activities from generic NDDN page HTML."""
        activities: list[NDDNActivity] = []

        link_pattern = re.compile(
            r'<a[^>]*href="(/Committees/en/nddn[^"]*)"[^>]*>(.*?)</a>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in link_pattern.finditer(html):
            href = match.group(1)
            raw_title = _HTML_TAG_RE.sub("", match.group(2)).strip()
            title = _WHITESPACE_RE.sub(" ", raw_title)

            if not title or len(title) < 10:
                continue
            if any(skip in title.lower() for skip in ["home", "committee", "français", "menu"]):
                continue

            url = f"https://www.ourcommons.ca{href}"

            date = self._extract_date_from_text(title)

            activities.append(NDDNActivity(
                activity_type=activity_type,
                title=title,
                url=url,
                date=date,
                details="",
            ))

        return activities[:20]

    def _parse_meetings_html(self, html: str) -> list[NDDNActivity]:
        """Extract meeting entries from the meetings page."""
        activities: list[NDDNActivity] = []

        meeting_pattern = re.compile(
            r'<h\d[^>]*>(.*?)</h\d>.*?'
            r'(?:<time[^>]*datetime="([^"]*)"[^>]*>|'
            r'<span[^>]*class="[^"]*date[^"]*"[^>]*>(.*?)</span>)',
            re.DOTALL | re.IGNORECASE,
        )

        blocks = re.split(r'(?=<div[^>]*class="[^"]*meeting)', html, flags=re.IGNORECASE)

        for block in blocks[:20]:
            title_match = re.search(r'<h\d[^>]*>(.*?)</h\d>', block, re.DOTALL | re.IGNORECASE)
            if not title_match:
                continue

            title = _HTML_TAG_RE.sub("", title_match.group(1)).strip()
            title = _WHITESPACE_RE.sub(" ", title)
            if not title or len(title) < 5:
                continue

            date: str | None = None
            date_match = re.search(
                r'<time[^>]*datetime="([^"]*)"', block, re.IGNORECASE
            )
            if date_match:
                date = date_match.group(1).split("T")[0]
            else:
                date = self._extract_date_from_text(block)

            link_match = re.search(
                r'<a[^>]*href="(/Committees/en/nddn[^"]*)"', block, re.IGNORECASE
            )
            url = (
                f"https://www.ourcommons.ca{link_match.group(1)}"
                if link_match
                else None
            )

            details = ""
            desc_match = re.search(
                r'<p[^>]*>(.*?)</p>', block, re.DOTALL | re.IGNORECASE
            )
            if desc_match:
                details = _HTML_TAG_RE.sub("", desc_match.group(1)).strip()[:300]

            activities.append(NDDNActivity(
                activity_type="meeting",
                title=title,
                url=url,
                date=date,
                details=details,
            ))

        return activities

    def _parse_studies_html(self, html: str) -> list[NDDNActivity]:
        """Extract study topics from the studies page."""
        activities: list[NDDNActivity] = []

        blocks = re.split(r'(?=<div[^>]*class="[^"]*study)', html, flags=re.IGNORECASE)
        if len(blocks) <= 1:
            blocks = re.split(r'(?=<li[^>]*>)', html, flags=re.IGNORECASE)

        for block in blocks[:15]:
            link_match = re.search(
                r'<a[^>]*href="(/Committees/en/nddn/StudyActivity[^"]*)"[^>]*>(.*?)</a>',
                block,
                re.DOTALL | re.IGNORECASE,
            )
            if not link_match:
                continue

            title = _HTML_TAG_RE.sub("", link_match.group(2)).strip()
            title = _WHITESPACE_RE.sub(" ", title)
            if not title or len(title) < 10:
                continue

            url = f"https://www.ourcommons.ca{link_match.group(1)}"

            activities.append(NDDNActivity(
                activity_type="study",
                title=title,
                url=url,
                date=None,
                details="Active study by the Standing Committee on National Defence",
            ))

        return activities

    @staticmethod
    def _extract_date_from_text(text: str) -> str | None:
        date_match = re.search(
            r'(\d{4}-\d{2}-\d{2})|'
            r'((?:January|February|March|April|May|June|July|August|'
            r'September|October|November|December)\s+\d{1,2},?\s+\d{4})',
            text,
            re.IGNORECASE,
        )
        if date_match:
            raw = date_match.group(1) or date_match.group(2)
            if raw and "-" in raw:
                return raw
            for fmt in ("%B %d, %Y", "%B %d %Y"):
                try:
                    return datetime.strptime(raw.strip().replace(",", ","), fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
        return None
