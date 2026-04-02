"""Mitigation Action Centre API endpoints.

Serves COA recommendations, tracks action status,
and triggers on-demand COA generation.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from src.storage.database import SessionLocal
from src.storage.models import MitigationAction
from src.utils.cache import TTLCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mitigation", tags=["Mitigation"])

_cache = TTLCache(ttl_seconds=300, max_size=100)

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


class StatusUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("/actions")
async def get_actions(
    status: str = Query(None, description="Filter: open, in_progress, resolved, or all"),
    priority: str = Query(None, description="Filter: critical, high, medium, low"),
    source: str = Query(None, description="Filter: supplier, taxonomy, psi"),
):
    """All mitigation actions with summary stats."""
    cache_key = f"actions:{status}:{priority}:{source}"
    cached = _cache.get(cache_key)
    if cached:
        return cached

    session = SessionLocal()
    try:
        # Always count ALL statuses for badges
        all_actions = session.query(MitigationAction).all()
        by_status = {"open": 0, "in_progress": 0, "resolved": 0}
        by_priority = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in all_actions:
            by_status[a.status] = by_status.get(a.status, 0) + 1
            if a.status != "resolved":
                by_priority[a.coa_priority] = by_priority.get(a.coa_priority, 0) + 1

        # Filter for the action list
        query = session.query(MitigationAction)
        if status and status != "all":
            query = query.filter(MitigationAction.status == status)
        elif not status:
            query = query.filter(MitigationAction.status.in_(["open", "in_progress"]))
        if priority:
            query = query.filter(MitigationAction.coa_priority == priority)
        if source:
            query = query.filter(MitigationAction.risk_source == source)

        actions = query.all()
        # Sort by priority in Python
        actions.sort(key=lambda a: PRIORITY_ORDER.get(a.coa_priority, 9))

        from src.analysis.confidence import compute_confidence
        result = {
            "actions": [
                {
                    "id": a.id,
                    "risk_source": a.risk_source,
                    "risk_entity": a.risk_entity,
                    "risk_dimension": a.risk_dimension,
                    "risk_score": a.risk_score,
                    "coa_action": a.coa_action,
                    "coa_priority": a.coa_priority,
                    "coa_timeline": a.coa_timeline,
                    "coa_responsible": a.coa_responsible,
                    "status": a.status,
                    "notes": a.notes,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                    "updated_at": a.updated_at.isoformat() if a.updated_at else None,
                    "confidence": compute_confidence(
                        data_source=None,
                        risk_source=a.risk_source,
                        dimension=a.risk_dimension,
                        session=session,
                    ),
                }
                for a in actions
            ],
            "total": len(actions),
            "by_priority": by_priority,
            "by_status": by_status,
        }
        _cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_actions failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.patch("/actions/{action_id}")
async def update_action(action_id: int, update: StatusUpdate):
    """Update action status and/or notes."""
    session = SessionLocal()
    try:
        action = session.get(MitigationAction, action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Resource not found")
        if update.status:
            action.status = update.status
        if update.notes is not None:
            action.notes = update.notes
        action.updated_at = __import__("datetime").datetime.utcnow()
        session.commit()
        _cache.clear()
        return {
            "id": action.id,
            "status": action.status,
            "notes": action.notes,
            "updated_at": action.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_action failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()


@router.get("/playbook")
async def get_playbook():
    """Return the full COA playbook reference (41 entries)."""
    from src.analysis.mitigation_playbook import PLAYBOOK

    entries = []
    category_counts: dict[str, int] = {}
    for (risk_category, risk_dimension), entry in PLAYBOOK.items():
        entries.append({
            "risk_category": risk_category,
            "risk_dimension": risk_dimension,
            "coa_action": entry.get("action", ""),
            "coa_timeline": entry.get("timeline", ""),
            "coa_responsible": entry.get("responsible", ""),
        })
        category_counts[risk_category] = category_counts.get(risk_category, 0) + 1

    return {
        "total_entries": len(entries),
        "categories": category_counts,
        "playbook": entries,
    }


@router.post("/generate")
async def generate_coas():
    """Trigger on-demand COA generation from current risk scores."""
    from src.analysis.mitigation_playbook import MitigationPlaybook
    session = SessionLocal()
    try:
        playbook = MitigationPlaybook(session)
        result = playbook.generate_all_coas()
        _cache.clear()
        return result
    except Exception as e:
        logger.error("generate_coas failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()
