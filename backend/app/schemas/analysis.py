from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IncidentAnalysisCreate(BaseModel):
    project_id: UUID
    record_id: UUID
    category: str
    severity_score: Decimal
    sentiment_score: Decimal
    confidence: Decimal
    needs_review: bool = False
    reason: str


class IncidentAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    record_id: UUID
    category: str
    severity_score: Decimal
    sentiment_score: Decimal
    confidence: Decimal
    needs_review: bool
    reason: str
    created_at: datetime
    updated_at: datetime


class InsightCreate(BaseModel):
    project_id: UUID
    agent_run_id: UUID | None = None
    title: str
    summary: str
    evidence: list = Field(default_factory=list)
    recommendation: str


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_run_id: UUID | None
    title: str
    summary: str
    evidence: list
    recommendation: str
    created_at: datetime
    updated_at: datetime


class ActionItemCreate(BaseModel):
    project_id: UUID
    agent_run_id: UUID | None = None
    title: str
    description: str
    priority: str
    owner_role: str
    status: str = "pending"


class ActionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    agent_run_id: UUID | None
    title: str
    description: str
    priority: str
    owner_role: str
    status: str
    created_at: datetime
    updated_at: datetime
