from sqlalchemy import Column, ForeignKey, Index, Integer, Text, VARCHAR
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class Document(PKMixin, TimestampMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_project_id", "project_id"),
        Index("idx_documents_created_at", "created_at"),
    )

    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename = Column(VARCHAR(255), nullable=False)
    document_type = Column(VARCHAR(100), nullable=False)
    source_path = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)

    project = relationship("Project", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(PKMixin, TimestampMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("idx_document_chunks_document_id", "document_id"),
    )

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, nullable=False, default=dict)

    document = relationship("Document", back_populates="chunks")
