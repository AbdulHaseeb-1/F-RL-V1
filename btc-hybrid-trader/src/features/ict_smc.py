"""ICT/SMC features: FVG, Order Blocks, BOS/CHoCH, liquidity sweeps."""
import numpy as np
import pandas as pd


def _swing_highs_lows(df: pd.DataFrame, lookback: int = 20):
    h, l = df["high"], df["low"]
    swing_high = h == h.rolling(lookback * 2 + 1, center=True).max()
    swing_low = l == l.rolling(lookback * 2 + 1, center=True).min()
    return swing_high, swing_low


def add_fvg(df: pd.DataFrame) -> pd.DataFrame:
    """Fair Value Gap: gap between candle[i-2] high and candle[i] low (bullish),
    or candle[i-2] low and candle[i] high (bearish)."""
    h, l = df["high"], df["low"]

    # Bullish FVG: l[i] > h[i-2]
    bull_fvg = l > h.shift(2)
    # Bearish FVG: h[i] < l[i-2]
    bear_fvg = h < l.shift(2)

    df["fvg_bull"] = bull_fvg.astype(int)
    df["fvg_bear"] = bear_fvg.astype(int)

    # FVG size as ATR multiple
    atr = (h - l).rolling(14).mean()
    df["fvg_bull_size"] = np.where(bull_fvg, (l - h.shift(2)) / (atr + 1e-9), 0.0)
    df["fvg_bear_size"] = np.where(bear_fvg, (l.shift(2) - h) / (atr + 1e-9), 0.0)

    return df


def add_order_blocks(df: pd.DataFrame, lookback: int = 50) -> pd.DataFrame:
    """Order block: last bullish/bearish candle before a significant move."""
    c, o, h, l = df["close"], df["open"], df["high"], df["low"]
    body = (c - o).abs()
    move = c.diff(3).abs()

    # Bullish OB: bearish candle (close < open) before upward move
    bull_ob = (c.shift(1) < o.shift(1)) & (move > body.rolling(lookback).mean() * 1.5)
    # Bearish OB: bullish candle before downward move
    bear_ob = (c.shift(1) > o.shift(1)) & (move < -body.rolling(lookback).mean() * 1.5)

    df["ob_bull"] = bull_ob.astype(int)
    df["ob_bear"] = bear_ob.astype(int)

    # Distance to nearest OB as ATR multiple
    atr = (h - l).rolling(14).mean()
    ob_bull_price = np.where(bull_ob, (o.shift(1) + c.shift(1)) / 2, np.nan)
    ob_bear_price = np.where(bear_ob, (o.shift(1) + c.shift(1)) / 2, np.nan)

    ob_bull_s = pd.Series(ob_bull_price, index=df.index).ffill()
    ob_bear_s = pd.Series(ob_bear_price, index=df.index).ffill()

    df["dist_ob_bull"] = (c - ob_bull_s) / (atr + 1e-9)
    df["dist_ob_bear"] = (ob_bear_s - c) / (atr + 1e-9)

    return df


def add_bos_choch(df: pd.DataFrame, swing_lookback: int = 20) -> pd.DataFrame:
    """Break of Structure and Change of Character."""
    swing_high, swing_low = _swing_highs_lows(df, swing_lookback)
    h, l, c = df["high"], df["low"], df["close"]

    # Last swing high/low
    last_sh = h.where(swing_high).ffill()
    last_sl = l.where(swing_low).ffill()

    # BOS: close breaks above last swing high (bullish) or below last swing low (bearish)
    df["bos_bull"] = (c > last_sh.shift(1)).astype(int)
    df["bos_bear"] = (c < last_sl.shift(1)).astype(int)

    # CHoCH: bos in opposite direction of recent trend
    trend = (last_sh > last_sh.shift(5)).astype(int) - (last_sl < last_sl.shift(5)).astype(int)
    df["choch_bull"] = ((df["bos_bull"] == 1) & (trend == -1)).astype(int)
    df["choch_bear"] = ((df["bos_bear"] == 1) & (trend == 1)).astype(int)

    return df


def add_liquidity_sweeps(df: pd.DataFrame, swing_lookback: int = 20) -> pd.DataFrame:
    """Liquidity sweep: wick pierces swing high/low then closes back inside."""
    swing_high, swing_low = _swing_highs_lows(df, swing_lookback)
    h, l, c, o = df["high"], df["low"], df["close"], df["open"]

    last_sh = h.where(swing_high).ffill()
    last_sl = l.where(swing_low).ffill()

    # Sweep of highs: wick above last swing high but close below
    df["sweep_highs"] = ((h > last_sh.shift(1)) & (c < last_sh.shift(1))).astype(int)
    # Sweep of lows: wick below last swing low but close above
    df["sweep_lows"] = ((l < last_sl.shift(1)) & (c > last_sl.shift(1))).astype(int)

    return df


def add_ict_smc(df: pd.DataFrame) -> pd.DataFrame:
    df = add_fvg(df)
    df = add_order_blocks(df)
    df = add_bos_choch(df)
    df = add_liquidity_sweeps(df)
    return df
