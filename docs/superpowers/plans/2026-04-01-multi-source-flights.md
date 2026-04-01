# Multi-Source Flight Tracking + Aircraft Intel Popups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add adsb.fi and Airplanes.live as additional flight data sources merged with adsb.lol, track aircraft position history for origin/destination estimation, and show detailed click popups on aircraft.

**Architecture:** Backend: multi-source parallel fetch in `flight_tracker.py` with dedup by ICAO hex, `sources` field on records. Frontend: position history buffer in `index.html`, enhanced popup handler for flight entities, origin estimation from oldest tracked position.

**Tech Stack:** Python (httpx async, asyncio.gather), CesiumJS 1.119

**Design spec:** `docs/superpowers/specs/2026-04-01-multi-source-flights-design.md`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/ingestion/flight_tracker.py` | Modify | Multi-source fetch + merge + dedup |
| `src/api/routes.py` | Modify | Add `sources` field to FlightOut |
| `src/static/index.html` | Modify | Position history, enhanced popup, origin estimation |
| `tests/test_flight_multi_source.py` | Create | Multi-source merge + dedup tests |

---

### Task 1: Multi-Source Backend (flight_tracker.py + routes.py + tests)

**Files:**
- Modify: `src/ingestion/flight_tracker.py`
- Modify: `src/api/routes.py:243-277`
- Create: `tests/test_flight_multi_source.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_flight_multi_source.py`:

```python
"""Tests for multi-source flight tracking."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion.flight_tracker import (
    FlightTrackerClient,
    MilitaryFlightRecord,
    ADSB_SOURCES,
)


class TestAdsbSources:
    def test_three_sources_defined(self):
        assert len(ADSB_SOURCES) == 3

    def test_sources_have_required_fields(self):
        for src in ADSB_SOURCES:
            assert "name" in src
            assert "url" in src
            assert src["url"].startswith("https://")

    def test_adsb_lol_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "adsb.lol" in names

    def test_adsb_fi_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "adsb.fi" in names

    def test_airplanes_live_present(self):
        names = [s["name"] for s in ADSB_SOURCES]
        assert "airplanes.live" in names


class TestDeduplication:
    def test_dedup_keeps_most_recent(self):
        client = FlightTrackerClient()
        records = [
            MilitaryFlightRecord(
                icao_hex="AE1234", callsign="RCH482", aircraft_type="C17",
                aircraft_description="C-17 Globemaster III", registration="05-5139",
                latitude=65.0, longitude=-95.0, altitude_ft=35000,
                ground_speed_knots=450, heading=340, vertical_rate=0,
                is_military=True, country_of_origin="United States (military)",
                squawk="1234", seen_at=None, sources=["adsb.lol"],
            ),
            MilitaryFlightRecord(
                icao_hex="AE1234", callsign="RCH482", aircraft_type="C17",
                aircraft_description="C-17 Globemaster III", registration="05-5139",
                latitude=65.1, longitude=-95.1, altitude_ft=35100,
                ground_speed_knots=451, heading=341, vertical_rate=0,
                is_military=True, country_of_origin="United States (military)",
                squawk="1234", seen_at=None, sources=["adsb.fi"],
            ),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 1
        assert "adsb.lol" in deduped[0].sources
        assert "adsb.fi" in deduped[0].sources

    def test_dedup_preserves_unique(self):
        client = FlightTrackerClient()
        records = [
            MilitaryFlightRecord(
                icao_hex="AE1234", callsign="RCH482", aircraft_type="C17",
                aircraft_description="C-17", registration="",
                latitude=65.0, longitude=-95.0, altitude_ft=35000,
                ground_speed_knots=450, heading=340, vertical_rate=0,
                is_military=True, country_of_origin="",
                squawk="", seen_at=None, sources=["adsb.lol"],
            ),
            MilitaryFlightRecord(
                icao_hex="AE5678", callsign="VIPER21", aircraft_type="F35",
                aircraft_description="F-35A", registration="",
                latitude=70.0, longitude=-80.0, altitude_ft=42000,
                ground_speed_knots=520, heading=270, vertical_rate=0,
                is_military=True, country_of_origin="",
                squawk="", seen_at=None, sources=["adsb.fi"],
            ),
        ]
        deduped = client._deduplicate(records)
        assert len(deduped) == 2


class TestSourcesField:
    def test_record_has_sources_field(self):
        r = MilitaryFlightRecord(
            icao_hex="AE1234", callsign="TEST", aircraft_type="C17",
            aircraft_description="C-17", registration="",
            latitude=0, longitude=0, altitude_ft=0,
            ground_speed_knots=0, heading=0, vertical_rate=0,
            is_military=True, country_of_origin="",
            squawk="", seen_at=None, sources=["adsb.lol"],
        )
        assert hasattr(r, "sources")
        assert r.sources == ["adsb.lol"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_flight_multi_source.py -v`
Expected: FAIL — `ADSB_SOURCES` not defined, `sources` field not on `MilitaryFlightRecord`

- [ ] **Step 3: Add ADSB_SOURCES and update MilitaryFlightRecord**

In `src/ingestion/flight_tracker.py`, replace the `ADSB_LOL_API` constant (line 22) with:

```python
ADSB_SOURCES = [
    {"name": "adsb.lol", "url": "https://api.adsb.lol/v2"},
    {"name": "adsb.fi", "url": "https://opendata.adsb.fi/api/v2"},
    {"name": "airplanes.live", "url": "https://api.airplanes.live/v2"},
]
```

Update the `MilitaryFlightRecord` dataclass — add `sources` field after `seen_at`:

```python
    seen_at: datetime

    sources: list[str] = None

    def __post_init__(self):
        if self.sources is None:
            self.sources = []
```

- [ ] **Step 4: Add `_deduplicate` method and update `fetch_military_aircraft`**

Add `_deduplicate` method to `FlightTrackerClient`:

```python
    @staticmethod
    def _deduplicate(records: list[MilitaryFlightRecord]) -> list[MilitaryFlightRecord]:
        """Deduplicate aircraft by ICAO hex, merging source lists."""
        by_hex: dict[str, MilitaryFlightRecord] = {}
        for r in records:
            hex_key = r.icao_hex.upper()
            if hex_key in by_hex:
                existing = by_hex[hex_key]
                for src in r.sources:
                    if src not in existing.sources:
                        existing.sources.append(src)
            else:
                by_hex[hex_key] = r
        return list(by_hex.values())
```

Replace `fetch_military_aircraft` method entirely:

```python
    async def fetch_military_aircraft(self) -> list[MilitaryFlightRecord]:
        """Fetch military aircraft from all sources, merge and deduplicate."""
        import asyncio

        async def _fetch_source(source: dict) -> list[MilitaryFlightRecord]:
            url = f"{source['url']}/mil"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                data = response.json()
                records = []
                for ac in data.get("ac", []):
                    record = self._parse_aircraft(ac)
                    if record:
                        record.sources = [source["name"]]
                        records.append(record)
                logger.info("Fetched %d aircraft from %s", len(records), source["name"])
                return records
            except Exception:
                logger.warning("Failed to fetch from %s", source["name"], exc_info=True)
                return []

        results = await asyncio.gather(*[_fetch_source(s) for s in ADSB_SOURCES])
        all_records = []
        for source_records in results:
            all_records.extend(source_records)

        deduped = self._deduplicate(all_records)
        logger.info("Multi-source: %d total, %d after dedup from %d sources",
                     len(all_records), len(deduped), len(ADSB_SOURCES))
        return deduped
```

Update `fetch_by_type` to also use multi-source:

```python
    async def fetch_by_type(self, type_code: str) -> list[MilitaryFlightRecord]:
        """Fetch all aircraft of a specific ICAO type code from all sources."""
        import asyncio

        async def _fetch_source(source: dict) -> list[MilitaryFlightRecord]:
            url = f"{source['url']}/type/{type_code}"
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                data = response.json()
                records = []
                for ac in data.get("ac", []):
                    record = self._parse_aircraft(ac)
                    if record:
                        record.sources = [source["name"]]
                        records.append(record)
                return records
            except Exception:
                logger.warning("Failed to fetch type %s from %s", type_code, source["name"], exc_info=True)
                return []

        results = await asyncio.gather(*[_fetch_source(s) for s in ADSB_SOURCES])
        all_records = []
        for source_records in results:
            all_records.extend(source_records)

        deduped = self._deduplicate(all_records)
        logger.info("Found %d aircraft of type %s (deduped from %d)", len(deduped), type_code, len(all_records))
        return deduped
```

- [ ] **Step 5: Add `sources` to FlightOut in routes.py**

In `src/api/routes.py`, add `sources` field to the `FlightOut` model (after `country_of_origin`):

```python
class FlightOut(BaseModel):
    icao_hex: str
    callsign: str
    aircraft_type: str
    aircraft_description: str
    registration: str
    latitude: float
    longitude: float
    altitude_ft: float
    ground_speed_knots: float
    heading: float
    is_military: bool
    country_of_origin: str
    sources: list[str] = []
```

Update the `get_military_flights` endpoint to pass sources:

```python
@app.get("/tracking/flights/military", response_model=list[FlightOut])
async def get_military_flights():
    """Get all currently visible military aircraft from multiple ADS-B sources."""
    client = FlightTrackerClient()
    records = await client.fetch_military_aircraft()
    return [
        FlightOut(
            icao_hex=r.icao_hex, callsign=r.callsign,
            aircraft_type=r.aircraft_type,
            aircraft_description=r.aircraft_description,
            registration=r.registration,
            latitude=r.latitude, longitude=r.longitude,
            altitude_ft=r.altitude_ft,
            ground_speed_knots=r.ground_speed_knots,
            heading=r.heading,
            is_military=r.is_military,
            country_of_origin=r.country_of_origin,
            sources=r.sources,
        )
        for r in records
    ]
```

Do the same for the `get_transport_flights` endpoint (add `sources=r.sources`).

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/test_flight_multi_source.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/test_globe.py tests/test_confidence_triangulation.py tests/test_dossier_completeness.py tests/test_comtrade_cobalt.py tests/test_flight_multi_source.py -q`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add src/ingestion/flight_tracker.py src/api/routes.py tests/test_flight_multi_source.py
git commit -m "feat(flights): add adsb.fi + airplanes.live multi-source tracking with dedup"
```

---

### Task 2: Position History + Enhanced Popup (Frontend)

**Files:**
- Modify: `src/static/index.html` — add history buffer, extend popup handler, enhance flight entity properties

- [ ] **Step 1: Add flight history global and origin estimation**

Find the Arctic global variables (search for `arcticLayerEntities`). Add after them:

```javascript
var arcticFlightHistory = {};  // keyed by ICAO hex: { positions: [{lat,lon,alt,heading,time}], firstSeen, lastSeen, sources: [], origin: null, dest: null }
```

Add origin estimation function near the other Arctic helper functions (after `updateArcticFreightStats`):

```javascript
function estimateFlightOrigin(hex, bases) {
  var hist = arcticFlightHistory[hex];
  if (!hist || hist.positions.length < 2) return null;
  var oldest = hist.positions[0];
  var bestBase = null;
  var bestDist = Infinity;
  bases.forEach(function(base) {
    var dist = _haversineJS(oldest.lat, oldest.lon, base.lat, base.lon);
    if (dist < 100 && dist < bestDist) {
      bestDist = dist;
      bestBase = base;
    }
  });
  return bestBase ? { name: bestBase.name, lat: bestBase.lat, lon: bestBase.lon, dist: Math.round(bestDist) } : null;
}

function getAveragedHeading(hex) {
  var hist = arcticFlightHistory[hex];
  if (!hist || hist.positions.length === 0) return null;
  var recent = hist.positions.slice(-3);
  var headings = recent.filter(function(p) { return p.heading != null; }).map(function(p) { return p.heading; });
  if (headings.length === 0) return null;
  // Simple circular mean for headings
  var sinSum = 0, cosSum = 0;
  headings.forEach(function(h) { sinSum += Math.sin(h * Math.PI / 180); cosSum += Math.cos(h * Math.PI / 180); });
  var avg = Math.atan2(sinSum / headings.length, cosSum / headings.length) * 180 / Math.PI;
  return (avg + 360) % 360;
}
```

- [ ] **Step 2: Update `renderArcticFlights` to track history and store properties for popup**

Find the existing `renderArcticFlights` function. Add history tracking at the top of the function (after the `if (!flights || !flights.flights) return;` check):

```javascript
  // Update position history
  var now = Date.now();
  flights.flights.forEach(function(f) {
    var hex = (f.icao_hex || '').toUpperCase();
    if (!hex) return;
    if (!arcticFlightHistory[hex]) {
      arcticFlightHistory[hex] = { positions: [], firstSeen: now, lastSeen: now, sources: [] };
    }
    var hist = arcticFlightHistory[hex];
    hist.positions.push({ lat: f.latitude, lon: f.longitude, alt: f.altitude_ft, heading: f.heading, time: now });
    if (hist.positions.length > 30) hist.positions.shift();
    hist.lastSeen = now;
    (f.sources || []).forEach(function(s) { if (hist.sources.indexOf(s) < 0) hist.sources.push(s); });
  });
  // Prune stale aircraft (not seen in 5 min)
  Object.keys(arcticFlightHistory).forEach(function(hex) {
    if (now - arcticFlightHistory[hex].lastSeen > 300000) delete arcticFlightHistory[hex];
  });
```

Then update the destination estimation to use averaged heading. Find the line:
```javascript
      dest = estimateFlightDestination(f, bases);
```

Replace with:
```javascript
      var avgHeading = getAveragedHeading((f.icao_hex || '').toUpperCase());
      if (avgHeading != null) {
        var fCopy = { latitude: f.latitude, longitude: f.longitude, heading: avgHeading };
        dest = estimateFlightDestination(fCopy, bases);
      } else {
        dest = estimateFlightDestination(f, bases);
      }
```

Update the entity properties to include all data needed for the popup. Find:
```javascript
      properties: { type: 'arctic-flight', nation: f.nation, isTransport: isTransport },
```

Replace with:
```javascript
      properties: {
        type: 'arctic-flight',
        nation: f.nation,
        isTransport: isTransport,
        isTanker: isTanker,
        hex: f.icao_hex || '',
        callsign: f.callsign || '',
        aircraftType: f.aircraft_type || '',
        aircraftDesc: f.aircraft_description || '',
        altitude_ft: f.altitude_ft || 0,
        speed_kts: f.ground_speed_knots || 0,
        heading: f.heading || 0,
        payload: payload,
        destName: dest ? dest.name : '',
        destDist: dest ? dest.dist : 0,
        sources: (f.sources || []).join(', '),
      },
```

- [ ] **Step 3: Extend `setupArcticPopupHandler` for flight entities**

Find the popup handler (search for `setupArcticPopupHandler`). Inside the click handler, after the `arctic-base` block (the `if` that checks `type.getValue() === 'arctic-base'`), add an `else if` for flight entities before the `else` that hides the popup:

Find:
```javascript
    } else {
      popupDiv.style.display = 'none';
    }
```

Replace with:
```javascript
    } else if (Cesium.defined(picked) && picked.id && picked.id.properties && picked.id.properties.type &&
               picked.id.properties.type.getValue() === 'arctic-flight') {
      var fp = picked.id.properties;
      var hex = fp.hex.getValue();
      var isT = fp.isTransport.getValue();
      var isTk = fp.isTanker.getValue();
      var hist = arcticFlightHistory[hex.toUpperCase()] || {};
      var trackLen = hist.positions ? hist.positions.length : 0;
      var trackMin = hist.firstSeen ? Math.round((Date.now() - hist.firstSeen) / 60000) : 0;
      var bases = (arcticBasesData && arcticBasesData.bases) ? arcticBasesData.bases : [];
      var origin = estimateFlightOrigin(hex.toUpperCase(), bases);
      var originStr = origin ? esc(origin.name.split(',')[0]) + ' (est.)' : (trackLen > 1 ? 'In transit (tracking...)' : 'Detecting...');
      var destName = fp.destName.getValue();
      var destStr = destName ? esc(destName.split(',')[0]) : 'Unknown';
      var destDist = fp.destDist.getValue();
      var payload = fp.payload.getValue();
      var sources = fp.sources.getValue();
      var nationLabels = { russian: 'Russia', chinese: 'China', nato: 'NATO', unknown: 'Unknown' };
      var nationName = nationLabels[fp.nation.getValue()] || fp.nation.getValue();

      var html = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">' +
        '<b style="font-size:14px;">\u2708 ' + esc(fp.aircraftDesc.getValue() || fp.aircraftType.getValue()) + '</b>' +
        '<span onclick="document.getElementById(\'arctic-base-popup-overlay\').style.display=\'none\'" style="cursor:pointer;color:var(--text-dim);font-size:16px;">&times;</span>' +
      '</div>' +
      '<div style="color:var(--text-dim);margin-bottom:8px;">Callsign: <b>' + esc(fp.callsign.getValue() || '---') + '</b> | ' + esc(nationName) + '</div>';

      if (isT && payload > 0) {
        html += '<div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:8px;margin-bottom:8px;">' +
          '<div style="margin-bottom:4px;">Payload Capacity: <b style="color:#10b981;">' + payload + ' tonnes</b></div>' +
          '<div style="margin-bottom:4px;color:var(--text-dim);">Status: Assumed fully loaded</div>' +
          '<div style="margin-bottom:4px;">Origin: <b>' + originStr + '</b></div>' +
          '<div style="margin-bottom:4px;">Destination: <b>' + destStr + '</b></div>' +
          (destDist > 0 ? '<div style="margin-bottom:4px;">Distance remaining: ~' + destDist.toLocaleString() + ' km</div>' : '') +
        '</div>';
      }

      html += '<div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:8px;">' +
        '<div>Alt: ' + (fp.altitude_ft.getValue() || 0).toLocaleString() + ' ft | Speed: ' + (fp.speed_kts.getValue() || 0).toFixed(0) + ' kts | Hdg: ' + (fp.heading.getValue() || 0).toFixed(0) + '\u00b0</div>' +
        '<div style="margin-top:4px;color:var(--text-dim);">Track: ' + trackLen + ' positions | ' + trackMin + ' min</div>' +
        (sources ? '<div style="margin-top:2px;color:var(--text-dim);">Sources: ' + esc(sources) + '</div>' : '') +
      '</div>';

      popupDiv.innerHTML = html;
      popupDiv.style.left = (click.position.x + 15) + 'px';
      popupDiv.style.top = (click.position.y - 10) + 'px';
      popupDiv.style.display = 'block';
    } else {
      popupDiv.style.display = 'none';
    }
```

- [ ] **Step 4: Verify everything works**

Open http://localhost:8000 → Arctic tab:
1. Flights render with plane icons (from previous task)
2. Click on a transport aircraft → detailed popup with payload, destination, origin (origin may show "Detecting..." initially)
3. Wait 2-3 minutes, click again → origin should populate
4. Click on a non-transport aircraft → simpler popup
5. Freight stats bar still works
6. Sources field shows which APIs detected each aircraft

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(arctic): add flight position history, origin estimation, and aircraft click popups"
```

---

## Final Verification

After both tasks:

- [ ] `/tracking/flights/military` returns aircraft with `sources` field
- [ ] Arctic globe shows flights from multiple sources (more coverage)
- [ ] Click transport → popup with origin, destination, payload, track history
- [ ] Click fighter → simpler popup with callsign, type, nation, altitude
- [ ] Freight stats bar reflects multi-source data
- [ ] After 2-3 refresh cycles, origin estimation populates
- [ ] All tests pass
