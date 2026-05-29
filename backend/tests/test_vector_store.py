"""
VectorStoreService 單元測試（mocked ChromaDB + mocked embedder）
意圖：
- add_chunks 必須帶齊 5 個 metadata 欄位，且 ChromaDB id == chunk_id（之後才能對回 PostgreSQL）
- search 必須以 project_id 過濾（避免跨專案洩漏），並把 cosine 距離換成相似度分數
- 空輸入不寫入也不嵌入
"""
from unittest.mock import MagicMock, patch

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

    @patch("chromadb.HttpClient")
    def test_upserts_with_full_metadata_and_matching_ids(self, mock_http):
        collection = mock_http.return_value.get_or_create_collection.return_value
        embedder = MagicMock()
        embedder.embed.return_value = [[0.1], [0.2]]

        store = VectorStoreService(embedder)
        count = store.add_chunks([
            _make_payload("c1", 0, "first"),
            _make_payload("c2", 1, "second"),
        ])

        assert count == 2
        embedder.embed.assert_called_once_with(["first", "second"])

        kwargs = collection.upsert.call_args.kwargs
        assert kwargs["ids"] == ["c1", "c2"]
        assert kwargs["documents"] == ["first", "second"]
        meta0 = kwargs["metadatas"][0]
        assert set(meta0) == {"project_id", "document_id", "chunk_id", "filename", "chunk_index"}
        assert meta0["chunk_id"] == "c1"  # ChromaDB id 對回 PostgreSQL document_chunks.id 的依據
        assert meta0["project_id"] == "proj-1"
        assert meta0["chunk_index"] == 0

    @patch("chromadb.HttpClient")
    def test_empty_chunks_no_embed_no_upsert(self, mock_http):
        collection = mock_http.return_value.get_or_create_collection.return_value
        embedder = MagicMock()

        store = VectorStoreService(embedder)
        assert store.add_chunks([]) == 0

        embedder.embed.assert_not_called()
        collection.upsert.assert_not_called()


class TestSearch:

    @patch("chromadb.HttpClient")
    def test_filters_by_project_and_maps_results(self, mock_http):
        collection = mock_http.return_value.get_or_create_collection.return_value
        collection.query.return_value = {
            "ids": [["c1", "c2"]],
            "documents": [["doc one", "doc two"]],
            "metadatas": [[{"project_id": "proj-1", "chunk_id": "c1"},
                           {"project_id": "proj-1", "chunk_id": "c2"}]],
            "distances": [[0.1, 0.4]],
        }
        embedder = MagicMock()
        embedder.embed.return_value = [[0.5, 0.5]]

        store = VectorStoreService(embedder)
        hits = store.search("proj-1", "how to restart", top_k=2)

        # 必須以 project_id 過濾，避免跨專案結果外洩
        qkwargs = collection.query.call_args.kwargs
        assert qkwargs["where"] == {"project_id": "proj-1"}
        assert qkwargs["n_results"] == 2

        assert len(hits) == 2
        assert hits[0]["chunk_id"] == "c1"
        assert hits[0]["content"] == "doc one"
        assert hits[0]["distance"] == 0.1
        assert abs(hits[0]["score"] - 0.9) < 1e-9  # score = 1 - distance

    @patch("chromadb.HttpClient")
    def test_no_results_returns_empty_list(self, mock_http):
        collection = mock_http.return_value.get_or_create_collection.return_value
        collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        }
        embedder = MagicMock()
        embedder.embed.return_value = [[0.5]]

        store = VectorStoreService(embedder)
        assert store.search("proj-1", "anything") == []
