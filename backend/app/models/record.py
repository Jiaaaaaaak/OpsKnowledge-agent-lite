from sqlalchemy import Column, DateTime, ForeignKey, Index, Text, VARCHAR
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class RawRecord(PKMixin, TimestampMixin, Base):
    __tablename__ = "raw_records"
    __table_args__ = (
        Index("idx_raw_records_project_id", "project_id"),
        Index("idx_raw_records_created_at", "created_at"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    source_file = Column(VARCHAR(255), nullable=False)
    raw_json = Column(JSONB, nullable=False, default=dict)

    project = relationship("Project", back_populates="raw_records")


class CleanedRecord(PKMixin, TimestampMixin, Base):
    __tablename__ = "cleaned_records"
    __table_args__ = (
        Index("idx_cleaned_records_project_id", "project_id"),
        Index("idx_cleaned_records_created_at", "created_at"),
        Index("idx_cleaned_records_status", "status"),
        Index("idx_cleaned_records_priority", "priority"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    ticket_id = Column(VARCHAR(255), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    system = Column(VARCHAR(255), nullable=False)
    module = Column(VARCHAR(255), nullable=False)
    issue_description = Column(Text, nullable=False)
    resolution = Column(Text, nullable=True)
    status = Column(VARCHAR(100), nullable=False)
    priority = Column(VARCHAR(50), nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)

    project = relationship("Project", back_populates="cleaned_records")
    analysis = relationship("IncidentAnalysis", back_populates="record", uselist=False)
