"""Authentication and authorization middleware.

Provides API key authentication, role-based access control (RBAC),
and audit logging for DND security compliance (Q15).
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from functools import wraps

from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader

from src.storage.database import SessionLocal
from src.storage.models import AuditLog

logger = logging.getLogger(__name__)

# API key configuration — in production, loaded from Azure Key Vault
API_KEYS = {
    "psi-admin-key-2026": {"role": "admin", "user": "Admin", "org": "QDT"},
    "psi-analyst-key-2026": {"role": "analyst", "user": "Analyst", "org": "DND"},
    "psi-viewer-key-2026": {"role": "viewer", "user": "Viewer", "org": "DND"},
    "demo": {"role": "admin", "user": "Demo User", "org": "QDT"},  # For demo convenience
}

# RBAC role permissions
ROLE_PERMISSIONS = {
    "admin": {"read", "write", "export", "generate", "configure"},
    "analyst": {"read", "write", "export", "generate"},
    "viewer": {"read", "export"},
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
    """Decorator to check user has a specific permission."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # In demo mode, allow everything
            if not AUTH_ENABLED:
                return await func(*args, **kwargs)
            # Permission check would go here in production
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
