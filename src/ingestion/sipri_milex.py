"""SIPRI Military Expenditure (MILEX) connector.

Downloads and parses the SIPRI Military Expenditure Excel file.
Provides annual defence spending data for countries worldwide (1949-2024).

Data includes:
  - Military expenditure in current USD
  - Military expenditure as share of GDP (%)

Reference: https://www.sipri.org/databases/milex
Excel URL: https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2024_2.xlsx
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

SIPRI_MILEX_URL = (
    "https://www.sipri.org/sites/default/files/SIPRI-Milex-data-1949-2024_2.xlsx"
)

# Rows to skip at the top of each sheet (title rows, notes, etc.)
# SIPRI MILEX sheets typically have ~5 header rows before country data begins
_HEADER_ROWS_TO_SKIP = 5

# Cache TTL: 24 hours (data is updated once per year)
_CACHE_TTL = 86400.0

# ISO3 mapping for key countries found in SIPRI MILEX
_COUNTRY_ISO3: dict[str, str] = {
    "Afghanistan": "AFG",
    "Albania": "ALB",
    "Algeria": "DZA",
    "Angola": "AGO",
    "Argentina": "ARG",
    "Armenia": "ARM",
    "Australia": "AUS",
    "Austria": "AUT",
    "Azerbaijan": "AZE",
    "Bahrain": "BHR",
    "Bangladesh": "BGD",
    "Belarus": "BLR",
    "Belgium": "BEL",
    "Bolivia": "BOL",
    "Bosnia and Herzegovina": "BIH",
    "Botswana": "BWA",
    "Brazil": "BRA",
    "Brunei": "BRN",
    "Bulgaria": "BGR",
    "Burkina Faso": "BFA",
    "Burundi": "BDI",
    "Cambodia": "KHM",
    "Cameroon": "CMR",
    "Canada": "CAN",
    "Central African Republic": "CAF",
    "Chad": "TCD",
    "Chile": "CHL",
    "China": "CHN",
    "Colombia": "COL",
    "Congo": "COG",
    "Congo, DR": "COD",
    "Costa Rica": "CRI",
    "Côte d'Ivoire": "CIV",
    "Cote d'Ivoire": "CIV",
    "Croatia": "HRV",
    "Cuba": "CUB",
    "Cyprus": "CYP",
    "Czech Republic": "CZE",
    "Czechia": "CZE",
    "Denmark": "DNK",
    "Djibouti": "DJI",
    "Dominican Republic": "DOM",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "El Salvador": "SLV",
    "Eritrea": "ERI",
    "Estonia": "EST",
    "Ethiopia": "ETH",
    "Finland": "FIN",
    "France": "FRA",
    "Gabon": "GAB",
    "Georgia": "GEO",
    "Germany": "DEU",
    "Ghana": "GHA",
    "Greece": "GRC",
    "Guatemala": "GTM",
    "Guinea": "GIN",
    "Honduras": "HND",
    "Hungary": "HUN",
    "India": "IND",
    "Indonesia": "IDN",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Ireland": "IRL",
    "Israel": "ISR",
    "Italy": "ITA",
    "Japan": "JPN",
    "Jordan": "JOR",
    "Kazakhstan": "KAZ",
    "Kenya": "KEN",
    "South Korea": "KOR",
    "Korea, South": "KOR",
    "Kuwait": "KWT",
    "Kyrgyzstan": "KGZ",
    "Laos": "LAO",
    "Latvia": "LVA",
    "Lebanon": "LBN",
    "Libya": "LBY",
    "Lithuania": "LTU",
    "Luxembourg": "LUX",
    "Madagascar": "MDG",
    "Malawi": "MWI",
    "Malaysia": "MYS",
    "Mali": "MLI",
    "Mauritania": "MRT",
    "Mexico": "MEX",
    "Moldova": "MDA",
    "Mongolia": "MNG",
    "Montenegro": "MNE",
    "Morocco": "MAR",
    "Mozambique": "MOZ",
    "Myanmar": "MMR",
    "Namibia": "NAM",
    "Nepal": "NPL",
    "Netherlands": "NLD",
    "New Zealand": "NZL",
    "Nicaragua": "NIC",
    "Niger": "NER",
    "Nigeria": "NGA",
    "North Korea": "PRK",
    "Korea, North": "PRK",
    "North Macedonia": "MKD",
    "Norway": "NOR",
    "Oman": "OMN",
    "Pakistan": "PAK",
    "Panama": "PAN",
    "Paraguay": "PRY",
    "Peru": "PER",
    "Philippines": "PHL",
    "Poland": "POL",
    "Portugal": "PRT",
    "Qatar": "QAT",
    "Romania": "ROU",
    "Russia": "RUS",
    "Rwanda": "RWA",
    "Saudi Arabia": "SAU",
    "Senegal": "SEN",
    "Serbia": "SRB",
    "Sierra Leone": "SLE",
    "Singapore": "SGP",
    "Slovakia": "SVK",
    "Slovenia": "SVN",
    "Somalia": "SOM",
    "South Africa": "ZAF",
    "South Sudan": "SSD",
    "Spain": "ESP",
    "Sri Lanka": "LKA",
    "Sudan": "SDN",
    "Sweden": "SWE",
    "Switzerland": "CHE",
    "Syria": "SYR",
    "Taiwan": "TWN",
    "Tajikistan": "TJK",
    "Tanzania": "TZA",
    "Thailand": "THA",
    "Togo": "TGO",
    "Tunisia": "TUN",
    "Turkey": "TUR",
    "Türkiye": "TUR",
    "Turkmenistan": "TKM",
    "Uganda": "UGA",
    "Ukraine": "UKR",
    "United Arab Emirates": "ARE",
    "United Kingdom": "GBR",
    "United States": "USA",
    "United States of America": "USA",
    "Uruguay": "URY",
    "Uzbekistan": "UZB",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
    "Viet Nam": "VNM",
    "Yemen": "YEM",
    "Zambia": "ZMB",
    "Zimbabwe": "ZWE",
}


@dataclass
class MilexRecord:
    """A single country-year military expenditure record."""

    country_name: str
    country_iso3: str | None
    year: int
    spending_usd: float  # current USD millions
    spending_pct_gdp: float | None


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL."""

    records: list[MilexRecord]
    fetched_at: float


class SIPRIMilexClient:
    """Client for SIPRI Military Expenditure data.

    Downloads and parses the annual Excel file from SIPRI.
    Results are cached in memory since the file is updated only once per year.

    The Excel file has multiple sheets including:
      - 'Current USD'  — spending in current USD millions
      - 'Constant (2022) USD' — constant USD millions
      - 'Share of GDP' — as % of GDP
      - 'Per capita' — USD per capita
    """

    def __init__(self, timeout: float = 120.0, cache_ttl: float = _CACHE_TTL):
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cache: _CacheEntry | None = None

    async def _download(self, url: str = SIPRI_MILEX_URL) -> bytes:
        """Download the SIPRI MILEX Excel file."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Downloading SIPRI MILEX Excel from %s", url)
            response = await client.get(
                url,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (compatible; weapons-tracker/1.0; "
                        "research tool for Canadian DND)"
                    )
                },
            )
            response.raise_for_status()
            logger.info("Downloaded %d bytes from SIPRI MILEX", len(response.content))
            return response.content

    def _find_sheet(self, xl: pd.ExcelFile, keywords: list[str]) -> str | None:
        """Find a sheet by matching keywords against sheet names (case-insensitive).

        Also strips currency symbols ($ £ €) so that "Current US$" matches
        the keyword list ["current", "us"] or ["current", "usd"].
        """
        for name in xl.sheet_names:
            # Normalise: lowercase, strip currency/punctuation symbols
            normalised = name.lower().replace("$", "usd").replace("£", "gbp").replace("€", "eur")
            if all(kw.lower() in normalised for kw in keywords):
                return name
        return None

    def _parse_spending_sheet(
        self, xl: pd.ExcelFile, sheet_name: str
    ) -> dict[str, dict[int, float]]:
        """Parse a SIPRI MILEX spending sheet returning {country: {year: value}}.

        SIPRI MILEX sheet layout (verified against 2024 release):
          - Rows 0-4: title + notes
          - Row 5: header row — col 0 = "Country", col 1 = "Notes",
                   col 2+ = year integers (1949, 1950, ..., 2024)
          - Row 6: blank separator
          - Rows 7+: data rows
              * Region/subregion header rows (no numeric data)
              * Country rows: col 0 = name, col 1 = footnote codes, col 2+ = values
              * Values are floats or strings ("...", "xxx") for missing data
        """
        raw = pd.read_excel(
            xl,
            sheet_name=sheet_name,
            header=None,
            engine="openpyxl",
        )

        # Find the header row: first row where col 0 == "Country" (or many year ints)
        year_row_idx: int | None = None
        for i, row in raw.iterrows():
            # Check if this row has many year-like integers
            numeric_vals = [
                v for v in row
                if isinstance(v, (int, float)) and not pd.isna(v) and 1949 <= v <= 2030
            ]
            if len(numeric_vals) >= 10:
                year_row_idx = int(i)
                break
            # Also detect by "Country" label in col 0
            if str(row.iloc[0]).strip() == "Country":
                year_row_idx = int(i)
                break

        if year_row_idx is None:
            logger.warning("Could not find year header row in sheet '%s'", sheet_name)
            return {}

        # Build column -> year mapping from the header row
        year_row = raw.iloc[year_row_idx]
        col_to_year: dict[int, int] = {}
        for col_idx, val in enumerate(year_row):
            if isinstance(val, (int, float)) and not pd.isna(val) and 1949 <= val <= 2030:
                col_to_year[col_idx] = int(val)

        if not col_to_year:
            logger.warning("No year columns found in sheet '%s'", sheet_name)
            return {}

        logger.debug(
            "Sheet '%s': %d year columns (%d-%d)",
            sheet_name, len(col_to_year),
            min(col_to_year.values()), max(col_to_year.values()),
        )

        # Region/subregion header names to skip (no numeric data in these rows)
        REGION_KEYWORDS = {
            "africa", "north africa", "sub-saharan", "americas", "north america",
            "central america", "south america", "asia", "east asia", "south asia",
            "southeast asia", "central asia", "europe", "western europe",
            "eastern europe", "middle east", "oceania", "total",
        }

        # Parse data rows (after header row)
        result: dict[str, dict[int, float]] = {}
        for i in range(year_row_idx + 1, len(raw)):
            row = raw.iloc[i]
            country_val = row.iloc[0]

            if not isinstance(country_val, str):
                continue
            country_name = country_val.strip()
            if not country_name:
                continue

            # Skip region headers (they have no numeric spending data)
            if country_name.lower() in REGION_KEYWORDS:
                continue
            # Skip footnote/notes rows
            if country_name.lower().startswith(("notes", "source", "footnote")):
                break
            # Skip pure-digit or very short entries
            if len(country_name) < 2 or country_name[0].isdigit():
                continue

            # Extract numeric values for each year column
            country_data: dict[int, float] = {}
            for col_idx, year in col_to_year.items():
                val = row.iloc[col_idx]
                if isinstance(val, (int, float)) and not pd.isna(val):
                    country_data[year] = float(val)

            if country_data:
                result[country_name] = country_data

        return result

    def parse_excel(self, excel_bytes: bytes) -> list[MilexRecord]:
        """Parse the SIPRI MILEX Excel file into structured records.

        Returns:
            List of MilexRecord, one per country per year.
        """
        xl = pd.ExcelFile(io.BytesIO(excel_bytes), engine="openpyxl")
        logger.info("SIPRI MILEX sheet names: %s", xl.sheet_names)

        # Find the "Current US$" sheet.
        # Sheet names vary slightly across SIPRI releases:
        #   "Current US$" (2024 release)
        #   "Current USD" (older releases)
        # _find_sheet normalises "$" -> "usd" to handle both.
        usd_sheet = self._find_sheet(xl, ["current", "usd"])
        if usd_sheet is None:
            # Broader fallback: any sheet with "current" in name
            usd_sheet = self._find_sheet(xl, ["current"])
        if usd_sheet is None:
            # Last resort: scan for a sheet containing many numeric year-like values
            for name in xl.sheet_names:
                sample = pd.read_excel(xl, sheet_name=name, header=None, engine="openpyxl", nrows=10)
                year_vals = [
                    v for row_data in sample.values
                    for v in row_data
                    if isinstance(v, (int, float)) and 1949 <= v <= 2030
                ]
                if len(year_vals) >= 20:
                    usd_sheet = name
                    break
        logger.info("Using USD sheet: '%s'", usd_sheet)

        # Find the "Share of GDP" sheet
        gdp_sheet = self._find_sheet(xl, ["gdp"])
        if gdp_sheet is None:
            gdp_sheet = self._find_sheet(xl, ["share"])
        logger.info("Using GDP share sheet: '%s'", gdp_sheet)

        # Parse spending data
        spending_data = self._parse_spending_sheet(xl, usd_sheet)

        # Parse GDP share data
        gdp_data: dict[str, dict[int, float]] = {}
        if gdp_sheet and gdp_sheet != usd_sheet:
            gdp_data = self._parse_spending_sheet(xl, gdp_sheet)

        # Merge into MilexRecord list
        records: list[MilexRecord] = []
        all_countries = set(spending_data.keys()) | set(gdp_data.keys())

        for country_name in sorted(all_countries):
            country_years = spending_data.get(country_name, {})
            gdp_years = gdp_data.get(country_name, {})
            all_years = set(country_years.keys()) | set(gdp_years.keys())

            iso3 = _COUNTRY_ISO3.get(country_name)

            for year in sorted(all_years):
                spending = country_years.get(year)
                if spending is None:
                    continue  # Skip if no USD spending value

                # GDP share sheet stores values as fractions (0.013 = 1.3%).
                # Convert to percentage points so the API returns e.g. 1.3 not 0.013.
                raw_gdp = gdp_years.get(year)
                pct_gdp = round(raw_gdp * 100, 3) if raw_gdp is not None else None

                records.append(MilexRecord(
                    country_name=country_name,
                    country_iso3=iso3,
                    year=year,
                    spending_usd=spending,
                    spending_pct_gdp=pct_gdp,
                ))

        logger.info(
            "Parsed %d SIPRI MILEX records (%d countries)",
            len(records),
            len(all_countries),
        )
        return records

    async def fetch_milex_data(self) -> list[MilexRecord]:
        """Download and parse SIPRI Military Expenditure data.

        Returns cached data if available and within TTL.

        Returns:
            List of MilexRecord for all countries and years.
        """
        # Return cached data if still fresh
        if (
            self._cache is not None
            and time.monotonic() - self._cache.fetched_at < self.cache_ttl
        ):
            logger.info(
                "Returning %d cached SIPRI MILEX records", len(self._cache.records)
            )
            return self._cache.records

        excel_bytes = await self._download()
        records = self.parse_excel(excel_bytes)
        self._cache = _CacheEntry(records=records, fetched_at=time.monotonic())
        return records
