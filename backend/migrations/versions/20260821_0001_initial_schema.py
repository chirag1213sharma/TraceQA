"""Create the TraceQA foundation schema.

Revision ID: 20260821_0001
Revises:
Create Date: 2026-08-21 14:02:28
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260821_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_drive", sa.String(length=2048), nullable=False),
        sa.Column("run_status", sa.String(length=50), nullable=False),
    )
    op.create_index("ix_test_runs_timestamp", "test_runs", ["timestamp"])

    op.create_table(
        "commit_impacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("commit_hash", sa.String(length=64), nullable=False),
        sa.Column("branch", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("regression_risk_level", sa.String(length=50), nullable=False),
        sa.Column("suggested_automated_tests", sa.JSON(), nullable=False),
        sa.Column("suggested_manual_tests", sa.JSON(), nullable=False),
        sa.UniqueConstraint("commit_hash", "branch", name="uq_commit_impact_hash_branch"),
    )
    op.create_index("ix_commit_impacts_branch", "commit_impacts", ["branch"])

    op.create_table(
        "test_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("test_name", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("execution_time", sa.Float(), nullable=False),
        sa.Column("error_log", sa.Text(), nullable=True),
        sa.Column("flakiness_score", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pass', 'fail', 'skip')",
            name="ck_test_results_status",
        ),
        sa.CheckConstraint(
            "execution_time >= 0",
            name="ck_test_results_execution_time",
        ),
        sa.CheckConstraint(
            "flakiness_score >= 0 AND flakiness_score <= 1",
            name="ck_test_results_flakiness_score",
        ),
    )
    op.create_index("ix_test_results_run_id", "test_results", ["run_id"])
    op.create_index("ix_test_results_test_name", "test_results", ["test_name"])

    op.create_table(
        "ai_test_insights",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("test_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("degradation_warning", sa.Text(), nullable=True),
        sa.Column("proactive_fixes", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
    )
    op.create_index("ix_ai_test_insights_run_id", "ai_test_insights", ["run_id"])


def downgrade() -> None:
    op.drop_table("ai_test_insights")
    op.drop_table("test_results")
    op.drop_table("commit_impacts")
    op.drop_table("test_runs")

