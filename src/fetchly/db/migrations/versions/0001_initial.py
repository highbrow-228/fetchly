"""Initial schema.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("settings", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_table(
        "media_cache",
        sa.Column("platform", sa.String(16), primary_key=True),
        sa.Column("media_id", sa.String(128), primary_key=True),
        sa.Column("media_type", sa.String(16), nullable=False),
        sa.Column("items", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "link_aliases",
        sa.Column("url", sa.Text, primary_key=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("media_id", sa.String(128), nullable=False),
        sa.ForeignKeyConstraint(
            ["platform", "media_id"],
            ["media_cache.platform", "media_cache.media_id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_link_aliases_media", "link_aliases", ["platform", "media_id"])
    op.create_table(
        "downloads",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            primary_key=True,
            server_default=sa.func.now(),
        ),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("result", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("size_bytes", sa.BigInteger, nullable=False),
        sa.Column("from_cache", sa.Boolean, nullable=False),
        postgresql_partition_by="RANGE (created_at)",
    )
    op.create_index("ix_downloads_chat", "downloads", ["chat_id", "created_at"])
    # Monthly partitions are created by the worker; this one catches anything else.
    op.execute("CREATE TABLE downloads_default PARTITION OF downloads DEFAULT")


def downgrade() -> None:
    op.drop_table("downloads")
    op.drop_table("link_aliases")
    op.drop_table("media_cache")
    op.drop_table("chats")
