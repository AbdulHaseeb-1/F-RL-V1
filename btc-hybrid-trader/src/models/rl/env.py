"""Custom Gymnasium environment for RL position sizing."""
import numpy as np
import gymnasium as gym
from gymnasium import spaces


class BTCTradingEnv(gym.Env):
    """
    BTC/USDT perpetual futures trading environment.

    State space (8 features):
        xgb_signal         int {-1, 0, 1}
        xgb_confidence     float [0, 1]
        current_position   float [-1, 1]
        unrealized_pnl_pct float
        drawdown_pct       float [0, 1]
        volatility_regime  int {0, 1, 2}
        time_in_position   int (normalized 0-1)
        rolling_win_rate   float [0, 1]

    Action space: continuous [0, 1] = fraction of capital to allocate.
        0.0 = skip or flat.
    """

    metadata = {"render_modes": []}

    def __init__(self, signals: np.ndarray, prices: np.ndarray,
                 vol_regimes: np.ndarray,
                 initial_capital: float = 10_000.0,
                 max_leverage: float = 3.0,
                 fee_rate: float = 0.0006,
                 slippage_rate: float = 0.0002,
                 funding_interval: int = 96,
                 funding_rate: float = 0.0001,
                 episode_steps: int = 8640,  # 30 days of 5m candles
                 max_position_hold: int = 48):
        super().__init__()
        assert len(signals) == len(prices) == len(vol_regimes)

        self.signals = signals      # (N, 2): [xgb_signal, xgb_confidence]
        self.prices = prices        # (N,): close prices
        self.vol_regimes = vol_regimes  # (N,): {0, 1, 2}
        self.initial_capital = initial_capital
        self.max_leverage = max_leverage
        self.fee_rate = fee_rate
        self.slippage_rate = slippage_rate
        self.funding_interval = funding_interval
        self.funding_rate = funding_rate
        self.episode_steps = min(episode_steps, len(prices) - 1)
        self.max_position_hold = max_position_hold

        self.observation_space = spaces.Box(
            low=np.array([-1, 0, -1, -1, 0, 0, 0, 0], dtype=np.float32),
            high=np.array([1, 1, 1, 1, 1, 1, 1, 1], dtype=np.float32),
        )
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)

        self._reset_state()

    def _reset_state(self):
        self.capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.position = 0.0       # fraction of capital, -1 to 1
        self.position_dir = 0     # +1 long, -1 short, 0 flat
        self.entry_price = 0.0
        self.time_in_position = 0
        self.trade_history = []
        self.step_idx = 0

    def _obs(self) -> np.ndarray:
        xgb_signal = self.signals[self.step_idx, 0] / 1.0  # normalize
        xgb_conf = self.signals[self.step_idx, 1]
        unrealized = self._unrealized_pnl_pct()
        drawdown = max(0.0, (self.peak_capital - self.capital) / (self.peak_capital + 1e-9))
        vol_regime = self.vol_regimes[self.step_idx] / 2.0  # normalize to [0,1]
        time_norm = min(self.time_in_position / self.max_position_hold, 1.0)
        win_rate = self._rolling_win_rate()

        return np.array([
            xgb_signal, xgb_conf, self.position, unrealized,
            drawdown, vol_regime, time_norm, win_rate,
        ], dtype=np.float32)

    def _unrealized_pnl_pct(self) -> float:
        if self.position_dir == 0 or self.entry_price == 0:
            return 0.0
        cur = self.prices[self.step_idx]
        ret = (cur - self.entry_price) / self.entry_price * self.position_dir
        return float(np.clip(ret, -1.0, 1.0))

    def _rolling_win_rate(self, n=20) -> float:
        recent = self.trade_history[-n:]
        if not recent:
            return 0.5
        return sum(1 for r in recent if r > 0) / len(recent)

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self._reset_state()
        # Random episode start to diversify training
        max_start = max(0, len(self.prices) - self.episode_steps - 1)
        if max_start > 0:
            self.start_idx = self.np_random.integers(0, max_start)
        else:
            self.start_idx = 0
        self.step_idx = self.start_idx
        self.end_idx = self.start_idx + self.episode_steps
        return self._obs(), {}

    def step(self, action):
        action_size = float(np.clip(action[0], 0.0, 1.0))
        cur_price = self.prices[self.step_idx]
        xgb_signal = int(self.signals[self.step_idx, 0])

        # Determine intended direction
        if action_size < 0.05 or xgb_signal == 0:
            new_dir = 0
            new_size = 0.0
        else:
            new_dir = xgb_signal
            new_size = action_size * np.sign(new_dir)

        reward = 0.0

        # Close existing position if direction changes or flattening
        if self.position_dir != 0 and (new_dir != self.position_dir or new_dir == 0):
            close_size = abs(self.position)
            close_fee = self.fee_rate * close_size
            close_slip = self.slippage_rate * close_size
            pnl = self._unrealized_pnl_pct() * close_size
            self.capital *= (1 + pnl)
            self.capital -= close_fee * self.capital
            self.capital -= close_slip * self.capital
            self.trade_history.append(pnl)
            self.position = 0.0
            self.position_dir = 0
            self.entry_price = 0.0
            self.time_in_position = 0

        # Open new position
        if new_dir != 0 and self.position_dir == 0:
            open_size = abs(new_size)
            open_fee = self.fee_rate * open_size
            self.position = new_size
            self.position_dir = new_dir
            self.entry_price = cur_price * (1 + self.slippage_rate * new_dir)
            self.capital -= open_fee * self.capital

        # Funding rate cost (every funding_interval candles)
        if self.position_dir != 0 and (self.step_idx % self.funding_interval == 0):
            funding_cost = self.funding_rate * abs(self.position)
            self.capital -= funding_cost * self.initial_capital

        if self.position_dir != 0:
            self.time_in_position += 1

        # Advance
        self.step_idx += 1
        self.peak_capital = max(self.peak_capital, self.capital)

        # Compute reward on next step
        unrealized = self._unrealized_pnl_pct()
        drawdown = max(0.0, (self.peak_capital - self.capital) / (self.peak_capital + 1e-9))

        reward = (unrealized / max(drawdown, 0.01)) \
                 - (0.5 * max(drawdown - 0.05, 0))

        terminated = self.step_idx >= self.end_idx
        truncated = self.capital <= self.initial_capital * 0.5  # blown up

        return self._obs(), float(reward), terminated, truncated, {}

    def render(self):
        pass
