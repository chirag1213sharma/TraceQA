import json
import logging
from time import perf_counter
from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from litellm import completion
from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from app.schemas import (
    CommitImpactAnalysis,
    HistoricalInsight,
    ParsedTestReport,
    TestHistoryEntry,
    TestRunAnalysis,
)

SchemaType = TypeVar("SchemaType", bound=BaseModel)
Completion = Callable[..., Any]
logger = logging.getLogger(__name__)


class AIConfigurationError(RuntimeError):
    pass


class AIResponseError(RuntimeError):
    pass


class AIRequestError(RuntimeError):
    pass


class AIService:
    def __init__(
        self,
        *,
        model: str,
        api_key: str | None,
        api_base: str | None = None,
        request_timeout_seconds: float = 600,
        max_input_chars: int = 40_000,
        completion_fn: Completion = completion,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.request_timeout_seconds = request_timeout_seconds
        self.max_input_chars = max_input_chars
        self.completion_fn = completion_fn

    def parse_test_report(self, markdown: str) -> ParsedTestReport:
        return self._structured_completion(
            schema=ParsedTestReport,
            system_prompt=(
                "You extract automated test results. Return every individual test, "
                "preserve full test and module names, use seconds for execution_time, "
                "and do not infer tests absent from the report. For aggregate JSON "
                "reports, emit one result per explicitly named top-level test or suite. "
                "Never expand nested error lists, diff operations, missing operations, "
                "artifact paths, or filenames into separate test results."
            ),
            user_prompt=f"Parse this test report:\n\n{markdown}",
        )

    def analyze_test_report(
        self,
        *,
        test_name: str,
        report_name: str,
        report_data: str,
    ) -> TestRunAnalysis:
        return self._structured_completion(
            schema=TestRunAnalysis,
            system_prompt=(
                "You are an automated test result analyser. Analyze the supplied "
                "test report and return a QA-ready structured response. Derive the "
                "execution date from the report name or report data in YYYYMMDD "
                "format. Status must be passed or failed. Report passed and failed "
                "case counts as '<count>/<total>' using the same total for both. "
                "failed_test_case_list must contain the explicitly named failing "
                "tests, suites, or modules and must be empty for a passed run. "
                "ai_analysis should concisely explain the outcome and strongest "
                "failure signals. instruction_to_qa must be a list of specific, "
                "prioritized investigation steps grounded only in the report. "
                "Return one actionable instruction per list item."
            ),
            user_prompt=(
                f"Test Name: {test_name}\n"
                f"Report Name: {report_name}\n\n"
                f"Test data for analysis:\n{report_data}"
            ),
        )

    def analyze_history(
        self,
        history: Sequence[TestHistoryEntry],
    ) -> HistoricalInsight:
        analyses = [
            self._analyze_history_batch(batch)
            for batch in self._history_batches(history)
        ]
        if len(analyses) == 1:
            return analyses[0]

        warnings = list(
            dict.fromkeys(
                analysis.degradation_warning
                for analysis in analyses
                if analysis.degradation_warning
            )
        )
        return HistoricalInsight(
            test_assessments=[
                assessment
                for analysis in analyses
                for assessment in analysis.test_assessments
            ],
            degradation_warning="\n".join(warnings) or None,
            proactive_fixes=[
                fix for analysis in analyses for fix in analysis.proactive_fixes
            ],
            summary=" ".join(analysis.summary for analysis in analyses),
        )

    def _analyze_history_batch(
        self,
        history: Sequence[TestHistoryEntry],
    ) -> HistoricalInsight:
        payload = [entry.model_dump(mode="json") for entry in history]
        return self._structured_completion(
            schema=HistoricalInsight,
            system_prompt=(
                "Analyze test history for intermittent outcomes and execution-time "
                "degradation. Assess every test_name present. Scores must be between "
                "0 and 1. Recommend concrete, evidence-based fixes only."
            ),
            user_prompt=(
                "Analyze this test history JSON:\n"
                f"{json.dumps(payload, separators=(',', ':'))}"
            ),
        )

    def _history_batches(
        self,
        history: Sequence[TestHistoryEntry],
    ) -> list[list[TestHistoryEntry]]:
        grouped: dict[str, list[TestHistoryEntry]] = {}
        for entry in history:
            grouped.setdefault(entry.test_name, []).append(entry)

        batches: list[list[TestHistoryEntry]] = []
        current: list[TestHistoryEntry] = []
        for entries in grouped.values():
            candidate = current + entries
            serialized = json.dumps(
                [entry.model_dump(mode="json") for entry in candidate],
                separators=(",", ":"),
            )
            if current and len(serialized) > self.max_input_chars:
                batches.append(current)
                current = list(entries)
            else:
                current = candidate
        if current:
            batches.append(current)
        return batches or [[]]

    def analyze_commit_diff(self, diff: str) -> CommitImpactAnalysis:
        return self._structured_completion(
            schema=CommitImpactAnalysis,
            system_prompt=(
                "You are a regression test impact analyst. Analyze only evidence in "
                "the Git diff. Identify impacted modules, risk, existing automated "
                "tests to execute, and detailed manual regression cases."
            ),
            user_prompt=f"Analyze this Git diff:\n\n{diff}",
        )

    def _structured_completion(
        self,
        *,
        schema: type[SchemaType],
        system_prompt: str,
        user_prompt: str,
    ) -> SchemaType:
        if not self.api_key:
            raise AIConfigurationError("TRACEQA_LLM_API_KEY is not configured")

        request: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": schema,
            "temperature": 0,
            "timeout": self.request_timeout_seconds,
        }
        request["api_key"] = self.api_key
        if self.api_base:
            request["api_base"] = self.api_base

        started_at = perf_counter()
        logger.info(
            "Gemini request starting: model=%s timeout_seconds=%s "
            "response_schema=%s user_prompt_chars=%s",
            self.model,
            self.request_timeout_seconds,
            schema.__name__,
            len(user_prompt),
        )
        try:
            response = self.completion_fn(**request)
        except OpenAIError as exc:
            logger.exception(
                "Gemini request failed after %.2f seconds: model=%s "
                "error_type=%s error=%s",
                perf_counter() - started_at,
                self.model,
                type(exc).__name__,
                exc,
            )
            raise AIRequestError(f"The LLM request failed: {exc}") from exc
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError) as exc:
            raise AIResponseError(
                "The LLM returned an invalid completion response"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise AIResponseError("The LLM returned an empty structured response")
        logger.info(
            "Gemini response received after %.2f seconds: model=%s "
            "response_chars=%s",
            perf_counter() - started_at,
            self.model,
            len(content),
        )
        try:
            return schema.model_validate_json(content)
        except ValidationError as exc:
            raise AIResponseError(
                f"The LLM response did not match {schema.__name__}"
            ) from exc
