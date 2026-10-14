"""Convert QA instructions to a structured list.

Revision ID: 20260901_0005
Revises: 20260901_0004
Create Date: 2026-09-01 19:46:00
"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260901_0005"
down_revision: str | None = "20260901_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_test_insights",
        sa.Column(
            "instruction_to_qa",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.execute(
        """
        UPDATE ai_test_insights
        SET instruction_to_qa = jsonb_build_array(insturctions_for_qa)
        WHERE insturctions_for_qa IS NOT NULL
          AND btrim(insturctions_for_qa) <> ''
        """
    )
    op.drop_column("ai_test_insights", "insturctions_for_qa")


def downgrade() -> None:
    op.add_column(
        "ai_test_insights",
        sa.Column("insturctions_for_qa", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE ai_test_insights
        SET insturctions_for_qa = instruction_to_qa ->> 0
        WHERE jsonb_array_length(instruction_to_qa) > 0
        """
    )
    op.drop_column("ai_test_insights", "instruction_to_qa")
