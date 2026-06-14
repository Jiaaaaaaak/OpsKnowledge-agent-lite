from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.services.embedding_service import EmbeddingProvider, get_embedding_provider


@dataclass
class ChunkPayload:
    """Single chunk to embed. chunk_id equals document_chunks.id."""

    chunk_id: str
    document_id: str
    project_id: str
    filename: str
    chunk_index: int
    content: str


class VectorStoreService:
    """PostgreSQL + pgvector-backed vector store.

    embedding_provider is injected so embedding providers can change without
    touching storage logic.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        db_session: Session | None = None,
    ) -> None:
        self._embedder = embedding_provider
        self._db_session = db_session

    @staticmethod
    def _vector_literal(vector: list[float]) -> str:
        return "[" + ",".join(str(float(v)) for v in vector) + "]"

    @staticmethod
    def _row_value(row, key: str):
        mapping = getattr(row, "_mapping", None)
        if mapping is not None and key in mapping:
            return mapping[key]
        return getattr(row, key)

    @contextmanager
    def _session_scope(self) -> Iterator[tuple[Session, bool]]:
        if self._db_session is not None:
            yield self._db_session, False
            return

        db = SessionLocal()
        try:
            yield db, True
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add_chunks(self, chunks: list[ChunkPayload]) -> int:
        """Embed chunks and update document_chunks.embedding."""
        if not chunks:
            return 0
        embeddings = self._embedder.embed([c.content for c in chunks])
        update_sql = text(
            """
            UPDATE document_chunks
            SET embedding = CAST(:embedding AS vector)
            WHERE id = CAST(:chunk_id AS uuid)
            """
        )
        with self._session_scope() as (db, _owns_session):
            for chunk, embedding in zip(chunks, embeddings):
                db.execute(
                    update_sql,
                    {
                        "chunk_id": chunk.chunk_id,
                        "embedding": self._vector_literal(embedding),
                    },
                )
        return len(chunks)

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Clear embeddings for chunk ids; used as ingest failure compensation."""
        if not chunk_ids:
            return
        with self._session_scope() as (db, _owns_session):
            db.execute(
                text(
                    """
                    UPDATE document_chunks
                    SET embedding = NULL
                    WHERE id = ANY(CAST(:chunk_ids AS uuid[]))
                    """
                ),
                {"chunk_ids": chunk_ids},
            )

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Search project-scoped chunks by cosine distance."""
        query_embedding = self._embedder.embed([query])[0]
        search_sql = text(
            """
            SELECT
                dc.id::text AS chunk_id,
                dc.content AS content,
                dc.metadata AS metadata,
                dc.document_id::text AS document_id,
                d.filename AS filename,
                dc.chunk_index AS chunk_index,
                dc.embedding <=> CAST(:query_embedding AS vector) AS distance
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE d.project_id = CAST(:project_id AS uuid)
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)
            LIMIT :top_k
            """
        )
        with self._session_scope() as (db, _owns_session):
            rows = db.execute(
                search_sql,
                {
                    "project_id": str(project_id),
                    "query_embedding": self._vector_literal(query_embedding),
                    "top_k": top_k,
                },
            ).fetchall()

        hits: list[dict] = []
        for row in rows:
            distance = self._row_value(row, "distance")
            chunk_id = self._row_value(row, "chunk_id")
            content = self._row_value(row, "content")
            document_id = self._row_value(row, "document_id")
            filename = self._row_value(row, "filename")
            chunk_index = self._row_value(row, "chunk_index")
            metadata = dict(self._row_value(row, "metadata") or {})
            metadata.update(
                {
                    "project_id": str(project_id),
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "filename": filename,
                    "chunk_index": chunk_index,
                }
            )
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": content,
                    "metadata": metadata,
                    "distance": distance,
                    "score": (1.0 - distance) if distance is not None else None,
                }
            )
        return hits


@lru_cache(maxsize=1)
def _get_cached_vector_store() -> VectorStoreService:
    return VectorStoreService(get_embedding_provider())


def get_vector_store(db_session: Session | None = None) -> VectorStoreService:
    """
    Build a vector store. Without db_session this returns a cached service.

    - "mock"   → MockEmbeddingProvider（無須 API key）
    - "openai" → OpenAIEmbeddingProvider（需 OPENAI_API_KEY）
    """
    if db_session is None:
        return _get_cached_vector_store()
    return VectorStoreService(get_embedding_provider(), db_session=db_session)
