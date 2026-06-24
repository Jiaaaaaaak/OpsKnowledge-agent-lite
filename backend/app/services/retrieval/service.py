from __future__ import annotations

import logging
from functools import lru_cache

from sqlalchemy.orm import Session

from app.services.retrieval.fusion import ReciprocalRankFusion
from app.services.retrieval.keyword_retriever import KeywordRetriever
from app.services.retrieval.vector_retriever import VectorRetriever

logger = logging.getLogger(__name__)


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

    def _keyword_arm(self, project_id: str, query: str, top_k: int) -> tuple[list[dict], str]:
        # keyword 這條獨立降級：全文檢索 SQL 出錯（PG 版本差異、未 migrate 出
        # search_vector 欄位等）時，回空結果並標記 fallback，不讓整個檢索失敗。
        try:
            return self._keyword.search(project_id, query, top_k), "ok"
        except Exception:
            logger.exception("keyword retrieval failed; falling back")
            return [], "fallback"

    def search(
        self, project_id: str, query: str, top_k: int = 5, strategy: str = "hybrid"
    ) -> tuple[list[dict], dict]:
        # strategy 由呼叫端（agent）依查詢類型選擇：
        #   "vector"  → 純語意向量（概念/語意題）
        #   "keyword" → 純全文檢索（錯誤碼/指令名/精確詞）
        #   "hybrid"  → 兩條 + RRF 融合（預設、通用）
        if strategy == "vector":
            vector_hits = self._vector.search(project_id, query, top_k)
            return vector_hits, {
                "mode": "vector",
                "vector_hit_count": len(vector_hits),
                "keyword_hit_count": 0,
                "fused_hit_count": len(vector_hits),
            }
        if strategy == "keyword":
            keyword_hits, keyword_status = self._keyword_arm(project_id, query, top_k)
            return keyword_hits, {
                "mode": "keyword",
                "vector_hit_count": 0,
                "keyword_hit_count": len(keyword_hits),
                "keyword_status": keyword_status,
                "fused_hit_count": len(keyword_hits),
            }

        vector_hits = self._vector.search(project_id, query, top_k)
        keyword_hits, keyword_status = self._keyword_arm(project_id, query, top_k)
        fused_hits = self._fusion.fuse(
            [("vector", vector_hits), ("keyword", keyword_hits)],
            limit=top_k,
        )
        return fused_hits, {
            "mode": "hybrid",
            "vector_hit_count": len(vector_hits),
            "keyword_hit_count": len(keyword_hits),
            "keyword_status": keyword_status,
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
