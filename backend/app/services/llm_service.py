from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.core.config import settings

_SYSTEM_PROMPT_TEMPLATE = """\
You are a technical support assistant for IT operations.

Answer ONLY using the context provided below. Do not draw on any external knowledge.

Rules:
- If the context contains the answer, give a concise response; use bullet points for \
step-by-step procedures.
- If the context does not contain enough information, say exactly: \
"The document does not contain enough information to answer this question."
- Never invent commands, configurations, file paths, or procedures that are not \
explicitly stated in the context.

Context:
{context}"""

_SNIPPET_LENGTH = 200


class LLMProvider(ABC):
    """LLM 推論的抽象介面。新增 provider 只需實作 complete 方法。"""

    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        """
        回傳 (answer_text, usage_metadata)。
        usage_metadata 結構由各 provider 自行定義；呼叫端不得假設其欄位。
        """


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    基於 OpenAI SDK 的 provider，可對接任何 OpenAI-compatible endpoint。

    新增 OllamaProvider 範例：
        class OllamaProvider(OpenAICompatibleLLMProvider):
            def __init__(self, model: str = "llama3.1") -> None:
                super().__init__(
                    api_key="ollama",
                    base_url="http://localhost:11434/v1",
                    model=model,
                )
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        from openai import OpenAI

        self._model = model or settings.llm_model
        self._temperature = temperature
        self._client = OpenAI(
            api_key=api_key or settings.openai_api_key,
            base_url=base_url or settings.openai_base_url,
        )

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        answer = response.choices[0].message.content or ""
        usage: dict = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return answer, usage


class MockLLMProvider(LLMProvider):
    """
    完全本地、確定性的 LLM provider，不需任何 API 金鑰。

    - 若 system prompt 中沒有 context（只有 no context retrieved），
      回傳標準「文件不含足夠資訊」回應。
    - 若有 context，從第一個 chunk 擷取前 200 字元作為 mock 答案（帶 [mock] 前綴）。
    適合 CI / 本地開發驗證端到端流程。
    """

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        if "(no context retrieved)" in system_prompt:
            answer = "The document does not contain enough information to answer this question."
        else:
            match = re.search(r"\[\d+\] .+?:\n(.+?)(?:\n\n---|$)", system_prompt, re.DOTALL)
            if match:
                excerpt = match.group(1).strip()[:200]
                answer = f"[mock] {excerpt}"
            else:
                answer = "[mock] Based on the provided context."
        return answer, {"prompt_tokens": 0, "completion_tokens": 0, "mock": True}


def get_llm_provider() -> LLMProvider:
    """
    從 LLM_PROVIDER 環境變數選擇 LLM provider。
    "mock"  → MockLLMProvider（不需 API key，適合 CI / 本地開發）
    "openai"→ OpenAICompatibleLLMProvider（需 OPENAI_API_KEY）
    """
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    return OpenAICompatibleLLMProvider()


def build_rag_prompt(chunks: list[dict]) -> str:
    """從向量搜尋結果建構 RAG system prompt。"""
    if not chunks:
        return _SYSTEM_PROMPT_TEMPLATE.format(context="(no context retrieved)")

    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        filename = meta.get("filename", "unknown")
        chunk_index = meta.get("chunk_index", "?")
        content = chunk.get("content", "")
        parts.append(f"[{i}] {filename} (chunk {chunk_index}):\n{content}")

    context = "\n\n---\n\n".join(parts)
    return _SYSTEM_PROMPT_TEMPLATE.format(context=context)


def format_citations(chunks: list[dict]) -> list[dict]:
    """將向量搜尋 hit 轉換成 API 回應所需的 citation 格式。"""
    citations: list[dict] = []
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        content = chunk.get("content", "")
        snippet = content[:_SNIPPET_LENGTH].strip()
        if len(content) > _SNIPPET_LENGTH:
            snippet += "..."
        citations.append(
            {
                "document_id": meta.get("document_id", ""),
                "chunk_id": chunk.get("chunk_id", ""),
                "filename": meta.get("filename", ""),
                "chunk_index": int(meta.get("chunk_index", 0)),
                "snippet": snippet,
            }
        )
    return citations
