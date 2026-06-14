from sqlalchemy import Column, ForeignKey, Index, Integer, Text, VARCHAR
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class AgentRun(PKMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_project_id", "project_id"),
        Index("idx_agent_runs_created_at", "created_at"),
        Index("idx_agent_runs_status", "status"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    task_type = Column(VARCHAR(255), nullable=False)
    model_name = Column(VARCHAR(255), nullable=False)
    input_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)
    status = Column(VARCHAR(50), nullable=False)
    latency_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    project = relationship("Project", back_populates="agent_runs")
    tool_calls = relationship("ToolCall", back_populates="agent_run", cascade="all, delete-orphan")
    insights = relationship("Insight", back_populates="agent_run")
    action_items = relationship("ActionItem", back_populates="agent_run")


class ToolCall(PKMixin, TimestampMixin, Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("idx_tool_calls_agent_run_id", "agent_run_id"),
    )

    agent_run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    tool_name = Column(VARCHAR(255), nullable=False)
    input_json = Column(JSONB, nullable=False, default=dict)
    output_json = Column(JSONB, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    agent_run = relationship("AgentRun", back_populates="tool_calls")
