from sqlalchemy import Column, Text, VARCHAR
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class Project(PKMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name = Column(VARCHAR(255), nullable=False)
    description = Column(Text, nullable=True)

    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="project", cascade="all, delete-orphan")
