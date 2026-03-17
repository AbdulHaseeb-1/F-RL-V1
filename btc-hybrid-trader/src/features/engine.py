"""Feature engine: combines all feature groups into a single DataFrame."""
import logging
import pandas as pd
import yaml
from pathlib import Path

from .price_action import add_price_action
from .ict_smc import add_ict_smc
from .htf_alignment import add_htf_alignment
from .order_flow import add_order_flow
from .regime import add_regime

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = Path(__file__).parents[2] / "configs" / "features.yaml"


def load_config(path=DEFAULT_CONFIG) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_features(df_5m: pd.DataFrame, df_4h: pd.DataFrame = None,
                   df_1d: pd.DataFrame = None,
                   config_path=DEFAULT_CONFIG) -> pd.DataFrame:
    """
    Build full feature set from OHLCV data.

    Args:
        df_5m: 5-minute klines DataFrame (must have open/high/low/close/volume/taker_buy_volume)
        df_4h: 4-hour klines (optional, for HTF alignment)
        df_1d: 1-day klines (optional, for HTF alignment)
        config_path: path to features.yaml

    Returns:
        DataFrame with all features, NaNs filled, aligned to 5m timestamps.
    """
    cfg = load_config(config_path)
    df = df_5m.copy()

    pa = cfg.get("price_action", {})
    df = add_price_action(
        df,
        return_windows=pa.get("return_windows", [1, 5, 15, 60]),
        atr_period=pa.get("atr_period", 14),
        vol_window=pa.get("volatility_window", 20),
    )
    logger.debug("Price action features added")

    df = add_ict_smc(df)
    logger.debug("ICT/SMC features added")

    of = cfg.get("order_flow", {})
    df = add_order_flow(df, cvd_window=of.get("cvd_window", 20),
                        oi_window=of.get("oi_window", 10))
    logger.debug("Order flow features added")

    rg = cfg.get("regime", {})
    df = add_regime(
        df,
        vol_window=rg.get("vol_percentile_window", 60),
        adx_period=rg.get("adx_period", 14),
        vol_zscore_window=rg.get("volume_zscore_window", 20),
    )
    logger.debug("Regime features added")

    if df_4h is not None and df_1d is not None:
        ht = cfg.get("htf_alignment", {})
        df = add_htf_alignment(df, df_4h, df_1d,
                               ema_fast=ht.get("ema_fast", 20),
                               ema_slow=ht.get("ema_slow", 50))
        logger.debug("HTF alignment features added")
    else:
        logger.warning("df_4h or df_1d not provided — skipping HTF alignment features")

    # Drop rows where core features are all NaN (warm-up period)
    df = df.dropna(subset=["atr_14", "vol_percentile"])

    # Forward-fill any remaining NaNs, then fill with 0
    df = df.ffill().fillna(0)

    logger.info("Feature engine complete: %d rows, %d features", len(df), len(df.columns))
    return df
