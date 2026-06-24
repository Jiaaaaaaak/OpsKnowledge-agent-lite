from __future__ import annotations

from functools import lru_cache

from sqlalchemy.orm import Session

from app.services.retrieval.fusion import ReciprocalRankFusion
from app.services.retrieval.keyword_retriever import KeywordRetriever
from app.services.retrieval.vector_retriever import VectorRetriever


class HybridRetrievalService:
    """Coordinate vector + keyword retrieval and RRF fusion."""

    def __init__(
        self,
        *,
        vector_retriever: VectorRetriever,
        keyword_retriever: KeywordRetriever,
        fusion: ReciprocalRankFusion | None = None,
    ) -> None:
        self._vector = vector_retriever
        self._keyword = keyword_retriever
        self._fusion = fusion or ReciprocalRankFusion()

    def search(self, project_id: str, query: str, top_k: int = 5) -> tuple[list[dict], dict]:
        vector_hits = self._vector.search(project_id, query, top_k)
        keyword_hits = self._keyword.search(project_id, query, top_k)
        fused_hits = self._fusion.fuse(
            [("vector", vector_hits), ("keyword", keyword_hits)],
            limit=top_k,
        )
        return fused_hits, {
            "mode": "hybrid",
            "vector_hit_count": len(vector_hits),
            "keyword_hit_count": len(keyword_hits),
            "fused_hit_count": len(fused_hits),
        }


@lru_cache(maxsize=1)
def _get_cached_retrieval_service() -> HybridRetrievalService:
    return HybridRetrievalService(
        vector_retriever=VectorRetriever(),
        keyword_retriever=KeywordRetriever(),
    )


def get_retrieval_service(db_session: Session | None = None) -> HybridRetrievalService:
    if db_session is None:
        return _get_cached_retrieval_service()
    return HybridRetrievalService(
        vector_retriever=VectorRetriever(db_session=db_session),
        keyword_retriever=KeywordRetriever(db_session=db_session),
    )
