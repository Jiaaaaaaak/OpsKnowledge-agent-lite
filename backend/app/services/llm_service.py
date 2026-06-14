from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod

from app.core.config import settings
from app.services.ai_tasks import (
    AGENT_TASK_ACTION_ITEMS,
    AGENT_TASK_CLASSIFY,
    AGENT_TASK_INSIGHTS,
    AGENT_TASK_SEVERITY,
    agent_task_marker,
)

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
        timeout: float = 60.0,
    ) -> None:
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.ollama_model
        self._temperature = temperature
        self._timeout = timeout

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


class MockLLMProvider(LLMProvider):
    """
    完全本地、確定性的 LLM provider，不需任何 API 金鑰。

    - 若 system prompt 中沒有 context（只有 no context retrieved），
      回傳標準「文件不含足夠資訊」回應。
    - 若有 context，從第一個 chunk 擷取前 200 字元作為 mock 答案（帶 [mock] 前綴）。
    適合 CI / 本地開發驗證端到端流程。
    """

    def complete(self, system_prompt: str, user_message: str) -> tuple[str, dict]:
        # Agent 任務：在 system prompt 加上 <<AGENT_TASK:xxx>> 標記，回傳確定性 JSON，
        # 讓 4 個 incident analysis tools 在 mock 模式下也能跑完整流程
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "mock": True}
        if agent_task_marker(AGENT_TASK_CLASSIFY) in system_prompt:
            return self._mock_classify(user_message), usage
        if agent_task_marker(AGENT_TASK_SEVERITY) in system_prompt:
            return self._mock_severity(user_message), usage
        if agent_task_marker(AGENT_TASK_INSIGHTS) in system_prompt:
            return self._mock_insights(user_message), usage
        if agent_task_marker(AGENT_TASK_ACTION_ITEMS) in system_prompt:
            return self._mock_action_items(user_message), usage

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

    @staticmethod
    def _safe_load(user_message: str) -> dict:
        try:
            data = json.loads(user_message)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _mock_classify(cls, user_message: str) -> str:
        data = cls._safe_load(user_message)
        text = ((data.get("issue_description") if data else None) or (user_message if not data else "")).lower()
        rules: list[tuple[tuple[str, ...], str]] = [
            (("network", "timeout", "connection", "dns", "vpn", "tcp", "packet", "502", "503"), "network_issue"),
            (("disk", "storage", "volume", "ebs", "filesystem", "inode", "quota"), "storage_issue"),
            (("deploy", "release", "rollout", "rollback", "build", "pipeline"), "deployment_issue"),
            (("permission", "access denied", "forbidden", "unauthor", "iam", "rbac"), "permission_issue"),
            (("security", "breach", "attack", "vulnerab", "malware", "intrusion", "phishing"), "security_issue"),
            (("slow", "performance", "latency", "cpu", "memory", "throttl", "leak", "queue", "accumulated"), "performance_issue"),
            (("null", "duplicate", "missing data", "invalid data", "corrupt", "schema", "skipped", "backfill"), "data_quality_issue"),
        ]
        for kws, cat in rules:
            for kw in kws:
                if kw in text:
                    return json.dumps({"category": cat, "reason": f"keyword '{kw}'"})
        return json.dumps({"category": "unknown", "reason": "no matching keyword"})

    @classmethod
    def _mock_severity(cls, user_message: str) -> str:
        data = cls._safe_load(user_message)
        if data:
            text = (data.get("issue_description") or "").lower()
            priority = (data.get("priority") or "").lower()
        else:
            text = user_message.lower()
            priority = ""
        if any(k in text for k in ("outage", "down", "critical", "urgent", "p0")) or priority in ("p1", "critical"):
            sev, sent, conf, reason = 5, -0.9, 0.85, "critical keywords detected"
        elif any(k in text for k in ("failed", "error", "broken", "502", "503")) or priority == "high":
            sev, sent, conf, reason = 4, -0.6, 0.8, "error keywords detected"
        elif any(k in text for k in ("warning", "degraded", "slow", "timed out")) or priority == "medium":
            sev, sent, conf, reason = 3, -0.3, 0.75, "warning keywords detected"
        elif text.strip():
            sev, sent, conf, reason = 2, -0.1, 0.7, "no severe keywords"
        else:
            sev, sent, conf, reason = 1, 0.0, 0.4, "insufficient text"
        return json.dumps(
            {"severity_score": sev, "sentiment_score": sent, "confidence": conf, "reason": reason}
        )

    @classmethod
    def _mock_insights(cls, user_message: str) -> str:
        data = cls._safe_load(user_message)
        cat_counts: dict = data.get("category_counts") or {}
        high_sev = data.get("high_severity_samples") or []
        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
        insights: list[dict] = []
        for cat, count in sorted_cats[:3]:
            insights.append(
                {
                    "title": f"Top category: {cat}",
                    "summary": f"{count} incident(s) classified as {cat}.",
                    "evidence": [f"{cat}: {count}"],
                    "recommendation": (
                        f"Investigate the root cause of {cat} incidents and add proactive monitoring."
                    ),
                }
            )
        if high_sev:
            insights.append(
                {
                    "title": "High severity patterns",
                    "summary": f"{len(high_sev)} incident(s) scored severity >= 4.",
                    "evidence": high_sev[:5],
                    "recommendation": (
                        "Prioritise post-mortems and define escalation paths for high severity tickets."
                    ),
                }
            )
        if not insights:
            insights.append(
                {
                    "title": "No clear pattern detected",
                    "summary": "Insufficient analyzed data to generate insights.",
                    "evidence": [],
                    "recommendation": "Ingest more ticket data and re-run the analysis.",
                }
            )
        return json.dumps({"insights": insights})

    @classmethod
    def _mock_action_items(cls, user_message: str) -> str:
        data = cls._safe_load(user_message)
        insights = data.get("insights") or []
        items: list[dict] = []
        for ins in insights[:5]:
            title = ins.get("title", "Investigate issue")
            rec = ins.get("recommendation", "Review and act on insight.")
            priority = "high" if "high severity" in title.lower() else "medium"
            items.append(
                {
                    "title": f"Action: {title}",
                    "description": rec,
                    "priority": priority,
                    "owner_role": "ops_lead",
                }
            )
        if not items:
            items.append(
                {
                    "title": "Review incident data quality",
                    "description": "No insights produced; verify ingestion and re-run analysis.",
                    "priority": "low",
                    "owner_role": "data_engineer",
                }
            )
        return json.dumps({"action_items": items})


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
            }
        )
    return citations
