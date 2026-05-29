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


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
