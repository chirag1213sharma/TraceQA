import logging
from contextlib import asynccontextmanager
from threading import Thread
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.api.workflows import (
    build_ai_service,
    build_ingestion_service,
    router as workflow_router,
)
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.ai import AIConfigurationError, AIRequestError, AIResponseError
from app.services.ingestion import IngestionError

logger = logging.getLogger(__name__)


def configure_application_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )


def ingest_new_reports_on_startup() -> None:
    """Run report ingestion outside the startup request path."""
    settings = get_settings()
    try:
        with SessionLocal() as db:
            service = build_ingestion_service(settings, build_ai_service(settings))
            result = service.ingest(db, settings.test_logs_directory)
            logger.info(
                "Startup ingestion completed: %s new report file(s)",
                len(result.processed_files),
            )
    except (
        IngestionError,
        AIConfigurationError,
        AIRequestError,
        AIResponseError,
        SQLAlchemyError,
    ) as exc:
        logger.warning("Startup ingestion did not complete: %s", exc)


@asynccontextmanager
async def application_lifespan(_application: FastAPI) -> AsyncIterator[None]:
    if get_settings().automatic_ingestion_enabled:
        Thread(
            target=ingest_new_reports_on_startup,
            name="traceqa-report-ingestion",
            daemon=True,
        ).start()
    yield


def create_app() -> FastAPI:
    configure_application_logging()
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=application_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(router, prefix=settings.api_v1_prefix)
    application.include_router(workflow_router, prefix=settings.api_v1_prefix)

    @application.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
