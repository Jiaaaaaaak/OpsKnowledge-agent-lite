"""
EmbeddingProvider / OpenAIEmbeddingProvider 單元測試
意圖：
- 缺金鑰必須 fail loud（這是上傳/搜尋失敗時給使用者清楚訊息的關鍵）
- 空輸入不應呼叫遠端 API（省 token、避免無謂請求）
- 回傳順序須與輸入一致
"""
from unittest.mock import MagicMock, patch

import pytest

from app.services.embedding_service import OpenAIEmbeddingProvider


class TestMissingKeyFailsLoud:

    @pytest.mark.parametrize("bad_key", ["", "sk-placeholder", "sk-your-key-here"])
    def test_placeholder_or_empty_key_raises_runtime_error(self, bad_key):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            OpenAIEmbeddingProvider(api_key=bad_key)


class TestEmbed:

    @patch("openai.OpenAI")
    def test_embed_returns_vectors_in_order(self, mock_openai_cls):
        item1, item2 = MagicMock(), MagicMock()
        item1.embedding = [0.1, 0.2]
        item2.embedding = [0.3, 0.4]
        mock_openai_cls.return_value.embeddings.create.return_value = MagicMock(data=[item1, item2])

        provider = OpenAIEmbeddingProvider(api_key="sk-real-key")
        result = provider.embed(["alpha", "beta"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]
        mock_openai_cls.return_value.embeddings.create.assert_called_once()

    @patch("openai.OpenAI")
    def test_empty_input_skips_api_call(self, mock_openai_cls):
        provider = OpenAIEmbeddingProvider(api_key="sk-real-key")
        assert provider.embed([]) == []
        mock_openai_cls.return_value.embeddings.create.assert_not_called()
