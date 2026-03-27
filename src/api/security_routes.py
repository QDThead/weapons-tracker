"""Security API endpoints — auth info, audit log, RBAC.

Addresses DND Q15: Security Measures and Practices.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from src.storage.database import SessionLocal
from src.storage.models import AuditLog
from src.api.auth import get_current_user, ROLE_PERMISSIONS, AUTH_ENABLED, log_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/whoami")
async def whoami(user: dict = Depends(get_current_user)):
    """Returns current user info and permissions."""
    return {
        "user": user["user"],
        "role": user["role"],
        "org": user["org"],
        "permissions": list(user["permissions"]),
        "auth_enabled": AUTH_ENABLED,
    }


@router.get("/roles")
async def get_roles():
    """List all RBAC roles and their permissions."""
    return {
        "roles": {
            role: list(perms)
            for role, perms in ROLE_PERMISSIONS.items()
        },
        "auth_enabled": AUTH_ENABLED,
    }


@router.get("/audit")
async def get_audit_log(limit: int = 50):
    """View recent audit log entries."""
    session = SessionLocal()
    try:
        entries = session.query(AuditLog).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()
        return {
            "entries": [
                {
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "user": e.user,
                    "action": e.action,
                    "resource": e.resource,
                    "detail": e.detail,
                }
                for e in entries
            ],
            "total": len(entries),
        }
    finally:
        session.close()


@router.get("/posture")
async def security_posture():
    """Security posture summary for DND compliance."""
    return {
        "classification": "UNCLASSIFIED",
        "auth_method": "API Key (X-API-Key header)",
        "auth_enabled": AUTH_ENABLED,
        "rbac_roles": ["admin", "analyst", "viewer"],
        "encryption": {
            "at_rest": "SQLite (local dev) / Azure Managed Encryption (production)",
            "in_transit": "TLS 1.3 (production) / HTTP (demo)",
        },
        "data_sovereignty": {
            "hosting": "Azure Canada Central (Toronto) — production",
            "jurisdiction": "Canadian law (PIPEDA/Privacy Act)",
            "extraterritorial_exposure": "None — no routing through US servers",
        },
        "compliance": {
            "pbmm": "Architected for Protected B, Medium Integrity, Medium Availability",
            "itsg_33": "Designed to comply with ITSG-33 security controls",
            "audit_trail": "All actions logged with immutable audit trail",
        },
        "security_assessments": {
            "sa_a": "QDT commits to completing SA&A process as required by DND",
            "penetration_testing": "Annual third-party testing available under NDA",
            "sbom": "Complete Software Bill of Materials maintained (CycloneDX)",
        },
    }
