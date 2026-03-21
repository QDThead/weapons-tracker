"""SIPRI Top 100 Arms-Producing Companies connector.

Fetches and parses the SIPRI Arms Industry Database Excel files.
Tracks the 100 largest defense companies by arms revenue.
Updated annually.

Reference: https://www.sipri.org/databases/armsindustry
"""

import io
import logging
from dataclasses import dataclass

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

# SIPRI provides Excel downloads for the Top 100 data
SIPRI_TOP100_URL = "https://www.sipri.org/sites/default/files/SIPRI-Top-100-2002-2023.xlsx"


@dataclass
class DefenseCompanyRecord:
    """A single defense company record."""
    name: str
    country: str
    rank: int
    year: int
    arms_revenue_usd_millions: float | None
    total_revenue_usd_millions: float | None
    arms_revenue_pct: float | None


class SIPRICompaniesClient:
    """Client for the SIPRI Arms Industry Database (Top 100)."""

    def __init__(self, timeout: float = 60.0):
        self.timeout = timeout

    async def fetch_top100_excel(self, url: str = SIPRI_TOP100_URL) -> bytes:
        """Download the Top 100 Excel file from SIPRI."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            logger.info("Downloading SIPRI Top 100 Excel from %s", url)
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.content

    def parse_top100(self, excel_bytes: bytes) -> list[DefenseCompanyRecord]:
        """Parse the Top 100 Excel file into structured records.

        The SIPRI Excel has multiple sheets/formats across years.
        This parser handles the standard column layout.
        """
        records = []

        try:
            xls = pd.ExcelFile(io.BytesIO(excel_bytes))

            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

                # Try to detect header row and extract year from sheet name
                year = self._extract_year(sheet_name)
                if year is None:
                    continue

                # Find the header row (look for "Company" or "Rank")
                header_row = None
                for i, row in df.iterrows():
                    row_str = " ".join(str(v).lower() for v in row.values if pd.notna(v))
                    if "company" in row_str and ("rank" in row_str or "country" in row_str):
                        header_row = i
                        break

                if header_row is None:
                    logger.warning("Could not find header row in sheet '%s'", sheet_name)
                    continue

                df.columns = df.iloc[header_row]
                df = df.iloc[header_row + 1:].reset_index(drop=True)

                # Normalize column names
                col_map = {}
                for col in df.columns:
                    col_lower = str(col).lower().strip()
                    if "rank" in col_lower:
                        col_map[col] = "rank"
                    elif "company" in col_lower or "name" in col_lower:
                        col_map[col] = "name"
                    elif "country" in col_lower:
                        col_map[col] = "country"
                    elif "arms" in col_lower and "rev" in col_lower:
                        col_map[col] = "arms_revenue"
                    elif "total" in col_lower and "rev" in col_lower:
                        col_map[col] = "total_revenue"

                df = df.rename(columns=col_map)

                for _, row in df.iterrows():
                    try:
                        name = str(row.get("name", "")).strip()
                        if not name or name == "nan":
                            continue

                        records.append(DefenseCompanyRecord(
                            name=name,
                            country=str(row.get("country", "")).strip(),
                            rank=self._safe_int(row.get("rank")),
                            year=year,
                            arms_revenue_usd_millions=self._safe_float(row.get("arms_revenue")),
                            total_revenue_usd_millions=self._safe_float(row.get("total_revenue")),
                            arms_revenue_pct=None,
                        ))
                    except Exception as e:
                        logger.debug("Skipping row in sheet '%s': %s", sheet_name, e)

        except Exception as e:
            logger.error("Failed to parse Top 100 Excel: %s", e)
            raise

        logger.info("Parsed %d company records from SIPRI Top 100", len(records))
        return records

    async def fetch_and_parse(self, url: str = SIPRI_TOP100_URL) -> list[DefenseCompanyRecord]:
        """Download and parse the Top 100 data in one step."""
        excel_bytes = await self.fetch_top100_excel(url)
        return self.parse_top100(excel_bytes)

    @staticmethod
    def _extract_year(sheet_name: str) -> int | None:
        """Try to extract a 4-digit year from a sheet name."""
        import re
        match = re.search(r"20\d{2}", sheet_name)
        if match:
            return int(match.group())
        return None

    @staticmethod
    def _safe_float(value) -> float | None:
        try:
            if pd.isna(value):
                return None
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_int(value) -> int:
        try:
            if pd.isna(value):
                return 0
            return int(float(value))
        except (ValueError, TypeError):
            return 0
