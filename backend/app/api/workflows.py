import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas import (
    CommitRadarRead,
    GitHubPushEvent,
    IngestionRead,
    RuntimeSettingsRead,
    RuntimeSettingsUpdate,
)
from app.services.ai import (
    AIConfigurationError,
    AIRequestError,
    AIResponseError,
    AIService,
)
from app.services.github import (
    GitHubConfigurationError,
    GitHubRequestError,
    GitHubService,
    GitHubSignatureError,
    verify_github_signature,
)
from app.services.ingestion import IngestionError, IngestionService
from app.services.settings import RuntimeSettingsStore
from app.core.config import SETTINGS_ENV_FILE

router = APIRouter(tags=["workflows"])
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def build_ai_service(settings: AppSettings) -> AIService:
    api_key = (
        settings.llm_api_key.get_secret_value()
        if settings.llm_api_key is not None
        else None
    )
    return AIService(
        model=settings.llm_model,
        api_key=api_key,
        api_base=settings.llm_api_base,
        request_timeout_seconds=settings.llm_request_timeout_seconds,
        max_input_chars=settings.llm_max_input_chars,
    )


def build_ingestion_service(
    settings: AppSettings,
    ai_service: Annotated[AIService, Depends(build_ai_service)],
) -> IngestionService:
    return IngestionService(
        ai_service=ai_service,
        max_files=settings.ingestion_max_files,
        max_file_bytes=settings.ingestion_max_file_bytes,
        max_markdown_chars=settings.ingestion_max_markdown_chars,
        max_llm_input_chars=settings.llm_max_input_chars,
    )


def build_github_service(
    settings: AppSettings,
    ai_service: Annotated[AIService, Depends(build_ai_service)],
) -> GitHubService:
    token = (
        settings.github_token.get_secret_value()
        if settings.github_token is not None
        else None
    )


def build_runtime_settings_store() -> RuntimeSettingsStore:
    return RuntimeSettingsStore(SETTINGS_ENV_FILE)
    return GitHubService(
        ai_service=ai_service,
        token=token,
        max_diff_chars=settings.github_diff_max_chars,
    )


@router.post("/ingestion/runs", response_model=IngestionRead, status_code=201)
def ingest_test_reports(
    db: DbSession,
    settings: AppSettings,
    service: Annotated[IngestionService, Depends(build_ingestion_service)],
) -> IngestionRead:
    try:
        return service.ingest(db, settings.test_logs_directory)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/github/webhooks/push", response_model=CommitRadarRead)
async def github_push_webhook(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    service: Annotated[GitHubService, Depends(build_github_service)],
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str | None, Header()] = None,
) -> CommitRadarRead:
    body = await request.body()
    secret = (
        settings.github_webhook_secret.get_secret_value()
        if settings.github_webhook_secret is not None
        else None
    )
    try:
        verify_github_signature(body, x_hub_signature_256, secret)
        if x_github_event != "push":
            raise HTTPException(
                status_code=422,
                detail="Only GitHub push events are supported",
            )
        payload = GitHubPushEvent.model_validate(json.loads(body))
        return service.process_push(db, payload)
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail="Invalid GitHub push payload") from exc
    except GitHubConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GitHubSignatureError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except GitHubRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except AIRequestError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/settings/runtime", response_model=RuntimeSettingsRead)
def read_runtime_settings(
    store: Annotated[RuntimeSettingsStore, Depends(build_runtime_settings_store)],
) -> RuntimeSettingsRead:
    return store.read()


@router.put("/settings/runtime", response_model=RuntimeSettingsRead)
def update_runtime_settings(
    payload: RuntimeSettingsUpdate,
    store: Annotated[RuntimeSettingsStore, Depends(build_runtime_settings_store)],
) -> RuntimeSettingsRead:
    return store.update(payload)
