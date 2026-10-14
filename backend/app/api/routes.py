from datetime import datetime, timezone
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crud import CRUDRepository
from app.db.base import Base
from app.db.session import get_db
from app.models import AITestInsight, CommitImpact, TestResult, TestRun
from app.schemas import (
    AITestInsightCreate,
    AITestInsightRead,
    AITestInsightUpdate,
    CommitImpactCreate,
    CommitImpactRead,
    CommitImpactUpdate,
    TestResultCreate,
    TestResultRead,
    TestResultUpdate,
    TestRunCreate,
    TestRunRead,
    TestRunUpdate,
)

router = APIRouter()
DbSession = Annotated[Session, Depends(get_db)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
ModelType = TypeVar("ModelType", bound=Base)

test_runs = CRUDRepository(TestRun)
test_results = CRUDRepository(TestResult)
test_insights = CRUDRepository(AITestInsight)
commit_impacts = CRUDRepository(CommitImpact)


def get_or_404(
    repository: CRUDRepository,
    db: Session,
    object_id: int,
) -> ModelType:
    instance = repository.get(db, object_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Resource not found")
    return instance


def ensure_run_exists(db: Session, run_id: int) -> None:
    if db.get(TestRun, run_id) is None:
        raise HTTPException(status_code=404, detail="Test run not found")


def commit_or_conflict(db: Session, action):
    try:
        return action()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Resource conflicts with existing data",
        ) from exc


@router.post("/test-runs", response_model=TestRunRead, status_code=201)
def create_test_run(payload: TestRunCreate, db: DbSession) -> TestRun:
    timestamp = payload.timestamp or datetime.now(timezone.utc)
    return test_runs.create(db, data=payload, overrides={"timestamp": timestamp})


@router.get("/test-runs", response_model=list[TestRunRead])
def list_test_runs(
    db: DbSession,
    offset: Offset = 0,
    limit: Limit = 50,
) -> list[TestRun]:
    statement = (
        select(TestRun)
        .order_by(TestRun.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))


@router.get("/test-runs/{run_id}", response_model=TestRunRead)
def get_test_run(run_id: int, db: DbSession) -> TestRun:
    return get_or_404(test_runs, db, run_id)


@router.patch("/test-runs/{run_id}", response_model=TestRunRead)
def update_test_run(
    run_id: int,
    payload: TestRunUpdate,
    db: DbSession,
) -> TestRun:
    return test_runs.update(
        db,
        instance=get_or_404(test_runs, db, run_id),
        data=payload,
    )


@router.delete("/test-runs/{run_id}", status_code=204)
def delete_test_run(run_id: int, db: DbSession) -> Response:
    test_runs.delete(db, instance=get_or_404(test_runs, db, run_id))
    return Response(status_code=204)


@router.post("/test-results", response_model=TestResultRead, status_code=201)
def create_test_result(payload: TestResultCreate, db: DbSession) -> TestResult:
    ensure_run_exists(db, payload.run_id)
    return test_results.create(db, data=payload)


@router.get("/test-results", response_model=list[TestResultRead])
def list_test_results(
    db: DbSession,
    offset: Offset = 0,
    limit: Limit = 50,
    run_id: int | None = None,
    test_name: str | None = None,
) -> list[TestResult]:
    statement = select(TestResult)
    if run_id is not None:
        statement = statement.where(TestResult.run_id == run_id)
    if test_name is not None:
        statement = statement.where(TestResult.test_name == test_name)
    statement = statement.order_by(TestResult.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement))


@router.get("/test-results/{result_id}", response_model=TestResultRead)
def get_test_result(result_id: int, db: DbSession) -> TestResult:
    return get_or_404(test_results, db, result_id)


@router.patch("/test-results/{result_id}", response_model=TestResultRead)
def update_test_result(
    result_id: int,
    payload: TestResultUpdate,
    db: DbSession,
) -> TestResult:
    if payload.run_id is not None:
        ensure_run_exists(db, payload.run_id)
    return test_results.update(
        db,
        instance=get_or_404(test_results, db, result_id),
        data=payload,
    )


@router.delete("/test-results/{result_id}", status_code=204)
def delete_test_result(result_id: int, db: DbSession) -> Response:
    test_results.delete(db, instance=get_or_404(test_results, db, result_id))
    return Response(status_code=204)


@router.post("/ai-test-insights", response_model=AITestInsightRead, status_code=201)
def create_ai_test_insight(
    payload: AITestInsightCreate,
    db: DbSession,
) -> AITestInsight:
    ensure_run_exists(db, payload.run_id)
    return test_insights.create(db, data=payload)


@router.get("/ai-test-insights", response_model=list[AITestInsightRead])
def list_ai_test_insights(
    db: DbSession,
    offset: Offset = 0,
    limit: Limit = 50,
    run_id: int | None = None,
) -> list[AITestInsight]:
    statement = select(AITestInsight)
    if run_id is not None:
        statement = statement.where(AITestInsight.run_id == run_id)
    statement = statement.order_by(AITestInsight.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement))


@router.get("/ai-test-insights/{insight_id}", response_model=AITestInsightRead)
def get_ai_test_insight(insight_id: int, db: DbSession) -> AITestInsight:
    return get_or_404(test_insights, db, insight_id)


@router.patch("/ai-test-insights/{insight_id}", response_model=AITestInsightRead)
def update_ai_test_insight(
    insight_id: int,
    payload: AITestInsightUpdate,
    db: DbSession,
) -> AITestInsight:
    if payload.run_id is not None:
        ensure_run_exists(db, payload.run_id)
    return test_insights.update(
        db,
        instance=get_or_404(test_insights, db, insight_id),
        data=payload,
    )


@router.delete("/ai-test-insights/{insight_id}", status_code=204)
def delete_ai_test_insight(insight_id: int, db: DbSession) -> Response:
    test_insights.delete(
        db,
        instance=get_or_404(test_insights, db, insight_id),
    )
    return Response(status_code=204)


@router.post("/commit-impacts", response_model=CommitImpactRead, status_code=201)
def create_commit_impact(
    payload: CommitImpactCreate,
    db: DbSession,
) -> CommitImpact:
    return commit_or_conflict(db, lambda: commit_impacts.create(db, data=payload))


@router.get("/commit-impacts", response_model=list[CommitImpactRead])
def list_commit_impacts(
    db: DbSession,
    offset: Offset = 0,
    limit: Limit = 50,
    branch: str | None = None,
) -> list[CommitImpact]:
    statement = select(CommitImpact)
    if branch is not None:
        statement = statement.where(CommitImpact.branch == branch)
    statement = statement.order_by(CommitImpact.id.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement))


@router.get("/commit-impacts/{impact_id}", response_model=CommitImpactRead)
def get_commit_impact(impact_id: int, db: DbSession) -> CommitImpact:
    return get_or_404(commit_impacts, db, impact_id)


@router.patch("/commit-impacts/{impact_id}", response_model=CommitImpactRead)
def update_commit_impact(
    impact_id: int,
    payload: CommitImpactUpdate,
    db: DbSession,
) -> CommitImpact:
    return commit_or_conflict(
        db,
        lambda: commit_impacts.update(
            db,
            instance=get_or_404(commit_impacts, db, impact_id),
            data=payload,
        )
    )


@router.delete("/commit-impacts/{impact_id}", status_code=204)
def delete_commit_impact(impact_id: int, db: DbSession) -> Response:
    commit_impacts.delete(
        db,
        instance=get_or_404(commit_impacts, db, impact_id),
    )
    return Response(status_code=204)
