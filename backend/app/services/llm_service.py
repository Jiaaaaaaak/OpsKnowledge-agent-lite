from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger(__name__)

_opencc_converter = None
_opencc_unavailable = False


def to_traditional(text: str) -> str:
    """簡體中文 → 繁體（台灣用語）。小模型常輸出簡體，這裡以 OpenCC 確定性轉換保證繁體。
    只影響簡體漢字，ASCII / 繁體 / 指令不受影響，可安全套用於任意輸出；OpenCC 不在時降級為原文。"""
    global _opencc_converter, _opencc_unavailable
    if not text or _opencc_unavailable:
        return text
    if _opencc_converter is None:
        try:
            import opencc

            _opencc_converter = opencc.OpenCC("s2twp")
        except Exception:
            logger.warning("opencc 不可用，略過簡轉繁（請確認 requirements 的 opencc 已安裝）")
            _opencc_unavailable = True
            return text
    return _opencc_converter.convert(text)


@dataclass
class AgentToolCall:
    """LLM 要求呼叫的一個工具。arguments 已解析為 dict。"""

    id: str
    name: str
    arguments: dict


@dataclass
class AgentLLMResponse:
    """tool-calling 模式下 LLM 單輪輸出：
    content（最終答案，或 None 表示這輪只想呼叫工具）+ tool_calls（要執行的工具）。"""

    content: str | None
    tool_calls: list[AgentToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)


def _to_openai_message(m: dict) -> dict:
    """canonical 訊息 → OpenAI chat 格式（assistant.tool_calls.arguments 為 JSON 字串）。"""
    role = m["role"]
    if role == "tool":
        return {"role": "tool", "tool_call_id": m.get("tool_call_id", ""), "content": m.get("content", "")}
    if role == "assistant" and m.get("tool_calls"):
        return {
            "role": "assistant",
            "content": m.get("content"),
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)},
                }
                for tc in m["tool_calls"]
            ],
        }
    return {"role": role, "content": m.get("content", "")}


def _to_ollama_message(m: dict) -> dict:
    """canonical 訊息 → Ollama chat 格式（arguments 為物件、tool 角色無需 id）。"""
    role = m["role"]
    if role == "tool":
        return {"role": "tool", "content": m.get("content", "")}
    if role == "assistant" and m.get("tool_calls"):
        return {
            "role": "assistant",
            "content": m.get("content") or "",
            "tool_calls": [
                {"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                for tc in m["tool_calls"]
            ],
        }
    return {"role": role, "content": m.get("content", "")}

_SYSTEM_PROMPT_TEMPLATE = """\
You are a technical support assistant for IT operations.

Answer ONLY using the context provided below. Do not draw on any external knowledge.

Rules:
- Respond in the same language as the user's question, even when the context is in \
another language. For any Chinese question, answer in Traditional Chinese (Taiwan), \
never Simplified Chinese.
- If the context contains the answer, give a concise response; use bullet points for \
step-by-step procedures.
- If the context does not contain enough information, say exactly: \
"The document does not contain enough information to answer this question."
- Never invent commands, configurations, file paths, or procedures that are not \
explicitly stated in the context.

Context:
{context}"""

_SNIPPET_LENGTH = 200

# 翻譯用的 system prompt 前綴（哨兵）。MockLLMProvider 看到此前綴時直接回傳原文，
# 讓 CI / 本地不需真實模型也能跑完跨語流程（翻譯結果 == 原文，僅驗證串接與欄位）。
_TRANSLATE_MARKER = "[TRANSLATE]"
_LANGUAGE_NAMES = {"zh": "Traditional Chinese", "en": "English"}

# 偵測 CJK（中日韓統一表意文字）以區分中／英文。只要含 CJK 字元即視為中文，
# 其餘視為英文 — 對「中英混合語料」的翻譯觸發判斷已足夠（Rule 5：能用程式判就別用模型）。
_CJK_RE = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


def detect_language(text: str) -> str:
    """回傳 'zh'（含 CJK 字元）或 'en'（其餘）。"""
    return "zh" if _CJK_RE.search(text or "") else "en"


def translate_snippet(
    text: str, target_language: str, provider: "LLMProvider | None" = None
) -> str:
    """將 text 翻成 target_language（'zh'/'en'）。
    provider 預設沿用 get_llm_provider()；呼叫端可傳入已建立的 provider 重用，省一次建構。"""
    target_name = _LANGUAGE_NAMES.get(target_language, target_language)
    system_prompt = (
        f"{_TRANSLATE_MARKER} You are a translator. Translate the user's text into "
        f"{target_name}. Output ONLY the translation, with no quotes, labels, or commentary."
    )
    answer, _ = (provider or get_llm_provider()).complete(system_prompt, text)
    result = answer.strip()
    # 目標為中文時統一轉繁體，避免小模型輸出簡體。
    return to_traditional(result) if target_language == "zh" else result


class LLMProvider(ABC):
    """LLM 推論的抽象介面。新增 provider 只需實作 complete 方法。"""

    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        """
        回傳 (answer_text, usage_metadata)。
        usage_metadata 結構由各 provider 自行定義；呼叫端不得假設其欄位。
        """

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> AgentLLMResponse:
        """
        tool-calling 單輪推論，供 agent 迴圈使用。

        messages 為 provider 無關的 canonical 格式（各 provider 自行轉成自家 API）：
          {"role": "system"|"user", "content": str}
          {"role": "assistant", "content": str|None,
           "tool_calls": [{"id", "name", "arguments": dict}]}
          {"role": "tool", "tool_call_id": str, "name": str, "content": str}
        tools 為 OpenAI 風格的 function 定義（Ollama 亦相容，可原樣傳遞）。

        預設不支援（mock 以外的某些 provider 若未實作則丟出明確錯誤）。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 尚未支援 tool-calling（agent 模式）。"
        )


class OpenAICompatibleLLMProvider(LLMProvider):
    """
    基於 OpenAI SDK 的 provider，可對接任何 OpenAI-compatible endpoint。

    若要改用本地模型，請改用 OllamaLLMProvider（直接呼叫 Ollama 原生 API），
    或設定 LLM_PROVIDER=ollama。
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

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> AgentLLMResponse:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[_to_openai_message(m) for m in messages],
            tools=tools,
            tool_choice="auto",
        )
        message = response.choices[0].message
        tool_calls: list[AgentToolCall] = []
        for tc in message.tool_calls or []:
            try:
                arguments = json.loads(tc.function.arguments or "{}")
            except (json.JSONDecodeError, TypeError):
                arguments = {}
            tool_calls.append(AgentToolCall(id=tc.id, name=tc.function.name, arguments=arguments))
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return AgentLLMResponse(content=message.content, tool_calls=tool_calls, usage=usage)


class OllamaLLMProvider(LLMProvider):
    """
    原生 Ollama HTTP provider，直接呼叫本機 Ollama 的 /api/chat 端點。

    與 OpenAICompatibleLLMProvider 不同，這個 provider 不經過 OpenAI SDK，
    而是直接打 Ollama 原生 API，用來示範 LLM 後端可完全替換成本地、
    私有 / 地端部署的模型。base_url 與 model 讀自 OLLAMA_BASE_URL / OLLAMA_MODEL。
    若 Ollama 服務未啟動或無法連線，complete() 會丟出帶有明確訊息的 RuntimeError。
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        temperature: float = 0.1,
        timeout: float | None = None,
    ) -> None:
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._temperature = temperature
        self._timeout = timeout if timeout is not None else settings.ollama_timeout_seconds

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        import httpx

        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # 連得上服務，但模型或請求有問題（最常見：模型尚未 pull 下來）
            raise RuntimeError(
                f"Ollama 回傳錯誤狀態 {exc.response.status_code}（model={self._model}）："
                f"請確認模型已下載（執行 `ollama pull {self._model}`）。"
            ) from exc
        except httpx.RequestError as exc:
            # 連不上服務本身
            raise RuntimeError(
                f"無法連線到 Ollama（{url}）：請確認 Ollama 服務已啟動，"
                f"Docker Compose 可執行 `docker compose ps ollama` 檢查狀態，"
                f"且 OLLAMA_BASE_URL 設定正確。原始錯誤：{exc}"
            ) from exc

        data = response.json()
        answer = data.get("message", {}).get("content", "")
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
        }
        return answer, usage

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> AgentLLMResponse:
        import httpx

        url = f"{self._base_url}/api/chat"
        payload = {
            "model": self._model,
            "messages": [_to_ollama_message(m) for m in messages],
            "tools": tools,
            "stream": False,
            "options": {"temperature": self._temperature},
        }
        try:
            response = httpx.post(url, json=payload, timeout=self._timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama 回傳錯誤狀態 {exc.response.status_code}（model={self._model}）："
                f"請確認模型已下載且支援 tool-calling（如 qwen2.5）。"
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(
                f"無法連線到 Ollama（{url}）：請確認 Ollama 服務已啟動。原始錯誤：{exc}"
            ) from exc

        data = response.json()
        message = data.get("message", {})
        # Ollama 不回 tool_call id，自行編號讓後續 tool 結果可對應。
        tool_calls = [
            AgentToolCall(
                id=f"call_{i}",
                name=tc.get("function", {}).get("name", ""),
                arguments=tc.get("function", {}).get("arguments", {}) or {},
            )
            for i, tc in enumerate(message.get("tool_calls", []) or [])
        ]
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
        }
        return AgentLLMResponse(
            content=message.get("content") or None, tool_calls=tool_calls, usage=usage
        )


class MockLLMProvider(LLMProvider):
    """
    完全本地、確定性的 LLM provider，不需任何 API 金鑰。

    - 若 system prompt 中沒有 context（只有 no context retrieved），
      回傳標準「文件不含足夠資訊」回應。
    - 若有 context，從第一個 chunk 擷取前 200 字元作為 mock 答案（帶 [mock] 前綴）。
    適合 CI / 本地開發驗證端到端流程。
    """

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "mock": True}
        if system_prompt.startswith(_TRANSLATE_MARKER):
            # 翻譯請求：直接回傳原文，CI 不需真實模型也能驗證跨語串接。
            return user_message, usage
        if "(no context retrieved)" in system_prompt:
            answer = "The document does not contain enough information to answer this question."
        else:
            match = re.search(r"\[\d+\] .+?:\n(.+?)(?:\n\n---|$)", system_prompt, re.DOTALL)
            if match:
                excerpt = match.group(1).strip()[:200]
                answer = f"[mock] {excerpt}"
            else:
                answer = "[mock] Based on the provided context."
        return answer, usage

    def complete_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> AgentLLMResponse:
        # 確定性 agent 行為，讓 CI 不需真實模型也能跑完 agent 迴圈：
        #   1) 已有工具結果 → 從結果擷取答案，不再呼叫工具（迴圈收斂）。
        #   2) 閒聊/問候 → 直接作答，不檢索。
        #   3) 其餘 → 呼叫一次 search_documents，依關鍵字 heuristic 選 strategy。
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "mock": True}
        tool_outputs = [m.get("content", "") for m in messages if m.get("role") == "tool"]
        if tool_outputs:
            joined = "\n".join(t for t in tool_outputs if t).strip()
            if not joined or "(no results)" in joined:
                return AgentLLMResponse(
                    content="The document does not contain enough information to answer this question.",
                    usage=usage,
                )
            return AgentLLMResponse(content=f"[mock] {joined[:200]}", usage=usage)

        question = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        if any(tok in question.lower() for tok in _CHITCHAT_TOKENS):
            return AgentLLMResponse(
                content="[mock] 你好！我是 IT 維運知識助理，有文件相關問題都可以問我。",
                usage=usage,
            )
        strategy = "keyword" if _looks_like_keyword_query(question) else "hybrid"
        return AgentLLMResponse(
            content=None,
            tool_calls=[
                AgentToolCall(
                    id="mock-call-1",
                    name="search_documents",
                    arguments={"query": question, "strategy": strategy},
                )
            ],
            usage=usage,
        )


# Mock agent heuristic：閒聊詞與「精確詞」判斷，僅供 MockLLMProvider 的確定性決策使用。
_CHITCHAT_TOKENS = (
    "你好", "哈囉", "嗨", "hi", "hello", "謝謝", "thanks", "thank you",
    "你是誰", "who are you", "掰掰", "bye",
)


def _looks_like_keyword_query(text: str) -> bool:
    """精確詞（錯誤碼/指令名/縮寫）→ 偏關鍵字檢索。含反引號、字母+數字混合 token、或長度≥3 全大寫詞即視為精確詞。"""
    if "`" in text:
        return True
    for token in re.findall(r"[A-Za-z0-9_]+", text):
        has_alpha = any(c.isalpha() for c in token)
        has_digit = any(c.isdigit() for c in token)
        if has_alpha and has_digit:
            return True
        if token.isupper() and len(token) >= 3:
            return True
    return False


def get_llm_provider() -> LLMProvider:
    """
    從 LLM_PROVIDER 環境變數選擇 LLM provider。
    "mock"  → MockLLMProvider（不需 API key，適合 CI / 本地開發）
    "ollama"→ OllamaLLMProvider（呼叫本機 Ollama，私有 / 地端部署用）
    "openai"→ OpenAICompatibleLLMProvider（需 OPENAI_API_KEY）
    """
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider()
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
                "source_language": detect_language(content),
                "snippet_translated": None,
            }
        )
    return citations
