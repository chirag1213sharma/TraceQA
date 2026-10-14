# TraceQA

TraceQA is an AI-driven test observability and predictive regression platform
with a FastAPI backend, PostgreSQL database, and Next.js frontend.

## Prerequisites

Install the following before starting:

- Python 3.12 or newer
- Node.js 20 or newer
- Docker Desktop
- A Google Gemini API key

## One-command local deployment

The root launcher prepares both applications, starts PostgreSQL, applies
migrations, creates a production frontend build, launches the backend and
frontend in separate windows, and opens the website:

```powershell
cd C:\TraceQA
.\deploy-local.bat
```

To validate prerequisites and project files without installing dependencies or
starting services:

```powershell
.\deploy-local.bat --check
```

The first full launch can take several minutes while dependencies and Docker
images are downloaded. Later launches reuse the installed dependencies and
Docker volume.

## 1. Start PostgreSQL

Start Docker Desktop from the Windows Start menu and wait until it reports that
the Docker engine is running. Verify the engine before starting PostgreSQL:

```powershell
docker info
```

Open PowerShell and run:

```powershell
cd C:\TraceQA\backend
docker compose up -d postgres
```

Wait until the database is healthy:

```powershell
docker compose ps
```

### Docker engine connection error

If PowerShell reports that it cannot connect to
`dockerDesktopLinuxEngine`, the Docker CLI is installed but the Docker Desktop
engine is not running. Start it with:

```powershell
Start-Process "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
```

Wait for Docker Desktop to finish starting, confirm it is using Linux
containers, and run `docker info` again. If Docker Desktop cannot start, update
WSL and restart Windows:

```powershell
wsl --status
wsl --update
```

In Docker Desktop, ensure **Settings > General > Use the WSL 2 based engine** is
enabled.

## 2. Configure and start the backend

In a PowerShell terminal:

```powershell
cd C:\TraceQA\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `C:\TraceQA\backend\.env` and configure at least:

```dotenv
TRACEQA_DATABASE_URL=postgresql+psycopg://traceqa:traceqa@localhost:5432/traceqa
TRACEQA_TEST_LOGS_DIRECTORY=C:\TraceQA\test-logs
TRACEQA_INGESTION_MAX_FILE_BYTES=52428800
TRACEQA_LLM_MODEL=gemini/gemini-2.5-flash
TRACEQA_LLM_API_BASE=https://generativelanguage.googleapis.com/v1beta
TRACEQA_LLM_REQUEST_TIMEOUT_SECONDS=600
TRACEQA_LLM_MAX_INPUT_CHARS=500000
TRACEQA_LLM_API_KEY=your-gemini-api-key
TRACEQA_GITHUB_TOKEN=your-github-token
TRACEQA_GITHUB_WEBHOOK_SECRET=your-webhook-secret
TRACEQA_CORS_ORIGINS=["http://localhost:3000"]
```

The `gemini/` prefix is LiteLLM's provider identifier. TraceQA sends each
compacted report to Gemini for one structured response containing pass/fail
counts, failed tests, an AI analysis, and prioritized QA instructions. The
Gemini API key is required.

Create the test-log directory if it does not exist:

```powershell
New-Item -ItemType Directory -Force C:\TraceQA\test-logs
```

Apply database migrations and launch FastAPI:

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Keep this terminal open. The backend will be available at:

- API: `http://localhost:8000`
- OpenAPI documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## 3. Configure and start the frontend

Open a second PowerShell terminal:

```powershell
cd C:\TraceQA\frontend
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

The default `C:\TraceQA\frontend\.env.local` should contain:

```dotenv
NEXT_PUBLIC_TRACEQA_API_URL=http://localhost:8000/api/v1
```

Keep this terminal open, then open the website:

`http://localhost:3000`

## Starting TraceQA again

After the initial setup, use three PowerShell terminals.

### Terminal 1: PostgreSQL

```powershell
cd C:\TraceQA\backend
docker compose up -d postgres
```

### Terminal 2: Backend

```powershell
cd C:\TraceQA\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 3: Frontend

```powershell
cd C:\TraceQA\frontend
npm run dev
```

Open `http://localhost:3000`.

## Stop the application

Press `Ctrl+C` in the backend and frontend terminals. Stop PostgreSQL with:

```powershell
cd C:\TraceQA\backend
docker compose down
```

Database data is retained in the Docker volume. To delete that data as well,
run `docker compose down --volumes`.

### Clearing local data

To clear application data while retaining the schema, truncate only TraceQA's
application tables. Do not truncate or delete `alembic_version`: Alembic uses
that table to record the schema revision, and clearing it makes the next
deployment attempt to recreate tables that already exist.

If `alembic_version` was accidentally cleared but the schema is otherwise
current, restore its marker before deploying:

```powershell
cd C:\TraceQA\backend
.\.venv\Scripts\python.exe -m alembic stamp head
```
