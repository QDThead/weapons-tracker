"""Financial scoring module — Altman Z-Score computation.

Computes real Altman Z-scores from financial filing data for
cobalt supply chain entities. Used by Supplier Dossier sub-tab.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_altman_z(financials: dict) -> dict:
    """Compute Altman Z-Score from financial statement data.

    Z = 1.2*(WC/TA) + 1.4*(RE/TA) + 3.3*(EBIT/TA) + 0.6*(MVE/TL) + 1.0*(S/TA)

    Parameters
    ----------
    financials : dict with keys:
        total_assets_usd_m, total_liabilities_usd_m, working_capital_usd_m,
        retained_earnings_usd_m, ebit_usd_m, revenue_usd_m, market_cap_usd_m

    Returns
    -------
    dict with z_score, zone, components, source
    """
    ta = financials.get("total_assets_usd_m", 0)
    tl = financials.get("total_liabilities_usd_m", 0)
    wc = financials.get("working_capital_usd_m", 0)
    re = financials.get("retained_earnings_usd_m", 0)
    ebit = financials.get("ebit_usd_m", 0)
    rev = financials.get("revenue_usd_m", 0)
    mve = financials.get("market_cap_usd_m", 0)

    if ta == 0 or tl == 0:
        return {
            "z_score": None,
            "zone": "insufficient_data",
            "source": financials.get("source", "unknown"),
            "error": "Total assets or liabilities is zero",
        }

    x1 = wc / ta          # Working Capital / Total Assets
    x2 = re / ta          # Retained Earnings / Total Assets
    x3 = ebit / ta        # EBIT / Total Assets
    x4 = mve / tl         # Market Value of Equity / Total Liabilities
    x5 = rev / ta         # Sales / Total Assets

    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5
    z = round(z, 2)

    # Altman zones
    if z > 2.99:
        zone = "safe"
    elif z > 1.81:
        zone = "grey"
    else:
        zone = "distress"

    # Insolvency probability estimate (rough mapping)
    if z > 3.0:
        insolvency_pct = 2
    elif z > 2.5:
        insolvency_pct = 5
    elif z > 2.0:
        insolvency_pct = 15
    elif z > 1.5:
        insolvency_pct = 35
    elif z > 1.0:
        insolvency_pct = 55
    else:
        insolvency_pct = 75

    return {
        "z_score": z,
        "zone": zone,
        "insolvency_pct": insolvency_pct,
        "components": {
            "x1_working_capital_ratio": round(x1, 4),
            "x2_retained_earnings_ratio": round(x2, 4),
            "x3_ebit_ratio": round(x3, 4),
            "x4_market_equity_ratio": round(x4, 4),
            "x5_asset_turnover": round(x5, 4),
        },
        "source": financials.get("source", "unknown"),
        "period": financials.get("period", "unknown"),
    }


def compute_sherritt_z_score(sherritt_financials: dict) -> dict:
    """Compute Altman Z-Score specifically for Sherritt International.

    Convenience wrapper that adds Sherritt-specific context.
    """
    result = compute_altman_z(sherritt_financials)
    result["entity"] = "Sherritt International"
    result["ticker"] = "TSX:S"
    result["note"] = (
        "Sherritt has significant going concern risk noted by auditors. "
        "Fort Saskatchewan refinery is a strategic Canadian asset."
    )
    return result
