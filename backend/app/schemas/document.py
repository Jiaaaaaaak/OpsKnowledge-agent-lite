from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    project_id: UUID
    filename: str
    document_type: str
    source_path: str
    metadata: dict = Field(default_factory=dict)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    filename: str
    document_type: str
    source_path: str
    created_at: datetime
    updated_at: datetime


class DocumentChunkCreate(BaseModel):
    document_id: UUID
    chunk_index: int
    content: str
    metadata: dict = Field(default_factory=dict)


class DocumentChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    created_at: datetime
