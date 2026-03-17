"""Order flow features: taker ratio, CVD, OI delta."""
import numpy as np
import pandas as pd


def add_order_flow(df: pd.DataFrame, cvd_window=20, oi_window=10) -> pd.DataFrame:
    vol = df["volume"]
    tbv = df["taker_buy_volume"]

    # Taker buy/sell ratio
    taker_sell = vol - tbv
    df["taker_buy_ratio"] = tbv / (vol + 1e-9)
    df["taker_sell_ratio"] = taker_sell / (vol + 1e-9)

    # Volume delta per candle (buy - sell)
    delta = tbv - taker_sell
    df["vol_delta"] = delta

    # CVD: cumulative volume delta
    df["cvd"] = delta.cumsum()
    df["cvd_change"] = df["cvd"].diff(cvd_window)

    # CVD divergence: price goes up but CVD goes down (or vice versa)
    price_dir = np.sign(df["close"].diff(cvd_window))
    cvd_dir = np.sign(df["cvd_change"])
    df["cvd_divergence"] = (price_dir != cvd_dir).astype(int)

    # OI change (if column exists)
    if "open_interest" in df.columns:
        df["oi_change"] = df["open_interest"].pct_change(oi_window)
        df["oi_delta"] = df["open_interest"].diff()
    else:
        df["oi_change"] = np.nan
        df["oi_delta"] = np.nan

    return df
