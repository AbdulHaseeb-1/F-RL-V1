"""Higher timeframe alignment: 4H/1D trend + zone proximity."""
import numpy as np
import pandas as pd


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def add_htf_alignment(df_5m: pd.DataFrame, df_4h: pd.DataFrame,
                      df_1d: pd.DataFrame, ema_fast=20, ema_slow=50) -> pd.DataFrame:
    """Merge 4H and 1D features into 5m DataFrame via forward-fill."""

    def compute_htf_features(htf: pd.DataFrame, prefix: str) -> pd.DataFrame:
        c = htf["close"]
        ema_f = _ema(c, ema_fast)
        ema_s = _ema(c, ema_slow)
        trend = np.sign(ema_f - ema_s)

        # HTF FVG zones
        h, l = htf["high"], htf["low"]
        bull_fvg = l > h.shift(2)
        bear_fvg = h < l.shift(2)
        bull_fvg_mid = np.where(bull_fvg, (l + h.shift(2)) / 2, np.nan)
        bear_fvg_mid = np.where(bear_fvg, (h + l.shift(2)) / 2, np.nan)
        bull_zone = pd.Series(bull_fvg_mid, index=htf.index).ffill()
        bear_zone = pd.Series(bear_fvg_mid, index=htf.index).ffill()

        atr = (h - l).rolling(14).mean()
        dist_bull = (c - bull_zone) / (atr + 1e-9)
        dist_bear = (bear_zone - c) / (atr + 1e-9)

        out = pd.DataFrame({
            f"{prefix}_trend": trend,
            f"{prefix}_ema_fast": ema_f,
            f"{prefix}_ema_slow": ema_s,
            f"{prefix}_dist_bull_fvg": dist_bull,
            f"{prefix}_dist_bear_fvg": dist_bear,
        }, index=htf.index)
        return out

    feat_4h = compute_htf_features(df_4h, "htf4h")
    feat_1d = compute_htf_features(df_1d, "htf1d")

    # Reindex to 5m with shift(1) to prevent lookahead:
    # HTF candle at time T contains data up to T, so it should only
    # be visible to 5m candles AFTER T, not during the HTF period.
    idx = df_5m.index
    for feat in [feat_4h, feat_1d]:
        # Shift HTF features forward by 1 period to avoid lookahead
        feat_shifted = feat.shift(1)
        feat_reindexed = feat_shifted.reindex(idx.union(feat_shifted.index)).ffill().reindex(idx)
        for col in feat_reindexed.columns:
            df_5m[col] = feat_reindexed[col].values

    return df_5m
