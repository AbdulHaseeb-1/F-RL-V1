"""Parquet read/write utilities."""
from pathlib import Path
import pandas as pd


def _path(interval: str, data_dir: str) -> Path:
    return Path(data_dir) / f"klines_{interval}.parquet"


def save_klines(df: pd.DataFrame, interval: str, data_dir: str = "data") -> Path:
    p = _path(interval, data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, engine="pyarrow", compression="snappy")
    return p


def load_klines(interval: str, data_dir: str = "data") -> pd.DataFrame:
    p = _path(interval, data_dir)
    if not p.exists():
        raise FileNotFoundError(f"No data file for {interval}: {p}")
    df = pd.read_parquet(p, engine="pyarrow")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()


def load_funding_rates(data_dir: str = "data") -> pd.DataFrame:
    p = Path(data_dir) / "funding_rates.parquet"
    if not p.exists():
        raise FileNotFoundError(f"No funding rate file: {p}")
    df = pd.read_parquet(p, engine="pyarrow")
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    return df.sort_index()
