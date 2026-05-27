from sqlalchemy import Boolean, Column, ForeignKey, Index, Numeric, Text, VARCHAR
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class IncidentAnalysis(PKMixin, TimestampMixin, Base):
    __tablename__ = "incident_analysis"
    __table_args__ = (
        Index("idx_incident_analysis_project_id", "project_id"),
        Index("idx_incident_analysis_record_id", "record_id"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    record_id = Column(UUID(as_uuid=True), ForeignKey("cleaned_records.id", ondelete="CASCADE"), nullable=False)
    category = Column(VARCHAR(255), nullable=False)
    severity_score = Column(Numeric(5, 4), nullable=False)
    sentiment_score = Column(Numeric(5, 4), nullable=False)
    confidence = Column(Numeric(5, 4), nullable=False)
    needs_review = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=False)

    project = relationship("Project", back_populates="incident_analyses")
    record = relationship("CleanedRecord", back_populates="analysis")


class Insight(PKMixin, TimestampMixin, Base):
    __tablename__ = "insights"
    __table_args__ = (
        Index("idx_insights_project_id", "project_id"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(VARCHAR(500), nullable=False)
    summary = Column(Text, nullable=False)
    evidence = Column(JSONB, nullable=False, default=list)
    recommendation = Column(Text, nullable=False)

    project = relationship("Project", back_populates="insights")


class ActionItem(PKMixin, TimestampMixin, Base):
    __tablename__ = "action_items"
    __table_args__ = (
        Index("idx_action_items_project_id", "project_id"),
        Index("idx_action_items_status", "status"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title = Column(VARCHAR(500), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(VARCHAR(50), nullable=False)
    owner_role = Column(VARCHAR(255), nullable=False)
    status = Column(VARCHAR(100), nullable=False, default="pending")

    project = relationship("Project", back_populates="action_items")
