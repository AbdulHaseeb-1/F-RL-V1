"""XGBoost evaluation: metrics, equity curve, SHAP."""
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEE_MAKER = 0.0004
FEE_TAKER = 0.0006
SLIPPAGE = 0.0002


def compute_trade_metrics(preds: pd.DataFrame, df_prices: pd.DataFrame,
                          forward_candles: int = 12,
                          fee: float = FEE_TAKER + SLIPPAGE) -> dict:
    """
    Compute precision, profit factor, win rate on OOS predictions.
    preds must have 'signal' and 'confidence' columns.
    df_prices must have 'close'.
    """
    aligned = preds.join(df_prices[["close"]], how="inner")
    aligned["fwd_ret"] = aligned["close"].shift(-forward_candles) / aligned["close"] - 1
    aligned = aligned.dropna(subset=["fwd_ret"])

    trades = aligned[aligned["signal"] != 0].copy()
    if len(trades) == 0:
        return {"n_trades": 0}

    # Net return per trade after fees and slippage
    trades["gross_ret"] = trades["fwd_ret"] * trades["signal"]
    trades["net_ret"] = trades["gross_ret"] - fee * 2  # entry + exit

    wins = trades[trades["net_ret"] > 0]
    losses = trades[trades["net_ret"] <= 0]

    gross_profit = wins["net_ret"].sum()
    gross_loss = losses["net_ret"].abs().sum()

    metrics = {
        "n_trades": len(trades),
        "win_rate": len(wins) / len(trades),
        "precision_long": (trades[trades["signal"] == 1]["gross_ret"] > 0).mean()
            if (trades["signal"] == 1).any() else np.nan,
        "precision_short": (trades[trades["signal"] == -1]["gross_ret"] > 0).mean()
            if (trades["signal"] == -1).any() else np.nan,
        "profit_factor": gross_profit / (gross_loss + 1e-9),
        "avg_trade_ret": trades["net_ret"].mean(),
        "total_ret": trades["net_ret"].sum(),
    }
    logger.info("Metrics: %s", {k: round(v, 4) for k, v in metrics.items()
                                if isinstance(v, float)})
    return metrics


def shap_importance(model, X: pd.DataFrame, max_display: int = 20,
                    output_dir: Optional[str] = None) -> pd.DataFrame:
    """Compute SHAP feature importance and optionally save plot."""
    try:
        import shap
    except ImportError:
        logger.warning("shap not installed — skipping SHAP analysis")
        return pd.DataFrame()

    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)

    # For multiclass, average absolute SHAP across classes
    if isinstance(shap_values, list):
        mean_abs = np.mean([np.abs(sv) for sv in shap_values], axis=0).mean(axis=0)
    else:
        mean_abs = np.abs(shap_values).mean(axis=0)

    importance = pd.DataFrame({
        "feature": X.columns,
        "shap_importance": mean_abs,
    }).sort_values("shap_importance", ascending=False).reset_index(drop=True)

    if output_dir:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        importance.to_csv(Path(output_dir) / "shap_importance.csv", index=False)
        logger.info("SHAP importance saved to %s", output_dir)

    return importance


def equity_curve(preds: pd.DataFrame, df_prices: pd.DataFrame,
                 forward_candles: int = 12, fee: float = FEE_TAKER + SLIPPAGE) -> pd.Series:
    """Compute cumulative equity curve from OOS predictions."""
    aligned = preds.join(df_prices[["close"]], how="inner")
    aligned["fwd_ret"] = aligned["close"].shift(-forward_candles) / aligned["close"] - 1
    aligned = aligned.dropna(subset=["fwd_ret"])
    aligned["trade_ret"] = np.where(
        aligned["signal"] != 0,
        aligned["fwd_ret"] * aligned["signal"] - fee * 2,
        0.0,
    )
    return (1 + aligned["trade_ret"]).cumprod()
