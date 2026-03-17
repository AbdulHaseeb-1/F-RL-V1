"""Tests for RL environment."""
import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from models.rl.env import BTCTradingEnv


def make_env(n=1000) -> BTCTradingEnv:
    rng = np.random.default_rng(42)
    prices = 30000 + np.cumsum(rng.normal(0, 50, n))
    signals = np.column_stack([
        rng.choice([-1, 0, 1], size=n),
        rng.uniform(0.5, 1.0, size=n),
    ]).astype(np.float32)
    vol_regimes = rng.choice([0, 1, 2], size=n).astype(np.float32)
    return BTCTradingEnv(signals=signals, prices=prices, vol_regimes=vol_regimes,
                         episode_steps=200)


def test_env_spaces():
    env = make_env()
    assert env.observation_space.shape == (8,)
    assert env.action_space.shape == (1,)


def test_env_reset():
    env = make_env()
    obs, info = env.reset(seed=0)
    assert obs.shape == (8,)
    assert env.observation_space.contains(obs)


def test_env_step():
    env = make_env()
    obs, _ = env.reset(seed=0)
    action = env.action_space.sample()
    obs2, reward, terminated, truncated, info = env.step(action)
    assert obs2.shape == (8,)
    assert isinstance(reward, float)
    assert isinstance(bool(terminated), bool)


def test_env_full_episode():
    env = make_env()
    obs, _ = env.reset(seed=0)
    done = False
    steps = 0
    while not done:
        action = env.action_space.sample()
        obs, reward, terminated, truncated, _ = env.step(action)
        done = terminated or truncated
        steps += 1
    assert steps > 0


def test_env_obs_in_bounds():
    env = make_env()
    obs, _ = env.reset(seed=0)
    for _ in range(50):
        action = np.array([0.5])
        obs, _, terminated, truncated, _ = env.step(action)
        assert env.observation_space.contains(obs), f"Obs out of bounds: {obs}"
        if terminated or truncated:
            obs, _ = env.reset()


def test_env_capital_positive():
    env = make_env()
    env.reset(seed=0)
    for _ in range(100):
        action = np.array([1.0])  # max position
        _, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break
    assert env.capital > 0
