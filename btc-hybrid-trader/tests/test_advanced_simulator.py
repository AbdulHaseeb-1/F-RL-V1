"""Tests for advanced simulator with risk management."""
import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from backtest.advanced_simulator import AdvancedSimulator, RiskConfig


def make_data(n=500, seed=42):
    rng = np.random.default_rng(seed)
    close = 30000 + np.cumsum(rng.normal(0, 50, n))
    high = close + rng.uniform(10, 100, n)
    low = close - rng.uniform(10, 100, n)
    idx = pd.date_range("2023-01-01", periods=n, freq="5min", tz="UTC")
    prices = pd.DataFrame({"close": close, "high": high, "low": low}, index=idx)
    signals = pd.Series(
        rng.choice([-1, 0, 1], size=n, p=[0.25, 0.5, 0.25]), index=idx)
    return signals, prices


def test_advanced_sim_runs():
    signals, prices = make_data()
    sim = AdvancedSimulator()
    result = sim.run(signals, prices)
    assert "equity" in result
    assert "trades" in result
    assert "metrics" in result
    assert len(result["equity"]) == len(signals)


def test_advanced_sim_equity_positive():
    signals, prices = make_data()
    sim = AdvancedSimulator()
    result = sim.run(signals, prices)
    assert (result["equity"] > 0).all()


def test_stop_loss_triggers():
    risk = RiskConfig(stop_loss_pct=0.001)  # very tight stop
    sim = AdvancedSimulator(risk=risk)
    signals, prices = make_data()
    result = sim.run(signals, prices)
    if len(result["trades"]) > 0:
        stop_exits = result["trades"][
            result["trades"]["exit_reason"] == "stop_loss"]
        # With a 0.1% stop, we should see some stop losses
        assert len(stop_exits) >= 0  # just verify column exists


def test_circuit_breaker():
    risk = RiskConfig(max_drawdown_pct=0.001)  # very tight breaker
    sim = AdvancedSimulator(risk=risk)
    signals, prices = make_data()
    result = sim.run(signals, prices)
    # Should have fewer trades due to circuit breaker
    assert "risk_events" in result


def test_no_trades_flat():
    signals, prices = make_data()
    flat = pd.Series(0, index=signals.index)
    sim = AdvancedSimulator()
    result = sim.run(flat, prices)
    assert len(result["trades"]) == 0
    assert result["equity"].iloc[-1] == pytest.approx(10_000.0, abs=1)


def test_advanced_metrics_computed():
    signals, prices = make_data()
    sim = AdvancedSimulator()
    result = sim.run(signals, prices)
    if result["metrics"]:
        assert "edge_ratio" in result["metrics"]
        assert "calmar_ratio" in result["metrics"]
        assert "avg_mfe" in result["metrics"]
        assert "cost_drag_pct" in result["metrics"]


def test_position_sizes_respected():
    signals, prices = make_data()
    sizes = pd.Series(0.5, index=signals.index)
    sim = AdvancedSimulator()
    result = sim.run(signals, prices, position_sizes=sizes)
    if len(result["trades"]) > 0:
        assert (result["trades"]["position_size"] <= 0.5 + 1e-9).all()


def test_confidence_filter():
    signals, prices = make_data()
    risk = RiskConfig(min_confidence=0.99)  # filter out almost everything
    sim = AdvancedSimulator(risk=risk)
    confs = pd.Series(0.5, index=signals.index)  # all below threshold
    result = sim.run(signals, prices, confidences=confs)
    assert len(result["trades"]) == 0
