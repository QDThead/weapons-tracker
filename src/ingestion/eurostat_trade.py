"""Eurostat Comext SDMX connector for EU arms trade data.

Fetches monthly EU arms trade data (HS Chapter 93 — Arms & Ammunition)
from the Eurostat Comext dissemination API (SDMX-CSV format).
Covers all 27 EU member states with monthly granularity.

Values are in EUR. No authentication required.

Reference: https://ec.europa.eu/eurostat/web/international-trade-in-goods/overview
Dataset: DS-045409 (EU trade since 1988 by HS2-HS4)
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

COMEXT_SDMX_BASE = (
    "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1"
    "/data/DS-045409"
)

# Top EU arms-exporting countries (ISO 2-letter codes used by Comext)
DEFAULT_REPORTERS = ["DE", "FR", "IT", "ES", "NL", "SE"]

# All EU reporters available for broader queries
ALL_EU_REPORTERS = [
    "DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE", "CZ", "FI",
    "AT", "GR", "RO", "BG", "PT", "HU", "DK",
]

# Flow codes
FLOW_EXPORT = "2"
FLOW_IMPORT = "1"

# HS Chapter 93 — Arms and Ammunition
HS_CHAPTER_93 = "93"


@dataclass
class EurostatTradeRecord:
    """A single Eurostat monthly arms trade record."""
    reporter: str           # ISO 2-letter country code
    partner: str            # Partner country/region code
    year: int
    month: int
    value_eur: float        # Trade value in EUR
    direction: str          # "export" or "import"


class EurostatTradeClient:
    """Client for the Eurostat Comext SDMX API (DS-045409 dataset).

    Fetches monthly EU arms trade data at HS Chapter 93 level,
    returning SDMX-CSV responses parsed into EurostatTradeRecord objects.
    """

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    def _build_url(
        self,
        reporters: list[str],
        partners: list[str] | None,
        flow: str,
        start_period: str,
        end_period: str,
    ) -> str:
        """Build the SDMX-CSV request URL.

        Args:
            reporters: List of ISO 2-letter reporter codes.
            partners: List of partner codes, or None for WORLD.
            flow: "1" (import) or "2" (export).
            start_period: Start month "YYYY-MM".
            end_period: End month "YYYY-MM".

        Returns:
            Full URL string.
        """
        reporter_str = "+".join(reporters)
        partner_str = "+".join(partners) if partners else "WORLD"

        path = f"/M.{reporter_str}.{partner_str}.{HS_CHAPTER_93}.{flow}.VALUE_IN_EUROS"
        params = f"?startPeriod={start_period}&endPeriod={end_period}&format=SDMX-CSV"

        return COMEXT_SDMX_BASE + path + params

    def _default_period(self) -> tuple[str, str]:
        """Return (start, end) period strings for the last 12 months."""
        now = datetime.now()
        end = now.replace(day=1)
        start = end - timedelta(days=365)
        return start.strftime("%Y-%m"), end.strftime("%Y-%m")

    def _parse_sdmx_csv(
        self, text: str, direction: str
    ) -> list[EurostatTradeRecord]:
        """Parse the SDMX-CSV response body into records.

        Expected columns: DATAFLOW, LAST UPDATE, freq, reporter, partner,
        product, flow, indicators, TIME_PERIOD, OBS_VALUE

        Args:
            text: Raw CSV text from the API.
            direction: "export" or "import".

        Returns:
            List of EurostatTradeRecord.
        """
        records: list[EurostatTradeRecord] = []
        reader = csv.DictReader(io.StringIO(text))

        for row in reader:
            try:
                obs_value = row.get("OBS_VALUE", "").strip()
                if not obs_value:
                    continue

                value_eur = float(obs_value)
                if value_eur <= 0:
                    continue

                time_period = row.get("TIME_PERIOD", "").strip()
                if "-" in time_period:
                    parts = time_period.split("-")
                    year = int(parts[0])
                    month = int(parts[1])
                else:
                    # Some formats may use YYYY-MM or YYYYMM
                    year = int(time_period[:4])
                    month = int(time_period[4:6]) if len(time_period) >= 6 else 1

                reporter = row.get("reporter", row.get("REPORTER", "")).strip()
                partner = row.get("partner", row.get("PARTNER", "")).strip()

                records.append(EurostatTradeRecord(
                    reporter=reporter,
                    partner=partner,
                    year=year,
                    month=month,
                    value_eur=value_eur,
                    direction=direction,
                ))
            except (ValueError, KeyError) as e:
                logger.debug("Skipping malformed row: %s (%s)", row, e)
                continue

        return records

    async def fetch_eu_arms_exports(
        self,
        reporters: list[str] | None = None,
        partners: list[str] | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> list[EurostatTradeRecord]:
        """Fetch monthly EU arms export data (HS 93).

        Args:
            reporters: ISO 2-letter codes for reporting countries.
                       Defaults to top 6 EU exporters.
            partners: Partner country codes (e.g. ["US", "SA"]).
                      Defaults to WORLD (all partners combined).
            start_period: Start month "YYYY-MM". Defaults to 12 months ago.
            end_period: End month "YYYY-MM". Defaults to current month.

        Returns:
            List of EurostatTradeRecord for exports.
        """
        if not reporters:
            reporters = DEFAULT_REPORTERS
        if not start_period or not end_period:
            start_period, end_period = self._default_period()

        url = self._build_url(reporters, partners, FLOW_EXPORT, start_period, end_period)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching Eurostat exports: reporters=%s, period=%s to %s",
                reporters, start_period, end_period,
            )
            response = await client.get(url)
            response.raise_for_status()

        records = self._parse_sdmx_csv(response.text, "export")
        logger.info("Parsed %d Eurostat export records", len(records))
        return records

    async def fetch_eu_arms_imports(
        self,
        reporters: list[str] | None = None,
        partners: list[str] | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> list[EurostatTradeRecord]:
        """Fetch monthly EU arms import data (HS 93).

        Args:
            reporters: ISO 2-letter codes for reporting countries.
                       Defaults to top 6 EU exporters.
            partners: Partner country codes. Defaults to WORLD.
            start_period: Start month "YYYY-MM". Defaults to 12 months ago.
            end_period: End month "YYYY-MM". Defaults to current month.

        Returns:
            List of EurostatTradeRecord for imports.
        """
        if not reporters:
            reporters = DEFAULT_REPORTERS
        if not start_period or not end_period:
            start_period, end_period = self._default_period()

        url = self._build_url(reporters, partners, FLOW_IMPORT, start_period, end_period)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching Eurostat imports: reporters=%s, period=%s to %s",
                reporters, start_period, end_period,
            )
            response = await client.get(url)
            response.raise_for_status()

        records = self._parse_sdmx_csv(response.text, "import")
        logger.info("Parsed %d Eurostat import records", len(records))
        return records

    async def fetch_eu_arms_trade(
        self,
        reporters: list[str] | None = None,
        partners: list[str] | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
    ) -> list[EurostatTradeRecord]:
        """Fetch both exports and imports in a single call.

        Returns:
            Combined list of EurostatTradeRecord (exports + imports).
        """
        exports = await self.fetch_eu_arms_exports(
            reporters, partners, start_period, end_period,
        )
        imports = await self.fetch_eu_arms_imports(
            reporters, partners, start_period, end_period,
        )
        return exports + imports
