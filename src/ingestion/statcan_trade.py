"""Statistics Canada CIMT connector for Canadian arms trade data.

Downloads bulk CSV exports from the CIMT (Canadian International
Merchandise Trade) database and filters for HS Chapter 93 (Arms
& Ammunition). Values are in Canadian dollars.

No authentication required. Downloads are large ZIP files (~50 MB each),
so results are cached for 24 hours after the first fetch.

Reference: https://www150.statcan.gc.ca/n1/pub/71-607-x/71-607-x2021004-eng.htm
"""

from __future__ import annotations

import csv
import io
import logging
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# URL templates for CIMT bulk CSV downloads
CIMT_EXPORT_URL = (
    "https://www150.statcan.gc.ca/n1/pub/71-607-x/2021004/zip/"
    "CIMT-CICM_Tot_Exp_{year}.zip"
)
CIMT_IMPORT_URL = (
    "https://www150.statcan.gc.ca/n1/pub/71-607-x/2021004/zip/"
    "CIMT-CICM_Imp_{year}.zip"
)

# HS2 chapter code for arms and ammunition
HS2_ARMS = "93"

# Cache TTL: 24 hours (large files, updated monthly)
_CACHE_TTL = 86400


@dataclass
class StatCanTradeRecord:
    """A single Canadian monthly arms trade record."""
    partner_country: str    # Full country name
    partner_code: str       # ISO 2-letter code
    year: int
    month: int
    value_cad: int          # Trade value in Canadian dollars
    direction: str          # "export" or "import"


# Module-level cache: key -> (timestamp, records)
_cache: dict[str, tuple[float, list[StatCanTradeRecord]]] = {}


def _is_cache_valid(key: str) -> bool:
    """Check if cached data for the given key is still fresh."""
    entry = _cache.get(key)
    if entry is None:
        return False
    return (time.time() - entry[0]) < _CACHE_TTL


class StatCanTradeClient:
    """Client for the Statistics Canada CIMT bulk CSV data.

    Downloads ZIP files containing HS2-level trade data, extracts
    arms/ammunition records (HS2 = 93), and parses country descriptions
    from the included lookup file.
    """

    def __init__(self, timeout: float = 120.0):
        # Large ZIP downloads need a generous timeout
        self.timeout = timeout

    async def _download_zip(self, url: str) -> zipfile.ZipFile:
        """Download a ZIP file and return it as a ZipFile object.

        Args:
            url: URL of the ZIP file.

        Returns:
            zipfile.ZipFile ready for extraction.
        """
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            logger.info("Downloading StatCan ZIP: %s", url)
            response = await client.get(url)
            response.raise_for_status()

        return zipfile.ZipFile(io.BytesIO(response.content))

    def _parse_country_lookup(self, zf: zipfile.ZipFile) -> dict[str, str]:
        """Extract country code-to-name mapping from the lookup file in the ZIP.

        The lookup file ODPF_6_CtyDesc.TXT uses a fixed-width format:
            AD 156     196601 999912 Andorra             Andorre              ...
        Fields: ISO2, numeric code, start date, end date, English name, French name, ...

        Args:
            zf: Opened ZipFile.

        Returns:
            Dict mapping ISO 2-letter country code to English name.
        """
        lookup: dict[str, str] = {}

        # Find the country description lookup file
        lookup_names = [
            n for n in zf.namelist()
            if "CtyDesc" in n or ("ODPF_6" in n and n.endswith(".TXT"))
        ]
        if not lookup_names:
            # Broader match
            lookup_names = [
                n for n in zf.namelist()
                if "cty" in n.lower() and n.endswith(".TXT")
            ]

        if not lookup_names:
            logger.warning("Country lookup file not found in ZIP; using raw codes")
            return lookup

        lookup_file = lookup_names[0]
        logger.info("Using country lookup file: %s", lookup_file)

        with zf.open(lookup_file) as f:
            raw = f.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")

        for line in text.splitlines():
            line = line.strip()
            if not line or len(line) < 30:
                continue

            # The ISO 2-letter code is the first 2 characters
            iso2 = line[:2].strip()
            if not iso2 or not iso2.isalpha() or len(iso2) != 2:
                continue

            # After the ISO2 and numeric code (positions 0-10ish), find the
            # English name. The format is fixed-width with the English name
            # starting around position 22 and running ~80 chars.
            # Split on multiple spaces to find the name fields.
            parts = line.split()
            # parts[0] = ISO2, parts[1] = numeric code, parts[2] = start date,
            # parts[3] = end date, then English name words until French name starts.
            # The English name ends roughly at a column boundary.
            # Simpler approach: extract by known position ranges.
            # After "AD 156     196601 999912 " the English name starts.
            # Find the position after the 4th whitespace-separated token.
            if len(parts) < 5:
                continue

            # Reconstruct English name: it's between end-date and the next
            # field that looks like a repeated name pattern.
            # Use a regex-free approach: the name starts after 4 tokens.
            rest = line
            for _ in range(4):
                rest = rest.lstrip()
                # Skip past the next whitespace-delimited token
                idx = 0
                while idx < len(rest) and not rest[idx].isspace():
                    idx += 1
                rest = rest[idx:]

            rest = rest.lstrip()
            # The English name is roughly 80 chars, followed by the French name.
            # Take up to 80 chars and strip trailing spaces.
            english_name = rest[:80].rstrip()

            if english_name:
                lookup[iso2] = english_name

        logger.info("Loaded %d country mappings from StatCan lookup", len(lookup))
        return lookup

    def _find_data_file(self, zf: zipfile.ZipFile, pattern: str) -> str | None:
        """Find the main data CSV file in the ZIP archive.

        Args:
            zf: Opened ZipFile.
            pattern: Substring to match (e.g. "ODPFN021" for HS2 data).

        Returns:
            Filename string or None.
        """
        # Look for HS2-level data file (ODPFN021_*)
        candidates = [
            n for n in zf.namelist()
            if pattern in n and n.endswith(".csv")
        ]
        if candidates:
            return candidates[0]

        # Broader fallback: any CSV file
        csvs = [n for n in zf.namelist() if n.endswith(".csv")]
        if csvs:
            return csvs[0]

        return None

    def _parse_data_csv(
        self,
        zf: zipfile.ZipFile,
        data_file: str,
        country_lookup: dict[str, str],
        direction: str,
    ) -> list[StatCanTradeRecord]:
        """Parse the HS2-level data CSV and filter for HS2 = 93.

        The bilingual column headers look like:
            YearMonth/AnnéeMois, HS2, Country/Pays, State/État, Value/Valeur
        Import files also have a Province column for Canadian provinces.

        Province/state-level rows are aggregated into country-month totals.

        Args:
            zf: Opened ZipFile.
            data_file: Name of the CSV file inside the ZIP.
            country_lookup: Code-to-name mapping.
            direction: "export" or "import".

        Returns:
            List of StatCanTradeRecord for HS2 = 93.
        """
        with zf.open(data_file) as f:
            raw = f.read()
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text))

        # Normalize column names (StatCan uses bilingual headers like "Country/Pays")
        fieldnames = reader.fieldnames or []
        col_map = {col.strip().strip('"').lower(): col for col in fieldnames}

        # Find the actual column keys — search handles bilingual names via partial match
        ym_key = self._find_column(col_map, [
            "yearmonth", "yearmonth/annéemois", "year_month", "anneemois",
            "date", "period",
        ])
        hs_key = self._find_column(col_map, [
            "hs2", "hs_2", "chapter", "hs2code", "commodity",
        ])
        country_key = self._find_column(col_map, [
            "country/pays", "country", "countrycode", "pays", "cty", "partner",
        ])
        value_key = self._find_column(col_map, [
            "value/valeur", "value", "valeur", "tradevalue", "val", "total",
        ])

        if not all([ym_key, hs_key, country_key, value_key]):
            logger.error(
                "Could not identify required columns. Available: %s",
                fieldnames,
            )
            return []

        # Accumulate values by (yearmonth, country_code) to aggregate
        # province/state-level rows into national totals
        aggregated: dict[tuple[str, str], int] = {}

        for row in reader:
            try:
                hs2 = row.get(hs_key, "").strip().strip('"')
                if hs2 != HS2_ARMS:
                    continue

                yearmonth = row.get(ym_key, "").strip().strip('"')
                if not yearmonth:
                    continue

                value_str = row.get(value_key, "").strip().strip('"').replace(",", "")
                if not value_str or value_str in ("0", "x", ".."):
                    continue
                value_cad = int(float(value_str))
                if value_cad <= 0:
                    continue

                country_code = row.get(country_key, "").strip().strip('"')

                key = (yearmonth, country_code)
                aggregated[key] = aggregated.get(key, 0) + value_cad
            except (ValueError, KeyError) as e:
                logger.debug("Skipping malformed row: %s (%s)", row, e)
                continue

        # Convert aggregated data to records
        records: list[StatCanTradeRecord] = []
        for (yearmonth, country_code), total_value in sorted(aggregated.items()):
            yearmonth_clean = yearmonth.replace("-", "")
            if len(yearmonth_clean) < 6:
                continue
            year = int(yearmonth_clean[:4])
            month = int(yearmonth_clean[4:6])

            country_name = country_lookup.get(country_code, country_code)

            records.append(StatCanTradeRecord(
                partner_country=country_name,
                partner_code=country_code,
                year=year,
                month=month,
                value_cad=total_value,
                direction=direction,
            ))

        return records

    @staticmethod
    def _find_column(col_map: dict[str, str], candidates: list[str]) -> str | None:
        """Find the actual column name from a list of possible names.

        Args:
            col_map: Mapping of lowercased column names to original names.
            candidates: Possible column name variations (lowercase).

        Returns:
            Original column name string, or None.
        """
        for candidate in candidates:
            if candidate in col_map:
                return col_map[candidate]
        # Partial match fallback
        for candidate in candidates:
            for key, original in col_map.items():
                if candidate in key:
                    return original
        return None

    async def _fetch_direction(
        self, url: str, direction: str
    ) -> list[StatCanTradeRecord]:
        """Download and parse one direction (export or import) of trade data.

        Args:
            url: Download URL for the ZIP file.
            direction: "export" or "import".

        Returns:
            List of StatCanTradeRecord.
        """
        zf = await self._download_zip(url)

        country_lookup = self._parse_country_lookup(zf)

        # Export HS2 file is ODPFN021_*, import HS2 file is ODPFN022_*
        # Try these specific patterns first before any general fallback
        hs2_patterns = ["ODPFN021", "ODPFN022"]
        data_file = None
        for pattern in hs2_patterns:
            candidates = [
                n for n in zf.namelist()
                if pattern in n and n.endswith(".csv")
            ]
            if candidates:
                data_file = candidates[0]
                break
        if not data_file:
            logger.error("No data CSV found in ZIP from %s. Contents: %s", url, zf.namelist())
            return []

        logger.info("Parsing %s from %s", data_file, url)
        records = self._parse_data_csv(zf, data_file, country_lookup, direction)
        logger.info("Parsed %d %s records (HS2=93) from StatCan", len(records), direction)
        return records

    async def fetch_canada_arms_trade(
        self, year: int | None = None
    ) -> list[StatCanTradeRecord]:
        """Fetch Canadian arms trade data (HS Chapter 93) for a given year.

        Downloads both export and import bulk CSV files, filters for
        HS2 = 93, and returns combined records. Results are cached for
        24 hours since the underlying files are large and update monthly.

        Args:
            year: Year to fetch (e.g. 2025). Defaults to current year.

        Returns:
            List of StatCanTradeRecord (exports + imports combined).
        """
        if year is None:
            year = datetime.now().year

        cache_key = f"statcan_{year}"
        if _is_cache_valid(cache_key):
            logger.info("Returning cached StatCan data for %d", year)
            return _cache[cache_key][1]

        export_url = CIMT_EXPORT_URL.format(year=year)
        import_url = CIMT_IMPORT_URL.format(year=year)

        all_records: list[StatCanTradeRecord] = []

        # Fetch exports
        try:
            exports = await self._fetch_direction(export_url, "export")
            all_records.extend(exports)
        except Exception as e:
            logger.error("StatCan export download failed for %d: %s", year, e)

        # Fetch imports
        try:
            imports = await self._fetch_direction(import_url, "import")
            all_records.extend(imports)
        except Exception as e:
            logger.error("StatCan import download failed for %d: %s", year, e)

        # Cache the combined results
        if all_records:
            _cache[cache_key] = (time.time(), all_records)
            logger.info(
                "Cached %d StatCan arms trade records for %d (TTL: %ds)",
                len(all_records), year, _CACHE_TTL,
            )

        return all_records
