#!/usr/bin/env python3
"""Create all SQLAlchemy ORM tables in the configured PostgreSQL database.

Usage:
    cd backend
    PYTHONPATH=. python scripts/create_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import app.models  # noqa: F401 — registers all models with Base.metadata
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.session import Base, engine, ensure_vector_extension, ensure_vector_schema


def main() -> None:
    setup_logging(debug=True)
    logger.info("Target database: %s", settings.database_url)
    logger.info("Ensuring pgvector extension...")
    ensure_vector_extension()
    logger.info("Creating tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Ensuring pgvector columns and indexes...")
    ensure_vector_schema()
    table_names = list(Base.metadata.tables.keys())
    logger.info("Done. Tables: %s", table_names)


if __name__ == "__main__":
    main()
