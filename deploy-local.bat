@echo off
setlocal EnableExtensions

set "ROOT_DIR=%~dp0"
set "BACKEND_DIR=%ROOT_DIR%backend"
set "FRONTEND_DIR=%ROOT_DIR%frontend"
set "CHECK_ONLY=0"

if /I "%~1"=="--check" set "CHECK_ONLY=1"

echo.
echo ============================================================
echo  TraceQA Local Deployment
echo ============================================================
echo.

call :require_command python "Python 3.12 or newer"
if errorlevel 1 goto :failed
call :require_command node "Node.js 20 or newer"
if errorlevel 1 goto :failed
call :require_command npm "npm"
if errorlevel 1 goto :failed
call :require_command docker "Docker Desktop"
if errorlevel 1 goto :failed
if not exist "%BACKEND_DIR%\pyproject.toml" (
    echo [ERROR] Backend project not found at "%BACKEND_DIR%".
    goto :failed
)
if not exist "%FRONTEND_DIR%\package.json" (
    echo [ERROR] Frontend project not found at "%FRONTEND_DIR%".
    goto :failed
)

if "%CHECK_ONLY%"=="1" (
    echo [OK] Required commands and TraceQA project files are available.
    echo [OK] Validation completed without starting any services.
    exit /b 0
)

echo [1/8] Checking Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
    set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    if not exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
        echo [ERROR] Docker Desktop is installed but its engine is not running.
        echo         Start Docker Desktop and run this file again.
        goto :failed
    )
    echo       Starting Docker Desktop. This can take up to two minutes...
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    for /L %%I in (1,1,60) do (
        docker info >nul 2>&1 && goto :docker_ready
        timeout /t 2 /nobreak >nul
    )
    echo [ERROR] Docker Desktop did not become ready in time.
    goto :failed
)

:docker_ready
echo       Docker engine is ready.

echo [2/8] Starting PostgreSQL...
pushd "%BACKEND_DIR%"
docker compose up -d --force-recreate postgres
if errorlevel 1 (
    popd
    echo [ERROR] PostgreSQL could not be started.
    goto :failed
)

echo       Waiting for PostgreSQL health checks...
for /L %%I in (1,1,30) do (
    docker compose exec -T postgres pg_isready -U traceqa -d traceqa >nul 2>&1 && goto :database_ready
    timeout /t 2 /nobreak >nul
)
popd
echo [ERROR] PostgreSQL did not become ready in time.
goto :failed

:database_ready
popd
echo       PostgreSQL is ready.

echo [3/8] Preparing backend configuration...
if not exist "%BACKEND_DIR%\.env" (
    copy /Y "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
    echo       Created backend\.env from .env.example.
    echo       API credentials can be configured later in TraceQA Settings.
)
if not exist "%ROOT_DIR%test-logs" mkdir "%ROOT_DIR%test-logs"

echo [4/8] Preparing the Python environment...
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
    python -m venv "%BACKEND_DIR%\.venv"
    if errorlevel 1 (
        echo [ERROR] Python virtual environment creation failed.
        goto :failed
    )
)
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -e "%BACKEND_DIR%[dev]" --quiet
if errorlevel 1 (
    echo [ERROR] Backend dependency installation failed.
    goto :failed
)

echo [5/8] Applying database migrations...
pushd "%BACKEND_DIR%"
".venv\Scripts\python.exe" -m alembic upgrade head
if errorlevel 1 (
    popd
    echo [ERROR] Database migration failed.
    goto :failed
)
popd

echo [6/8] Preparing and building the frontend...
if not exist "%FRONTEND_DIR%\.env.local" (
    copy /Y "%FRONTEND_DIR%\.env.local.example" "%FRONTEND_DIR%\.env.local" >nul
)
pushd "%FRONTEND_DIR%"
call npm install
if errorlevel 1 (
    popd
    echo [ERROR] Frontend dependency installation failed.
    goto :failed
)
call npm run build
if errorlevel 1 (
    popd
    echo [ERROR] Frontend production build failed.
    goto :failed
)
popd

echo [7/8] Launching TraceQA services...
call :url_ready "http://localhost:8000/health"
if errorlevel 1 (
    start "TraceQA Backend" /D "%BACKEND_DIR%" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
) else (
    echo       Backend is already running.
)

call :url_ready "http://localhost:3000"
if errorlevel 1 (
    start "TraceQA Frontend" /D "%FRONTEND_DIR%" cmd /k "npm start"
) else (
    echo       Frontend is already running.
)

echo [8/8] Waiting for TraceQA...
for /L %%I in (1,1,30) do (
    call :url_ready "http://localhost:8000/health" && goto :backend_ready
    timeout /t 1 /nobreak >nul
)
echo [ERROR] Backend did not become ready. Review the TraceQA Backend window.
goto :failed

:backend_ready
for /L %%I in (1,1,30) do (
    call :url_ready "http://localhost:3000" && goto :application_ready
    timeout /t 1 /nobreak >nul
)
echo [ERROR] Frontend did not become ready. Review the TraceQA Frontend window.
goto :failed

:application_ready
echo.
echo ============================================================
echo  TraceQA is running
echo  Website: http://localhost:3000
echo  API docs: http://localhost:8000/docs
echo ============================================================
echo.
start "" "http://localhost:3000"
exit /b 0

:require_command
where %~1 >nul 2>&1
if errorlevel 1 (
    echo [ERROR] %~2 is required but was not found in PATH.
    exit /b 1
)
exit /b 0

:url_ready
powershell -NoProfile -Command "try { $response = Invoke-WebRequest -Uri '%~1' -UseBasicParsing -TimeoutSec 2; if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) { exit 0 }; exit 1 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:failed
echo.
echo TraceQA local deployment did not complete.
echo Resolve the error above, then run deploy-local.bat again.
exit /b 1
