from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRunCreate(BaseModel):
    project_id: UUID | None = None
    task_type: str
    model_name: str
    input_json: dict = Field(default_factory=dict)
    output_json: dict = Field(default_factory=dict)
    status: str
    latency_ms: int | None = None
    error_message: str | None = None


class AgentRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID | None
    task_type: str
    model_name: str
    input_json: dict
    output_json: dict
    status: str
    latency_ms: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ToolCallCreate(BaseModel):
    agent_run_id: UUID
    tool_name: str
    input_json: dict = Field(default_factory=dict)
    output_json: dict = Field(default_factory=dict)
    error_message: str | None = None
    latency_ms: int | None = None


class ToolCallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_run_id: UUID
    tool_name: str
    input_json: dict
    output_json: dict
    error_message: str | None
    latency_ms: int | None
    created_at: datetime
