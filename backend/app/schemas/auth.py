from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BootstrapRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1)


class AdminRead(BaseModel):
    # 僅暴露非敏感欄位；password_hash 與 session token_hash 一律不進入回應。
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    is_active: bool
    created_at: datetime


class AuthStatus(BaseModel):
    bootstrap_required: bool


class MessageResponse(BaseModel):
    message: str
