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
from app.db.session import Base, engine


def main() -> None:
    setup_logging(debug=True)
    logger.info("Target database: %s", settings.database_url)
    logger.info("Creating tables...")
    Base.metadata.create_all(bind=engine)
    table_names = list(Base.metadata.tables.keys())
    logger.info("Done. Tables: %s", table_names)


if __name__ == "__main__":
    main()
