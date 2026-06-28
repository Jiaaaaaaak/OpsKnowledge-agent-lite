"""add administrator identity and session tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "administrators",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.VARCHAR(length=100), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_administrators_username"),
    )

    op.create_table(
        "admin_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "administrator_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("token_hash", sa.VARCHAR(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["administrator_id"],
            ["administrators.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_admin_sessions_token_hash"),
    )
    op.create_index(
        "idx_admin_sessions_administrator_id",
        "admin_sessions",
        ["administrator_id"],
        unique=False,
    )
    op.create_index(
        "idx_admin_sessions_expires_at",
        "admin_sessions",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_admin_sessions_expires_at", table_name="admin_sessions")
    op.drop_index("idx_admin_sessions_administrator_id", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_table("administrators")
