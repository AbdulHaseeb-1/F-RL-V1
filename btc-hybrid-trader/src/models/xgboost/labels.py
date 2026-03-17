"""Signal labeling for XGBoost training."""
import numpy as np
import pandas as pd


def make_labels(df: pd.DataFrame, forward_candles: int = 12,
                threshold_pct: float = 0.003,
                use_atr: bool = False) -> pd.Series:
    """
    Classify each candle as Long (+1), Short (-1), or Skip (0).

    Args:
        df: DataFrame with 'close' and optionally 'atr_14'
        forward_candles: lookahead window
        threshold_pct: minimum return to classify as signal
        use_atr: if True, threshold = ATR / close (dynamic)

    Returns:
        Series of labels {-1, 0, 1} aligned to df.index
        NOTE: last `forward_candles` rows will be NaN (no future data)
    """
    c = df["close"]
    fwd_ret = c.shift(-forward_candles) / c - 1

    if use_atr and "atr_14" in df.columns:
        thresh = df["atr_14"] / c
    else:
        thresh = threshold_pct

    labels = pd.Series(0, index=df.index, dtype=int)
    labels[fwd_ret > thresh] = 1
    labels[fwd_ret < -thresh] = -1
    labels[fwd_ret.isna()] = np.nan  # last N rows have no label

    return labels


def make_sample_weights(df: pd.DataFrame, decay: float = 0.9995) -> np.ndarray:
    """Exponential time decay: recent samples weighted higher."""
    n = len(df)
    weights = decay ** np.arange(n - 1, -1, -1)
    return weights / weights.sum() * n  # normalize to mean=1
