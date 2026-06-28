"""自主 tool-calling RAG agent。

與固定流程的 run_rag_chat 不同，這裡讓 LLM 自己決定：要不要查、查什麼、查幾次、
用哪種檢索策略（hybrid/keyword/vector），最後再作答。程式只負責執行 LLM 要求的工具、
聚合引用、翻譯，並以 settings.agent_max_steps 作步數上限避免無限迴圈。
決策軌跡沿用既有 AgentRun / ToolCall，回應 shape 與 /chat 一致。
"""
from __future__ import annotations

import re
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentRun, ToolCall
from app.models.project import Project
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.llm_service import (
    AgentToolCall,
    detect_language,
    format_citations,
    get_llm_provider,
    to_traditional,
    translate_snippet,
)

# 純閒聊／問候才允許不檢索；含疑問或技術詞、或較長的輸入一律視為需檢索（偏向接地）。
_CHITCHAT_TOKENS = (
    "你好", "哈囉", "嗨", "hi", "hello", "早安", "午安", "晚安",
    "謝謝", "thanks", "thank you", "你是誰", "who are you", "掰掰", "bye", "再見",
)
_QUESTION_HINTS = (
    "?", "？", "如何", "怎麼", "怎樣", "什麼", "為什麼", "哪", "步驟", "設定",
    "錯誤", "how", "what", "why", "when", "where", "which", "error", "config",
)


def _is_chitchat(text: str) -> bool:
    """是否為純閒聊／問候（可不檢索）。偏保守：含疑問/技術詞或較長輸入一律回 False。"""
    q = text.strip().lower()
    if not q:
        return False
    if any(h in q for h in _QUESTION_HINTS):
        return False
    if len(q) > 16:
        return False
    return any(t in q for t in _CHITCHAT_TOKENS)
from app.services.retrieval import get_retrieval_service

_VALID_STRATEGIES = ("hybrid", "keyword", "vector")
_MAX_CITATIONS = 10  # agent 可能多次檢索，引用去重後最多回傳這麼多筆

_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_documents",
        "description": (
            "Search the project's knowledge base for relevant document chunks. "
            "Call this when you need facts from the documents to answer. "
            "Break multi-part questions into several focused calls. "
            "Do NOT call it for greetings or meta questions you can answer directly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "strategy": {
                    "type": "string",
                    "enum": list(_VALID_STRATEGIES),
                    "description": (
                        "hybrid = general questions; "
                        "keyword = exact terms such as error codes, command names, config keys, IDs; "
                        "vector = conceptual or semantic questions."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

_AGENT_SYSTEM_PROMPT = """\
You are an autonomous technical support agent for IT operations.

You have one tool: search_documents(query, strategy). You decide what to search for,
how many times, and which strategy:
- ONLY pure greetings or meta questions ("hi", "who are you") may be answered without
  searching. For EVERY other question you MUST call search_documents at least once
  before answering. Never answer factual or how-to questions from your own prior
  knowledge — the answer must come from the project's documents.
- Factual or how-to questions -> search first, then answer ONLY from the results.
- Exact terms (error codes, command names, config keys, IDs) -> strategy="keyword".
- Conceptual or semantic questions -> strategy="vector". Otherwise -> strategy="hybrid".
- Multi-part questions -> issue several focused search calls.

Rules:
- Respond in the same language as the user's question. For any Chinese question, \
answer in Traditional Chinese (Taiwan), never Simplified Chinese.
- Answer ONLY using information from the search results. Never invent commands, file \
paths, configurations, or procedures.
- If the results do not contain the answer, say exactly: "The document does not contain \
enough information to answer this question."
- Stop searching once you have enough to answer.
"""


def _format_search_results(hits: list[dict]) -> str:
    """把檢索結果整理成餵回 LLM 的文字（編號 + 檔名 + 內容）。"""
    if not hits:
        return "(no results)"
    parts = []
    for i, hit in enumerate(hits, 1):
        meta = hit.get("metadata", {})
        parts.append(
            f"[{i}] {meta.get('filename', 'unknown')} (chunk {meta.get('chunk_index', '?')}):\n"
            f"{hit.get('content', '')}"
        )
    return "\n\n---\n\n".join(parts)


def _accumulate_usage(total: dict, usage: dict) -> None:
    total["prompt_tokens"] = total.get("prompt_tokens", 0) + (usage.get("prompt_tokens") or 0)
    total["completion_tokens"] = total.get("completion_tokens", 0) + (usage.get("completion_tokens") or 0)


def run_agent_chat(project_id: uuid.UUID, body: ChatRequest, db: Session) -> ChatResponse:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    total_start = time.monotonic()
    retrieval = get_retrieval_service(db_session=db)
    llm = get_llm_provider()

    # 弱模型（如 qwen2.5:3b）容易忽略埋在長提示詞中間的語言規則，故依提問語言
    # 用程式判斷後，把強制語言指令硬插到 system prompt 最前面、且用目標語言書寫。
    system_content = _AGENT_SYSTEM_PROMPT
    if detect_language(body.question) == "zh":
        system_content = (
            "最高優先規則：使用者以中文提問，你必須全程使用「繁體中文（台灣）」作答，"
            "不得使用英文，也不得使用簡體中文。\n\n"
        ) + _AGENT_SYSTEM_PROMPT

    messages: list[dict] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": body.question},
    ]
    accumulated_hits: dict[str, dict] = {}  # chunk_id -> hit，去重並保留首見順序
    search_records: list[dict] = []         # 每次 search 的 ToolCall 素材
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    answer = ""
    stop_reason = "completed"
    chitchat = _is_chitchat(body.question)  # 純閒聊才允許不檢索
    forced_search = False
    run_status = "success"
    run_error: str | None = None

    try:
        for _ in range(settings.agent_max_steps):
            resp = llm.complete_with_tools(messages, [_SEARCH_TOOL])
            _accumulate_usage(total_usage, resp.usage)

            if not resp.tool_calls:
                # 強制接地：非閒聊卻一次都沒查 → 程式強制檢索一次再讓模型基於文件重答，
                # 不讓 agent「覺得自己會」就略過文件、答得沒有出處。
                if not search_records and not chitchat and not forced_search:
                    forced_search = True
                    forced_tc = AgentToolCall(
                        id="forced-search",
                        name="search_documents",
                        arguments={"query": body.question, "strategy": "hybrid"},
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {"id": forced_tc.id, "name": forced_tc.name, "arguments": forced_tc.arguments}
                            ],
                        }
                    )
                    content, record, hits = _execute_tool(
                        retrieval, str(project_id), forced_tc, body.top_k
                    )
                    messages.append(
                        {"role": "tool", "tool_call_id": forced_tc.id, "name": forced_tc.name, "content": content}
                    )
                    if record is not None:
                        search_records.append(record)
                    for hit in hits:
                        accumulated_hits.setdefault(hit["chunk_id"], hit)
                    continue
                answer = resp.content or ""
                break

            messages.append(
                {
                    "role": "assistant",
                    "content": resp.content,
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in resp.tool_calls
                    ],
                }
            )
            for tc in resp.tool_calls:
                content, record, hits = _execute_tool(retrieval, str(project_id), tc, body.top_k)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "name": tc.name, "content": content}
                )
                if record is not None:
                    search_records.append(record)
                for hit in hits:
                    accumulated_hits.setdefault(hit["chunk_id"], hit)
        else:
            # 步數用盡仍想繼續查 -> 強制收尾：要求只用已取得結果作答，忽略後續工具請求。
            stop_reason = "max_steps"
            messages.append(
                {
                    "role": "user",
                    "content": "You have reached the search limit. Answer now using only the "
                    "search results gathered so far.",
                }
            )
            final = llm.complete_with_tools(messages, [_SEARCH_TOOL])
            _accumulate_usage(total_usage, final.usage)
            answer = final.content or ""
    except RuntimeError as exc:
        # provider 連線/模型問題（含未支援 tool-calling）：先記錄 AgentRun 失敗 + 已蒐集的
        # 檢索軌跡（可觀測性），再對外 500，與 /chat 的稽核行為一致。
        run_status = "error"
        run_error = str(exc)

    total_ms = int((time.monotonic() - total_start) * 1000)
    query_language = detect_language(body.question)
    translated_count = 0
    translate_failed = 0
    cross_lingual: list[dict] = []
    citations: list[Citation] = []

    # 僅在成功時整理答案與引用翻譯；provider 失敗時保留已蒐集軌跡，不再呼叫已壞的 LLM。
    if run_status == "success":
        if not answer.strip():
            answer = "The document does not contain enough information to answer this question."
        answer = to_traditional(answer)  # 小模型常輸出簡體 → 統一轉繁體（台灣）

        # 引用聚合：跨多次檢索去重後取前 N 筆，再對跨語的 snippet 翻成提問語言。
        citation_dicts = format_citations(list(accumulated_hits.values())[:_MAX_CITATIONS])
        cross_lingual = [c for c in citation_dicts if c["snippet"] and c["source_language"] != query_language]
        for citation in cross_lingual:
            try:
                citation["snippet_translated"] = translate_snippet(citation["snippet"], query_language, provider=llm)
                translated_count += 1
            except Exception:
                translate_failed += 1
        citations = [Citation(**c) for c in citation_dicts]

    agent_run_id = uuid.uuid4()
    db.add(
        AgentRun(
            id=agent_run_id,
            project_id=project_id,
            task_type="agent_chat",
            model_name=settings.effective_llm_model,
            input_json={"question": body.question, "top_k": body.top_k},
            output_json={
                "answer": answer,
                "citation_count": len(citations),
                "search_count": len(search_records),
                "stop_reason": stop_reason,
                **total_usage,
            },
            status=run_status,
            latency_ms=total_ms,
            error_message=run_error,
        )
    )
    for record in search_records:
        db.add(
            ToolCall(
                agent_run_id=agent_run_id,
                tool_name="search_documents",
                input_json=record["input"],
                output_json=record["output"],
                latency_ms=record["latency_ms"],
            )
        )
    if cross_lingual:
        db.add(
            ToolCall(
                agent_run_id=agent_run_id,
                tool_name="translate",
                input_json={"target_language": query_language, "candidate_count": len(cross_lingual)},
                output_json={
                    "status": "fallback" if translate_failed else "success",
                    "translated": translated_count,
                    "failed": translate_failed,
                },
            )
        )
    db.commit()

    if run_status == "error":
        # 軌跡已落地，再對外回 500（與 /chat 一致）。
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=run_error or "agent provider error",
        )

    return ChatResponse(answer=answer, citations=citations)


def _execute_tool(
    retrieval, project_id: str, tool_call, top_k: int
) -> tuple[str, dict | None, list[dict]]:
    """執行 LLM 要求的工具，回 (餵回 LLM 的文字, ToolCall 素材或 None, 命中 hits)。"""
    if tool_call.name != "search_documents":
        return f"(error: unknown tool '{tool_call.name}')", None, []

    args = tool_call.arguments or {}
    query = (args.get("query") or "").strip()
    strategy = args.get("strategy") or "hybrid"
    if strategy not in _VALID_STRATEGIES:
        strategy = "hybrid"
    if not query:
        return "(no results)", None, []

    start = time.monotonic()
    hits, breakdown = retrieval.search(project_id, query, top_k=top_k, strategy=strategy)
    latency_ms = int((time.monotonic() - start) * 1000)

    record = {
        "input": {"query": query, "strategy": strategy, "top_k": top_k, "project_id": project_id},
        "output": {**breakdown, "hit_count": len(hits), "chunk_ids": [h["chunk_id"] for h in hits]},
        "latency_ms": latency_ms,
    }
    return _format_search_results(hits), record, hits
