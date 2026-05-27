import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import UUID


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PKMixin:
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)
