"""Add structured QA analysis fields.

Revision ID: 20260901_0004
Revises: 20260830_0003
Create Date: 2026-09-01 16:30:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0004"
down_revision: str | None = "20260830_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_test_insights",
        sa.Column("test_name", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("execution_date", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("test_cases_passed", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("test_cases_failed", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column(
            "failed_test_case_list",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("ai_analysis", sa.Text(), nullable=True),
    )
    op.add_column(
        "ai_test_insights",
        sa.Column("insturctions_for_qa", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_test_insights", "insturctions_for_qa")
    op.drop_column("ai_test_insights", "ai_analysis")
    op.drop_column("ai_test_insights", "failed_test_case_list")
    op.drop_column("ai_test_insights", "test_cases_failed")
    op.drop_column("ai_test_insights", "test_cases_passed")
    op.drop_column("ai_test_insights", "status")
    op.drop_column("ai_test_insights", "execution_date")
    op.drop_column("ai_test_insights", "test_name")
