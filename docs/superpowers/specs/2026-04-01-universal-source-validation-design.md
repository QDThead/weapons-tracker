# Universal Source Validation — Design Spec

**Date:** 2026-04-01
**Status:** Approved
**Scope:** Full expandable validation panels on every card, table, stat box, and chart across all 7 dashboard tabs

---

## Problem

The dashboard displays data from 56 active connectors across 150+ UI elements, but only 8 elements (BOM Explorer tiers) have source validation panels. Analysts cannot trace where a number comes from, assess its confidence, or check data freshness without leaving the dashboard. For an intelligence platform serving DND, every data point must be auditable.

## Solution

Centralized source registry with hierarchical key inheritance, served via two API endpoints, rendered by a universal frontend component that auto-attaches to every data element.

---

## Architecture

### 1. Source Registry (`src/analysis/source_registry.py`)

Single Python module containing ~70 hierarchical entries mapping UI element keys to source metadata.

**Entry structure:**

```python
"arctic.bases": {
    "title": "Arctic Base Registry — Source Validation",
    "sources": [
        {
            "name": "SIPRI Military Bases Data Project",
            "type": "Primary",
            "url": "https://sipri.org/...",
            "date": "2024",
            "note": "25 Arctic military installations with coordinates and capability data"
        },
        # ... additional sources
    ],
    "confidence": "HIGH",
    "confidence_note": "Triangulated across SIPRI + CSIS + national MoD data",
    "health_keys": ["sipri_transfers", "cia_factbook"]
}
```

**Fields per entry:**
- `title` — Section heading for the validation panel
- `sources[]` — Array of source objects, each with: `name`, `type`, `url` (optional), `date`, `note`
- `confidence` — HIGH / MEDIUM / LOW
- `confidence_note` — Human-readable triangulation/methodology explanation
- `health_keys[]` — References to data source connector names (used to look up live health)

**Source type badges** (8 types, reusing existing BOM palette):
- Primary (green)
- Cross-validation (purple)
- Trade validation (amber)
- Company reports (cyan)
- Manufacturer datasheets (cyan)
- Derived estimate (red)
- Reference (gray)
- Public domain (green)

### 2. Hierarchical Key Inheritance

Keys use dot notation: `tab.section.element`. Lookup walks up the tree until a match is found.

```
resolve("arctic.kpis.threat_level")
  1. Check "arctic.kpis.threat_level" → not found
  2. Check "arctic.kpis" → not found
  3. Check "arctic" → FOUND, return arctic sources
```

Section-level entries cover all children by default. Leaf entries override when a specific element has different sources (e.g., `arctic.kpis.ice_extent` overrides with NOAA-specific source).

**Reduces registry size from ~150 entries to ~56 explicit + ~14 inherited = ~70 entries.**

### 3. API Endpoints (`src/api/validation_routes.py`)

**`GET /validation/sources`** — Returns the full source registry. Cached 1 hour server-side.

Response:
```json
{
    "registry": {
        "arctic": { "title": "...", "sources": [...], "confidence": "HIGH", ... },
        "arctic.kpis.ice_extent": { "title": "...", "sources": [...], ... },
        ...
    },
    "total_keys": 70,
    "source_types": ["Primary", "Cross-validation", "Trade validation", ...]
}
```

**`GET /validation/health`** — Returns live freshness/health data for every data source connector. Cached 60 seconds.

Response:
```json
{
    "sipri_transfers": {
        "last_fetch": "2026-04-01T14:32:00Z",
        "records": 9311,
        "cache_age_seconds": 127,
        "cache_status": "FRESH",
        "health": "OK"
    },
    "gdelt_news": {
        "last_fetch": "2026-04-01T15:45:00Z",
        "records": 167,
        "cache_age_seconds": 43,
        "cache_status": "FRESH",
        "health": "OK"
    }
}
```

Health status values: `OK`, `STALE` (>2x expected freshness), `ERROR` (last fetch failed), `UNKNOWN` (never fetched).
Cache status values: `FRESH` (within TTL), `STALE` (past TTL), `EXPIRED` (>2x TTL).

### 4. Frontend System (`src/static/index.html`)

**`validationManager`** — JavaScript module responsible for:
- Fetching `/validation/sources` on page load (cached in memory)
- Polling `/validation/health` every 60 seconds
- Key resolution with hierarchical inheritance walk-up
- Merging static source citations with live health data

**`renderValidation(key, container)`** — Universal render function that:
- Resolves the key via inheritance
- Builds the collapsed trigger bar (confidence badge + source count)
- Builds the expandable panel (sources, health row, confidence note)
- Appends to the container element

**`attachAll()`** — Auto-discovery: finds all elements with `data-val-key` attribute and appends validation panels.

**`attach(element, key)`** — Manual attachment for dynamically rendered content (e.g., after API fetch populates a card).

**HTML integration — two modes:**

Static HTML elements:
```html
<div class="card" data-val-key="arctic.bases">
    <h3>Arctic Base Registry</h3>
    ...card content...
</div>
```

Dynamic content (in JS render functions):
```javascript
const card = document.getElementById('some-card');
validationManager.attach(card, "insights.sitrep.sanctions");
```

---

## UI Component Design

### Collapsed State (default)

Slim bar at the bottom of every element:
- Right-pointing chevron (▶)
- "SOURCES & VALIDATION" label (uppercase, cyan, 11px)
- Confidence badge: HIGH (green pill) / MEDIUM (amber pill) / LOW (red pill)
- Source count: "3 sources" (dim text)
- Subtle top border separator

### Expanded State (on click)

Full panel below the trigger bar:
- Cyan left border accent (3px)
- Dim cyan background (rgba(0,212,255,0.03))
- **Source list:** Each source gets a row with:
  - Type badge (color-coded pill)
  - Source name (white, 13px, semibold)
  - Date + URL link (dim, 11px)
  - Note (italic, dim, 11px)
- **Data Health row:** 4-column grid showing:
  - Last Fetch (relative time, green/amber/red based on freshness)
  - Records (count)
  - Cache (FRESH/STALE/EXPIRED)
  - Health (OK/STALE/ERROR)
- **Confidence assessment:** Confidence level + triangulation explanation

### CSS

Extends existing `.bom-val-panel` / `.bom-validate-btn` system. New classes:
- `.val-trigger` — collapsed bar
- `.val-panel` — expandable container
- `.val-panel.open` — expanded state
- `.val-health` — data health grid
- `.val-confidence` — confidence assessment row
- Reuses existing `.bvp-src`, `.bvp-type`, badge color classes

---

## Key Inventory (~70 entries)

### Insights Tab (10 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `insights` | Section default | Aggregated multi-source |
| `insights.sitrep` | Situation report (6 indicators) | SIPRI + GDELT + Sanctions + Flights + NATO + Comtrade |
| `insights.sitrep.sanctions` | Sanctions indicator | OFAC SDN + EU + UN + 17 embargoes |
| `insights.sitrep.arctic` | Arctic threat indicator | SIPRI + CIA Factbook + NOAA |
| `insights.taxonomy` | 13-category risk strip | PSI + GDELT + World Bank + OSINT |
| `insights.news` | Live news feed | GDELT + Defense RSS (4 feeds) |
| `insights.dsca` | DSCA sales cards | Federal Register API |
| `insights.alliances` | Shifting alliances | SIPRI transfers + Comtrade |
| `insights.freshness` | Data freshness banner | All 56 connectors |
| `insights.adversary` | Adversary flows | Comtrade buyer-side mirror |

### Arctic Tab (8 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `arctic` | Section default | SIPRI + CIA Factbook + Arctic Council |
| `arctic.kpis` | KPI stat boxes | Inherits arctic |
| `arctic.kpis.ice_extent` | Ice extent override | NOAA NSIDC |
| `arctic.bases` | 25-base registry table | SIPRI + CSIS + national MoD |
| `arctic.flights` | Live flight cards | 4 ADS-B sources |
| `arctic.routes` | Shipping routes table | IMF PortWatch + Arctic Council |
| `arctic.trade` | Trade flow cards (6) | Comtrade + StatCan |
| `arctic.naval` | Naval presence + weakness | CIA Factbook + Jane's |

### Deals Tab (2 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `deals` | Section default | SIPRI Arms Transfers DB |
| `deals.transfers` | 9,311 transfer table | SIPRI + Comtrade cross-validation |

### Canada Intel Tab (6 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `canada` | Section default | StatCan + DND + SIPRI |
| `canada.flows` | Ally vs adversary flows | SIPRI + Comtrade |
| `canada.threats` | Threat watchlist table | GDELT + Sanctions + Flights |
| `canada.suppliers` | Defence supply base | DND procurement + Wikidata ownership |
| `canada.suppliers.risk` | Supplier risk ranking | PSI 6-dimension scoring |
| `canada.actions` | Action Centre | Mitigation playbook (191 COAs) |

### Supply Chain Tab (20 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `supply.overview` | Global risk summary | PSI aggregated |
| `supply.globe` | 3D supply map | mineral_supply_chains.py (30 minerals) |
| `supply.graph` | Knowledge graph | NetworkX (90 nodes, 97 edges) |
| `supply.risks` | Risk matrix | PSI 6-dimension scoring |
| `supply.scenarios` | Scenario sandbox | Scenario engine + cascade model |
| `supply.taxonomy` | Risk taxonomy accordion | DND Annex B + live OSINT |
| `supply.forecasting` | Price forecasting | IMF PCOBALT + FRED + linear regression |
| `supply.bom` | BOM Explorer default | Migrated from existing validation |
| `supply.bom.mining` | Mining tier | USGS + BGS + NRCan + Comtrade |
| `supply.bom.processing` | Processing tier | USGS + Cobalt Institute + filings |
| `supply.bom.alloys` | Alloys tier | AMS specs + manufacturer datasheets |
| `supply.bom.platforms` | Platforms tier | DND fleet + OEM + Jane's |
| `supply.dossier` | Supplier dossiers (18) | Financial filings + FOCI + Wikidata |
| `supply.alerts` | Watchtower alerts | GDELT keyword + rule engine |
| `supply.register` | Risk register (10 risks) | PSI scoring + analyst input |
| `supply.feedback` | Analyst feedback / RLHF | ML engine + analyst adjudications |
| `supply.chokepoints` | Strategic chokepoints | IMF PortWatch + canal authorities |
| `supply.hhi` | HHI concentration | BGS live API + USGS |
| `supply.canada` | Canada dependency | NRCan + DND fleet + StatCan |
| `supply.risk_factors` | Risk factors | USGS + DRC MoM + Cobalt Institute |

### Data Feeds Tab (3 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `feeds` | Section default | All 56 connectors |
| `feeds.status` | Feed health cards | Scheduler + cache metadata |
| `feeds.stats` | Aggregate stats | Computed from all sources |

### Compliance Tab (2 keys)

| Key | Covers | Sources |
|-----|--------|---------|
| `compliance` | Section default | DMPP 11 RFI + internal mapping |
| `compliance.matrix` | 22 RFI questions | Traceability to implementation evidence |

---

## Migration

The existing 8 BOM validation tiers (currently hardcoded in `mineral_supply_chains.py`) get migrated into the centralized registry. The `validation` key in mineral data will be removed; BOM Explorer render functions will use `validationManager.attach()` instead of the current `renderBomValBtn()` / `toggleBomVal()` system.

Existing CSS classes (`.bom-val-panel`, `.bom-validate-btn`, `.bvp-*`) are kept as aliases or renamed to the new `.val-*` namespace.

---

## Files

| File | Action | Description |
|------|--------|-------------|
| `src/analysis/source_registry.py` | CREATE | ~70 hierarchical registry entries |
| `src/api/validation_routes.py` | CREATE | GET /validation/sources + /validation/health |
| `src/static/index.html` | MODIFY | validationManager JS, renderValidation(), CSS, data-val-key attributes on all elements |
| `src/main.py` | MODIFY | Register validation_routes router |
| `src/analysis/mineral_supply_chains.py` | MODIFY | Remove inline validation data (migrated to registry) |

---

## Testing

- Unit tests for key resolution (inheritance walk-up)
- Unit tests for health status computation (FRESH/STALE/EXPIRED logic)
- API tests for /validation/sources and /validation/health responses
- Verify all 56 explicit registry keys resolve correctly
- Verify inherited keys resolve to correct parent
- Frontend: verify all data-val-key elements get panels attached on each tab
