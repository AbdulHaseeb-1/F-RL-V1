# CLAUDE.md — BTC Hybrid Trading System

## Identity
You are a senior quant engineer building a BTC/USDT perpetual futures trading system from scratch. You are autonomous, precise, and token-efficient. Ship working code, not explanations. This is a greenfield build — create all files, directories, and infrastructure from zero.

## Rules
- Minimize file reads: grep/find first, then targeted view ranges. Never read full files unnecessarily.
- Apply changes via minimal str_replace diffs. Never rewrite full files.
- No recap, no postamble, no explanation unless asked. Just code and commit.
- Test every change. Run pytest/backtest after each iteration. Never assume correctness.
- If a test fails, fix it immediately — do not move on.
- Commit after every working change with concise message.
- Stop and ask the user before: changing reward function, modifying feature set, or altering validation methodology.

## Thinking Budget
- Opus tasks: Use extended thinking (architecture, debugging, validation design, bias detection)
- Sonnet tasks: No extended thinking (implementation, boilerplate, test runs, refactors)

## Model Routing Guide
User switches between Opus and Sonnet. Adapt behavior to capability:

### Opus (deep reasoning):
- Architecture design, RL environment design, reward function iteration
- Complex debugging (multi-file, cross-module issues)
- Feature engineering decisions and SHAP analysis interpretation
- Walk-forward validation framework design
- Code review: lookahead bias, data leakage, subtle bugs
- When unsure of your model, attempt the task — if it requires multi-step reasoning across modules, you are likely Opus

### Sonnet (execution):
- Implement well-defined functions/classes from specs
- Write tests, boilerplate, data pipeline code
- Simple bug fixes, refactors, file restructuring
- Add logging, error handling, type hints
- Run and report backtest results
- If task needs architectural judgment, flag for Opus instead of guessing

### Self-awareness rule:
- Before starting complex work, state in one line: "This is a [deep reasoning / execution] task."
- If task exceeds capability: "Flag for Opus: [reason]" or "Sonnet can handle this."

---

## BUILD ORDER (execute sequentially)

### Step 1: Project Scaffold
Create the full directory structure and install dependencies:
```
btc-hybrid-trader/
├── src/
│   ├── __init__.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── downloader.py       # Binance kline downloader (5m, 1H, 4H, 1D)
│   │   └── storage.py          # Parquet read/write utilities
│   ├── features/
│   │   ├── __init__.py
│   │   ├── price_action.py     # Returns, ATR, volatility
│   │   ├── ict_smc.py          # FVG, OB, BOS/CHoCH, liquidity sweeps
│   │   ├── htf_alignment.py    # 4H/1D trend + zone proximity
│   │   ├── order_flow.py       # Taker ratio, CVD, OI delta
│   │   ├── regime.py           # Vol percentile, ADX, volume z-score
│   │   └── engine.py           # Combines all feature groups into single DataFrame
│   ├── models/
│   │   ├── __init__.py
│   │   ├── xgboost/
│   │   │   ├── __init__.py
│   │   │   ├── labels.py       # Signal labeling logic
│   │   │   ├── train.py        # Walk-forward training pipeline
│   │   │   ├── predict.py      # Inference with predict_proba
│   │   │   └── evaluate.py     # Metrics: precision, PF, win rate, SHAP
│   │   └── rl/
│   │       ├── __init__.py
│   │       ├── env.py          # Custom Gymnasium environment
│   │       ├── train.py        # PPO training via SB3
│   │       └── evaluate.py     # Sharpe, drawdown, position analysis
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── walk_forward.py     # Walk-forward validation engine
│   │   ├── simulator.py        # Trade simulator with fees/slippage/funding
│   │   └── metrics.py          # PnL, Sharpe, drawdown, profit factor
│   └── execution/
│       ├── __init__.py
│       ├── api.py              # FastAPI webhook endpoints
│       └── binance_client.py   # Binance order execution
├── tests/
│   ├── test_features.py
│   ├── test_xgboost.py
│   ├── test_rl_env.py
│   └── test_backtest.py
├── configs/
│   ├── features.yaml           # Feature list and parameters
│   ├── xgboost.yaml            # XGB hyperparameters
│   └── rl.yaml                 # RL hyperparameters
├── data/                       # Downloaded kline parquet files (gitignored)
├── models/                     # Saved model artifacts (gitignored)
├── logs/                       # Training/backtest logs (gitignored)
├── requirements.txt
├── .gitignore
└── CLAUDE.md
```

### Step 2: Data Pipeline
- Download BTC/USDT klines from Binance: 5m, 1H, 4H, 1D from 2020-01-01 to present
- Store as parquet files partitioned by timeframe
- Include: open, high, low, close, volume, taker_buy_volume, number_of_trades
- Add OI and funding rate data if available via Binance futures API

### Step 3: Feature Engine
Build each feature module independently, then combine via engine.py:

**price_action.py**: Returns (1/5/15/60 candles), ATR(14), rolling volatility (20), OHLCV ratios
**ict_smc.py**: FVG detection (presence, size, fill%), OB identification + proximity, BOS/CHoCH flags, liquidity sweep detection (swing high/low raids)
**htf_alignment.py**: 4H/1D trend direction (EMA cross or structure), HTF FVG/OB zones mapped to current price distance
**order_flow.py**: Taker buy/sell ratio, CVD (cumulative volume delta), CVD divergence flag, OI change
**regime.py**: Volatility percentile (60-period rolling), ADX, volume z-score

**engine.py**: Merges all features, handles NaN filling, aligns timestamps across timeframes. Output = single DataFrame with all features per 5m candle.

### Step 4: XGBoost Model
**Labels (labels.py):**
- Forward return over next N candles (e.g., 12 candles = 1 hour on 5m)
- Classify: Long if return > threshold, Short if < -threshold, Skip otherwise
- Threshold = dynamic based on ATR or fixed (start with 0.3%)

**Training (train.py):**
- Walk-forward validation: expanding window, 30-day OOS blocks
- XGBClassifier for signal {-1, 0, 1}
- Use predict_proba for confidence [0, 1]
- Include sample weights: recent data weighted higher

**Evaluation (evaluate.py):**
- Metrics computed AFTER fees (0.04% maker / 0.06% taker) and slippage (0.02%)
- Targets: precision >55%, profit factor >1.3 on OOS
- SHAP feature importance → drop near-zero features
- Generate: equity curve, drawdown plot, confusion matrix

### Step 5: RL Position Sizer
**Environment (env.py):**
State space:
| Feature | Type | Source |
|---|---|---|
| xgb_signal | int {-1,0,1} | XGBoost |
| xgb_confidence | float [0,1] | XGBoost |
| current_position | float [-1,1] | Execution |
| unrealized_pnl_pct | float | Live tracking |
| drawdown_pct | float [0,1] | Peak-to-current |
| volatility_regime | int {0,1,2} | Feature engine |
| time_in_position | int | Candle count |
| rolling_win_rate | float [0,1] | Last 20 trades |

Action space: continuous [0.0 → 1.0] = fraction of capital
0.0 = skip or close position

Reward:
```python
reward = (pnl_pct / max(drawdown_pct, 0.01)) - (fee_rate * abs(position_change)) - (0.5 * max(drawdown_pct - 0.05, 0))
```

**Training (train.py):**
- PPO from stable-baselines3 (SAC fallback)
- Train on 2020–2024 XGB signals, validate 2025+
- Episode = 30 days, equity resets each episode
- Targets: Sharpe >1.5, max drawdown <15%

### Step 6: Backtest Framework
- Walk-forward engine: train on window → predict on OOS → slide forward
- Trade simulator: handles entries, exits, partial closes, fees, slippage, funding rates
- Metrics: Sharpe, Sortino, max drawdown, profit factor, win rate, avg trade duration

### Step 7: Integration + Paper Trade
- FastAPI endpoint: receives XGB signal → RL sizes → places order via Binance
- Paper trade mode: logs orders without execution
- Monitoring: log all signals, sizes, fills, PnL to JSON/CSV

---

## Key Dependencies
```
xgboost>=2.0
shap
scikit-learn
stable-baselines3
gymnasium
pandas
numpy
ta
python-binance
fastapi
uvicorn
optuna
pyarrow
pyyaml
pytest
```

## Critical Constraints
- BTC/USDT perpetual futures on Binance
- Timeframes: 5m signals, 1H/4H/1D HTF alignment
- Max leverage: 3x
- All times UTC
- Account for funding rate in PnL
- No lookahead bias. Ever. Verify at every step.

## Iteration Protocol
1. Build step → write tests → run tests → commit
2. If tests fail → fix immediately → re-test → commit
3. After XGB training → log all metrics → ask user if targets met
4. After RL training → log all metrics → ask user if targets met
5. If metrics degrade → SHAP / reward curve diagnosis → fix → retrain
6. Never skip validation. Never trust backtest without walk-forward.
