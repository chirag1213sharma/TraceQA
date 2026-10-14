import hashlib
import hmac
import json
import logging
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError

from app.api.workflows import (
    build_github_service,
    build_ingestion_service,
    build_runtime_settings_store,
)
from app.core.config import Settings, get_settings
from app.schemas import (
    CommitImpactAnalysis,
    ManualTestCase,
    ParsedTestReport,
    ParsedTestResult,
    RegressionRiskLevel,
    RunStatus,
    TestStatus as StatusSchema,
    RuntimeSettingsRead,
    TestRunAnalysis as RunAnalysisSchema,
)
from app.services.ai import AIConfigurationError, AIRequestError, AIService
from app.services.github import GitHubService
from app.services.ingestion import IngestionService
from app.services.settings import RuntimeSettingsStore


class FakeAIService:
    def analyze_test_report(
        self,
        *,
        test_name: str,
        report_name: str,
        report_data: str,
    ) -> RunAnalysisSchema:
        assert test_name
        assert report_name.endswith(".json")
        assert "checkout.test_payment" in report_data
        return RunAnalysisSchema(
            test_name="Regression_Report",
            execution_date=20260621,
            status=RunStatus.FAILED,
            test_cases_passed="80/100",
            test_cases_failed="20/100",
            failed_test_case_list=["checkout.test_payment"],
            ai_analysis="Twenty checkout tests failed because payments were declined.",
            instruction_to_qa=["Investigate checkout payment validation first."],
        )

    def analyze_commit_diff(self, diff: str) -> CommitImpactAnalysis:
        assert "payment.py" in diff
        return CommitImpactAnalysis(
            impacted_modules=["checkout"],
            summary="Payment validation changed",
            regression_risk_level=RegressionRiskLevel.HIGH,
            suggested_automated_tests=["checkout.test_payment"],
            suggested_manual_tests=[
                ManualTestCase(
                    title="Declined payment",
                    preconditions=["A declined test card"],
                    steps=["Submit checkout"],
                    expected_result="The decline is displayed",
                    priority=RegressionRiskLevel.HIGH,
                )
            ],
        )


class FakeConverter:
    def convert(self, source: Path):
        return SimpleNamespace(markdown=source.read_text())


def test_ingestion_workflow_persists_structured_results(
    client: TestClient,
    tmp_path: Path,
) -> None:
    report = tmp_path / "checkout.json"
    report.write_text('{"test": "checkout.test_payment"}')
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        test_logs_directory=tmp_path,
        llm_api_key="test-key",
    )
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_ingestion_service] = lambda: service

    run = client.post(
        "/api/v1/test-runs",
        json={"source_drive": "C:\\Previous", "run_status": "passed"},
    ).json()
    client.post(
        "/api/v1/test-results",
        json={
            "run_id": run["id"],
            "test_name": "checkout.test_payment",
            "status": "pass",
            "execution_time": 1.2,
            "flakiness_score": 0,
        },
    )

    response = client.post("/api/v1/ingestion/runs")

    assert response.status_code == 201
    payload = response.json()
    assert payload["run"]["run_status"] == "failed"
    assert payload["results"][0]["flakiness_score"] == 0
    assert payload["insight"]["test_cases_passed"] == "80/100"
    assert payload["insight"]["test_cases_failed"] == "20/100"
    assert payload["insight"]["ai_analysis"].startswith("Twenty checkout")
    assert payload["insight"]["instruction_to_qa"] == [
        "Investigate checkout payment validation first."
    ]
    assert payload["processed_files"] == ["checkout.json"]
    assert payload["run"]["source_file"] == "checkout.json"


def test_ingestion_rejects_missing_directory(client: TestClient, tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        test_logs_directory=tmp_path / "missing",
        llm_api_key="test-key",
    )
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_ingestion_service] = lambda: service

    response = client.post("/api/v1/ingestion/runs")

    assert response.status_code == 422
    assert "does not exist" in response.json()["detail"]


def test_ingestion_persists_each_new_file_and_skips_completed_files(
    client: TestClient,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    first.write_text('{"test": "checkout.test_payment"}')
    second.write_text('{"test": "checkout.test_payment"}')
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        test_logs_directory=tmp_path,
        llm_api_key="test-key",
    )
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_ingestion_service] = lambda: service

    first_response = client.post("/api/v1/ingestion/runs")
    second_response = client.post("/api/v1/ingestion/runs")
    runs_response = client.get("/api/v1/test-runs")

    assert first_response.status_code == 201
    assert first_response.json()["processed_files"] == ["first.json", "second.json"]
    assert second_response.status_code == 201
    assert second_response.json()["processed_files"] == []
    assert len(runs_response.json()) == 2


def test_ingestion_skips_a_file_claimed_by_another_ingestion(
    client: TestClient,
    tmp_path: Path,
) -> None:
    report = tmp_path / "checkout" / "test-data" / "report.json"
    report.parent.mkdir(parents=True)
    report.write_text('{"test": "checkout.test_payment"}')
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        test_logs_directory=tmp_path,
        llm_api_key="test-key",
    )
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_ingestion_service] = lambda: service

    claimed_file_id = service._file_id(report, tmp_path)
    claim_response = client.post(
        "/api/v1/test-runs",
        json={
            "source_drive": str(tmp_path),
            "run_status": "processing",
        },
    )
    assert claim_response.status_code == 201

    # Associate the existing run with the report identity to emulate a parallel
    # ingestion worker that has claimed it before invoking the model.
    from app.db.session import get_db

    session_factory = client.app.dependency_overrides[get_db]
    with next(session_factory()) as db:
        from app.models import TestRun

        claim = db.get(TestRun, claim_response.json()["id"])
        assert claim is not None
        claim.source_file_id = claimed_file_id
        claim.source_file = "checkout\\test-data\\report.json"
        db.commit()

    response = client.post("/api/v1/ingestion/runs")

    assert response.status_code == 201
    assert response.json()["processed_files"] == []


def test_default_ingestion_limit_accepts_large_html_report(tmp_path: Path) -> None:
    report = tmp_path / "large-report.html"
    with report.open("wb") as report_file:
        report_file.seek(20 * 1024 * 1024)
        report_file.write(b"x")
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )

    files = service._scan(tmp_path)

    assert files == [report]
    assert service.max_file_bytes == 50 * 1024 * 1024


def test_large_markdown_over_gemini_limit_is_rejected(
    client: TestClient,
    tmp_path: Path,
) -> None:
    report = tmp_path / "large.json"
    report.write_text('{"test":"checkout.test_payment","data":"' + ("a" * 200) + '"}')
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
        max_llm_input_chars=100,
    )
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        test_logs_directory=tmp_path,
        llm_api_key="test-key",
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_ingestion_service] = lambda: service

    response = client.post("/api/v1/ingestion/runs")

    assert response.status_code == 422
    assert "Gemini input limit" in response.json()["detail"]


def test_repetitive_json_lists_are_compacted_without_dropping_test_objects() -> None:
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    markdown = json.dumps(
        {
            "Diff Operations": {
                "Rough Mill": [f"operation-{index}" for index in range(30)],
                "Finish Mill": [f"finish-{index}" for index in range(10)],
            },
            "tests": [
                {"name": f"test-{index}", "status": "pass"}
                for index in range(30)
            ],
        }
    )

    compacted = json.loads(service._compact_repetitive_json(markdown))

    assert compacted["Diff Operations"]["total_items"] == 40
    assert compacted["Diff Operations"]["total_categories"] == 2
    assert len(
        compacted["Diff Operations"]["sample_categories"]["Rough Mill"]
    ) == 3
    assert len(compacted["tests"]) == 30


def test_large_markdown_tables_are_compacted_to_counts_and_samples() -> None:
    service = IngestionService(
        ai_service=FakeAIService(),
        converter=FakeConverter(),
    )
    header = "| " + " | ".join(f"column-{index}" for index in range(50)) + " |"
    separator = "| " + " | ".join("---" for _ in range(50)) + " |"
    rows = [
        "| " + " | ".join(f"value-{row}-{column}" for column in range(50)) + " |"
        for row in range(30)
    ]

    compacted = service._compact_markdown_tables(
        "\n".join([header, separator, *rows])
    )

    assert "[Large table compacted: 30 data rows, 50 columns]" in compacted
    assert "column-0" in compacted
    assert "value-0-0" in compacted
    assert "value-29-0" not in compacted


def test_github_webhook_verifies_signature_and_persists_impact(
    client: TestClient,
) -> None:
    def github_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer github-token"
        return httpx.Response(
            200,
            text="diff --git a/payment.py b/payment.py",
            request=request,
        )

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        github_token="github-token",
        github_webhook_secret="webhook-secret",
        llm_api_key="test-key",
    )
    github_client = httpx.Client(transport=httpx.MockTransport(github_handler))
    service = GitHubService(
        ai_service=FakeAIService(),
        token="github-token",
        client=github_client,
    )
    client.app.dependency_overrides[get_settings] = lambda: settings
    client.app.dependency_overrides[build_github_service] = lambda: service
    body = json.dumps(
        {
            "after": "abc1234567890",
            "ref": "refs/heads/main",
            "repository": {
                "full_name": "acme/traceqa",
                "extra_github_field": True,
            },
            "extra_push_field": "accepted",
        }
    ).encode()
    signature = "sha256=" + hmac.new(
        b"webhook-secret",
        body,
        hashlib.sha256,
    ).hexdigest()

    response = client.post(
        "/api/v1/github/webhooks/push",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["impacted_modules"] == ["checkout"]
    assert payload["impact"]["regression_risk_level"] == "high"
    assert client.get("/api/v1/commit-impacts").json()[0]["branch"] == "main"

    repeated = client.post(
        "/api/v1/github/webhooks/push",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": signature,
        },
    )
    assert repeated.status_code == 200
    assert len(client.get("/api/v1/commit-impacts").json()) == 1
    github_client.close()


def test_github_webhook_rejects_invalid_signature(client: TestClient) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        github_webhook_secret="webhook-secret",
    )
    client.app.dependency_overrides[get_settings] = lambda: settings

    response = client.post(
        "/api/v1/github/webhooks/push",
        json={
            "after": "abc1234567890",
            "ref": "refs/heads/main",
            "repository": {"full_name": "acme/traceqa"},
        },
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )

    assert response.status_code == 401


def test_ai_service_uses_pydantic_response_format() -> None:
    captured = {}
    expected = ParsedTestReport(
        run_status=RunStatus.PASSED,
        results=[
            ParsedTestResult(
                test_name="smoke.test_health",
                module_name="smoke",
                status=StatusSchema.PASS,
                execution_time=0.1,
                error_log=None,
            )
        ],
    )

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=expected.model_dump_json())
                )
            ]
        )

    service = AIService(
        model="gemini/test-model",
        api_key="test-key",
        completion_fn=fake_completion,
    )
    parsed = service.parse_test_report("# test output")

    assert parsed == expected
    assert captured["response_format"] is ParsedTestReport
    assert captured["temperature"] == 0


def test_ai_service_requests_qa_ready_gemini_analysis() -> None:
    captured = {}
    expected = RunAnalysisSchema(
        test_name="Regression_Report",
        execution_date=20260621,
        status=RunStatus.FAILED,
        test_cases_passed="11832/18984",
        test_cases_failed="7152/18984",
        failed_test_case_list=["Smoke-master", "Turn-master"],
        ai_analysis="The regression suite has significant failures.",
        instruction_to_qa=["Investigate Turn-master first."],
    )

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=expected.model_dump_json())
                )
            ]
        )

    service = AIService(
        model="gemini/gemini-2.5-flash",
        api_key="test-key",
        completion_fn=fake_completion,
    )

    analysis = service.analyze_test_report(
        test_name="Regression_Report",
        report_name="test_system_report_20260621.json",
        report_data='{"failed": 7152}',
    )

    assert analysis == expected
    assert captured["response_format"] is RunAnalysisSchema
    assert captured["api_key"] == "test-key"
    assert "Test Name: Regression_Report" in captured["messages"][1]["content"]
    assert '{"failed": 7152}' in captured["messages"][1]["content"]


def test_ai_service_requires_api_key() -> None:
    service = AIService(model="gemini/test-model", api_key=None)

    try:
        service.parse_test_report("# test output")
    except AIConfigurationError as exc:
        assert "TRACEQA_LLM_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected AIConfigurationError")


def test_ai_service_normalizes_gemini_timeout() -> None:
    def timed_out_completion(**_kwargs):
        raise APITimeoutError(request=httpx.Request("POST", "http://localhost"))

    service = AIService(
        model="gemini/gemini-2.5-flash",
        api_key="test-key",
        request_timeout_seconds=30,
        completion_fn=timed_out_completion,
    )

    with pytest.raises(AIRequestError, match="LLM request failed"):
        service.parse_test_report("# test output")


def test_ai_service_logs_gemini_request_and_response(caplog: pytest.LogCaptureFixture) -> None:
    expected = ParsedTestReport(
        run_status=RunStatus.PASSED,
        results=[],
    )

    def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=expected.model_dump_json())
                )
            ]
        )

    service = AIService(
        model="gemini/gemini-2.5-flash",
        api_key="test-key",
        completion_fn=fake_completion,
    )

    with caplog.at_level(logging.INFO, logger="app.services.ai"):
        assert service.parse_test_report("test output") == expected

    assert "Gemini request starting" in caplog.text
    assert "user_prompt_chars=" in caplog.text
    assert "Gemini response received" in caplog.text


def test_runtime_settings_api_masks_secrets(client: TestClient) -> None:
    class FakeSettingsStore:
        def read(self) -> RuntimeSettingsRead:
            return RuntimeSettingsRead(
                test_logs_directory="C:\\TraceQA\\test-logs",
                llm_model="gemini/test-model",
                llm_api_base="https://example.invalid",
                llm_api_key_configured=True,
                github_token_configured=False,
                github_webhook_secret_configured=True,
            )

        def update(self, _payload) -> RuntimeSettingsRead:
            return self.read()

    client.app.dependency_overrides[build_runtime_settings_store] = (
        FakeSettingsStore
    )

    response = client.get("/api/v1/settings/runtime")

    assert response.status_code == 200
    assert response.json() == {
        "test_logs_directory": "C:\\TraceQA\\test-logs",
        "llm_model": "gemini/test-model",
        "llm_api_base": "https://example.invalid",
        "llm_api_key_configured": True,
        "github_token_configured": False,
        "github_webhook_secret_configured": True,
    }
    assert "llm_api_key" not in response.json()
    assert "github_token" not in response.json()
    assert "github_webhook_secret" not in response.json()


def test_runtime_settings_store_updates_and_clears_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from app.core.config import get_settings
    from app.schemas import RuntimeSettingsUpdate

    for name in (
        "TRACEQA_TEST_LOGS_DIRECTORY",
        "TRACEQA_LLM_MODEL",
        "TRACEQA_LLM_API_BASE",
        "TRACEQA_LLM_API_KEY",
        "TRACEQA_GITHUB_TOKEN",
        "TRACEQA_GITHUB_WEBHOOK_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    store = RuntimeSettingsStore(tmp_path / ".env")

    updated = store.update(
        RuntimeSettingsUpdate(
            test_logs_directory="C:\\QA\\logs",
            llm_model="gemini/custom",
            llm_api_base="http://localhost:11434",
            llm_api_key="secret",
            github_token="",
        )
    )

    assert updated.test_logs_directory == "C:\\QA\\logs"
    assert updated.llm_model == "gemini/custom"
    assert updated.llm_api_base == "http://localhost:11434"
    assert updated.llm_api_key_configured is True
    assert updated.github_token_configured is False
    contents = (tmp_path / ".env").read_text()
    assert "TRACEQA_LLM_API_KEY='secret'" in contents
    assert "TRACEQA_GITHUB_TOKEN" not in contents
    get_settings.cache_clear()
