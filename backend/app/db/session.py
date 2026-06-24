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
        conn.execute(
            text(
                f"ALTER TABLE document_chunks "
                f"ADD COLUMN IF NOT EXISTS embedding vector({settings.embedding_dimensions})"
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE document_chunks
                ADD COLUMN IF NOT EXISTS search_vector tsvector
                GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector_gin
                ON document_chunks USING gin (search_vector)
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
