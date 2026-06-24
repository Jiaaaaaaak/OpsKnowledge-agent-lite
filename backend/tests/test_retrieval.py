"""
Hybrid retrieval unit tests.

These tests define the modular retrieval boundary:
- KeywordRetriever performs PostgreSQL full-text recall.
- ReciprocalRankFusion merges vector and keyword ranks by chunk_id.
"""
from unittest.mock import MagicMock

from app.services.retrieval.fusion import ReciprocalRankFusion
from app.services.retrieval.keyword_retriever import KeywordRetriever


def _hit(chunk_id: str, *, source: str, score: float) -> dict:
    return {
        "chunk_id": chunk_id,
        "content": f"{chunk_id} content",
        "metadata": {
            "document_id": "doc-1",
            "chunk_id": chunk_id,
            "filename": "manual.pdf",
            "chunk_index": 0,
        },
        "score": score,
        "source": source,
    }


class TestReciprocalRankFusion:
    def test_deduplicates_by_chunk_id_and_prefers_cross_source_matches(self):
        vector_hits = [
            _hit("vector-only", source="vector", score=0.9),
            _hit("shared", source="vector", score=0.8),
        ]
        keyword_hits = [
            _hit("shared", source="keyword", score=0.7),
            _hit("keyword-only", source="keyword", score=0.6),
        ]

        fused = ReciprocalRankFusion(k=60).fuse(
            [("vector", vector_hits), ("keyword", keyword_hits)],
            limit=3,
        )

        assert [h["chunk_id"] for h in fused] == ["shared", "vector-only", "keyword-only"]
        assert fused[0]["sources"] == ["vector", "keyword"]
        assert fused[0]["fusion_score"] > fused[1]["fusion_score"]
        assert fused[0]["scores"]["vector"] == 0.8
        assert fused[0]["scores"]["keyword"] == 0.7

    def test_empty_sources_return_empty_list(self):
        assert ReciprocalRankFusion().fuse([], limit=5) == []


class TestKeywordRetriever:
    def test_search_uses_postgresql_full_text_with_project_scope(self):
        row = MagicMock()
        row.chunk_id = "c1"
        row.content = "Restart postgres after editing pg_hba.conf."
        row.document_id = "doc-1"
        row.filename = "postgres.pdf"
        row.chunk_index = 2
        row.metadata = {"page_number": 4}
        row.rank = 0.42

        result = MagicMock()
        result.fetchall.return_value = [row]
        db = MagicMock()
        db.execute.return_value = result

        hits = KeywordRetriever(db_session=db).search("proj-1", "restart postgres", top_k=5)

        sql = str(db.execute.call_args.args[0])
        params = db.execute.call_args.args[1]
        assert "websearch_to_tsquery('english', :query)" in sql
        assert "dc.search_vector @@ query.q" in sql
        assert "d.project_id = CAST(:project_id AS uuid)" in sql
        assert "ts_rank_cd(dc.search_vector, query.q)" in sql
        assert params == {"project_id": "proj-1", "query": "restart postgres", "top_k": 5}

        assert hits[0]["chunk_id"] == "c1"
        assert hits[0]["source"] == "keyword"
        assert hits[0]["score"] == 0.42
        assert hits[0]["metadata"]["filename"] == "postgres.pdf"
