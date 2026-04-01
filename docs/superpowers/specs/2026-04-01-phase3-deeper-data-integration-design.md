# Phase 3 — Deeper Data Integration Design Spec

**Date**: 2026-04-01
**Goal**: Activate Comtrade cobalt bilateral queries, fill all 15 remaining Supplier Dossiers with real sourced data, and wire BGS + NRCan + USGS + Comtrade into active confidence triangulation with discrepancy detection.
**Scope**: Cobalt only. Three workstreams: Comtrade queries, Dossier data, Confidence triangulation.
**Prerequisite**: Phase 1-2 complete (all fabricated data replaced, 7 new connectors built, IMF PCOBALT wired in).

---

## Workstream 1: Comtrade Cobalt Bilateral Queries

### 1.1 — Overview

Activate real bilateral cobalt trade queries using the Comtrade Plus API (key stored in `config/.env`), covering 4 HS codes across key corridors. Surface USD values across globe, scenario, BOM, and dossier views.

### 1.2 — Key Research Findings

- DRC export reporting is severely unreliable (4kt reported vs 86kt China received in 2018) — **must use buyer-side mirror**
- HS 282200 (cobalt oxides) is the biggest value code ($4.78B DRC exports 2023), dwarfing 2605 (ore, $63M)
- Cuba→Canada MSP trade does not appear under standard cobalt HS codes (classified as nickel intermediates)
- Missing M49 country codes in current connector: Belgium (56), Finland (246), Morocco (504), Zambia (894), Cuba (192), Madagascar (450)
- Annual data has 12-18 month lag; 2023 is the most complete year
- DRC imposed cobalt export ban Q1-Q3 2025, replaced by quotas 96,600t/yr for 2026-2027

### 1.3 — Real Trade Values (2023 baseline from WITS/Comtrade)

| Corridor | HS Code | Value (USD) | Source |
|----------|---------|------------|--------|
| DRC → China (mattes/unwrought) | 8105 | $2.39B | TrendEconomy 2023 |
| DRC → World (oxides/hydroxides) | 282200 | $4.78B | WITS 2023 |
| China → Netherlands (cobalt) | 8105 | $79M | TrendEconomy 2023 |
| China → Japan (cobalt) | 8105 | $18.1M | TrendEconomy 2023 |
| China → USA (cobalt) | 8105 | $16.4M | TrendEconomy 2023 |
| China → South Korea (cobalt) | 8105 | $14.4M | TrendEconomy 2023 |
| Canada → World (cobalt) | 8105 | $420M | TrendEconomy 2023 |
| Canada → Norway | 8105 | $78M (18.5%) | TrendEconomy 2023 |
| Canada → South Korea | 8105 | $63M (15.1%) | TrendEconomy 2023 |
| Canada → China | 8105 | $61M (14.7%) | TrendEconomy 2023 |
| Finland ← Austria (ore) | 2605 | $11.2M | WITS 2023 |
| China total ore imports | 2605 | $38.8M | TrendEconomy 2023 |

### 1.4 — Implementation

**File: `src/ingestion/comtrade.py`**

New function `fetch_cobalt_bilateral_flows()`:
- Queries 4 HS codes: 2605, 810520, 810590, 282200
- Reporter countries (7): DRC (180), China (156), Finland (246), Belgium (56), Canada (124), Australia (36), Japan (392)
- Partner countries: all (use 0 for "world"), plus specific bilateral pairs
- Uses **buyer-side mirror** for DRC corridors — query China/Belgium/Finland imports FROM DRC
- Adds missing M49 codes to `COMTRADE_COUNTRY_CODES`: Belgium (56), Finland (246), Morocco (504), Zambia (894), Cuba (192), Madagascar (450)
- Returns: `[{reporter, partner, hs_code, hs_description, value_usd, quantity_kg, year, flow_direction}]`
- Cache: 24hr TTL (data is annual)
- Rate limit: respect 500 calls/day authenticated limit; batch queries efficiently

**API key usage**: Loaded from `UN_COMTRADE_API_KEY` env var, passed as `Ocp-Apim-Subscription-Key` header (existing pattern in connector).

**Schedule**: Monthly via `scheduler.py` (data updates annually with ~12mo lag).

### 1.5 — Data Surfacing

| Surface | What Shows | How |
|---------|-----------|-----|
| Globe routes | Arc thickness ∝ trade value; tooltip: "$2.39B (HS 8105, 2023)" | Enrich `shipping_routes` with `trade_value_usd` |
| Scenario Sandbox | Real dollar values in value-at-risk calculations | Replace estimate placeholders with Comtrade values |
| BOM Explorer | USD values next to HS code entries | Add `trade_value_usd` field to HS code objects |
| Supplier Dossier | Trade context per entity | e.g., "GEM Co. receives 14,400t/yr via Glencore offtake ($2.39B corridor)" |

---

## Workstream 2: Supplier Dossiers (All 15 Entities)

### 2.1 — Overview

Fill all 15 remaining dossier entries in `mineral_supply_chains.py` with real, sourced data from corporate filings, stock exchanges, and OSINT research. Each dossier contains: Z-score/insolvency, UBO ownership chain, recent intel, DND contracts, FOCI assessment, and financial snapshot.

### 2.2 — Dossier Data Structure

```python
"dossier": {
    "z_score": 2.8,
    "z_source": "computed",        # "computed" | "estimated" | "parent_consolidated" | "not_available_unlisted_soe"
    "z_filing": "Vale S.A. 20-F FY2025",
    "insolvency_prob": "8%",
    "credit_trend": "stable",      # "stable" | "improving" | "declining" | "distress"
    "ubo_chain": [
        "Voisey's Bay Mine",
        "Vale Base Metals Ltd. (Toronto)",
        "Vale S.A. (NYSE:VALE, B3:VALE3) — 90%",
        "Manara Minerals (Saudi PIF/Ma'aden JV) — 10%",
        "No single controlling shareholder (Brazilian golden shares grant veto only)"
    ],
    "foci_score": 25,              # 0-100 scale
    "foci_assessment": "LOW-MODERATE",
    "foci_detail": "Brazilian parent with Saudi minority stake; no hostile foreign govt control",
    "recent_intel": [
        {
            "text": "VBME underground expansion completed Dec 2024; cobalt throughput test passed Sep 2025 at 93.7%",
            "severity": "low",
            "date": "2025-09",
            "source": "Vale Base Metals IR"
        }
    ],
    "contracts": "No direct DND cobalt procurement contracts identified in Open Canada disclosure data",
    "financials": {
        "revenue_usd": 41_400_000_000,
        "ebitda_usd": 16_300_000_000,
        "market_cap_usd": 64_300_000_000,
        "total_assets_usd": 94_000_000_000,
        "total_liabilities_usd": None,
        "net_debt_usd": 15_600_000_000,
        "source": "Vale Q4 2025 Financial Results",
        "as_of": "2025-12-31",
        "currency_original": "USD"
    }
}
```

### 2.3 — FOCI Scoring Scale

| Score | Level | Criteria |
|-------|-------|----------|
| 0-25 | LOW | Western-allied ownership, no foreign state stake, Five Eyes/NATO nation |
| 26-50 | MODERATE | Foreign parent but allied nation, passive sovereign wealth stake |
| 51-75 | HIGH | Adversary-adjacent, partial state control, sanctions-proximate |
| 76-100 | CRITICAL | Direct adversary state ownership, CCP/SASAC control, sanctioned UBO |

### 2.4 — Z-Score Computation Strategy

| Entity | Method | Source |
|--------|--------|--------|
| Sherritt / Fort Sask / Moa JV | Computed from TSX quarterly filings | `financial_scoring.py` |
| Vale / Voisey's Bay / Long Harbour | Computed from SEC 20-F annual | `financial_scoring.py` via SEC EDGAR |
| Glencore / Sudbury / Raglan / Mutanda / Murrin Murrin | Computed from LSE annual report | `financial_scoring.py` |
| Umicore / Kokkola / Hoboken | Computed from Euronext annual | `financial_scoring.py` |
| Sumitomo / Niihama | Computed from TYO annual | `financial_scoring.py` |
| Nornickel / Harjavalta | Computed from MOEX filing (available in English) | `financial_scoring.py` |
| Huayou Cobalt | Computed from SSE annual (English summary available) | `financial_scoring.py` |
| GEM Co. | Computed from SZSE annual | `financial_scoring.py` |
| Jinchuan Group | NOT AVAILABLE — unlisted SOE | Mark `"z_source": "not_available_unlisted_soe"` |

For subsidiary entities (Voisey's Bay, Sudbury, Raglan, Mutanda, etc.), use parent company Z-score with `"z_source": "parent_consolidated"` flag.

### 2.5 — Entity Data (All 15)

#### Canadian Entities

**1. Voisey's Bay Mine** (Labrador, NL)
- Parent: Vale Base Metals Ltd. (90% Vale S.A., 10% Manara Minerals / Saudi PIF)
- Production: ~448t cobalt FY2025 (stream to Ecora Royalties); design capacity 2,600t/yr at steady state H2 2026
- Status: OPERATING — ramping up. VBME underground expansion completed Dec 2024. Cobalt throughput test passed Sep 2025 at 93.7%.
- Financials (Vale S.A.): Revenue $41.4B, EBITDA $16.3B, market cap $64.3B, net debt $15.6B, S&P BBB-
- UBO: Vale S.A. (publicly traded, no controlling shareholder; Brazilian golden shares; Manara/PIF 10% passive)
- FOCI: 25/100 LOW-MODERATE. Brazilian parent, Saudi minority — no hostile foreign control.
- Intel: Glencore-Vale joint Sudbury copper development evaluation (Mar 2026); 2026 exploration focus on mine plan optimization.

**2. Sudbury Basin Operations** (Ontario)
- Parent: Glencore Canada Corp → Glencore plc (LSE:GLEN, Swiss)
- Production: ~300-400t cobalt est. (part of INO 600t combined with Raglan); Glencore total cobalt 36,100t FY2025
- Status: OPERATING with disruptions. Jun 2025 furnace incident at Falconbridge; Sep 2025 dust fallout on community. $1.3B Onaping Depth under construction.
- Financials (Glencore): Revenue $247.5B, adj. EBITDA $13.5B, market cap $79-84B, total assets $142.2B, net debt $11.2B
- UBO: Glencore plc (widely held, no controlling shareholder)
- FOCI: 15/100 LOW. Swiss/LSE-listed, NATO-allied. Past DRC corruption (DOJ $1.1B plea 2022) but no foreign govt control.
- Intel: Falconbridge smelter incidents (Jun-Oct 2025); Onaping Depth delays to 2026; Glencore-Vale joint evaluation.

**3. Raglan Mine** (Nunavik, Quebec)
- Parent: Glencore Canada Corp → Glencore plc
- Production: ~200-300t cobalt est. (industry estimate from ore grade); all concentrate exported to Nikkelverk, Norway
- Status: OPERATING strongly. Anuri mine inaugurated 2024 ($600M Sivumut Project). Autonomous haulage milestone Mar 2026.
- Financials: Consolidated into Glencore (see Sudbury)
- UBO: Same as Sudbury
- FOCI: 15/100 LOW. Note: cobalt exported to Norway for refining — does NOT enter Canadian domestic supply chain.
- Intel: Raglan Agreement enhanced with Inuit communities; autonomous haulage at Anuri.

**4. Fort Saskatchewan Refinery** (Alberta)
- Parent: Sherritt International (TSX:S); feedstock from Moa JV (50% Sherritt / 50% Cuban state GNC)
- Production: 2,728t cobalt FY2025; design capacity 3,800t/yr; 2026 guidance 2,750-2,850t
- Status: CRITICAL — feedstock PAUSED Feb 2026. Moa mining suspended due to Cuba fuel crisis (US ban on Venezuelan oil to Cuba). Inventory to ~mid-Apr 2026.
- Financials (Sherritt): Revenue CAD $177.3M, adj. EBITDA CAD $7.1M, net loss CAD $65.4M, cash CAD $124.9M, market cap CAD ~$99-122M, DBRS B rating
- UBO: Sherritt (Canadian, widely held) but 50% of JV is Republic of Cuba
- FOCI: 82/100 CRITICAL. 50% Cuban state control of feedstock. US Helms-Burton exposure. Sole source dependency on Cuba.
- Intel: Moa Phase Two expansion completed Q3 2025 but fuel crisis hit; debt restructuring Q1 2025; Copper Mark May 2025.

**5. Long Harbour Processing Plant** (NL)
- Parent: Vale Base Metals Ltd. (same as Voisey's Bay)
- Production: ~448t+ cobalt FY2025 (refines Voisey's Bay concentrate); design capacity 2,600t/yr
- Status: OPERATING — ramping up. World's first hydromet plant for hard rock sulphide. Lowest-emission nickel processing globally.
- Financials: Consolidated into Vale S.A. (see Voisey's Bay)
- UBO: Same as Voisey's Bay
- FOCI: 25/100 LOW-MODERATE. Same as Voisey's Bay.
- Intel: Q4 2025 planned maintenance reduced throughput; linked directly to VB underground ramp-up.

#### Western Entities

**6. Umicore Kokkola Refinery** (Finland)
- Parent: Umicore SA (Euronext Brussels: UMI)
- Capacity: 15,000-16,000t/yr cobalt refined (largest outside China); expansion to 21,000t/yr permitted
- Status: OPERATING. No disruptions. EUR 350M EIB loan for battery R&D (Feb 2024). Acquired from Freeport Cobalt Nov 2019 for $150M.
- Financials (Umicore): Revenue EUR 3.6B, adj. EBITDA EUR 847M, market cap EUR 3.88B, net debt EUR 1.4B
- Shareholders: BlackRock 6.11%, Norges Bank 5.30%, SFPIM (Belgian state) 5.00%, no controlling shareholder
- UBO: Widely held, Belgian state holds 5% strategic stake
- FOCI: 10/100 LOW. NATO-allied (Belgium), EU-regulated, ESG leader.
- Intel: FY2025 cobalt premiums improved; Specialty Materials segment EUR 558M revenue.

**7. Umicore Hoboken Plant** (Belgium)
- Parent: Umicore SA (same as Kokkola)
- Capacity: ~5,000t/yr cobalt from recycling (world's largest integrated precious metals recycling complex)
- Status: OPERATING. 40% capacity expansion ongoing (EUR 100M). Battery recycling mega-plant delayed to 2032+.
- Financials: Consolidated into Umicore (see Kokkola)
- UBO: Same as Kokkola
- FOCI: 10/100 LOW. Belgium is NATO HQ nation. Critical EU strategic recycling asset.
- Intel: Battery recycling scale-up postponed; PMR expansion continues; 17 metals recovered including cobalt.

**8. Harjavalta Refinery** (Finland)
- Parent: Norilsk Nickel Harjavalta Oy → PJSC MMC Norilsk Nickel (MOEX:GMKN, Russia)
- Capacity: ~2,500-3,500t/yr cobalt est. (not separately disclosed); nickel expanded to 75,000tpa, targeting >100,000tpa
- Status: OPERATING under regulatory pressure. LME suspended then reinstated Harjavalta nickel brands (Oct 2024). Global Witness flagged sanctions loophole.
- Financials (Nornickel): Revenue $12.5B (FY2024), EBITDA $5.2B, market cap ~$21.5B, net debt $8.6B
- UBO: **Vladimir Potanin (35-37%) via Interros** — personally sanctioned by UK, US, Canada, Australia, NZ, Ukraine. Oleg Deripaska (27-28%) via EN+/RUSAL.
- FOCI: 95/100 CRITICAL. Russian-owned in NATO Finland. UBO sanctioned by 6 Western nations. Russian-origin matte processed as "Finnish" product — sanctions loophole. Finnish govt monitoring but not intervening.
- Intel: US Aug 2024 sanctions hit 10 Nornickel subsidiaries (not Nornickel itself); BASF JV at site not yet operational; Global Witness report on sanctions gap.

**9. Niihama Nickel Refinery** (Japan)
- Parent: Sumitomo Metal Mining Co., Ltd. (TYO:5713)
- Production: ~3,800t cobalt FY2023; capacity ~4,000-4,500t/yr. Only Japanese plant producing electrolytic cobalt.
- Status: OPERATING at full capacity. Battery recycling plant under construction (completion Jun 2026, 10,000t battery cells/yr). Feed from Philippine HPAL plants (Coral Bay + Taganito).
- Financials (SMM): Revenue JPY 1,593B ($10.6B), total assets JPY 3,069B ($20.5B), market cap ~$17.5B, net income down 72% FY2024 due to price weakness
- UBO: Sumitomo Group keiretsu cross-holdings, no single controller. 253 institutional holders.
- FOCI: 8/100 LOW. Japanese (US treaty ally, AUKUS/MSP member). No foreign state ownership.
- Intel: FY2024 profit collapse on nickel/cobalt prices; FY2027 recovery target JPY 140B; large-scale CAM production began 2025 at Niihama.

**10. Moa JV / Moa Nickel Mine** (Cuba)
- Parent: 50/50 JV — Sherritt International (TSX:S) / General Nickel Company S.A. (Republic of Cuba)
- Production: 2,728t cobalt FY2025 (100% basis); design capacity 3,200t/yr; Moa Phase Two completed Q3 2025
- Status: PAUSED as of Feb 17, 2026. Mining suspended, processing on standby — Cuba fuel crisis. Fort Saskatchewan has inventory to ~mid-Apr 2026.
- Financials: Consolidated into Sherritt (see Fort Saskatchewan)
- UBO: 50% Republic of Cuba (state-owned)
- FOCI: 92/100 CRITICAL. 50% Cuban state. US Helms-Burton secondary sanctions. Cuba domestic collapse directly controls supply.
- Intel: Cuba nationwide power outage Sep 2025 impacted production; US banned Venezuelan oil to Cuba Jan 2026; Sherritt settled CAD $362M Cuban receivables.

#### Chinese Entities

**11. Huayou Cobalt** (Tongxiang, Zhejiang — SSE:603799)
- Parent: Huayou Holding Group → **Chen Xuehua** (founder, Chairman & CEO, actual controller, 23.35%)
- Capacity: 40,000t/yr cobalt refining at Tongxiang; Indonesia HPAL plants: Huayue (5kt Co/yr), Huafei (15kt Co/yr — world's largest HPAL), Huashan (15kt, under construction)
- Status: OPERATING. CDM Lubumbashi toxic dam failure Nov 2025 — suspended 3 months by DRC.
- Financials (FY2024): Revenue CNY 60.9B ($8.47B), net profit CNY 4.16B, total assets CNY 136.6B, total liabilities CNY 99.6B, market cap ~$17.3B
- UBO: Chen Xuehua (private founder). NOT state-owned but mandatory CCP party committee. Subject to MOFCOM export controls.
- FOCI: 92/100 CRITICAL. Private but CCP-directed. DRC mining via CDM subsidiary. Vertically integrated across DRC, Indonesia, China.
- Intel: CDM toxic dam failure (Nov 2025, 3-month suspension); 9M 2025 revenue +30% YoY; MOFCOM SmCo export controls Dec 2025 — precedent for broader cobalt controls.

**12. GEM Co. Ltd** (Taixing refinery, Jiangsu — SZSE:002340)
- Parent: Prof. Xu Kaihua (founder 2001, Chairman, actual controller)
- Capacity: 30,000t/yr cobalt smelting at Taixing; recycled cobalt >6,000t in 9M 2025 (350% of China's primary mining output)
- Status: OPERATING. QMB Indonesia HPAL at full 150kt Ni capacity. Glencore offtake: 14,400t cobalt hydroxide/yr through 2029.
- Financials (FY2024): Revenue CNY 33.2B, net profit CNY 1.02B, net assets CNY 19.5B, market cap CNY 43.98B
- UBO: Xu Kaihua (private academic founder). NOT state-owned but mandatory CCP party committee.
- FOCI: 88/100 CRITICAL. The Glencore offtake agreement channels Western-mined DRC cobalt through Chinese processing — strategically significant.
- Intel: QMB HPAL reached full capacity; GEM MHP output cut early 2026 tightened feedstock; Bloomberg reports GEM boosting recycling of niche metals in trade war.

**13. Jinchuan Group** (Jinchang, Gansu — unlisted SOE; HKEx:2362 subsidiary)
- Parent: **Gansu Provincial SASAC (66.03%)** → People's Government of Gansu Province → **State Council of the PRC**
- Capacity: 17,000t/yr cobalt refining (including 7,000t electrolytic); 190,000t electrolytic nickel (China's largest)
- Status: OPERATING but DRC production collapsed — FY2024 cobalt only 855t (-61%). Q1 2025 cobalt down 86.6%. NEW: Musonoi DRC (75% Jinchuan) first cobalt hydroxide Oct 2025, capacity 7,400t Co/yr.
- Financials: Parent unlisted (Revenue >CNY 300B / ~$43B, Fortune Global 500 #339). HKEx subsidiary (2362.HK): total assets $2.296B, revenue $283M H1 2024.
- UBO: **State Council of the PRC** via Gansu SASAC (66.03%). Dec 2024 restructuring added CITIC, Minmetals, Zijin — multi-SOE state consolidation.
- FOCI: 98/100 CRITICAL. **Highest-risk entity.** Direct PRC state ownership. Mandatory CCP committee. Will comply immediately with any government directive. Intelligence services have standing access.
- Intel: Dec 2024 Jinchuan Group Nickel and Cobalt Co. JV with CITIC/Minmetals/Zijin; Musonoi DRC coming online; existing DRC ops (Ruashi) in production collapse.

#### Glencore Subsidiaries

**14. Mutanda Mine** (DRC)
- Parent: Glencore plc (100%). **PENDING: Orion CMC (US DFC-backed) acquiring 40% for $9B combined with KCC** (Feb 2026 MoU).
- Production: Combined KCC+Mutanda FY2025: 33.5kt cobalt in hydroxides. Historical peak: 27.3kt cobalt in 2018 (then world's largest). Suspended Nov 2019-2022.
- Status: OPERATING but DRC export quotas severely constrain output. Mutanda 2026 quota: 6.7kt; KCC 2026: 16.1kt. No cobalt exported Q4 2025 — stored in-country. Glencore unable to provide 2026 guidance.
- Financials: Consolidated into Glencore (see Sudbury)
- UBO: Glencore plc. History: Gertler/Fleurette 31% bought out 2017 for $534M (IMF-scrutinized Gecamines sale).
- FOCI: 18/100 LOW. Western-owned, strengthened by US DFC-backed Orion CMC consortium. BUT: 14,400t/yr flows to GEM Co. (China) via Glencore offtake.
- Intel: Orion CMC $9B deal (Feb 2026) — US strategic counter to Chinese dominance; DRC export ban Q1-Q3 2025 replaced by quotas; cobalt price rallied 170%.

**15. Murrin Murrin** (Western Australia)
- Parent: Minara Resources Pty Ltd → Glencore plc (100% since Nov 2011; original $1.6B construction with Fluor Daniel)
- Production: ~2,100t cobalt FY2023 (declining from 3,400t in 2019); >50% of Australian cobalt output. HPAL laterite process.
- Status: OPERATING but declining. Nickel price weakness threatens viability. Produces LME-grade cobalt briquettes on-site (fully refined, not concentrate).
- Financials: Consolidated into Glencore
- UBO: Glencore plc
- FOCI: 12/100 LOW. Five Eyes nation (Australia, AUKUS). Fully Western-controlled. On-site refining to finished product — most secure entity from a Canadian intel perspective.
- Intel: Production declining; GISTM 2025 tailings disclosure published; construction cost overrun history ($1B→$1.6B, Fluor paid $155M settlement).

### 2.6 — Key Intelligence Findings

1. **Canada's sovereign cobalt refining is critically constrained.** Fort Saskatchewan (only vertically integrated non-Chinese pipeline) has feedstock PAUSED. Voisey's Bay/Long Harbour won't reach full capacity until H2 2026. Glencore Canadian cobalt (Sudbury + Raglan) is exported to Norway for refining.

2. **Jinchuan Group is the highest-risk entity** — direct PRC state ownership (66% Gansu SASAC), Dec 2024 multi-SOE restructuring with CITIC/Minmetals/Zijin, intelligence service access assumed.

3. **Harjavalta is a Russian-owned refinery in NATO Finland** — UBO Potanin sanctioned by 6 Western nations, but Nornickel itself not sanctioned. Russian matte processed as "Finnish" product — documented sanctions loophole.

4. **GEM Co. Glencore offtake (14,400t/yr through 2029)** channels Western-mined DRC cobalt through Chinese processing — a strategic vulnerability.

5. **Orion CMC deal (Feb 2026)** — US DFC-backed consortium buying 40% of Mutanda+KCC for $9B. Explicit Western counter to Chinese dominance in DRC cobalt.

6. **DRC export quotas 2026-2027 (96,600t/yr)** cut authorized cobalt by ~50% vs peak output. Glencore unable to provide 2026 guidance.

---

## Workstream 3: Active Confidence Triangulation

### 3.1 — Overview

Wire BGS + NRCan + USGS + Comtrade data into the confidence scoring system. Cross-check figures between sources at ingestion time. Flag discrepancies as analyst alerts.

### 3.2 — Data Sources for Triangulation

| Source | Granularity | Freshness | Endpoint |
|--------|-----------|-----------|----------|
| USGS MCS | Country-level tonnes | Annual (Jan release) | `bgs_minerals.py` fallback / CSV download |
| BGS WMS | Country-level tonnes | Annual (1-2yr lag) | OGC API: `ogcapi.bgs.ac.uk` |
| NRCan | Canada provinces | Annual | HTML scrape: `natural-resources.canada.ca` |
| Comtrade | Bilateral USD flows | Annual (12-18mo lag) | REST API: `comtradeapi.un.org` |
| Company reports | Asset-level tonnes | Quarterly | Glencore/CMOC/Sherritt/Vale connectors |

### 3.3 — Triangulation Function

**File: `src/analysis/confidence.py`**

New function `triangulate_cobalt_production(country: str) -> TriangulationResult`:

```python
@dataclass
class SourceDataPoint:
    name: str           # "USGS MCS 2025"
    value_t: float      # 170000
    year: int           # 2024
    tier: str           # "live" | "hybrid" | "seeded"

@dataclass
class Discrepancy:
    source_a: str
    source_b: str
    value_a: float
    value_b: float
    delta_pct: float
    year_gap: int       # 0 if same year
    severity: str       # "info" | "warning" | "critical"
    note: str           # human-readable explanation

@dataclass
class TriangulationResult:
    country: str
    production_t: float         # best estimate (weighted average of same-year sources)
    source_count: int
    triangulated: bool          # source_count >= 3
    confidence_score: int       # 0-100
    confidence_level: str       # "high" | "medium" | "low"
    label: str                  # "Triangulated (4 sources)"
    sources: list[SourceDataPoint]
    discrepancies: list[Discrepancy]
```

### 3.4 — Comparison Logic

1. Group sources by year. Compare same-year pairs first.
2. For cross-year comparisons (e.g., BGS 2022 vs USGS 2024), apply estimated growth rate before comparing.
3. Tolerance thresholds:
   - **≤10% delta**: CORROBORATED — sources agree within measurement variance
   - **10-25% delta**: INFO — expected variance between methodologies, log but don't alert
   - **25-50% delta**: WARNING — significant disagreement, generate analyst alert
   - **>50% delta**: CRITICAL — possible data manipulation or reporting gap, generate high-priority alert

4. Best estimate calculation:
   - Use most recent same-source data
   - Weight live sources > seeded sources
   - If multiple same-year sources, use median (robust to outliers)

### 3.5 — Discrepancy Alert Generation

When sources diverge >25% for overlapping periods, auto-generate a Watchtower alert:

```python
{
    "alert_id": "DISC-DRC-2024-001",
    "type": "data_discrepancy",
    "severity": "warning",  # or "critical"
    "title": "Production data discrepancy: DRC cobalt",
    "description": "BGS reports 130,000t (2022) vs USGS reports 170,000t (2024) — 30.7% delta. 2-year gap may explain divergence (DRC production grew ~30% 2022-2024).",
    "sources": ["BGS WMS", "USGS MCS 2025"],
    "recommended_action": "Verify with Comtrade export volumes and company-reported DRC production",
    "auto_generated": True,
    "timestamp": "2026-04-01T..."
}
```

### 3.6 — Where Confidence Surfaces

| Surface | What Shows | Implementation |
|---------|-----------|---------------|
| Risk Taxonomy bars | Solid fill = triangulated (3+ sources); translucent = 1 source | CSS opacity based on `confidence_level` |
| Globe entity popups | "Confidence: HIGH (triangulated, 4 sources)" badge | Badge in popup HTML |
| Supplier Dossier | Confidence breakdown per data dimension | New `confidence` section in dossier |
| Overview | Live-computed HHI from triangulated production figures (replaces static 5900) | `compute_hhi()` from triangulated country data |
| Watchtower Alerts | Discrepancy alerts with both figures and resolution guidance | New alert type in `cobalt_alert_engine.py` |

### 3.7 — HHI Computation

Replace static HHI 5900 with live-computed value:

```python
def compute_cobalt_hhi(triangulated_data: dict[str, TriangulationResult]) -> int:
    """Herfindahl-Hirschman Index from triangulated country production shares."""
    total = sum(t.production_t for t in triangulated_data.values())
    hhi = sum((t.production_t / total * 100) ** 2 for t in triangulated_data.values())
    return round(hhi)
```

Expected result: ~5,800-6,200 (DRC 74% ≈ 5,476 + other countries ~400-700).

---

## Files Modified

| File | Changes |
|------|---------|
| `src/ingestion/comtrade.py` | New `fetch_cobalt_bilateral_flows()`, add M49 codes |
| `src/analysis/mineral_supply_chains.py` | Fill all 15 dossiers with real data |
| `src/analysis/confidence.py` | New `triangulate_cobalt_production()`, `compute_cobalt_hhi()`, discrepancy detection |
| `src/analysis/cobalt_alert_engine.py` | New discrepancy alert type |
| `src/analysis/financial_scoring.py` | Add Z-score computation for new parent companies (Vale, Glencore, Umicore, SMM, Nornickel, Huayou, GEM) |
| `src/api/globe_routes.py` | Enrich cobalt response with trade flow values, confidence badges |
| `src/api/psi_routes.py` | Live HHI, trade values in scenarios, confidence in taxonomy |
| `src/ingestion/scheduler.py` | Add Comtrade cobalt monthly schedule |
| `src/static/index.html` | Confidence badges on taxonomy/globe/dossier; trade values in BOM/globe; HHI update |

## New Tests

| Test File | Coverage |
|-----------|----------|
| `tests/test_comtrade_cobalt.py` | Bilateral query mocking, M49 codes, buyer-side mirror, response parsing |
| `tests/test_confidence_triangulation.py` | Multi-source comparison, discrepancy detection, HHI computation, year-gap handling |
| `tests/test_dossier_completeness.py` | All 18 entities have dossier, required fields present, FOCI scores in range |

## Implementation Priority

| Step | What | Impact |
|------|------|--------|
| 1 | Fill all 15 dossiers in `mineral_supply_chains.py` | Closes biggest data gap — all entities have real intelligence |
| 2 | Comtrade bilateral queries | Adds real trade flow USD values to analysis |
| 3 | Confidence triangulation + HHI | Adds analytical rigor, discrepancy detection |
| 4 | UI surfacing (globe, BOM, taxonomy, dossier badges) | Makes new data visible |
| 5 | Tests | Validates all new data and logic |
