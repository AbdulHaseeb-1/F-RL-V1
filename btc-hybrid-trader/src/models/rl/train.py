"""PPO training via Stable-Baselines3."""
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.vec_env import DummyVecEnv

from .env import BTCTradingEnv

logger = logging.getLogger(__name__)


def build_env(oos_preds: pd.DataFrame, df_5m: pd.DataFrame,
              cfg: dict, eval_mode: bool = False) -> BTCTradingEnv:
    """Construct BTCTradingEnv from OOS predictions and price data."""
    aligned = oos_preds.join(df_5m[["close", "vol_regime"]], how="inner")
    aligned = aligned.dropna(subset=["close", "signal", "confidence"])

    signals = aligned[["signal", "confidence"]].values.astype(np.float32)
    prices = aligned["close"].values.astype(np.float64)
    vol_regimes = aligned["vol_regime"].fillna(1).values.astype(np.float32)

    env_cfg = cfg["environment"]
    return BTCTradingEnv(
        signals=signals,
        prices=prices,
        vol_regimes=vol_regimes,
        initial_capital=env_cfg["initial_capital"],
        max_leverage=env_cfg["max_leverage"],
        fee_rate=env_cfg["fee_rate"],
        slippage_rate=env_cfg["slippage_rate"],
        funding_interval=env_cfg["funding_interval_candles"],
        funding_rate=env_cfg["funding_rate"],
        episode_steps=env_cfg["episode_days"] * 288,  # 288 5m candles/day
    )


def train_ppo(oos_preds: pd.DataFrame, df_5m: pd.DataFrame,
              config_path: str = "configs/rl.yaml",
              model_dir: str = "models/rl") -> PPO:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    env = build_env(oos_preds, df_5m, cfg)
    check_env(env, warn=True)
    vec_env = DummyVecEnv([lambda: env])

    ppo_cfg = cfg["ppo"]
    model = PPO(
        policy=ppo_cfg["policy"],
        env=vec_env,
        learning_rate=ppo_cfg["learning_rate"],
        n_steps=ppo_cfg["n_steps"],
        batch_size=ppo_cfg["batch_size"],
        n_epochs=ppo_cfg["n_epochs"],
        gamma=ppo_cfg["gamma"],
        gae_lambda=ppo_cfg["gae_lambda"],
        clip_range=ppo_cfg["clip_range"],
        ent_coef=ppo_cfg["ent_coef"],
        vf_coef=ppo_cfg["vf_coef"],
        max_grad_norm=ppo_cfg["max_grad_norm"],
        verbose=1,
    )

    model.learn(total_timesteps=ppo_cfg["total_timesteps"])

    Path(model_dir).mkdir(parents=True, exist_ok=True)
    save_path = Path(model_dir) / "ppo_btc"
    model.save(str(save_path))
    logger.info("PPO model saved to %s", save_path)
    return model
