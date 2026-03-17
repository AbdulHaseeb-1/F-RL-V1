"""Binance kline downloader for BTC/USDT perpetual futures."""
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from .storage import save_klines

logger = logging.getLogger(__name__)

BASE_URL = "https://fapi.binance.com"
SYMBOL = "BTCUSDT"
TIMEFRAMES = ["5m", "1h", "4h", "1d"]
START_DATE = "2020-01-01"
LIMIT = 1500


def _ts_ms(dt) -> int:
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt).replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _fetch_klines(interval: str, start_ms: int, end_ms: int) -> list:
    url = f"{BASE_URL}/fapi/v1/klines"
    params = {"symbol": SYMBOL, "interval": interval,
               "startTime": start_ms, "endTime": end_ms, "limit": LIMIT}
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _parse_klines(raw: list) -> pd.DataFrame:
    cols = ["open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "num_trades",
            "taker_buy_volume", "taker_buy_quote_volume", "ignore"]
    df = pd.DataFrame(raw, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    numeric = ["open", "high", "low", "close", "volume",
               "quote_volume", "taker_buy_volume", "taker_buy_quote_volume"]
    df[numeric] = df[numeric].astype(float)
    df["num_trades"] = df["num_trades"].astype(int)
    df = df.drop(columns=["ignore"])
    return df.set_index("open_time").sort_index()


def _fetch_funding_rates(start_ms: int, end_ms: int) -> pd.DataFrame:
    url = f"{BASE_URL}/fapi/v1/fundingRate"
    rows = []
    cur = start_ms
    while cur < end_ms:
        params = {"symbol": SYMBOL, "startTime": cur, "endTime": end_ms, "limit": 1000}
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        rows.extend(data)
        cur = data[-1]["fundingTime"] + 1
        if len(data) < 1000:
            break
        time.sleep(0.1)
    if not rows:
        return pd.DataFrame(columns=["funding_rate"])
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df["fundingTime"], unit="ms", utc=True)
    df.index.name = "funding_time"
    df["funding_rate"] = df["fundingRate"].astype(float)
    return df[["funding_rate"]].sort_index()


def download_klines(interval: str, start: str = START_DATE,
                    end: Optional[str] = None, data_dir: str = "data") -> pd.DataFrame:
    start_ms = _ts_ms(start)
    end_ms = _ts_ms(end) if end else int(datetime.now(timezone.utc).timestamp() * 1000)
    all_rows = []
    cur = start_ms
    while cur < end_ms:
        raw = _fetch_klines(interval, cur, end_ms)
        if not raw:
            break
        all_rows.extend(raw)
        cur = raw[-1][6] + 1  # close_time + 1ms
        logger.info("Fetched %d candles up to %s", len(all_rows),
                    pd.to_datetime(cur, unit="ms", utc=True))
        if len(raw) < LIMIT:
            break
        time.sleep(0.05)
    df = _parse_klines(all_rows)
    save_klines(df, interval, data_dir)
    logger.info("Saved %d %s candles", len(df), interval)
    return df


def download_funding_rates(start: str = START_DATE, end: Optional[str] = None,
                           data_dir: str = "data") -> pd.DataFrame:
    start_ms = _ts_ms(start)
    end_ms = _ts_ms(end) if end else int(datetime.now(timezone.utc).timestamp() * 1000)
    df = _fetch_funding_rates(start_ms, end_ms)
    path = Path(data_dir) / "funding_rates.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path)
    logger.info("Saved %d funding rate records", len(df))
    return df


def download_all(data_dir: str = "data", start: str = START_DATE) -> dict:
    results = {}
    for tf in TIMEFRAMES:
        logger.info("Downloading %s klines...", tf)
        try:
            results[tf] = download_klines(tf, start=start, data_dir=data_dir)
        except Exception as e:
            logger.error("Failed to download %s: %s", tf, e)
    try:
        results["funding"] = download_funding_rates(start=start, data_dir=data_dir)
    except Exception as e:
        logger.error("Failed to download funding rates: %s", e)
    return results
