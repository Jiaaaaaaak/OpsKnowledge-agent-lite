from __future__ import annotations

import hashlib
import math
import random as _random
from abc import ABC, abstractmethod

from app.core.config import settings

# 視為「未設定」的金鑰預設值（config.py 與 .env.example 的 placeholder）
_PLACEHOLDER_KEYS = {"", "sk-placeholder", "sk-your-key-here"}


class EmbeddingProvider(ABC):
    """Embedding 抽象介面。之後要換成本地模型只需另寫一個子類別實作 embed()."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """將一批文字轉成向量，回傳順序與輸入一致."""
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """以 OpenAI（或相容端點）產生 embedding。金鑰／模型皆讀自環境變數."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        api_key = api_key if api_key is not None else settings.openai_api_key
        if not api_key or api_key in _PLACEHOLDER_KEYS:
            raise RuntimeError(
                "缺少 OPENAI_API_KEY：請在 .env 設定有效的金鑰後再進行 embedding 與文件搜尋。"
            )

        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url or settings.openai_base_url)
        self._model = model or settings.embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in resp.data]


class MockEmbeddingProvider(EmbeddingProvider):
    """
    完全本地、確定性的 embedding provider，不需任何 API 金鑰。

    每段文字透過 MD5 hash 產生固定的隨機種子，再生成 L2 單位向量。
    相同文字永遠回傳相同向量；可安全用於 CI / 本地開發。
    向量維度固定為 mock_embedding_dim（預設 384）。
    """

    def __init__(self, dim: int | None = None) -> None:
        self._dim = dim if dim is not None else settings.mock_embedding_dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [self._text_to_unit_vector(t) for t in texts]

    def _text_to_unit_vector(self, text: str) -> list[float]:
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
        rng = _random.Random(seed)
        vec = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            vec[0] = 1.0
            norm = 1.0
        return [x / norm for x in vec]


def get_embedding_provider() -> EmbeddingProvider:
    """
    從 EMBEDDING_PROVIDER 環境變數選擇 embedding provider。
    "mock"  → MockEmbeddingProvider（不需 API key，適合 CI / 本地開發）
    "openai"→ OpenAIEmbeddingProvider（需 OPENAI_API_KEY）
    """
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider()
    return OpenAIEmbeddingProvider()
