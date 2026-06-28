import re
from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _offline_sql(revision_range: str, *, downgrade: bool = False) -> str:
    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "migrations"))
    output = StringIO()
    config.output_buffer = output
    operation = command.downgrade if downgrade else command.upgrade
    operation(config, revision_range, sql=True)
    return output.getvalue()


def _table_definition(sql: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE {table_name} \((.*?)\n\);",
        sql,
        flags=re.DOTALL,
    )
    assert match is not None, f"missing generated DDL for {table_name}"
    return " ".join(match.group(1).split())


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _offline_sql("0002:0003")


def test_0003_upgrade_generates_identity_tables_and_constraints(
    upgrade_sql: str,
) -> None:
    administrators = _table_definition(upgrade_sql, "administrators")
    sessions = _table_definition(upgrade_sql, "admin_sessions")

    assert "username VARCHAR(100) NOT NULL" in administrators
    assert "UNIQUE (username)" in administrators
    assert "is_active BOOLEAN DEFAULT true NOT NULL" in administrators
    assert "token_hash VARCHAR(64) NOT NULL" in sessions
    assert "UNIQUE (token_hash)" in sessions
    assert (
        "FOREIGN KEY(administrator_id) REFERENCES administrators (id) "
        "ON DELETE CASCADE"
    ) in sessions


def test_0003_upgrade_generates_timezone_columns_and_session_indexes(
    upgrade_sql: str,
) -> None:
    sessions = _table_definition(upgrade_sql, "admin_sessions")

    assert "expires_at TIMESTAMP WITH TIME ZONE NOT NULL" in sessions
    assert "revoked_at TIMESTAMP WITH TIME ZONE" in sessions
    assert (
        "CREATE INDEX idx_admin_sessions_administrator_id "
        "ON admin_sessions (administrator_id);"
    ) in upgrade_sql
    assert (
        "CREATE INDEX idx_admin_sessions_expires_at "
        "ON admin_sessions (expires_at);"
    ) in upgrade_sql


def test_0003_downgrade_drops_sessions_before_administrators() -> None:
    downgrade_sql = _offline_sql("0003:0002", downgrade=True)

    sessions_position = downgrade_sql.index("DROP TABLE admin_sessions;")
    administrators_position = downgrade_sql.index("DROP TABLE administrators;")
    assert sessions_position < administrators_position
