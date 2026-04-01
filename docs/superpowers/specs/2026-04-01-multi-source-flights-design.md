# Multi-Source Flight Tracking + Aircraft Intel Popups Design Spec

**Date**: 2026-04-01
**Goal**: Add adsb.fi and Airplanes.live as additional flight data sources (merged with adsb.lol), track aircraft position history for origin/destination estimation, and show detailed click popups on transport aircraft.
**Scope**: Backend (`flight_tracker.py`) + frontend (`index.html`). No new API endpoints — the existing `/tracking/flights/military` endpoint returns merged data.

---

## Part 1: Multi-Source Flight Data (Backend)

### New Sources

All 3 sources use identical readsb/tar1090 JSON format (`{"ac": [...]}` with same field names). The existing `_parse_aircraft()` method works for all with zero changes.

| Source | Base URL | Military Endpoint | Rate Limit | Auth |
|--------|----------|------------------|------------|------|
| adsb.lol (existing) | `https://api.adsb.lol/v2` | `/mil` | Unspecified | None |
| adsb.fi (new) | `https://opendata.adsb.fi/api/v2` | `/mil` | 1 req/sec | None |
| Airplanes.live (new) | `https://api.airplanes.live/v2` | `/mil` | 1 req/sec | None |

### Merge Strategy

In `FlightTrackerClient.fetch_military_aircraft()`:

1. Query all 3 sources in parallel using `asyncio.gather()` with `return_exceptions=True`
2. Flatten all aircraft records into a single list
3. Deduplicate by ICAO hex (`hex` field) — keep the record with the lowest `seen` value (most recently updated)
4. Add a `sources` field to each `MilitaryFlightRecord` indicating which APIs returned this aircraft (e.g., `["adsb.lol", "adsb.fi"]`)
5. If all 3 sources fail, return empty list with logged warning

### Changes to `flight_tracker.py`

**Constants:**
```python
ADSB_SOURCES = [
    {"name": "adsb.lol", "url": "https://api.adsb.lol/v2"},
    {"name": "adsb.fi", "url": "https://opendata.adsb.fi/api/v2"},
    {"name": "airplanes.live", "url": "https://api.airplanes.live/v2"},
]
```

**MilitaryFlightRecord**: Add `sources: list[str]` field (default `[]`).

**`fetch_military_aircraft()`**: Query all 3 `/mil` endpoints in parallel, merge, deduplicate by hex.

**`fetch_transport_aircraft()`** and **`fetch_by_type()`**: Same multi-source pattern.

**`fetch_area()`**: Only adsb.lol and Airplanes.live support `/point/{lat}/{lon}/{radius}`. adsb.fi uses `/v3/lat/{lat}/lon/{lon}/dist/{dist}`. Query all 3 with appropriate URL patterns.

### Changes to API response

**`FlightOut` model** in `routes.py`: Add `sources: list[str]` field.

The `/tracking/flights/military` endpoint automatically returns merged data since it calls `FlightTrackerClient`.

---

## Part 2: Position History Tracking (Frontend)

### In-Memory Flight History

New global in `index.html`:

```javascript
var arcticFlightHistory = {};  // keyed by ICAO hex
// Each entry: { hex, positions: [{lat, lon, alt, heading, time}], firstSeen, lastSeen, sources: [] }
```

### Update Logic (in `renderArcticFlights`)

On each 60-second refresh:

1. For each aircraft in the response:
   - If hex not in `arcticFlightHistory`, create new entry
   - Append current `{lat, lon, alt_ft, heading, time: Date.now()}` to `positions` array
   - Cap at 30 entries per aircraft (30 minutes at 60s intervals)
   - Update `lastSeen` timestamp
   - Merge `sources` arrays

2. Prune stale aircraft: remove any hex not seen in last 5 minutes (300,000ms)

### Origin Estimation

Look at the aircraft's **oldest tracked position**. Find the nearest Arctic base within 100km of that position. If found, that's the estimated departure base.

If no base within 100km of the oldest position (aircraft was already in transit when first detected), show "Origin: In transit (first detected at [lat, lon])".

### Destination Estimation (Enhanced)

Use **average heading over last 3 positions** instead of instantaneous heading. This smooths out heading jitter and gives a more stable destination estimate.

Still uses `estimateFlightDestination()` with the averaged heading, same ±30° cone and 4000km range.

---

## Part 3: Aircraft Click Popup (Frontend)

### Transport Aircraft Popup

When clicking a transport aircraft entity on the Arctic globe, show a detailed glass-morphism popup:

```
┌──────────────────────────────────────┐
│ ✈ C-17 Globemaster III        [×]   │
│ Callsign: RCH482 | USAF             │
│──────────────────────────────────────│
│ Payload Capacity: 77 tonnes          │
│ Status: Assumed fully loaded         │
│                                      │
│ Origin: Eielson AFB, Alaska (est.)   │
│ Destination: Pituffik Space Base     │
│ Distance remaining: ~2,400 km        │
│──────────────────────────────────────│
│ Alt: 35,000 ft | Speed: 450 kts     │
│ Heading: 340° | Track: 28 positions  │
│ Sources: adsb.lol + adsb.fi          │
│──────────────────────────────────────│
│ Tracking: 28 min                     │
└──────────────────────────────────────┘
```

**Fields:**
- Aircraft type description (from `MILITARY_TRANSPORT_TYPES` lookup or `aircraft_description`)
- Callsign + nation/country
- Payload capacity (from `TRANSPORT_PAYLOAD_TONNES`)
- Estimated origin base (from position history oldest point)
- Estimated destination base (from averaged heading projection)
- Distance remaining to destination
- Current altitude, ground speed, heading
- Track length (number of positions in history)
- Data sources that detected this aircraft
- Tracking duration (time since first seen)

### Non-Transport Aircraft Popup

Simpler popup for fighters, tankers, and unclassified:

```
┌──────────────────────────────────────┐
│ ✈ F-35A Lightning II          [×]   │
│ Callsign: VIPER21 | NATO            │
│──────────────────────────────────────│
│ Alt: 42,000 ft | Speed: 520 kts     │
│ Heading: 270°                        │
│ Sources: adsb.lol                    │
└──────────────────────────────────────┘
```

### Popup Interaction

- Click on aircraft entity → show popup positioned near click point
- Click elsewhere or [×] → dismiss popup
- Reuses the existing `setupArcticPopupHandler()` pattern — extend it to handle `arctic-flight` entity type in addition to `arctic-base`

---

## Files Modified

| File | Changes |
|------|---------|
| `src/ingestion/flight_tracker.py` | Add `ADSB_SOURCES` list, `sources` field on `MilitaryFlightRecord`, multi-source parallel fetch + merge + dedup in all fetch methods |
| `src/api/routes.py` | Add `sources: list[str]` to `FlightOut` model |
| `src/static/index.html` | Add `arcticFlightHistory`, update `renderArcticFlights()` with history tracking, extend `setupArcticPopupHandler()` for flight click popups |

## New Tests

| File | Tests |
|------|-------|
| `tests/test_flight_multi_source.py` | Test deduplication by hex, source merging, graceful failure when sources are down |

---

## Test Plan

- Existing tests must pass
- New tests: multi-source merge, dedup, source attribution
- Manual verification:
  - Arctic flights render from merged sources
  - Freight stats bar shows data
  - Click on transport → detailed popup with origin/destination/payload
  - Click on fighter → simple popup
  - After 2-3 refresh cycles, origin estimation populates
  - Sources field shows which APIs detected each aircraft
  - If one source is down, others still work
