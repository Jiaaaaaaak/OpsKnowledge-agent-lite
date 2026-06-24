from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class RerankerProvider(ABC):
    """第二階段重排的抽象介面。新增 provider 只需實作 rerank()。"""

    @abstractmethod
    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        """回傳 [(原始 index, 相關性分數), ...]，依相關性由高到低排序。"""


class NoopRerankerProvider(RerankerProvider):
    """Identity reranker — 維持第一階段（向量）順序。停用或 CI 時使用。"""

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        return [(i, 0.0) for i in range(len(documents))]


class TeiRerankerProvider(RerankerProvider):
    """
    呼叫 HF text-embeddings-inference 的 /rerank 端點（bge-reranker-v2-m3）。

    cross-encoder 直接以 (query, document) 配對算相關分，跨語言（英文文件 +
    中文問題）效果遠勝純向量距離。base_url 讀自 RERANKER_BASE_URL；
    TEI 未啟動或模型未載入時，rerank() 會丟出帶明確訊息的 RuntimeError，
    由呼叫端決定是否降級為純向量。
    """

    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self._base_url = (base_url or settings.reranker_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.reranker_timeout_seconds

    def rerank(self, query: str, documents: list[str]) -> list[tuple[int, float]]:
        if not documents:
            return []

        import httpx

        url = f"{self._base_url}/rerank"
        try:
            resp = httpx.post(
                url,
                json={"query": query, "texts": documents},
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Reranker 回傳錯誤狀態 {exc.response.status_code}："
                f"請確認 TEI 已載入 {settings.reranker_model}。"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"無法連線到 reranker（{url}）：請確認 reranker 容器已啟動。原始錯誤：{exc}"
            ) from exc

        # TEI 回傳 [{"index": i, "score": s}, ...]，已依 score 由高到低排序
        data = resp.json()
        return [(int(item["index"]), float(item["score"])) for item in data]


def get_reranker_provider() -> RerankerProvider:
    """
    依 RERANKER_ENABLED 選擇 provider。
    True  → TeiRerankerProvider（呼叫 reranker 容器）
    False → NoopRerankerProvider（維持向量順序，CI / 單階段預設）
    """
    if settings.reranker_enabled:
        return TeiRerankerProvider()
    return NoopRerankerProvider()
