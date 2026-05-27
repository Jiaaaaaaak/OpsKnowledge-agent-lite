from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RawRecordCreate(BaseModel):
    project_id: UUID
    source_file: str
    raw_json: dict = Field(default_factory=dict)


class RawRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_file: str
    raw_json: dict
    created_at: datetime


class CleanedRecordCreate(BaseModel):
    project_id: UUID
    ticket_id: str
    occurred_at: datetime | None = None
    system: str
    module: str
    issue_description: str
    resolution: str | None = None
    status: str
    priority: str
    metadata: dict = Field(default_factory=dict)


class CleanedRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    ticket_id: str
    occurred_at: datetime | None
    system: str
    module: str
    issue_description: str
    resolution: str | None
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
