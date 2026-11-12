"""Caption stored next to the cached file_ids.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("media_cache", sa.Column("caption", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("media_cache", "caption")
