"""Auto-generated intelligence insights from arms trade data.

Computes pattern changes, anomalies, and key takeaways
that analysts can act on without manual data exploration.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from src.storage.database import SessionLocal

router = APIRouter(prefix="/insights", tags=["Insights"])


def _query(session, sql, params=None):
    return session.execute(text(sql), params or {}).fetchall()


@router.get("/freshness")
async def get_data_freshness():
    """Get freshness timestamps for all data sources."""
    session = SessionLocal()
    try:
        sources = []

        # SIPRI Arms Transfers
        r = _query(session, """
            SELECT MAX(order_year), MAX(updated_at), COUNT(*),
                   COUNT(DISTINCT seller_id), COUNT(DISTINCT buyer_id)
            FROM arms_transfers
        """)
        if r:
            sources.append({
                "source": "SIPRI Arms Transfers",
                "records": r[0][2],
                "latest_data_year": r[0][0],
                "last_updated": r[0][1],
                "update_frequency": "Annual (March)",
                "sellers": r[0][3],
                "buyers": r[0][4],
            })

        # World Bank
        r = _query(session, "SELECT MAX(year), COUNT(*) FROM trade_indicators")
        if r:
            sources.append({
                "source": "World Bank Indicators",
                "records": r[0][1],
                "latest_data_year": r[0][0],
                "last_updated": None,
                "update_frequency": "Annual",
            })

        # Flight Tracking
        r = _query(session, "SELECT MAX(detected_at), COUNT(*) FROM delivery_tracking")
        if r:
            sources.append({
                "source": "Military Flights (adsb.lol)",
                "records": r[0][1],
                "latest_data_year": None,
                "last_updated": r[0][0],
                "update_frequency": "Every 5 minutes (live)",
            })

        # GDELT News
        r = _query(session, "SELECT MAX(published_at), MAX(created_at), COUNT(*) FROM arms_trade_news")
        if r:
            sources.append({
                "source": "Arms Trade News (GDELT)",
                "records": r[0][2],
                "latest_data_year": None,
                "last_updated": r[0][1] or r[0][0],
                "update_frequency": "Every 15 minutes",
            })

        # UN Comtrade (not persisted)
        sources.append({
            "source": "UN Comtrade (USD values)",
            "records": "live",
            "latest_data_year": 2023,
            "last_updated": "cached (1hr TTL)",
            "update_frequency": "Annual (~6 month lag)",
        })

        # US Census Monthly Trade (not persisted)
        sources.append({
            "source": "US Census Monthly Trade",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (1hr TTL)",
            "update_frequency": "Monthly (~2 month lag)",
        })

        # Defense News RSS (not persisted)
        sources.append({
            "source": "Defense News RSS",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (15min TTL)",
            "update_frequency": "Every 15 minutes (4 feeds)",
        })

        # Eurostat EU Trade (not persisted)
        sources.append({
            "source": "Eurostat EU Arms Trade",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (1hr TTL)",
            "update_frequency": "Monthly (~2 month lag)",
        })

        # Statistics Canada (not persisted)
        sources.append({
            "source": "Statistics Canada CIMT",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (24hr TTL)",
            "update_frequency": "Monthly (~6 week lag)",
        })

        # UK HMRC Trade (not persisted)
        sources.append({
            "source": "UK HMRC Arms Trade",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (1hr TTL)",
            "update_frequency": "Monthly (~2 month lag)",
        })

        # NATO Defence Expenditure
        sources.append({
            "source": "NATO Defence Expenditure",
            "records": "live",
            "latest_data_year": 2025,
            "last_updated": "cached (24hr TTL)",
            "update_frequency": "Annual (includes estimates)",
        })

        # DSCA Arms Sales (not persisted)
        sources.append({
            "source": "DSCA Arms Sales",
            "records": "live",
            "latest_data_year": None,
            "last_updated": "cached (1hr TTL)",
            "update_frequency": "Days (Federal Register)",
        })

        return sources
    finally:
        session.close()


@router.get("/all")
async def get_all_insights():
    """Generate all insights in a single call for the dashboard."""
    session = SessionLocal()
    try:
        shifts = _supplier_shifts(session)
        return {
            "emerging_relationships": _emerging_relationships(session),
            "fading_relationships": _fading_relationships(session),
            "biggest_movers": _biggest_movers(session),
            "supplier_shifts": _add_shift_context(shifts),
            "weapon_trends": _weapon_trends(session),
            "regional_hotspots": _regional_hotspots(session),
            "canada_alerts": _canada_alerts(session),
            "situation_report": _compute_situation_report(session),
        }
    finally:
        session.close()


def _compute_situation_report(session) -> dict:
    """Compute 6 threat indicators for the situation report."""
    report = {}

    # 1. Arctic Threat — Russian exports to Arctic-adjacent countries
    arctic_countries = (
        "Norway", "Finland", "Sweden", "Denmark", "Iceland",
        "Greenland", "Canada", "United States",
    )
    placeholders = ", ".join(f":ac{i}" for i in range(len(arctic_countries)))
    params = {f"ac{i}": c for i, c in enumerate(arctic_countries)}
    rows = _query(session, f"""
        SELECT COUNT(*) as deals, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c1.name = 'Russia' AND c2.name IN ({placeholders})
          AND at.order_year >= 2018
    """, params)
    arctic_deals = rows[0][0] if rows else 0
    arctic_tiv = rows[0][1] if rows else 0
    if arctic_deals >= 5:
        level = "red"
    elif arctic_deals >= 1:
        level = "yellow"
    else:
        level = "green"
    report["arctic_threat"] = {
        "level": level,
        "deals": arctic_deals,
        "tiv": arctic_tiv,
        "summary": f"{arctic_deals} Russian arms deals to Arctic nations since 2018 (TIV {arctic_tiv:.0f}M)" if arctic_deals else "No Russian arms transfers to Arctic nations detected",
    }

    # 2. Supply Chain Risk — Canada's import concentration
    rows = _query(session, """
        SELECT c1.name, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c2.name = 'Canada' AND at.order_year >= 2015
        GROUP BY c1.name ORDER BY tiv DESC
    """)
    if rows:
        total = sum(r[1] for r in rows)
        top_supplier = rows[0][0]
        top_pct = (rows[0][1] / total * 100) if total > 0 else 0
    else:
        total = 0
        top_supplier = "N/A"
        top_pct = 0
    if top_pct > 60:
        level = "red"
    elif top_pct > 40:
        level = "yellow"
    else:
        level = "green"
    report["supply_chain_risk"] = {
        "level": level,
        "top_supplier": top_supplier,
        "top_pct": round(top_pct, 1),
        "summary": f"{top_pct:.0f}% of imports from {top_supplier}" if top_supplier != "N/A" else "No import data available",
    }

    # 3. Adversary Expansion — new seller-buyer pairs since 2020 where seller is Russia or China
    rows = _query(session, """
        SELECT c1.name as seller, c2.name as buyer,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c1.name IN ('Russia', 'China') AND at.order_year >= 2020
        GROUP BY c1.name, c2.name
        HAVING c1.name || '|' || c2.name NOT IN (
            SELECT c1b.name || '|' || c2b.name
            FROM arms_transfers at2
            JOIN countries c1b ON at2.seller_id = c1b.id
            JOIN countries c2b ON at2.buyer_id = c2b.id
            WHERE at2.order_year >= 2015 AND at2.order_year < 2020
              AND c1b.name IN ('Russia', 'China')
        )
        ORDER BY tiv DESC
    """)
    new_pairs_count = len(rows) if rows else 0
    if new_pairs_count >= 5:
        level = "red"
    elif new_pairs_count >= 1:
        level = "yellow"
    else:
        level = "green"
    report["adversary_expansion"] = {
        "level": level,
        "new_pairs": new_pairs_count,
        "pairs": [{"seller": r[0], "buyer": r[1], "tiv": r[2]} for r in (rows or [])],
        "summary": f"{new_pairs_count} new Russia/China arms relationships since 2020",
    }

    # 4. Allied Rearmament — placeholder for client-side computation from NATO data
    report["allied_rearmament"] = {
        "level": "yellow",
        "summary": "Computed client-side from NATO spending data",
    }

    # 5. Canada NATO Rank — placeholder for client-side computation from NATO data
    report["canada_nato_rank"] = {
        "level": "yellow",
        "summary": "Computed client-side from NATO spending data",
    }

    # 6. Sanctions Compliance — cross-reference Canada's trade partners against embargo list
    try:
        from src.ingestion.sanctions import SanctionsClient
        client = SanctionsClient()
        embargoes = client.get_embargoed_countries()
        embargoed_names = {e.country.lower() for e in embargoes}
        embargoed_iso3 = {e.iso3.lower() for e in embargoes}
    except Exception:
        embargoed_names = set()
        embargoed_iso3 = set()

    # Canada's trade partners from arms_transfers
    partner_rows = _query(session, """
        SELECT DISTINCT c.name
        FROM (
            SELECT buyer_id as cid FROM arms_transfers at
            JOIN countries cs ON at.seller_id = cs.id WHERE cs.name = 'Canada'
            UNION
            SELECT seller_id as cid FROM arms_transfers at
            JOIN countries cb ON at.buyer_id = cb.id WHERE cb.name = 'Canada'
        ) sub
        JOIN countries c ON sub.cid = c.id
    """)
    flagged = []
    for r in (partner_rows or []):
        if r[0].lower() in embargoed_names:
            flagged.append(r[0])
    report["sanctions_compliance"] = {
        "level": "red" if flagged else "green",
        "flagged_partners": flagged,
        "summary": f"{len(flagged)} trade partner(s) under embargo: {', '.join(flagged)}" if flagged else "No trade partners under active embargoes",
    }

    # --- PSI indicators (7-9) — each wrapped individually for resilience ---
    _psi_gray = "PSI data not yet seeded"
    try:
        from src.analysis.supply_chain import SupplyChainAnalyzer
        psi = SupplyChainAnalyzer(session)
    except Exception:
        psi = None

    # 7. Supply chain concentration (HHI)
    try:
        if psi is None:
            raise RuntimeError("PSI not available")
        conc_score = psi.score_supplier_concentration("Canada")
        report["supply_chain_concentration"] = {
            "level": "red" if conc_score > 70 else ("yellow" if conc_score > 40 else "green"),
            "score": round(conc_score, 1),
            "summary": f"Supplier concentration score: {conc_score:.0f}/100"
                       f" — {'high single-source dependency' if conc_score > 70 else 'moderate diversity' if conc_score > 40 else 'well diversified'}",
        }
    except Exception:
        report["supply_chain_concentration"] = {"level": "gray", "score": 0, "summary": _psi_gray}

    # 8. Material dependency on adversaries
    try:
        import json as _json
        from sqlalchemy import select as _sel
        from src.storage.models import SupplyChainMaterial
        materials = session.execute(_sel(SupplyChainMaterial)).scalars().all()
        adversary_materials = []
        for m in materials:
            if not m.top_producers:
                continue
            try:
                producers = _json.loads(m.top_producers)
            except Exception:
                continue
            for p in producers:
                if p.get("country") in ("China", "Russia") and p.get("pct", 0) > 60:
                    adversary_materials.append(f"{m.name} ({p['country']} {p['pct']}%)")
                    break

        report["material_dependency"] = {
            "level": "red" if len(adversary_materials) >= 3 else ("yellow" if adversary_materials else "green"),
            "count": len(adversary_materials),
            "flagged": adversary_materials[:5],
            "summary": f"{len(adversary_materials)} critical material(s) >60% from adversaries"
                       if adversary_materials else "No critical material dependency on adversaries",
        }
    except Exception:
        report["material_dependency"] = {"level": "gray", "count": 0, "flagged": [], "summary": _psi_gray}

    # 9. Chokepoint exposure
    try:
        if psi is None:
            raise RuntimeError("PSI not available")
        choke_score = psi.score_chokepoint_exposure("Canada")
        report["chokepoint_exposure"] = {
            "level": "red" if choke_score > 60 else ("yellow" if choke_score > 30 else "green"),
            "score": round(choke_score, 1),
            "summary": f"Chokepoint exposure score: {choke_score:.0f}/100"
                       f" — {'high route vulnerability' if choke_score > 60 else 'moderate exposure' if choke_score > 30 else 'low exposure'}",
        }
    except Exception:
        report["chokepoint_exposure"] = {"level": "gray", "score": 0, "summary": _psi_gray}

    return report


def _add_shift_context(shifts: list[dict]) -> list[dict]:
    """Add context and context_type fields to supplier shift entries."""
    adversaries = {"Russia", "China", "Iran"}
    for s in shifts:
        old = s.get("old_supplier", "")
        new = s.get("new_supplier", "")
        if old in adversaries and new not in adversaries:
            s["context_type"] = "opportunity"
            s["context"] = "Moving away from adversary — potential opportunity for Canada"
        elif new in adversaries and old not in adversaries:
            s["context_type"] = "threat"
            s["context"] = "Shifting to adversary supplier — growing adversary influence"
        elif new == "South Korea":
            s["context_type"] = "competition"
            s["context"] = "South Korea gaining market share — competitive pressure"
        else:
            s["context_type"] = "neutral"
            s["context"] = ""
    return shifts


def _emerging_relationships(session) -> list[dict]:
    """Find seller-buyer pairs that are new since 2020 (didn't exist 2015-2019)."""
    rows = _query(session, """
        SELECT c1.name as seller, c2.name as buyer,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv, COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE at.order_year >= 2020 AND at.order_year <= 2025
        GROUP BY c1.name, c2.name
        HAVING SUM(COALESCE(at.tiv_delivered, 0)) > 50
        AND c1.name || '|' || c2.name NOT IN (
            SELECT c1b.name || '|' || c2b.name
            FROM arms_transfers at2
            JOIN countries c1b ON at2.seller_id = c1b.id
            JOIN countries c2b ON at2.buyer_id = c2b.id
            WHERE at2.order_year >= 2015 AND at2.order_year < 2020
        )
        ORDER BY tiv DESC
        LIMIT 15
    """)
    return [{"seller": r[0], "buyer": r[1], "tiv": r[2], "deals": r[3]} for r in rows]


def _fading_relationships(session) -> list[dict]:
    """Find seller-buyer pairs active 2015-2019 that stopped or dropped sharply by 2020-2023."""
    rows = _query(session, """
        WITH old_pairs AS (
            SELECT c1.name as seller, c2.name as buyer,
                   SUM(COALESCE(at.tiv_delivered, 0)) as old_tiv
            FROM arms_transfers at
            JOIN countries c1 ON at.seller_id = c1.id
            JOIN countries c2 ON at.buyer_id = c2.id
            WHERE at.order_year >= 2015 AND at.order_year < 2020
            GROUP BY c1.name, c2.name
            HAVING old_tiv > 100
        ),
        new_pairs AS (
            SELECT c1.name as seller, c2.name as buyer,
                   SUM(COALESCE(at.tiv_delivered, 0)) as new_tiv
            FROM arms_transfers at
            JOIN countries c1 ON at.seller_id = c1.id
            JOIN countries c2 ON at.buyer_id = c2.id
            WHERE at.order_year >= 2020 AND at.order_year <= 2025
            GROUP BY c1.name, c2.name
        )
        SELECT old_pairs.seller, old_pairs.buyer, old_pairs.old_tiv,
               COALESCE(new_pairs.new_tiv, 0) as new_tiv,
               ROUND((COALESCE(new_pairs.new_tiv, 0) - old_pairs.old_tiv) / old_pairs.old_tiv * 100) as change_pct
        FROM old_pairs
        LEFT JOIN new_pairs ON old_pairs.seller = new_pairs.seller AND old_pairs.buyer = new_pairs.buyer
        WHERE COALESCE(new_pairs.new_tiv, 0) < old_pairs.old_tiv * 0.3
        ORDER BY old_pairs.old_tiv DESC
        LIMIT 15
    """)
    return [{"seller": r[0], "buyer": r[1], "old_tiv": r[2], "new_tiv": r[3], "change_pct": r[4]} for r in rows]


def _biggest_movers(session) -> list[dict]:
    """Countries with the largest change in total arms imports between periods."""
    rows = _query(session, """
        WITH old_imports AS (
            SELECT c.name as country, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
            FROM arms_transfers at
            JOIN countries c ON at.buyer_id = c.id
            WHERE at.order_year >= 2015 AND at.order_year < 2020
            GROUP BY c.name
            HAVING tiv > 50
        ),
        new_imports AS (
            SELECT c.name as country, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
            FROM arms_transfers at
            JOIN countries c ON at.buyer_id = c.id
            WHERE at.order_year >= 2020 AND at.order_year <= 2025
            GROUP BY c.name
            HAVING tiv > 50
        )
        SELECT
            COALESCE(n.country, o.country) as country,
            COALESCE(o.tiv, 0) as old_tiv,
            COALESCE(n.tiv, 0) as new_tiv,
            COALESCE(n.tiv, 0) - COALESCE(o.tiv, 0) as abs_change,
            CASE WHEN COALESCE(o.tiv, 0) > 0
                 THEN ROUND((COALESCE(n.tiv, 0) - o.tiv) / o.tiv * 100)
                 ELSE 999 END as change_pct
        FROM old_imports o
        FULL OUTER JOIN new_imports n ON o.country = n.country
        WHERE COALESCE(n.country, o.country) IS NOT NULL
        ORDER BY ABS(COALESCE(n.tiv, 0) - COALESCE(o.tiv, 0)) DESC
        LIMIT 20
    """)
    # SQLite doesn't support FULL OUTER JOIN, use UNION approach
    if not rows:
        rows = _query(session, """
            WITH old_imports AS (
                SELECT c.name as country, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                JOIN countries c ON at.buyer_id = c.id
                WHERE at.order_year >= 2015 AND at.order_year < 2020
                GROUP BY c.name HAVING tiv > 50
            ),
            new_imports AS (
                SELECT c.name as country, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                JOIN countries c ON at.buyer_id = c.id
                WHERE at.order_year >= 2020 AND at.order_year <= 2025
                GROUP BY c.name HAVING tiv > 50
            ),
            combined AS (
                SELECT o.country, o.tiv as old_tiv, COALESCE(n.tiv, 0) as new_tiv
                FROM old_imports o LEFT JOIN new_imports n ON o.country = n.country
                UNION
                SELECT n.country, COALESCE(o.tiv, 0), n.tiv
                FROM new_imports n LEFT JOIN old_imports o ON n.country = o.country
                WHERE o.country IS NULL
            )
            SELECT country, old_tiv, new_tiv,
                   new_tiv - old_tiv as abs_change,
                   CASE WHEN old_tiv > 0 THEN ROUND((new_tiv - old_tiv) * 100.0 / old_tiv) ELSE 999 END as change_pct
            FROM combined
            ORDER BY ABS(new_tiv - old_tiv) DESC
            LIMIT 20
        """)
    return [
        {"country": r[0], "old_tiv": r[1], "new_tiv": r[2], "abs_change": r[3],
         "change_pct": r[4], "direction": "up" if r[3] > 0 else "down"}
        for r in rows
    ]


def _supplier_shifts(session) -> list[dict]:
    """Countries that changed their primary arms supplier between periods."""
    rows = _query(session, """
        WITH old_top AS (
            SELECT buyer, seller, tiv, ROW_NUMBER() OVER (PARTITION BY buyer ORDER BY tiv DESC) as rn
            FROM (
                SELECT c2.name as buyer, c1.name as seller, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                JOIN countries c1 ON at.seller_id = c1.id
                JOIN countries c2 ON at.buyer_id = c2.id
                WHERE at.order_year >= 2015 AND at.order_year < 2020
                GROUP BY c2.name, c1.name
                HAVING tiv > 20
            )
        ),
        new_top AS (
            SELECT buyer, seller, tiv, ROW_NUMBER() OVER (PARTITION BY buyer ORDER BY tiv DESC) as rn
            FROM (
                SELECT c2.name as buyer, c1.name as seller, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                JOIN countries c1 ON at.seller_id = c1.id
                JOIN countries c2 ON at.buyer_id = c2.id
                WHERE at.order_year >= 2020 AND at.order_year <= 2025
                GROUP BY c2.name, c1.name
                HAVING tiv > 20
            )
        )
        SELECT old_top.buyer, old_top.seller as old_supplier, new_top.seller as new_supplier,
               old_top.tiv as old_tiv, new_top.tiv as new_tiv
        FROM old_top
        JOIN new_top ON old_top.buyer = new_top.buyer
        WHERE old_top.rn = 1 AND new_top.rn = 1
          AND old_top.seller != new_top.seller
        ORDER BY new_top.tiv DESC
        LIMIT 15
    """)
    return [
        {"buyer": r[0], "old_supplier": r[1], "new_supplier": r[2],
         "old_tiv": r[3], "new_tiv": r[4]}
        for r in rows
    ]


def _weapon_trends(session) -> list[dict]:
    """Weapon categories with significant volume changes between periods."""
    rows = _query(session, """
        SELECT weapon, old_tiv, new_tiv, new_tiv - old_tiv as abs_change
        FROM (
            SELECT COALESCE(n.weapon, o.weapon) as weapon,
                   COALESCE(o.tiv, 0) as old_tiv, COALESCE(n.tiv, 0) as new_tiv
            FROM (
                SELECT at.weapon_description as weapon, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                WHERE at.order_year >= 2015 AND at.order_year < 2020
                GROUP BY at.weapon_description HAVING tiv > 100
            ) o
            LEFT JOIN (
                SELECT at.weapon_description as weapon, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                WHERE at.order_year >= 2020 AND at.order_year <= 2025
                GROUP BY at.weapon_description HAVING tiv > 100
            ) n ON o.weapon = n.weapon
            UNION ALL
            SELECT n.weapon, 0 as old_tiv, n.tiv as new_tiv
            FROM (
                SELECT at.weapon_description as weapon, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                WHERE at.order_year >= 2020 AND at.order_year <= 2025
                GROUP BY at.weapon_description HAVING tiv > 100
            ) n
            LEFT JOIN (
                SELECT at.weapon_description as weapon
                FROM arms_transfers at
                WHERE at.order_year >= 2015 AND at.order_year < 2020
                GROUP BY at.weapon_description HAVING SUM(COALESCE(at.tiv_delivered, 0)) > 100
            ) o ON n.weapon = o.weapon
            WHERE o.weapon IS NULL
        )
        ORDER BY ABS(new_tiv - old_tiv) DESC
        LIMIT 12
    """)
    return [
        {"weapon": r[0], "old_tiv": r[1], "new_tiv": r[2], "abs_change": r[3],
         "direction": "up" if r[3] > 0 else "down"}
        for r in rows
    ]


def _regional_hotspots(session) -> list[dict]:
    """Regions with the highest import growth (potential conflict signals)."""
    rows = _query(session, """
        WITH buyer_data AS (
            SELECT c.name as country,
                   SUM(CASE WHEN at.order_year >= 2015 AND at.order_year < 2020
                       THEN COALESCE(at.tiv_delivered, 0) ELSE 0 END) as old_tiv,
                   SUM(CASE WHEN at.order_year >= 2020 AND at.order_year <= 2025
                       THEN COALESCE(at.tiv_delivered, 0) ELSE 0 END) as new_tiv
            FROM arms_transfers at
            JOIN countries c ON at.buyer_id = c.id
            GROUP BY c.name
        )
        SELECT country, old_tiv, new_tiv,
               new_tiv - old_tiv as growth,
               CASE WHEN old_tiv > 0 THEN ROUND((new_tiv - old_tiv) * 100.0 / old_tiv) ELSE 999 END as growth_pct
        FROM buyer_data
        WHERE new_tiv > 200 AND new_tiv > old_tiv * 1.5
        ORDER BY new_tiv - old_tiv DESC
        LIMIT 10
    """)
    return [
        {"country": r[0], "old_tiv": r[1], "new_tiv": r[2],
         "growth": r[3], "growth_pct": r[4]}
        for r in rows
    ]


def _canada_alerts(session) -> list[dict]:
    """Canada-specific intelligence alerts."""
    alerts = []

    # Canada's top supplier concentration
    rows = _query(session, """
        SELECT c1.name, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c2.name = 'Canada' AND at.order_year >= 2015
        GROUP BY c1.name ORDER BY tiv DESC
    """)
    if rows:
        total = sum(r[1] for r in rows)
        top_pct = (rows[0][1] / total * 100) if total > 0 else 0
        if top_pct > 50:
            alerts.append({
                "level": "warning",
                "title": f"Supply chain concentration: {top_pct:.0f}% from {rows[0][0]}",
                "detail": f"Canada imports {top_pct:.0f}% of arms from {rows[0][0]} (TIV {rows[0][1]:.0f}M of {total:.0f}M total). Consider diversification risk.",
            })

    # Russia arming Arctic neighbors or adversaries
    rows = _query(session, """
        SELECT c2.name, SUM(COALESCE(at.tiv_delivered, 0)) as tiv, COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c1.name = 'Russia' AND at.order_year >= 2020
        GROUP BY c2.name ORDER BY tiv DESC LIMIT 5
    """)
    if rows:
        buyers = ", ".join(f"{r[0]} ({r[1]:.0f}M)" for r in rows)
        alerts.append({
            "level": "threat",
            "title": "Russia's top arms customers (2020-2025)",
            "detail": f"Active supply relationships: {buyers}",
        })

    # China expanding into new markets
    rows = _query(session, """
        SELECT c2.name, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c1.name = 'China' AND at.order_year >= 2020
        GROUP BY c2.name ORDER BY tiv DESC LIMIT 5
    """)
    if rows:
        buyers = ", ".join(f"{r[0]} ({r[1]:.0f}M)" for r in rows)
        alerts.append({
            "level": "threat",
            "title": "China's top arms customers (2020-2025)",
            "detail": f"Active supply relationships: {buyers}",
        })

    # Canada's own export customers
    rows = _query(session, """
        SELECT c2.name, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE c1.name = 'Canada' AND at.order_year >= 2020
        GROUP BY c2.name ORDER BY tiv DESC LIMIT 3
    """)
    if rows:
        customers = ", ".join(f"{r[0]} (TIV {r[1]:.0f}M)" for r in rows)
        alerts.append({
            "level": "info",
            "title": "Canada's top export customers (2020-2025)",
            "detail": customers,
        })

    # Countries arming up fast near Canada's interests
    rows = _query(session, """
        SELECT c.name,
               SUM(CASE WHEN at.order_year < 2020 THEN COALESCE(at.tiv_delivered,0) ELSE 0 END) as old,
               SUM(CASE WHEN at.order_year >= 2020 THEN COALESCE(at.tiv_delivered,0) ELSE 0 END) as new
        FROM arms_transfers at
        JOIN countries c ON at.buyer_id = c.id
        WHERE c.name IN ('Ukraine', 'Poland', 'Finland', 'Norway', 'Japan', 'Taiwan', 'Philippines')
          AND at.order_year >= 2015
        GROUP BY c.name
        HAVING new > old * 1.3
        ORDER BY new - old DESC
    """)
    for r in rows:
        growth = ((r[2] - r[1]) / r[1] * 100) if r[1] > 0 else 999
        alerts.append({
            "level": "info",
            "title": f"{r[0]} arms imports up {growth:.0f}%",
            "detail": f"TIV {r[1]:.0f}M (2015-19) → {r[2]:.0f}M (2020-23). Ally rearmament signal.",
        })

    return alerts
