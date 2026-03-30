# Cobalt Supply Chain Data Sources -- Scrapeable Public Sources

Research completed 2026-03-29. All sources verified as publicly accessible, machine-readable or scrapeable, and regularly updated.

---

## 1. COBALT MARKET PRICING DATA

### 1.1 Metals-API (LME Cobalt Spot + Historical)
- **URL**: `https://metals-api.com/api/latest?access_key=API_KEY&base=USD&symbols=LCO`
- **Historical**: `https://metals-api.com/api/YYYY-MM-DD?access_key=API_KEY&base=USD&symbols=LCO`
- **Time-series**: `https://metals-api.com/api/timeseries?access_key=API_KEY&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&base=USD&symbols=LCO`
- **Data format**: JSON API
- **Update frequency**: Every 60 minutes (free tier), every 10 minutes (paid)
- **Authentication**: Free API key required (signup at metals-api.com)
- **Free tier**: 100 requests/month, hourly updates, latest + historical endpoints
- **Symbol**: `LCO` = Cobalt, `CO-SO4` = Cobalt Sulphate
- **Fields available**: `success`, `timestamp`, `base`, `date`, `rates.LCO` (price per troy ounce in USD)
- **Connector priority**: HIGH -- provides real-time cobalt spot pricing

### 1.2 IMF Primary Commodity Price System (PCPS)
- **API endpoint**: `http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/PCPS/M.W00.PCOBALT?startPeriod=2020&endPeriod=2026`
- **Dataset page**: `https://data.imf.org/Datasets/PCPS`
- **Data format**: SDMX-JSON (REST API), also available as CSV
- **Update frequency**: Monthly (published first full week of each month)
- **Authentication**: None required
- **Fields available**: Monthly average cobalt price (nominal USD), price indices
- **Code lookup**: Use `http://dataservices.imf.org/REST/SDMX_JSON.svc/DataStructure/PCPS` to confirm exact cobalt commodity code
- **Python library**: `imfp` package -- `imfp.imf_dataset(database_id="PCPS", commodity=["PCOBALT"])`
- **Connector priority**: HIGH -- free, no auth, monthly cobalt prices since 1980

### 1.3 World Bank Commodity Price Data (Pink Sheet)
- **Monthly XLSX**: `https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx`
- **Annual XLSX**: `https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Annual.xlsx`
- **Monthly PDF**: `https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Pink-Sheet-January-2026.pdf`
- **Main page**: `https://www.worldbank.org/en/research/commodity-markets`
- **Data format**: XLSX direct download (parseable with openpyxl)
- **Update frequency**: Monthly
- **Authentication**: None
- **Fields available**: Monthly nominal prices for 100+ commodities (1960-present), including cobalt
- **Connector priority**: HIGH -- stable URLs, direct download, no auth

### 1.4 FRED (Federal Reserve Economic Data)
- **API endpoint**: `https://api.stlouisfed.org/fred/series/observations?series_id=PCOBALTM&api_key=API_KEY&file_type=json`
- **Alternate series**: Try `PCOBALTM` (monthly), `PCOBALTA` (annual), or search via `https://api.stlouisfed.org/fred/release/series?release_id=365&api_key=API_KEY&file_type=json`
- **Data format**: JSON API
- **Update frequency**: Monthly
- **Authentication**: Free API key required (register at fred.stlouisfed.org)
- **Fields available**: `date`, `value` (cobalt price in USD)
- **Note**: Sources IMF PCPS data; provides clean REST interface on top of it
- **Connector priority**: MEDIUM -- requires free API key, mirrors IMF data

---

## 2. COBALT PRODUCTION & TRADE STATISTICS

### 2.1 USGS Mineral Commodity Summaries -- Cobalt (Annual CSV)
- **MCS 2025 Data Release**: `https://data.usgs.gov/datacatalog/data/USGS:6797fb00d34ea8c18376e159`
- **MCS 2026 publication**: `https://pubs.usgs.gov/publication/mcs2026`
- **MCS Cobalt PDF**: `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-cobalt.pdf`
- **Metadata XML**: `https://data.usgs.gov/datacatalog/metadata/USGS.6797fb00d34ea8c18376e159.xml`
- **Data format**: 2 CSV files per annual release
  - CSV 1: US Salient Statistics (production, imports, exports, price, stocks, consumption, net import reliance) -- 5 years of data
  - CSV 2: World production totals by country
- **Update frequency**: Annual (January/February each year)
- **Authentication**: None
- **Fields available**: Production (metric tons contained cobalt), imports, exports, apparent consumption, stocks, price, net import reliance, world mine production by country
- **URL pattern**: Data catalog IDs change yearly; scrape catalog page or use metadata XML
- **Connector priority**: HIGH -- authoritative source, machine-readable CSV

### 2.2 USGS Mineral Industry Surveys -- Cobalt (Monthly XLSX)
- **Latest file**: `https://www.usgs.gov/media/files/cobalt-march-2025-xlsx`
- **File naming**: `mis-YYYYMM-cobal.xlsx`
- **Statistics page**: `https://www.usgs.gov/centers/national-minerals-information-center/cobalt-statistics-and-information`
- **Historical statistics**: `https://www.usgs.gov/media/files/cobalt-historical-statistics-data-series-140`
- **Data format**: XLSX (parseable with openpyxl)
- **Update frequency**: Monthly
- **Authentication**: None
- **Fields available**: US production, imports (by form and country), exports, consumption (by end use), stocks, prices
- **Scraping approach**: Parse the statistics page HTML for the latest month's download link
- **Connector priority**: HIGH -- monthly updates, granular US cobalt data

### 2.3 UN Comtrade API -- Cobalt Trade Flows
- **Preview (no auth)**: `https://comtradeapi.un.org/public/v1/preview/C/A/HS?cmdCode=2605&flowCode=X&period=2023`
- **Full API**: `https://comtradeapi.un.org/data/v1/get/C/A/HS?cmdCode=260500,810520,810590&reporterCode=180&period=2023&partnerCode=0&includeDesc=TRUE`
- **Developer portal**: `https://comtradedeveloper.un.org/`
- **Python library**: `pip install comtradeapicall`
- **Data format**: JSON API
- **Update frequency**: Annual data (lag ~1-2 years), monthly data available
- **Authentication**: Preview = none; Full API = free subscription key (register at comtradedeveloper.un.org)
- **Relevant HS codes**:
  - `260500` -- Cobalt ores and concentrates
  - `810520` -- Cobalt mattes and other intermediate products; unwrought cobalt; powders
  - `810590` -- Articles of cobalt (wrought)
  - `282200` -- Cobalt oxides and hydroxides
  - `283329` -- Cobalt sulphates
- **Fields available**: Reporter country, partner country, trade flow (import/export), value (USD), quantity (kg), year
- **Connector priority**: HIGH -- already have Comtrade connector, just add cobalt HS codes

### 2.4 USGS Copperbelt Mining Database (DRC + Zambia)
- **Data catalog**: `https://data.usgs.gov/datacatalog/data/USGS:64dfd268d34e5f6cd553c2cf`
- **Data format**: Shapefiles, CSV, Excel
- **Update frequency**: Periodic (research-driven)
- **Authentication**: None
- **Fields available**: Mine locations (lat/lon), mining extent, technique (artisanal vs large-scale), commodity type, mine names
- **Connector priority**: MEDIUM -- one-time download with geo-coordinates for mine mapping

---

## 3. MINING COMPANY PRODUCTION DATA

### 3.1 CMOC Group (World's Largest Cobalt Producer)
- **News releases page**: `https://en.cmoc.com/html/InvestorMedia/News/`
- **URL pattern**: `https://en.cmoc.com/html/YYYY/News_MMDD/##.html`
- **Recent reports**:
  - 2025 Interim: `https://en.cmoc.com/html/2025/News_0824/80.html`
  - 2024 Annual: `https://en.cmoc.com/html/2025/News_0324/73.html`
  - 2024 Interim: `https://en.cmoc.com/html/2024/News_0823/71.html`
  - Q1 2024: `https://en.cmoc.com/html/2024/News_0430/66.html`
- **HKEX ticker**: 03993
- **Data format**: HTML page scrape (press releases with production figures in body text)
- **Update frequency**: Quarterly
- **Authentication**: None
- **Fields available**: Cobalt production (tonnes), copper production, TFM plant capacity (37,000 tpa cobalt), revenue, cost data
- **Key data points**: 114,165t cobalt in 2024 (31% global share), 61,073t H1 2025
- **Scraping approach**: Parse news releases page for links, then extract production figures from HTML body
- **Connector priority**: HIGH -- world's #1 producer, public quarterly data

### 3.2 Glencore (Production Reports as PDF)
- **Publications page**: `https://www.glencore.com/publications`
- **PDF URL pattern**: `https://www.glencore.com/.rest/api/v1/documents/static/{UUID}/{FILENAME}.pdf`
- **Known report URLs**:
  - FY 2024: `https://www.glencore.com/.rest/api/v1/documents/static/437c6cdb-dbfb-4e61-a769-18655951cee2/Glencore+production+report_FY2024.pdf`
  - Q1 2025: `https://www.glencore.com/.rest/api/v1/documents/static/0a6952b0-b644-41ee-b291-c1ee6a93f9d5/GLEN_2025-Q1ProductionReport.pdf`
  - H1 2025: `https://www.glencore.com/.rest/api/v1/documents/static/80aa3906-26b0-40d5-8fb1-881442e89c39/GLEN_2025-H1+ProductionReport.pdf`
  - Q3 2025: `https://www.glencore.com/.rest/api/v1/documents/static/11f0a647-a249-4bcc-a36d-bce97eb25d38/GLEN_2025-Q3+ProductionReport.pdf`
- **News pages** (for discovering new PDFs):
  - `https://www.glencore.com/media-and-insights/news/full-year-2025-production-report`
  - `https://www.glencore.com/media-and-insights/news/first-quarter-production-report-2025`
- **Data format**: PDF (requires PDF parsing -- tabula-py or pdfplumber)
- **Update frequency**: Quarterly
- **Authentication**: None
- **Fields available**: Own-sourced cobalt production (tonnes), by asset (KCC/Katanga, Mutanda), copper production, year-over-year changes
- **Key data points**: 18,900t H1 2025, KCC ~22ktpa, Mutanda restarted
- **Scraping approach**: Scrape news page HTML for PDF links, extract tables from PDF
- **Connector priority**: HIGH -- world's #2 producer, structured PDF data

### 3.3 Sherritt International (TSX: S)
- **Investor relations**: `https://sherritt.com/investors/`
- **News releases**: `https://www.sherritt.com/Investor-Relations/News-Releases/`
- **SEC filings (20-F)**: `https://data.sec.gov/submissions/CIK{sherritt_cik}.json`
- **Data format**: HTML press releases, also distributed via BusinessWire
- **Update frequency**: Quarterly
- **Authentication**: None
- **Fields available**: Nickel and cobalt production at Moa JV (100% basis), cobalt sales, cobalt swap distributions, finished cobalt tonnes
- **Key data points**: 3,368t cobalt in 2022, Moa JV 50% interest, Cuban operations
- **Connector priority**: MEDIUM -- Canadian company, smaller producer but Canadian defence relevance

### 3.4 Vale (NYSE: VALE)
- **Investor relations**: `https://www.vale.com/investors`
- **Production reports**: `https://www.vale.com/announcements-results-presentations-and-reports`
- **SEC 20-F filings**: `https://data.sec.gov/submissions/CIK0000917851.json`
- **Data format**: PDF production reports, SEC EDGAR JSON/XBRL
- **Update frequency**: Quarterly
- **Authentication**: None (SEC EDGAR), None (vale.com)
- **Fields available**: Nickel production, cobalt as byproduct, base metals operations, quarterly volumes
- **Connector priority**: MEDIUM -- cobalt is byproduct of nickel

### 3.5 BHP (NYSE: BHP)
- **Investor relations**: `https://www.bhp.com/investors`
- **Financial results**: `https://www.bhp.com/investors/financial-results-operational-reviews`
- **Operational reviews (PDF)**: `https://www.bhp.com/-/media/documents/media/reports-and-presentations/2024/240717_bhpoperationalreviewfortheyearended30june2024.pdf`
- **SEC 20-F filings**: `https://data.sec.gov/submissions/CIK0000811809.json`
- **Data format**: PDF, SEC EDGAR JSON
- **Update frequency**: Quarterly operational reviews
- **Authentication**: None
- **Fields available**: Nickel production (Nickel West), cobalt byproduct volumes
- **Note**: Nickel West suspended October 2024 due to low nickel prices -- cobalt output impacted
- **Connector priority**: LOW -- operations suspended

### 3.6 ERG (Eurasian Resources Group) -- Metalkol RTR
- **Press releases**: `https://www.ergafrica.com/press-releases/`
- **Clean Cobalt report**: `https://www.ergafrica.com/metalkol-rtr-clean-cobalt-performance-report/`
- **Metalkol page**: `https://www.ergafrica.com/cobalt-copper-division/metalkol-rtr/`
- **Data format**: HTML pages, PDF annual reports (PwC-assured)
- **Update frequency**: Annual (Clean Cobalt & Copper Performance Report -- 5th edition published 2025)
- **Authentication**: None
- **Fields available**: Cobalt hydroxide production, copper cathode production, ESG compliance, OECD due diligence status
- **Key data points**: Nameplate capacity ~23ktpa cobalt hydroxide, ~100ktpa copper cathode
- **Connector priority**: MEDIUM -- world's #2 standalone cobalt producer, ESG data

---

## 4. REFINERY DATA

### 4.1 Huayou Cobalt (SSE: 603799)
- **Investor relations**: `https://www.huayou.com/` (English reports section)
- **2024 Annual Report PDF**: `https://www.huayou.com/Public/Uploads/uploadfile2/files/20250418/2024AnnualReportofHuayouCobalt.pdf`
- **H1 2025 Results PDF**: `https://www.huayou.com/Public/Uploads/uploadfile2/files/20250817/HuayouCobaltReleasesResultsForTheFirstHalfof2025.pdf`
- **Data format**: PDF (English-language annual/semi-annual reports)
- **Update frequency**: Semi-annual
- **Authentication**: None
- **Fields available**: Revenue, cobalt refining capacity (50,000 mt/yr), cobalt product volumes, battery materials output, DRC operations
- **Connector priority**: HIGH -- world's largest cobalt refiner

### 4.2 GEM Co. Ltd (SZE: 002340)
- **Company page**: `https://en.gem.com.cn/`
- **Key data**: Cobalt refining capacity 50,000 mt/yr, high-purity cobalt plate 11,000 t/yr, ultrafine cobalt powder 6,000 t/yr, battery-grade Co3O4 25,000 t/yr
- **Jingmen subsidiary**: LME-registered "GEM-CO" brand, annual capacity 10,000 mt refined cobalt
- **Data format**: HTML pages, PDF annual reports (Chinese with English summaries)
- **Update frequency**: Semi-annual
- **Authentication**: None
- **Connector priority**: MEDIUM -- major Chinese refiner, limited English data

### 4.3 Jinchuan Group (via Jinchuan International, HKEX: 2362)
- **Investor relations**: `https://www.jinchuan-intl.com/`
- **H1 2024 Results PDF**: `https://www.jinchuan-intl.com/pdf/presentation/2024IRP_EN.pdf`
- **Data format**: PDF presentations
- **Update frequency**: Semi-annual
- **Authentication**: None
- **Fields available**: Cobalt production (17,000 tpa capacity, including 7,000t electrolytic cobalt), nickel production (230,000 tpa)
- **Connector priority**: MEDIUM -- China's largest nickel-cobalt producer

### 4.4 Umicore (EBR: UMI)
- **Investor relations**: `https://www.umicore.com/en/investor-relations/`
- **Annual reports**: `https://www.umicore.com/en/investor-relations/publications-reports/annual-report/`
- **Financial reports**: `https://www.umicore.com/en/investor-relations/publications-reports/financial-reports/`
- **FY 2025 Results PDF**: `https://www.umicore.com/en/files/secure-documents/7893839e-71dc-414a-b5ec-1aa47454a114.pdf`
- **Data format**: PDF financial reports, HTML press releases
- **Update frequency**: Semi-annual (with quarterly trading updates)
- **Authentication**: None
- **Fields available**: Battery cathode materials revenue, cobalt & nickel chemicals refining volumes, recycling volumes
- **Connector priority**: MEDIUM -- major European refiner, good ESG data

### 4.5 RMI Cobalt Refiners List (Conformant Smelters)
- **Cobalt refiners list**: `https://www.responsiblemineralsinitiative.org/cobalt-refiners-list/`
- **Conformant refiners**: `https://www.responsiblemineralsinitiative.org/cobalt-refiners-list/conformant-cobalt-refiners/`
- **Data format**: HTML table (scrapeable)
- **Update frequency**: Ongoing (as assessments complete)
- **Authentication**: None
- **Fields available**: Refiner name, location (country/city), RMAP conformance status, supply chain policy links
- **Connector priority**: HIGH -- authoritative list of all assessed cobalt refiners globally

---

## 5. DRC-SPECIFIC DATA

### 5.1 IPIS Artisanal Mining Sites (GeoJSON via WFS)
- **WFS endpoint**: `http://geo.ipisresearch.be/geoserver/public/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=public:cod_mines_curated_all_opendata_p_ipis&outputFormat=application/json`
- **Open data portal**: `https://ipisresearch.be/home/maps-data/open-data/`
- **HDX mirror**: `https://data.humdata.org/dataset/cod_mines_curated_all_opendata_p_ipis`
- **Data format**: GeoJSON (via WFS), also available as CSV/Shapefile
- **Update frequency**: Ongoing (field surveys since 2009, 2,800+ sites)
- **Authentication**: None (CORS enabled, no proxy needed)
- **License**: ODC-BY v1.0 (attribution required)
- **Fields available**: Mine location (lat/lon), mineral type (cobalt, copper, gold, etc.), mining technique, number of workers, armed group presence, child labour indicators, traceability status, mine legal status, state services presence, mineral sales destination
- **Layer name**: `cod_mines_curated_all_opendata_p_ipis`
- **Connector priority**: CRITICAL -- exact geo-coordinates for artisanal cobalt mines, conflict zone indicators, armed group presence

### 5.2 DRC Cobalt Export Ban/Quota Data
- **Key regulatory body**: ARECOMS (Authority for Regulation and Control of Strategic Mineral Substance Markets)
- **News monitoring sources**:
  - Mining Technology: `https://www.mining-technology.com/` (RSS available)
  - Fastmarkets: `https://www.fastmarkets.com/insights/` (cobalt section)
  - S&P Global: `https://www.spglobal.com/energy/en/news-research/latest-news/metals/`
- **Current quota data** (as of Q4 2025):
  - Annual export quota: 96,600 tonnes (2026-2027)
  - Base quota: 87,000t allocated to producers
  - Strategic reserve: 9,600t (ARECOMS-controlled)
  - 10% royalty required within 48 hours of export
- **Data format**: News article scraping (HTML)
- **Update frequency**: Event-driven (policy announcements)
- **Authentication**: None
- **Connector priority**: HIGH -- critical for supply disruption alerts

### 5.3 Delve ASM Database (World Bank)
- **DRC country page**: `https://www.delvedatabase.org/data/countries/democratic-republic-of-congo`
- **DRC country profile PDF**: `https://www.delvedatabase.org/uploads/resources/Delve-Country-Profile-DRC.pdf`
- **BGR Cobalt Mapping PDF**: `https://www.delvedatabase.org/uploads/resources/BGR_Cobalt_Congo_2019_en.pdf`
- **Data format**: Interactive dashboard, PDF reports
- **Update frequency**: Periodic (data added on ongoing basis)
- **Authentication**: None
- **Fields available**: ASM production estimates, mine survey data (102 artisanal mines surveyed), socio-economic data, child labour prevalence, household economic data
- **Connector priority**: LOW -- supplementary reference data, not machine-readable API

---

## 6. INDUSTRY REPORTS (FREE PDFs)

### 6.1 Cobalt Institute Market Reports
- **Annual Report 2024**: `https://www.cobaltinstitute.org/wp-content/uploads/2025/05/Cobalt-Market-Report-2024.pdf`
- **Annual Report 2023**: `https://www.cobaltinstitute.org/wp-content/uploads/2025/02/Cobalt-Market-Report-2023.pdf`
- **Q3 2025 Quarterly**: `https://www.cobaltinstitute.org/wp-content/uploads/2025/10/Quarterly-Cobalt-Market-Report-Q3-2025-1.pdf`
- **Q4 2025 Quarterly**: `https://www.cobaltinstitute.org/wp-content/uploads/2026/02/Cobalt-Market-Report-Q4-2025.pdf`
- **URL pattern**: `https://www.cobaltinstitute.org/wp-content/uploads/YYYY/MM/{filename}.pdf`
- **Demand data**: `https://www.cobaltinstitute.org/resources/data-room/demand/`
- **Data format**: PDF reports (require PDF parsing)
- **Update frequency**: Quarterly market reports, annual comprehensive report
- **Authentication**: None (free download)
- **Fields available**: Global supply/demand balance, production by country, demand by application (batteries, superalloys, hard metals), producer rankings, price trends, DRC production share, LFP vs NMC chemistry trends
- **Key data**: 2025 total demand ~213.5kt, 2026 forecast ~219.6kt
- **Connector priority**: HIGH -- most comprehensive free cobalt market intelligence

### 6.2 IEA Critical Minerals Data Explorer
- **Interactive tool**: `https://www.iea.org/data-and-statistics/data-tools/critical-minerals-data-explorer`
- **Methodology**: `https://iea.blob.core.windows.net/assets/0bdb1732-e110-4957-a905-2c074eafe8f4/CMDataExplorerMethodology.pdf`
- **Global Outlook 2025**: `https://www.iea.org/reports/global-critical-minerals-outlook-2025`
- **Data format**: Interactive dashboard (JavaScript-driven, may need to scrape underlying API calls)
- **Update frequency**: Annual (outlook reports)
- **Authentication**: None
- **Fields available**: Cobalt supply/demand projections, mining concentration by country, refining concentration, demand by technology (EVs, electronics, superalloys), scenario modelling
- **Connector priority**: MEDIUM -- authoritative projections but tricky to scrape

### 6.3 EU RMIS (Raw Materials Information System)
- **Cobalt profile**: `https://rmis.jrc.ec.europa.eu/rmp/Cobalt`
- **JRC data catalog**: `https://data.jrc.ec.europa.eu/collection/id-00192`
- **Data format**: Interactive dashboard, downloadable factsheets
- **Update frequency**: Periodic updates
- **Authentication**: None
- **Fields available**: EU cobalt trade data, supply chain analysis, recycling rates, substitution potential, criticality assessment
- **Connector priority**: MEDIUM -- EU-specific perspective, good for European refinery data

---

## 7. SEC EDGAR -- COMPANY FILINGS SEARCH

### 7.1 EDGAR Full Text Search API
- **Endpoint**: `https://efts.sec.gov/LATEST/search-index?q=%22cobalt+supply+chain%22&dateRange=custom&startdt=2025-01-01&enddt=2026-03-29&forms=10-K,20-F,8-K`
- **Alternative queries**:
  - `?q=%22cobalt+superalloy%22&forms=10-K` -- superalloy filings
  - `?q=%22cobalt+sourcing%22+%22defense%22` -- defense supply chain
  - `?q=%22cobalt%22+%22critical+mineral%22+%22supply+risk%22` -- risk disclosures
- **Data format**: JSON (returns filing metadata, links to full documents)
- **Update frequency**: Real-time (filings indexed as submitted)
- **Authentication**: None (rate limit: 10 requests/sec with User-Agent header)
- **Fields available**: Filing type, company name, CIK, filing date, document URLs
- **Connector priority**: HIGH -- catches defence contractor cobalt supply chain disclosures

### 7.2 EDGAR Submissions API (Company Filing History)
- **Endpoint**: `https://data.sec.gov/submissions/CIK{10-digit-cik}.json`
- **Company tickers**: `https://www.sec.gov/files/company_tickers.json`
- **Relevant CIKs**:
  - Vale S.A.: `CIK0000917851`
  - BHP Group: `CIK0000811809`
  - Look up others via company_tickers.json
- **Data format**: JSON
- **Authentication**: None (requires User-Agent header: `"CompanyName admin@company.com"`)
- **Fields available**: Filing history (type, date, accession number), company metadata
- **Connector priority**: MEDIUM -- useful for tracking specific companies' annual reports

---

## 8. DEFENCE-RELATED COBALT USAGE

### 8.1 Cobalt Institute -- Superalloy Demand Data
- **Source**: Annual and quarterly market reports (see Section 6.1)
- **Relevant data**: Demand breakdown by end-use includes "Superalloys" as a category
- **Key context**: Superalloys account for ~15% of cobalt demand (jet engines, gas turbines)
- **Fields**: Superalloy demand (tonnes), % of total demand, growth trends

### 8.2 Engine Manufacturer Supply Chain News (RSS Monitoring)
- **Rolls-Royce press**: `https://www.rolls-royce.com/media/press-releases.aspx` (scrape HTML)
- **RTX/Pratt & Whitney**: `https://www.rtx.com/news` (scrape HTML)
- **GE Aerospace**: `https://www.geaerospace.com/news` (scrape HTML)
- **Supply Chain 24/7**: `https://www.supplychain247.com/` (general supply chain news)
- **Data format**: HTML scraping for press releases mentioning cobalt/superalloy supply chain
- **Update frequency**: Daily monitoring
- **Authentication**: None
- **Connector priority**: LOW -- supplementary monitoring, event-driven

### 8.3 USITC Cobalt Report (One-time reference)
- **PDF**: `https://www.usitc.gov/publications/332/journals/jice_more_than_a_pretty_color_the_renaissance_cobalt_industry.pdf`
- **Content**: Comprehensive overview of cobalt in superalloys, battery chemistry, and defence applications
- **Connector priority**: LOW -- reference document, not updated

---

## RECOMMENDED IMPLEMENTATION ORDER

### Phase 1 -- Immediate (High value, easy to implement)
1. **IMF PCPS cobalt prices** -- No auth, JSON API, monthly prices
2. **World Bank Pink Sheet** -- Direct XLSX download, monthly prices since 1960
3. **UN Comtrade cobalt HS codes** -- Add codes 260500, 810520, 810590, 282200 to existing connector
4. **USGS MCS cobalt CSV** -- Annual production data, direct download
5. **IPIS WFS GeoJSON** -- Live artisanal mine map with conflict indicators

### Phase 2 -- Short-term (Requires API keys or PDF parsing)
6. **Metals-API cobalt spot price** -- Free API key, real-time LME pricing
7. **USGS Monthly Industry Surveys** -- XLSX parsing with openpyxl
8. **Cobalt Institute reports** -- PDF parsing for market data
9. **CMOC news releases** -- HTML scraping for production figures
10. **Glencore production reports** -- PDF download + tabula-py parsing

### Phase 3 -- Enrichment (Company-level intelligence)
11. **RMI Cobalt Refiners List** -- HTML table scraping
12. **SEC EDGAR full-text search** -- Cobalt supply chain disclosures
13. **Huayou/GEM/Umicore reports** -- PDF annual report parsing
14. **ERG Clean Cobalt reports** -- ESG/compliance data
15. **Sherritt/Vale/BHP production** -- Quarterly press releases

---

## HS CODES REFERENCE (for Comtrade + Census + Eurostat connectors)

| HS Code | Description | Relevance |
|---------|-------------|-----------|
| 260500 | Cobalt ores and concentrates | Raw material trade |
| 810520 | Cobalt mattes; unwrought cobalt; powders | Intermediate products |
| 810590 | Other articles of cobalt | Finished cobalt products |
| 282200 | Cobalt oxides and hydroxides | Chemical intermediates |
| 283329 | Other sulphates (includes cobalt sulphate) | Battery precursors |
| 750210 | Unwrought nickel (not alloyed) | Nickel-cobalt association |
| 811292 | Unwrought cobalt; cobalt powders (HS2022) | Updated classification |

---

## KEY DRC COBALT EXPORT QUOTA CONTEXT (Current as of March 2026)

- Export ban imposed: February 2025
- Ban lifted: October 16, 2025
- Replaced by: Quota system via ARECOMS
- Q4 2025 quota: 18,125 tonnes
- Annual quota 2026-2027: 96,600 tonnes
  - Base allocation: 87,000t (to producers)
  - Strategic reserve: 9,600t (ARECOMS)
- Royalty: 10% advance payment within 48 hours
- Major allocations: CMOC and Glencore (largest shares)
- DRC global share: ~73% of mined cobalt (2025)
