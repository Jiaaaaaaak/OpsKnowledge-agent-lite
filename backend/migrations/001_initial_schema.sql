-- OpsKnowledge Agent Lite — Initial Schema
-- Migration: 001
-- PostgreSQL 13+ (uses gen_random_uuid() built-in)

CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────
-- projects
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────
-- documents
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename      VARCHAR(255) NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    source_path   TEXT         NOT NULL,
    metadata      JSONB        NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- ─────────────────────────────────────────────────────────
-- document_chunks
-- ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID        NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER     NOT NULL,
    content     TEXT        NOT NULL,
    embedding   vector(1024),
    metadata    JSONB       NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- ─────────────────────────────────────────────────────────
-- agent_runs
-- ─────────────────────────────────────────────────────────
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
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_project_id ON agent_runs(project_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON agent_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status     ON agent_runs(status);

-- ─────────────────────────────────────────────────────────
-- tool_calls
-- ─────────────────────────────────────────────────────────
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
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_agent_run_id ON tool_calls(agent_run_id);
