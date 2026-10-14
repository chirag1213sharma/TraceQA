from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        UniqueConstraint("source_file_id", name="uq_test_runs_source_file_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    source_drive: Mapped[str] = mapped_column(String(2048))
    source_file_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_file: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    run_status: Mapped[str] = mapped_column(String(50))

    results: Mapped[list[TestResult]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    insights: Mapped[list[AITestInsight]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pass', 'fail', 'skip')",
            name="ck_test_results_status",
        ),
        CheckConstraint(
            "execution_time >= 0",
            name="ck_test_results_execution_time",
        ),
        CheckConstraint(
            "flakiness_score >= 0 AND flakiness_score <= 1",
            name="ck_test_results_flakiness_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        index=True,
    )
    test_name: Mapped[str] = mapped_column(String(500), index=True)
    status: Mapped[str] = mapped_column(String(10))
    execution_time: Mapped[float] = mapped_column(Float)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
    flakiness_score: Mapped[float] = mapped_column(Float, default=0.0)

    run: Mapped[TestRun] = relationship(back_populates="results")


class AITestInsight(Base):
    __tablename__ = "ai_test_insights"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("test_runs.id", ondelete="CASCADE"),
        index=True,
    )
    degradation_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    proactive_fixes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text)
    test_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    execution_date: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    test_cases_passed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    test_cases_failed: Mapped[str | None] = mapped_column(String(50), nullable=True)
    failed_test_case_list: Mapped[list[str]] = mapped_column(JSON, default=list)
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    instruction_to_qa: Mapped[list[str]] = mapped_column(JSON, default=list)

    run: Mapped[TestRun] = relationship(back_populates="insights")


class CommitImpact(Base):
    __tablename__ = "commit_impacts"
    __table_args__ = (
        UniqueConstraint(
            "commit_hash",
            "branch",
            name="uq_commit_impact_hash_branch",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    commit_hash: Mapped[str] = mapped_column(String(64))
    branch: Mapped[str] = mapped_column(String(255), index=True)
    summary: Mapped[str] = mapped_column(Text)
    regression_risk_level: Mapped[str] = mapped_column(String(50))
    suggested_automated_tests: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggested_manual_tests: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
    )
