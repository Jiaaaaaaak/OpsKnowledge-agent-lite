"""
MockEmbeddingProvider / MockLLMProvider 單元測試，以及 get_*_provider() factory 測試。

目的：
- 驗證 mock provider 在不需任何 API key 的情況下能正確運作
- 確保向量維度、確定性、L2 正規化的性質成立
- 確保 LLM mock 在有 context / 無 context 兩種情境下回傳合理答案
- 確保 factory function 能依 settings 選擇正確的 provider
- 確保 mock provider 可以串接 VectorStoreService (mocked ChromaDB) 完成完整端到端流程
"""
import math
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.services.embedding_service import (
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
)
from app.services.llm_service import (
    MockLLMProvider,
    OpenAICompatibleLLMProvider,
    build_rag_prompt,
    format_citations,
    get_llm_provider,
)


# ─────────────────────────────────────────────────────────────
# MockEmbeddingProvider
# ─────────────────────────────────────────────────────────────

class TestMockEmbeddingProvider:

    def test_default_dim_matches_config(self):
        provider = MockEmbeddingProvider()
        assert provider.dim == settings.mock_embedding_dim

    def test_custom_dim(self):
        provider = MockEmbeddingProvider(dim=64)
        vecs = provider.embed(["hello"])
        assert len(vecs[0]) == 64

    def test_returns_correct_number_of_vectors(self):
        provider = MockEmbeddingProvider(dim=16)
        vecs = provider.embed(["a", "b", "c"])
        assert len(vecs) == 3

    def test_vector_dimension(self):
        dim = 32
        provider = MockEmbeddingProvider(dim=dim)
        vec = provider.embed(["some text"])[0]
        assert len(vec) == dim

    def test_empty_input_returns_empty_list(self):
        provider = MockEmbeddingProvider(dim=16)
        assert provider.embed([]) == []

    def test_deterministic_same_text_same_vector(self):
        provider = MockEmbeddingProvider(dim=32)
        v1 = provider.embed(["Docker volumes persist data"])[0]
        v2 = provider.embed(["Docker volumes persist data"])[0]
        assert v1 == v2

    def test_different_texts_give_different_vectors(self):
        provider = MockEmbeddingProvider(dim=64)
        v1 = provider.embed(["restart service"])[0]
        v2 = provider.embed(["database connection error"])[0]
        assert v1 != v2

    def test_vectors_are_unit_normalized(self):
        provider = MockEmbeddingProvider(dim=128)
        for text in ["foo", "bar baz", "the quick brown fox"]:
            vec = provider.embed([text])[0]
            norm = math.sqrt(sum(x * x for x in vec))
            assert abs(norm - 1.0) < 1e-9, f"Norm {norm!r} is not 1.0 for {text!r}"

    def test_multiple_texts_each_normalized(self):
        provider = MockEmbeddingProvider(dim=64)
        texts = ["alpha", "beta", "gamma", "delta"]
        vecs = provider.embed(texts)
        for text, vec in zip(texts, vecs):
            norm = math.sqrt(sum(x * x for x in vec))
            assert abs(norm - 1.0) < 1e-9

    def test_order_preserved(self):
        provider = MockEmbeddingProvider(dim=16)
        texts = ["first", "second", "third"]
        vecs = provider.embed(texts)
        for i, t in enumerate(texts):
            expected = provider.embed([t])[0]
            assert vecs[i] == expected


# ─────────────────────────────────────────────────────────────
# MockLLMProvider
# ─────────────────────────────────────────────────────────────

class TestMockLLMProvider:

    def _no_context_prompt(self) -> str:
        return build_rag_prompt([])

    def _with_context_prompt(self) -> str:
        return build_rag_prompt([
            {
                "chunk_id": "c1",
                "content": "To check Docker volumes, run docker inspect <container> and look at Mounts.",
                "metadata": {"filename": "docker.pdf", "chunk_index": 0},
            }
        ])

    def test_returns_str_and_dict(self):
        provider = MockLLMProvider()
        answer, usage = provider.complete(self._no_context_prompt(), "question")
        assert isinstance(answer, str)
        assert isinstance(usage, dict)

    def test_no_context_returns_insufficient_info_phrase(self):
        # 當 context 為空時必須回傳標準「文件不含足夠資訊」措辭
        provider = MockLLMProvider()
        answer, _ = provider.complete(self._no_context_prompt(), "how do I bake a cake?")
        assert "does not contain enough information" in answer

    def test_with_context_returns_mock_prefix(self):
        # 有 context 時 mock provider 應帶 [mock] 前綴
        provider = MockLLMProvider()
        answer, _ = provider.complete(self._with_context_prompt(), "what should I check?")
        assert answer.startswith("[mock]")

    def test_with_context_answer_contains_context_content(self):
        # mock answer 應包含 chunk 內容的摘取
        provider = MockLLMProvider()
        answer, _ = provider.complete(self._with_context_prompt(), "what should I check?")
        assert "docker inspect" in answer.lower() or "docker" in answer.lower()

    def test_usage_dict_has_token_keys(self):
        provider = MockLLMProvider()
        _, usage = provider.complete(self._no_context_prompt(), "q")
        assert "prompt_tokens" in usage
        assert "completion_tokens" in usage

    def test_usage_tokens_are_zero(self):
        # mock provider 不呼叫遠端，token 計數為 0
        provider = MockLLMProvider()
        _, usage = provider.complete(self._no_context_prompt(), "q")
        assert usage["prompt_tokens"] == 0
        assert usage["completion_tokens"] == 0

    def test_deterministic_same_input_same_output(self):
        provider = MockLLMProvider()
        prompt = self._with_context_prompt()
        a1, u1 = provider.complete(prompt, "same question")
        a2, u2 = provider.complete(prompt, "same question")
        assert a1 == a2
        assert u1 == u2


# ─────────────────────────────────────────────────────────────
# get_embedding_provider() factory
# ─────────────────────────────────────────────────────────────

class TestGetEmbeddingProviderFactory:

    def test_returns_mock_when_configured(self):
        with patch.object(settings, "embedding_provider", "mock"):
            provider = get_embedding_provider()
        assert isinstance(provider, MockEmbeddingProvider)

    def test_returns_openai_when_configured(self):
        with patch.object(settings, "embedding_provider", "openai"), \
             patch.object(settings, "openai_api_key", "sk-test-valid-key"), \
             patch("openai.OpenAI"):
            provider = get_embedding_provider()
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_mock_provider_respects_mock_embedding_dim(self):
        with patch.object(settings, "embedding_provider", "mock"), \
             patch.object(settings, "mock_embedding_dim", 64):
            provider = get_embedding_provider()
        assert isinstance(provider, MockEmbeddingProvider)
        assert provider.dim == 64


# ─────────────────────────────────────────────────────────────
# get_llm_provider() factory
# ─────────────────────────────────────────────────────────────

class TestGetLLMProviderFactory:

    def test_returns_mock_when_configured(self):
        with patch.object(settings, "llm_provider", "mock"):
            provider = get_llm_provider()
        assert isinstance(provider, MockLLMProvider)

    def test_returns_openai_when_configured(self):
        with patch.object(settings, "llm_provider", "openai"), \
             patch("openai.OpenAI"):
            provider = get_llm_provider()
        assert isinstance(provider, OpenAICompatibleLLMProvider)


# ─────────────────────────────────────────────────────────────
# 端到端：MockEmbeddingProvider → VectorStoreService → search → MockLLMProvider
# ─────────────────────────────────────────────────────────────

class TestMockProviderEndToEnd:
    """
    使用 mocked ChromaDB 驗證完整的 mock pipeline。
    不需要任何外部服務或 API key。
    """

    def _make_hit(self, chunk_id: str, content: str, filename: str, chunk_index: int) -> dict:
        return {
            "chunk_id": chunk_id,
            "content": content,
            "metadata": {
                "document_id": "doc-1",
                "chunk_id": chunk_id,
                "filename": filename,
                "chunk_index": chunk_index,
                "project_id": "proj-1",
            },
            "distance": 0.15,
            "score": 0.85,
        }

    def test_mock_embedding_can_embed_and_produce_valid_hits(self):
        """MockEmbeddingProvider + VectorStoreService (mocked ChromaDB) 能完成 add_chunks + search。"""
        from unittest.mock import MagicMock, patch
        from app.services.vector_store import VectorStoreService, ChunkPayload

        hit = self._make_hit("c1", "Run docker inspect to check volumes.", "ops.pdf", 0)

        with patch("chromadb.HttpClient") as mock_http:
            collection = mock_http.return_value.get_or_create_collection.return_value
            collection.query.return_value = {
                "ids": [["c1"]],
                "documents": [["Run docker inspect to check volumes."]],
                "metadatas": [[hit["metadata"]]],
                "distances": [[0.15]],
            }

            embedder = MockEmbeddingProvider(dim=16)
            store = VectorStoreService(embedder)

            # add_chunks 使用 mock embedding
            count = store.add_chunks([
                ChunkPayload(
                    chunk_id="c1",
                    document_id="doc-1",
                    project_id="proj-1",
                    filename="ops.pdf",
                    chunk_index=0,
                    content="Run docker inspect to check volumes.",
                )
            ])
            assert count == 1

            # search 回傳 hit
            hits = store.search("proj-1", "docker volume issue", top_k=1)

        assert len(hits) == 1
        assert hits[0]["chunk_id"] == "c1"
        assert abs(hits[0]["score"] - 0.85) < 1e-9

    def test_mock_pipeline_prompt_to_answer(self):
        """build_rag_prompt → MockLLMProvider.complete → format_citations 完整串接。"""
        hits = [
            self._make_hit("c1", "Docker volumes persist data outside the container lifecycle.", "docker.pdf", 0),
            self._make_hit("c2", "Use named volumes in docker-compose.yml for persistence.", "docker.pdf", 1),
        ]

        system_prompt = build_rag_prompt(hits)
        assert "[1] docker.pdf (chunk 0)" in system_prompt
        assert "[2] docker.pdf (chunk 1)" in system_prompt

        provider = MockLLMProvider()
        answer, usage = provider.complete(system_prompt, "How do I persist Docker data?")

        assert answer.startswith("[mock]")
        assert usage["prompt_tokens"] == 0

        citations = format_citations(hits)
        assert len(citations) == 2
        assert citations[0]["filename"] == "docker.pdf"
        assert citations[0]["chunk_index"] == 0
        assert citations[1]["chunk_index"] == 1
        # snippet truncation
        for c in citations:
            assert len(c["snippet"]) <= 203

    def test_mock_pipeline_no_hits_returns_cannot_answer(self):
        """context 為空時 MockLLMProvider 應回傳標準拒答措辭。"""
        system_prompt = build_rag_prompt([])
        provider = MockLLMProvider()
        answer, _ = provider.complete(system_prompt, "unrelated question")
        assert "does not contain enough information" in answer
        assert format_citations([]) == []
