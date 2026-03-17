# BTC Hybrid Trader — Complete Model Training Guide

> A detailed reference covering every step of the training pipeline, how each stage progresses, walk-forward fold mechanics, and all hyperparameters.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Pipeline at a Glance](#2-pipeline-at-a-glance)
3. [Stage 1 — Data Loading](#3-stage-1--data-loading)
4. [Stage 2 — Feature Engineering](#4-stage-2--feature-engineering)
5. [Stage 3 — XGBoost Walk-Forward Training](#5-stage-3--xgboost-walk-forward-training)
6. [Stage 4 — XGBoost Quality Gate](#6-stage-4--xgboost-quality-gate)
7. [Stage 5 — Reinforcement Learning (PPO)](#7-stage-5--reinforcement-learning-ppo)
8. [Stage 6 — Full Backtest](#8-stage-6--full-backtest)
9. [Stage 7 — Final Report](#9-stage-7--final-report)
10. [Walk-Forward Folding — Deep Dive](#10-walk-forward-folding--deep-dive)
11. [Label Generation](#11-label-generation)
12. [Feature Groups Reference](#12-feature-groups-reference)
13. [Risk Management & Cost Model](#13-risk-management--cost-model)
14. [Hyperparameter Reference](#14-hyperparameter-reference)
15. [Validation Gates Reference](#15-validation-gates-reference)
16. [File Map](#16-file-map)

---

## 1. System Architecture Overview

The system is a **hybrid ML + RL trading engine** for BTC/USDT perpetual futures. Two models work in sequence:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      HYBRID TRADING SYSTEM                          │
│                                                                     │
│  Raw OHLCV Data                                                     │
│       │                                                             │
│       ▼                                                             │
│  Feature Engine ──── 50+ indicators ──── 5m / 4h / 1d timeframes   │
│       │                                                             │
│       ▼                                                             │
│  ┌─────────────┐     signal                                         │
│  │  XGBoost    │ ─────────── {Long / Short / Skip}                  │
│  │  Classifier │ ─────────── confidence score [0, 1]               │
│  └─────────────┘                                                    │
│       │                                                             │
│       ▼  (signal + confidence + market state)                       │
│  ┌─────────────┐                                                    │
│  │  PPO Agent  │ ─────────── position size [0, 1] of capital       │
│  │  (RL)       │                                                    │
│  └─────────────┘                                                    │
│       │                                                             │
│       ▼                                                             │
│  Risk Manager ── stops / leverage / drawdown circuit breaker        │
│       │                                                             │
│       ▼                                                             │
│  Trade Execution                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Why two models?**
- **XGBoost** is excellent at pattern recognition in tabular data — it decides *direction*.
- **PPO (RL)** learns from experience — it decides *how much* to risk per trade.

---

## 2. Pipeline at a Glance

The pipeline orchestrator (`src/pipeline/orchestrator.py`) runs 7 sequential stages. Each stage must pass a validation gate before the next begins.

```
┌──────────────────────────────────────────────────────────────────┐
│  PIPELINE STAGES                                                  │
│                                                                   │
│  [1] Data Load          ──► Download / cache OHLCV candles       │
│       │                                                           │
│  [2] Feature Engineering ──► Compute 50+ indicators              │
│       │                                                           │
│  [3] XGBoost Training   ──► Walk-forward folds (12mo / 1mo)      │
│       │                                                           │
│  [4] Quality Gate ──► Win Rate ≥52%, Profit Factor ≥1.1          │
│       │  (HALT if gate fails)                                     │
│  [5] RL Training (PPO)  ──► 1M timesteps, 30-day episodes        │
│       │                                                           │
│  [6] Full Backtest      ──► Simulate all OOS periods              │
│       │                                                           │
│  [7] Final Report       ──► JSON metrics + equity curve           │
└──────────────────────────────────────────────────────────────────┘
```

Each stage writes its outputs to `runs/<run_id>/` so training can be **resumed** from any completed stage.

---

## 3. Stage 1 — Data Loading

**File:** `src/data/downloader.py`
**Config:** `configs/pipeline.yaml → data`

### What happens

1. Connects to Binance Futures API (FAPI).
2. Downloads OHLCV candlestick data for **three timeframes**:
   - `5m` — primary trading timeframe (each candle = 5 minutes)
   - `4h` — intermediate trend context
   - `1d` — macro trend context
3. Stores data as Parquet files in `runs/<run_id>/data/`.
4. On subsequent runs, loads from cache unless `force_reload=True`.

### Data schema (per candle)

| Column         | Type    | Description                    |
|----------------|---------|--------------------------------|
| `timestamp`    | int64   | Unix ms timestamp              |
| `open`         | float64 | Open price                     |
| `high`         | float64 | High price                     |
| `low`          | float64 | Low price                      |
| `close`        | float64 | Close price                    |
| `volume`       | float64 | Quoted volume (USDT)           |
| `taker_buy_vol`| float64 | Aggressive buy volume (USDT)   |

### Typical data volume

| Timeframe | Candles per year | 3 years of data |
|-----------|-----------------|-----------------|
| 5m        | ~105,120        | ~315,360        |
| 4h        | ~2,190          | ~6,570          |
| 1d        | ~365            | ~1,095          |

---

## 4. Stage 2 — Feature Engineering

**File:** `src/features/engine.py`
**Config:** `configs/features.yaml`

### Overview

All features are computed on the **5m timeframe**. Higher-timeframe features (4h, 1d) are resampled and merged, with a **`shift(1)` applied to prevent lookahead bias** — i.e., a 5m candle at `T` only sees the most recently *closed* 4h/1d candle, not the current one still forming.

### Feature groups

There are 5 feature modules, producing 50+ features total:

---

#### 4.1 Price Action (`price_action.py`)

Core OHLCV-derived indicators. Computed entirely on 5m data.

| Feature          | Formula / Method           | Description                          |
|------------------|---------------------------|--------------------------------------|
| `ret_1`          | `close/close.shift(1) - 1`| 1-candle log return                  |
| `ret_5`          | `close/close.shift(5) - 1`| 5-candle (25m) return                |
| `ret_15`         | `close/close.shift(15) - 1`| 15-candle (75m) return              |
| `ret_60`         | `close/close.shift(60) - 1`| 60-candle (5h) return               |
| `atr_14`         | Wilder's ATR, 14 periods  | Average True Range                   |
| `volatility_20`  | `std(log_ret, 20)`         | Rolling 20-period return std dev     |
| `hl_ratio`       | `(high - low) / close`     | Candle range relative to close       |
| `co_ratio`       | `(close - open) / open`    | Candle body direction and size       |
| `upper_wick`     | `(high - max(open,close)) / (high - low)` | Upper wick fraction |
| `lower_wick`     | `(min(open,close) - low) / (high - low)`  | Lower wick fraction |
| `volume_ratio`   | `volume / volume.rolling(20).mean()`      | Volume vs 20-period avg |

---

#### 4.2 ICT / Smart Money Concepts (`ict_smc.py`)

Structural price action patterns used in institutional trading analysis.

| Feature              | Description                                                     |
|----------------------|----------------------------------------------------------------|
| `fvg_bullish`        | `1` if a bullish Fair Value Gap exists (gap between candle N-2 high and candle N low) |
| `fvg_bearish`        | `1` if a bearish Fair Value Gap exists                          |
| `fvg_distance`       | Distance from current close to nearest FVG level (normalized by ATR) |
| `ob_bullish`         | `1` if recent Order Block to the downside detected              |
| `ob_bearish`         | `1` if recent Order Block to the upside detected                |
| `ob_distance`        | Distance to nearest Order Block level                           |
| `bos_up`             | `1` if Break of Structure to the upside (new swing high broken) |
| `bos_down`           | `1` if Break of Structure to the downside                       |
| `choch`              | `1` if Change of Character (BOS in opposite direction to trend) |
| `liq_sweep_high`     | `1` if recent high swept (wick above prior swing high, closed below) |
| `liq_sweep_low`      | `1` if recent low swept                                         |
| `swing_high_dist`    | Distance to most recent swing high (normalized)                  |
| `swing_low_dist`     | Distance to most recent swing low (normalized)                   |

**What is a Fair Value Gap?**

```
Candle N-2:  ───────────[HIGH]────────
                         ↑
                      Gap zone
                         ↓
Candle N:   ─[LOW]──────────────────
```
When price jumps over a zone without trading through it, that gap (FVG) acts as a magnet for price.

---

#### 4.3 Regime (`regime.py`)

Market state classification features.

| Feature            | Description                                                  |
|--------------------|-------------------------------------------------------------|
| `vol_percentile`   | Rolling 60-period percentile rank of current ATR             |
| `adx_14`           | Average Directional Index (14-period) — trend strength       |
| `volume_zscore`    | Z-score of volume vs 20-period mean                          |
| `regime_vol`       | 3-state: `0=Low` (`<33rd pct`), `1=Mid`, `2=High` (`>66th pct`) |

---

#### 4.4 Order Flow (`order_flow.py`)

Indicators derived from taker buy/sell volume and open interest.

| Feature             | Formula                                       | Description                           |
|---------------------|----------------------------------------------|---------------------------------------|
| `taker_buy_ratio`   | `taker_buy_vol / total_vol`                   | Aggressor buy pressure [0, 1]         |
| `taker_sell_ratio`  | `1 - taker_buy_ratio`                         | Aggressor sell pressure               |
| `cvd`               | `cumsum(taker_buy_vol - taker_sell_vol)`       | Cumulative Volume Delta               |
| `cvd_20`            | `cvd - cvd.shift(20)`                          | 20-period CVD change                  |
| `cvd_divergence`    | Sign mismatch: `sign(ret_60) ≠ sign(cvd_20)` | Price/flow divergence flag           |
| `oi_delta`          | `open_interest - open_interest.shift(1)`       | OI change (if available)             |

---

#### 4.5 Higher Timeframe Alignment (`htf_alignment.py`)

Trend-context features from 4h and 1d timeframes, preventing lookahead via `shift(1)`.

| Feature              | Timeframe | Description                                  |
|----------------------|-----------|----------------------------------------------|
| `htf_4h_ema_fast`    | 4h        | EMA(20) on 4h candles, resampled to 5m        |
| `htf_4h_ema_slow`    | 4h        | EMA(50) on 4h candles                         |
| `htf_4h_trend`       | 4h        | `1` if ema_fast > ema_slow, else `-1`          |
| `htf_1d_ema_fast`    | 1d        | EMA(20) on daily candles                      |
| `htf_1d_ema_slow`    | 1d        | EMA(50) on daily candles                      |
| `htf_1d_trend`       | 1d        | `1` if daily ema_fast > ema_slow              |
| `htf_fvg_distance`   | 4h        | Distance to nearest 4h FVG level              |

---

### Feature cleaning pipeline

After all feature groups are computed:

```
Step 1: Merge all feature DataFrames on timestamp index
Step 2: Drop rows where core features are NaN
        (covers the warm-up period for indicators with long lookbacks)
        dropna(subset=["atr_14", "vol_percentile"])
Step 3: Forward-fill remaining NaNs (handles sparse HTF alignment)
Step 4: Fill any remaining NaN with 0
Step 5: Apply label generation (see Section 11)
```

---

## 5. Stage 3 — XGBoost Walk-Forward Training

**File:** `src/models/xgboost/train.py`
**Config:** `configs/xgboost.yaml`

### The problem walk-forward solves

A standard train/test split would let the model see future data patterns during training (look-ahead bias). In financial time series, data is non-stationary — the statistical properties of 2021 data differ from 2024 data. Walk-forward validation mirrors real trading:

> Train on the past → test on the immediate future → advance the window → repeat.

### Expanding window mechanics

```
┌──────────────────────────────────────────────────────────────────────────┐
│  WALK-FORWARD EXPANDING WINDOW                                           │
│                                                                          │
│  Full dataset: Jan 2021 ──────────────────────────────── Dec 2024        │
│                                                                          │
│  Fold 0:  [═══════════════Train══════════════][OOS ]                     │
│           Jan 2021 ─────────── Jun 2021       Jul 2021                   │
│                                                                          │
│  Fold 1:  [════════════════Train═════════════════][OOS ]                 │
│           Jan 2021 ─────────────── Jul 2021        Aug 2021              │
│                                                                          │
│  Fold 2:  [═════════════════Train══════════════════════][OOS ]           │
│           Jan 2021 ────────────────── Aug 2021          Sep 2021         │
│                                                                          │
│  Fold N:  [══════════════Train (grows each fold)══════════][OOS ]        │
│           Jan 2021 ─────────────────────────── Nov 2024   Dec 2024       │
│                                                                          │
│  Key:  [═══] = Training data (expanding, always starts at day 0)        │
│        [OOS] = Out-of-sample test window (1 month, slides forward)       │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key parameters:**
- `train_months = 12` — minimum training window before first OOS test
- `oos_months = 1` — each OOS test period is 1 month
- `min_train_months = 6` — absolute minimum data to start training

**How many folds?**

The number of folds depends on your dataset length:

```
folds = (total_months - min_train_months) / oos_months

Example with 3 years of data (36 months):
  folds = (36 - 6) / 1 = 30 folds

Example with 4 years of data (48 months):
  folds = (48 - 6) / 1 = 42 folds
```

Each fold trains a **separate XGBoost model**, then generates predictions for its 1-month OOS window. All OOS predictions are concatenated to form the full OOS dataset used downstream.

---

### XGBoost model architecture

**Type:** Gradient Boosted Decision Trees (multi-class classifier)

```
Input: ~50 features (float32)
       │
       ▼
  XGBClassifier
  ├── n_estimators: 500      (number of trees)
  ├── max_depth: 6           (max tree depth)
  ├── learning_rate: 0.05    (shrinkage)
  ├── subsample: 0.8         (row sampling per tree)
  ├── colsample_bytree: 0.8  (feature sampling per tree)
  ├── min_child_weight: 5    (min sum of instance weights in leaf)
  ├── gamma: 0.1             (min loss reduction to split)
  ├── reg_alpha: 0.1         (L1 regularization)
  ├── reg_lambda: 1.0        (L2 regularization)
  └── scale_pos_weight       (auto-computed for class imbalance)
       │
       ▼
Output: [P(Short), P(Skip), P(Long)]  — 3 class probabilities
Decision: argmax → {-1, 0, 1}
Confidence: max(probabilities)
```

**Why these parameters?**

| Parameter          | Value  | Rationale                                                    |
|--------------------|--------|--------------------------------------------------------------|
| `n_estimators`     | 500    | High enough for complex patterns, with early stopping to prevent overfit |
| `max_depth`        | 6      | Controls tree complexity; deeper = more overfit risk         |
| `learning_rate`    | 0.05   | Small shrinkage = more trees needed but better generalization |
| `subsample`        | 0.8    | Stochastic gradient boosting reduces variance                |
| `colsample_bytree` | 0.8    | Feature subsampling at tree level (similar to random forests) |
| `min_child_weight` | 5      | Prevents splits on very small groups (reduces noise fitting) |
| `gamma`            | 0.1    | Minimum gain threshold — prevents trivial splits             |
| `reg_alpha`        | 0.1    | L1 regularization → feature sparsity                         |
| `reg_lambda`       | 1.0    | L2 regularization → weight magnitude control                 |

---

### Sample weighting

Older samples get lower weight — the model emphasizes recent market behavior:

```
weight(i) = decay^(N-1-i)   where decay = 0.9995

For N=100,000 samples:
  Most recent candle:   weight ≈ 1.0
  1 week ago (2016 candles of 5m): weight ≈ 0.37
  1 month ago (~8640 candles):     weight ≈ 0.013
```

This reflects the reality that market regimes change over time — patterns from 2021 bull market may not apply in 2024.

---

### Per-fold training sequence

For each fold:

```
1. Slice training data: df[train_start : train_end]
2. Generate labels for training slice (forward-looking, see Section 11)
3. Drop rows where label is NaN (last 12 candles)
4. Compute sample weights (time decay)
5. Split features (X) from label (y)
6. Scale_pos_weight: count(majority_class) / count(minority_class)
7. Train XGBClassifier with eval_set on last 10% of training data
8. Early stopping: stop if eval metric hasn't improved in 50 rounds
9. Slice OOS data: df[oos_start : oos_end]
10. Generate predictions on OOS data
11. Compute per-fold metrics: win rate, profit factor, sharpe
12. Save fold model: runs/<run_id>/models/xgb_fold_{N}.json
13. Append OOS predictions to master predictions list
```

---

## 6. Stage 4 — XGBoost Quality Gate

**File:** `src/pipeline/monitor.py`
**Config:** `configs/pipeline.yaml → gates.xgb_evaluate`

After all folds complete, the concatenated OOS predictions are evaluated. The pipeline **halts** if any gate fails.

### Gates

| Metric           | Threshold | Direction | Description                                        |
|------------------|-----------|-----------|---------------------------------------------------|
| `win_rate`       | 0.52      | `≥`       | At least 52% of trades must be profitable          |
| `profit_factor`  | 1.1       | `≥`       | Gross profit / Gross loss must be > 1.1            |
| `n_trades`       | 50        | `≥`       | Minimum 50 trades needed for statistical validity  |

### How metrics are computed

**Win Rate:**
```
win_rate = trades where net_pnl > 0 / total_trades
```

**Profit Factor:**
```
profit_factor = sum(pnl for winning trades) / abs(sum(pnl for losing trades))
```

A profit factor of 1.0 = break-even. 1.1 = 10% more profit than loss.

### Gate failure behavior

- If `n_trades < 50`: warning logged, but training continues (not enough data to evaluate fairly)
- If `win_rate < 0.52` or `profit_factor < 1.1`: pipeline **halts** with `GATE_FAILED` status
- Failed runs are saved so the configuration can be debugged

---

## 7. Stage 5 — Reinforcement Learning (PPO)

**Files:** `src/models/rl/train.py`, `src/models/rl/env.py`
**Config:** `configs/rl.yaml`

### Why RL on top of XGBoost?

XGBoost tells us *which direction* to trade. But it doesn't answer:
- *How much* of our capital should we risk on this trade?
- Should we trade smaller when drawdown is high?
- Should we be more aggressive when win rate is high?

A PPO agent learns these risk management decisions by interacting with the trading environment.

---

### The Trading Environment (`env.py`)

Built on Gymnasium (OpenAI Gym successor).

**State space (8 features):**

| Index | Feature              | Range    | Description                                   |
|-------|----------------------|----------|-----------------------------------------------|
| 0     | `xgb_signal`         | {-1,0,1} | XGBoost direction prediction                  |
| 1     | `xgb_confidence`     | [0, 1]   | XGBoost max class probability                 |
| 2     | `current_position`   | [-1, 1]  | Current position (negative = short)           |
| 3     | `unrealized_pnl`     | [-1, 1]  | P&L on open position, normalized              |
| 4     | `drawdown`           | [0, 1]   | Current drawdown from peak equity             |
| 5     | `vol_regime`         | [0, 1]   | Volatility regime (0=low, 0.5=mid, 1=high)   |
| 6     | `time_in_position`   | [0, 1]   | How long current trade has been open          |
| 7     | `rolling_win_rate`   | [0, 1]   | Win rate over last 20 trades                  |

**Action space (1 continuous):**

```
action ∈ [0, 1]   →   position_size = action × max_capital_pct
```

The agent outputs a single number representing what fraction of capital to commit.

**Reward function:**

```
reward = (step_return × 100)
       - 0.5 × max(drawdown - 0.05, 0)   ← drawdown penalty activates above 5%
       - 0.01 × (position == 0)           ← small penalty for idle periods
```

This reward function:
- Rewards profitable trading proportionally
- Penalizes large drawdowns to teach capital preservation
- Provides a small incentive to stay active (avoid analysis paralysis)

---

### PPO Algorithm

PPO (Proximal Policy Optimization) is an actor-critic RL algorithm. It's used here via **Stable-Baselines3**.

```
┌─────────────────────────────────────────────────────────────────────┐
│  PPO TRAINING LOOP                                                  │
│                                                                     │
│  Initialize policy network (MLP: 64 → 64 → action)                 │
│  Initialize value network (MLP: 64 → 64 → scalar)                  │
│                                                                     │
│  For timestep in range(total_timesteps = 1,000,000):               │
│    ┌─────────────────────────────────────────────────────────────┐  │
│    │  ROLLOUT PHASE (n_steps = 2048 timesteps)                   │  │
│    │    - Agent acts in environment                              │  │
│    │    - Store: states, actions, rewards, values, log_probs     │  │
│    │    - One rollout = ~2048 × 5m = ~7 days of trading          │  │
│    └─────────────────────────────────────────────────────────────┘  │
│           │                                                          │
│           ▼                                                          │
│    ┌─────────────────────────────────────────────────────────────┐  │
│    │  ADVANTAGE ESTIMATION (GAE)                                 │  │
│    │    - Compute advantage: A(t) = R(t) - V(s(t))              │  │
│    │    - GAE smoothing: λ = 0.95                                │  │
│    │    - Advantage = "how much better was this action than avg" │  │
│    └─────────────────────────────────────────────────────────────┘  │
│           │                                                          │
│           ▼                                                          │
│    ┌─────────────────────────────────────────────────────────────┐  │
│    │  UPDATE PHASE (n_epochs = 10, batch_size = 64)              │  │
│    │    For each mini-batch:                                     │  │
│    │      ratio = π_new(a|s) / π_old(a|s)                       │  │
│    │      clipped_ratio = clip(ratio, 1-0.2, 1+0.2)             │  │
│    │      policy_loss = -min(ratio×A, clipped_ratio×A)          │  │
│    │      value_loss = (V(s) - R_target)²                       │  │
│    │      entropy_bonus = -0.01 × entropy(π)                    │  │
│    │      total_loss = policy_loss + value_loss + entropy_bonus  │  │
│    │      Backprop + Adam update                                 │  │
│    └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

**The clip trick (what makes PPO "proximal"):**
```
clip_range = 0.2

If the new policy moves too far from the old policy (ratio > 1.2 or < 0.8),
the gradient is clipped. This prevents catastrophic policy updates and
provides stable training without trust region calculations.
```

---

### PPO Hyperparameters

| Parameter          | Value     | Effect                                                    |
|--------------------|-----------|-----------------------------------------------------------|
| `learning_rate`    | 0.0003    | Adam optimizer step size                                  |
| `n_steps`          | 2048      | Rollout buffer size; larger = more stable gradients       |
| `batch_size`       | 64        | Mini-batch size for updates                               |
| `n_epochs`         | 10        | How many passes over each rollout buffer                  |
| `gamma`            | 0.99      | Discount factor; 0.99 = values rewards up to ~100 steps ahead |
| `gae_lambda`       | 0.95      | Bias-variance tradeoff in advantage estimation           |
| `clip_range`       | 0.2       | Maximum policy change per update (the "proximal" part)   |
| `ent_coef`         | 0.01      | Entropy bonus; encourages exploration                     |
| `total_timesteps`  | 1,000,000 | Total environment steps to train for                     |

**Episode structure:**
- Each episode = 30 days of 5m candles (8,640 timesteps)
- Initial capital: $10,000 USD
- Max leverage: 3x
- Fee rate: 0.06% (Binance taker)

---

## 8. Stage 6 — Full Backtest

**File:** `src/backtest/advanced_simulator.py`
**Config:** `configs/pipeline.yaml → backtest`

The backtest simulates trading on the entire OOS dataset using:
1. XGBoost signals from Stage 3
2. RL position sizing from Stage 5 (or fixed sizing if RL disabled)
3. Full cost model and risk management rules

---

### Risk management rules

The simulator enforces 7 layers of risk control:

```
┌─────────────────────────────────────────────────────────────────────┐
│  RISK MANAGEMENT STACK                                              │
│                                                                     │
│  1. MIN CONFIDENCE GATE                                             │
│     If XGB confidence < 0.55 → skip trade                          │
│                                                                     │
│  2. POSITION SIZE LIMIT                                             │
│     Max 1% of capital per trade (before leverage)                  │
│                                                                     │
│  3. LEVERAGE CAP                                                    │
│     Max 3x leverage (e.g., $100 capital → max $300 notional)       │
│                                                                     │
│  4. STOP LOSS                                                       │
│     Exit if price moves 2% against position                        │
│                                                                     │
│  5. TRAILING STOP                                                   │
│     Once in profit, maintain 1.5% trailing stop from peak          │
│     (locks in profits as trade moves favorably)                    │
│                                                                     │
│  6. TIME STOP                                                       │
│     Exit after 96 candles (8 hours) regardless of P&L              │
│     (prevents capital being locked in stalled trades)              │
│                                                                     │
│  7. MAX DRAWDOWN CIRCUIT BREAKER                                    │
│     If portfolio drawdown reaches 15% → stop all trading            │
│     Cooldown: 12 candles (1 hour) before resuming                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Cost model

Every simulated trade accounts for:

```
Net P&L = Gross P&L
        − Entry Fee   (0.06% × notional)
        − Exit Fee    (0.06% × notional)
        − Slippage    (0.02% × notional, both sides)
        − Funding     (0.01% per 8h held × intervals_held)

Total cost on round-trip: ≈ 0.16% + funding
```

**Why funding matters:**
On perpetual futures, one side pays the other every 8 hours (funding rate). Long positions typically pay short positions in bull markets. This cost accumulates on multi-day trades.

---

### Per-trade metrics recorded

For every completed trade:

| Metric       | Description                                              |
|--------------|----------------------------------------------------------|
| `entry_time` | Timestamp of entry                                       |
| `exit_time`  | Timestamp of exit                                        |
| `direction`  | `1` = Long, `-1` = Short                                 |
| `leverage`   | Leverage used                                            |
| `gross_pnl`  | P&L before costs                                         |
| `net_pnl`    | P&L after all costs                                      |
| `fees`       | Total fees paid                                          |
| `slippage`   | Slippage cost                                            |
| `funding`    | Funding rate paid/received                               |
| `hold_bars`  | Duration in 5m candles                                   |
| `mfe`        | Maximum Favorable Excursion (best unrealized profit)     |
| `mae`        | Maximum Adverse Excursion (worst unrealized loss)        |
| `exit_reason`| `stop_loss` / `trailing_stop` / `signal_flip` / `time_stop` / `max_dd` |

---

### Backtest validation gate

After the full backtest, another set of gates validates performance:

| Metric          | Threshold | Direction | Description                                |
|-----------------|-----------|-----------|-------------------------------------------|
| `max_drawdown`  | 0.20      | `≤`       | Portfolio drawdown must stay under 20%    |
| `total_return`  | 0.0       | `>`       | Must be profitable overall                |
| `sharpe_ratio`  | 0.5       | `≥`       | Risk-adjusted return must be acceptable   |

---

## 9. Stage 7 — Final Report

**Output:** `runs/<run_id>/report.json`

The pipeline compiles all metrics into a structured JSON report:

```json
{
  "run_id": "run_20240315_143022",
  "status": "SUCCESS",
  "timestamp": "2024-03-15T14:30:22Z",
  "data": {
    "symbol": "BTCUSDT",
    "timeframe": "5m",
    "date_range": ["2021-01-01", "2024-03-01"]
  },
  "xgboost": {
    "n_folds": 38,
    "mean_win_rate": 0.573,
    "mean_profit_factor": 1.42,
    "total_oos_trades": 1840,
    "feature_importance": { ... }
  },
  "rl": {
    "enabled": true,
    "final_reward": 2847.3,
    "episodes_trained": 488
  },
  "backtest": {
    "total_return": 0.312,
    "sharpe_ratio": 1.24,
    "max_drawdown": 0.087,
    "win_rate": 0.561,
    "profit_factor": 1.38,
    "n_trades": 1840,
    "equity_curve": [ ... ]
  }
}
```

The Go backend (`Backend/internal/handlers/pipeline.go`) exposes this report via HTTP API for the frontend dashboard.

---

## 10. Walk-Forward Folding — Deep Dive

### Visual timeline example

Assume we have data from **Jan 2021 to Dec 2023** (3 years = 36 months).
`min_train_months = 6`, `oos_months = 1`

```
Month:    1    2    3    4    5    6    7    8    9   10   11   12  ...  36
          J    F    M    A    M    J    J    A    S    O    N    D  ...

Fold 0:  [═════════════════Train══════════════] [OOS]
         Jan ─────────────────────── Jun         Jul

Fold 1:  [══════════════════Train═══════════════════][OOS]
         Jan ──────────────────────────── Jul         Aug

Fold 2:  [═══════════════════Train════════════════════════][OOS]
         Jan ─────────────────────────────── Aug              Sep

...

Fold 29: [══════════════════════════Train══════════════════════════][OOS]
         Jan ────────────────────────────────────────── Nov         Dec
```

**Total folds = 30**

Each fold's OOS predictions contribute 1 month of signal data.
All 30 months of OOS predictions are stacked = **30 months of signal history** for backtesting.

---

### Why NOT use standard K-fold?

```
STANDARD K-FOLD (WRONG for time series):

Fold 1:  [Test][═══Train═══════════════════════]
Fold 2:  [═Train═][Test][═══Train═══════════════]
Fold 3:  [══Train══════][Test][═══Train══════════]

Problem: The model in Fold 1 trains on data AFTER the test period.
         This is look-ahead bias — it "knows the future."
         Metrics look great but don't reflect real performance.

WALK-FORWARD (CORRECT):

Fold 1:  [═══Train═════][Test]
Fold 2:  [═════Train════════][Test]
Fold 3:  [═══════Train═══════════][Test]

✓ Model never sees future data
✓ Reflects real-world deployment scenario
✓ Catches model degradation over time
```

---

### Per-fold performance tracking

The monitor tracks performance across folds to detect **model drift**:

```
Fold  │ Train End  │ OOS Period  │ Win Rate │ PF   │ Trades
──────┼────────────┼─────────────┼──────────┼──────┼───────
0     │ Jun 2021   │ Jul 2021    │ 0.581    │ 1.52 │ 62
1     │ Jul 2021   │ Aug 2021    │ 0.564    │ 1.38 │ 58
2     │ Aug 2021   │ Sep 2021    │ 0.571    │ 1.44 │ 55
...
15    │ Sep 2022   │ Oct 2022    │ 0.498    │ 0.94 │ 71   ← drift!
16    │ Oct 2022   │ Nov 2022    │ 0.512    │ 1.07 │ 68
...
```

When performance degrades over multiple consecutive folds, the monitoring system flags potential regime change.

---

## 11. Label Generation

**File:** `src/models/xgboost/labels.py`

### Forward-looking return classification

Labels are generated using **future price data** — this is only valid during training (the model never sees future data at inference time).

```python
# For each candle at time T:
forward_return = close(T + 12) / close(T) - 1   # 12 candles = 1 hour ahead

if forward_return > +0.003:   label = +1   # Long — price rises 0.3%+ in 1h
if forward_return < -0.003:   label = -1   # Short — price falls 0.3%+ in 1h
otherwise:                    label =  0   # Skip — price stays flat
```

### Why 0.3% threshold?

```
Round-trip cost:  ~0.16% (fees + slippage)
Safety buffer:    ~0.14%
Minimum move:      0.30%

A trade only makes sense if the expected move covers costs.
Smaller threshold → too many marginal trades that get eaten by fees.
Larger threshold → too few trades, model under-trains.
```

### Label distribution (typical)

```
Long (+1):  ~22% of candles
Short (-1): ~20% of candles
Skip (0):   ~58% of candles
```

The class imbalance (skip dominates) is handled via `scale_pos_weight` in XGBoost.

### Last N candles

The last 12 candles in any dataset receive `NaN` labels (there's no future data to look at). These rows are dropped before training.

---

## 12. Feature Groups Reference

### Complete feature list

| # | Feature              | Group       | Lookback | Type       |
|---|----------------------|-------------|----------|------------|
| 1 | ret_1                | Price       | 1        | Float      |
| 2 | ret_5                | Price       | 5        | Float      |
| 3 | ret_15               | Price       | 15       | Float      |
| 4 | ret_60               | Price       | 60       | Float      |
| 5 | atr_14               | Price       | 14       | Float      |
| 6 | volatility_20        | Price       | 20       | Float      |
| 7 | hl_ratio             | Price       | 1        | Float      |
| 8 | co_ratio             | Price       | 1        | Float      |
| 9 | upper_wick           | Price       | 1        | Float      |
|10 | lower_wick           | Price       | 1        | Float      |
|11 | volume_ratio         | Price       | 20       | Float      |
|12 | fvg_bullish          | ICT/SMC     | 3        | Binary     |
|13 | fvg_bearish          | ICT/SMC     | 3        | Binary     |
|14 | fvg_distance         | ICT/SMC     | varies   | Float      |
|15 | ob_bullish           | ICT/SMC     | 10       | Binary     |
|16 | ob_bearish           | ICT/SMC     | 10       | Binary     |
|17 | ob_distance          | ICT/SMC     | varies   | Float      |
|18 | bos_up               | ICT/SMC     | 20       | Binary     |
|19 | bos_down             | ICT/SMC     | 20       | Binary     |
|20 | choch                | ICT/SMC     | 20       | Binary     |
|21 | liq_sweep_high       | ICT/SMC     | 10       | Binary     |
|22 | liq_sweep_low        | ICT/SMC     | 10       | Binary     |
|23 | swing_high_dist      | ICT/SMC     | 20       | Float      |
|24 | swing_low_dist       | ICT/SMC     | 20       | Float      |
|25 | vol_percentile       | Regime      | 60       | Float      |
|26 | adx_14               | Regime      | 14       | Float      |
|27 | volume_zscore        | Regime      | 20       | Float      |
|28 | regime_vol           | Regime      | 60       | Int {0,1,2}|
|29 | taker_buy_ratio      | Order Flow  | 1        | Float      |
|30 | taker_sell_ratio     | Order Flow  | 1        | Float      |
|31 | cvd                  | Order Flow  | all      | Float      |
|32 | cvd_20               | Order Flow  | 20       | Float      |
|33 | cvd_divergence       | Order Flow  | 60       | Binary     |
|34 | oi_delta             | Order Flow  | 1        | Float      |
|35 | htf_4h_ema_fast      | HTF Align   | 20       | Float      |
|36 | htf_4h_ema_slow      | HTF Align   | 50       | Float      |
|37 | htf_4h_trend         | HTF Align   | 50       | Int {-1,1} |
|38 | htf_1d_ema_fast      | HTF Align   | 20       | Float      |
|39 | htf_1d_ema_slow      | HTF Align   | 50       | Float      |
|40 | htf_1d_trend         | HTF Align   | 50       | Int {-1,1} |
|41 | htf_fvg_distance     | HTF Align   | varies   | Float      |

---

## 13. Risk Management & Cost Model

### Trade lifecycle

```
Signal arrives from XGBoost
        │
        ▼
[Gate 1] Confidence ≥ 0.55?
        │ No → SKIP
        │ Yes ↓
[Gate 2] Circuit breaker active?
        │ Yes → SKIP (cooldown)
        │ No ↓
RL agent determines position size
        │
        ▼
[Gate 3] Position size × leverage ≤ limits?
        │ Clamp to max if exceeded
        ↓
Enter trade (pay entry fee + slippage)
        │
        ▼ (each subsequent 5m candle)
┌──────────────────────────────────────┐
│ Check exit conditions (in order):    │
│                                      │
│ 1. Max drawdown circuit breaker?     │
│    → CLOSE ALL, start cooldown       │
│                                      │
│ 2. Stop loss hit? (−2%)              │
│    → EXIT, exit_reason = stop_loss   │
│                                      │
│ 3. Trailing stop hit? (−1.5% from peak)│
│    → EXIT, exit_reason = trailing   │
│                                      │
│ 4. New opposing signal?              │
│    → EXIT, exit_reason = signal_flip │
│                                      │
│ 5. Time stop (96 candles / 8 hours)? │
│    → EXIT, exit_reason = time_stop   │
│                                      │
│ 6. None of above → HOLD              │
└──────────────────────────────────────┘
        │
        ▼
Pay exit fee + slippage + accumulated funding
Record trade metrics
Update equity curve
```

---

## 14. Hyperparameter Reference

### XGBoost (`configs/xgboost.yaml`)

```yaml
label:
  forward_candles: 12         # Look-ahead for label generation (12 × 5m = 1h)
  threshold_pct: 0.003        # Minimum move to assign non-zero label (0.3%)
  use_atr_threshold: false    # If true, threshold adapts to ATR

model:
  n_estimators: 500           # Number of boosting rounds
  max_depth: 6                # Max tree depth
  learning_rate: 0.05         # Eta (shrinkage)
  subsample: 0.8              # Row sample fraction per tree
  colsample_bytree: 0.8       # Feature sample fraction per tree
  min_child_weight: 5         # Min sum of weights in leaf
  gamma: 0.1                  # Min loss reduction to split
  reg_alpha: 0.1              # L1 regularization
  reg_lambda: 1.0             # L2 regularization
  early_stopping_rounds: 50   # Stop if no improvement in 50 rounds
  eval_fraction: 0.1          # Use last 10% of training fold as eval set

walk_forward:
  train_months: 12            # Initial training window size
  oos_months: 1               # OOS test window size
  min_train_months: 6         # Minimum window before first fold
  sample_weight_decay: 0.9995 # Exponential time decay for sample weights
```

### PPO / RL (`configs/rl.yaml`)

```yaml
ppo:
  learning_rate: 0.0003       # Adam LR
  n_steps: 2048               # Steps per rollout buffer
  batch_size: 64              # Mini-batch size
  n_epochs: 10                # Policy update epochs per rollout
  gamma: 0.99                 # Discount factor
  gae_lambda: 0.95            # GAE lambda
  clip_range: 0.2             # PPO epsilon clip
  ent_coef: 0.01              # Entropy coefficient
  vf_coef: 0.5                # Value function loss coefficient
  max_grad_norm: 0.5          # Gradient clipping
  total_timesteps: 1000000    # Total training steps

environment:
  episode_days: 30            # Episode length in days
  initial_capital: 10000.0    # Starting capital (USD)
  max_leverage: 3.0           # Maximum leverage allowed
  fee_rate: 0.0006            # Taker fee rate (0.06%)
  slippage_rate: 0.0002       # Slippage per side (0.02%)
  funding_rate: 0.0001        # Funding per 8h (0.01%)
  funding_interval_candles: 96 # 96 × 5m = 8 hours
  min_confidence: 0.55        # Gate: skip trade if XGB confidence below this
  reward_scale: 100.0         # Scale returns for reward signal
  drawdown_penalty: 0.5       # Penalty coefficient for drawdown > 5%
  idle_penalty: 0.01          # Penalty per step when flat (no position)
```

### Pipeline (`configs/pipeline.yaml`)

```yaml
data:
  symbol: BTCUSDT
  primary_tf: 5m
  htf_list: [4h, 1d]
  lookback_years: 3

backtest:
  max_position_pct: 0.01      # 1% of capital per trade max
  max_leverage: 3.0
  stop_loss_pct: 0.02         # 2% stop loss
  trailing_stop_pct: 0.015    # 1.5% trailing stop
  time_stop_candles: 96       # 96 candles = 8h time stop
  max_drawdown_pct: 0.15      # 15% portfolio-level circuit breaker
  cooldown_candles: 12        # 12 candle cooldown after circuit break

gates:
  xgb_evaluate:
    win_rate: { threshold: 0.52, direction: gte }
    profit_factor: { threshold: 1.1, direction: gte }
    n_trades: { threshold: 50, direction: gte }
  backtest:
    max_drawdown: { threshold: 0.20, direction: lte }
    total_return: { threshold: 0.0, direction: gt }
    sharpe: { threshold: 0.5, direction: gte }
```

---

## 15. Validation Gates Reference

Gates act as checkpoints. Failing a gate halts training and saves the partial run for debugging.

```
┌────────────────────────────────────────────────────────────────┐
│  GATE EVALUATION FLOW                                          │
│                                                                │
│  for each metric in gate:                                      │
│    if direction == "gte":                                      │
│      pass = metric_value >= threshold                         │
│    if direction == "lte":                                      │
│      pass = metric_value <= threshold                         │
│    if direction == "gt":                                       │
│      pass = metric_value > threshold                          │
│                                                                │
│  overall_pass = ALL individual metrics pass                    │
│                                                                │
│  if not overall_pass:                                          │
│    log each failing metric with actual vs threshold           │
│    set pipeline status = GATE_FAILED                           │
│    save run state (allow inspection/debugging)                │
│    raise PipelineGateError                                     │
└────────────────────────────────────────────────────────────────┘
```

---

## 16. File Map

```
/home/user/F-RL-V1/
│
├── MODEL_TRAINING_GUIDE.md          ← this file
│
├── btc-hybrid-trader/
│   │
│   ├── configs/
│   │   ├── pipeline.yaml            Pipeline settings, risk params, gates
│   │   ├── xgboost.yaml             XGBoost model + walk-forward params
│   │   ├── rl.yaml                  PPO hyperparams + environment config
│   │   └── features.yaml            Feature engineering parameters
│   │
│   ├── src/
│   │   │
│   │   ├── pipeline/
│   │   │   ├── orchestrator.py      Master pipeline: 7 stages, checkpoint/resume
│   │   │   └── monitor.py           Progress tracking, gate evaluation
│   │   │
│   │   ├── data/
│   │   │   ├── downloader.py        Binance FAPI downloader (3 timeframes)
│   │   │   └── storage.py           Parquet read/write, caching
│   │   │
│   │   ├── features/
│   │   │   ├── engine.py            Feature orchestration + cleaning pipeline
│   │   │   ├── price_action.py      Returns, ATR, volatility, OHLCV ratios
│   │   │   ├── ict_smc.py           FVG, Order Blocks, BOS, CHoCH, sweeps
│   │   │   ├── regime.py            Vol percentile, ADX, regime classification
│   │   │   ├── order_flow.py        Taker ratios, CVD, OI delta
│   │   │   └── htf_alignment.py     4h/1d EMA trends, HTF FVG levels
│   │   │
│   │   ├── models/
│   │   │   │
│   │   │   ├── xgboost/
│   │   │   │   ├── train.py         Walk-forward fold training + splitting
│   │   │   │   ├── labels.py        Ternary label generation + sample weights
│   │   │   │   ├── evaluate.py      OOS metrics, SHAP feature importance
│   │   │   │   └── predict.py       Inference on new data
│   │   │   │
│   │   │   └── rl/
│   │   │       ├── train.py         PPO training via Stable-Baselines3
│   │   │       ├── env.py           Gymnasium trading environment
│   │   │       └── evaluate.py      RL evaluation (Sharpe, drawdown, win rate)
│   │   │
│   │   └── backtest/
│   │       ├── advanced_simulator.py  Full production backtest engine
│   │       ├── walk_forward.py        Walk-forward validation harness
│   │       └── metrics.py             Sharpe, drawdown, profit factor calculators
│   │
│   ├── runs/                        Training run outputs (per run_id)
│   │   └── <run_id>/
│   │       ├── data/                Cached OHLCV parquet files
│   │       ├── features/            Feature DataFrame
│   │       ├── models/
│   │       │   ├── xgb_fold_0.json  XGBoost model for fold 0
│   │       │   ├── xgb_fold_1.json
│   │       │   ├── ...
│   │       │   └── ppo_agent.zip    PPO model checkpoint
│   │       ├── predictions.parquet  Concatenated OOS predictions
│   │       ├── backtest.parquet     Per-trade simulation results
│   │       └── report.json          Final metrics report
│   │
│   └── models/                      Symlink or copy of best run's models
│       ├── xgb_fold_latest.json     Latest production XGBoost
│       └── ppo_agent_latest.zip     Latest production PPO
│
└── Backend/
    └── internal/handlers/
        └── pipeline.go              HTTP API: trigger/monitor/report pipeline
```

---

## Quick Reference: Training Numbers

| Parameter                    | Value         |
|------------------------------|---------------|
| Primary timeframe            | 5m            |
| Feature count                | ~41 features  |
| Label lookahead              | 12 candles (1h) |
| Label threshold              | ±0.3%         |
| Training window              | 12 months expanding |
| OOS window per fold          | 1 month       |
| Minimum training window      | 6 months      |
| Folds (3y dataset)           | ~30 folds     |
| Folds (4y dataset)           | ~42 folds     |
| XGBoost trees per fold       | 500 (max)     |
| XGBoost early stopping       | 50 rounds     |
| PPO total timesteps          | 1,000,000     |
| PPO rollout size             | 2,048 steps   |
| PPO update epochs            | 10            |
| Episode length               | 30 days       |
| Max leverage                 | 3x            |
| Stop loss                    | 2%            |
| Trailing stop                | 1.5%          |
| Time stop                    | 8 hours       |
| Circuit breaker              | 15% drawdown  |
| Entry fee                    | 0.06%         |
| Exit fee                     | 0.06%         |
| Slippage (each side)         | 0.02%         |
| Funding (per 8h)             | 0.01%         |

---

*Last updated: March 2026*
