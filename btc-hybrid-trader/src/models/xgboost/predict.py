"""XGBoost inference."""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd


def load_latest_model(model_dir: str = "models/xgboost"):
    models = sorted(Path(model_dir).glob("fold_*.pkl"))
    if not models:
        raise FileNotFoundError(f"No models found in {model_dir}")
    with open(models[-1], "rb") as f:
        return pickle.load(f)


def predict(model, X: pd.DataFrame) -> pd.DataFrame:
    """Return signal and confidence for each row in X."""
    proba = model.predict_proba(X)
    signal = np.argmax(proba, axis=1) - 1
    confidence = proba.max(axis=1)
    return pd.DataFrame({
        "signal": signal,
        "confidence": confidence,
        "prob_short": proba[:, 0],
        "prob_skip": proba[:, 1],
        "prob_long": proba[:, 2],
    }, index=X.index)
