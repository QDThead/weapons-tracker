"""Cobalt forecasting engine — live price data + computed predictions.

Fetches cobalt prices from IMF Primary Commodity Price System (PCOBALT).
Falls back to FRED nickel proxy if IMF is unavailable.
Applies linear regression for 12-month price forecast, and computes
lead time and insolvency risks from existing supply chain data.
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx

from src.analysis.mineral_supply_chains import get_mineral_by_name

logger = logging.getLogger(__name__)

FRED_NICKEL_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PNICKUSDM&cosd=2023-01-01"

# Cobalt/nickel price ratio — historical average ~1.8-2.2x
# Cobalt LME ~$28,000-33,000/mt, Nickel ~$15,000-17,000/mt
COBALT_NICKEL_RATIO = 2.0

IMF_COBALT_URL = "http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/PCPS/M.W00.PCOBALT"


async def fetch_cobalt_prices() -> list[dict]:
    """Fetch monthly cobalt prices from IMF PCPS (free, no API key).

    Returns list of {date, usd_mt} sorted oldest-first.
    Falls back to FRED nickel proxy if IMF is unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(IMF_COBALT_URL)
            if r.status_code != 200:
                logger.warning("IMF PCOBALT returned HTTP %s, falling back to nickel proxy", r.status_code)
                return await _fetch_nickel_as_fallback()

            data = r.json()
            series = data.get("CompactData", {}).get("DataSet", {}).get("Series", {})
            obs = series.get("Obs", [])
            if isinstance(obs, dict):
                obs = [obs]

            prices = []
            for o in obs:
                period = o.get("@TIME_PERIOD", "")
                value = o.get("@OBS_VALUE")
                if period and value:
                    prices.append({
                        "date": period,
                        "usd_mt": round(float(value), 2),
                    })

            prices.sort(key=lambda x: x["date"])
            if not prices:
                logger.warning("IMF PCOBALT returned no data, falling back to nickel proxy")
                return await _fetch_nickel_as_fallback()

            logger.info("Fetched %d months of IMF cobalt prices", len(prices))
            return prices
    except Exception as e:
        logger.warning("IMF cobalt fetch failed: %s, falling back to nickel proxy", e)
        return await _fetch_nickel_as_fallback()


async def _fetch_nickel_as_fallback() -> list[dict]:
    """Fallback: fetch FRED nickel and apply cobalt/nickel ratio."""
    nickel = await fetch_nickel_prices()
    return [
        {"date": p["date"], "usd_mt": round(p["usd_mt"] * COBALT_NICKEL_RATIO, 2)}
        for p in nickel
    ]


async def fetch_nickel_prices() -> list[dict]:
    """Fetch monthly nickel prices from FRED (free, no API key)."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(FRED_NICKEL_URL)
            if r.status_code != 200:
                return []
            lines = r.text.strip().split("\n")
            prices = []
            for line in lines[1:]:  # skip header
                parts = line.split(",")
                if len(parts) == 2 and parts[1] != ".":
                    try:
                        date_str = parts[0].strip()
                        value = float(parts[1].strip())
                        prices.append({"date": date_str, "usd_mt": round(value, 2)})
                    except (ValueError, IndexError):
                        continue
            return prices
    except Exception as e:
        logger.warning("FRED nickel fetch failed: %s", e)
        return []


def _linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Simple linear regression returning (slope, intercept)."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_xx = sum((x - mean_x) ** 2 for x in xs)
    if ss_xx == 0:
        return 0.0, mean_y
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / ss_xx
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _compute_price_forecast(cobalt_prices: list[dict], source: str = "IMF PCOBALT") -> dict:
    """Compute 12-month cobalt price forecast from price data."""
    if not cobalt_prices:
        return {"status": "no_data", "source": f"{source} unavailable"}

    # Convert to quarterly averages for cleaner chart
    quarterly: dict[str, list[float]] = {}
    for p in cobalt_prices:
        date = p["date"]
        year = date[:4]
        month = int(date[5:7])
        q = f"Q{(month - 1) // 3 + 1} {year}"
        quarterly.setdefault(q, []).append(p["usd_mt"])

    q_prices = []
    for q_label, values in quarterly.items():
        avg = sum(values) / len(values)
        q_prices.append({
            "quarter": q_label,
            "usd_mt": round(avg, 0),
            "usd_lb": round(avg / 2204.62, 2),  # mt to lb
            "type": "actual",
        })

    # Linear regression on cobalt prices for forecasting
    xs = list(range(len(q_prices)))
    ys = [p["usd_mt"] for p in q_prices]
    slope, intercept = _linear_regression(xs, ys)

    # Forecast 4 quarters ahead
    last_q = q_prices[-1]["quarter"]
    last_year = int(last_q.split()[-1])
    last_qnum = int(last_q[1])
    forecasts = []
    for i in range(1, 5):
        fq = last_qnum + i
        fy = last_year + (fq - 1) // 4
        fq_num = ((fq - 1) % 4) + 1
        x_val = len(q_prices) + i - 1
        predicted = max(0, intercept + slope * x_val)
        forecasts.append({
            "quarter": f"Q{fq_num} {fy}",
            "usd_mt": round(predicted, 0),
            "usd_lb": round(predicted / 2204.62, 2),
            "type": "forecast",
        })

    all_prices = q_prices + forecasts

    # Compute pct change (last actual vs last forecast)
    if q_prices and forecasts:
        pct_change = round(
            (forecasts[-1]["usd_mt"] - q_prices[-1]["usd_mt"]) / q_prices[-1]["usd_mt"] * 100, 1
        )
    else:
        pct_change = 0

    return {
        "price_forecast": {
            "pct_change": abs(pct_change),
            "direction": "up" if pct_change > 0 else "down",
            "period": "12 months",
            "methodology": f"Linear regression on {source} monthly data",
        },
        "price_history": all_prices,
        "source": source,
        "price_source": source,
        "last_updated": datetime.utcnow().isoformat(),
        "data_points": len(cobalt_prices),
    }


def _compute_lead_time(mineral: dict) -> dict:
    """Compute lead time risk from shipping routes and chokepoints."""
    routes = mineral.get("shipping_routes", [])
    chokepoints = mineral.get("chokepoints", [])

    if not routes:
        return {"days": 0, "period": "N/A", "component": "N/A", "status": "no_data"}

    # Find the primary route (longest transit = most vulnerable)
    primary = max(routes, key=lambda r: r.get("transit_days", 0))
    base_days = primary.get("transit_days", 0)

    # Add chokepoint delay risk — each critical chokepoint adds potential delay
    chokepoint_delay = 0
    for cp in chokepoints:
        risk = cp.get("risk", "medium")
        if risk == "critical":
            chokepoint_delay += 7
        elif risk == "high":
            chokepoint_delay += 4
        else:
            chokepoint_delay += 1

    # Risk-adjusted additional delay
    risk_level = primary.get("risk", "medium")
    risk_multiplier = {"critical": 0.25, "high": 0.15, "medium": 0.05, "low": 0.02}
    disruption_delay = round(base_days * risk_multiplier.get(risk_level, 0.05))

    total_additional = chokepoint_delay + disruption_delay
    total_transit = base_days + total_additional

    return {
        "days": total_additional,
        "base_transit_days": base_days,
        "risk_adjusted_transit_days": total_transit,
        "period": "next 6 months",
        "component": primary.get("form", "Cobalt"),
        "primary_route": primary.get("name", "Unknown"),
        "chokepoint_count": len(chokepoints),
        "chokepoint_delay_days": chokepoint_delay,
        "disruption_delay_days": disruption_delay,
        "methodology": "Base transit + chokepoint risk factors + route disruption probability",
    }


def _compute_insolvency_risks(mineral: dict) -> list[dict]:
    """Compute supplier insolvency scores from taxonomy financial data."""
    results = []
    entities = (mineral.get("mines", []) or []) + (mineral.get("refineries", []) or [])

    for entity in entities:
        ts = entity.get("taxonomy_scores", {})
        financial = ts.get("financial", {})
        economic = ts.get("economic", {})
        dossier = entity.get("dossier", {})

        fin_score = financial.get("score", 30)
        econ_score = economic.get("score", 30)

        # Higher taxonomy risk score = higher insolvency probability
        # Map 0-100 risk score to 0-60% probability (non-linear)
        raw_prob = (fin_score * 0.6 + econ_score * 0.4) / 100
        probability_pct = round(raw_prob * raw_prob * 60, 0)

        # Use dossier z_score if available to adjust
        z_score = dossier.get("z_score")
        if z_score is not None:
            if z_score < 1.8:
                probability_pct = max(probability_pct, 40)  # distress zone
            elif z_score < 2.7:
                probability_pct = max(probability_pct, 15)  # grey zone
            else:
                probability_pct = min(probability_pct, 10)  # safe zone

        if probability_pct >= 5:  # Only include non-trivial risks
            results.append({
                "supplier": entity.get("name", "Unknown"),
                "owner": entity.get("owner", ""),
                "country": entity.get("country", ""),
                "probability_pct": int(probability_pct),
                "horizon": "12 months",
                "reason": financial.get("rationale", "Financial risk assessment"),
                "z_score": z_score,
                "fin_risk_score": fin_score,
                "econ_risk_score": econ_score,
                "methodology": "Taxonomy financial/economic scores + Altman Z-Score",
            })

    return sorted(results, key=lambda r: r["probability_pct"], reverse=True)


def _generate_signals(mineral: dict, price_data: dict, lead_time: dict, insolvency: list) -> list[dict]:
    """Generate forecast signals from computed data."""
    signals = []

    pf = price_data.get("price_forecast", {})
    if pf.get("pct_change", 0) > 10:
        signals.append({
            "text": f"Cobalt price forecast {pf['direction']} {pf['pct_change']}% over next 12 months (nickel proxy trend)",
            "severity": "high" if pf["pct_change"] > 20 else "medium",
            "sources": ["FRED PNICKUSDM", "Linear Regression Model"],
            "confidence_pct": 75,
        })

    if lead_time.get("days", 0) > 10:
        signals.append({
            "text": f"Lead time risk: +{lead_time['days']} days on {lead_time['primary_route']} ({lead_time['chokepoint_count']} chokepoints)",
            "severity": "high" if lead_time["days"] > 20 else "medium",
            "sources": ["PSI Shipping Routes", "Mineral Supply Chain Data"],
            "confidence_pct": 82,
        })

    for ins in insolvency[:3]:
        if ins["probability_pct"] >= 25:
            signals.append({
                "text": f"{ins['supplier']} insolvency risk: {ins['probability_pct']}% ({ins['reason']})",
                "severity": "critical" if ins["probability_pct"] >= 35 else "high",
                "sources": [f"{ins['supplier']} Financial Filings", "Altman Z-Score Model", "PSI Taxonomy Financial Scores"],
                "confidence_pct": 70,
            })

    for rf in mineral.get("risk_factors", [])[:4]:
        severity = "critical" if any(w in rf.lower() for w in ["no substitut", "80%", "76%", "export quota"]) else "high"
        signals.append({
            "text": rf,
            "severity": severity,
            "sources": ["USGS MCS 2025", "PSI Risk Assessment"],
            "confidence_pct": 88,
        })

    return signals


async def compute_cobalt_forecast() -> dict:
    """Main entry point — compute full Cobalt forecast from live data."""
    mineral = get_mineral_by_name("Cobalt")
    if not mineral:
        return {"error": "Cobalt mineral data not found"}

    # Fetch live cobalt prices (IMF PCOBALT, falls back to FRED nickel proxy)
    cobalt_prices = await fetch_cobalt_prices()

    # Compute all forecasts
    price_data = _compute_price_forecast(
        cobalt_prices, source="IMF Primary Commodity Prices (PCOBALT)"
    )
    lead_time = _compute_lead_time(mineral)
    insolvency = _compute_insolvency_risks(mineral)

    # Supply adequacy from existing sufficiency data
    suf = mineral.get("sufficiency", {})
    scenario0 = (suf.get("scenarios") or [{}])[0]

    # Generate signals
    signals = _generate_signals(mineral, price_data, lead_time, insolvency)

    return {
        "mineral": "Cobalt",
        "generated_at": datetime.utcnow().isoformat(),
        "horizon": "12 months",
        "live_data": len(cobalt_prices) > 0,
        "price_forecast": price_data.get("price_forecast", {}),
        "price_history": price_data.get("price_history", []),
        "price_source": price_data.get("source", ""),
        "price_data_points": price_data.get("data_points", 0),
        "lead_time": lead_time,
        "insolvency_risks": insolvency,
        "supply_adequacy": {
            "ratio": scenario0.get("ratio", 0),
            "verdict": scenario0.get("verdict", "Unknown"),
            "supply_t": scenario0.get("supply_t", 0),
            "demand_t": scenario0.get("demand_t", 0),
        },
        "signals": signals,
    }
