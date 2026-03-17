"""Walk-forward validation engine."""
import logging
from pathlib import Path
from typing import List

import pandas as pd
import yaml

from .simulator import TradeSimulator
from .metrics import compute_all

logger = logging.getLogger(__name__)


def run_walk_forward_backtest(oos_preds: pd.DataFrame, df_5m: pd.DataFrame,
                               position_sizes: pd.Series = None,
                               fee_taker: float = 0.0006,
                               slippage: float = 0.0002) -> dict:
    """
    Run walk-forward backtest on OOS predictions.

    Args:
        oos_preds: DataFrame with 'signal' column (from XGB walk-forward)
        df_5m: 5m price data with 'close'
        position_sizes: optional Series of position sizes from RL model
    """
    aligned = oos_preds[["signal"]].join(df_5m[["close"]], how="inner")
    aligned = aligned.dropna()

    sim = TradeSimulator(fee_taker=fee_taker, slippage=slippage)
    result = sim.run(
        signals=aligned["signal"],
        prices=aligned["close"],
        position_sizes=position_sizes.reindex(aligned.index) if position_sizes is not None else None,
    )

    logger.info("Walk-forward backtest complete")
    logger.info("Metrics: %s", {k: round(v, 4) for k, v in result["metrics"].items()
                                if isinstance(v, float)})
    return result
