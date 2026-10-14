"""Track completed report files.

Revision ID: 20260830_0002
Revises: 20260821_0001
Create Date: 2026-08-30 10:32:40
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0002"
down_revision: str | None = "20260821_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "test_runs",
        sa.Column("source_file_id", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_test_runs_source_file_id",
        "test_runs",
        ["source_file_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_test_runs_source_file_id",
        "test_runs",
        type_="unique",
    )
    op.drop_column("test_runs", "source_file_id")
