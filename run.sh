#!/usr/bin/env bash
# =============================================================================
# run.sh — F-RL-V1 All-in-One Startup Script
# Starts Go backend, React frontend, and optionally the Python execution API.
# All output is logged to logs/ with timestamps.
# =============================================================================

set -euo pipefail

# ─── Paths ──────────────────────────────────────────────────────────────────
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$REPO_ROOT/logs"
BACKEND_DIR="$REPO_ROOT/Backend"
FRONTEND_DIR="$REPO_ROOT/Frontend"
PYTHON_DIR="$REPO_ROOT/btc-hybrid-trader"

# ─── Log file names (timestamped per run) ────────────────────────────────────
RUN_TS="$(date +%Y%m%d_%H%M%S)"
LOG_MAIN="$LOG_DIR/run_${RUN_TS}.log"
LOG_BACKEND="$LOG_DIR/backend_${RUN_TS}.log"
LOG_FRONTEND="$LOG_DIR/frontend_${RUN_TS}.log"
LOG_EXEC_API="$LOG_DIR/exec_api_${RUN_TS}.log"
LOG_PIPELINE="$LOG_DIR/pipeline_${RUN_TS}.log"

# ─── Ports ───────────────────────────────────────────────────────────────────
BACKEND_PORT="${PORT:-8080}"
FRONTEND_PORT=5173
EXEC_API_PORT=8000

# ─── PIDs (tracked for clean shutdown) ───────────────────────────────────────
BACKEND_PID=""
FRONTEND_PID=""
EXEC_API_PID=""

# ─── Colours ─────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ─── Helpers ─────────────────────────────────────────────────────────────────
log() {
    local level="$1"; shift
    local msg="$*"
    local ts; ts="$(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "${ts} [${level}] ${msg}" | tee -a "$LOG_MAIN"
}

info()    { log "${CYAN}INFO${RESET} " "$@"; }
success() { log "${GREEN}OK  ${RESET} " "$@"; }
warn()    { log "${YELLOW}WARN${RESET} " "$@"; }
error()   { log "${RED}ERR ${RESET} " "$@"; }
header()  { echo -e "\n${BOLD}${CYAN}=== $* ===${RESET}\n" | tee -a "$LOG_MAIN"; }

# ─── Cleanup on exit ─────────────────────────────────────────────────────────
cleanup() {
    echo ""
    header "Shutting down all services"
    for pid_var in BACKEND_PID FRONTEND_PID EXEC_API_PID; do
        pid="${!pid_var}"
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            info "Stopping PID $pid ($pid_var)..."
            kill "$pid" 2>/dev/null || true
        fi
    done
    info "All services stopped. Logs in: $LOG_DIR/"
}
trap cleanup EXIT INT TERM

# ─── Prerequisite checks ─────────────────────────────────────────────────────
check_cmd() {
    if ! command -v "$1" &>/dev/null; then
        error "Required command not found: $1"
        error "See howto.md §Prerequisites for installation instructions."
        exit 1
    fi
}

check_port_free() {
    local port="$1" name="$2"
    if lsof -iTCP:"$port" -sTCP:LISTEN -t &>/dev/null 2>&1; then
        warn "Port $port is already in use ($name). The service may fail to start."
    fi
}

# ─── Usage ───────────────────────────────────────────────────────────────────
usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Options:
  --with-exec-api      Also start the Python FastAPI execution webhook (:${EXEC_API_PORT})
  --run-pipeline       Run the full 7-stage ML pipeline (blocking, runs after services start)
  --run-tests          Run all tests (Python pytest + Go) then exit
  --no-frontend        Skip the React dev server
  --no-backend         Skip the Go API server
  -h, --help           Show this help

Examples:
  ./run.sh                          # Start Go backend + React frontend
  ./run.sh --with-exec-api          # + Python execution API
  ./run.sh --run-pipeline           # + Run ML pipeline after startup
  ./run.sh --run-tests              # Run test suites only
EOF
}

# ─── Parse flags ─────────────────────────────────────────────────────────────
OPT_EXEC_API=false
OPT_PIPELINE=false
OPT_TESTS=false
OPT_FRONTEND=true
OPT_BACKEND=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-exec-api)   OPT_EXEC_API=true ;;
        --run-pipeline)    OPT_PIPELINE=true ;;
        --run-tests)       OPT_TESTS=true ;;
        --no-frontend)     OPT_FRONTEND=false ;;
        --no-backend)      OPT_BACKEND=false ;;
        -h|--help)         usage; exit 0 ;;
        *) error "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
done

# ─── Banner ───────────────────────────────────────────────────────────────────
clear
echo -e "${BOLD}${CYAN}"
cat <<'BANNER'
  ███████╗      ██████╗ ██╗      ██╗   ██╗ ██╗
  ██╔════╝      ██╔══██╗██║      ██║   ██║ ██║
  █████╗  █████╗██████╔╝██║█████╗██║   ██║ ██║
  ██╔══╝  ╚════╝██╔══██╗██║╚════╝╚██╗ ██╔╝ ╚═╝
  ██║           ██║  ██║███████╗  ╚████╔╝  ██╗
  ╚═╝           ╚═╝  ╚═╝╚══════╝   ╚═══╝   ╚═╝
  BTC Hybrid Trading System — Startup Script
BANNER
echo -e "${RESET}"

# ─── Create log directory ─────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"
info "Logging to: $LOG_DIR/"
info "Run log:    $LOG_MAIN"

# ─── Check prerequisites ─────────────────────────────────────────────────────
header "Checking prerequisites"
check_cmd go
check_cmd node
check_cmd npm
check_cmd python3

GO_VER="$(go version | awk '{print $3}')"
NODE_VER="$(node --version)"
PYTHON_VER="$(python3 --version)"
success "Go:     $GO_VER"
success "Node:   $NODE_VER"
success "Python: $PYTHON_VER"

# ─── Tests only mode ─────────────────────────────────────────────────────────
if $OPT_TESTS; then
    header "Running test suites"

    info "Running Python tests..."
    VENV_PYTHON="$PYTHON_DIR/.venv/bin/python"
    if [[ ! -f "$VENV_PYTHON" ]]; then
        warn "Python venv not found at $PYTHON_DIR/.venv — creating it now"
        python3 -m venv "$PYTHON_DIR/.venv"
        "$PYTHON_DIR/.venv/bin/pip" install -q --upgrade pip
        "$PYTHON_DIR/.venv/bin/pip" install -q -r "$PYTHON_DIR/requirements.txt"
    fi
    (
        cd "$PYTHON_DIR"
        "$VENV_PYTHON" -m pytest tests/ -v 2>&1 | tee -a "$LOG_PIPELINE"
    ) && success "Python tests passed" || error "Python tests FAILED — see $LOG_PIPELINE"

    info "Running Go tests..."
    (
        cd "$BACKEND_DIR"
        go test ./... 2>&1 | tee -a "$LOG_BACKEND"
    ) && success "Go tests passed" || error "Go tests FAILED — see $LOG_BACKEND"

    exit 0
fi

# ─── Setup: Go backend ────────────────────────────────────────────────────────
if $OPT_BACKEND; then
    header "Setting up Go backend"
    check_port_free "$BACKEND_PORT" "Go backend"

    if [[ ! -f "$BACKEND_DIR/.env" ]]; then
        warn ".env not found in Backend/ — copying from .env.example"
        cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
    fi

    info "Running: go mod tidy"
    (cd "$BACKEND_DIR" && go mod tidy 2>&1 | tee -a "$LOG_BACKEND")

    info "Starting Go backend on :${BACKEND_PORT}..."
    (
        cd "$BACKEND_DIR"
        go run ./cmd/server 2>&1 | while IFS= read -r line; do
            echo "$(date '+%Y-%m-%d %H:%M:%S') [backend] $line"
        done
    ) >> "$LOG_BACKEND" 2>&1 &
    BACKEND_PID=$!
    success "Go backend started (PID $BACKEND_PID) — log: $LOG_BACKEND"

    # Wait for backend to be ready (up to 15s)
    info "Waiting for backend to be ready..."
    for i in $(seq 1 15); do
        if curl -sf "http://localhost:${BACKEND_PORT}/api/health" &>/dev/null; then
            success "Backend is ready at http://localhost:${BACKEND_PORT}"
            break
        fi
        sleep 1
        if [[ $i -eq 15 ]]; then
            warn "Backend health check timed out. It may still be starting."
        fi
    done
fi

# ─── Setup: React frontend ────────────────────────────────────────────────────
if $OPT_FRONTEND; then
    header "Setting up React frontend"
    check_port_free "$FRONTEND_PORT" "React dev server"

    if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
        info "node_modules not found — running npm install..."
        (cd "$FRONTEND_DIR" && npm install 2>&1 | tee -a "$LOG_FRONTEND")
    fi

    info "Starting React dev server on :${FRONTEND_PORT}..."
    (
        cd "$FRONTEND_DIR"
        npm run dev 2>&1 | while IFS= read -r line; do
            echo "$(date '+%Y-%m-%d %H:%M:%S') [frontend] $line"
        done
    ) >> "$LOG_FRONTEND" 2>&1 &
    FRONTEND_PID=$!
    success "React frontend started (PID $FRONTEND_PID) — log: $LOG_FRONTEND"
fi

# ─── Setup: Python execution API (optional) ───────────────────────────────────
if $OPT_EXEC_API; then
    header "Setting up Python execution API"
    check_port_free "$EXEC_API_PORT" "Python FastAPI"

    VENV_PYTHON="$PYTHON_DIR/.venv/bin/python"
    if [[ ! -f "$VENV_PYTHON" ]]; then
        info "Python venv not found — creating it..."
        python3 -m venv "$PYTHON_DIR/.venv"
        "$PYTHON_DIR/.venv/bin/pip" install -q --upgrade pip
        "$PYTHON_DIR/.venv/bin/pip" install -q -r "$PYTHON_DIR/requirements.txt"
        success "Python venv ready"
    fi

    info "Starting FastAPI execution server on :${EXEC_API_PORT}..."
    (
        cd "$PYTHON_DIR"
        "$PYTHON_DIR/.venv/bin/uvicorn" src.execution.api:app \
            --host 0.0.0.0 --port "$EXEC_API_PORT" 2>&1 | while IFS= read -r line; do
            echo "$(date '+%Y-%m-%d %H:%M:%S') [exec-api] $line"
        done
    ) >> "$LOG_EXEC_API" 2>&1 &
    EXEC_API_PID=$!
    success "Execution API started (PID $EXEC_API_PID) — log: $LOG_EXEC_API"
fi

# ─── Run ML pipeline (optional, blocking) ─────────────────────────────────────
if $OPT_PIPELINE; then
    header "Running ML pipeline (7 stages)"

    VENV_PYTHON="$PYTHON_DIR/.venv/bin/python"
    if [[ ! -f "$VENV_PYTHON" ]]; then
        info "Python venv not found — creating it..."
        python3 -m venv "$PYTHON_DIR/.venv"
        "$PYTHON_DIR/.venv/bin/pip" install -q --upgrade pip
        "$PYTHON_DIR/.venv/bin/pip" install -q -r "$PYTHON_DIR/requirements.txt"
        success "Python venv ready"
    fi

    info "Pipeline log: $LOG_PIPELINE"
    info "This may take a long time (XGBoost + RL training)..."
    (
        cd "$PYTHON_DIR"
        "$VENV_PYTHON" -c "
from src.pipeline.orchestrator import PipelineOrchestrator
pipeline = PipelineOrchestrator()
pipeline.run()
" 2>&1 | while IFS= read -r line; do
            echo "$(date '+%Y-%m-%d %H:%M:%S') [pipeline] $line"
        done
    ) >> "$LOG_PIPELINE" 2>&1
    success "ML pipeline complete — see $LOG_PIPELINE"
fi

# ─── Summary ─────────────────────────────────────────────────────────────────
header "Services running"
if $OPT_BACKEND;  then echo -e "  ${GREEN}●${RESET} Go API         http://localhost:${BACKEND_PORT}"; fi
if $OPT_FRONTEND; then echo -e "  ${GREEN}●${RESET} React Dashboard http://localhost:${FRONTEND_PORT}"; fi
if $OPT_EXEC_API; then echo -e "  ${GREEN}●${RESET} Execution API   http://localhost:${EXEC_API_PORT}"; fi
echo ""
echo -e "  Logs directory: ${CYAN}${LOG_DIR}/${RESET}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${RESET} to stop all services."
echo ""

# ─── Wait ─────────────────────────────────────────────────────────────────────
# Block until user interrupts; cleanup trap handles shutdown
wait
