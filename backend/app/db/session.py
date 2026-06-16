from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def ensure_vector_extension() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def ensure_vector_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(384)"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )


def ensure_analysis_schema() -> None:
    """Repair additive analysis schema changes for existing PostgreSQL volumes."""
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE insights ADD COLUMN IF NOT EXISTS agent_run_id UUID"))
        conn.execute(text("ALTER TABLE action_items ADD COLUMN IF NOT EXISTS agent_run_id UUID"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_insights_agent_run_id
                ON insights (agent_run_id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_action_items_agent_run_id
                ON action_items (agent_run_id)
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'insights_agent_run_id_fkey'
                    ) THEN
                        ALTER TABLE insights
                        ADD CONSTRAINT insights_agent_run_id_fkey
                        FOREIGN KEY (agent_run_id)
                        REFERENCES agent_runs(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint
                        WHERE conname = 'action_items_agent_run_id_fkey'
                    ) THEN
                        ALTER TABLE action_items
                        ADD CONSTRAINT action_items_agent_run_id_fkey
                        FOREIGN KEY (agent_run_id)
                        REFERENCES agent_runs(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            )
        )


def check_vector_extension() -> bool:
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            return result.scalar() == 1
    except Exception:
        return False
