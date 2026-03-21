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


@router.get("/all")
async def get_all_insights():
    """Generate all insights in a single call for the dashboard."""
    session = SessionLocal()
    try:
        return {
            "emerging_relationships": _emerging_relationships(session),
            "fading_relationships": _fading_relationships(session),
            "biggest_movers": _biggest_movers(session),
            "supplier_shifts": _supplier_shifts(session),
            "weapon_trends": _weapon_trends(session),
            "regional_hotspots": _regional_hotspots(session),
            "canada_alerts": _canada_alerts(session),
        }
    finally:
        session.close()


def _emerging_relationships(session) -> list[dict]:
    """Find seller-buyer pairs that are new since 2020 (didn't exist 2015-2019)."""
    rows = _query(session, """
        SELECT c1.name as seller, c2.name as buyer,
               SUM(COALESCE(at.tiv_delivered, 0)) as tiv, COUNT(*) as deals
        FROM arms_transfers at
        JOIN countries c1 ON at.seller_id = c1.id
        JOIN countries c2 ON at.buyer_id = c2.id
        WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
            WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
            WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
                WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
                WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
                WHERE at.order_year >= 2020 AND at.order_year <= 2023
                GROUP BY at.weapon_description HAVING tiv > 100
            ) n ON o.weapon = n.weapon
            UNION ALL
            SELECT n.weapon, 0 as old_tiv, n.tiv as new_tiv
            FROM (
                SELECT at.weapon_description as weapon, SUM(COALESCE(at.tiv_delivered, 0)) as tiv
                FROM arms_transfers at
                WHERE at.order_year >= 2020 AND at.order_year <= 2023
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
                   SUM(CASE WHEN at.order_year >= 2020 AND at.order_year <= 2023
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
            "title": "Russia's top arms customers (2020-2023)",
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
            "title": "China's top arms customers (2020-2023)",
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
            "title": "Canada's top export customers (2020-2023)",
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
