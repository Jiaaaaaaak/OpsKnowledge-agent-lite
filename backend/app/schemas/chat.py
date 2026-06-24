from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    filename: str
    chunk_index: int
    snippet: str
    # source_language：偵測到的 chunk 原文語言（"zh" / "en"）。
    # snippet_translated：跨語時（chunk 語言 ≠ 使用者提問語言）翻成提問語言的 snippet；
    # 同語言時為 None，前端據此決定是否顯示翻譯。
    source_language: str = ""
    snippet_translated: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
