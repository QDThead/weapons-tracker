# SO2 + NDVI Satellite Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Sentinel-5P SO2 smelting detection (refineries) and Sentinel-2 NDVI bare-soil mining activity detection (mines) with tier-specific combined verdicts.

**Architecture:** Extend existing `sentinel_no2.py` connector with SO2 + NDVI query methods using the same Copernicus OAuth + Processing API. Expand `compute_combined_verdict()` to accept 4 signals + facility type. Enrich globe routes with new data. Add frontend visualization.

**Tech Stack:** Same Copernicus Sentinel Hub Processing API, httpx, PIL, Chart.js

**Spec:** `docs/superpowers/specs/2026-04-04-so2-ndvi-satellite-verification-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/ingestion/sentinel_no2.py` | Modify | Add SO2 query, NDVI query, status functions, fetch methods, fallback data, history |
| `src/api/globe_routes.py` | Modify | Add SO2 + NDVI enrichment blocks, pass facility_type to verdict |
| `src/ingestion/scheduler.py` | Modify | Add job #29 (SO2 daily) and #30 (NDVI weekly) |
| `src/static/index.html` | Modify | Verification charts, verdict scoring, alerts KPIs, globe layers, dossier sections |
| `tests/test_sentinel_no2.py` | Modify | Add SO2, NDVI, and expanded verdict tests |
| `data/sentinel_so2_history.json` | Create | SO2 history (empty init, populated by scheduler) |
| `data/sentinel_ndvi_history.json` | Create | NDVI history (empty init, populated by scheduler) |

---

### Task 1: SO2 Status Function + Tests

**Files:**
- Modify: `tests/test_sentinel_no2.py`
- Modify: `src/ingestion/sentinel_no2.py`

- [ ] **Step 1: Write SO2 status tests**

Add to `tests/test_sentinel_no2.py`:

```python
def test_so2_status_smelting():
    """SO2 ratio >= 1.5 should return SMELTING."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.00045, background_so2=0.00015)
    assert result["status"] == "SMELTING"
    assert result["ratio"] == 3.0


def test_so2_status_at_threshold():
    """SO2 ratio exactly at 1.5 should return SMELTING."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.000015, background_so2=0.00001)
    assert result["status"] == "SMELTING"
    assert result["ratio"] == 1.5


def test_so2_status_low():
    """SO2 ratio < 1.5 should return LOW_SO2."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=0.000012, background_so2=0.00001)
    assert result["status"] == "LOW_SO2"
    assert result["ratio"] == 1.2


def test_so2_status_unknown():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_so2_status
    result = compute_so2_status(facility_so2=None, background_so2=None)
    assert result["status"] == "UNKNOWN"
    assert result["ratio"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sentinel_no2.py::test_so2_status_smelting -v`
Expected: FAIL — `ImportError: cannot import name 'compute_so2_status'`

- [ ] **Step 3: Implement compute_so2_status**

Add to `src/ingestion/sentinel_no2.py` after `compute_no2_status`:

```python
def compute_so2_status(facility_so2: float | None, background_so2: float | None) -> dict:
    """Classify SO2 emissions: SMELTING (>= 1.5x background) or LOW_SO2."""
    if facility_so2 is None or background_so2 is None:
        return {"status": "UNKNOWN", "ratio": 0}
    ratio = facility_so2 / max(background_so2, 1e-8)
    ratio = round(ratio, 1)
    if ratio >= 1.5:
        return {"status": "SMELTING", "ratio": ratio}
    return {"status": "LOW_SO2", "ratio": ratio}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sentinel_no2.py -k "so2_status" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/sentinel_no2.py tests/test_sentinel_no2.py
git commit -m "feat(satellite): add SO2 status classification function"
```

---

### Task 2: NDVI Status Function + Tests

**Files:**
- Modify: `tests/test_sentinel_no2.py`
- Modify: `src/ingestion/sentinel_no2.py`

- [ ] **Step 1: Write NDVI status tests**

Add to `tests/test_sentinel_no2.py`:

```python
def test_ndvi_status_active_mining():
    """Bare soil > 60% should return ACTIVE_MINING."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=75.0, mean_ndvi=0.15)
    assert result["status"] == "ACTIVE_MINING"


def test_ndvi_status_moderate():
    """Bare soil 30-60% should return MODERATE."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=45.0, mean_ndvi=0.35)
    assert result["status"] == "MODERATE"


def test_ndvi_status_vegetated():
    """Bare soil < 30% should return VEGETATED."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=15.0, mean_ndvi=0.65)
    assert result["status"] == "VEGETATED"


def test_ndvi_status_unknown():
    """None values should return UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_ndvi_status
    result = compute_ndvi_status(bare_soil_pct=None, mean_ndvi=None)
    assert result["status"] == "UNKNOWN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_sentinel_no2.py::test_ndvi_status_active_mining -v`
Expected: FAIL — `ImportError: cannot import name 'compute_ndvi_status'`

- [ ] **Step 3: Implement compute_ndvi_status**

Add to `src/ingestion/sentinel_no2.py` after `compute_so2_status`:

```python
def compute_ndvi_status(bare_soil_pct: float | None, mean_ndvi: float | None) -> dict:
    """Classify mine activity from Sentinel-2 bare soil percentage."""
    if bare_soil_pct is None or mean_ndvi is None:
        return {"status": "UNKNOWN", "bare_soil_pct": 0, "mean_ndvi": 0}
    if bare_soil_pct > 60:
        return {"status": "ACTIVE_MINING", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}
    if bare_soil_pct >= 30:
        return {"status": "MODERATE", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}
    return {"status": "VEGETATED", "bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sentinel_no2.py -k "ndvi_status" -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/sentinel_no2.py tests/test_sentinel_no2.py
git commit -m "feat(satellite): add NDVI bare-soil mining activity classification"
```

---

### Task 3: Expand Combined Verdict to 4 Signals + Facility Type

**Files:**
- Modify: `tests/test_sentinel_no2.py`
- Modify: `src/ingestion/sentinel_no2.py`

- [ ] **Step 1: Write expanded verdict tests**

Add to `tests/test_sentinel_no2.py`:

```python
def test_combined_verdict_mine_3_signals():
    """Mine with all 3 signals active → CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "ACTIVE_MINING", "mine")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"
    assert len(result["sources"]) == 3


def test_combined_verdict_mine_2_signals():
    """Mine with 2/3 signals active → ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "VEGETATED", "mine")
    assert result["status"] == "ACTIVE"
    assert result["confidence"] == "medium-high"


def test_combined_verdict_mine_1_signal():
    """Mine with 1/3 signals active → LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "UNKNOWN", "ACTIVE_MINING", "mine")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_mine_0_signals():
    """Mine with 0/3 signals active → IDLE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "UNKNOWN", "VEGETATED", "mine")
    assert result["status"] == "IDLE"
    assert result["confidence"] == "low"


def test_combined_verdict_refinery_3_signals():
    """Refinery with all 3 signals active → CONFIRMED ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("ACTIVE", "EMITTING", "SMELTING", "UNKNOWN", "refinery")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"
    assert len(result["sources"]) == 3


def test_combined_verdict_refinery_so2_only():
    """Refinery with only SO2 → LIKELY ACTIVE."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("IDLE", "LOW_EMISSION", "SMELTING", "UNKNOWN", "refinery")
    assert result["status"] == "LIKELY ACTIVE"
    assert result["confidence"] == "medium"


def test_combined_verdict_backward_compat():
    """With no SO2/NDVI data (UNKNOWN), degrades to 2-signal logic."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    # 2 signals active out of 2 known (UNKNOWN doesn't count)
    result = compute_combined_verdict("ACTIVE", "EMITTING", "UNKNOWN", "UNKNOWN", "mine")
    assert result["status"] == "CONFIRMED ACTIVE"
    assert result["confidence"] == "high"


def test_combined_verdict_all_unknown():
    """All signals UNKNOWN → UNKNOWN."""
    from src.ingestion.sentinel_no2 import compute_combined_verdict
    result = compute_combined_verdict("UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN", "mine")
    assert result["status"] == "UNKNOWN"
    assert result["confidence"] == "none"
```

- [ ] **Step 2: Run tests to verify failures**

Run: `python -m pytest tests/test_sentinel_no2.py -k "combined_verdict_mine_3" -v`
Expected: FAIL — `compute_combined_verdict() takes 2 positional arguments but 5 positional arguments were given`

- [ ] **Step 3: Rewrite compute_combined_verdict**

Replace the entire `compute_combined_verdict` function in `src/ingestion/sentinel_no2.py`:

```python
def compute_combined_verdict(
    thermal_status: str,
    no2_status: str,
    so2_status: str = "UNKNOWN",
    ndvi_status: str = "UNKNOWN",
    facility_type: str = "mine",
) -> dict:
    """Tier-specific operational verdict from up to 4 satellite signals.

    Mines use: thermal + NO2 + NDVI (ignore SO2).
    Refineries use: thermal + NO2 + SO2 (ignore NDVI).
    UNKNOWN signals are excluded from the count (not confirming or denying).
    """
    sources = []
    active_count = 0
    known_count = 0

    # Thermal — applies to both types
    if thermal_status != "UNKNOWN":
        known_count += 1
        if thermal_status == "ACTIVE":
            active_count += 1
            sources.append("FIRMS VIIRS thermal")

    # NO2 — applies to both types
    if no2_status != "UNKNOWN":
        known_count += 1
        if no2_status == "EMITTING":
            active_count += 1
            sources.append("Sentinel-5P NO2")

    # Tier-specific third signal
    if facility_type == "refinery":
        if so2_status != "UNKNOWN":
            known_count += 1
            if so2_status == "SMELTING":
                active_count += 1
                sources.append("Sentinel-5P SO2")
    else:  # mine
        if ndvi_status != "UNKNOWN":
            known_count += 1
            if ndvi_status == "ACTIVE_MINING":
                active_count += 1
                sources.append("Sentinel-2 NDVI")

    if known_count == 0:
        return {"status": "UNKNOWN", "confidence": "none", "sources": []}

    # Score based on active signals out of known signals
    if active_count >= 3:
        return {"status": "CONFIRMED ACTIVE", "confidence": "high", "sources": sources}
    if active_count == 2:
        # 2/2 known = CONFIRMED, 2/3 known = ACTIVE
        if known_count == 2 and active_count == 2:
            return {"status": "CONFIRMED ACTIVE", "confidence": "high", "sources": sources}
        return {"status": "ACTIVE", "confidence": "medium-high", "sources": sources}
    if active_count == 1:
        return {"status": "LIKELY ACTIVE", "confidence": "medium", "sources": sources}
    return {"status": "IDLE", "confidence": "low", "sources": []}
```

- [ ] **Step 4: Run ALL verdict tests**

Run: `python -m pytest tests/test_sentinel_no2.py -k "combined_verdict" -v`
Expected: all verdict tests pass (old + new)

- [ ] **Step 5: Run full sentinel test suite**

Run: `python -m pytest tests/test_sentinel_no2.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/sentinel_no2.py tests/test_sentinel_no2.py
git commit -m "feat(satellite): expand combined verdict to 4 signals with tier-specific logic"
```

---

### Task 4: SO2 Query Method + Fetch Methods + Fallback Data

**Files:**
- Modify: `src/ingestion/sentinel_no2.py`
- Modify: `tests/test_sentinel_no2.py`

- [ ] **Step 1: Write fallback SO2 test**

Add to `tests/test_sentinel_no2.py`:

```python
def test_fallback_so2_data():
    """SO2 fallback data should cover all 18 facilities."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client
    client = SentinelNO2Client()
    data = client._fallback_so2_data()
    from src.ingestion.firms_thermal import FACILITY_CONFIG
    assert len(data) == len(FACILITY_CONFIG)
    for name, entry in data.items():
        assert "so2_mol_m2" in entry
        assert "status" in entry
        assert entry["status"] in ("SMELTING", "LOW_SO2", "UNKNOWN")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sentinel_no2.py::test_fallback_so2_data -v`
Expected: FAIL — `AttributeError: 'SentinelNO2Client' object has no attribute '_fallback_so2_data'`

- [ ] **Step 3: Add SO2 evalscript, query, fetch, and fallback methods**

Add the SO2 evalscript constant near the top of `src/ingestion/sentinel_no2.py`, after `_EVALSCRIPT`:

```python
_SO2_EVALSCRIPT = """//VERSION=3
function setup(){
  return {
    input: ["SO2", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var v = s.SO2 / 0.001 * 255;
  v = Math.min(255, Math.max(0, v));
  return [v, v, v, 255];
}"""

_SO2_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sentinel_so2_history.json"
```

Add these methods to the `SentinelNO2Client` class, after `fetch_all_facilities`:

```python
    async def _query_bbox_so2(self, bbox: list[float], days: int = 7) -> dict | None:
        """Query SO2 for a bbox. Returns {so2: float, cloud_free_pct: int} or None."""
        token = await self._get_token()
        if not token:
            return None
        now = datetime.now(timezone.utc) - timedelta(days=5)
        time_from = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        time_to = now.strftime("%Y-%m-%dT23:59:59Z")
        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-5p-l2",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "s5pType": "SO2",
                    },
                    "processing": {"minQa": 50},
                }],
            },
            "output": {
                "width": 8,
                "height": 8,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": _SO2_EVALSCRIPT,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE SO2 Process API returned HTTP %s", resp.status_code)
                    return None
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                total = len(pixels)
                valid = [p[0] for p in pixels if len(p) >= 4 and p[3] > 0]
                cloud_free_pct = round(len(valid) / max(total, 1) * 100)
                if not valid:
                    return {"so2": None, "cloud_free_pct": cloud_free_pct}
                mean_scaled = sum(valid) / len(valid)
                return {"so2": mean_scaled / 255 * 0.001, "cloud_free_pct": cloud_free_pct}
        except Exception as e:
            logger.warning("CDSE SO2 query failed: %s", e)
            return None

    async def fetch_facility_so2(self, name: str, lat: float, lon: float, radius_deg: float, days: int = 7) -> dict:
        """Fetch SO2 emissions data for a single facility."""
        cache_key = f"so2_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        so2_radius = max(radius_deg, 0.1)
        facility_bbox = _make_bbox(lat, lon, so2_radius)
        facility_result = await self._query_bbox_so2(facility_bbox, days)
        bg_bbox = _make_bbox(lat, lon, so2_radius * 5)
        bg_result = await self._query_bbox_so2(bg_bbox, days)
        facility_so2 = facility_result["so2"] if facility_result else None
        background_so2 = bg_result["so2"] if bg_result else None
        cloud_free_pct = facility_result["cloud_free_pct"] if facility_result else 0
        status_info = compute_so2_status(facility_so2, background_so2)
        result = {
            "so2_mol_m2": round(facility_so2, 10) if facility_so2 else None,
            "background_mol_m2": round(background_so2, 10) if background_so2 else None,
            "ratio": status_info["ratio"],
            "status": status_info["status"],
            "cloud_free_pct": cloud_free_pct,
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-5P TROPOMI SO2 (live)",
        }
        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities_so2(self) -> dict[str, dict]:
        """Fetch SO2 data for all 18 cobalt facilities."""
        cache_key = "so2_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        if not self.client_id or not self.client_secret:
            logger.info("No SENTINEL credentials — using fallback SO2 data")
            return self._fallback_so2_data()
        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            data = await self.fetch_facility_so2(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=7,
            )
            result[name] = data
        self._snapshot_so2_history(result)
        history = self._load_so2_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]
        _cache_set(self._cache, cache_key, result)
        smelting = sum(1 for v in result.values() if v["status"] == "SMELTING")
        logger.info("Sentinel SO2: %d/%d facilities SMELTING", smelting, len(result))
        return result

    def _fallback_so2_data(self) -> dict[str, dict]:
        """Seed SO2 data when no Copernicus credentials are configured."""
        seeds = {
            # Refineries — higher SO2 from smelting
            "Huayou Cobalt":           (0.00065, 0.00020, "SMELTING"),
            "GEM Co.":                 (0.00050, 0.00018, "SMELTING"),
            "Jinchuan Group":          (0.00070, 0.00015, "SMELTING"),
            "Umicore Kokkola":         (0.00020, 0.00012, "SMELTING"),
            "Umicore Hoboken":         (0.00028, 0.00020, "LOW_SO2"),
            "Fort Saskatchewan":       (0.00015, 0.00010, "LOW_SO2"),
            "Long Harbour NPP":        (0.00012, 0.00009, "LOW_SO2"),
            "Niihama Nickel Refinery":  (0.00022, 0.00013, "SMELTING"),
            "Harjavalta":              (0.00018, 0.00010, "SMELTING"),
            # Mines — low SO2 (no smelting on-site)
            "Tenke Fungurume (TFM)":   (0.00008, 0.00007, "LOW_SO2"),
            "Kisanfu (KFM)":           (0.00006, 0.00006, "LOW_SO2"),
            "Kamoto (KCC)":            (0.00009, 0.00008, "LOW_SO2"),
            "Mutanda":                 (0.00007, 0.00006, "LOW_SO2"),
            "Murrin Murrin":           (0.00004, 0.00003, "LOW_SO2"),
            "Moa JV":                  (0.00005, 0.00005, "LOW_SO2"),
            "Voisey's Bay":            (0.00003, 0.00003, "LOW_SO2"),
            "Sudbury Basin":           (0.00012, 0.00009, "LOW_SO2"),
            "Raglan Mine":             (0.00002, 0.00002, "LOW_SO2"),
        }
        result = {}
        for name, (so2, bg, status) in seeds.items():
            ratio = round(so2 / max(bg, 1e-8), 1)
            result[name] = {
                "so2_mol_m2": so2,
                "background_mol_m2": bg,
                "ratio": ratio,
                "status": status,
                "last_overpass": "2026-04-03",
                "source": "Sentinel-5P TROPOMI SO2 (fallback)",
                "history": [],
            }
        history = self._load_so2_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "so2_all_facilities", result)
        return result

    @staticmethod
    def _load_so2_history() -> dict[str, list[dict]]:
        if not _SO2_HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_SO2_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _save_so2_history(history: dict[str, list[dict]]) -> None:
        for name in history:
            history[name] = history[name][-90:]
        _SO2_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _SO2_HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def _snapshot_so2_history(self, all_data: dict[str, dict]) -> None:
        history = self._load_so2_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for name, data in all_data.items():
            if name not in history:
                history[name] = []
            existing_dates = {e["date"] for e in history[name]}
            if today in existing_dates:
                continue
            history[name].append({
                "date": today,
                "so2_mol_m2": data.get("so2_mol_m2"),
                "background_mol_m2": data.get("background_mol_m2"),
                "ratio": data.get("ratio", 0),
                "status": data.get("status", "UNKNOWN"),
            })
        self._save_so2_history(history)
        logger.info("Sentinel SO2 history snapshot saved for %d facilities", len(all_data))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_sentinel_no2.py -v`
Expected: all pass including `test_fallback_so2_data`

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/sentinel_no2.py tests/test_sentinel_no2.py
git commit -m "feat(satellite): add SO2 query, fetch, and fallback methods"
```

---

### Task 5: NDVI Query Method + Fetch Methods + Fallback Data

**Files:**
- Modify: `src/ingestion/sentinel_no2.py`
- Modify: `tests/test_sentinel_no2.py`

- [ ] **Step 1: Write fallback NDVI test**

Add to `tests/test_sentinel_no2.py`:

```python
def test_fallback_ndvi_data():
    """NDVI fallback data should cover all 9 mines."""
    from src.ingestion.sentinel_no2 import SentinelNO2Client, MINE_NAMES
    client = SentinelNO2Client()
    data = client._fallback_ndvi_data()
    assert len(data) == len(MINE_NAMES)
    for name, entry in data.items():
        assert name in MINE_NAMES
        assert "bare_soil_pct" in entry
        assert "status" in entry
        assert entry["status"] in ("ACTIVE_MINING", "MODERATE", "VEGETATED", "UNKNOWN")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sentinel_no2.py::test_fallback_ndvi_data -v`
Expected: FAIL

- [ ] **Step 3: Add MINE_NAMES constant, NDVI evalscript, query, fetch, and fallback methods**

Add near the top of `src/ingestion/sentinel_no2.py`, after the `FACILITY_CONFIG` import:

```python
MINE_NAMES = {
    "Tenke Fungurume (TFM)", "Kisanfu (KFM)", "Kamoto (KCC)", "Mutanda",
    "Murrin Murrin", "Moa JV", "Voisey's Bay", "Sudbury Basin", "Raglan Mine",
}
```

Add after `_SO2_HISTORY_PATH`:

```python
_NDVI_EVALSCRIPT = """//VERSION=3
function setup(){
  return {
    input: ["B04", "B08", "SCL", "dataMask"],
    output: { bands: 4, sampleType: "UINT8" }
  };
}
function evaluatePixel(s) {
  if (s.dataMask == 0) return [0, 0, 0, 0];
  var ndvi = (s.B08 - s.B04) / (s.B08 + s.B04 + 1e-10);
  var ndvi_scaled = Math.round((ndvi + 1) / 2 * 255);
  var bare = (s.SCL == 5) ? 255 : 0;
  return [ndvi_scaled, bare, 255, 255];
}"""

_NDVI_HISTORY_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sentinel_ndvi_history.json"
```

Add these methods to the `SentinelNO2Client` class, after the SO2 methods:

```python
    async def _query_bbox_ndvi(self, bbox: list[float], days: int = 30) -> dict | None:
        """Query NDVI + bare soil for a bbox. Returns {bare_soil_pct, mean_ndvi, cloud_free_pct} or None."""
        token = await self._get_token()
        if not token:
            return None
        now = datetime.now(timezone.utc)
        time_from = (now - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        time_to = now.strftime("%Y-%m-%dT23:59:59Z")
        payload = {
            "input": {
                "bounds": {
                    "bbox": bbox,
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": time_from, "to": time_to},
                        "maxCloudCoverage": 30,
                    },
                }],
            },
            "output": {
                "width": 32,
                "height": 32,
                "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
            },
            "evalscript": _NDVI_EVALSCRIPT,
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    _PROCESS_ENDPOINT, json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code != 200:
                    logger.warning("CDSE NDVI query returned HTTP %s", resp.status_code)
                    return None
                from PIL import Image
                img = Image.open(io.BytesIO(resp.content))
                pixels = list(img.getdata())
                total = len(pixels)
                # Channel 0 = NDVI scaled, Channel 1 = bare soil flag, Channel 3 = dataMask (always 255 if valid)
                valid = [(p[0], p[1]) for p in pixels if len(p) >= 4 and p[2] > 0]
                cloud_free_pct = round(len(valid) / max(total, 1) * 100)
                if not valid:
                    return {"bare_soil_pct": None, "mean_ndvi": None, "cloud_free_pct": cloud_free_pct}
                bare_count = sum(1 for _, b in valid if b > 128)
                bare_soil_pct = round(bare_count / len(valid) * 100, 1)
                mean_ndvi_scaled = sum(n for n, _ in valid) / len(valid)
                mean_ndvi = round((mean_ndvi_scaled / 255 * 2) - 1, 3)
                return {"bare_soil_pct": bare_soil_pct, "mean_ndvi": mean_ndvi, "cloud_free_pct": cloud_free_pct}
        except Exception as e:
            logger.warning("CDSE NDVI query failed: %s", e)
            return None

    async def fetch_facility_ndvi(self, name: str, lat: float, lon: float, radius_deg: float, days: int = 30) -> dict:
        """Fetch NDVI/bare-soil data for a single mine facility."""
        cache_key = f"ndvi_{name}_{days}"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        facility_bbox = _make_bbox(lat, lon, max(radius_deg, 0.05))
        result_data = await self._query_bbox_ndvi(facility_bbox, days)
        bare_soil_pct = result_data["bare_soil_pct"] if result_data else None
        mean_ndvi = result_data["mean_ndvi"] if result_data else None
        cloud_free_pct = result_data["cloud_free_pct"] if result_data else 0
        status_info = compute_ndvi_status(bare_soil_pct, mean_ndvi)
        result = {
            "bare_soil_pct": bare_soil_pct,
            "mean_ndvi": mean_ndvi,
            "status": status_info["status"],
            "cloud_free_pct": cloud_free_pct,
            "last_overpass": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "source": "Sentinel-2 L2A NDVI (live)",
        }
        _cache_set(self._cache, cache_key, result)
        return result

    async def fetch_all_facilities_ndvi(self) -> dict[str, dict]:
        """Fetch NDVI data for all 9 cobalt mines (skip refineries)."""
        cache_key = "ndvi_all_facilities"
        cached = _cache_get(self._cache, cache_key)
        if cached is not None:
            return cached
        if not self.client_id or not self.client_secret:
            logger.info("No SENTINEL credentials — using fallback NDVI data")
            return self._fallback_ndvi_data()
        result: dict[str, dict] = {}
        for name, cfg in FACILITY_CONFIG.items():
            if name not in MINE_NAMES:
                continue
            data = await self.fetch_facility_ndvi(
                name=name, lat=cfg["lat"], lon=cfg["lon"],
                radius_deg=cfg["radius_deg"], days=30,
            )
            result[name] = data
        self._snapshot_ndvi_history(result)
        history = self._load_ndvi_history()
        for name in result:
            result[name]["history"] = history.get(name, [])[-30:]
        _cache_set(self._cache, cache_key, result)
        active = sum(1 for v in result.values() if v["status"] == "ACTIVE_MINING")
        logger.info("Sentinel NDVI: %d/%d mines ACTIVE_MINING", active, len(result))
        return result

    def _fallback_ndvi_data(self) -> dict[str, dict]:
        """Seed NDVI data for mines when no credentials are configured."""
        seeds = {
            "Tenke Fungurume (TFM)": (82.0, 0.12, "ACTIVE_MINING"),
            "Kisanfu (KFM)":         (71.0, 0.18, "ACTIVE_MINING"),
            "Kamoto (KCC)":          (78.0, 0.14, "ACTIVE_MINING"),
            "Mutanda":               (65.0, 0.22, "ACTIVE_MINING"),
            "Murrin Murrin":          (55.0, 0.28, "MODERATE"),
            "Moa JV":                (38.0, 0.42, "MODERATE"),
            "Voisey's Bay":          (45.0, 0.35, "MODERATE"),
            "Sudbury Basin":         (52.0, 0.30, "MODERATE"),
            "Raglan Mine":           (62.0, 0.20, "ACTIVE_MINING"),
        }
        result = {}
        for name, (bare, ndvi, status) in seeds.items():
            result[name] = {
                "bare_soil_pct": bare,
                "mean_ndvi": ndvi,
                "status": status,
                "last_overpass": "2026-04-03",
                "source": "Sentinel-2 L2A NDVI (fallback)",
                "history": [],
            }
        history = self._load_ndvi_history()
        for name in result:
            if name in history:
                result[name]["history"] = history[name][-30:]
        _cache_set(self._cache, "ndvi_all_facilities", result)
        return result

    @staticmethod
    def _load_ndvi_history() -> dict[str, list[dict]]:
        if not _NDVI_HISTORY_PATH.exists():
            return {}
        try:
            return json.loads(_NDVI_HISTORY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}

    @staticmethod
    def _save_ndvi_history(history: dict[str, list[dict]]) -> None:
        for name in history:
            history[name] = history[name][-90:]
        _NDVI_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _NDVI_HISTORY_PATH.write_text(json.dumps(history, indent=1), encoding="utf-8")

    def _snapshot_ndvi_history(self, all_data: dict[str, dict]) -> None:
        history = self._load_ndvi_history()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for name, data in all_data.items():
            if name not in history:
                history[name] = []
            existing_dates = {e["date"] for e in history[name]}
            if today in existing_dates:
                continue
            history[name].append({
                "date": today,
                "bare_soil_pct": data.get("bare_soil_pct"),
                "mean_ndvi": data.get("mean_ndvi"),
                "status": data.get("status", "UNKNOWN"),
            })
        self._save_ndvi_history(history)
        logger.info("Sentinel NDVI history snapshot saved for %d mines", len(all_data))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_sentinel_no2.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/ingestion/sentinel_no2.py tests/test_sentinel_no2.py
git commit -m "feat(satellite): add NDVI bare-soil query, fetch, and fallback methods for mines"
```

---

### Task 6: Globe Routes — SO2 + NDVI Enrichment

**Files:**
- Modify: `src/api/globe_routes.py:61-91`

- [ ] **Step 1: Add SO2 enrichment block**

In `src/api/globe_routes.py`, after the NO2 enrichment block (after the `except` at line ~91), add:

```python
        # Enrich mines/refineries with Sentinel-5P SO2 smelting data
        try:
            from src.ingestion.sentinel_no2 import SentinelNO2Client as SO2Client
            so2_client = SO2Client()
            so2_data = await so2_client.fetch_all_facilities_so2()
            unknown_so2 = {"status": "UNKNOWN", "ratio": 0, "source": "Sentinel-5P SO2 (unavailable)", "history": []}
            for mine in mineral.get("mines", []):
                mine["so2"] = so2_data.get(mine["name"], unknown_so2)
            for ref in mineral.get("refineries", []):
                ref["so2"] = so2_data.get(ref["name"], unknown_so2)
        except Exception as e:
            logger.warning("Sentinel SO2 enrichment failed: %s", e)
```

- [ ] **Step 2: Add NDVI enrichment block**

Immediately after the SO2 block, add:

```python
        # Enrich mines with Sentinel-2 NDVI bare-soil activity data
        try:
            from src.ingestion.sentinel_no2 import SentinelNO2Client as NDVIClient
            ndvi_client = NDVIClient()
            ndvi_data = await ndvi_client.fetch_all_facilities_ndvi()
            unknown_ndvi = {"status": "UNKNOWN", "bare_soil_pct": 0, "source": "Sentinel-2 NDVI (unavailable)", "history": []}
            for mine in mineral.get("mines", []):
                mine["ndvi"] = ndvi_data.get(mine["name"], unknown_ndvi)
        except Exception as e:
            logger.warning("Sentinel NDVI enrichment failed: %s", e)
```

- [ ] **Step 3: Update verdict computation to pass all 4 signals + facility type**

Replace the existing verdict computation sections (in both mine and refinery loops) with:

```python
        # Compute tier-specific combined verdicts
        try:
            from src.ingestion.sentinel_no2 import compute_combined_verdict
            for mine in mineral.get("mines", []):
                t_status = mine.get("thermal", {}).get("status", "UNKNOWN")
                n_status = mine.get("no2", {}).get("status", "UNKNOWN")
                s_status = mine.get("so2", {}).get("status", "UNKNOWN")
                d_status = mine.get("ndvi", {}).get("status", "UNKNOWN")
                mine["operational_verdict"] = compute_combined_verdict(t_status, n_status, s_status, d_status, "mine")
            for ref in mineral.get("refineries", []):
                t_status = ref.get("thermal", {}).get("status", "UNKNOWN")
                n_status = ref.get("no2", {}).get("status", "UNKNOWN")
                s_status = ref.get("so2", {}).get("status", "UNKNOWN")
                d_status = ref.get("ndvi", {}).get("status", "UNKNOWN")
                ref["operational_verdict"] = compute_combined_verdict(t_status, n_status, s_status, d_status, "refinery")
        except Exception as e:
            logger.warning("Combined verdict computation failed: %s", e)
```

Note: remove the previous verdict computation that was inside the NO2 enrichment block to avoid duplicate computation.

- [ ] **Step 4: Run globe tests**

Run: `python -m pytest tests/test_globe.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/api/globe_routes.py
git commit -m "feat(globe): enrich facilities with SO2 + NDVI data, tier-specific verdicts"
```

---

### Task 7: Scheduler Jobs — SO2 Daily + NDVI Weekly

**Files:**
- Modify: `src/ingestion/scheduler.py:786-788`
- Modify: `tests/test_scheduler_feeds.py`

- [ ] **Step 1: Add SO2 scheduler job**

In `src/ingestion/scheduler.py`, before the `return scheduler` line at the end, add:

```python
    # Sentinel-5P SO2 facility smelting monitoring (daily at 03:30 UTC)
    async def refresh_sentinel_so2():
        from src.ingestion.sentinel_no2 import SentinelNO2Client, _SO2_HISTORY_PATH
        client = SentinelNO2Client()
        if not _SO2_HISTORY_PATH.exists():
            logger.info("[sentinel_so2] First run — backfilling not implemented yet")
        data = await client.fetch_all_facilities_so2()
        smelting = sum(1 for v in data.values() if v["status"] == "SMELTING")
        logger.info("[sentinel_so2] %d/%d facilities SMELTING", smelting, len(data))

    scheduler.add_job(
        resilient_job("sentinel_so2", timeout_s=300)(refresh_sentinel_so2),
        CronTrigger(hour=3, minute=30),
        id="sentinel_so2",
        name="Sentinel-5P SO2 facility smelting (18 facilities)",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 2: Add NDVI scheduler job**

Immediately after, add:

```python
    # Sentinel-2 NDVI mine activity monitoring (weekly Sunday 04:00 UTC)
    async def refresh_sentinel_ndvi():
        from src.ingestion.sentinel_no2 import SentinelNO2Client, _NDVI_HISTORY_PATH
        client = SentinelNO2Client()
        if not _NDVI_HISTORY_PATH.exists():
            logger.info("[sentinel_ndvi] First run — backfilling not implemented yet")
        data = await client.fetch_all_facilities_ndvi()
        active = sum(1 for v in data.values() if v["status"] == "ACTIVE_MINING")
        logger.info("[sentinel_ndvi] %d/%d mines ACTIVE_MINING", active, len(data))

    scheduler.add_job(
        resilient_job("sentinel_ndvi", timeout_s=300)(refresh_sentinel_ndvi),
        CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="sentinel_ndvi",
        name="Sentinel-2 NDVI mine activity (9 mines)",
        replace_existing=True,
        max_instances=1,
    )
```

- [ ] **Step 3: Update scheduler test assertion**

In `tests/test_scheduler_feeds.py`, update the job count assertion:

```python
    assert len(jobs) >= 22, f"Expected >= 22 jobs, got {len(jobs)}: {sorted(job_ids)}"
```

Change to:

```python
    assert len(jobs) >= 24, f"Expected >= 24 jobs, got {len(jobs)}: {sorted(job_ids)}"
```

And add the new job ID assertions:

```python
    assert "sentinel_so2" in job_ids
    assert "sentinel_ndvi" in job_ids
```

- [ ] **Step 4: Update scheduler docstring**

Add to the schedule comment at the top of `scheduler.py`:

```
  - Sentinel-5P SO2:         daily 3:30 AM
  - Sentinel-2 NDVI:         weekly Sunday 4 AM
```

- [ ] **Step 5: Run scheduler tests**

Run: `python -m pytest tests/test_scheduler_feeds.py -v`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/ingestion/scheduler.py tests/test_scheduler_feeds.py
git commit -m "feat(scheduler): add SO2 daily and NDVI weekly polling jobs"
```

---

### Task 8: Frontend — Verification Tab SO2/NDVI Charts + Scoring

**Files:**
- Modify: `src/static/index.html` (verification tab section, ~line 13332-13530)

- [ ] **Step 1: Update computeVerificationScore to use tier-specific 3-signal scoring**

Find the `computeVerificationScore` function (~line 13332). Replace the satellite activity calculation section:

Old:
```javascript
  var thermalActiveDays = thermalHistory.filter(function(h) { return h.count > 0; }).length;
  var no2EmittingDays = no2History.filter(function(h) { return (h.ratio || 0) >= 1.5; }).length;
  var totalDays = Math.max(thermalHistory.length, no2History.length, 1);
```

New:
```javascript
  var thermalActiveDays = thermalHistory.filter(function(h) { return h.count > 0; }).length;
  var no2EmittingDays = no2History.filter(function(h) { return (h.ratio || 0) >= 1.5; }).length;

  // Tier-specific third signal
  var so2 = facility.so2 || {};
  var ndvi = facility.ndvi || {};
  var so2History = so2.history || [];
  var ndviHistory = ndvi.history || [];
  var isMine = !(facility._isRefinery);
  var thirdSignalDays;
  if (isMine) {
    thirdSignalDays = ndviHistory.filter(function(h) { return h.status === 'ACTIVE_MINING'; }).length;
  } else {
    thirdSignalDays = so2History.filter(function(h) { return (h.ratio || 0) >= 1.5; }).length;
  }

  var totalDays = Math.max(thermalHistory.length, no2History.length, (isMine ? ndviHistory.length : so2History.length), 1);
  var satelliteActivityPct = Math.max(thermalActiveDays, no2EmittingDays, thirdSignalDays) / totalDays;
```

- [ ] **Step 2: Update renderVerificationTab to tag facilities and add third signal to charts**

In `renderVerificationTab` (~line 13400), where facilities are concatenated from mines and refineries, add a tagging step:

```javascript
  var mines = (m.mines || []).map(function(f) { f._isRefinery = false; return f; });
  var refFacilities = (m.refineries || []).map(function(f) { f._isRefinery = true; return f; });
  var facilities = mines.concat(refFacilities);
```

Replace the existing `var facilities = (m.mines || []).concat(m.refineries || []);` line.

- [ ] **Step 3: Add signal badges to each verification card**

In the card rendering section, after the verdict badge, add a signal summary line:

```javascript
var signals = [];
if ((f.thermal || {}).status === 'ACTIVE') signals.push('<span style="color:#ff4444;">THERMAL</span>');
if ((f.no2 || {}).status === 'EMITTING') signals.push('<span style="color:#a050dc;">NO2</span>');
if (f._isRefinery && (f.so2 || {}).status === 'SMELTING') signals.push('<span style="color:#e6c619;">SO2</span>');
if (!f._isRefinery && (f.ndvi || {}).status === 'ACTIVE_MINING') signals.push('<span style="color:#6b9080;">NDVI</span>');
html += '<div style="font-size:9px; font-family:var(--font-mono); color:var(--text-dim); margin-top:4px;">Signals: ' + (signals.length > 0 ? signals.join(' + ') : 'None') + '</div>';
```

- [ ] **Step 4: Add third signal dataset to renderVerificationChart**

In the `renderVerificationChart` function (~line 13581), add a third dataset to the Chart.js config:

After the NO2 dataset, add:

```javascript
// Third signal: SO2 (refineries, yellow) or NDVI bare soil (mines, green)
var thirdLabel, thirdData, thirdColor;
if (facility._isRefinery) {
  thirdLabel = 'SO2 Ratio';
  thirdData = (facility.so2 && facility.so2.history || []).map(function(h) { return h.ratio || 0; });
  thirdColor = '#e6c619';
} else {
  thirdLabel = 'Bare Soil %';
  thirdData = (facility.ndvi && facility.ndvi.history || []).map(function(h) { return h.bare_soil_pct || 0; });
  thirdColor = '#6b9080';
}
```

Add the third dataset to the Chart.js datasets array:

```javascript
{
  label: thirdLabel,
  data: thirdData,
  backgroundColor: thirdColor + '66',
  borderColor: thirdColor,
  borderWidth: 1,
  yAxisID: facility._isRefinery ? 'y1' : 'y2',
  type: 'bar',
  order: 3,
}
```

If the facility is a mine, add a third Y axis for bare soil %:

```javascript
y2: {
  position: 'right',
  display: !facility._isRefinery,
  title: { display: true, text: 'Bare Soil %', color: '#6b9080', font: { size: 9 } },
  min: 0, max: 100,
  grid: { display: false },
}
```

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(ui): add SO2/NDVI to verification tab scoring and charts"
```

---

### Task 9: Frontend — Alerts Satellite Card SO2/NDVI KPIs + Anomalies

**Files:**
- Modify: `src/static/index.html` (Alerts & Sensing satellite intelligence section, ~line 10670-10756)

- [ ] **Step 1: Add SO2 and NDVI counters to anomaly detection loop**

In the facility loop that starts around line 10675, add counters:

```javascript
var so2Smelting = 0, ndviActive = 0;
```

Inside the loop, add:

```javascript
      var sStatus = (f.so2 || {}).status || 'UNKNOWN';
      var dStatus = (f.ndvi || {}).status || 'UNKNOWN';
      if (sStatus === 'SMELTING') so2Smelting++;
      if (dStatus === 'ACTIVE_MINING') ndviActive++;
```

- [ ] **Step 2: Add VEGETATED_BUT_OPERATING anomaly**

After the existing `OPERATING_NO_SIGNAL` anomaly check, add:

```javascript
      // Mine reports production but NDVI shows vegetation recovery (no bare soil)
      if (capacity > 1000 && !isPaused && dStatus === 'VEGETATED' && note.indexOf('mine') >= 0) {
        anomalies.push({name: f.name, type: 'VEGETATED_BUT_OPERATING', detail: 'Reports ' + capacity.toLocaleString() + ' t/yr but NDVI shows vegetation recovery (bare soil < 30%)'});
      }
```

Update the anomaly card color logic:

```javascript
        var aColor = a.type === 'PAUSED_BUT_ACTIVE' ? '#D80621' : a.type === 'VEGETATED_BUT_OPERATING' ? '#6b9080' : '#a89060';
        var aBadge = a.type === 'PAUSED_BUT_ACTIVE' ? 'INVESTIGATE' : a.type === 'VEGETATED_BUT_OPERATING' ? 'VERIFY' : 'MONITOR';
```

- [ ] **Step 3: Add SO2 and NDVI KPI boxes**

After the "NO2 Emitting" KPI box and before the "Anomalies" KPI box, add:

```javascript
    html += '<div style="text-align:center; padding:8px; background:rgba(255,255,255,0.02); border:1px solid var(--border);">';
    html += '<div style="font-family:var(--font-mono); font-size:18px; font-weight:700; color:#e6c619;">' + so2Smelting + '</div>';
    html += '<div style="font-size:9px; color:var(--text-muted); text-transform:uppercase;">SO2 Smelting</div></div>';
    html += '<div style="text-align:center; padding:8px; background:rgba(255,255,255,0.02); border:1px solid var(--border);">';
    html += '<div style="font-family:var(--font-mono); font-size:18px; font-weight:700; color:#6b9080;">' + ndviActive + '</div>';
    html += '<div style="font-size:9px; color:var(--text-muted); text-transform:uppercase;">NDVI Active</div></div>';
```

- [ ] **Step 4: Add source badges**

After the existing "Sentinel-5P TROPOMI" badge, add:

```javascript
    html += '<span style="font-size:9px; font-family:var(--font-mono); padding:2px 6px; background:rgba(230,198,25,0.08); border:1px solid rgba(230,198,25,0.2); color:#e6c619;">Sentinel-5P SO2 (5.5km)</span>';
    html += '<span style="font-size:9px; font-family:var(--font-mono); padding:2px 6px; background:rgba(107,144,128,0.08); border:1px solid rgba(107,144,128,0.2); color:#6b9080;">Sentinel-2 NDVI (10m)</span>';
```

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(ui): add SO2/NDVI KPIs and anomaly detection to Alerts satellite card"
```

---

### Task 10: Frontend — Globe Layers (SO2 Plumes + NDVI Markers)

**Files:**
- Modify: `src/static/index.html` (globe rendering section + layer control panel)

- [ ] **Step 1: Add SO2 plume rendering**

Find the NO2 plume rendering section (search for `NO2 Emissions` or `no2.*plume`). After the NO2 plume rendering block, add an equivalent SO2 block using yellow color:

```javascript
// SO2 smelting plumes (yellow, refineries only)
if (so2Status === 'SMELTING') {
  [0.015, 0.010, 0.005].forEach(function(r, i) {
    supplyViewer.entities.add({
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      ellipse: {
        semiMajorAxis: r * 111000,
        semiMinorAxis: r * 111000 * 0.7,
        height: 100,
        material: Cesium.Color.YELLOW.withAlpha(0.08 - i * 0.02),
        outline: i === 0,
        outlineColor: Cesium.Color.YELLOW.withAlpha(0.3),
      },
      _layerGroup: 'so2_plumes',
    });
  });
}
```

- [ ] **Step 2: Add NDVI bare soil markers**

After the SO2 block, add NDVI markers for mines:

```javascript
// NDVI active mining markers (orange circles, mines only)
if (ndviStatus === 'ACTIVE_MINING') {
  supplyViewer.entities.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat),
    ellipse: {
      semiMajorAxis: radiusDeg * 111000,
      semiMinorAxis: radiusDeg * 111000,
      height: 50,
      material: Cesium.Color.ORANGE.withAlpha(0.12),
      outline: true,
      outlineColor: Cesium.Color.ORANGE.withAlpha(0.4),
    },
    _layerGroup: 'ndvi_activity',
  });
}
```

- [ ] **Step 3: Add layer toggles**

In the layer control panel, add two new toggle entries:

```javascript
{id: 'so2_plumes', label: 'SO2 Emissions (S5P)', color: '#e6c619', defaultOn: true},
{id: 'ndvi_activity', label: 'Mine Activity (NDVI)', color: '#6b9080', defaultOn: true},
```

- [ ] **Step 4: Add SO2/NDVI to dossier popup**

In the dossier popup rendering, after the NO2 section, add:

For refineries (check if so2 data exists):
```javascript
if (f.so2 && f.so2.status !== 'UNKNOWN') {
  html += '<div style="margin-top:8px; padding-top:6px; border-top:1px solid var(--border);">';
  html += '<div style="font-size:9px; font-family:var(--font-mono); color:#e6c619; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">SO2 SMELTING VERIFICATION</div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">SO2 Ratio: <span style="color:#e6c619; font-weight:600;">' + (f.so2.ratio || 0) + 'x background</span></div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">Status: <span style="font-weight:600; color:' + (f.so2.status === 'SMELTING' ? '#e6c619' : 'var(--text-dim)') + ';">' + f.so2.status + '</span></div>';
  html += '</div>';
}
```

For mines (check if ndvi data exists):
```javascript
if (f.ndvi && f.ndvi.status !== 'UNKNOWN') {
  html += '<div style="margin-top:8px; padding-top:6px; border-top:1px solid var(--border);">';
  html += '<div style="font-size:9px; font-family:var(--font-mono); color:#6b9080; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px;">LAND ACTIVITY (NDVI)</div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">Bare Soil: <span style="color:#6b9080; font-weight:600;">' + (f.ndvi.bare_soil_pct || 0) + '%</span></div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">Mean NDVI: <span style="font-weight:600;">' + (f.ndvi.mean_ndvi || 0) + '</span></div>';
  html += '<div style="font-size:11px; color:var(--text-dim);">Status: <span style="font-weight:600; color:' + (f.ndvi.status === 'ACTIVE_MINING' ? '#6b9080' : 'var(--text-dim)') + ';">' + f.ndvi.status + '</span></div>';
  html += '</div>';
}
```

- [ ] **Step 5: Commit**

```bash
git add src/static/index.html
git commit -m "feat(ui): add SO2 plumes, NDVI markers, layer toggles, and dossier sections"
```

---

### Task 11: Initialize History Files + Run Full Test Suite

**Files:**
- Create: `data/sentinel_so2_history.json`
- Create: `data/sentinel_ndvi_history.json`

- [ ] **Step 1: Create empty history files**

```bash
echo "{}" > data/sentinel_so2_history.json
echo "{}" > data/sentinel_ndvi_history.json
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: all tests pass (365 existing + ~15 new = ~380)

- [ ] **Step 3: Update CLAUDE.md**

Update the relevant sections:
- Data Sources table: add rows 54 (Sentinel-5P SO2) and 55 (Sentinel-2 NDVI)
- Intelligence Features: update Satellite NO2 → Satellite Emissions (NO2 + SO2), add NDVI entry
- Tests count: update to new total
- Scheduler jobs: mention 30 jobs
- Known items: note SO2 has same 5.5km limitation as NO2

- [ ] **Step 4: Final commit**

```bash
git add data/sentinel_so2_history.json data/sentinel_ndvi_history.json CLAUDE.md
git commit -m "feat(satellite): initialize SO2/NDVI history files, update CLAUDE.md"
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | SO2 status function | 4 tests |
| 2 | NDVI status function | 4 tests |
| 3 | Expanded 4-signal verdict | 8 tests |
| 4 | SO2 query + fetch + fallback | 1 test |
| 5 | NDVI query + fetch + fallback | 1 test |
| 6 | Globe routes enrichment | existing globe tests |
| 7 | Scheduler jobs | scheduler test update |
| 8 | Frontend verification charts | manual QA |
| 9 | Frontend alerts KPIs | manual QA |
| 10 | Frontend globe layers | manual QA |
| 11 | History files + CLAUDE.md | full suite |
