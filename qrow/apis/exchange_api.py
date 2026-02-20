"""Exchange API wrapper — unified interface for CEX data."""

import requests
from core.config import SAFE_MODE


class ExchangeAPI:
    """Lightweight wrapper for public exchange endpoints (no auth required)."""

    ENDPOINTS = {
        "binance": "https://api.binance.com/api/v3",
        "coinbase": "https://api.coinbase.com/v2",
    }

    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange
        self.base = self.ENDPOINTS.get(exchange, self.ENDPOINTS["binance"])

    def get_ticker(self, symbol: str) -> dict:
        if SAFE_MODE:
            return {"status": "safe_mode", "symbol": symbol, "price": "N/A"}
        if self.exchange == "binance":
            resp = requests.get(
                f"{self.base}/ticker/price",
                params={"symbol": symbol},
                timeout=10,
            )
            return resp.json()
        return {"error": "exchange not supported yet"}

    def get_orderbook(self, symbol: str, limit: int = 20) -> dict:
        if SAFE_MODE:
            return {"status": "safe_mode", "symbol": symbol, "bids": [], "asks": []}
        if self.exchange == "binance":
            resp = requests.get(
                f"{self.base}/depth",
                params={"symbol": symbol, "limit": limit},
                timeout=10,
            )
            return resp.json()
        return {"error": "exchange not supported yet"}

    def get_klines(self, symbol: str, interval: str = "1h", limit: int = 100) -> list:
        if SAFE_MODE:
            return []
        if self.exchange == "binance":
            resp = requests.get(
                f"{self.base}/klines",
                params={"symbol": symbol, "interval": interval, "limit": limit},
                timeout=10,
            )
            return resp.json()
        return []
