import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from markitdown import (
    FileConversionException,
    MarkItDown,
    UnsupportedFormatException,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import AITestInsight, TestResult, TestRun
from app.schemas import (
    IngestionRead,
    TestRunAnalysis,
)
from app.services.ai import (
    AIConfigurationError,
    AIRequestError,
    AIResponseError,
    AIService,
)

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".htm",
    ".html",
    ".json",
    ".md",
    ".pdf",
    ".txt",
    ".xml",
}


class MarkdownResult(Protocol):
    markdown: str


class MarkdownConverter(Protocol):
    def convert(self, source: Path) -> MarkdownResult: ...


class IngestionError(RuntimeError):
    pass


class IngestionService:
    def __init__(
        self,
        *,
        ai_service: AIService,
        converter: MarkdownConverter | None = None,
        max_files: int = 100,
        max_file_bytes: int = 50 * 1024 * 1024,
        max_markdown_chars: int = 1_000_000,
        max_llm_input_chars: int = 40_000,
    ) -> None:
        self.ai_service = ai_service
        self.converter = converter or MarkItDown()
        self.max_files = max_files
        self.max_file_bytes = max_file_bytes
        self.max_markdown_chars = max_markdown_chars
        self.max_llm_input_chars = max_llm_input_chars

    def ingest(self, db: Session, source_directory: Path) -> IngestionRead:
        files = self._scan(source_directory)
        source_directory = source_directory.expanduser().resolve()
        file_ids = {path: self._file_id(path, source_directory) for path in files}
        completed_ids = set(
            db.scalars(
                select(TestRun.source_file_id).where(
                    TestRun.source_file_id.in_(file_ids.values())
                )
            )
        )
        new_files = [
            path for path in files if file_ids[path] not in completed_ids
        ]
        if len(new_files) > self.max_files:
            raise IngestionError(
                f"Found {len(new_files)} new files; maximum is {self.max_files}"
            )

        completed: list[tuple[TestRun, list[TestResult], AITestInsight, Path]] = []
        for path in new_files:
            persisted = self._ingest_file(
                db,
                source_directory,
                path,
                file_ids[path],
            )
            if persisted is not None:
                completed.append((*persisted, path))

        if not completed:
            return IngestionRead(processed_files=[])

        run, results, insight, _path = completed[-1]
        return IngestionRead(
            run=run,
            results=results,
            insight=insight,
            processed_files=[
                str(path.relative_to(source_directory)) for *_values, path in completed
            ],
        )

    def _ingest_file(
        self,
        db: Session,
        source_directory: Path,
        path: Path,
        source_file_id: str,
    ) -> tuple[TestRun, list[TestResult], AITestInsight] | None:
        now = datetime.now(timezone.utc)
        try:
            run = TestRun(
                timestamp=now,
                source_drive=str(source_directory),
                source_file_id=source_file_id,
                source_file=str(path.relative_to(source_directory)),
                run_status="processing",
            )
            db.add(run)
            db.commit()
        except IntegrityError:
            db.rollback()
            return None

        try:
            markdown = self._convert_file(path)
            if len(markdown) > self.max_llm_input_chars:
                raise IngestionError(
                    f"Compacted report exceeds the configured Gemini input limit: "
                    f"{path.name}"
                )
            relative_path = path.relative_to(source_directory)
            test_name = (
                relative_path.parts[0]
                if len(relative_path.parts) > 1
                else path.stem
            )
            analysis = self.ai_service.analyze_test_report(
                test_name=test_name,
                report_name=path.name,
                report_data=markdown,
            )
            run.run_status = analysis.status.value
            run.timestamp = datetime.strptime(
                str(analysis.execution_date),
                "%Y%m%d",
            ).replace(tzinfo=timezone.utc)
            result_names = analysis.failed_test_case_list or [analysis.test_name]
            results = [
                TestResult(
                    run_id=run.id,
                    test_name=result_name,
                    status=(
                        "fail"
                        if analysis.failed_test_case_list
                        else "pass"
                    ),
                    execution_time=0,
                    error_log=(
                        analysis.ai_analysis
                        if analysis.failed_test_case_list
                        else None
                    ),
                    flakiness_score=0,
                )
                for result_name in result_names
            ]
            db.add_all(results)
            db.flush()
            insight = AITestInsight(
                run_id=run.id,
                degradation_warning=None,
                proactive_fixes=[],
                summary=analysis.ai_analysis,
                test_name=analysis.test_name,
                execution_date=analysis.execution_date,
                status=analysis.status.value,
                test_cases_passed=analysis.test_cases_passed,
                test_cases_failed=analysis.test_cases_failed,
                failed_test_case_list=analysis.failed_test_case_list,
                ai_analysis=analysis.ai_analysis,
                instruction_to_qa=analysis.instruction_to_qa,
            )
            db.add(insight)
            db.commit()
        except (
            AIConfigurationError,
            AIRequestError,
            AIResponseError,
            IngestionError,
            SQLAlchemyError,
        ):
            db.rollback()
            claimed_run = db.get(TestRun, run.id)
            if claimed_run is not None:
                db.delete(claimed_run)
                db.commit()
            raise

        db.refresh(run)
        for result in results:
            db.refresh(result)
        db.refresh(insight)
        return run, results, insight

    def _scan(self, source_directory: Path) -> list[Path]:
        source_directory = source_directory.expanduser()
        if not source_directory.exists():
            raise IngestionError(f"Test log directory does not exist: {source_directory}")
        if not source_directory.is_dir():
            raise IngestionError(f"Test log path is not a directory: {source_directory}")

        root = source_directory.resolve()
        files = sorted(
            path
            for path in root.rglob("*")
            if path.is_file()
            and not path.is_symlink()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        )
        if not files:
            raise IngestionError("No supported test report files were found")
        return files

    def _file_id(self, path: Path, source_directory: Path) -> str:
        try:
            if path.stat().st_size > self.max_file_bytes:
                raise IngestionError(
                    f"Test report exceeds the per-file size limit: {path.name}"
                )
            digest = hashlib.sha256()
            digest.update(
                str(path.relative_to(source_directory)).replace("\\", "/").encode()
            )
            with path.open("rb") as report:
                while chunk := report.read(1024 * 1024):
                    digest.update(chunk)
        except OSError as exc:
            raise IngestionError(f"Could not inspect test report {path.name}: {exc}") from exc
        return digest.hexdigest()

    def _convert_file(self, path: Path) -> str:
        try:
            markdown = self.converter.convert(path).markdown
        except (UnsupportedFormatException, FileConversionException) as exc:
            raise IngestionError(f"Could not convert {path.name}: {exc}") from exc
        except OSError as exc:
            raise IngestionError(f"Could not read {path.name}: {exc}") from exc
        if path.suffix.lower() == ".json":
            markdown = self._compact_repetitive_json(markdown)
        markdown = self._compact_markdown_tables(markdown).strip()
        if len(markdown) > self.max_markdown_chars:
            raise IngestionError(
                f"Converted report exceeds the configured Markdown size limit: {path.name}"
            )
        return markdown

    def _compact_repetitive_json(self, markdown: str) -> str:
        try:
            document = json.loads(markdown)
        except json.JSONDecodeError:
            return markdown

        operation_keys = {"diff operations", "missing operations"}

        def compact(value, key: str | None = None):
            if (
                key is not None
                and key.lower() in operation_keys
                and isinstance(value, dict)
            ):
                categories = list(value.items())
                return {
                    "total_categories": len(categories),
                    "total_items": sum(
                        len(items) if isinstance(items, list) else 1
                        for _category, items in categories
                    ),
                    "sample_categories": {
                        category: items[:3] if isinstance(items, list) else items
                        for category, items in categories[:10]
                    },
                    "truncated_operation_details": True,
                }
            if isinstance(value, dict):
                return {
                    child_key: compact(item, child_key)
                    for child_key, item in value.items()
                }
            if isinstance(value, list):
                primitive = all(
                    item is None or isinstance(item, (str, int, float, bool))
                    for item in value
                )
                if primitive and len(value) > 20:
                    return {
                        "total_items": len(value),
                        "sample_items": value[:20],
                        "truncated_repetitive_values": True,
                    }
                return [compact(item) for item in value]
            return value

        return json.dumps(compact(document), ensure_ascii=False, indent=2)

    def _compact_markdown_tables(self, markdown: str) -> str:
        lines = markdown.splitlines()
        output: list[str] = []
        index = 0
        while index < len(lines):
            if not lines[index].lstrip().startswith("|"):
                output.append(lines[index])
                index += 1
                continue

            end = index
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            table = lines[index:end]
            column_count = max(
                (line.count("|") - 1 for line in table),
                default=0,
            )
            if len(table) <= 22 and column_count <= 40:
                output.extend(table)
            else:
                header_cells = [
                    cell.strip()
                    for cell in table[0].strip().strip("|").split("|")
                ]
                data_rows = max(0, len(table) - 2)
                output.append(
                    f"[Large table compacted: {data_rows} data rows, "
                    f"{column_count} columns]"
                )
                output.append(
                    "Columns (sample): "
                    + ", ".join(header_cells[:20])
                    + (" ..." if len(header_cells) > 20 else "")
                )
                output.append("Sample rows:")
                output.extend(row[:2_000] for row in table[2:7])
            index = end
        return "\n".join(output)
