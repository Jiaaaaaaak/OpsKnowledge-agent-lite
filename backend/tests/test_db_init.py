from sqlalchemy import create_mock_engine

import app.models  # noqa: F401 - registers all ORM models with Base.metadata
from app.db.session import Base


def test_all_expected_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == {
        "projects",
        "documents",
        "document_chunks",
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
    assert "embedding vector(1024)" in ddl


def test_initial_alembic_migration_repairs_existing_document_chunks_schema(monkeypatch) -> None:
    """既有 volume 可能已存在 document_chunks，但缺 pgvector/FTS 欄位或索引。

    0001 migration 不能只靠 CREATE TABLE IF NOT EXISTS；表已存在時仍需補 schema，
    否則從 create_all 時代升級到 Alembic 會被標記成功但檢索壞掉。
    """
    import importlib

    migration = importlib.import_module("migrations.versions.0001_initial_schema")
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda sql: statements.append(str(sql)))

    migration.upgrade()

    ddl = "\n".join(statements)
    assert "ALTER TABLE document_chunks" in ddl
    assert "ADD COLUMN IF NOT EXISTS embedding vector(" in ddl
    assert "ADD COLUMN IF NOT EXISTS search_vector tsvector" in ddl
    assert "idx_document_chunks_embedding_hnsw" in ddl
    assert "idx_document_chunks_search_vector_gin" in ddl
