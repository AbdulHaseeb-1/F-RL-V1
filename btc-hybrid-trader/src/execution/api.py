"""FastAPI webhook endpoint for signal reception and order execution."""
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .binance_client import BinanceExecutor

logger = logging.getLogger(__name__)

app = FastAPI(title="BTC Hybrid Trader", version="1.0")

# Global state
executor: Optional[BinanceExecutor] = None
signal_log = []


class SignalPayload(BaseModel):
    xgb_signal: int          # {-1, 0, 1}
    xgb_confidence: float    # [0, 1]
    position_size: float     # from RL model [0, 1]
    price: float
    paper_mode: bool = True


class OrderResponse(BaseModel):
    status: str
    order: dict
    timestamp: str


@app.on_event("startup")
async def startup():
    global executor
    executor = BinanceExecutor(paper_mode=True)
    logger.info("BTC Hybrid Trader API started (paper mode)")


@app.post("/signal", response_model=OrderResponse)
async def receive_signal(payload: SignalPayload):
    global executor
    ts = datetime.now(timezone.utc).isoformat()
    signal_log.append({"ts": ts, **payload.dict()})

    # Log signal
    logger.info("Signal received: %s", payload.dict())
    _append_log(payload.dict(), ts)

    if payload.xgb_signal == 0 or payload.position_size < 0.05:
        return OrderResponse(status="skip", order={}, timestamp=ts)

    side = "BUY" if payload.xgb_signal == 1 else "SELL"

    # Calculate quantity (simplified: position_size * capital / price)
    # In production, fetch actual capital from Binance
    capital = 10_000.0
    quantity = round(capital * payload.position_size / payload.price, 3)
    quantity = max(quantity, 0.001)  # Binance min

    try:
        order = executor.place_order(side=side, quantity=quantity)
        return OrderResponse(status="filled", order=order, timestamp=ts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "signals_received": len(signal_log)}


@app.get("/logs")
async def get_logs(n: int = 50):
    return signal_log[-n:]


def _append_log(payload: dict, ts: str):
    log_path = Path("logs/signals.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps({"ts": ts, **payload}) + "\n")
