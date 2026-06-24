"""
VectorStoreService unit tests for PostgreSQL + pgvector.

The service should keep the public vector-store API stable while using
PostgreSQL writes and pgvector cosine-distance search against document_chunks.
"""
from unittest.mock import MagicMock
from unittest.mock import patch

from app.services.vector_store import ChunkPayload, VectorStoreService


def _make_payload(chunk_id: str, idx: int, content: str) -> ChunkPayload:
    return ChunkPayload(
        chunk_id=chunk_id,
        document_id="doc-1",
        project_id="proj-1",
        filename="manual.pdf",
        chunk_index=idx,
        content=content,
    )


class TestAddChunks:

    def test_updates_chunk_embeddings_in_postgresql(self):
        db = MagicMock()
        embedder = MagicMock()
        embedder.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]

        store = VectorStoreService(embedder, db_session=db)
        count = store.add_chunks([
            _make_payload("c1", 0, "first"),
            _make_payload("c2", 1, "second"),
        ])

        assert count == 2
        embedder.embed.assert_called_once_with(["first", "second"])
        assert db.execute.call_count == 2

        first_sql = str(db.execute.call_args_list[0].args[0])
        first_params = db.execute.call_args_list[0].args[1]
        assert "UPDATE document_chunks" in first_sql
        assert "embedding = CAST(:embedding AS vector)" in first_sql
        assert first_params == {"chunk_id": "c1", "embedding": "[0.1,0.2]"}

    def test_raises_when_update_matches_no_row(self):
        # 大聲報錯：chunk 尚未寫入 DB 時 UPDATE 命中 0 列，必須丟錯而非靜默讓 embedding 維持 NULL。
        import pytest

        db = MagicMock()
        db.execute.return_value.rowcount = 0
        embedder = MagicMock()
        embedder.embed.return_value = [[0.1, 0.2]]

        store = VectorStoreService(embedder, db_session=db)
        with pytest.raises(RuntimeError, match="未命中"):
            store.add_chunks([_make_payload("ghost", 0, "orphan chunk")])

    def test_empty_chunks_no_embed_no_update(self):
        db = MagicMock()
        embedder = MagicMock()

        store = VectorStoreService(embedder, db_session=db)
        assert store.add_chunks([]) == 0

        embedder.embed.assert_not_called()
        db.execute.assert_not_called()

    def test_embeds_chunks_in_configured_batches(self):
        db = MagicMock()
        embedder = MagicMock()
        embedder.embed.side_effect = [
            [[0.1], [0.2]],
            [[0.3], [0.4]],
            [[0.5]],
        ]

        chunks = [_make_payload(f"c{i}", i, f"text-{i}") for i in range(5)]
        store = VectorStoreService(embedder, db_session=db)

        with patch("app.services.vector_store.settings.embedding_batch_size", 2):
            count = store.add_chunks(chunks)

        assert count == 5
        assert embedder.embed.call_args_list[0].args[0] == ["text-0", "text-1"]
        assert embedder.embed.call_args_list[1].args[0] == ["text-2", "text-3"]
        assert embedder.embed.call_args_list[2].args[0] == ["text-4"]
        assert db.execute.call_count == 5


class TestDeleteChunks:

    def test_clears_embeddings_for_failed_ingest_compensation(self):
        db = MagicMock()
        embedder = MagicMock()

        store = VectorStoreService(embedder, db_session=db)
        store.delete_chunks(["c1", "c2"])

        sql = str(db.execute.call_args.args[0])
        params = db.execute.call_args.args[1]
        assert "UPDATE document_chunks" in sql
        assert "embedding = NULL" in sql
        assert params == {"chunk_ids": ["c1", "c2"]}


class TestSearch:

    def test_filters_by_project_and_maps_pgvector_results(self):
        row1 = MagicMock()
        row1.chunk_id = "c1"
        row1.content = "doc one"
        row1.distance = 0.1
        row1.document_id = "doc-1"
        row1.filename = "manual.pdf"
        row1.chunk_index = 0
        row1.metadata = {"page_number": 1}

        row2 = MagicMock()
        row2.chunk_id = "c2"
        row2.content = "doc two"
        row2.distance = 0.4
        row2.document_id = "doc-1"
        row2.filename = "manual.pdf"
        row2.chunk_index = 1
        row2.metadata = {"page_number": 2}

        result = MagicMock()
        result.fetchall.return_value = [row1, row2]
        db = MagicMock()
        db.execute.return_value = result
        embedder = MagicMock()
        embedder.embed.return_value = [[0.5, 0.5]]

        store = VectorStoreService(embedder, db_session=db)
        hits = store.search("proj-1", "how to restart", top_k=2)

        sql = str(db.execute.call_args.args[0])
        params = db.execute.call_args.args[1]
        assert "WHERE d.project_id = CAST(:project_id AS uuid)" in sql
        assert "dc.embedding IS NOT NULL" in sql
        assert "dc.embedding <=> CAST(:query_embedding AS vector)" in sql
        assert "LIMIT :top_k" in sql
        assert params == {
            "project_id": "proj-1",
            "query_embedding": "[0.5,0.5]",
            "top_k": 2,
        }

        assert len(hits) == 2
        assert hits[0]["chunk_id"] == "c1"
        assert hits[0]["content"] == "doc one"
        assert hits[0]["metadata"]["project_id"] == "proj-1"
        assert hits[0]["metadata"]["document_id"] == "doc-1"
        assert hits[0]["metadata"]["filename"] == "manual.pdf"
        assert hits[0]["metadata"]["chunk_index"] == 0
        assert hits[0]["distance"] == 0.1
        assert abs(hits[0]["score"] - 0.9) < 1e-9

    def test_no_results_returns_empty_list(self):
        result = MagicMock()
        result.fetchall.return_value = []
        db = MagicMock()
        db.execute.return_value = result
        embedder = MagicMock()
        embedder.embed.return_value = [[0.5]]

        store = VectorStoreService(embedder, db_session=db)
        assert store.search("proj-1", "anything") == []
