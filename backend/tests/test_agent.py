"""
自主 tool-calling agent（/agent-chat）測試。

驗證 agent 的決策行為（要不要查 / 查什麼 strategy / 查幾次）與安全上限，
以及引用聚合、跨語翻譯、AgentRun/ToolCall 軌跡。
- 用真實 MockLLMProvider 驗證確定性決策（閒聊不查、factual 走 hybrid、精確詞走 keyword）。
- 用 scripted provider 驗證多子查詢、步數上限這類需要精確編排的情境。
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.models.agent import AgentRun, ToolCall
from app.schemas.chat import ChatRequest
from app.services.agent_service import run_agent_chat
from app.services.llm_service import AgentLLMResponse, AgentToolCall, MockLLMProvider

_NOW = datetime.now(timezone.utc)


class _FakeProject:
    def __init__(self, project_id: uuid.UUID) -> None:
        self.id = project_id
        self.name = "Test Project"
        self.created_at = _NOW
        self.updated_at = _NOW


def _hit(chunk_id: str, content: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "content": content,
        "metadata": {
            "document_id": "d1",
            "chunk_id": chunk_id,
            "filename": "sop.pdf",
            "chunk_index": 1,
        },
        "source": "vector",
    }


def _breakdown(hits: list[dict], mode: str = "hybrid") -> dict:
    return {
        "mode": mode,
        "vector_hit_count": len(hits),
        "keyword_hit_count": 0,
        "fused_hit_count": len(hits),
    }


def _make_db(project_id: uuid.UUID) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _FakeProject(project_id)
    return db


def _tool_calls(db: MagicMock) -> list[ToolCall]:
    return [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], ToolCall)]


def _agent_run(db: MagicMock) -> AgentRun:
    return next(c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], AgentRun))


class _ScriptedProvider:
    """依序回傳預先編排的 AgentLLMResponse，用來精確控制 agent 迴圈走向。"""

    def __init__(self, responses: list[AgentLLMResponse]) -> None:
        self._responses = list(responses)
        self.tool_messages_seen: list[list[dict]] = []

    def complete_with_tools(self, messages, tools):
        self.tool_messages_seen.append(messages)
        return self._responses.pop(0)

    def complete(self, system_prompt, user_message):
        # 供 translate_snippet 重用：直接 passthrough。
        return user_message, {}


# ─────────────────────────────────────────────────────────────
# 確定性 MockLLMProvider 決策
# ─────────────────────────────────────────────────────────────

def test_agent_chitchat_answers_without_searching() -> None:
    # 閒聊/問候 → 不呼叫檢索，直接作答；不記 search ToolCall。
    project_id = uuid.uuid4()
    db = _make_db(project_id)

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=MockLLMProvider()):
        response = run_agent_chat(project_id, ChatRequest(question="你好", top_k=5), db)

    mock_retrieval.return_value.search.assert_not_called()
    assert response.citations == []
    assert _tool_calls(db) == []
    assert _agent_run(db).output_json["search_count"] == 0


def test_agent_factual_question_searches_once_with_hybrid() -> None:
    # 一般 how-to 問題 → 呼叫一次 search_documents(hybrid)，再依結果作答。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    hits = [_hit("c1", "Restart with: systemctl restart myapp.")]

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=MockLLMProvider()):
        mock_retrieval.return_value.search.return_value = (hits, _breakdown(hits))
        response = run_agent_chat(project_id, ChatRequest(question="how do I restart the service?", top_k=5), db)

    assert mock_retrieval.return_value.search.call_args.kwargs["strategy"] == "hybrid"
    assert mock_retrieval.return_value.search.call_args.kwargs["top_k"] == 5
    tool_calls = _tool_calls(db)
    assert [t.tool_name for t in tool_calls] == ["search_documents"]
    assert tool_calls[0].input_json["strategy"] == "hybrid"
    assert tool_calls[0].output_json["chunk_ids"] == ["c1"]
    assert response.citations[0].chunk_id == "c1"
    assert _agent_run(db).output_json["stop_reason"] == "completed"


def test_agent_exact_term_routes_to_keyword_strategy() -> None:
    # 精確詞（錯誤碼）→ strategy=keyword。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    hits = [_hit("c1", "ORA-12154: TNS could not resolve the connect identifier.")]

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=MockLLMProvider()):
        mock_retrieval.return_value.search.return_value = (hits, _breakdown(hits, "keyword"))
        run_agent_chat(project_id, ChatRequest(question="what causes ORA-12154?", top_k=5), db)

    assert mock_retrieval.return_value.search.call_args.kwargs["strategy"] == "keyword"


# ─────────────────────────────────────────────────────────────
# Scripted provider：多子查詢、步數上限、向量策略
# ─────────────────────────────────────────────────────────────

def test_agent_decomposes_into_multiple_searches_and_dedupes_citations() -> None:
    # 多子查詢：一輪內發兩個 search 呼叫（不同 query），引用跨呼叫去重。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    provider = _ScriptedProvider([
        AgentLLMResponse(content=None, tool_calls=[
            AgentToolCall("call_0", "search_documents", {"query": "backup", "strategy": "vector"}),
            AgentToolCall("call_1", "search_documents", {"query": "restore", "strategy": "keyword"}),
        ]),
        AgentLLMResponse(content="先備份再還原。", tool_calls=[]),
    ])

    def _search(project, query, top_k, strategy):
        if query == "backup":
            return ([_hit("shared", "backup steps"), _hit("c-backup", "more backup")], _breakdown([], strategy))
        return ([_hit("shared", "backup steps"), _hit("c-restore", "restore steps")], _breakdown([], strategy))

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=provider):
        mock_retrieval.return_value.search.side_effect = _search
        response = run_agent_chat(project_id, ChatRequest(question="如何備份與還原?", top_k=5), db)

    search_calls = [t for t in _tool_calls(db) if t.tool_name == "search_documents"]
    assert len(search_calls) == 2
    assert {t.input_json["strategy"] for t in search_calls} == {"vector", "keyword"}
    # shared chunk 去重 → 三個唯一引用
    assert sorted(c.chunk_id for c in response.citations) == ["c-backup", "c-restore", "shared"]
    assert _agent_run(db).output_json["search_count"] == 2


def test_agent_respects_max_steps_safety_cap() -> None:
    # LLM 一直想查 → 程式以 agent_max_steps 截斷，強制收尾並標記 stop_reason。
    project_id = uuid.uuid4()
    db = _make_db(project_id)

    class _AlwaysSearch:
        def complete_with_tools(self, messages, tools):
            return AgentLLMResponse(
                content=None,
                tool_calls=[AgentToolCall("c", "search_documents", {"query": "q", "strategy": "hybrid"})],
            )

        def complete(self, system_prompt, user_message):
            return user_message, {}

    with patch.object(settings, "agent_max_steps", 3), \
         patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=_AlwaysSearch()):
        mock_retrieval.return_value.search.return_value = ([_hit("c1", "x")], _breakdown([]))
        response = run_agent_chat(project_id, ChatRequest(question="never satisfied", top_k=5), db)

    search_calls = [t for t in _tool_calls(db) if t.tool_name == "search_documents"]
    assert len(search_calls) == 3  # == agent_max_steps，未爆衝
    assert _agent_run(db).output_json["stop_reason"] == "max_steps"
    assert "does not contain enough information" in response.answer


def test_agent_translates_cross_lingual_citation() -> None:
    # 中文提問 + 英文原文 → citation 帶翻譯，並記 translate ToolCall。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    provider = _ScriptedProvider([
        AgentLLMResponse(content=None, tool_calls=[
            AgentToolCall("call_0", "search_documents", {"query": "restart", "strategy": "hybrid"}),
        ]),
        AgentLLMResponse(content="使用 systemctl 重啟。", tool_calls=[]),
    ])
    hits = [_hit("c1", "Restart the service with systemctl restart myapp.")]

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=provider):
        mock_retrieval.return_value.search.return_value = (hits, _breakdown(hits))
        response = run_agent_chat(project_id, ChatRequest(question="如何重啟服務?", top_k=5), db)

    c = response.citations[0]
    assert c.source_language == "en"
    assert c.snippet_translated == c.snippet  # scripted provider 翻譯為 passthrough
    assert "translate" in [t.tool_name for t in _tool_calls(db)]


def test_agent_project_not_found_raises_404() -> None:
    from fastapi import HTTPException

    project_id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.services.agent_service.get_llm_provider", return_value=MockLLMProvider()):
        try:
            run_agent_chat(project_id, ChatRequest(question="hi", top_k=5), db)
            assert False, "should have raised"
        except HTTPException as exc:
            assert exc.status_code == 404


def test_agent_provider_failure_is_audited_before_500() -> None:
    # provider 中途壞掉：仍須落地 AgentRun(status=error) + 已蒐集的 search 軌跡，再回 500。
    # 否則這類失敗不進稽核，可觀測性會有破口。
    from fastapi import HTTPException

    project_id = uuid.uuid4()
    db = _make_db(project_id)

    class _FailAfterSearch:
        def __init__(self) -> None:
            self._calls = 0

        def complete_with_tools(self, messages, tools):
            self._calls += 1
            if self._calls == 1:
                return AgentLLMResponse(content=None, tool_calls=[
                    AgentToolCall("c0", "search_documents", {"query": "q", "strategy": "hybrid"}),
                ])
            raise RuntimeError("ollama connection refused")

        def complete(self, system_prompt, user_message):
            return user_message, {}

    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=_FailAfterSearch()):
        mock_retrieval.return_value.search.return_value = ([_hit("c1", "x")], _breakdown([]))
        try:
            run_agent_chat(project_id, ChatRequest(question="how do I restart?", top_k=5), db)
            assert False, "should have raised 500"
        except HTTPException as exc:
            assert exc.status_code == 500

    run = _agent_run(db)
    assert run.status == "error"
    assert "ollama connection refused" in (run.error_message or "")
    # 失敗前已完成的檢索仍記入軌跡。
    assert [t.tool_name for t in _tool_calls(db)] == ["search_documents"]
    db.commit.assert_called_once()


def test_agent_run_records_ollama_model_name() -> None:
    # Ollama 模式的稽核 model_name 必須是 ollama_model，不能誤記成 openai 的 llm_model。
    project_id = uuid.uuid4()
    db = _make_db(project_id)

    with patch.object(settings, "llm_provider", "ollama"), \
         patch.object(settings, "ollama_model", "qwen2.5:7b-instruct"), \
         patch("app.services.agent_service.get_retrieval_service"), \
         patch("app.services.agent_service.get_llm_provider", return_value=MockLLMProvider()):
        run_agent_chat(project_id, ChatRequest(question="你好", top_k=5), db)

    assert _agent_run(db).model_name == "qwen2.5:7b-instruct"


# ─────────────────────────────────────────────────────────────
# 強制接地：非閒聊不得跳過檢索
# ─────────────────────────────────────────────────────────────

def test_agent_forces_retrieval_when_model_skips_for_non_chitchat() -> None:
    # 模型第一輪想直接作答（未呼叫工具）但問題非閒聊 → 程式強制檢索一次再讓它基於文件重答。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    provider = _ScriptedProvider([
        AgentLLMResponse(content="我直接回答（未檢索）", tool_calls=[]),
        AgentLLMResponse(content="根據文件：systemctl restart nginx", tool_calls=[]),
    ])
    hits = [_hit("c1", "Restart nginx with systemctl restart nginx.")]

    with patch.object(settings, "agent_max_steps", 5), \
         patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=provider):
        mock_retrieval.return_value.search.return_value = (hits, _breakdown(hits))
        response = run_agent_chat(project_id, ChatRequest(question="如何重啟 nginx 服務？", top_k=3), db)

    # 程式強制檢索（query=原問題, strategy=hybrid），引用接地、答案來自文件
    assert mock_retrieval.return_value.search.call_args.kwargs["strategy"] == "hybrid"
    search_calls = [t for t in _tool_calls(db) if t.tool_name == "search_documents"]
    assert len(search_calls) == 1
    assert search_calls[0].input_json["query"] == "如何重啟 nginx 服務？"
    assert [c.chunk_id for c in response.citations] == ["c1"]
    assert "systemctl" in response.answer
    assert _agent_run(db).output_json["search_count"] == 1


def test_agent_chitchat_still_skips_retrieval() -> None:
    # 純閒聊 → 不強制檢索（沿用既有行為）。
    project_id = uuid.uuid4()
    db = _make_db(project_id)
    provider = _ScriptedProvider([
        AgentLLMResponse(content="你好！我是維運助理。", tool_calls=[]),
    ])
    with patch("app.services.agent_service.get_retrieval_service") as mock_retrieval, \
         patch("app.services.agent_service.get_llm_provider", return_value=provider):
        run_agent_chat(project_id, ChatRequest(question="你好", top_k=3), db)

    mock_retrieval.return_value.search.assert_not_called()
    assert [t.tool_name for t in _tool_calls(db)] == []
