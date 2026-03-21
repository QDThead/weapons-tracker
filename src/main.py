"""Weapons Tracker — entry point.

Starts the FastAPI server for the global weapons trade tracking platform.
"""

import logging
import uvicorn

from src.storage.database import init_db
from src.api.routes import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@app.on_event("startup")
async def startup():
    logger.info("Initializing database...")
    init_db()
    logger.info("Weapons Tracker API is ready")


def main():
    uvicorn.run(
        "src.api.routes:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
