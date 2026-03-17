"""Market regime features: volatility percentile, ADX, volume z-score."""
import numpy as np
import pandas as pd


def _adx(df: pd.DataFrame, period=14) -> pd.Series:
    h, l, c = df["high"], df["low"], df["close"]
    prev_c = c.shift(1)
    prev_h = h.shift(1)
    prev_l = l.shift(1)

    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    # dm_plus/minus as pandas Series preserving index
    dm_plus = pd.Series(
        np.where((h - prev_h) > (prev_l - l), np.maximum(h - prev_h, 0), 0),
        index=df.index)
    dm_minus = pd.Series(
        np.where((prev_l - l) > (h - prev_h), np.maximum(prev_l - l, 0), 0),
        index=df.index)

    atr_s = tr.ewm(span=period, adjust=False).mean()
    di_plus = 100 * dm_plus.ewm(span=period, adjust=False).mean() / (atr_s + 1e-9)
    di_minus = 100 * dm_minus.ewm(span=period, adjust=False).mean() / (atr_s + 1e-9)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-9)
    return dx.ewm(span=period, adjust=False).mean()


def add_regime(df: pd.DataFrame, vol_window=60, adx_period=14,
               vol_zscore_window=20) -> pd.DataFrame:
    log_ret = np.log(df["close"] / df["close"].shift(1))
    rolling_vol = log_ret.rolling(vol_window).std()
    df["vol_percentile"] = rolling_vol.rolling(vol_window).rank(pct=True)

    df["vol_regime"] = pd.cut(
        df["vol_percentile"],
        bins=[-0.01, 0.33, 0.66, 1.01],
        labels=[0, 1, 2]
    ).astype(float)

    df["adx"] = _adx(df, adx_period)
    df["trending"] = (df["adx"] > 25).astype(int)

    vol_mean = df["volume"].rolling(vol_zscore_window).mean()
    vol_std = df["volume"].rolling(vol_zscore_window).std()
    df["volume_zscore"] = (df["volume"] - vol_mean) / (vol_std + 1e-9)

    return df
