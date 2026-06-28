from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Text, VARCHAR
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.models.base import PKMixin, TimestampMixin


class Administrator(PKMixin, TimestampMixin, Base):
    __tablename__ = "administrators"

    username = Column(VARCHAR(100), nullable=False, unique=True)
    password_hash = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    sessions = relationship(
        "AdminSession",
        back_populates="administrator",
        cascade="all, delete-orphan",
    )


class AdminSession(PKMixin, TimestampMixin, Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (Index("idx_admin_sessions_expires_at", "expires_at"),)

    administrator_id = Column(
        UUID(as_uuid=True),
        ForeignKey("administrators.id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash = Column(VARCHAR(64), nullable=False, unique=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    administrator = relationship("Administrator", back_populates="sessions")
