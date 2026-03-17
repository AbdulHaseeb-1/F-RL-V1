"""Tests for XGBoost labeling and training pipeline."""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from models.xgboost.labels import make_labels, make_sample_weights
from features.price_action import add_price_action


def make_df(n=500, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 30000 + np.cumsum(rng.normal(0, 100, n))
    volume = rng.uniform(100, 1000, n)
    df = pd.DataFrame({
        "close": close,
        "high": close * 1.002, "low": close * 0.998,
        "open": close * 1.001,
        "volume": volume,
        "taker_buy_volume": volume * 0.5,
    }, index=pd.date_range("2023-01-01", periods=n, freq="5min", tz="UTC"))
    return add_price_action(df)


def test_labels_shape():
    df = make_df()
    labels = make_labels(df, forward_candles=12, threshold_pct=0.003)
    assert len(labels) == len(df)


def test_labels_values():
    df = make_df()
    labels = make_labels(df, forward_candles=12, threshold_pct=0.003)
    valid = labels.dropna()
    assert set(valid.unique()).issubset({-1, 0, 1})


def test_labels_no_lookahead():
    """Last forward_candles rows must be NaN."""
    df = make_df()
    n_forward = 12
    labels = make_labels(df, forward_candles=n_forward)
    assert labels.iloc[-n_forward:].isna().all()


def test_sample_weights_sum():
    df = make_df(n=100)
    w = make_sample_weights(df)
    assert len(w) == 100
    assert abs(w.sum() - 100) < 0.01  # normalized to mean=1


def test_sample_weights_increasing():
    df = make_df(n=100)
    w = make_sample_weights(df)
    assert w[-1] > w[0]  # recent samples have higher weight
