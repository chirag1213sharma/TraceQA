from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TestStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


class RunStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RegressionRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WebhookModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ParsedTestResult(StrictAIModel):
    test_name: str = Field(min_length=1, max_length=500)
    module_name: str = Field(min_length=1, max_length=255)
    status: TestStatus
    execution_time: float = Field(ge=0)
    error_log: str | None


class ParsedTestReport(StrictAIModel):
    run_status: RunStatus
    results: list[ParsedTestResult] = Field(max_length=100)


class TestRunAnalysis(StrictAIModel):
    test_name: str = Field(min_length=1, max_length=500)
    execution_date: int = Field(ge=20000101, le=29991231)
    status: RunStatus
    test_cases_passed: str = Field(pattern=r"^\d+\s*/\s*\d+$")
    test_cases_failed: str = Field(pattern=r"^\d+\s*/\s*\d+$")
    failed_test_case_list: list[str]
    ai_analysis: str = Field(min_length=1)
    instruction_to_qa: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_analysis_consistency(self) -> "TestRunAnalysis":
        if self.status not in {RunStatus.PASSED, RunStatus.FAILED}:
            raise ValueError("status must be passed or failed")
        try:
            datetime.strptime(str(self.execution_date), "%Y%m%d")
        except ValueError as exc:
            raise ValueError("execution_date must be a valid YYYYMMDD date") from exc

        passed, passed_total = (
            int(part.strip()) for part in self.test_cases_passed.split("/")
        )
        failed, failed_total = (
            int(part.strip()) for part in self.test_cases_failed.split("/")
        )
        if passed_total != failed_total or passed + failed != passed_total:
            raise ValueError("Passed and failed counts must add up to the same total")
        if self.status == RunStatus.PASSED and failed:
            raise ValueError("A passed run cannot contain failed test cases")
        if self.status == RunStatus.FAILED and not failed:
            raise ValueError("A failed run must contain failed test cases")
        if self.status == RunStatus.PASSED and self.failed_test_case_list:
            raise ValueError("A passed run cannot list failed test cases")
        return self


class TestHistoryEntry(StrictAIModel):
    test_name: str
    status: TestStatus
    execution_time: float
    flakiness_score: float
    timestamp: datetime


class ProactiveFix(StrictAIModel):
    test_name: str | None
    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class TestAssessment(StrictAIModel):
    test_name: str
    flakiness_score: float = Field(ge=0, le=1)
    performance_degradation: bool
    warning: str | None


class HistoricalInsight(StrictAIModel):
    test_assessments: list[TestAssessment]
    degradation_warning: str | None
    proactive_fixes: list[ProactiveFix]
    summary: str = Field(min_length=1)


class ManualTestCase(StrictAIModel):
    title: str = Field(min_length=1)
    preconditions: list[str]
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    priority: RegressionRiskLevel


class CommitImpactAnalysis(StrictAIModel):
    impacted_modules: list[str]
    summary: str = Field(min_length=1)
    regression_risk_level: RegressionRiskLevel
    suggested_automated_tests: list[str]
    suggested_manual_tests: list[ManualTestCase]


class IngestionRead(StrictAIModel):
    run: "TestRunRead | None" = None
    results: list["TestResultRead"] = Field(default_factory=list)
    insight: "AITestInsightRead | None" = None
    processed_files: list[str]


class CommitRadarRead(StrictAIModel):
    impact: "CommitImpactRead"
    impacted_modules: list[str]


class GitHubRepository(WebhookModel):
    full_name: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitHubPushEvent(WebhookModel):
    after: str = Field(min_length=7, max_length=64, pattern=r"^[0-9a-fA-F]+$")
    ref: str = Field(pattern=r"^refs/heads/.+")
    repository: GitHubRepository
    deleted: bool = False


class RuntimeSettingsRead(StrictAIModel):
    test_logs_directory: str
    llm_model: str
    llm_api_base: str
    llm_api_key_configured: bool
    github_token_configured: bool
    github_webhook_secret_configured: bool


class RuntimeSettingsUpdate(StrictAIModel):
    test_logs_directory: str | None = Field(default=None, min_length=1)
    llm_model: str | None = Field(default=None, min_length=1)
    llm_api_base: str | None = Field(default=None, min_length=1)
    llm_api_key: str | None = None
    github_token: str | None = None
    github_webhook_secret: str | None = None


class TestRunBase(BaseModel):
    source_drive: str = Field(min_length=1, max_length=2048)
    run_status: str = Field(min_length=1, max_length=50)


class TestRunCreate(TestRunBase):
    timestamp: datetime | None = None


class TestRunUpdate(BaseModel):
    timestamp: datetime | None = None
    source_drive: str | None = Field(default=None, min_length=1, max_length=2048)
    run_status: str | None = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "TestRunUpdate":
        required = {"timestamp", "source_drive", "run_status"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required
        ):
            raise ValueError("Required test run fields cannot be null")
        return self


class TestRunRead(TestRunBase, ORMModel):
    id: int
    timestamp: datetime
    source_file: str | None = None


class TestResultBase(BaseModel):
    run_id: int
    test_name: str = Field(min_length=1, max_length=500)
    status: TestStatus
    execution_time: float = Field(ge=0)
    error_log: str | None = None
    flakiness_score: float = Field(default=0, ge=0, le=1)


class TestResultCreate(TestResultBase):
    pass


class TestResultUpdate(BaseModel):
    run_id: int | None = None
    test_name: str | None = Field(default=None, min_length=1, max_length=500)
    status: TestStatus | None = None
    execution_time: float | None = Field(default=None, ge=0)
    error_log: str | None = None
    flakiness_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "TestResultUpdate":
        required = {
            "run_id",
            "test_name",
            "status",
            "execution_time",
            "flakiness_score",
        }
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required
        ):
            raise ValueError("Required test result fields cannot be null")
        return self


class TestResultRead(TestResultBase, ORMModel):
    id: int


class AITestInsightBase(BaseModel):
    run_id: int
    degradation_warning: str | None = None
    proactive_fixes: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = Field(min_length=1)
    test_name: str | None = Field(default=None, max_length=500)
    execution_date: int | None = Field(default=None, ge=20000101, le=29991231)
    status: RunStatus | None = None
    test_cases_passed: str | None = Field(
        default=None,
        pattern=r"^\d+\s*/\s*\d+$",
    )
    test_cases_failed: str | None = Field(
        default=None,
        pattern=r"^\d+\s*/\s*\d+$",
    )
    failed_test_case_list: list[str] = Field(default_factory=list)
    ai_analysis: str | None = None
    instruction_to_qa: list[str] = Field(default_factory=list)


class AITestInsightCreate(AITestInsightBase):
    pass


class AITestInsightUpdate(BaseModel):
    run_id: int | None = None
    degradation_warning: str | None = None
    proactive_fixes: list[dict[str, Any]] | None = None
    summary: str | None = Field(default=None, min_length=1)
    test_name: str | None = Field(default=None, min_length=1, max_length=500)
    execution_date: int | None = Field(default=None, ge=20000101, le=29991231)
    status: RunStatus | None = None
    test_cases_passed: str | None = Field(
        default=None,
        pattern=r"^\d+\s*/\s*\d+$",
    )
    test_cases_failed: str | None = Field(
        default=None,
        pattern=r"^\d+\s*/\s*\d+$",
    )
    failed_test_case_list: list[str] | None = None
    ai_analysis: str | None = Field(default=None, min_length=1)
    instruction_to_qa: list[str] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "AITestInsightUpdate":
        required = {"run_id", "proactive_fixes", "summary"}
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required
        ):
            raise ValueError("Required AI insight fields cannot be null")
        return self


class AITestInsightRead(AITestInsightBase, ORMModel):
    id: int


class CommitImpactBase(BaseModel):
    commit_hash: str = Field(min_length=7, max_length=64)
    branch: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1)
    regression_risk_level: str = Field(min_length=1, max_length=50)
    suggested_automated_tests: list[str] = Field(default_factory=list)
    suggested_manual_tests: list[dict[str, Any]] = Field(default_factory=list)


class CommitImpactCreate(CommitImpactBase):
    pass


class CommitImpactUpdate(BaseModel):
    commit_hash: str | None = Field(default=None, min_length=7, max_length=64)
    branch: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1)
    regression_risk_level: str | None = Field(
        default=None,
        min_length=1,
        max_length=50,
    )
    suggested_automated_tests: list[str] | None = None
    suggested_manual_tests: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "CommitImpactUpdate":
        required = {
            "commit_hash",
            "branch",
            "summary",
            "regression_risk_level",
            "suggested_automated_tests",
            "suggested_manual_tests",
        }
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in required
        ):
            raise ValueError("Required commit impact fields cannot be null")
        return self


class CommitImpactRead(CommitImpactBase, ORMModel):
    id: int
