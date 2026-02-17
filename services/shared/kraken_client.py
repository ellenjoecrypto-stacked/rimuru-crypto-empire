"""
Rimuru Crypto Empire — Kraken API Client
Extracted for reuse across microservices.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request

logger = logging.getLogger("rimuru.kraken")


class KrakenClient:
    BASE_URL = "https://api.kraken.com"

    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret
        self._call_count = 0
        self._last_call = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_call = time.time()
        self._call_count += 1

    def _sign(self, urlpath: str, data: dict) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data["nonce"]) + postdata).encode("utf-8")
        message = urlpath.encode("utf-8") + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode("utf-8")

    def _private(self, endpoint: str, data: dict = None) -> dict:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        if data is None:
            data = {}
        data["nonce"] = str(int(time.time() * 1000))
        sig = self._sign(endpoint, data)
        postdata = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=postdata, method="POST")
        req.add_header("API-Key", self.key)
        req.add_header("API-Sign", sig)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get("error"):
            raise Exception(f"Kraken API: {result['error']}")
        return result.get("result", {})

    def _public(self, endpoint: str, params: dict = None) -> dict:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        if result.get("error"):
            raise Exception(f"Kraken API: {result['error']}")
        return result.get("result", {})

    # ----- Public endpoints -----

    def ticker(self, pairs: list) -> dict:
        return self._public("/0/public/Ticker", {"pair": ",".join(pairs)})

    def ohlc(self, pair: str, interval: int = 5, since: int = None) -> list:
        params = {"pair": pair, "interval": interval}
        if since:
            params["since"] = since
        result = self._public("/0/public/OHLC", params)
        for v in result.values():
            if isinstance(v, list):
                return v
        return []

    def orderbook(self, pair: str, count: int = 10) -> dict:
        result = self._public("/0/public/Depth", {"pair": pair, "count": count})
        for v in result.values():
            if isinstance(v, dict):
                return v
        return {}

    def system_status(self) -> dict:
        return self._public("/0/public/SystemStatus")

    # ----- Private endpoints -----

    def balance(self) -> dict:
        return self._private("/0/private/Balance")

    def trade_balance(self) -> dict:
        return self._private("/0/private/TradeBalance", {"asset": "ZUSD"})

    def open_orders(self) -> dict:
        result = self._private("/0/private/OpenOrders")
        return result.get("open", {})

    def closed_orders(self, start: int = None) -> dict:
        data = {}
        if start:
            data["start"] = start
        result = self._private("/0/private/ClosedOrders", data)
        return result.get("closed", {})

    def place_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        volume: float,
        price: float = None,
        validate: bool = False,
    ) -> dict:
        data = {
            "pair": pair,
            "type": side,
            "ordertype": order_type,
            "volume": str(volume),
        }
        if price is not None:
            data["price"] = str(price)
        if validate:
            data["validate"] = "true"
        return self._private("/0/private/AddOrder", data)

    def cancel_order(self, txid: str) -> dict:
        return self._private("/0/private/CancelOrder", {"txid": txid})
