from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings
from app.services.embedding_service import EmbeddingProvider, OpenAIEmbeddingProvider


@dataclass
class ChunkPayload:
    """送入 ChromaDB 的單一 chunk。chunk_id 等同 PostgreSQL document_chunks.id."""

    chunk_id: str
    document_id: str
    project_id: str
    filename: str
    chunk_index: int
    content: str


class VectorStoreService:
    """封裝 ChromaDB collection，負責寫入 chunk 向量與相似度搜尋.

    embedding_provider 以建構子注入，之後要換成本地 embedding 不需動到本類別。
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        host: str | None = None,
        port: int | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._embedder = embedding_provider

        import chromadb

        self._client = chromadb.HttpClient(
            host=host or settings.chroma_host,
            port=port or settings.chroma_port,
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name or settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[ChunkPayload]) -> int:
        """嵌入並 upsert 一批 chunk，回傳寫入筆數."""
        if not chunks:
            return 0
        embeddings = self._embedder.embed([c.content for c in chunks])
        self._collection.upsert(
            ids=[c.chunk_id for c in chunks],
            embeddings=embeddings,
            documents=[c.content for c in chunks],
            metadatas=[
                {
                    "project_id": c.project_id,
                    "document_id": c.document_id,
                    "chunk_id": c.chunk_id,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                }
                for c in chunks
            ],
        )
        return len(chunks)

    def search(self, project_id: str, query: str, top_k: int = 5) -> list[dict]:
        """在指定專案範圍內做相似度搜尋，回傳 top_k 個 chunk（含 metadata 與分數）."""
        query_embedding = self._embedder.embed([query])[0]
        res = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"project_id": str(project_id)},
        )
        ids = (res.get("ids") or [[]])[0]
        documents = (res.get("documents") or [[]])[0]
        metadatas = (res.get("metadatas") or [[]])[0]
        distances = (res.get("distances") or [[]])[0]

        hits: list[dict] = []
        for i, chunk_id in enumerate(ids):
            distance = distances[i] if i < len(distances) else None
            hits.append(
                {
                    "chunk_id": chunk_id,
                    "content": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "distance": distance,
                    # cosine 距離 → 相似度分數（1 - distance），方便前端排序顯示
                    "score": (1.0 - distance) if distance is not None else None,
                }
            )
        return hits


@lru_cache(maxsize=1)
def get_vector_store() -> VectorStoreService:
    """模組級單例：第一次呼叫才建立 OpenAI provider 與 ChromaDB 連線（並在缺金鑰時 fail loud）."""
    return VectorStoreService(OpenAIEmbeddingProvider())
