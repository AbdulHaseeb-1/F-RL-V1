"""Binance order execution client."""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    logger.warning("python-binance not installed — execution disabled")


class BinanceExecutor:
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
                 paper_mode: bool = True, symbol: str = "BTCUSDT",
                 max_leverage: int = 3):
        self.symbol = symbol
        self.paper_mode = paper_mode
        self.max_leverage = max_leverage
        self._orders = []  # paper trade log

        if not paper_mode and BINANCE_AVAILABLE:
            key = api_key or os.environ.get("BINANCE_API_KEY", "")
            secret = api_secret or os.environ.get("BINANCE_API_SECRET", "")
            self.client = Client(key, secret)
            self._set_leverage()
        else:
            self.client = None

    def _set_leverage(self):
        try:
            self.client.futures_change_leverage(symbol=self.symbol, leverage=self.max_leverage)
        except Exception as e:
            logger.error("Failed to set leverage: %s", e)

    def place_order(self, side: str, quantity: float, order_type: str = "MARKET") -> dict:
        """Place order. In paper mode, logs without executing."""
        order = {"symbol": self.symbol, "side": side,
                 "type": order_type, "quantity": quantity}
        if self.paper_mode:
            logger.info("[PAPER] Order: %s", order)
            self._orders.append(order)
            return {"paper": True, **order}

        try:
            result = self.client.futures_create_order(**order)
            logger.info("Order placed: %s", result)
            return result
        except Exception as e:
            logger.error("Order failed: %s", e)
            raise

    def get_position(self) -> dict:
        if self.paper_mode:
            return {}
        try:
            positions = self.client.futures_position_information(symbol=self.symbol)
            return positions[0] if positions else {}
        except Exception as e:
            logger.error("Failed to get position: %s", e)
            return {}

    def close_position(self, quantity: float, side: str) -> dict:
        close_side = "SELL" if side == "BUY" else "BUY"
        return self.place_order(close_side, quantity)
