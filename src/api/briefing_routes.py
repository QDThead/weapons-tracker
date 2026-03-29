"""PDF Intelligence Briefing endpoint.

Generates a multi-page PDF briefing for DND leadership.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from src.storage.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/briefing", tags=["Briefing"])


@router.get("/pdf")
async def generate_briefing_pdf():
    """Generate and download a PDF intelligence briefing."""
    from src.analysis.briefing_generator import BriefingGenerator

    session = SessionLocal()
    try:
        generator = BriefingGenerator(session)
        pdf_bytes = bytes(generator.generate_pdf())
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=PSI-Intelligence-Briefing.pdf",
            },
        )
    except Exception as e:
        logger.error("Briefing generation failed: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        session.close()
