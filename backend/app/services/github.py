import hashlib
import hmac

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CommitImpact
from app.schemas import CommitRadarRead, GitHubPushEvent
from app.services.ai import (
    AIConfigurationError,
    AIRequestError,
    AIResponseError,
    AIService,
)


class GitHubConfigurationError(RuntimeError):
    pass


class GitHubRequestError(RuntimeError):
    pass


class GitHubSignatureError(RuntimeError):
    pass


def verify_github_signature(
    body: bytes,
    signature: str | None,
    secret: str | None,
) -> None:
    if not secret:
        raise GitHubConfigurationError(
            "TRACEQA_GITHUB_WEBHOOK_SECRET is not configured"
        )
    if not signature or not signature.startswith("sha256="):
        raise GitHubSignatureError("Missing or invalid GitHub webhook signature")
    expected = "sha256=" + hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise GitHubSignatureError("GitHub webhook signature verification failed")


class GitHubService:
    def __init__(
        self,
        *,
        ai_service: AIService,
        token: str | None,
        client: httpx.Client | None = None,
        max_diff_chars: int = 500_000,
    ) -> None:
        self.ai_service = ai_service
        self.token = token
        self.client = client
        self.max_diff_chars = max_diff_chars

    def process_push(
        self,
        db: Session,
        event: GitHubPushEvent,
    ) -> CommitRadarRead:
        branch = event.ref.removeprefix("refs/heads/")
        if event.deleted:
            raise GitHubRequestError("Branch deletion push events are not analyzed")
        existing = db.scalar(
            select(CommitImpact).where(
                CommitImpact.commit_hash == event.after,
                CommitImpact.branch == branch,
            )
        )
        if existing is not None:
            return CommitRadarRead(impact=existing, impacted_modules=[])

        try:
            diff = self._fetch_diff(event.repository.full_name, event.after)
            analysis = self.ai_service.analyze_commit_diff(diff)
            impact = CommitImpact(
                commit_hash=event.after,
                branch=branch,
                summary=analysis.summary,
                regression_risk_level=analysis.regression_risk_level.value,
                suggested_automated_tests=analysis.suggested_automated_tests,
                suggested_manual_tests=[
                    test.model_dump(mode="json")
                    for test in analysis.suggested_manual_tests
                ],
            )
            db.add(impact)
            db.commit()
            db.refresh(impact)
        except IntegrityError:
            db.rollback()
            existing = db.scalar(
                select(CommitImpact).where(
                    CommitImpact.commit_hash == event.after,
                    CommitImpact.branch == branch,
                )
            )
            if existing is None:
                raise
            impact = existing
        except (
            AIConfigurationError,
            AIRequestError,
            AIResponseError,
            SQLAlchemyError,
        ):
            db.rollback()
            raise
        return CommitRadarRead(
            impact=impact,
            impacted_modules=analysis.impacted_modules,
        )

    def _fetch_diff(self, repository: str, commit_hash: str) -> str:
        if not self.token:
            raise GitHubConfigurationError("TRACEQA_GITHUB_TOKEN is not configured")
        headers = {
            "Accept": "application/vnd.github.diff",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"https://api.github.com/repos/{repository}/commits/{commit_hash}"
        try:
            if self.client is not None:
                response = self.client.get(url, headers=headers)
            else:
                response = httpx.get(url, headers=headers, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GitHubRequestError(f"Could not fetch GitHub commit diff: {exc}") from exc
        if not response.text.strip():
            raise GitHubRequestError("GitHub returned an empty commit diff")
        if len(response.text) > self.max_diff_chars:
            raise GitHubRequestError(
                "GitHub commit diff exceeds the configured size limit"
            )
        return response.text
