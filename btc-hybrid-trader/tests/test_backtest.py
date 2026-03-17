"""Tests for backtest simulator and metrics."""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from backtest.simulator import TradeSimulator
from backtest.metrics import sharpe, sortino, max_drawdown, profit_factor


def make_signals(n=200, seed=42) -> tuple:
    rng = np.random.default_rng(seed)
    prices = pd.Series(
        30000 + np.cumsum(rng.normal(0, 50, n)),
        index=pd.date_range("2023-01-01", periods=n, freq="5min", tz="UTC"),
    )
    signals = pd.Series(
        rng.choice([-1, 0, 1], size=n, p=[0.25, 0.5, 0.25]),
        index=prices.index,
    )
    return signals, prices


def test_simulator_returns_equity():
    sim = TradeSimulator()
    signals, prices = make_signals()
    result = sim.run(signals, prices)
    assert "equity" in result
    assert "trade_returns" in result
    assert len(result["equity"]) == len(signals)


def test_simulator_equity_positive():
    sim = TradeSimulator()
    signals, prices = make_signals()
    result = sim.run(signals, prices)
    assert (result["equity"] > 0).all()


def test_simulator_fees_reduce_pnl():
    """Compare no-fee sim vs with-fee sim."""
    signals, prices = make_signals()
    sim_fee = TradeSimulator(fee_taker=0.0006)
    sim_nofee = TradeSimulator(fee_taker=0.0)
    r_fee = sim_fee.run(signals, prices)
    r_nofee = sim_nofee.run(signals, prices)
    assert r_fee["equity"].iloc[-1] <= r_nofee["equity"].iloc[-1]


def test_metrics_sharpe():
    returns = pd.Series(np.random.normal(0.001, 0.01, 1000))
    s = sharpe(returns, periods_per_year=252)
    assert isinstance(s, float)


def test_metrics_max_drawdown():
    equity = pd.Series([100, 110, 90, 95, 80, 100])
    dd = max_drawdown(equity)
    assert abs(dd - (110 - 80) / 110) < 0.01


def test_metrics_profit_factor():
    returns = pd.Series([0.01, -0.005, 0.02, -0.01, 0.015])
    pf = profit_factor(returns)
    assert pf > 1.0  # net positive


def test_simulator_no_trades_flat():
    signals, prices = make_signals()
    flat_signals = pd.Series(0, index=signals.index)
    sim = TradeSimulator()
    result = sim.run(flat_signals, prices)
    assert len(result["trade_returns"]) == 0
    # Capital should only decrease by funding (none here since never in position)
    assert result["equity"].iloc[-1] == pytest.approx(10_000.0, abs=1)
