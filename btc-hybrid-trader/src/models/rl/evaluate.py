"""RL model evaluation: Sharpe, drawdown, position analysis."""
import logging

import numpy as np
import pandas as pd
from stable_baselines3 import PPO

from .env import BTCTradingEnv

logger = logging.getLogger(__name__)


def run_episode(model: PPO, env: BTCTradingEnv) -> dict:
    """Run single episode deterministically. Returns metrics dict."""
    env.reset()
    # Override to evaluate from beginning of full dataset
    env.start_idx = 0
    env.step_idx = 0
    env.end_idx = len(env.prices) - 1
    obs = env._obs()  # refresh observation for index 0

    capitals = [env.initial_capital]
    positions = []
    done = False

    while not done:
        action, _ = model.predict(obs, deterministic=True)
        obs, reward, terminated, truncated, _ = env.step(action)
        capitals.append(env.capital)
        positions.append(env.position)
        done = terminated or truncated

    equity = pd.Series(capitals)
    returns = equity.pct_change().dropna()

    sharpe = returns.mean() / (returns.std() + 1e-9) * np.sqrt(252 * 288)
    rolling_max = equity.cummax()
    drawdown = (rolling_max - equity) / (rolling_max + 1e-9)
    max_dd = drawdown.max()
    final_return = (equity.iloc[-1] / equity.iloc[0]) - 1

    metrics = {
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "final_return": float(final_return),
        "n_trades": len(env.trade_history),
        "win_rate": env._rolling_win_rate(n=len(env.trade_history)) if env.trade_history else 0.0,
    }
    logger.info("RL eval: %s", {k: round(v, 4) for k, v in metrics.items()
                                if isinstance(v, float)})
    return metrics
