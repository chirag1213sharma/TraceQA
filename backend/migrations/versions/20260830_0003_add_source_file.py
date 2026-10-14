"""Store the source-relative report path.

Revision ID: 20260830_0003
Revises: 20260830_0002
Create Date: 2026-08-30 10:59:21
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0003"
down_revision: str | None = "20260830_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column("source_file", sa.String(length=2048), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("test_runs", "source_file")
