from sqlalchemy import create_mock_engine

import app.models  # noqa: F401 - registers all ORM models with Base.metadata
from app.db.session import Base


def test_all_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "projects",
        "documents",
        "document_chunks",
        "raw_records",
        "cleaned_records",
        "incident_analysis",
        "insights",
        "action_items",
        "agent_runs",
        "tool_calls",
    }


def test_metadata_create_all_emits_postgresql_ddl() -> None:
    statements: list[str] = []

    engine = create_mock_engine(
        "postgresql://",
        lambda sql, *multiparams, **params: statements.append(
            str(sql.compile(dialect=engine.dialect))
        ),
    )

    Base.metadata.create_all(bind=engine)

    ddl = "\n".join(statements)
    assert "CREATE TABLE projects" in ddl
    assert "CREATE TABLE agent_runs" in ddl
    assert "CREATE TABLE tool_calls" in ddl
    assert "FOREIGN KEY(project_id) REFERENCES projects (id)" in ddl
