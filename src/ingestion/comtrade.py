"""UN Comtrade arms trade data connector.

Fetches actual USD trade values for arms and ammunition (HS Chapter 93)
from the UN Comtrade API. Complements SIPRI TIV data with real financial values.

Free preview endpoint: max 500 records, no auth required.
Authenticated endpoint: max 100K records, free registration.

Reference: https://comtradedeveloper.un.org/
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

COMTRADE_PREVIEW_URL = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
COMTRADE_AUTH_URL = "https://comtradeapi.un.org/data/v1/get/C/A/HS"

# HS Chapter 93 subcodes for arms and ammunition
HS_ARMS_CODES = {
    "9301": "Military weapons (artillery, rockets, launchers)",
    "9302": "Revolvers and pistols",
    "9303": "Firearms (sporting/hunting/other)",
    "9304": "Other arms (air guns, spring guns, etc.)",
    "9305": "Parts and accessories of weapons",
    "9306": "Bombs, grenades, torpedoes, mines, missiles, ammunition",
    "9307": "Swords, bayonets, lances and similar",
}

# UN M49 country codes for major arms traders
COMTRADE_COUNTRY_CODES = {
    "United States": 842,
    "Russia": 643,
    "China": 156,
    "France": 251,
    "Germany": 276,
    "United Kingdom": 826,
    "Italy": 380,
    "Israel": 376,
    "South Korea": 410,
    "Spain": 724,
    "India": 699,
    "Saudi Arabia": 682,
    "Ukraine": 804,
    "Japan": 392,
    "Australia": 36,
    "Turkiye": 792,
    "Egypt": 818,
    "Brazil": 76,
    "Canada": 124,
    "Netherlands": 528,
    "Sweden": 752,
    "Norway": 578,
    "Poland": 616,
    "Pakistan": 586,
    "Iran": 364,
    "Taiwan": 490,
    "Qatar": 634,
    "Singapore": 702,
    "Indonesia": 360,
    "Thailand": 764,
}


@dataclass
class ComtradeRecord:
    """A single UN Comtrade arms trade record."""
    reporter: str
    reporter_iso: str
    partner: str
    partner_iso: str
    year: int
    flow: str  # "Export" or "Import"
    hs_code: str
    hs_description: str
    trade_value_usd: float
    quantity: float | None = None
    net_weight_kg: float | None = None


@dataclass
class ComtradeQuery:
    """Query parameters for UN Comtrade API."""
    reporter_codes: list[int] = field(default_factory=list)
    partner_codes: list[int] = field(default_factory=list)
    years: list[int] = field(default_factory=lambda: [2023])
    flow_codes: list[str] = field(default_factory=lambda: ["M", "X"])
    hs_codes: list[str] = field(default_factory=lambda: ["93"])
    include_descriptions: bool = True


class ComtradeClient:
    """Client for the UN Comtrade arms trade API.

    Uses the free preview endpoint by default (500 records max, no auth).
    Set subscription_key for the authenticated endpoint (100K records).
    """

    def __init__(self, subscription_key: str | None = None, timeout: float = 30.0):
        self.subscription_key = subscription_key
        self.timeout = timeout

    def _build_params(self, query: ComtradeQuery) -> dict:
        """Build query parameters for the Comtrade API."""
        params = {
            "cmdCode": ",".join(query.hs_codes),
            "flowCode": ",".join(query.flow_codes),
            "period": ",".join(str(y) for y in query.years),
            "includeDesc": "true" if query.include_descriptions else "false",
        }

        if query.reporter_codes:
            params["reporterCode"] = ",".join(str(c) for c in query.reporter_codes)

        if query.partner_codes:
            params["partnerCode"] = ",".join(str(c) for c in query.partner_codes)
        else:
            params["partnerCode"] = "0"  # World aggregate

        return params

    async def fetch(self, query: ComtradeQuery) -> list[ComtradeRecord]:
        """Fetch arms trade data from UN Comtrade.

        Args:
            query: Query parameters.

        Returns:
            List of trade records.
        """
        params = self._build_params(query)

        if self.subscription_key:
            url = COMTRADE_AUTH_URL
            headers = {"Ocp-Apim-Subscription-Key": self.subscription_key}
        else:
            url = COMTRADE_PREVIEW_URL
            headers = {}
            params["maxRecords"] = 500

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info(
                "Fetching Comtrade: reporters=%s, years=%s, hs=%s",
                params.get("reporterCode", "all"),
                params["period"],
                params["cmdCode"],
            )
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()

        data = response.json()

        if data.get("error"):
            logger.error("Comtrade API error: %s", data["error"])
            return []

        records = []
        for item in data.get("data", []):
            # Skip aggregates where partner is "World"
            if item.get("partnerCode") == 0 and len(query.partner_codes) == 0:
                # Keep World aggregates only if explicitly requested
                pass

            trade_value = item.get("primaryValue") or item.get("fobvalue") or item.get("cifvalue") or 0

            records.append(ComtradeRecord(
                reporter=item.get("reporterDesc", ""),
                reporter_iso=item.get("reporterISO", ""),
                partner=item.get("partnerDesc", ""),
                partner_iso=item.get("partnerISO", ""),
                year=item.get("refYear", 0),
                flow=item.get("flowDesc", ""),
                hs_code=item.get("cmdCode", ""),
                hs_description=item.get("cmdDesc", ""),
                trade_value_usd=trade_value,
                quantity=item.get("qty") if item.get("qty") and item["qty"] > 0 else None,
                net_weight_kg=item.get("netWgt") if item.get("netWgt") and item["netWgt"] > 0 else None,
            ))

        logger.info("Fetched %d Comtrade records", len(records))
        return records

    async def fetch_country_exports(
        self, country_name: str, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch arms exports for a specific country with partner breakdown."""
        code = COMTRADE_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}")

        query = ComtradeQuery(
            reporter_codes=[code],
            years=years or [2022, 2023],
            flow_codes=["X"],
            hs_codes=["9301", "9302", "9303", "9304", "9305", "9306"],
        )
        return await self.fetch(query)

    async def fetch_country_imports(
        self, country_name: str, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch arms imports for a specific country with partner breakdown."""
        code = COMTRADE_COUNTRY_CODES.get(country_name)
        if code is None:
            raise ValueError(f"Unknown country: {country_name}")

        query = ComtradeQuery(
            reporter_codes=[code],
            years=years or [2022, 2023],
            flow_codes=["M"],
            hs_codes=["9301", "9302", "9303", "9304", "9305", "9306"],
        )
        return await self.fetch(query)

    async def fetch_global_summary(
        self, years: list[int] | None = None
    ) -> list[ComtradeRecord]:
        """Fetch aggregate arms trade (HS 93) for major exporters."""
        top_exporters = [842, 251, 276, 380, 826, 156, 410, 724, 376, 643]
        query = ComtradeQuery(
            reporter_codes=top_exporters,
            years=years or [2020, 2021, 2022, 2023],
            flow_codes=["X"],
            hs_codes=["93"],
        )
        return await self.fetch(query)
