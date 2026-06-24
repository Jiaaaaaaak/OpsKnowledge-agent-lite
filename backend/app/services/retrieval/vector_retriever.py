from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.vector_store import get_vector_store


class VectorRetriever:
    """Dense vector retriever backed by pgvector."""

    def __init__(self, *, db_session: Session | None = None) -> None:
        self._db_session = db_session

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        hits = get_vector_store(db_session=self._db_session).search(project_id, query, top_k)
        return [{**hit, "source": "vector"} for hit in hits]
