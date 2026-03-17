# F-RL-V1 — BTC Hybrid Trading System: Setup & Run Guide

A production-grade algorithmic trading system for BTC/USDT perpetual futures, combining XGBoost signal generation with PPO reinforcement learning position sizing.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Full Stack                              │
│                                                             │
│  [React Dashboard :5173] ←→ [Go API :8080] ←→ [Python ML]  │
│                                                             │
│  Python ML Pipeline (btc-hybrid-trader/)                   │
│  ├── Data: Binance klines (5m, 1H, 4H, 1D) → Parquet      │
│  ├── Features: Price action, ICT/SMC, HTF, Order flow      │
│  ├── XGBoost: Walk-forward classifier (Long/Short/Skip)    │
│  ├── RL (PPO): Position sizing agent (SB3/Gymnasium)       │
│  ├── Backtest: Advanced simulator w/ margin & funding      │
│  └── Execution: FastAPI webhook → Binance client           │
│                                                             │
│  Go Backend (Backend/)  →  REST API, CORS, middleware      │
│  React Frontend (Frontend/)  →  Live dashboard, charts     │
└─────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | 3.11 recommended |
| Go | 1.24+ | `go version` to check |
| Node.js | 20+ | LTS recommended |
| npm | 9+ | Bundled with Node.js |
| Git | any | For cloning |

Optional but recommended:
- `make` — used by the Go backend Makefile
- A Python virtual environment tool (`venv` or `conda`)

---

## 1. Clone the Repository

```bash
git clone https://github.com/AbdulHaseeb-1/F-RL-V1.git
cd F-RL-V1
```

---

## 2. Python ML Pipeline Setup

### 2a. Create a Virtual Environment

```bash
cd btc-hybrid-trader
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
```

### 2b. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Key packages installed:
- `xgboost>=2.0` — signal classification model
- `stable-baselines3[extra]` — PPO position sizing agent
- `gymnasium` — RL environment interface
- `python-binance` — market data & order execution
- `fastapi` + `uvicorn` — live execution webhook server
- `pyarrow` — Parquet data storage
- `ta` — technical analysis indicators

### 2c. Configure Environment (Optional — for live trading)

Create a `.env` file inside `btc-hybrid-trader/` for Binance API keys:

```bash
cp ../.env.example .env   # or create manually
```

```env
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
PAPER_TRADING=true          # set false for live orders
```

> **Warning:** Never commit `.env` files. The `.gitignore` already excludes them.

---

## 3. Go Backend Setup

```bash
cd Backend
cp .env.example .env
```

The `.env` file contains:
```env
PORT=8080
APP_ENV=development
ALLOW_ORIGIN=http://localhost:5173
```

Install Go module dependencies:
```bash
go mod tidy
```

---

## 4. React Frontend Setup

```bash
cd Frontend
npm install
```

The frontend connects to the Go backend at `http://localhost:8080` (proxied through Vite) and polls these endpoints:
- `GET /api/pipeline` — pipeline stage status
- `GET /api/monitor` — training metrics
- `GET /api/backtest` — backtest results & equity curve

---

## 5. Running Each Component

### 5a. Start the Go Backend

```bash
cd Backend
make run
# or: go run ./cmd/server
```

Server starts at: `http://localhost:8080`
Health check: `http://localhost:8080/api/health`

### 5b. Start the React Frontend

```bash
cd Frontend
npm run dev
```

Dashboard available at: `http://localhost:5173`

### 5c. Run the ML Pipeline

```bash
cd btc-hybrid-trader
source .venv/bin/activate

# Full 7-stage pipeline:
python -c "
from src.pipeline.orchestrator import PipelineOrchestrator
pipeline = PipelineOrchestrator()
pipeline.run()
"
```

Or run individual stages:

```bash
# Stage 1: Download market data
python -c "from src.data.downloader import download_klines; download_klines()"

# Stage 2: Compute features
python -c "from src.features.engine import FeatureEngine; FeatureEngine().build()"

# Stage 3: Train XGBoost (walk-forward)
python -c "from src.models.xgboost.train import train_xgboost; train_xgboost()"

# Stage 4: Train RL agent (PPO)
python -c "from src.models.rl.train import train_rl; train_rl()"

# Stage 5: Run backtest
python -c "from src.backtest.walk_forward import run_walk_forward; run_walk_forward()"
```

### 5d. Start the Execution API (Live/Paper Trading)

```bash
cd btc-hybrid-trader
source .venv/bin/activate
uvicorn src.execution.api:app --host 0.0.0.0 --port 8000 --reload
```

Execution API available at: `http://localhost:8000`

---

## 6. Running Tests

```bash
# Python tests
cd btc-hybrid-trader
source .venv/bin/activate
pytest tests/ -v

# Go tests
cd Backend
make test
# or: go test ./...

# Frontend lint
cd Frontend
npm run lint
```

---

## 7. Configuration

All ML pipeline behaviour is controlled via YAML configs in `btc-hybrid-trader/configs/`:

| File | Purpose |
|------|---------|
| `pipeline.yaml` | Stage orchestration, data timeframes, validation gates |
| `xgboost.yaml` | Model hyperparams, walk-forward windows, labeling thresholds |
| `rl.yaml` | PPO settings, episode length, capital, leverage limits |
| `features.yaml` | Feature parameters (ATR, ICT, regime, order flow windows) |

Key defaults:
- Data timeframes: `5m`, `4H`, `1D`
- Max leverage: `3x`
- XGBoost: 500 trees, walk-forward 12-month train / 1-month OOS
- RL PPO: 1M timesteps, Sharpe target ≥ 1.5, max drawdown ≤ 15%
- Backtest gates: win rate ≥ 52%, profit factor ≥ 1.1, drawdown ≤ 20%

---

## 8. Directory Layout

```
F-RL-V1/
├── howto.md                    # This guide
├── run.sh                      # All-in-one startup script
├── vercel.json                 # Vercel deployment config
├── btc-hybrid-trader/          # Python ML/RL pipeline
│   ├── src/
│   │   ├── data/               # Binance kline downloader + Parquet storage
│   │   ├── features/           # Feature engineering modules
│   │   ├── models/
│   │   │   ├── xgboost/        # Walk-forward XGBoost classifier
│   │   │   └── rl/             # PPO RL agent (Stable-Baselines3)
│   │   ├── backtest/           # Advanced simulator + metrics
│   │   ├── execution/          # FastAPI webhook + Binance client
│   │   └── pipeline/           # Master orchestrator + monitor
│   ├── configs/                # YAML configuration files
│   ├── tests/                  # pytest test suite
│   └── requirements.txt
├── Backend/                    # Go REST API (:8080)
│   ├── cmd/server/main.go
│   ├── internal/               # Handlers, middleware, router
│   └── Makefile
├── Frontend/                   # React + Vite dashboard (:5173)
│   ├── src/
│   │   ├── components/         # UI components
│   │   ├── hooks/              # usePolling
│   │   ├── App.jsx
│   │   └── api.js
│   └── package.json
└── api/                        # Vercel serverless Go functions
```

---

## 9. Deployment (Vercel)

The project is pre-configured for Vercel deployment via `vercel.json`:

```bash
npm i -g vercel
vercel
```

- Frontend is built from `Frontend/` → output to `Frontend/dist/`
- API routes (`/api/*`) are handled by serverless Go functions in `api/`

---

## 10. Troubleshooting

**Python import errors:**
Ensure you're inside the virtual environment (`source .venv/bin/activate`) and run from the `btc-hybrid-trader/` directory.

**Binance data download fails:**
Check your internet connection. Public endpoints don't require API keys. For order flow / OI data, API keys may be needed.

**Go backend won't start:**
Run `go mod tidy` in `Backend/` and ensure `PORT=8080` is set in `.env`.

**Frontend can't reach backend:**
Ensure the Go backend is running on `:8080` before starting the frontend. Check `ALLOW_ORIGIN` in `Backend/.env`.

**RL training is slow:**
PPO trains for 1M timesteps by default. Reduce `total_timesteps` in `configs/rl.yaml` for faster testing. GPU acceleration is supported if CUDA is available.

**Out of memory during XGBoost training:**
Reduce the walk-forward window or feature set in `configs/pipeline.yaml` and `configs/features.yaml`.

---

## Quick Reference

```bash
# One-command startup (all services + logging)
./run.sh

# Individual services
cd Backend && make run                          # Go API  :8080
cd Frontend && npm run dev                      # React   :5173
cd btc-hybrid-trader && uvicorn src.execution.api:app --port 8000  # Exec API :8000

# Run full ML pipeline
cd btc-hybrid-trader && python -c "from src.pipeline.orchestrator import PipelineOrchestrator; PipelineOrchestrator().run()"

# Tests
cd btc-hybrid-trader && pytest tests/ -v
cd Backend && make test
```
