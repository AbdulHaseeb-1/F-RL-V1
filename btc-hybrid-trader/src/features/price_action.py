"""Price action features: returns, ATR, volatility, OHLCV ratios."""
import numpy as np
import pandas as pd


def add_price_action(df: pd.DataFrame, return_windows=(1, 5, 15, 60),
                     atr_period=14, vol_window=20) -> pd.DataFrame:
    c = df["close"]
    h, l, o = df["high"], df["low"], df["open"]

    # Returns
    for w in return_windows:
        df[f"ret_{w}"] = c.pct_change(w)

    # ATR
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.ewm(span=atr_period, adjust=False).mean()

    # Rolling volatility (std of log returns)
    log_ret = np.log(c / c.shift(1))
    df["volatility_20"] = log_ret.rolling(vol_window).std()

    # OHLCV ratios
    df["hl_ratio"] = (h - l) / c
    df["co_ratio"] = (c - o) / (h - l + 1e-9)  # candle body direction
    df["upper_wick"] = (h - np.maximum(o, c)) / (h - l + 1e-9)
    df["lower_wick"] = (np.minimum(o, c) - l) / (h - l + 1e-9)
    df["volume_ma20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / (df["volume_ma20"] + 1e-9)

    return df
