"""Weapons Tracker — entry point.

Starts the FastAPI server with scheduled data ingestion
for the global weapons trade tracking platform.
"""

import logging
from pathlib import Path

import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.storage.database import init_db
from src.api.routes import app
from src.api.trend_routes import router as trend_router
from src.api.dashboard_routes import router as dashboard_router
from src.api.insights_routes import router as insights_router
from src.api.arctic_routes import router as arctic_router
from src.ingestion.scheduler import create_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

# Register routes
app.include_router(trend_router)
app.include_router(dashboard_router)
app.include_router(insights_router)
app.include_router(arctic_router)

# Serve dashboard UI
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    return FileResponse(str(_static_dir / "index.html"))

scheduler = create_scheduler()


@app.on_event("startup")
async def startup():
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting ingestion scheduler...")
    scheduler.start()
    logger.info(
        "Scheduler running — %d jobs configured",
        len(scheduler.get_jobs()),
    )
    for job in scheduler.get_jobs():
        logger.info("  [%s] %s — next run: %s", job.id, job.name, job.next_run_time)

    logger.info("Weapons Tracker API is ready")


@app.on_event("shutdown")
async def shutdown():
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)


def main():
    uvicorn.run(
        "src.api.routes:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
