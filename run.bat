@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================================================
rem run.bat - F-RL-V1 All-in-One Startup Script for Windows
rem Starts Go backend, React frontend, and optionally the Python execution API.
rem All output is logged to logs\ with timestamps.
rem ============================================================================

set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"
set "LOG_DIR=%REPO_ROOT%\logs"
set "BACKEND_DIR=%REPO_ROOT%\Backend"
set "FRONTEND_DIR=%REPO_ROOT%\Frontend"
set "PYTHON_DIR=%REPO_ROOT%\btc-hybrid-trader"

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "RUN_TS=%%I"
set "LOG_MAIN=%LOG_DIR%\run_%RUN_TS%.log"
set "LOG_BACKEND=%LOG_DIR%\backend_%RUN_TS%.log"
set "LOG_FRONTEND=%LOG_DIR%\frontend_%RUN_TS%.log"
set "LOG_EXEC_API=%LOG_DIR%\exec_api_%RUN_TS%.log"
set "LOG_PIPELINE=%LOG_DIR%\pipeline_%RUN_TS%.log"

if defined PORT (
    set "BACKEND_PORT=%PORT%"
) else (
    set "BACKEND_PORT=8080"
)
set "FRONTEND_PORT=5173"
set "EXEC_API_PORT=8000"

set "BACKEND_PID="
set "FRONTEND_PID="
set "EXEC_API_PID="

set "OPT_EXEC_API=false"
set "OPT_PIPELINE=false"
set "OPT_TESTS=false"
set "OPT_FRONTEND=true"
set "OPT_BACKEND=true"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="--with-exec-api" (
    set "OPT_EXEC_API=true"
    shift
    goto parse_args
)
if /I "%~1"=="--run-pipeline" (
    set "OPT_PIPELINE=true"
    shift
    goto parse_args
)
if /I "%~1"=="--run-tests" (
    set "OPT_TESTS=true"
    shift
    goto parse_args
)
if /I "%~1"=="--no-frontend" (
    set "OPT_FRONTEND=false"
    shift
    goto parse_args
)
if /I "%~1"=="--no-backend" (
    set "OPT_BACKEND=false"
    shift
    goto parse_args
)
if /I "%~1"=="-h" goto help
if /I "%~1"=="--help" goto help
call :error "Unknown option: %~1"
goto help_error

:args_done
cls
echo ============================================================
echo F-RL-V1 BTC Hybrid Trading System - Startup Script
echo ============================================================
echo.

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
call :info "Logging to: %LOG_DIR%"
call :info "Run log:    %LOG_MAIN%"

call :header "Checking prerequisites"
call :check_cmd go || exit /b 1
call :check_cmd node || exit /b 1
call :check_cmd npm || exit /b 1
call :check_cmd python || exit /b 1

for /f "delims=" %%I in ('go version') do set "GO_VER=%%I"
for /f "delims=" %%I in ('node --version') do set "NODE_VER=%%I"
for /f "delims=" %%I in ('python --version') do set "PYTHON_VER=%%I"
call :success "Go:     %GO_VER%"
call :success "Node:   %NODE_VER%"
call :success "Python: %PYTHON_VER%"

if /I "%OPT_TESTS%"=="true" goto run_tests

if /I "%OPT_BACKEND%"=="true" call :start_backend || goto fail
if /I "%OPT_FRONTEND%"=="true" call :start_frontend || goto fail
if /I "%OPT_EXEC_API%"=="true" call :start_exec_api || goto fail
if /I "%OPT_PIPELINE%"=="true" call :run_pipeline || goto fail

call :header "Services running"
if /I "%OPT_BACKEND%"=="true" echo   [OK] Go API         http://localhost:%BACKEND_PORT%
if /I "%OPT_FRONTEND%"=="true" echo   [OK] React Dashboard http://localhost:%FRONTEND_PORT%
if /I "%OPT_EXEC_API%"=="true" echo   [OK] Execution API   http://localhost:%EXEC_API_PORT%
echo.
echo   Logs directory: %LOG_DIR%
echo.
echo   Press any key to stop all services.
echo.
pause >nul
call :cleanup
exit /b 0

:run_tests
call :header "Running test suites"
call :ensure_python_venv || goto fail

call :info "Running Python tests..."
pushd "%PYTHON_DIR%" >nul
"%VENV_PYTHON%" -m pytest tests/ -v >> "%LOG_PIPELINE%" 2>&1
set "PYTEST_EXIT=%ERRORLEVEL%"
popd >nul
if "%PYTEST_EXIT%"=="0" (
    call :success "Python tests passed"
) else (
    call :error "Python tests FAILED - see %LOG_PIPELINE%"
    set "TEST_FAILED=1"
)

call :info "Running Go tests..."
pushd "%BACKEND_DIR%" >nul
go test ./... >> "%LOG_BACKEND%" 2>&1
set "GOTEST_EXIT=%ERRORLEVEL%"
popd >nul
if "%GOTEST_EXIT%"=="0" (
    call :success "Go tests passed"
) else (
    call :error "Go tests FAILED - see %LOG_BACKEND%"
    set "TEST_FAILED=1"
)

if defined TEST_FAILED exit /b 1
exit /b 0

:start_backend
call :header "Setting up Go backend"
call :check_port_free "%BACKEND_PORT%" "Go backend"

if not exist "%BACKEND_DIR%\.env" (
    call :warn ".env not found in Backend - copying from .env.example"
    copy /Y "%BACKEND_DIR%\.env.example" "%BACKEND_DIR%\.env" >nul
)

call :info "Running: go mod tidy"
pushd "%BACKEND_DIR%" >nul
go mod tidy >> "%LOG_BACKEND%" 2>&1
set "GO_TIDY_EXIT=%ERRORLEVEL%"
popd >nul
if not "%GO_TIDY_EXIT%"=="0" (
    call :error "go mod tidy failed - see %LOG_BACKEND%"
    exit /b 1
)

call :info "Starting Go backend on :%BACKEND_PORT%..."
call :start_background_process "%BACKEND_DIR%" "go run ./cmd/server" "%LOG_BACKEND%" BACKEND_PID
if not defined BACKEND_PID (
    call :error "Failed to start Go backend"
    exit /b 1
)
call :success "Go backend started (PID %BACKEND_PID%) - log: %LOG_BACKEND%"

call :info "Waiting for backend to be ready..."
for /l %%I in (1,1,15) do (
    powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing 'http://localhost:%BACKEND_PORT%/api/health' -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
    if "!ERRORLEVEL!"=="0" (
        call :success "Backend is ready at http://localhost:%BACKEND_PORT%"
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)
call :warn "Backend health check timed out. It may still be starting."
exit /b 0

:start_frontend
call :header "Setting up React frontend"
call :check_port_free "%FRONTEND_PORT%" "React dev server"

if not exist "%FRONTEND_DIR%\node_modules" (
    call :info "node_modules not found - running npm install..."
    pushd "%FRONTEND_DIR%" >nul
    npm install >> "%LOG_FRONTEND%" 2>&1
    set "NPM_INSTALL_EXIT=%ERRORLEVEL%"
    popd >nul
    if not "%NPM_INSTALL_EXIT%"=="0" (
        call :error "npm install failed - see %LOG_FRONTEND%"
        exit /b 1
    )
)

call :info "Starting React dev server on :%FRONTEND_PORT%..."
call :start_background_process "%FRONTEND_DIR%" "npm run dev" "%LOG_FRONTEND%" FRONTEND_PID
if not defined FRONTEND_PID (
    call :error "Failed to start React frontend"
    exit /b 1
)
call :success "React frontend started (PID %FRONTEND_PID%) - log: %LOG_FRONTEND%"
exit /b 0

:start_exec_api
call :header "Setting up Python execution API"
call :check_port_free "%EXEC_API_PORT%" "Python FastAPI"
call :ensure_python_venv || exit /b 1

call :info "Starting FastAPI execution server on :%EXEC_API_PORT%..."
call :start_background_process "%PYTHON_DIR%" """%VENV_PYTHON%"" -m uvicorn src.execution.api:app --host 0.0.0.0 --port %EXEC_API_PORT%" "%LOG_EXEC_API%" EXEC_API_PID
if not defined EXEC_API_PID (
    call :error "Failed to start execution API"
    exit /b 1
)
call :success "Execution API started (PID %EXEC_API_PID%) - log: %LOG_EXEC_API%"
exit /b 0

:run_pipeline
call :header "Running ML pipeline (7 stages)"
call :ensure_python_venv || exit /b 1

call :info "Pipeline log: %LOG_PIPELINE%"
call :info "This may take a long time (XGBoost + RL training)..."
pushd "%PYTHON_DIR%" >nul
"%VENV_PYTHON%" -c "from src.pipeline.orchestrator import PipelineOrchestrator; pipeline = PipelineOrchestrator(); pipeline.run()" >> "%LOG_PIPELINE%" 2>&1
set "PIPELINE_EXIT=%ERRORLEVEL%"
popd >nul
if "%PIPELINE_EXIT%"=="0" (
    call :success "ML pipeline complete - see %LOG_PIPELINE%"
    exit /b 0
)

call :error "ML pipeline failed - see %LOG_PIPELINE%"
exit /b 1

:ensure_python_venv
set "VENV_PYTHON=%PYTHON_DIR%\.venv\Scripts\python.exe"
if exist "%VENV_PYTHON%" exit /b 0

call :warn "Python venv not found at %PYTHON_DIR%\.venv - creating it now"
python -m venv "%PYTHON_DIR%\.venv" >> "%LOG_PIPELINE%" 2>&1
if not "%ERRORLEVEL%"=="0" (
    call :error "Failed to create Python virtual environment - see %LOG_PIPELINE%"
    exit /b 1
)

"%PYTHON_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip >> "%LOG_PIPELINE%" 2>&1
if not "%ERRORLEVEL%"=="0" (
    call :error "Failed to upgrade pip - see %LOG_PIPELINE%"
    exit /b 1
)

"%PYTHON_DIR%\.venv\Scripts\python.exe" -m pip install -r "%PYTHON_DIR%\requirements.txt" >> "%LOG_PIPELINE%" 2>&1
if not "%ERRORLEVEL%"=="0" (
    call :error "Failed to install Python requirements - see %LOG_PIPELINE%"
    exit /b 1
)

call :success "Python venv ready"
set "VENV_PYTHON=%PYTHON_DIR%\.venv\Scripts\python.exe"
exit /b 0

:start_background_process
set "START_DIR=%~1"
set "START_CMD=%~2"
set "START_LOG=%~3"
set "PID_VAR=%~4"
set "PS_SCRIPT=$p = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'cd /d ""%START_DIR%"" && %START_CMD% >> ""%START_LOG%"" 2>&1' -WindowStyle Hidden -PassThru; $p.Id"
for /f %%I in ('powershell -NoProfile -Command "!PS_SCRIPT!"') do set "%PID_VAR%=%%I"
exit /b 0

:check_cmd
where /q %~1
if "%ERRORLEVEL%"=="0" exit /b 0
call :error "Required command not found: %~1"
call :error "See howto.md section 'Prerequisites' for installation instructions."
exit /b 1

:check_port_free
powershell -NoProfile -Command "$conn = Get-NetTCPConnection -State Listen -LocalPort %~1 -ErrorAction SilentlyContinue | Select-Object -First 1; if ($conn) { exit 0 } else { exit 1 }" >nul 2>&1
if "%ERRORLEVEL%"=="0" call :warn "Port %~1 is already in use (%~2). The service may fail to start."
exit /b 0

:cleanup
echo.
call :header "Shutting down all services"
for %%V in (BACKEND_PID FRONTEND_PID EXEC_API_PID) do (
    set "CURRENT_PID=!%%V!"
    if defined CURRENT_PID (
        tasklist /FI "PID eq !CURRENT_PID!" | findstr /R /C:" !CURRENT_PID! " >nul 2>&1
        if "!ERRORLEVEL!"=="0" (
            call :info "Stopping PID !CURRENT_PID! (%%V)..."
            taskkill /PID !CURRENT_PID! /T /F >nul 2>&1
        )
    )
)
call :info "All services stopped. Logs in: %LOG_DIR%"
exit /b 0

:log
set "LOG_LEVEL=%~1"
set "LOG_MESSAGE=%~2"
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd HH:mm:ss'"') do set "LOG_TS=%%I"
echo %LOG_TS% [%LOG_LEVEL%] %LOG_MESSAGE%
>> "%LOG_MAIN%" echo %LOG_TS% [%LOG_LEVEL%] %LOG_MESSAGE%
exit /b 0

:info
call :log INFO "%~1"
exit /b 0

:success
call :log OK "%~1"
exit /b 0

:warn
call :log WARN "%~1"
exit /b 0

:error
call :log ERR "%~1"
exit /b 0

:header
echo.
echo === %~1 ===
echo.
>> "%LOG_MAIN%" echo.
>> "%LOG_MAIN%" echo === %~1 ===
>> "%LOG_MAIN%" echo.
exit /b 0

:help
echo Usage: run.bat [OPTIONS]
echo.
echo Options:
echo   --with-exec-api      Also start the Python FastAPI execution webhook (:%EXEC_API_PORT%)
echo   --run-pipeline       Run the full 7-stage ML pipeline (blocking, runs after services start)
echo   --run-tests          Run all tests (Python pytest + Go) then exit
echo   --no-frontend        Skip the React dev server
echo   --no-backend         Skip the Go API server
echo   -h, --help           Show this help
echo.
echo Examples:
echo   run.bat
echo   run.bat --with-exec-api
echo   run.bat --run-pipeline
echo   run.bat --run-tests
exit /b 0

:help_error
call :help
exit /b 1

:fail
set "FAIL_CODE=%ERRORLEVEL%"
call :cleanup
exit /b %FAIL_CODE%
