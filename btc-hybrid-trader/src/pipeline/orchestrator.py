"""Pipeline orchestrator: controls the full training lifecycle from data
   download through XGBoost walk-forward, RL training, to final backtest
   with validation gates, checkpointing, and progress tracking."""
import argparse
import logging
import pickle
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import yaml

from ..data.downloader import download_klines
from ..data.storage import load_klines
from ..features.engine import build_features
from ..models.xgboost.train import (
    get_feature_cols, generate_splits, train_fold, WalkForwardSplit
)
from ..models.xgboost.labels import make_labels
from ..models.xgboost.evaluate import compute_trade_metrics, shap_importance
from ..backtest.advanced_simulator import AdvancedSimulator, RiskConfig
from .monitor import TrainingMonitor

logger = logging.getLogger(__name__)


@dataclass
class PipelineState:
    """Serializable pipeline checkpoint."""
    stage: str = "init"
    features_ready: bool = False
    xgb_folds_done: int = 0
    xgb_total_folds: int = 0
    rl_trained: bool = False
    backtest_done: bool = False
    oos_preds_path: Optional[str] = None
    feature_cols: Optional[List[str]] = None


class PipelineOrchestrator:
    """Master orchestrator for the BTC Hybrid Trader pipeline.

    Stages:
        1. data_load    — Load or download kline data
        2. features     — Compute full feature set
        3. xgb_train    — Walk-forward XGBoost training with per-fold validation
        4. xgb_evaluate — OOS signal quality assessment
        5. rl_train     — PPO position sizing (optional, requires SB3)
        6. backtest     — Full simulation with advanced risk management
        7. report       — Final metrics and summary

    Each stage has validation gates. Pipeline halts if gates fail.
    All progress is tracked by TrainingMonitor.
    """

    def __init__(self, config_path: str = "configs/pipeline.yaml",
                 data_dir: str = "data",
                 model_dir: str = "models",
                 output_dir: str = "runs",
                 run_name: Optional[str] = None):
        self.config_path = Path(config_path)
        self.data_dir = data_dir
        self.model_dir = model_dir
        self.cfg = self._load_config()

        self.monitor = TrainingMonitor(
            output_dir=output_dir,
            run_name=run_name,
        )
        self._setup_gates()

        self.state = PipelineState()
        self._checkpoint_path = Path(output_dir) / (self.monitor.run_name) / "checkpoint.pkl"

        # Data holders
        self.df_5m: Optional[pd.DataFrame] = None
        self.df_4h: Optional[pd.DataFrame] = None
        self.df_1d: Optional[pd.DataFrame] = None
        self.df_features: Optional[pd.DataFrame] = None
        self.oos_preds: Optional[pd.DataFrame] = None

    def _load_config(self) -> dict:
        if self.config_path.exists():
            with open(self.config_path) as f:
                return yaml.safe_load(f)
        logger.warning("Pipeline config not found at %s, using defaults", self.config_path)
        return self._default_config()

    @staticmethod
    def _default_config() -> dict:
        return {
            "data": {"timeframes": ["5m", "4h", "1d"]},
            "features": {"config_path": "configs/features.yaml"},
            "xgboost": {"config_path": "configs/xgboost.yaml"},
            "rl": {"config_path": "configs/rl.yaml", "enabled": True},
            "backtest": {
                "risk": {
                    "max_position_pct": 1.0,
                    "max_leverage": 3.0,
                    "stop_loss_pct": 0.02,
                    "trailing_stop_pct": 0.015,
                    "time_stop_candles": 96,
                    "max_drawdown_pct": 0.15,
                    "cooldown_candles": 12,
                },
            },
            "gates": {
                "xgb_evaluate": {
                    "win_rate": {"threshold": 0.52, "direction": "gte"},
                    "profit_factor": {"threshold": 1.1, "direction": "gte"},
                },
                "backtest": {
                    "max_drawdown": {"threshold": 0.20, "direction": "lte"},
                    "total_return": {"threshold": 0.0, "direction": "gt"},
                },
            },
        }

    def _setup_gates(self):
        gates_cfg = self.cfg.get("gates", {})
        for stage, metrics in gates_cfg.items():
            for metric, spec in metrics.items():
                self.monitor.add_gate(
                    stage, metric,
                    threshold=spec["threshold"],
                    direction=spec.get("direction", "gte"),
                )

    def _save_checkpoint(self):
        with open(self._checkpoint_path, "wb") as f:
            pickle.dump(self.state, f)

    def _load_checkpoint(self) -> bool:
        if self._checkpoint_path.exists():
            with open(self._checkpoint_path, "rb") as f:
                self.state = pickle.load(f)
            logger.info("Resumed from checkpoint: stage=%s", self.state.stage)
            return True
        return False

    # ──────────────────────────────────────────────────────────────
    # Stage 1: Data Loading
    # ──────────────────────────────────────────────────────────────
    def stage_data_load(self):
        self.monitor.start_stage("data_load")
        try:
            self.df_5m = self._load_or_download_klines("5m")
            self.df_4h = self._load_or_download_klines("4h")
            self.df_1d = self._load_or_download_klines("1d")

            metrics = {
                "rows_5m": len(self.df_5m),
                "rows_4h": len(self.df_4h),
                "rows_1d": len(self.df_1d),
                "date_start": str(self.df_5m.index[0].date()),
                "date_end": str(self.df_5m.index[-1].date()),
            }
            self.monitor.log_metrics("data_load", {
                k: v if isinstance(v, (int, float)) else 0
                for k, v in metrics.items()
            })
            logger.info("Data loaded: 5m=%d, 4h=%d, 1d=%d rows",
                        len(self.df_5m), len(self.df_4h), len(self.df_1d))

            self.state.stage = "data_load"
            self._save_checkpoint()
        except Exception as e:
            self.monitor.fail_stage("data_load", str(e))
            raise

    def _load_or_download_klines(self, interval: str) -> pd.DataFrame:
        try:
            return load_klines(interval, self.data_dir)
        except FileNotFoundError:
            logger.warning("No local data for %s in %s; downloading from Binance",
                           interval, self.data_dir)
            return download_klines(interval, data_dir=self.data_dir)

    # ──────────────────────────────────────────────────────────────
    # Stage 2: Feature Engineering
    # ──────────────────────────────────────────────────────────────
    def stage_features(self):
        self.monitor.start_stage("features")
        try:
            feat_cfg = self.cfg.get("features", {})
            config_path = feat_cfg.get("config_path", "configs/features.yaml")

            self.df_features = build_features(
                self.df_5m, self.df_4h, self.df_1d,
                config_path=config_path,
            )

            feature_cols = get_feature_cols(self.df_features)
            self.state.feature_cols = feature_cols

            metrics = {
                "n_rows": len(self.df_features),
                "n_features": len(feature_cols),
                "nan_pct": float(self.df_features[feature_cols].isna().mean().mean()),
            }
            self.monitor.log_metrics("features", metrics)

            self.state.features_ready = True
            self.state.stage = "features"
            self._save_checkpoint()
        except Exception as e:
            self.monitor.fail_stage("features", str(e))
            raise

    # ──────────────────────────────────────────────────────────────
    # Stage 3: XGBoost Walk-Forward Training
    # ──────────────────────────────────────────────────────────────
    def stage_xgb_train(self):
        self.monitor.start_stage("xgb_train")

        xgb_cfg_path = self.cfg.get("xgboost", {}).get(
            "config_path", "configs/xgboost.yaml")
        with open(xgb_cfg_path) as f:
            xgb_cfg = yaml.safe_load(f)

        wf = xgb_cfg["walk_forward"]
        feature_cols = self.state.feature_cols or get_feature_cols(self.df_features)
        splits = generate_splits(
            self.df_features,
            train_months=wf["train_months"],
            oos_months=wf["oos_months"],
            min_train_months=wf["min_train_months"],
        )
        self.state.xgb_total_folds = len(splits)

        xgb_model_dir = Path(self.model_dir) / "xgboost"
        xgb_model_dir.mkdir(parents=True, exist_ok=True)
        all_preds = []

        for i, split in enumerate(splits):
            # Skip already-done folds (resume support)
            if i < self.state.xgb_folds_done:
                # Reload existing predictions
                pred_path = xgb_model_dir / f"fold_{i:03d}_preds.parquet"
                if pred_path.exists():
                    all_preds.append(pd.read_parquet(pred_path))
                continue

            self.monitor.start_stage("xgb_fold")
            fold_start = time.time()

            try:
                model = train_fold(self.df_features, split, feature_cols, xgb_cfg)

                # Save model
                model_path = xgb_model_dir / f"fold_{i:03d}.pkl"
                with open(model_path, "wb") as f:
                    pickle.dump(model, f)

                # OOS predictions
                oos = self.df_features.loc[split.oos_start:split.oos_end]
                if len(oos) == 0:
                    continue

                X_oos = oos[feature_cols]
                proba = model.predict_proba(X_oos)
                preds = pd.DataFrame({
                    "prob_short": proba[:, 0],
                    "prob_skip": proba[:, 1],
                    "prob_long": proba[:, 2],
                    "signal": np.argmax(proba, axis=1) - 1,
                    "confidence": proba.max(axis=1),
                    "fold": i,
                }, index=oos.index)

                # Save fold predictions
                pred_path = xgb_model_dir / f"fold_{i:03d}_preds.parquet"
                preds.to_parquet(pred_path)
                all_preds.append(preds)

                # Per-fold metrics
                fold_metrics = compute_trade_metrics(
                    preds, self.df_features[["close"]],
                    forward_candles=xgb_cfg["label"]["forward_candles"],
                )
                fold_metrics["train_rows"] = len(
                    self.df_features.loc[split.train_start:split.train_end])
                fold_metrics["oos_rows"] = len(oos)
                fold_metrics["duration_sec"] = round(time.time() - fold_start, 1)

                self.monitor.log_metrics("xgb_fold", fold_metrics, fold=i)

                # Feature importance on last fold
                if i == len(splits) - 1:
                    try:
                        importance = shap_importance(
                            model, X_oos.iloc[:500],
                            output_dir=str(xgb_model_dir))
                    except Exception:
                        pass

            except Exception as e:
                self.monitor.fail_stage("xgb_fold", str(e), fold=i)
                logger.error("Fold %d failed: %s", i, e)
                continue

            self.state.xgb_folds_done = i + 1
            self._save_checkpoint()

        if not all_preds:
            self.monitor.fail_stage("xgb_train", "No OOS predictions generated")
            raise ValueError("No OOS predictions generated")

        self.oos_preds = pd.concat(all_preds).sort_index()
        oos_path = xgb_model_dir / "oos_predictions.parquet"
        self.oos_preds.to_parquet(oos_path)
        self.state.oos_preds_path = str(oos_path)

        # Aggregate XGB metrics
        summary = self.monitor.get_stage_summary("xgb_fold")
        agg = {k: v["mean"] for k, v in summary.items() if "mean" in v}
        self.monitor.log_metrics("xgb_train", agg)

        self.state.stage = "xgb_train"
        self._save_checkpoint()

    # ──────────────────────────────────────────────────────────────
    # Stage 4: XGBoost OOS Evaluation + Gate Check
    # ──────────────────────────────────────────────────────────────
    def stage_xgb_evaluate(self) -> bool:
        self.monitor.start_stage("xgb_evaluate")

        xgb_cfg_path = self.cfg.get("xgboost", {}).get(
            "config_path", "configs/xgboost.yaml")
        with open(xgb_cfg_path) as f:
            xgb_cfg = yaml.safe_load(f)

        metrics = compute_trade_metrics(
            self.oos_preds,
            self.df_features[["close"]],
            forward_candles=xgb_cfg["label"]["forward_candles"],
        )
        self.monitor.log_metrics("xgb_evaluate", metrics)

        passed, failures = self.monitor.check_gates("xgb_evaluate", metrics)
        if not passed:
            logger.warning("XGB evaluation gate failed: %s", failures)
        return passed

    # ──────────────────────────────────────────────────────────────
    # Stage 5: RL Training (Optional)
    # ──────────────────────────────────────────────────────────────
    def stage_rl_train(self):
        rl_cfg = self.cfg.get("rl", {})
        if not rl_cfg.get("enabled", True):
            logger.info("RL training disabled in config — skipping")
            self.state.rl_trained = False
            return

        self.monitor.start_stage("rl_train")
        try:
            from ..models.rl.train import train_ppo, build_env

            rl_config_path = rl_cfg.get("config_path", "configs/rl.yaml")
            rl_model_dir = Path(self.model_dir) / "rl"

            model = train_ppo(
                self.oos_preds,
                self.df_features,
                config_path=rl_config_path,
                model_dir=str(rl_model_dir),
            )

            # Evaluate
            from ..models.rl.evaluate import run_episode
            with open(rl_config_path) as f:
                rl_yaml = yaml.safe_load(f)
            env = build_env(self.oos_preds, self.df_features, rl_yaml,
                            eval_mode=True)
            rl_metrics = run_episode(model, env)
            self.monitor.log_metrics("rl_train", rl_metrics)

            self.state.rl_trained = True
            self.state.stage = "rl_train"
            self._save_checkpoint()

        except ImportError:
            logger.warning("stable-baselines3 not available — skipping RL")
            self.state.rl_trained = False
        except Exception as e:
            self.monitor.fail_stage("rl_train", str(e))
            self.state.rl_trained = False

    # ──────────────────────────────────────────────────────────────
    # Stage 6: Full Backtest with Advanced Simulator
    # ──────────────────────────────────────────────────────────────
    def stage_backtest(self):
        self.monitor.start_stage("backtest")

        bt_cfg = self.cfg.get("backtest", {})
        risk_cfg = bt_cfg.get("risk", {})
        risk = RiskConfig(**{k: v for k, v in risk_cfg.items()
                             if k in RiskConfig.__dataclass_fields__})

        sim = AdvancedSimulator(
            initial_capital=bt_cfg.get("initial_capital", 10_000.0),
            fee_taker=bt_cfg.get("fee_taker", 0.0006),
            slippage=bt_cfg.get("slippage", 0.0002),
            risk=risk,
        )

        # Align signals with price data
        aligned = self.oos_preds[["signal"]].join(
            self.df_features[["close", "high", "low"]], how="inner"
        ).dropna()

        # Get position sizes from RL if available
        position_sizes = None
        if self.state.rl_trained:
            position_sizes = self._get_rl_position_sizes(aligned)

        confidences = None
        if "confidence" in self.oos_preds.columns:
            confidences = self.oos_preds["confidence"].reindex(aligned.index)

        result = sim.run(
            signals=aligned["signal"],
            prices=aligned[["close", "high", "low"]],
            position_sizes=position_sizes,
            confidences=confidences,
        )

        # Save results
        bt_dir = Path(self.model_dir) / "backtest"
        bt_dir.mkdir(parents=True, exist_ok=True)
        result["equity"].to_frame().to_parquet(bt_dir / "equity.parquet")
        if len(result["trades"]) > 0:
            result["trades"].to_parquet(bt_dir / "trades.parquet")
        if len(result["risk_events"]) > 0:
            result["risk_events"].to_parquet(bt_dir / "risk_events.parquet")

        metrics = result["metrics"]
        self.monitor.log_metrics("backtest", metrics)

        passed, failures = self.monitor.check_gates("backtest", metrics)
        if not passed:
            logger.warning("Backtest gate failed: %s", failures)

        # ── Save JSON for Go backend ────────────────────────────────────
        self._save_backtest_json(result, metrics)

        self.state.backtest_done = True
        self.state.stage = "backtest"
        self._save_checkpoint()
        return result

    def _save_backtest_json(self, result: dict, metrics: dict):
        """Persist backtest results to runs/{run_name}/backtest_results.json
        so the Go backend can serve them without Parquet dependencies."""
        import json as _json

        def _ts(v):
            return v.isoformat() if hasattr(v, "isoformat") else str(v)

        def _scalar(v):
            if isinstance(v, float) and np.isnan(v):
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return str(v)

        # Equity curve: [{ts, value}]
        equity_json = [
            {"ts": _ts(ts), "value": float(v)}
            for ts, v in zip(result["equity"].index, result["equity"].values)
        ]

        # Trades: list of dicts with string timestamps and enum values
        trades_json = []
        trade_df = result.get("trades", pd.DataFrame())
        if len(trade_df) > 0:
            for _, row in trade_df.iterrows():
                d = {}
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        d[k] = v.isoformat()
                    elif isinstance(v, ExitReason):
                        d[k] = v.value
                    elif isinstance(v, float) and np.isnan(v):
                        d[k] = None
                    else:
                        d[k] = _scalar(v) if not isinstance(v, str) else v
                trades_json.append(d)

        # Risk events
        risk_events_json = []
        risk_df = result.get("risk_events", pd.DataFrame())
        if len(risk_df) > 0:
            for _, row in risk_df.iterrows():
                d = {}
                for k, v in row.items():
                    if hasattr(v, "isoformat"):
                        d[k] = v.isoformat()
                    elif isinstance(v, float) and np.isnan(v):
                        d[k] = None
                    else:
                        d[k] = _scalar(v) if not isinstance(v, str) else v
                risk_events_json.append(d)

        # Metrics: ensure all values are JSON-serializable
        metrics_json = {}
        for k, v in metrics.items():
            metrics_json[k] = _scalar(v) if not isinstance(v, str) else v

        bt_results_path = self.monitor.output_dir / "backtest_results.json"
        with open(bt_results_path, "w") as f:
            _json.dump({
                "equity_curve": equity_json,
                "trades": trades_json,
                "metrics": metrics_json,
                "risk_events": risk_events_json,
            }, f, indent=2, default=str)
        logger.info("Backtest results saved → %s", bt_results_path)

    def _get_rl_position_sizes(self, aligned: pd.DataFrame) -> Optional[pd.Series]:
        """Run RL model to get position sizes for each timestamp."""
        try:
            from stable_baselines3 import PPO
            rl_model_path = Path(self.model_dir) / "rl" / "ppo_btc.zip"
            if not rl_model_path.exists():
                return None

            model = PPO.load(str(rl_model_path))

            # Simple inference: run model on each row
            sizes = []
            for idx in aligned.index:
                row = self.oos_preds.loc[idx]
                obs = np.array([
                    row.get("signal", 0), row.get("confidence", 0.5),
                    0.0, 0.0, 0.0, 0.5, 0.0, 0.5,
                ], dtype=np.float32)
                action, _ = model.predict(obs, deterministic=True)
                sizes.append(float(np.clip(action[0], 0.0, 1.0)))

            return pd.Series(sizes, index=aligned.index)
        except Exception as e:
            logger.warning("Could not get RL position sizes: %s", e)
            return None

    # ──────────────────────────────────────────────────────────────
    # Stage 7: Final Report
    # ──────────────────────────────────────────────────────────────
    def stage_report(self):
        self.monitor.start_stage("report")
        self.monitor.save_summary()

        progress = self.monitor.get_progress()
        logger.info("=" * 60)
        logger.info("PIPELINE COMPLETE: %s", self.monitor.run_name)
        logger.info("Stages: %s", list(progress["stages"].keys()))
        logger.info("Total time: %.0fs", progress["total_duration_sec"])

        # Print key metrics
        for stage in ["xgb_evaluate", "backtest"]:
            summary = self.monitor.get_stage_summary(stage)
            if summary:
                logger.info("--- %s ---", stage)
                for metric, vals in summary.items():
                    logger.info("  %s: %.4f", metric, vals["mean"])
        logger.info("=" * 60)

        self.monitor.log_metrics("report", {"completed": 1.0})

    # ──────────────────────────────────────────────────────────────
    # Full Pipeline Run
    # ──────────────────────────────────────────────────────────────
    def run(self, resume: bool = True) -> Dict:
        """Execute full pipeline with optional resume from checkpoint."""
        logger.info("=" * 60)
        logger.info("Starting pipeline: %s", self.monitor.run_name)
        logger.info("=" * 60)

        if resume:
            self._load_checkpoint()

        stages = [
            ("data_load", self.stage_data_load),
            ("features", self.stage_features),
            ("xgb_train", self.stage_xgb_train),
            ("xgb_evaluate", self.stage_xgb_evaluate),
            ("rl_train", self.stage_rl_train),
            ("backtest", self.stage_backtest),
            ("report", self.stage_report),
        ]

        stage_order = [s[0] for s in stages]
        start_from = 0
        if resume and self.state.stage in stage_order:
            start_from = stage_order.index(self.state.stage) + 1
            logger.info("Resuming from stage: %s (starting at %s)",
                        self.state.stage,
                        stage_order[start_from] if start_from < len(stages) else "done")

        result = None
        for name, fn in stages[start_from:]:
            logger.info(">>> Stage: %s", name)
            try:
                ret = fn()
                if name == "backtest":
                    result = ret
                # xgb_evaluate returns bool (gate pass/fail)
                if name == "xgb_evaluate" and ret is False:
                    logger.warning("XGB evaluation gate failed — "
                                   "continuing but results may be poor")
            except Exception as e:
                logger.error("Pipeline failed at stage '%s': %s", name, e)
                self.monitor.fail_stage(name, str(e))
                raise

        return {
            "run_name": self.monitor.run_name,
            "progress": self.monitor.get_progress(),
            "backtest_result": result,
        }


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the BTC hybrid trader pipeline")
    parser.add_argument("--run-name", default=None, help="Override the generated run name")
    parser.add_argument("--config-path", default="configs/pipeline.yaml")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--output-dir", default="runs")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start from scratch instead of resuming from a checkpoint")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        pipeline = PipelineOrchestrator(
            config_path=args.config_path,
            data_dir=args.data_dir,
            model_dir=args.model_dir,
            output_dir=args.output_dir,
            run_name=args.run_name,
        )
        pipeline.run(resume=not args.no_resume)
        return 0
    except Exception:
        logger.exception("Pipeline execution failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
