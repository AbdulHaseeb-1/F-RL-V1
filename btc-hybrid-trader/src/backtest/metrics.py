"""Backtest metrics: Sharpe, Sortino, drawdown, profit factor."""
import numpy as np
import pandas as pd


def sharpe(returns: pd.Series, periods_per_year: int = 252 * 288) -> float:
    """Annualized Sharpe ratio (5m candle base)."""
    if returns.std() == 0:
        return 0.0
    return float(returns.mean() / returns.std() * np.sqrt(periods_per_year))


def sortino(returns: pd.Series, periods_per_year: int = 252 * 288) -> float:
    downside = returns[returns < 0]
    if len(downside) == 0 or downside.std() == 0:
        return 0.0
    return float(returns.mean() / downside.std() * np.sqrt(periods_per_year))


def max_drawdown(equity: pd.Series) -> float:
    rolling_max = equity.cummax()
    dd = (rolling_max - equity) / (rolling_max + 1e-9)
    return float(dd.max())


def profit_factor(returns: pd.Series) -> float:
    gross_profit = returns[returns > 0].sum()
    gross_loss = returns[returns < 0].abs().sum()
    return float(gross_profit / (gross_loss + 1e-9))


def compute_all(trade_returns: pd.Series, equity: pd.Series) -> dict:
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns <= 0]
    return {
        "sharpe": sharpe(trade_returns),
        "sortino": sortino(trade_returns),
        "max_drawdown": max_drawdown(equity),
        "profit_factor": profit_factor(trade_returns),
        "win_rate": len(wins) / (len(trade_returns) + 1e-9),
        "avg_win": float(wins.mean()) if len(wins) else 0.0,
        "avg_loss": float(losses.mean()) if len(losses) else 0.0,
        "n_trades": len(trade_returns),
        "total_return": float((equity.iloc[-1] / equity.iloc[0]) - 1),
    }
