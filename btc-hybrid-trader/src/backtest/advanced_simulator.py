"""Production-grade simulator with full risk management, margin accounting,
   circuit breakers, trailing stops, and detailed PnL attribution."""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd

from .metrics import compute_all

logger = logging.getLogger(__name__)


class ExitReason(str, Enum):
    SIGNAL_FLIP = "signal_flip"
    SIGNAL_FLAT = "signal_flat"
    STOP_LOSS = "stop_loss"
    TRAILING_STOP = "trailing_stop"
    TIME_STOP = "time_stop"
    MAX_DRAWDOWN = "max_drawdown_breaker"
    MARGIN_CALL = "margin_call"
    END_OF_DATA = "end_of_data"


@dataclass
class RiskConfig:
    max_position_pct: float = 1.0        # max fraction of capital per trade
    max_leverage: float = 3.0
    stop_loss_pct: float = 0.02          # 2% stop loss
    trailing_stop_pct: float = 0.015     # 1.5% trailing stop (0 = disabled)
    time_stop_candles: int = 96          # max hold time (8h in 5m candles, 0 = disabled)
    max_drawdown_pct: float = 0.15       # 15% circuit breaker
    cooldown_candles: int = 12           # candles to wait after circuit breaker
    max_daily_trades: int = 0            # 0 = unlimited
    min_confidence: float = 0.0          # minimum XGB confidence to trade


@dataclass
class TradeRecord:
    entry_ts: pd.Timestamp
    exit_ts: pd.Timestamp
    direction: int                       # +1 long, -1 short
    entry_price: float
    exit_price: float
    position_size: float
    gross_pnl_pct: float
    fee_cost: float
    slippage_cost: float
    funding_cost: float
    net_pnl_pct: float
    net_pnl_usd: float
    capital_after: float
    hold_candles: int
    exit_reason: ExitReason
    peak_favorable: float = 0.0          # max favorable excursion
    peak_adverse: float = 0.0            # max adverse excursion


class AdvancedSimulator:
    """Production-grade backtesting engine with:
    - Proper margin and leverage accounting
    - Stop-loss, trailing stop, time stop
    - Max drawdown circuit breaker with cooldown
    - Detailed PnL attribution (gross, fees, slippage, funding)
    - Per-trade MFE/MAE tracking
    - Daily trade limits
    """

    def __init__(self, initial_capital: float = 10_000.0,
                 fee_taker: float = 0.0006,
                 fee_maker: float = 0.0004,
                 slippage: float = 0.0002,
                 funding_interval: int = 96,
                 funding_rate: float = 0.0001,
                 risk: RiskConfig = None):
        self.initial_capital = initial_capital
        self.fee_taker = fee_taker
        self.fee_maker = fee_maker
        self.slippage = slippage
        self.funding_interval = funding_interval
        self.funding_rate = funding_rate
        self.risk = risk or RiskConfig()

    def run(self, signals: pd.Series, prices: pd.DataFrame,
            position_sizes: pd.Series = None,
            confidences: pd.Series = None) -> dict:
        """
        Run full simulation.

        Args:
            signals: Series of {-1, 0, 1} indexed by timestamp
            prices: DataFrame with at least 'close', 'high', 'low' columns
            position_sizes: fraction of capital [0, 1] from RL model
            confidences: XGB confidence scores for filtering

        Returns:
            dict with equity, trades, metrics, risk_events
        """
        if isinstance(prices, pd.Series):
            prices = pd.DataFrame({"close": prices, "high": prices, "low": prices})

        if position_sizes is None:
            position_sizes = pd.Series(
                np.where(signals != 0, self.risk.max_position_pct, 0.0),
                index=signals.index)

        if confidences is None:
            confidences = pd.Series(1.0, index=signals.index)

        # State
        capital = self.initial_capital
        peak_capital = self.initial_capital
        position = 0          # +1, -1, 0
        entry_price = 0.0
        entry_ts = None
        size = 0.0
        hold_candles = 0
        peak_favorable = 0.0
        peak_adverse = 0.0
        total_funding = 0.0
        total_entry_fee = 0.0
        cooldown_remaining = 0
        daily_trade_count = {}

        # Output
        equity_curve = []
        drawdown_curve = []
        trades: List[TradeRecord] = []
        risk_events = []
        positions_log = []

        def _close_position(ts, close_price, reason: ExitReason):
            nonlocal capital, position, entry_price, size, hold_candles
            nonlocal peak_favorable, peak_adverse, total_funding, total_entry_fee, entry_ts

            # Exit slippage
            exit_slip = self.slippage * position  # adverse direction
            exit_price = close_price * (1 - exit_slip)
            exit_fee = self.fee_taker * size * capital

            # Gross PnL
            gross_pnl_pct = (exit_price - entry_price) / entry_price * position
            net_pnl_pct = gross_pnl_pct - self.fee_taker - (total_entry_fee / (capital * size + 1e-9))
            net_pnl_usd = capital * size * gross_pnl_pct - exit_fee - total_entry_fee - total_funding

            capital += net_pnl_usd

            trade = TradeRecord(
                entry_ts=entry_ts, exit_ts=ts,
                direction=position,
                entry_price=entry_price, exit_price=exit_price,
                position_size=size,
                gross_pnl_pct=gross_pnl_pct,
                fee_cost=exit_fee + total_entry_fee,
                slippage_cost=abs(exit_slip * close_price) * size,
                funding_cost=total_funding,
                net_pnl_pct=net_pnl_pct,
                net_pnl_usd=net_pnl_usd,
                capital_after=capital,
                hold_candles=hold_candles,
                exit_reason=reason,
                peak_favorable=peak_favorable,
                peak_adverse=peak_adverse,
            )
            trades.append(trade)

            position = 0
            entry_price = 0.0
            size = 0.0
            hold_candles = 0
            peak_favorable = 0.0
            peak_adverse = 0.0
            total_funding = 0.0
            total_entry_fee = 0.0
            entry_ts = None

            return trade

        candle = 0
        for ts in signals.index:
            sig = int(signals.loc[ts])
            price_close = float(prices.loc[ts, "close"])
            price_high = float(prices.loc[ts, "high"])
            price_low = float(prices.loc[ts, "low"])
            pos_size = float(np.clip(position_sizes.loc[ts], 0.0, self.risk.max_position_pct))
            conf = float(confidences.loc[ts])

            # --- Cooldown after circuit breaker ---
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
                sig = 0  # force flat during cooldown

            # --- Funding cost ---
            if position != 0 and candle % self.funding_interval == 0 and candle > 0:
                notional = size * price_close
                fund_cost = notional * self.funding_rate
                capital -= fund_cost
                total_funding += fund_cost

            # --- Risk checks on open position ---
            if position != 0:
                hold_candles += 1
                cur_pnl = (price_close - entry_price) / entry_price * position

                # Track MFE/MAE using high/low
                if position == 1:  # long
                    fav = (price_high - entry_price) / entry_price
                    adv = (entry_price - price_low) / entry_price
                else:  # short
                    fav = (entry_price - price_low) / entry_price
                    adv = (price_high - entry_price) / entry_price
                peak_favorable = max(peak_favorable, fav)
                peak_adverse = max(peak_adverse, adv)

                # Stop-loss
                if self.risk.stop_loss_pct > 0 and cur_pnl <= -self.risk.stop_loss_pct:
                    _close_position(ts, price_close, ExitReason.STOP_LOSS)
                    risk_events.append({"ts": ts, "event": "stop_loss", "pnl": cur_pnl})

                # Trailing stop
                elif (self.risk.trailing_stop_pct > 0
                      and peak_favorable > self.risk.trailing_stop_pct
                      and cur_pnl < peak_favorable - self.risk.trailing_stop_pct):
                    _close_position(ts, price_close, ExitReason.TRAILING_STOP)
                    risk_events.append({"ts": ts, "event": "trailing_stop"})

                # Time stop
                elif (self.risk.time_stop_candles > 0
                      and hold_candles >= self.risk.time_stop_candles):
                    _close_position(ts, price_close, ExitReason.TIME_STOP)
                    risk_events.append({"ts": ts, "event": "time_stop"})

            # --- Max drawdown circuit breaker ---
            dd_pct = (peak_capital - capital) / (peak_capital + 1e-9)
            if dd_pct >= self.risk.max_drawdown_pct:
                if position != 0:
                    _close_position(ts, price_close, ExitReason.MAX_DRAWDOWN)
                    risk_events.append({"ts": ts, "event": "circuit_breaker", "dd": dd_pct})
                    cooldown_remaining = self.risk.cooldown_candles
                sig = 0  # no new trades

            # --- Signal-based exit ---
            if position != 0 and (sig != position or sig == 0):
                reason = ExitReason.SIGNAL_FLAT if sig == 0 else ExitReason.SIGNAL_FLIP
                _close_position(ts, price_close, reason)

            # --- Entry ---
            if sig != 0 and position == 0 and cooldown_remaining == 0:
                # Confidence filter
                if conf < self.risk.min_confidence:
                    sig = 0
                # Daily trade limit
                elif self.risk.max_daily_trades > 0:
                    day = ts.date() if hasattr(ts, 'date') else ts
                    count = daily_trade_count.get(day, 0)
                    if count >= self.risk.max_daily_trades:
                        sig = 0
                    else:
                        daily_trade_count[day] = count + 1

                if sig != 0:
                    entry_slip = self.slippage * sig
                    entry_price = price_close * (1 + entry_slip)
                    position = sig
                    size = min(pos_size, self.risk.max_leverage)
                    entry_ts = ts
                    hold_candles = 0
                    peak_favorable = 0.0
                    peak_adverse = 0.0
                    total_funding = 0.0
                    total_entry_fee = self.fee_taker * size * capital
                    capital -= total_entry_fee

            # --- Track equity ---
            # Mark-to-market: include unrealized PnL
            if position != 0:
                unrealized = (price_close - entry_price) / entry_price * position * size * capital
            else:
                unrealized = 0.0
            mtm_capital = capital + unrealized

            peak_capital = max(peak_capital, mtm_capital)
            dd = (peak_capital - mtm_capital) / (peak_capital + 1e-9)

            equity_curve.append(mtm_capital)
            drawdown_curve.append(dd)
            positions_log.append({
                "ts": ts, "position": position, "size": size,
                "capital": capital, "mtm": mtm_capital, "drawdown": dd,
            })
            candle += 1

        # Close any open position at end
        if position != 0:
            last_ts = signals.index[-1]
            last_price = float(prices.iloc[-1]["close"])
            _close_position(last_ts, last_price, ExitReason.END_OF_DATA)

        # Build results
        equity = pd.Series(equity_curve, index=signals.index, name="equity")
        dd_series = pd.Series(drawdown_curve, index=signals.index, name="drawdown")
        trade_df = pd.DataFrame([t.__dict__ for t in trades]) if trades else pd.DataFrame()
        trade_returns = pd.Series([t.net_pnl_pct for t in trades]) if trades else pd.Series(dtype=float)

        metrics = {}
        if len(trades) > 0:
            metrics = compute_all(trade_returns, equity)
            metrics.update(self._compute_advanced_metrics(trades, equity, dd_series))

        return {
            "equity": equity,
            "drawdown": dd_series,
            "trades": trade_df,
            "trade_returns": trade_returns,
            "metrics": metrics,
            "risk_events": pd.DataFrame(risk_events) if risk_events else pd.DataFrame(),
            "positions": pd.DataFrame(positions_log),
        }

    def _compute_advanced_metrics(self, trades: List[TradeRecord],
                                  equity: pd.Series,
                                  drawdown: pd.Series) -> dict:
        """Compute advanced risk and performance metrics."""
        if not trades:
            return {}

        net_pnls = [t.net_pnl_pct for t in trades]
        wins = [p for p in net_pnls if p > 0]
        losses = [p for p in net_pnls if p <= 0]
        hold_times = [t.hold_candles for t in trades]

        # Consecutive wins/losses
        max_consec_win = max_consec_loss = cur_win = cur_loss = 0
        for p in net_pnls:
            if p > 0:
                cur_win += 1
                cur_loss = 0
            else:
                cur_loss += 1
                cur_win = 0
            max_consec_win = max(max_consec_win, cur_win)
            max_consec_loss = max(max_consec_loss, cur_loss)

        # PnL attribution
        total_fees = sum(t.fee_cost for t in trades)
        total_slippage = sum(t.slippage_cost for t in trades)
        total_funding = sum(t.funding_cost for t in trades)
        total_gross = sum(t.gross_pnl_pct * t.position_size for t in trades)

        # Exit reason distribution
        exit_reasons = {}
        for t in trades:
            r = t.exit_reason.value
            exit_reasons[f"exits_{r}"] = exit_reasons.get(f"exits_{r}", 0) + 1

        # Long vs Short breakdown
        long_trades = [t for t in trades if t.direction == 1]
        short_trades = [t for t in trades if t.direction == -1]

        metrics = {
            # Risk metrics
            "max_drawdown_duration": int(self._max_dd_duration(drawdown)),
            "calmar_ratio": float(
                (equity.iloc[-1] / equity.iloc[0] - 1) / (drawdown.max() + 1e-9)),
            "ulcer_index": float(np.sqrt((drawdown ** 2).mean())),

            # Trade quality
            "avg_hold_candles": float(np.mean(hold_times)),
            "median_hold_candles": float(np.median(hold_times)),
            "max_consec_wins": max_consec_win,
            "max_consec_losses": max_consec_loss,
            "expectancy": float(np.mean(net_pnls)),

            # MFE/MAE
            "avg_mfe": float(np.mean([t.peak_favorable for t in trades])),
            "avg_mae": float(np.mean([t.peak_adverse for t in trades])),
            "edge_ratio": float(
                np.mean([t.peak_favorable for t in trades]) /
                (np.mean([t.peak_adverse for t in trades]) + 1e-9)),

            # Cost attribution
            "total_fees_usd": total_fees,
            "total_slippage_usd": total_slippage,
            "total_funding_usd": total_funding,
            "cost_drag_pct": float(
                (total_fees + total_slippage + total_funding) /
                (self.initial_capital + 1e-9) * 100),

            # Direction breakdown
            "n_long": len(long_trades),
            "n_short": len(short_trades),
            "long_win_rate": float(
                sum(1 for t in long_trades if t.net_pnl_pct > 0) /
                (len(long_trades) + 1e-9)),
            "short_win_rate": float(
                sum(1 for t in short_trades if t.net_pnl_pct > 0) /
                (len(short_trades) + 1e-9)),

            **exit_reasons,
        }
        return metrics

    @staticmethod
    def _max_dd_duration(drawdown: pd.Series) -> int:
        """Maximum number of candles spent in drawdown."""
        in_dd = (drawdown > 0).astype(int)
        if in_dd.sum() == 0:
            return 0
        groups = (in_dd != in_dd.shift()).cumsum()
        dd_groups = groups[in_dd == 1]
        if len(dd_groups) == 0:
            return 0
        return int(dd_groups.value_counts().max())
