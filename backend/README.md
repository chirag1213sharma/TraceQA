# TraceQA Backend

Phase 1 provides a FastAPI service, PostgreSQL persistence through SQLAlchemy,
Alembic migrations, and CRUD APIs for test runs, test results, AI insights, and
commit impacts.

Phase 2 adds MarkItDown-based report ingestion, Gemini structured outputs,
QA-ready test analysis, and a signature-verified GitHub push webhook.

## Local setup

```powershell
cd C:\TraceQA\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
docker compose up -d postgres   (docker compose exec db psql -U traceqa -d traceqa)
alembic upgrade head
uvicorn app.main:app --reload
```

OpenAPI documentation is available at `http://localhost:8000/docs`. The health
endpoint is `GET /health`; resource endpoints are under `/api/v1`.

Configuration uses environment variables prefixed with `TRACEQA_`. Copy
`.env.example` to `.env` to override defaults.

## Intelligence workflows

- On application startup, TraceQA scans `TRACEQA_TEST_LOGS_DIRECTORY` and
  automatically ingests new supported reports (`PDF`, `HTML`, `JSON`, `CSV`,
  `XML`, Markdown, and text). Set `TRACEQA_AUTOMATIC_INGESTION_ENABLED=false`
  to disable this behavior.
- `POST /api/v1/ingestion/runs` performs the same incremental scan manually.
  Each report is analyzed by Gemini and persisted as an independent transaction,
  so completed reports remain available if a later report fails. A SHA-256
  identity derived from the report's relative path and contents prevents an
  unchanged completed report from being ingested again; modifying a report
  produces a new identity and makes it eligible for ingestion.
- `POST /api/v1/github/webhooks/push` verifies `X-Hub-Signature-256`, fetches
  the pushed commit diff through the GitHub API, and persists its structured
  regression impact.

The default model is Google Gemini 2.5 Flash through LiteLLM. Set a Gemini API
key in `TRACEQA_LLM_API_KEY`; `TRACEQA_LLM_MODEL` defaults to
`gemini/gemini-2.5-flash`. Each analysis includes aggregate pass/fail counts,
failed test names, an AI analysis, and prioritized instructions for QA. GitHub
workflows still require
`TRACEQA_GITHUB_TOKEN` and `TRACEQA_GITHUB_WEBHOOK_SECRET`. Individual source
reports are limited to 50 MB by default; override
`TRACEQA_INGESTION_MAX_FILE_BYTES` when a controlled environment requires a
different ceiling.

## Frontend integration

Browser access is allowed from origins listed in `TRACEQA_CORS_ORIGINS`
(`http://localhost:3000` by default). Resource feeds support the filters used
by the frontend:

- `GET /api/v1/test-results?run_id={id}`
- `GET /api/v1/ai-test-insights?run_id={id}`
- `GET /api/v1/commit-impacts?branch={branch}`

`GET` and `PUT /api/v1/settings/runtime` power the Settings view. Secret values
are persisted in the ignored local `.env` file, applied immediately, and never
returned by the API; responses expose only configured/not-configured flags.
