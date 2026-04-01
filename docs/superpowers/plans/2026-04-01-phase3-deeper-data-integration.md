# Phase 3 — Deeper Data Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate Comtrade cobalt bilateral queries, fill all 10 remaining supplier dossiers with real OSINT data, and build active confidence triangulation with discrepancy detection.

**Architecture:** Three independent workstreams: (1) Comtrade bilateral query function in `comtrade.py` with scheduler integration, (2) dossier data blocks added to `mineral_supply_chains.py` for 10 entities, (3) triangulation function in `confidence.py` with discrepancy alerts. UI surfaces data from all three.

**Tech Stack:** Python 3.9+ (httpx async), SQLAlchemy, APScheduler, FastAPI, CesiumJS/Leaflet (frontend)

**Design spec:** `docs/superpowers/specs/2026-04-01-phase3-deeper-data-integration-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/ingestion/comtrade.py` | Modify (lines 36-76, 362-374, new function ~line 375) | Add M49 codes, cobalt bilateral query function |
| `src/analysis/mineral_supply_chains.py` | Modify (lines 623-762 mines, 997-1157 refineries) | Add 10 dossier blocks |
| `src/analysis/confidence.py` | Modify (add ~80 lines after line 200) | Triangulation function, HHI computation |
| `src/analysis/cobalt_alert_engine.py` | Modify (add rule ~line 120) | Discrepancy alert rule |
| `src/api/globe_routes.py` | Modify (lines 25-31) | Enrich cobalt response with trade flows + confidence |
| `src/ingestion/scheduler.py` | Modify (add job ~line 363) | Monthly Comtrade cobalt job |
| `src/static/index.html` | Modify (lines 7717, 7142, 8255, 8367, 7947) | Confidence badges, trade values, taxonomy opacity |
| `tests/test_comtrade_cobalt.py` | Create | Bilateral query tests |
| `tests/test_confidence_triangulation.py` | Create | Triangulation + HHI tests |
| `tests/test_dossier_completeness.py` | Create | All 18 entities have required fields |

---

### Task 1: Comtrade Cobalt Bilateral Query Function

**Files:**
- Modify: `src/ingestion/comtrade.py:36-76` (M49 codes), `src/ingestion/comtrade.py:362-374` (source countries)
- Modify: `src/ingestion/comtrade.py` (new function after line 422)
- Test: `tests/test_comtrade_cobalt.py`

- [ ] **Step 1: Write failing tests for cobalt bilateral queries**

Create `tests/test_comtrade_cobalt.py`:

```python
"""Tests for Comtrade cobalt bilateral trade flow queries."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch
from src.ingestion.comtrade import (
    ComtradeMaterialsClient,
    COMTRADE_COUNTRY_CODES,
    MATERIAL_SOURCE_COUNTRIES,
    COBALT_BILATERAL_CORRIDORS,
    ComtradeRecord,
)


class TestCobaltM49Codes:
    """Verify all cobalt-relevant countries have M49 codes."""

    def test_belgium_in_codes(self):
        assert "Belgium" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Belgium"] == 56

    def test_finland_in_codes(self):
        assert "Finland" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Finland"] == 246

    def test_zambia_in_codes(self):
        assert "Zambia" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Zambia"] == 894

    def test_cuba_in_codes(self):
        assert "Cuba" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Cuba"] == 192

    def test_morocco_in_codes(self):
        assert "Morocco" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Morocco"] == 504

    def test_madagascar_in_codes(self):
        assert "Madagascar" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["Madagascar"] == 450

    def test_drc_in_codes(self):
        assert "DRC" in COMTRADE_COUNTRY_CODES
        assert COMTRADE_COUNTRY_CODES["DRC"] == 180

    def test_cobalt_source_countries_expanded(self):
        sources = MATERIAL_SOURCE_COUNTRIES["cobalt"]
        assert 180 in sources  # DRC
        assert 156 in sources  # China
        assert 246 in sources  # Finland
        assert 56 in sources   # Belgium
        assert 124 in sources  # Canada


class TestCobaltBilateralCorridors:
    """Verify corridor definitions."""

    def test_corridors_defined(self):
        assert len(COBALT_BILATERAL_CORRIDORS) >= 6

    def test_drc_china_corridor(self):
        drc_china = [c for c in COBALT_BILATERAL_CORRIDORS if c["reporter"] == 156 and c["partner"] == 180]
        assert len(drc_china) > 0, "DRC→China corridor (buyer-side: China reports imports FROM DRC)"


class TestFetchCobaltBilateralFlows:
    """Test the bilateral query function."""

    @pytest.mark.asyncio
    async def test_returns_list_of_records(self):
        client = ComtradeMaterialsClient(subscription_key="test-key")
        mock_records = [
            ComtradeRecord(
                reporter="China", reporter_iso="CHN", partner="Congo", partner_iso="COD",
                year=2023, flow="Import", hs_code="810520",
                hs_description="Cobalt unwrought/powder",
                trade_value_usd=2_390_000_000, quantity=85000, net_weight_kg=85000000,
            ),
        ]
        with patch.object(client, "fetch", new_callable=AsyncMock, return_value=mock_records):
            results = await client.fetch_cobalt_bilateral_flows(years=[2023])
        assert len(results) > 0
        assert results[0].trade_value_usd == 2_390_000_000

    @pytest.mark.asyncio
    async def test_uses_buyer_side_mirror_for_drc(self):
        """DRC corridors should query the IMPORTER (e.g., China), not DRC."""
        client = ComtradeMaterialsClient(subscription_key="test-key")
        queries_made = []
        original_fetch = client.fetch

        async def capture_fetch(query):
            queries_made.append(query)
            return []

        client.fetch = capture_fetch
        await client.fetch_cobalt_bilateral_flows(years=[2023])
        # At least one query should have China (156) as reporter importing FROM DRC (180)
        has_buyer_mirror = any(
            156 in q.reporter_codes and 180 in q.partner_codes and "M" in q.flow_codes
            for q in queries_made
        )
        assert has_buyer_mirror, "Should use buyer-side mirror: China reports imports FROM DRC"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_comtrade_cobalt.py -v`
Expected: FAIL — `COBALT_BILATERAL_CORRIDORS` not defined, `fetch_cobalt_bilateral_flows` not defined

- [ ] **Step 3: Add missing M49 codes to COMTRADE_COUNTRY_CODES**

In `src/ingestion/comtrade.py`, add after line 75 (`"Serbia": 688,`):

```python
    "DRC": 180,
    "Belgium": 56,
    "Finland": 246,
    "Cuba": 192,
    "Morocco": 504,
    "Zambia": 894,
    "Madagascar": 450,
    "South Africa": 710,
```

- [ ] **Step 4: Expand cobalt source countries**

In `src/ingestion/comtrade.py`, replace the cobalt entry in `MATERIAL_SOURCE_COUNTRIES` (line 363):

```python
    "cobalt": [180, 156, 643, 36, 586, 104, 246, 56, 124, 192],  # DRC, China, Russia, Australia, Philippines, Myanmar, Finland, Belgium, Canada, Cuba
```

- [ ] **Step 5: Add COBALT_BILATERAL_CORRIDORS and fetch function**

In `src/ingestion/comtrade.py`, add after line 374 (before the `ComtradeMaterialsClient` class):

```python
# Cobalt bilateral trade corridors for targeted queries
# Uses buyer-side mirror for DRC (DRC under-reports; query importers instead)
COBALT_BILATERAL_CORRIDORS: list[dict] = [
    # Buyer-side mirror: query IMPORTER's records for DRC origin
    {"reporter": 156, "partner": 180, "flow": "M", "label": "DRC→China (buyer-side)"},
    {"reporter": 56,  "partner": 180, "flow": "M", "label": "DRC→Belgium (buyer-side)"},
    {"reporter": 246, "partner": 180, "flow": "M", "label": "DRC→Finland (buyer-side)"},
    {"reporter": 392, "partner": 180, "flow": "M", "label": "DRC→Japan (buyer-side)"},
    # Direct export queries for reliable reporters
    {"reporter": 156, "partner": 0,   "flow": "X", "label": "China exports (world)"},
    {"reporter": 246, "partner": 0,   "flow": "X", "label": "Finland exports (world)"},
    {"reporter": 124, "partner": 0,   "flow": "X", "label": "Canada exports (world)"},
    {"reporter": 56,  "partner": 0,   "flow": "X", "label": "Belgium exports (world)"},
    {"reporter": 392, "partner": 0,   "flow": "X", "label": "Japan exports (world)"},
    # Canada import sources
    {"reporter": 124, "partner": 0,   "flow": "M", "label": "Canada imports (world)"},
]

COBALT_HS_CODES = ["2605", "810520", "810590", "282200"]
```

Then add this method inside `ComtradeMaterialsClient` (after `fetch_material_trade`, ~line 422):

```python
    async def fetch_cobalt_bilateral_flows(
        self,
        years: list[int] | None = None,
    ) -> list[ComtradeRecord]:
        """Fetch bilateral cobalt trade flows for key corridors.

        Uses buyer-side mirror for DRC corridors (DRC under-reports exports).
        Queries 4 cobalt HS codes across 10 defined corridors.

        Args:
            years: Years to query (default: [2022, 2023]).

        Returns:
            List of ComtradeRecords with bilateral trade values.
        """
        query_years = years or [2022, 2023]
        all_records: list[ComtradeRecord] = []

        for corridor in COBALT_BILATERAL_CORRIDORS:
            query = ComtradeQuery(
                reporter_codes=[corridor["reporter"]],
                partner_codes=[corridor["partner"]] if corridor["partner"] != 0 else [0],
                years=query_years,
                flow_codes=[corridor["flow"]],
                hs_codes=COBALT_HS_CODES,
            )
            logger.info("Cobalt bilateral query: %s", corridor["label"])
            try:
                records = await self.fetch(query)
                all_records.extend(records)
            except Exception:
                logger.warning("Failed cobalt corridor query: %s", corridor["label"], exc_info=True)

        logger.info("Cobalt bilateral: %d records from %d corridors", len(all_records), len(COBALT_BILATERAL_CORRIDORS))
        return all_records
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_comtrade_cobalt.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add tests/test_comtrade_cobalt.py src/ingestion/comtrade.py
git commit -m "feat(comtrade): add cobalt bilateral trade flow queries with buyer-side mirror"
```

---

### Task 2: Add Dossiers for 4 Remaining Mines

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py:623-762` (Moa JV, Voisey's Bay, Sudbury, Raglan)

- [ ] **Step 1: Add Moa JV dossier**

In `src/analysis/mineral_supply_chains.py`, add dossier block to the Moa JV mine entry (after line 656, before the closing `}}`):

```python
             "dossier": {
                 "z_score": 0.87,
                 "z_source": "parent_consolidated",
                 "z_filing": "Sherritt International FY2025 Results (Feb 2026)",
                 "insolvency_prob": 65,
                 "credit_trend": "distress",
                 "ubo_chain": [
                     "Moa JV (50/50 joint venture)",
                     "Sherritt International Corporation (TSX:S) — 50%",
                     "General Nickel Company S.A. (GNC / Cubaniquel) — 50%",
                     "Republic of Cuba (state-owned) — controls GNC",
                 ],
                 "foci_score": 92,
                 "foci_assessment": "CRITICAL",
                 "foci_detail": "50% Cuban state ownership of JV. US Helms-Burton exposure. Sole feedstock dependency on Cuba.",
                 "recent_intel": [
                     {"text": "Moa mining operations PAUSED Feb 17, 2026 — Cuban national fuel crisis after US banned Venezuelan oil shipments to Cuba", "severity": "critical", "date": "2026-02-17", "source": "Sherritt Operational Update / BNN Bloomberg"},
                     {"text": "Moa JV Phase Two expansion (6th leach train) completed and commissioned Q3 2025", "severity": "medium", "date": "2025-09-15", "source": "Sherritt Q3 2025 Results"},
                     {"text": "Cuba nationwide power outage Sep 2025 impacted Moa production", "severity": "high", "date": "2025-09-20", "source": "Sherritt Q3 2025 Results"},
                     {"text": "Sherritt settled CAD $362M of outstanding Cuban receivables via 5-year payment agreements", "severity": "medium", "date": "2025-06-01", "source": "Sherritt Press Release"},
                     {"text": "Fort Saskatchewan refinery has feed inventory to operate until ~mid-April 2026; after that production constrained", "severity": "critical", "date": "2026-02-17", "source": "Sherritt Operational Update"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_cad_m": 177.3,
                     "ebitda_cad_m": 7.1,
                     "net_loss_cad_m": 65.4,
                     "cash_cad_m": 124.9,
                     "liquidity_canada_cad_m": 43.7,
                     "total_assets_cad_m": 1382.8,
                     "total_liabilities_cad_m": 785.4,
                     "market_cap_cad_m": 99,
                     "shares_outstanding": 496_288_670,
                     "credit_rating": "DBRS B",
                     "source": "Sherritt FY2025 Results (Feb 2026)",
                     "as_of": "2025-12-31",
                 },
             },
```

- [ ] **Step 2: Add Voisey's Bay dossier**

Add dossier block to Voisey's Bay mine entry (after line 691, before closing `}}`):

```python
             "dossier": {
                 "z_score": 3.2,
                 "z_source": "parent_consolidated",
                 "z_filing": "Vale S.A. 20-F FY2025",
                 "insolvency_prob": 2,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Voisey's Bay Mine (Labrador, NL)",
                     "Vale Base Metals Ltd. (Toronto) — 90%",
                     "Vale S.A. (NYSE:VALE, B3:VALE3) — parent",
                     "Manara Minerals (Ma'aden + Saudi PIF JV) — 10% of VBM",
                     "No single controlling shareholder (Brazilian golden shares grant veto only)",
                 ],
                 "foci_score": 25,
                 "foci_assessment": "LOW-MODERATE",
                 "foci_detail": "Brazilian parent (Vale S.A.) with Saudi minority (10% PIF). No hostile foreign govt control. VBM headquartered in Toronto.",
                 "recent_intel": [
                     {"text": "VBME underground expansion completed Dec 2024 — transition from open pit to underground", "severity": "low", "date": "2024-12-15", "source": "Vale Base Metals Press Release"},
                     {"text": "Cobalt throughput test passed Sep 2025 at 93.7% of capacity (requirement was 85%)", "severity": "low", "date": "2025-09-01", "source": "Ecora Royalties Q3 2025 Trading Update"},
                     {"text": "Full ramp-up to steady-state production (2,600t/yr cobalt) expected H2 2026", "severity": "medium", "date": "2025-12-01", "source": "Vale Base Metals IR"},
                     {"text": "Glencore and Vale Base Metals evaluating joint Sudbury copper development (Mar 2026)", "severity": "low", "date": "2026-03-15", "source": "Vale Base Metals Press Release"},
                     {"text": "Q4 2025 planned maintenance reduced cobalt deliveries to 126t (vs 182t in Q3)", "severity": "low", "date": "2026-01-20", "source": "Ecora Q4 2025 Trading Update"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_usd_b": 41.4,
                     "ebitda_usd_b": 16.3,
                     "market_cap_usd_b": 64.3,
                     "net_debt_usd_b": 15.6,
                     "credit_rating": "S&P BBB- (VBM)",
                     "source": "Vale Q4 2025 Financial Results",
                     "as_of": "2025-12-31",
                     "note": "Vale S.A. parent consolidated — VBM not separately listed",
                 },
             },
```

- [ ] **Step 3: Add Sudbury Basin dossier**

Add dossier block to Sudbury Basin mine entry (after line 725, before closing `}}`):

```python
             "dossier": {
                 "z_score": 3.5,
                 "z_source": "parent_consolidated",
                 "z_filing": "Glencore 2025 Annual Report (LSE:GLEN)",
                 "insolvency_prob": 2,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Sudbury Basin Operations (Ontario)",
                     "Glencore Canada Corporation (Toronto)",
                     "Glencore plc (LSE:GLEN, Baar, Switzerland)",
                     "No single controlling shareholder (~45% individual, ~37% institutional)",
                 ],
                 "foci_score": 15,
                 "foci_assessment": "LOW",
                 "foci_detail": "Swiss-headquartered, LSE-listed. No government controlling stake. Past DOJ $1.1B DRC corruption plea (2022) but no foreign govt control.",
                 "recent_intel": [
                     {"text": "Falconbridge smelter furnace incident Jun 2025 — molten material release, facility evacuated", "severity": "high", "date": "2025-06-13", "source": "Sudbury.com / Glencore Canada"},
                     {"text": "Smelter dust fallout Sep 2025 — nickel/cobalt particles deposited on Falconbridge community; public health investigation", "severity": "high", "date": "2025-09-15", "source": "Northern Ontario Business"},
                     {"text": "Glencore held community town hall Oct 2025 to apologize for dust incidents", "severity": "medium", "date": "2025-10-15", "source": "Glencore Canada"},
                     {"text": "$1.3B Onaping Depth underground project under construction — extends mine life to 2040; all-electric fleet", "severity": "low", "date": "2025-12-01", "source": "CBC News / Glencore Canada"},
                     {"text": "Glencore-Vale joint evaluation of Sudbury copper deposits announced Mar 2026", "severity": "low", "date": "2026-03-15", "source": "Vale Base Metals Press Release"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_usd_b": 247.5,
                     "adj_ebitda_usd_b": 13.5,
                     "market_cap_usd_b": 81,
                     "total_assets_usd_b": 142.2,
                     "total_equity_usd_b": 33.6,
                     "net_debt_usd_b": 11.2,
                     "source": "Glencore Preliminary Results 2025",
                     "as_of": "2025-12-31",
                     "note": "Glencore plc parent consolidated — Sudbury not separately reported",
                 },
             },
```

- [ ] **Step 4: Add Raglan Mine dossier**

Add dossier block to Raglan Mine entry (after line 760, before closing `}}`):

```python
             "dossier": {
                 "z_score": 3.5,
                 "z_source": "parent_consolidated",
                 "z_filing": "Glencore 2025 Annual Report (LSE:GLEN)",
                 "insolvency_prob": 2,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Raglan Mine (Nunavik, Quebec)",
                     "Glencore Canada Corporation — Raglan Division",
                     "Glencore plc (LSE:GLEN, Baar, Switzerland)",
                     "No single controlling shareholder",
                 ],
                 "foci_score": 15,
                 "foci_assessment": "LOW",
                 "foci_detail": "Western-allied, Glencore-owned. Note: all cobalt exported to Nikkelverk, Norway for refining — does NOT enter Canadian domestic supply chain.",
                 "recent_intel": [
                     {"text": "Anuri mine inaugurated 2024 as part of $600M Sivumut Project — extends Raglan life 20+ years", "severity": "low", "date": "2024-06-01", "source": "Glencore Canada"},
                     {"text": "Autonomous haulage milestone achieved at Anuri using Sandvik AutoMine (Mar 2026)", "severity": "low", "date": "2026-03-18", "source": "IM Mining / Glencore"},
                     {"text": "Raglan Agreement with Inuit communities enhanced — employment, training, business participation", "severity": "low", "date": "2025-06-01", "source": "Glencore Canada Raglan"},
                 ],
                 "contracts": [],
                 "financials": {
                     "source": "Glencore plc parent consolidated (see Sudbury)",
                     "note": "Raglan not separately reported. Glencore INO combined cobalt ~600t/yr (Sudbury + Raglan + Nikkelverk)",
                 },
             },
```

- [ ] **Step 5: Run existing tests to verify no breakage**

Run: `python -m pytest tests/ -x -q`
Expected: All 219 tests pass (218 + 1 pre-existing failure in test_mitigation.py)

- [ ] **Step 6: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(cobalt): add dossiers for 4 Canadian mines (Moa JV, Voisey's Bay, Sudbury, Raglan)"
```

---

### Task 3: Add Dossiers for 6 Remaining Refineries

**Files:**
- Modify: `src/analysis/mineral_supply_chains.py:997-1157` (Umicore Kokkola, Umicore Hoboken, Fort Saskatchewan, Long Harbour, Niihama, Harjavalta)

- [ ] **Step 1: Add Umicore Kokkola dossier**

Add dossier block to Umicore Kokkola entry (after line 999, before closing `}}`):

```python
             "dossier": {
                 "z_score": 2.9,
                 "z_source": "parent_consolidated",
                 "z_filing": "Umicore FY2025 Results (Euronext: UMI)",
                 "insolvency_prob": 5,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Umicore Kokkola Refinery (Finland)",
                     "Umicore Finland Oy",
                     "Umicore SA (Euronext Brussels: UMI)",
                     "No single controlling shareholder (BlackRock 6.11%, Norges Bank 5.30%, SFPIM/Belgian state 5.00%)",
                 ],
                 "foci_score": 10,
                 "foci_assessment": "LOW",
                 "foci_detail": "Belgian-headquartered, Euronext-listed. NATO-allied. Belgian state holds 5% strategic stake via SFPIM. Acquired from Freeport Cobalt Nov 2019 for $150M.",
                 "recent_intel": [
                     {"text": "Largest cobalt refinery outside China — 15-16kt/yr capacity, expansion to 21kt/yr permitted", "severity": "low", "date": "2025-12-01", "source": "Umicore Finland / Coastline.fi"},
                     {"text": "FY2025 Cobalt & Specialty Materials revenue EUR 558M, adj. EBITDA EUR 108M", "severity": "low", "date": "2026-02-20", "source": "Umicore FY2025 Results"},
                     {"text": "EUR 350M EIB loan secured Feb 2024 for battery R&D across Kokkola, Hoboken, other sites", "severity": "low", "date": "2024-02-15", "source": "European Investment Bank Press Release"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_eur_b": 3.6,
                     "adj_ebitda_eur_m": 847,
                     "adj_ebit_eur_m": 579,
                     "market_cap_eur_b": 3.88,
                     "net_debt_eur_b": 1.4,
                     "roce_pct": 15.7,
                     "source": "Umicore FY2025 Results (Feb 2026)",
                     "as_of": "2025-12-31",
                     "note": "Umicore SA parent consolidated — Kokkola falls within Cobalt & Specialty Materials segment",
                 },
             },
```

- [ ] **Step 2: Add Umicore Hoboken dossier**

Add dossier block to Umicore Hoboken entry (after line 1030, before closing `}}`):

```python
             "dossier": {
                 "z_score": 2.9,
                 "z_source": "parent_consolidated",
                 "z_filing": "Umicore FY2025 Results (Euronext: UMI)",
                 "insolvency_prob": 5,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Umicore Hoboken Plant (Belgium)",
                     "Umicore SA (Euronext Brussels: UMI)",
                     "No single controlling shareholder",
                 ],
                 "foci_score": 10,
                 "foci_assessment": "LOW",
                 "foci_detail": "Belgium is NATO HQ nation. World's largest integrated precious metals recycling complex. 130+ years operation. Critical EU strategic recycling asset.",
                 "recent_intel": [
                     {"text": "EUR 100M expansion investment — 40% capacity increase at precious metals recycling plant", "severity": "low", "date": "2025-06-01", "source": "Umicore Hoboken Newsroom"},
                     {"text": "Large-scale battery recycling facility (150,000 t/yr) delayed from 2026 to at least 2032", "severity": "medium", "date": "2025-12-01", "source": "Green Li-ion / Umicore"},
                     {"text": "Battery recycling recovery yields >95% for cobalt, copper, nickel; >90% for lithium", "severity": "low", "date": "2025-06-01", "source": "Umicore Battery Recycling Solutions"},
                 ],
                 "contracts": [],
                 "financials": {
                     "source": "Umicore SA parent consolidated (see Kokkola)",
                     "note": "Hoboken falls within Precious Metals Refining (Recycling) business unit. 17 metals recovered including cobalt.",
                 },
             },
```

- [ ] **Step 3: Add Fort Saskatchewan dossier**

Add dossier block to Fort Saskatchewan entry (after line 1062, before closing `}}`):

```python
             "dossier": {
                 "z_score": 0.87,
                 "z_source": "computed",
                 "z_filing": "Sherritt International FY2025 Results (TSX:S)",
                 "insolvency_prob": 65,
                 "credit_trend": "distress",
                 "ubo_chain": [
                     "Fort Saskatchewan Refinery (Alberta)",
                     "Sherritt International Corporation (TSX:S)",
                     "No single controlling shareholder (widely held, TSX-listed)",
                     "Feedstock: Moa JV (50% Sherritt / 50% Republic of Cuba via GNC)",
                 ],
                 "foci_score": 82,
                 "foci_assessment": "CRITICAL",
                 "foci_detail": "Refinery is Canadian-owned but 100% feedstock dependent on Cuba. 50% of Moa JV is Cuban state. US Helms-Burton sanctions. Executives cannot travel to US.",
                 "recent_intel": [
                     {"text": "Feedstock PAUSED Feb 2026 — Moa JV suspended; refinery operating on inventory until ~mid-Apr 2026", "severity": "critical", "date": "2026-02-17", "source": "Sherritt Operational Update"},
                     {"text": "FY2025 finished cobalt production: 2,728t (100% basis); 2026 guidance: 2,750-2,850t (at risk)", "severity": "high", "date": "2026-02-15", "source": "Sherritt FY2025 Results"},
                     {"text": "Fort Saskatchewan received Copper Mark certification May 2025, pursuing Nickel Mark", "severity": "low", "date": "2025-05-01", "source": "Sherritt Press Release"},
                     {"text": "Sherritt debt restructuring completed Q1 2025 to extend maturities", "severity": "medium", "date": "2025-03-15", "source": "Sherritt Q1 2025 Results"},
                     {"text": "Only vertically integrated non-Chinese cobalt pipeline in Western hemisphere — strategic loss if idled", "severity": "critical", "date": "2026-03-01", "source": "DND Assessment"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_cad_m": 177.3,
                     "ebitda_cad_m": 7.1,
                     "net_loss_cad_m": 65.4,
                     "cash_cad_m": 124.9,
                     "total_assets_cad_m": 1382.8,
                     "total_liabilities_cad_m": 785.4,
                     "market_cap_cad_m": 99,
                     "credit_rating": "DBRS B",
                     "source": "Sherritt FY2025 Results (Feb 2026)",
                     "as_of": "2025-12-31",
                 },
             },
```

- [ ] **Step 4: Add Long Harbour NPP dossier**

Add dossier block to Long Harbour entry (after line 1093, before closing `}}`):

```python
             "dossier": {
                 "z_score": 3.2,
                 "z_source": "parent_consolidated",
                 "z_filing": "Vale S.A. 20-F FY2025",
                 "insolvency_prob": 2,
                 "credit_trend": "stable",
                 "ubo_chain": [
                     "Long Harbour Processing Plant (NL)",
                     "Vale Base Metals Ltd. (Toronto) — operator",
                     "Vale S.A. (NYSE:VALE) — 90%",
                     "Manara Minerals (Saudi PIF/Ma'aden) — 10% of VBM",
                 ],
                 "foci_score": 25,
                 "foci_assessment": "LOW-MODERATE",
                 "foci_detail": "Same ownership as Voisey's Bay. Canadian-operated facility. 10% Saudi PIF-linked stake is passive financial investment. VBM has independent Toronto board.",
                 "recent_intel": [
                     {"text": "World's first hydromet plant for hard rock sulphide concentrate (commissioned 2014) — lowest-emission nickel processing globally", "severity": "low", "date": "2025-01-01", "source": "Vale Base Metals Website"},
                     {"text": "Processing increasing volumes from Voisey's Bay underground expansion; full capacity expected H2 2026", "severity": "low", "date": "2025-12-01", "source": "Vale Base Metals IR"},
                     {"text": "Q4 2025 planned maintenance at both VB mine and Long Harbour reduced throughput", "severity": "low", "date": "2026-01-20", "source": "Ecora Royalties Q4 2025"},
                 ],
                 "contracts": [],
                 "financials": {
                     "source": "Vale S.A. parent consolidated (see Voisey's Bay)",
                     "note": "Long Harbour not separately reported. Refines Voisey's Bay concentrate — output directly linked to mine production.",
                 },
             },
```

- [ ] **Step 5: Add Niihama dossier**

Add dossier block to Niihama entry (after line 1124, before closing `}}`):

```python
             "dossier": {
                 "z_score": 3.1,
                 "z_source": "parent_consolidated",
                 "z_filing": "Sumitomo Metal Mining FY2024 (ending Mar 2025)",
                 "insolvency_prob": 3,
                 "credit_trend": "declining",
                 "ubo_chain": [
                     "Niihama Nickel Refinery (Ehime, Japan)",
                     "Sumitomo Metal Mining Co., Ltd. (TYO:5713)",
                     "Sumitomo Group keiretsu (cross-holdings, no single controller)",
                     "253 institutional holders (Vanguard, BlackRock, Fidelity, etc.)",
                 ],
                 "foci_score": 8,
                 "foci_assessment": "LOW",
                 "foci_detail": "Japanese (US treaty ally, Minerals Security Partnership member). No foreign state ownership. Feed from Philippine HPAL plants (Coral Bay + Taganito — both SMM subsidiaries).",
                 "recent_intel": [
                     {"text": "Only plant in Japan producing electrolytic cobalt — ~3,800t FY2023", "severity": "low", "date": "2025-06-01", "source": "SMM Website / Metal.com"},
                     {"text": "Battery recycling plant under construction at Niihama — 10,000t battery cells/yr, completion Jun 2026", "severity": "low", "date": "2025-09-01", "source": "Sumitomo Metal Mining News"},
                     {"text": "FY2024 net income collapsed 72% to JPY 16.5B on nickel/cobalt price weakness", "severity": "high", "date": "2025-05-15", "source": "SMM Financial Highlights"},
                     {"text": "Feed source: Taganito HPAL (Philippines) nameplate 30,000t Ni + 2,600t Co annually", "severity": "low", "date": "2025-01-01", "source": "JBIC / Philippine Resources Magazine"},
                     {"text": "Large-scale cathode active materials (CAM) production began at Niihama 2025", "severity": "low", "date": "2025-03-01", "source": "SMM Press Release"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_jpy_b": 1593,
                     "revenue_usd_b": 10.6,
                     "total_assets_jpy_b": 3069,
                     "net_assets_jpy_b": 2049,
                     "market_cap_usd_b": 17.5,
                     "net_income_jpy_b": 16.5,
                     "source": "SMM Financial Highlights FY2024 (ending Mar 2025)",
                     "as_of": "2025-03-31",
                 },
             },
```

- [ ] **Step 6: Add Harjavalta dossier**

Add dossier block to Harjavalta entry (after line 1156, before closing `}}`):

```python
             "dossier": {
                 "z_score": 2.4,
                 "z_source": "parent_consolidated",
                 "z_filing": "Nornickel FY2024 IFRS Results (Feb 2025)",
                 "insolvency_prob": 12,
                 "credit_trend": "declining",
                 "ubo_chain": [
                     "Harjavalta Refinery (Finland)",
                     "Norilsk Nickel Harjavalta Oy",
                     "PJSC MMC Norilsk Nickel (MOEX:GMKN, Russia)",
                     "Vladimir Potanin (35-37%) via Olderfrey Holdings / Interros — SANCTIONED by UK, US, Canada, Australia, NZ, Ukraine",
                     "Oleg Deripaska (27-28%) via EN+ Group / RUSAL",
                 ],
                 "foci_score": 95,
                 "foci_assessment": "CRITICAL",
                 "foci_detail": "Russian-owned refinery in NATO Finland. UBO Potanin sanctioned by 6 Western nations. Nornickel itself NOT directly sanctioned (jurisdictional gap). Russian-origin matte classified as 'Finnish' product — documented sanctions loophole (Global Witness).",
                 "recent_intel": [
                     {"text": "LME suspended Harjavalta nickel brands Oct 2024 over responsible sourcing compliance — subsequently reinstated", "severity": "high", "date": "2024-10-15", "source": "Argus Media / LME Announcements"},
                     {"text": "Global Witness report flagged sanctions gap: Russian-mined nickel enters Western markets via Finnish refinery", "severity": "critical", "date": "2025-06-01", "source": "Global Witness Report"},
                     {"text": "US Aug 2024 sanctions targeted 10 Nornickel service subsidiaries but NOT Nornickel itself or Harjavalta", "severity": "high", "date": "2024-08-15", "source": "US Treasury / Barents Observer"},
                     {"text": "Nornickel expanding Harjavalta from 75,000tpa to >100,000tpa nickel — targeting early 2026 completion", "severity": "medium", "date": "2025-01-01", "source": "Nornickel PR / NS Energy"},
                     {"text": "BASF battery materials JV at Harjavalta site received environmental permit but not yet operational", "severity": "low", "date": "2025-03-01", "source": "Mining Magazine"},
                 ],
                 "contracts": [],
                 "financials": {
                     "revenue_usd_b": 12.5,
                     "ebitda_usd_b": 5.2,
                     "net_income_usd_b": 1.8,
                     "market_cap_usd_b": 21.5,
                     "net_debt_usd_b": 8.6,
                     "source": "Nornickel FY2024 IFRS Results (Feb 2025)",
                     "as_of": "2024-12-31",
                     "note": "Nornickel parent consolidated — Harjavalta not separately reported. Potanin net worth ~$24.2B (Forbes May 2025).",
                 },
             },
```

- [ ] **Step 7: Run existing tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass (same as before)

- [ ] **Step 8: Commit**

```bash
git add src/analysis/mineral_supply_chains.py
git commit -m "feat(cobalt): add dossiers for 6 remaining refineries (Umicore, Fort Sask, Long Harbour, Niihama, Harjavalta)"
```

---

### Task 4: Confidence Triangulation and HHI Computation

**Files:**
- Modify: `src/analysis/confidence.py` (add after line 199)
- Test: `tests/test_confidence_triangulation.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_confidence_triangulation.py`:

```python
"""Tests for cobalt production data triangulation and HHI computation."""
from __future__ import annotations

import pytest
from src.analysis.confidence import (
    triangulate_cobalt_production,
    compute_cobalt_hhi,
    SourceDataPoint,
    Discrepancy,
)


class TestSourceDataPoint:
    def test_creation(self):
        s = SourceDataPoint(name="USGS MCS 2025", value_t=170000, year=2024, tier="live")
        assert s.value_t == 170000
        assert s.tier == "live"


class TestTriangulation:
    def test_single_source_low_confidence(self):
        sources = [SourceDataPoint("USGS MCS 2025", 170000, 2024, "live")]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["triangulated"] is False
        assert result["confidence_level"] in ("low", "medium")
        assert result["source_count"] == 1

    def test_three_agreeing_sources_high_confidence(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 168000, 2024, "live"),
            SourceDataPoint("Comtrade implied", 172000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert result["triangulated"] is True
        assert result["confidence_level"] == "high"
        assert result["source_count"] == 3
        # Best estimate should be close to median
        assert 165000 < result["production_t"] < 175000

    def test_discrepancy_detected(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 100000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        assert len(result["discrepancies"]) > 0
        disc = result["discrepancies"][0]
        assert disc["severity"] in ("warning", "critical")
        assert disc["delta_pct"] > 25

    def test_year_gap_noted(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 130000, 2022, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        discrepancies = result["discrepancies"]
        if discrepancies:
            assert discrepancies[0]["year_gap"] == 2

    def test_within_tolerance_no_discrepancy(self):
        sources = [
            SourceDataPoint("USGS MCS 2025", 170000, 2024, "live"),
            SourceDataPoint("BGS WMS", 167000, 2024, "live"),
        ]
        result = triangulate_cobalt_production("DRC", sources)
        # 1.8% delta — within 10% tolerance
        assert len(result["discrepancies"]) == 0


class TestHHI:
    def test_monopoly_hhi(self):
        data = {"CountryA": 100000}
        hhi = compute_cobalt_hhi(data)
        assert hhi == 10000  # 100^2

    def test_duopoly_hhi(self):
        data = {"A": 50000, "B": 50000}
        hhi = compute_cobalt_hhi(data)
        assert hhi == 5000  # 50^2 + 50^2

    def test_cobalt_realistic_hhi(self):
        data = {
            "DRC": 170000,
            "Indonesia": 12000,
            "Russia": 8900,
            "Australia": 5900,
            "Philippines": 4800,
            "Canada": 3351,
            "Cuba": 3800,
            "Madagascar": 2800,
            "Other": 19449,
        }
        hhi = compute_cobalt_hhi(data)
        # DRC 74% ≈ 5476 + rest ~400-700 = ~5900-6200
        assert 5500 < hhi < 6500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_confidence_triangulation.py -v`
Expected: FAIL — `SourceDataPoint`, `triangulate_cobalt_production`, `compute_cobalt_hhi` not defined

- [ ] **Step 3: Implement triangulation and HHI**

Add to `src/analysis/confidence.py` after line 199:

```python


# --- Cobalt Production Triangulation ---

class SourceDataPoint:
    """A single production data point from one source."""
    __slots__ = ("name", "value_t", "year", "tier")

    def __init__(self, name: str, value_t: float, year: int, tier: str = "live"):
        self.name = name
        self.value_t = value_t
        self.year = year
        self.tier = tier


def triangulate_cobalt_production(
    country: str,
    sources: list[SourceDataPoint],
) -> dict:
    """Cross-check cobalt production figures from multiple independent sources.

    Compares pairwise, detects discrepancies, and computes a confidence-weighted
    best estimate.

    Args:
        country: Country name (for labeling).
        sources: List of production data points from independent sources.

    Returns:
        dict with production_t, source_count, triangulated, confidence_score,
        confidence_level, label, sources, discrepancies.
    """
    if not sources:
        return {
            "country": country,
            "production_t": 0,
            "source_count": 0,
            "triangulated": False,
            "confidence_score": 0,
            "confidence_level": "low",
            "label": "No data",
            "sources": [],
            "discrepancies": [],
        }

    source_count = len(sources)
    discrepancies: list[dict] = []

    # Pairwise comparison
    for i in range(source_count):
        for j in range(i + 1, source_count):
            a, b = sources[i], sources[j]
            if a.value_t == 0 and b.value_t == 0:
                continue
            avg = (a.value_t + b.value_t) / 2
            if avg == 0:
                continue
            delta_pct = abs(a.value_t - b.value_t) / avg * 100
            year_gap = abs(a.year - b.year)

            if delta_pct <= 10:
                continue  # Within tolerance

            severity = "info"
            if delta_pct > 50:
                severity = "critical"
            elif delta_pct > 25:
                severity = "warning"

            note = f"{a.name} reports {a.value_t:,.0f}t ({a.year}) vs {b.name} reports {b.value_t:,.0f}t ({b.year})"
            if year_gap > 0:
                note += f" — {year_gap}-year gap may explain divergence"

            discrepancies.append({
                "source_a": a.name,
                "source_b": b.name,
                "value_a": a.value_t,
                "value_b": b.value_t,
                "delta_pct": round(delta_pct, 1),
                "year_gap": year_gap,
                "severity": severity,
                "note": note,
            })

    # Best estimate: median of most recent same-year group, else all values
    max_year = max(s.year for s in sources)
    recent = [s for s in sources if s.year == max_year]
    if not recent:
        recent = sources
    values = sorted(s.value_t for s in recent)
    mid = len(values) // 2
    production_t = values[mid] if len(values) % 2 == 1 else (values[mid - 1] + values[mid]) / 2

    # Confidence scoring
    triangulated = source_count >= 3
    has_critical_disc = any(d["severity"] == "critical" for d in discrepancies)

    if triangulated and not has_critical_disc:
        confidence_level = "high"
        confidence_score = min(80 + source_count * 5, 95)
    elif source_count >= 2 and not has_critical_disc:
        confidence_level = "medium"
        confidence_score = 60 + source_count * 5
    elif source_count >= 2 and has_critical_disc:
        confidence_level = "medium"
        confidence_score = 45
    else:
        confidence_level = "low" if source_count == 0 else "medium"
        confidence_score = 25 + source_count * 10

    confidence_score = min(confidence_score, 95)

    if triangulated:
        label = f"Triangulated ({source_count} sources)"
    elif source_count >= 2:
        label = f"Corroborated ({source_count} sources)"
    else:
        label = "Single source"

    return {
        "country": country,
        "production_t": production_t,
        "source_count": source_count,
        "triangulated": triangulated,
        "confidence_score": confidence_score,
        "confidence_level": confidence_level,
        "label": label,
        "sources": [{"name": s.name, "value_t": s.value_t, "year": s.year, "tier": s.tier} for s in sources],
        "discrepancies": discrepancies,
    }


def compute_cobalt_hhi(country_production: dict[str, float]) -> int:
    """Compute Herfindahl-Hirschman Index from country production shares.

    Args:
        country_production: Mapping of country name to production in tonnes.

    Returns:
        HHI value (0-10000). Above 2500 = highly concentrated.
    """
    total = sum(country_production.values())
    if total == 0:
        return 0
    return round(sum((v / total * 100) ** 2 for v in country_production.values()))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_confidence_triangulation.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/analysis/confidence.py tests/test_confidence_triangulation.py
git commit -m "feat(confidence): add cobalt production triangulation and HHI computation"
```

---

### Task 5: Discrepancy Alert Rule

**Files:**
- Modify: `src/analysis/cobalt_alert_engine.py:66-122` (add new rule)

- [ ] **Step 1: Add discrepancy alert rule to generate_rule_alerts()**

In `src/analysis/cobalt_alert_engine.py`, add a new rule inside `generate_rule_alerts()` after the existing "paused operations" rule (after ~line 119):

```python
    # Rule 4: Data discrepancy alert (from triangulation)
    from src.analysis.confidence import triangulate_cobalt_production, SourceDataPoint
    try:
        bgs_client = None
        nrcan_client = None
        try:
            from src.ingestion.bgs_minerals import BGSCobaltClient
            bgs_client = BGSCobaltClient()
            bgs_data = bgs_client._fallback_data()
        except Exception:
            bgs_data = []
        try:
            from src.ingestion.nrcan_cobalt import NRCanCobaltClient
            nrcan_client = NRCanCobaltClient()
            nrcan_data = nrcan_client._fallback_data()
        except Exception:
            nrcan_data = {}

        # Build DRC sources from BGS + USGS
        drc_sources = []
        for entry in bgs_data:
            if entry.get("country") == "Congo (Kinshasa)":
                drc_sources.append(SourceDataPoint("BGS WMS", entry["production_tonnes"], entry.get("year", 2022), "live"))
                break
        # USGS figure from mineral_supply_chains
        cobalt = get_mineral_by_name("Cobalt")
        if cobalt:
            mining = cobalt.get("mining", [])
            drc_mines = [m for m in mining if m.get("country") == "DRC"]
            drc_total = sum(m.get("production_t", 0) for m in drc_mines)
            if drc_total > 0:
                drc_sources.append(SourceDataPoint("USGS MCS 2025", drc_total, 2024, "live"))

        if len(drc_sources) >= 2:
            tri = triangulate_cobalt_production("DRC", drc_sources)
            for disc in tri.get("discrepancies", []):
                if disc["severity"] in ("warning", "critical"):
                    alerts.append({
                        "id": f"RULE-DISC-DRC-{len(alerts)}",
                        "title": f"Production data discrepancy: DRC cobalt — {disc['source_a']} vs {disc['source_b']} ({disc['delta_pct']}% delta)",
                        "severity": 4 if disc["severity"] == "critical" else 3,
                        "category": "Economic",
                        "sources": [disc["source_a"], disc["source_b"]],
                        "confidence": 80,
                        "coa": "Verify with Comtrade export volumes and company-reported DRC production figures",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "auto_generated": True,
                    })
    except Exception:
        logger.warning("Discrepancy alert rule failed", exc_info=True)
```

- [ ] **Step 2: Add required imports at top of file if missing**

Verify `from datetime import datetime, timezone` is at the top. If not, add it.

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/analysis/cobalt_alert_engine.py
git commit -m "feat(alerts): add data discrepancy detection rule from triangulation"
```

---

### Task 6: Comtrade Scheduler + Globe API Integration

**Files:**
- Modify: `src/ingestion/scheduler.py` (~line 363)
- Modify: `src/api/globe_routes.py` (lines 25-31)

- [ ] **Step 1: Add Comtrade cobalt monthly job to scheduler**

In `src/ingestion/scheduler.py`, add after the existing cobalt feeds job (after ~line 363):

```python
    # Comtrade cobalt bilateral trade flows — monthly
    async def refresh_comtrade_cobalt():
        import os
        from src.ingestion.comtrade import ComtradeMaterialsClient
        key = os.getenv("UN_COMTRADE_API_KEY")
        if not key:
            logger.warning("UN_COMTRADE_API_KEY not set — skipping cobalt bilateral queries")
            return
        client = ComtradeMaterialsClient(subscription_key=key)
        records = await client.fetch_cobalt_bilateral_flows()
        logger.info("Comtrade cobalt bilateral: fetched %d records", len(records))

    scheduler.add_job(
        refresh_comtrade_cobalt,
        trigger=CronTrigger(day=1, hour=6, minute=0),
        id="comtrade_cobalt",
        name="Comtrade cobalt bilateral flows",
        max_instances=1,
    )
```

- [ ] **Step 2: Enrich globe cobalt response with trade flow and confidence data**

In `src/api/globe_routes.py`, modify the `/globe/minerals/{name}` endpoint (around line 25):

```python
@router.get("/minerals/{name}")
async def get_mineral(name: str):
    """Get single mineral supply chain with enriched cobalt data."""
    from src.analysis.mineral_supply_chains import get_mineral_by_name
    mineral = get_mineral_by_name(name)
    if not mineral:
        raise HTTPException(status_code=404, detail=f"Mineral '{name}' not found")

    # Enrich cobalt with triangulation confidence
    if name.lower() == "cobalt":
        try:
            from src.analysis.confidence import triangulate_cobalt_production, compute_cobalt_hhi, SourceDataPoint
            from src.ingestion.bgs_minerals import BGSCobaltClient

            bgs = BGSCobaltClient()
            bgs_data = bgs._fallback_data()

            country_production = {}
            for entry in bgs_data:
                country_production[entry["country"]] = entry["production_tonnes"]

            mineral["hhi_live"] = compute_cobalt_hhi(country_production)
            mineral["hhi_source"] = "BGS World Mineral Statistics"
            mineral["confidence_triangulation"] = "active"
        except Exception:
            pass

    return mineral
```

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/ingestion/scheduler.py src/api/globe_routes.py
git commit -m "feat: wire Comtrade cobalt into scheduler + enrich globe API with live HHI"
```

---

### Task 7: UI Surfacing — Confidence Badges, Trade Values, Taxonomy Opacity

**Files:**
- Modify: `src/static/index.html` (lines ~7717, ~7142, ~7947, ~8255, ~8367)

- [ ] **Step 1: Add confidence badge to globe entity popups**

In `src/static/index.html`, after the flags badges (after ~line 7720), add:

```javascript
// Confidence badge
if (entity.dossier) {
    var conf = entity.dossier.foci_assessment || '';
    var confColor = conf === 'CRITICAL' ? '#ef4444' : conf === 'HIGH' ? '#f59e0b' : conf === 'LOW-MODERATE' ? '#eab308' : '#10b981';
    html += '<div style="margin-top:6px;"><span style="font-size:9px; font-family:var(--font-mono); padding:2px 6px; border-radius:4px; background:' + confColor + '22; color:' + confColor + ';">FOCI: ' + esc(conf) + '</span>';
    if (entity.dossier.z_score != null) {
        var zColor = entity.dossier.z_score > 2.99 ? '#10b981' : entity.dossier.z_score > 1.81 ? '#f59e0b' : '#ef4444';
        html += ' <span style="font-size:9px; font-family:var(--font-mono); padding:2px 6px; border-radius:4px; background:' + zColor + '22; color:' + zColor + ';">Z: ' + entity.dossier.z_score.toFixed(1) + '</span>';
    }
    html += '</div>';
}
```

- [ ] **Step 2: Add taxonomy bar confidence opacity**

In `src/static/index.html`, modify the taxonomy bar rendering (around line 7142). Change the bar `<div>` to include opacity based on source count:

```javascript
// Replace the bar fill div with confidence-aware opacity
var barOpacity = (s.sources && s.sources.length >= 3) ? '1.0' : (s.sources && s.sources.length >= 2) ? '0.85' : '0.6';
html += '<div style="width:' + s.score + '%; height:100%; background:' + c + '; opacity:' + barOpacity + '; border-radius:2px;"></div>';
```

- [ ] **Step 3: Update Overview HHI to use live value**

In `src/static/index.html`, modify the HHI display (around line 7947) to prefer `hhi_live`:

```javascript
var hhiVal = m.hhi_live || m.hhi || '--';
var hhiSource = m.hhi_source ? ' <span style="font-size:7px; color:var(--text-dim);">(' + esc(m.hhi_source) + ')</span>' : '';
html += '<div style="text-align:center;"><div class="stat-num" style="font-size:28px; color:var(--accent);">' + (typeof hhiVal === 'number' ? hhiVal.toLocaleString() : hhiVal) + '</div><div style="font-size:9px; color:var(--text-dim);">HHI' + hhiSource + '</div></div>';
```

- [ ] **Step 4: Add trade values to BOM Explorer HS codes**

In `src/static/index.html`, modify the HS code badge rendering (around line 8255):

```javascript
var tradeVal = (m.hs_trade_values && m.hs_trade_values[hs]) ? ' — $' + formatDollar(m.hs_trade_values[hs]) : '';
html += '<span style="background:rgba(0,212,255,0.08); color:var(--accent); padding:1px 6px; border-radius:3px; font-size:9px; margin-right:6px;">HS ' + esc(hs) + ': ' + esc(hsCodes[hs]) + tradeVal + '</span>';
```

- [ ] **Step 5: Add FOCI badge to Supplier Dossier header**

In `src/static/index.html`, in the dossier entity card rendering (around line 8358), add after the entity name/owner:

```javascript
if (d.foci_assessment) {
    var fc2 = d.foci_assessment === 'CRITICAL' ? '#ef4444' : d.foci_assessment === 'HIGH' ? '#f59e0b' : d.foci_assessment === 'LOW-MODERATE' ? '#eab308' : '#10b981';
    html += '<span style="font-size:9px; font-family:var(--font-mono); padding:2px 6px; border-radius:4px; background:' + fc2 + '22; color:' + fc2 + '; margin-left:8px;">FOCI: ' + esc(d.foci_assessment) + ' (' + (d.foci_score || '?') + '/100)</span>';
}
```

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/static/index.html
git commit -m "feat(ui): add confidence badges, FOCI scores, live HHI, trade values to supply chain tabs"
```

---

### Task 8: Dossier Completeness Tests

**Files:**
- Create: `tests/test_dossier_completeness.py`

- [ ] **Step 1: Write completeness tests**

Create `tests/test_dossier_completeness.py`:

```python
"""Tests to verify all 18 cobalt entities have complete dossiers."""
from __future__ import annotations

import pytest
from src.analysis.mineral_supply_chains import get_mineral_by_name


@pytest.fixture
def cobalt():
    return get_mineral_by_name("Cobalt")


class TestAllMinesHaveDossiers:
    def test_cobalt_has_mines(self, cobalt):
        assert cobalt is not None
        assert "mines" in cobalt
        assert len(cobalt["mines"]) == 9

    @pytest.mark.parametrize("mine_name", [
        "Tenke Fungurume (TFM)",
        "Kisanfu (KFM)",
        "Kamoto (KCC)",
        "Mutanda",
        "Murrin Murrin",
        "Moa JV",
        "Voisey's Bay",
        "Sudbury Basin",
        "Raglan Mine",
    ])
    def test_mine_has_dossier(self, cobalt, mine_name):
        mine = next((m for m in cobalt["mines"] if m["name"] == mine_name), None)
        assert mine is not None, f"Mine '{mine_name}' not found"
        assert "dossier" in mine, f"Mine '{mine_name}' missing dossier"

    @pytest.mark.parametrize("mine_name", [
        "Tenke Fungurume (TFM)",
        "Kisanfu (KFM)",
        "Kamoto (KCC)",
        "Mutanda",
        "Murrin Murrin",
        "Moa JV",
        "Voisey's Bay",
        "Sudbury Basin",
        "Raglan Mine",
    ])
    def test_mine_dossier_has_required_fields(self, cobalt, mine_name):
        mine = next(m for m in cobalt["mines"] if m["name"] == mine_name)
        d = mine["dossier"]
        assert "z_score" in d
        assert "credit_trend" in d
        assert "ubo_chain" in d
        assert isinstance(d["ubo_chain"], list)
        assert len(d["ubo_chain"]) >= 2
        assert "recent_intel" in d
        assert isinstance(d["recent_intel"], list)


class TestAllRefineriesHaveDossiers:
    def test_cobalt_has_refineries(self, cobalt):
        assert "refineries" in cobalt
        assert len(cobalt["refineries"]) == 9

    @pytest.mark.parametrize("refinery_name", [
        "Huayou Cobalt",
        "GEM Co.",
        "Jinchuan Group",
        "Umicore Kokkola",
        "Umicore Hoboken",
        "Fort Saskatchewan",
        "Long Harbour NPP",
        "Niihama Nickel Refinery",
        "Harjavalta",
    ])
    def test_refinery_has_dossier(self, cobalt, refinery_name):
        ref = next((r for r in cobalt["refineries"] if r["name"] == refinery_name), None)
        assert ref is not None, f"Refinery '{refinery_name}' not found"
        assert "dossier" in ref, f"Refinery '{refinery_name}' missing dossier"

    @pytest.mark.parametrize("refinery_name", [
        "Huayou Cobalt",
        "GEM Co.",
        "Jinchuan Group",
        "Umicore Kokkola",
        "Umicore Hoboken",
        "Fort Saskatchewan",
        "Long Harbour NPP",
        "Niihama Nickel Refinery",
        "Harjavalta",
    ])
    def test_refinery_dossier_has_required_fields(self, cobalt, refinery_name):
        ref = next(r for r in cobalt["refineries"] if r["name"] == refinery_name)
        d = ref["dossier"]
        assert "z_score" in d
        assert "credit_trend" in d
        assert "ubo_chain" in d
        assert isinstance(d["ubo_chain"], list)
        assert len(d["ubo_chain"]) >= 2
        assert "recent_intel" in d


class TestFOCIScoresInRange:
    def test_all_foci_scores_valid(self, cobalt):
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if "dossier" in entity and "foci_score" in entity["dossier"]:
                    score = entity["dossier"]["foci_score"]
                    assert 0 <= score <= 100, f"{entity['name']} FOCI score {score} out of range"

    def test_critical_foci_entities(self, cobalt):
        """Jinchuan, Harjavalta, Huayou should have FOCI >= 88."""
        critical_names = ["Jinchuan Group", "Harjavalta", "Huayou Cobalt"]
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if entity["name"] in critical_names and "dossier" in entity:
                    assert entity["dossier"].get("foci_score", 0) >= 88, \
                        f"{entity['name']} should have critical FOCI score"

    def test_allied_entities_low_foci(self, cobalt):
        """Voisey's Bay, Long Harbour, Umicore should have FOCI <= 30."""
        allied_names = ["Voisey's Bay", "Long Harbour NPP", "Umicore Kokkola", "Umicore Hoboken"]
        for entity_list in [cobalt["mines"], cobalt["refineries"]]:
            for entity in entity_list:
                if entity["name"] in allied_names and "dossier" in entity:
                    assert entity["dossier"].get("foci_score", 100) <= 30, \
                        f"{entity['name']} should have low FOCI score"
```

- [ ] **Step 2: Run all tests including completeness checks**

Run: `python -m pytest tests/test_dossier_completeness.py tests/test_comtrade_cobalt.py tests/test_confidence_triangulation.py -v`
Expected: ALL PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -q`
Expected: All pass (219+ tests)

- [ ] **Step 4: Commit**

```bash
git add tests/test_dossier_completeness.py
git commit -m "test: add dossier completeness, FOCI range, and triangulation tests"
```

---

## Final Verification

After all 8 tasks:

- [ ] Run `python -m pytest tests/ -v` — all tests pass
- [ ] Run `python -m src.main` — server starts, no errors
- [ ] Hit `GET /globe/minerals/cobalt` — verify all 18 entities have dossiers, `hhi_live` present
- [ ] Hit `GET /psi/alerts/cobalt/live` — verify discrepancy alerts if applicable
- [ ] Open dashboard → Supply Chain → Supplier Dossier — verify 18 entity cards with FOCI badges
- [ ] Open dashboard → Supply Chain → Overview — verify live HHI value
