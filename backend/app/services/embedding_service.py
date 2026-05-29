from __future__ import annotations

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
