"""Authentication and authorization middleware.

Provides API key authentication, role-based access control (RBAC),
and audit logging for DND security compliance (Q15).
"""
from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from functools import wraps

from fastapi import Depends, Request, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.storage.database import SessionLocal
from src.storage.models import AuditLog

logger = logging.getLogger(__name__)

# Default API keys for dev — no demo key.  In production, set API_KEYS_JSON.
_DEFAULT_API_KEYS: dict[str, dict[str, str]] = {
    "psi-admin-key-2026": {"role": "admin", "user": "Admin", "org": "QDT"},
    "psi-analyst-key-2026": {"role": "analyst", "user": "Analyst", "org": "DND"},
    "psi-viewer-key-2026": {"role": "viewer", "user": "Viewer", "org": "DND"},
}


def _load_api_keys() -> dict[str, dict[str, str]]:
    """Load API keys from API_KEYS_JSON env var, falling back to defaults."""
    raw = os.environ.get("API_KEYS_JSON")
    if raw:
        try:
            keys = json.loads(raw)
            if isinstance(keys, dict) and keys:
                logger.info("Loaded %d API key(s) from API_KEYS_JSON.", len(keys))
                return keys
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("Invalid API_KEYS_JSON, falling back to defaults: %s", exc)
    return dict(_DEFAULT_API_KEYS)


API_KEYS: dict[str, dict[str, str]] = _load_api_keys()

# RBAC role permissions
ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"read", "write", "export", "generate", "configure"},
    "analyst": {"read", "write", "export", "generate"},
    "viewer": {"read", "export"},
}

# Role hierarchy: higher value = more privilege.
# admin > analyst > viewer.
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 0,
    "analyst": 1,
    "admin": 2,
}

# Minimum role required for each permission.
_PERMISSION_MIN_ROLE: dict[str, str] = {
    "read": "viewer",
    "export": "viewer",
    "write": "analyst",
    "generate": "analyst",
    "configure": "admin",
}

# API key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# Auth can be disabled for demo mode
AUTH_ENABLED = os.environ.get("PSI_AUTH_ENABLED", "false").lower() == "true"


def get_current_user(api_key: str | None = Security(api_key_header), request: Request = None) -> dict:
    """Validate API key and return user info. Returns demo user if auth disabled."""
    if not AUTH_ENABLED:
        return {"user": "Demo User", "role": "admin", "org": "QDT", "permissions": ROLE_PERMISSIONS["admin"]}

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Include X-API-Key header.")

    key_info = API_KEYS.get(api_key)
    if not key_info:
        raise HTTPException(status_code=403, detail="Invalid API key.")

    role = key_info["role"]
    return {
        "user": key_info["user"],
        "role": role,
        "org": key_info["org"],
        "permissions": ROLE_PERMISSIONS.get(role, set()),
    }


def require_permission(permission: str):
    """Decorator to check that the current user has the required permission.

    Uses the role hierarchy (admin > analyst > viewer) together with the
    ROLE_PERMISSIONS table.  When AUTH_ENABLED is False the check is
    skipped entirely (demo mode).

    The decorated endpoint must receive its authenticated user dict via a
    FastAPI ``Depends(get_current_user)`` parameter named ``current_user``.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # In demo mode, allow everything
            if not AUTH_ENABLED:
                return await func(*args, **kwargs)

            # Resolve the current user from kwargs (injected by FastAPI Depends).
            current_user: dict | None = kwargs.get("current_user")
            if current_user is None:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required.",
                )

            user_role: str = current_user.get("role", "")
            user_permissions: set[str] = ROLE_PERMISSIONS.get(user_role, set())

            if permission not in user_permissions:
                logger.warning(
                    "Permission denied: user=%s role=%s needs=%s",
                    current_user.get("user", "unknown"),
                    user_role,
                    permission,
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. '{permission}' requires "
                           f"role '{_PERMISSION_MIN_ROLE.get(permission, 'unknown')}' or higher. "
                           f"Your role: '{user_role}'.",
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator


def log_audit(user: str, action: str, resource: str, detail: str = ""):
    """Log an action to the audit trail."""
    try:
        session = SessionLocal()
        try:
            entry = AuditLog(
                timestamp=datetime.utcnow(),
                user=user,
                action=action,
                resource=resource,
                detail=detail[:500],
                ip_address="",
            )
            session.add(entry)
            session.commit()
        finally:
            session.close()
    except Exception as e:
        logger.warning("Audit log failed: %s", e)
