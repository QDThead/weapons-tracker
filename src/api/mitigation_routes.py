"""Mitigation Action Centre API endpoints.

Serves COA recommendations, tracks action status,
and triggers on-demand COA generation.
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Query
from pydantic import BaseModel

from src.storage.database import SessionLocal
from src.storage.models import MitigationAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mitigation", tags=["Mitigation"])

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 300  # 5 minutes

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _check_cache(key: str) -> dict | None:
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < _TTL:
        return cached[1]
    return None


def _set_cache(key: str, data: dict) -> None:
    _cache[key] = (time.time(), data)


def _clear_cache():
    _cache.clear()


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
    cached = _check_cache(cache_key)
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
                }
                for a in actions
            ],
            "total": len(actions),
            "by_priority": by_priority,
            "by_status": by_status,
        }
        _set_cache(cache_key, result)
        return result
    except Exception as e:
        logger.error("get_actions failed: %s", e)
        return {"actions": [], "total": 0, "by_priority": {}, "by_status": {}, "error": str(e)}
    finally:
        session.close()


@router.patch("/actions/{action_id}")
async def update_action(action_id: int, update: StatusUpdate):
    """Update action status and/or notes."""
    session = SessionLocal()
    try:
        action = session.get(MitigationAction, action_id)
        if not action:
            return {"error": f"Action {action_id} not found"}
        if update.status:
            action.status = update.status
        if update.notes is not None:
            action.notes = update.notes
        action.updated_at = __import__("datetime").datetime.utcnow()
        session.commit()
        _clear_cache()
        return {
            "id": action.id,
            "status": action.status,
            "notes": action.notes,
            "updated_at": action.updated_at.isoformat(),
        }
    except Exception as e:
        logger.error("update_action failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()


@router.post("/generate")
async def generate_coas():
    """Trigger on-demand COA generation from current risk scores."""
    from src.analysis.mitigation_playbook import MitigationPlaybook
    session = SessionLocal()
    try:
        playbook = MitigationPlaybook(session)
        result = playbook.generate_all_coas()
        _clear_cache()
        return result
    except Exception as e:
        logger.error("generate_coas failed: %s", e)
        return {"error": str(e)}
    finally:
        session.close()
