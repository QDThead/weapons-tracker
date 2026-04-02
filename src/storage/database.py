"""Database connection and session management."""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///weapons_tracker.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, echo=False)
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=5,
        pool_recycle=3600,
        pool_pre_ping=True,
    )
SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Get a database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
