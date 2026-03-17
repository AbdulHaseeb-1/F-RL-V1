"""Walk-forward XGBoost training pipeline."""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import pickle

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
import yaml

from .labels import make_labels, make_sample_weights

logger = logging.getLogger(__name__)

OHLCV_COLS = ["open", "high", "low", "close", "volume", "quote_volume",
              "num_trades", "taker_buy_volume", "taker_buy_quote_volume", "close_time"]


def get_feature_cols(df: pd.DataFrame) -> List[str]:
    """Return all feature columns (exclude raw OHLCV and label)."""
    exclude = set(OHLCV_COLS + ["label", "signal"])
    return [c for c in df.columns if c not in exclude]


@dataclass
class WalkForwardSplit:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    oos_start: pd.Timestamp
    oos_end: pd.Timestamp
    fold: int


def generate_splits(df: pd.DataFrame, train_months: int = 12,
                    oos_months: int = 1, min_train_months: int = 6) -> List[WalkForwardSplit]:
    """Generate expanding window walk-forward splits."""
    splits = []
    start = df.index[0]
    end = df.index[-1]

    oos_start = start + pd.DateOffset(months=min_train_months)
    fold = 0
    while oos_start < end:
        oos_end = oos_start + pd.DateOffset(months=oos_months)
        if oos_end > end:
            break
        splits.append(WalkForwardSplit(
            train_start=start,
            train_end=oos_start,
            oos_start=oos_start,
            oos_end=oos_end,
            fold=fold,
        ))
        oos_start = oos_end
        fold += 1

    logger.info("Generated %d walk-forward splits", len(splits))
    return splits


def train_fold(df: pd.DataFrame, split: WalkForwardSplit,
               feature_cols: List[str], cfg: dict) -> XGBClassifier:
    # Exclusive end: avoid overlap with OOS start row
    train = df.loc[split.train_start:split.train_end].iloc[:-1]
    labels = make_labels(train, forward_candles=cfg["label"]["forward_candles"],
                         threshold_pct=cfg["label"]["threshold_pct"],
                         use_atr=cfg["label"].get("use_atr_threshold", False))
    valid_mask = labels.notna()
    X = train.loc[valid_mask, feature_cols]
    y = labels[valid_mask] + 1  # shift to {0, 1, 2} for XGB
    weights = make_sample_weights(X)

    mc = cfg["model"]
    model = XGBClassifier(
        n_estimators=mc["n_estimators"],
        max_depth=mc["max_depth"],
        learning_rate=mc["learning_rate"],
        subsample=mc["subsample"],
        colsample_bytree=mc["colsample_bytree"],
        min_child_weight=mc["min_child_weight"],
        gamma=mc["gamma"],
        reg_alpha=mc["reg_alpha"],
        reg_lambda=mc["reg_lambda"],
        eval_metric=mc["eval_metric"],
        random_state=mc["random_state"],
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X, y, sample_weight=weights)
    return model


def run_walk_forward(df: pd.DataFrame, config_path: str = "configs/xgboost.yaml",
                     model_dir: str = "models/xgboost") -> pd.DataFrame:
    """Run full walk-forward training. Returns OOS predictions DataFrame."""
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    wf = cfg["walk_forward"]
    feature_cols = get_feature_cols(df)
    splits = generate_splits(df, train_months=wf["train_months"],
                             oos_months=wf["oos_months"],
                             min_train_months=wf["min_train_months"])

    Path(model_dir).mkdir(parents=True, exist_ok=True)
    all_preds = []

    for split in splits:
        logger.info("Fold %d: train=%s→%s, OOS=%s→%s",
                    split.fold, split.train_start.date(), split.train_end.date(),
                    split.oos_start.date(), split.oos_end.date())
        model = train_fold(df, split, feature_cols, cfg)

        # Save model
        model_path = Path(model_dir) / f"fold_{split.fold:03d}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # OOS predictions
        oos = df.loc[split.oos_start:split.oos_end]
        if len(oos) == 0:
            continue
        X_oos = oos[feature_cols]
        proba = model.predict_proba(X_oos)  # shape: (n, 3) for {short, skip, long}
        preds = pd.DataFrame({
            "prob_short": proba[:, 0],
            "prob_skip": proba[:, 1],
            "prob_long": proba[:, 2],
            "signal": np.argmax(proba, axis=1) - 1,  # back to {-1, 0, 1}
            "confidence": proba.max(axis=1),
            "fold": split.fold,
        }, index=oos.index)
        all_preds.append(preds)

    if not all_preds:
        raise ValueError("No OOS predictions generated")

    result = pd.concat(all_preds).sort_index()
    result.to_parquet(Path(model_dir) / "oos_predictions.parquet")
    logger.info("Walk-forward complete: %d OOS predictions", len(result))
    return result
