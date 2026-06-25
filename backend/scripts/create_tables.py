#!/usr/bin/env python3
"""Bootstrap the database schema by running Alembic migrations to head.

歷史上此腳本以 Base.metadata.create_all 建表；現已改為執行 Alembic versioned
migrations（單一真實的 schema 演進來源），不再用 create_all。保留檔名與進入點是為了
相容既有的 compose command 與文件。

Usage:
    cd backend
    PYTHONPATH=. python scripts/create_tables.py
等同於：
    cd backend
    alembic upgrade head
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alembic import command
from alembic.config import Config

from app.core.config import settings
from app.core.logging import logger, setup_logging

_BACKEND_ROOT = Path(__file__).parent.parent


def main() -> None:
    setup_logging(debug=True)
    logger.info("Target database: %s", settings.database_url)
    logger.info("Running Alembic migrations to head...")
    alembic_cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    logger.info("Done. Schema is at head revision.")


if __name__ == "__main__":
    main()
