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
    assert "embedding vector(384)" in ddl
    # 事件分析輸出連結到 agent_runs（spec：run-level 關聯 + 索引）
    assert "FOREIGN KEY(agent_run_id) REFERENCES agent_runs (id) ON DELETE SET NULL" in ddl
    assert "CREATE INDEX idx_insights_agent_run_id ON insights (agent_run_id)" in ddl
    assert "CREATE INDEX idx_action_items_agent_run_id ON action_items (agent_run_id)" in ddl


def test_analysis_outputs_link_to_agent_runs() -> None:
    insights = Base.metadata.tables["insights"]
    action_items = Base.metadata.tables["action_items"]

    # 選填關聯欄位存在且可為 NULL（ON DELETE SET NULL 的前提）
    for table in (insights, action_items):
        assert "agent_run_id" in table.columns
        assert table.columns["agent_run_id"].nullable is True

    # run-level 查詢所需的索引存在
    index_names = {idx.name for idx in insights.indexes} | {idx.name for idx in action_items.indexes}
    assert "idx_insights_agent_run_id" in index_names
    assert "idx_action_items_agent_run_id" in index_names
