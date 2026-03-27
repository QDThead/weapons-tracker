"""World Bank Enrichment — additional indicators for risk scoring.

Fetches governance, economic, and military indicators beyond the
base arms trade data. No authentication required.

New indicators:
  - CC.EST — Control of Corruption (-2.5 to 2.5)
  - PV.EST — Political Stability & Absence of Violence
  - GE.EST — Government Effectiveness
  - RL.EST — Rule of Law
  - MS.MIL.XPND.CD — Military expenditure (current USD)
  - MS.MIL.TOTL.TF.ZS — Armed forces (% of labor force)
  - FP.CPI.TOTL.ZG — Inflation rate (consumer prices)
  - SL.UEM.TOTL.ZS — Unemployment rate
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

WB_API_BASE = "https://api.worldbank.org/v2"

GOVERNANCE_INDICATORS = {
    "corruption_control": "CC.EST",
    "political_stability": "PV.EST",
    "govt_effectiveness": "GE.EST",
    "rule_of_law": "RL.EST",
    "regulatory_quality": "RQ.EST",
}

ECONOMIC_INDICATORS = {
    "military_spending_usd": "MS.MIL.XPND.CD",
    "armed_forces_pct": "MS.MIL.TOTL.TF.ZS",
    "inflation_rate": "FP.CPI.TOTL.ZG",
    "unemployment_rate": "SL.UEM.TOTL.ZS",
    "gdp_current_usd": "NY.GDP.MKTP.CD",
}


@dataclass
class GovernanceRecord:
    """Governance indicator for a country-year."""
    country_name: str
    country_iso3: str
    year: int
    indicator: str
    value: float


class WorldBankEnrichmentClient:
    """Fetches governance and economic indicators from World Bank."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    async def fetch_governance_indicators(
        self, countries: list[str] | None = None, year: int = 2023
    ) -> list[GovernanceRecord]:
        """Fetch all governance indicators for specified countries."""
        if not countries:
            countries = ["CAN", "USA", "GBR", "DEU", "FRA", "RUS", "CHN", "IND",
                        "TUR", "ISR", "SAU", "IRN", "KOR", "JPN", "AUS", "BRA",
                        "NOR", "SWE", "FIN", "POL", "ITA", "ESP", "NLD", "UKR"]

        records = []
        country_str = ";".join(countries)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for name, indicator_code in GOVERNANCE_INDICATORS.items():
                try:
                    url = f"{WB_API_BASE}/country/{country_str}/indicator/{indicator_code}"
                    params = {"format": "json", "per_page": 100, "date": str(year)}
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    if not isinstance(data, list) or len(data) < 2:
                        continue

                    for entry in data[1]:
                        if entry.get("value") is not None:
                            records.append(GovernanceRecord(
                                country_name=entry["country"]["value"],
                                country_iso3=entry["countryiso3code"],
                                year=int(entry["date"]),
                                indicator=name,
                                value=float(entry["value"]),
                            ))
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", indicator_code, e)

        logger.info("Fetched %d governance records for %d countries", len(records), len(countries))
        return records

    async def fetch_economic_indicators(
        self, countries: list[str] | None = None, year: int = 2023
    ) -> list[GovernanceRecord]:
        """Fetch economic indicators."""
        if not countries:
            countries = ["CAN", "USA", "GBR", "DEU", "FRA", "RUS", "CHN"]

        records = []
        country_str = ";".join(countries)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for name, indicator_code in ECONOMIC_INDICATORS.items():
                try:
                    url = f"{WB_API_BASE}/country/{country_str}/indicator/{indicator_code}"
                    params = {"format": "json", "per_page": 100, "date": str(year)}
                    resp = await client.get(url, params=params)
                    if resp.status_code != 200:
                        continue

                    data = resp.json()
                    if not isinstance(data, list) or len(data) < 2:
                        continue

                    for entry in data[1]:
                        if entry.get("value") is not None:
                            records.append(GovernanceRecord(
                                country_name=entry["country"]["value"],
                                country_iso3=entry["countryiso3code"],
                                year=int(entry["date"]),
                                indicator=name,
                                value=float(entry["value"]),
                            ))
                except Exception as e:
                    logger.warning("Failed to fetch %s: %s", indicator_code, e)

        logger.info("Fetched %d economic records", len(records))
        return records

    async def fetch_exchange_rates(self) -> dict:
        """Fetch current CAD-based exchange rates."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://api.exchangerate-api.com/v4/latest/CAD")
            resp.raise_for_status()
            data = resp.json()
            return {
                "base": "CAD",
                "date": data.get("date"),
                "rates": data.get("rates", {}),
                "key_rates": {
                    "USD": data["rates"].get("USD"),
                    "EUR": data["rates"].get("EUR"),
                    "GBP": data["rates"].get("GBP"),
                    "CNY": data["rates"].get("CNY"),
                    "JPY": data["rates"].get("JPY"),
                },
            }
