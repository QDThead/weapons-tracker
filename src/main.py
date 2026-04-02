"""Weapons Tracker — entry point.

Starts the FastAPI server with scheduled data ingestion
for the global weapons trade tracking platform.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / "config" / ".env")

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from src.storage.database import init_db
from src.api.routes import router as core_router
from src.api.trend_routes import router as trend_router
from src.api.dashboard_routes import router as dashboard_router
from src.api.insights_routes import router as insights_router
from src.api.arctic_routes import router as arctic_router
from src.api.psi_routes import router as psi_router
from src.api.supplier_routes import router as supplier_router
from src.api.mitigation_routes import router as mitigation_router
from src.api.briefing_routes import router as briefing_router
from src.api.security_routes import router as security_router
from src.api.ml_routes import router as ml_router
from src.api.enrichment_routes import router as enrichment_router
from src.api.cyber_routes import router as cyber_router
from src.api.export_routes import router as export_router
from src.api.globe_routes import router as globe_router
from src.api.validation_routes import router as validation_router
from src.ingestion.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

_environment = os.getenv("ENVIRONMENT", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting ingestion scheduler...")
    scheduler = create_scheduler()
    scheduler.start()
    logger.info(
        "Scheduler running — %d jobs configured",
        len(scheduler.get_jobs()),
    )
    for job in scheduler.get_jobs():
        logger.info("  [%s] %s — next run: %s", job.id, job.name, job.next_run_time)

    logger.info("Weapons Tracker API is ready")
    yield
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Weapons Tracker API",
    description="Global weapons sales and trade tracking across countries using OSINT data sources.",
    version="0.1.0",
    lifespan=lifespan,
)

# Security middleware (skipped in development so localhost:8000 works)
_allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").split(",")

if _environment != "development":
    app.add_middleware(HTTPSRedirectMiddleware)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)

# CORS middleware
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
_cors_allow_credentials = "*" not in _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=_cors_allow_credentials,
)

# Register routes
app.include_router(core_router)
app.include_router(trend_router)
app.include_router(dashboard_router)
app.include_router(insights_router)
app.include_router(arctic_router)
app.include_router(psi_router)
app.include_router(supplier_router)
app.include_router(mitigation_router)
app.include_router(briefing_router)
app.include_router(security_router)
app.include_router(ml_router)
app.include_router(enrichment_router)
app.include_router(cyber_router)
app.include_router(export_router)
app.include_router(globe_router)
app.include_router(validation_router)

# Serve dashboard UI
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(str(_static_dir / "index.html"))


def main():
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=(_environment == "development"),
    )


if __name__ == "__main__":
    main()
