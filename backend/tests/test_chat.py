"""
chat 端點測試
涵蓋：build_rag_prompt prompt 建構、format_citations 引用格式化、
      POST /projects/{id}/chat 端點（mocked VectorStore + mocked LLM）
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.llm_service import build_rag_prompt, format_citations

_NOW = datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────
# build_rag_prompt
# ─────────────────────────────────────────────────────────────

class TestBuildRagPrompt:

    def test_empty_chunks_inserts_no_context_placeholder(self):
        prompt = build_rag_prompt([])
        assert "(no context retrieved)" in prompt

    def test_prompt_contains_hallucination_guard(self):
        # 模型不得捏造文件中未提及的操作步驟
        prompt = build_rag_prompt([])
        assert "Never invent" in prompt

    def test_prompt_contains_insufficient_context_instruction(self):
        # 若 context 不足，模型須以固定措辭回應
        prompt = build_rag_prompt([])
        assert "does not contain enough information" in prompt

    def test_single_chunk_numbered_correctly(self):
        chunks = [
            {
                "chunk_id": "c1",
                "content": "Restart the service with systemctl restart myapp.",
                "metadata": {"filename": "sop.pdf", "chunk_index": 3},
            }
        ]
        prompt = build_rag_prompt(chunks)
        assert "[1] sop.pdf (chunk 3)" in prompt
        assert "Restart the service with systemctl restart myapp." in prompt

    def test_multiple_chunks_numbered_sequentially(self):
        chunks = [
            {"chunk_id": "c1", "content": "first", "metadata": {"filename": "a.pdf", "chunk_index": 0}},
            {"chunk_id": "c2", "content": "second", "metadata": {"filename": "b.pdf", "chunk_index": 1}},
            {"chunk_id": "c3", "content": "third", "metadata": {"filename": "c.pdf", "chunk_index": 2}},
        ]
        prompt = build_rag_prompt(chunks)
        assert "[1] a.pdf" in prompt
        assert "[2] b.pdf" in prompt
        assert "[3] c.pdf" in prompt

    def test_missing_metadata_uses_defaults(self):
        chunks = [{"chunk_id": "c1", "content": "text", "metadata": {}}]
        prompt = build_rag_prompt(chunks)
        assert "[1] unknown (chunk ?)" in prompt

    def test_context_separates_chunks_with_delimiter(self):
        chunks = [
            {"chunk_id": "c1", "content": "A", "metadata": {"filename": "x.pdf", "chunk_index": 0}},
            {"chunk_id": "c2", "content": "B", "metadata": {"filename": "y.pdf", "chunk_index": 1}},
        ]
        prompt = build_rag_prompt(chunks)
        assert "---" in prompt

    def test_chunk_content_is_embedded_in_prompt(self):
        content = "Docker volumes persist data beyond container lifecycle."
        chunks = [{"chunk_id": "c1", "content": content, "metadata": {"filename": "docker.pdf", "chunk_index": 0}}]
        prompt = build_rag_prompt(chunks)
        assert content in prompt


# ─────────────────────────────────────────────────────────────
# format_citations
# ─────────────────────────────────────────────────────────────

class TestFormatCitations:

    def _make_hit(
        self,
        chunk_id: str = "c1",
        document_id: str = "d1",
        filename: str = "manual.pdf",
        chunk_index: int = 3,
        content: str = "Some content text",
    ) -> dict:
        return {
            "chunk_id": chunk_id,
            "content": content,
            "metadata": {
                "document_id": document_id,
                "chunk_id": chunk_id,
                "filename": filename,
                "chunk_index": chunk_index,
            },
        }

    def test_all_fields_mapped_correctly(self):
        citations = format_citations([self._make_hit()])
        assert len(citations) == 1
        c = citations[0]
        assert c["document_id"] == "d1"
        assert c["chunk_id"] == "c1"
        assert c["filename"] == "manual.pdf"
        assert c["chunk_index"] == 3
        assert c["snippet"] == "Some content text"

    def test_short_content_not_truncated(self):
        c = format_citations([self._make_hit(content="Short text.")])[0]
        assert c["snippet"] == "Short text."
        assert not c["snippet"].endswith("...")

    def test_long_content_truncated_with_ellipsis(self):
        # 超過 200 字元應截斷並加 "..."
        c = format_citations([self._make_hit(content="x" * 300)])[0]
        assert c["snippet"].endswith("...")
        assert len(c["snippet"]) <= 203  # 200 chars + "..."

    def test_exact_200_chars_not_truncated(self):
        c = format_citations([self._make_hit(content="a" * 200)])[0]
        assert not c["snippet"].endswith("...")

    def test_empty_hits_returns_empty_list(self):
        assert format_citations([]) == []

    def test_chunk_index_cast_to_int(self):
        # ChromaDB metadata 有時回傳 float；必須確保最終型別為 int
        hit = self._make_hit()
        hit["metadata"]["chunk_index"] = 7.0
        c = format_citations([hit])[0]
        assert isinstance(c["chunk_index"], int)
        assert c["chunk_index"] == 7

    def test_missing_metadata_fields_use_empty_defaults(self):
        hit = {"chunk_id": "c1", "content": "text", "metadata": {}}
        c = format_citations([hit])[0]
        assert c["document_id"] == ""
        assert c["filename"] == ""
        assert c["chunk_index"] == 0

    def test_multiple_hits_preserve_order(self):
        hits = [
            self._make_hit(chunk_id="c1", filename="first.pdf"),
            self._make_hit(chunk_id="c2", filename="second.pdf"),
        ]
        citations = format_citations(hits)
        assert citations[0]["filename"] == "first.pdf"
        assert citations[1]["filename"] == "second.pdf"


# ─────────────────────────────────────────────────────────────
# POST /projects/{project_id}/chat 端點
# ─────────────────────────────────────────────────────────────

class _FakeProject:
    def __init__(self, project_id: uuid.UUID | None = None) -> None:
        self.id = project_id or uuid.uuid4()
        self.name = "Test Project"
        self.created_at = _NOW
        self.updated_at = _NOW


def _db_override(project: object | None = None):
    def _get_db():
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = project
        yield db
    return _get_db


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


_SAMPLE_HIT = {
    "chunk_id": "c1",
    "content": "To check Docker volume mounts, run: docker inspect <container>.",
    "metadata": {
        "document_id": "d1",
        "chunk_id": "c1",
        "filename": "docker_guide.pdf",
        "chunk_index": 5,
    },
    "distance": 0.1,
    "score": 0.9,
}


def test_chat_returns_answer_and_citations(client: TestClient) -> None:
    project_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override(project=_FakeProject(project_id))

    with patch("app.services.chat_service.get_vector_store") as mock_vs, \
         patch("app.services.chat_service.get_llm_provider") as mock_llm_cls:
        mock_vs.return_value.search.return_value = [_SAMPLE_HIT]
        mock_llm_cls.return_value.complete.return_value = (
            "Run docker inspect to check volume mounts.",
            {"prompt_tokens": 120, "completion_tokens": 20},
        )

        response = client.post(
            f"/projects/{project_id}/chat",
            json={
                "question": "Docker volume data disappeared after container restart. What should I check?",
                "top_k": 5,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Run docker inspect to check volume mounts."
    assert len(data["citations"]) == 1
    c = data["citations"][0]
    assert c["chunk_id"] == "c1"
    assert c["document_id"] == "d1"
    assert c["filename"] == "docker_guide.pdf"
    assert c["chunk_index"] == 5
    assert "docker inspect" in c["snippet"]


def test_chat_writes_agent_run_and_tool_call() -> None:
    from app.services.chat_service import run_rag_chat
    from app.models.agent import AgentRun, ToolCall
    from app.schemas.chat import ChatRequest

    project_id = uuid.uuid4()
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = _FakeProject(project_id)

    with patch("app.services.chat_service.get_vector_store") as mock_vs, \
         patch("app.services.chat_service.get_llm_provider") as mock_llm_cls:
        mock_vs.return_value.search.return_value = [_SAMPLE_HIT]
        mock_llm_cls.return_value.complete.return_value = (
            "Run docker inspect to check volume mounts.",
            {"prompt_tokens": 120, "completion_tokens": 20},
        )

        response = run_rag_chat(
            project_id,
            ChatRequest(question="What should I check?", top_k=5),
            db,
        )

    assert response.answer == "Run docker inspect to check volume mounts."
    added = [call.args[0] for call in db.add.call_args_list]
    agent_run = next(obj for obj in added if isinstance(obj, AgentRun))
    tool_call = next(obj for obj in added if isinstance(obj, ToolCall))

    assert agent_run.project_id == project_id
    assert agent_run.task_type == "rag_chat"
    assert agent_run.status == "success"
    assert agent_run.output_json["citation_count"] == 1
    assert tool_call.agent_run_id == agent_run.id
    assert tool_call.tool_name == "vector_search"
    assert tool_call.output_json["chunk_ids"] == ["c1"]
    db.commit.assert_called_once()


def test_chat_route_delegates_to_service(client: TestClient) -> None:
    from app.api.chat import chat

    project_id = uuid.uuid4()
    db = MagicMock()

    with patch("app.api.chat.run_rag_chat") as mock_service:
        mock_service.return_value = ChatResponse(answer="service answer", citations=[])

        response = chat(project_id, ChatRequest(question="What should I check?", top_k=5), db)

    assert response.answer == "service answer"
    assert response.citations == []
    mock_service.assert_called_once_with(project_id, ChatRequest(question="What should I check?", top_k=5), db)


def test_chat_project_not_found_returns_404(client: TestClient) -> None:
    app.dependency_overrides[get_db] = _db_override(project=None)

    response = client.post(
        f"/projects/{uuid.uuid4()}/chat",
        json={"question": "What is Docker?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


def test_chat_missing_question_returns_422(client: TestClient) -> None:
    response = client.post(f"/projects/{uuid.uuid4()}/chat", json={})
    assert response.status_code == 422


def test_chat_no_hits_returns_answer_without_citations(client: TestClient) -> None:
    project_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override(project=_FakeProject(project_id))

    with patch("app.services.chat_service.get_vector_store") as mock_vs, \
         patch("app.services.chat_service.get_llm_provider") as mock_llm_cls:
        mock_vs.return_value.search.return_value = []
        mock_llm_cls.return_value.complete.return_value = (
            "The document does not contain enough information to answer this question.",
            {},
        )

        response = client.post(
            f"/projects/{project_id}/chat",
            json={"question": "How do I bake a cake?"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["citations"] == []
    assert "does not contain enough information" in data["answer"]


def test_chat_llm_error_returns_500(client: TestClient) -> None:
    project_id = uuid.uuid4()
    app.dependency_overrides[get_db] = _db_override(project=_FakeProject(project_id))

    with patch("app.services.chat_service.get_vector_store") as mock_vs, \
         patch("app.services.chat_service.get_llm_provider") as mock_llm_cls:
        mock_vs.return_value.search.return_value = [_SAMPLE_HIT]
        mock_llm_cls.return_value.complete.side_effect = RuntimeError("API quota exceeded")

        response = client.post(
            f"/projects/{project_id}/chat",
            json={"question": "test question"},
        )

    assert response.status_code == 500
    assert "API quota exceeded" in response.json()["detail"]


def test_chat_top_k_out_of_range_returns_422(client: TestClient) -> None:
    response = client.post(
        f"/projects/{uuid.uuid4()}/chat",
        json={"question": "valid question", "top_k": 100},
    )
    assert response.status_code == 422


def test_chat_invalid_project_uuid_returns_422(client: TestClient) -> None:
    response = client.post(
        "/projects/not-a-uuid/chat",
        json={"question": "valid question"},
    )
    assert response.status_code == 422
