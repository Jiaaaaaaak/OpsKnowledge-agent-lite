"""initial schema (projects, documents, document_chunks, agent_runs, tool_calls)

Revision ID: 0001
Revises:
Create Date: 2026-06-25

對齊既有 migrations/001_initial_schema.sql 與 ORM 模型。全程使用 IF NOT EXISTS，
讓既有（曾以 create_all 建好）的資料庫能安全沿用、只補登版本，不破壞既有資料。
向量維度取自 settings.embedding_dimensions（單一真實來源）。
"""
from typing import Sequence, Union

from alembic import op

from app.core.config import settings

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIM = settings.embedding_dimensions


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            name        VARCHAR(255) NOT NULL,
            description TEXT,
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id    UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            filename      VARCHAR(255) NOT NULL,
            document_type VARCHAR(100) NOT NULL,
            source_path   TEXT         NOT NULL,
            metadata      JSONB        NOT NULL DEFAULT '{}',
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)")

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS document_chunks (
            id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id   UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index   INTEGER     NOT NULL,
            content       TEXT        NOT NULL,
            embedding     vector({_DIM}),
            search_vector tsvector    GENERATED ALWAYS AS
                          (to_tsvector('english', coalesce(content, ''))) STORED,
            metadata      JSONB       NOT NULL DEFAULT '{{}}',
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector_gin
        ON document_chunks USING gin (search_vector)
        """
    )
    # Repair path for existing databases created before Alembic adoption:
    # CREATE TABLE IF NOT EXISTS is a no-op when the table already exists, so explicitly
    # add the pgvector / FTS columns and indexes that retrieval requires.
    op.execute(
        f"""
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS embedding vector({_DIM})
        """
    )
    op.execute(
        """
        ALTER TABLE document_chunks
        ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector_gin
        ON document_chunks USING gin (search_vector)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id    UUID         REFERENCES projects(id) ON DELETE SET NULL,
            task_type     VARCHAR(255) NOT NULL,
            model_name    VARCHAR(255) NOT NULL,
            input_json    JSONB        NOT NULL DEFAULT '{}',
            output_json   JSONB        NOT NULL DEFAULT '{}',
            status        VARCHAR(50)  NOT NULL,
            latency_ms    INTEGER,
            error_message TEXT,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_project_id ON agent_runs(project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS tool_calls (
            id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            agent_run_id  UUID         NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
            tool_name     VARCHAR(255) NOT NULL,
            input_json    JSONB        NOT NULL DEFAULT '{}',
            output_json   JSONB        NOT NULL DEFAULT '{}',
            error_message TEXT,
            latency_ms    INTEGER,
            created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_tool_calls_agent_run_id ON tool_calls(agent_run_id)"
    )


def downgrade() -> None:
    # 依外鍵相依的反序丟棄。
    op.execute("DROP TABLE IF EXISTS tool_calls")
    op.execute("DROP TABLE IF EXISTS agent_runs")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    op.execute("DROP TABLE IF EXISTS projects")
