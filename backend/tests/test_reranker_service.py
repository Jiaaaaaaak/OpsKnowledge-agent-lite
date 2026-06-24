"""
RerankerProvider 單元測試。

涵蓋：
- NoopRerankerProvider 維持原順序（停用 / CI 行為）
- TeiRerankerProvider 解析 TEI /rerank 回應並保留其排序；空輸入不打 HTTP
- 連線 / 狀態錯誤丟出可操作的 RuntimeError
- get_reranker_provider() 依 RERANKER_ENABLED 選對 provider
"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.reranker_service import (
    NoopRerankerProvider,
    TeiRerankerProvider,
    get_reranker_provider,
)


class TestNoopRerankerProvider:
    def test_preserves_input_order(self):
        out = NoopRerankerProvider().rerank("q", ["a", "b", "c"])
        assert out == [(0, 0.0), (1, 0.0), (2, 0.0)]

    def test_empty_input(self):
        assert NoopRerankerProvider().rerank("q", []) == []


class TestTeiRerankerProvider:
    def test_empty_input_skips_http_call(self):
        with patch("httpx.post") as mock_post:
            assert TeiRerankerProvider().rerank("q", []) == []
        mock_post.assert_not_called()

    def test_parses_and_preserves_tei_order(self):
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [
            {"index": 2, "score": 0.91},
            {"index": 0, "score": 0.42},
            {"index": 1, "score": 0.05},
        ]
        with patch("httpx.post", return_value=resp) as mock_post:
            out = TeiRerankerProvider(base_url="http://reranker:80").rerank("q", ["a", "b", "c"])
        assert out == [(2, 0.91), (0, 0.42), (1, 0.05)]
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"query": "q", "texts": ["a", "b", "c"]}

    def test_http_status_error_raises_runtime_error(self):
        import httpx

        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )
        with patch("httpx.post", return_value=resp):
            with pytest.raises(RuntimeError, match="TEI"):
                TeiRerankerProvider().rerank("q", ["a"])

    def test_connection_error_raises_runtime_error(self):
        import httpx

        with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
            with pytest.raises(RuntimeError, match="無法連線到 reranker"):
                TeiRerankerProvider().rerank("q", ["a"])

    def test_uses_settings_defaults(self):
        with patch.object(settings, "reranker_base_url", "http://example:9999"), \
             patch.object(settings, "reranker_timeout_seconds", 30.0):
            provider = TeiRerankerProvider()
        assert provider._base_url == "http://example:9999"
        assert provider._timeout == 30.0


class TestGetRerankerProviderFactory:
    def test_disabled_returns_noop(self):
        with patch.object(settings, "reranker_enabled", False):
            assert isinstance(get_reranker_provider(), NoopRerankerProvider)

    def test_enabled_returns_tei(self):
        with patch.object(settings, "reranker_enabled", True):
            assert isinstance(get_reranker_provider(), TeiRerankerProvider)
