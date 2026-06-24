"""自主 tool-calling RAG agent。

與固定流程的 run_rag_chat 不同，這裡讓 LLM 自己決定：要不要查、查什麼、查幾次、
用哪種檢索策略（hybrid/keyword/vector），最後再作答。程式只負責執行 LLM 要求的工具、
聚合引用、翻譯，並以 settings.agent_max_steps 作步數上限避免無限迴圈。
決策軌跡沿用既有 AgentRun / ToolCall，回應 shape 與 /chat 一致。
"""
from __future__ import annotations

import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent import AgentRun, ToolCall
from app.models.project import Project
from app.schemas.chat import ChatRequest, ChatResponse, Citation
from app.services.llm_service import (
    detect_language,
    format_citations,
    get_llm_provider,
    translate_snippet,
)
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

You have one tool: search_documents(query, strategy). You decide whether to use it,
what to search for, how many times, and which strategy:
- Greetings or meta questions ("who are you") -> answer directly, do NOT search.
- Factual or how-to questions -> search first, then answer ONLY from the results.
- Exact terms (error codes, command names, config keys, IDs) -> strategy="keyword".
- Conceptual or semantic questions -> strategy="vector". Otherwise -> strategy="hybrid".
- Multi-part questions -> issue several focused search calls.

Rules:
- Respond in the same language as the user's question.
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

    messages: list[dict] = [
        {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
        {"role": "user", "content": body.question},
    ]
    accumulated_hits: dict[str, dict] = {}  # chunk_id -> hit，去重並保留首見順序
    search_records: list[dict] = []         # 每次 search 的 ToolCall 素材
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    answer = ""
    stop_reason = "completed"

    try:
        for _ in range(settings.agent_max_steps):
            resp = llm.complete_with_tools(messages, [_SEARCH_TOOL])
            _accumulate_usage(total_usage, resp.usage)

            if not resp.tool_calls:
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
        # provider 連線/模型問題（含未支援 tool-calling）-> 對外 500，與 /chat 一致。
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    if not answer.strip():
        answer = "The document does not contain enough information to answer this question."

    total_ms = int((time.monotonic() - total_start) * 1000)

    # 引用聚合：跨多次檢索去重後取前 N 筆，再對跨語的 snippet 翻成提問語言。
    citation_dicts = format_citations(list(accumulated_hits.values())[:_MAX_CITATIONS])
    query_language = detect_language(body.question)
    translated_count = 0
    translate_failed = 0
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
            model_name="mock" if settings.llm_provider == "mock" else settings.llm_model,
            input_json={"question": body.question, "top_k": body.top_k},
            output_json={
                "answer": answer,
                "citation_count": len(citations),
                "search_count": len(search_records),
                "stop_reason": stop_reason,
                **total_usage,
            },
            status="success",
            latency_ms=total_ms,
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
