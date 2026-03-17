"""Trade simulator with fees, slippage, and funding rates."""
import numpy as np
import pandas as pd

from .metrics import compute_all


FEE_TAKER = 0.0006
SLIPPAGE = 0.0002
FUNDING_INTERVAL = 96  # 8h in 5m candles
FUNDING_RATE = 0.0001


class TradeSimulator:
    def __init__(self, initial_capital: float = 10_000.0,
                 fee_taker: float = FEE_TAKER,
                 slippage: float = SLIPPAGE,
                 funding_interval: int = FUNDING_INTERVAL,
                 funding_rate: float = FUNDING_RATE,
                 max_leverage: float = 3.0):
        self.initial_capital = initial_capital
        self.fee_taker = fee_taker
        self.slippage = slippage
        self.funding_interval = funding_interval
        self.funding_rate = funding_rate
        self.max_leverage = max_leverage

    def run(self, signals: pd.Series, prices: pd.Series,
            position_sizes: pd.Series = None) -> dict:
        """
        Simulate trading given signals and prices.

        Args:
            signals: Series of {-1, 0, 1}
            prices: close prices aligned to signals
            position_sizes: fraction of capital [0, 1], defaults to 1.0 for non-zero signals

        Returns:
            dict with trade_returns, equity, metrics
        """
        if position_sizes is None:
            position_sizes = pd.Series(
                np.where(signals != 0, 1.0, 0.0), index=signals.index)

        capital = self.initial_capital
        equity_curve = []
        trade_returns = []
        trade_log = []

        position = 0      # +1 long, -1 short, 0 flat
        entry_price = 0.0
        entry_capital = 0.0
        size = 0.0
        candle = 0

        for ts, sig, price, pos_size in zip(
                signals.index, signals.values, prices.values, position_sizes.values):

            # Funding rate cost
            if position != 0 and candle % self.funding_interval == 0 and candle > 0:
                capital -= capital * size * self.funding_rate

            new_sig = int(sig)
            new_size = float(np.clip(pos_size, 0.0, 1.0))

            # Exit if signal changes or flattens
            if position != 0 and (new_sig != position or new_sig == 0):
                exit_price = price * (1 - self.slippage * position)  # slip on exit
                pnl_pct = (exit_price - entry_price) / entry_price * position
                fee = self.fee_taker  # flat rate, size already in trade_pnl
                net_pct = pnl_pct - fee
                trade_pnl = entry_capital * size * net_pct
                capital += trade_pnl
                trade_returns.append(net_pct)
                trade_log.append({
                    "ts": ts, "dir": position, "entry": entry_price,
                    "exit": exit_price, "pnl_pct": net_pct, "capital": capital,
                })
                position = 0
                size = 0.0

            # Enter new position
            if new_sig != 0 and position == 0:
                entry_price = price * (1 + self.slippage * new_sig)
                position = new_sig
                size = min(new_size, self.max_leverage)
                entry_capital = capital
                capital -= capital * size * self.fee_taker  # entry fee

            equity_curve.append(capital)
            candle += 1

        equity = pd.Series(equity_curve, index=signals.index)
        trade_ret_s = pd.Series(trade_returns)
        metrics = compute_all(trade_ret_s, equity) if len(trade_returns) > 0 else {}
        return {
            "equity": equity,
            "trade_returns": trade_ret_s,
            "trade_log": pd.DataFrame(trade_log),
            "metrics": metrics,
        }
