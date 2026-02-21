"""
Rimuru Crypto Empire — Data Ingest Service
Fetches OHLCV, ticker, and orderbook data from Kraken.
Provides a REST API for other services to consume market data.
"""

from datetime import UTC, datetime
import logging
import os
from pathlib import Path
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Add shared lib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import ServiceConfig
from shared.kraken_client import KrakenClient
from shared.models import (
    OHLCV,
    MarketDataRequest,
    MarketDataResponse,
    OrderBook,
    OrderBookEntry,
    ServiceHealth,
    TickerData,
)
from shared.security import secure_app

logger = logging.getLogger("rimuru.data-ingest")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Data Ingest", version="2.0.0")
secure_app(app)
START_TIME = time.time()

# --------------- State ---------------
kraken: KrakenClient = None
cache: dict[str, dict] = {}  # pair_interval -> {data, timestamp}
CACHE_TTL = int(os.getenv("CACHE_TTL", "30"))  # seconds


def get_kraken() -> KrakenClient:
    global kraken
    if kraken is None:
        key, secret = ServiceConfig.load_kraken_keys()
        kraken = KrakenClient(key, secret)
    return kraken


def _cache_key(pair: str, interval: int) -> str:
    return f"{pair}_{interval}"


def _is_fresh(key: str) -> bool:
    if key not in cache:
        return False
    return time.time() - cache[key]["timestamp"] < CACHE_TTL


# --------------- Endpoints ---------------


@app.get("/health")
def health():
    return ServiceHealth(
        service="data-ingest",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        last_activity=datetime.now(UTC).isoformat(),
        details={"cache_entries": len(cache), "pairs": list(ServiceConfig.TRADEABLE_PAIRS.keys())},
    )


@app.get("/pairs")
def list_pairs():
    return ServiceConfig.TRADEABLE_PAIRS


@app.get("/ticker/{pair}")
def get_ticker(pair: str):
    kc = get_kraken()
    try:
        result = kc.ticker([pair])
        for v in result.values():
            ask = float(v["a"][0])
            bid = float(v["b"][0])
            last = float(v["c"][0])
            vol = float(v["v"][1])
            high = float(v["h"][1])
            low = float(v["l"][1])
            spread = (ask - bid) / ask * 100 if ask > 0 else 0
            return TickerData(
                pair=pair,
                ask=ask,
                bid=bid,
                last=last,
                volume_24h=vol,
                high_24h=high,
                low_24h=low,
                spread_pct=round(spread, 4),
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/ticker")
def get_all_tickers():
    kc = get_kraken()
    pairs = list(ServiceConfig.TRADEABLE_PAIRS.values())
    try:
        result = kc.ticker(pairs)
        tickers = {}
        for k, v in result.items():
            ask = float(v["a"][0])
            bid = float(v["b"][0])
            last = float(v["c"][0])
            vol = float(v["v"][1])
            tickers[k] = {"ask": ask, "bid": bid, "last": last, "volume_24h": vol}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return tickers


@app.get("/ohlc/{pair}")
def get_ohlc(pair: str, interval: int = 5, count: int = 200):
    ck = _cache_key(pair, interval)
    if _is_fresh(ck):
        return cache[ck]["data"]

    kc = get_kraken()
    try:
        raw = kc.ohlc(pair, interval)
        candles = [
            OHLCV(
                timestamp=float(c[0]),
                open=float(c[1]),
                high=float(c[2]),
                low=float(c[3]),
                close=float(c[4]),
                vwap=float(c[5]) if c[5] else 0,
                volume=float(c[6]),
                count=int(c[7]) if len(c) > 7 else 0,
            )
            for c in raw[-count:]
        ]
        resp = MarketDataResponse(pair=pair, interval=interval, candles=candles)
        cache[ck] = {"data": resp.model_dump(), "timestamp": time.time()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return resp


@app.get("/orderbook/{pair}")
def get_orderbook(pair: str, depth: int = 10):
    kc = get_kraken()
    try:
        raw = kc.orderbook(pair, depth)
        asks = [OrderBookEntry(price=float(a[0]), volume=float(a[1])) for a in raw.get("asks", [])]
        bids = [OrderBookEntry(price=float(b[0]), volume=float(b[1])) for b in raw.get("bids", [])]
        return OrderBook(pair=pair, asks=asks, bids=bids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/market-data")
def get_market_data(req: MarketDataRequest):
    """Full market data bundle: OHLCV + ticker for a pair"""
    ohlc_data = get_ohlc(req.pair, req.interval, req.count)
    resp = MarketDataResponse(**ohlc_data) if isinstance(ohlc_data, dict) else ohlc_data

    try:
        ticker = get_ticker(req.pair)
        resp.ticker = ticker
    except Exception:
        logger.debug("Could not fetch ticker for %s", req.pair)
    return resp


@app.get("/multi-ohlc/{pair}")
def get_multi_timeframe(pair: str):
    """Get 5m, 15m, 1h candles for a pair in one call"""
    try:
        return {
            "pair": pair,
            "5m": get_ohlc(pair, 5, 200),
            "15m": get_ohlc(pair, 15, 200),
            "1h": get_ohlc(pair, 60, 200),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/balance")
def get_balance():
    kc = get_kraken()
    try:
        bal = kc.balance()
        tb = kc.trade_balance()
        return {
            "balances": bal,
            "trade_balance": tb,
            "equivalent_usd": float(tb.get("eb", 0)),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# --------------- Metrics ---------------


@app.get("/metrics")
def prometheus_metrics():
    """Prometheus-compatible metrics endpoint"""
    uptime = time.time() - START_TIME
    lines = [
        "# HELP rimuru_data_ingest_uptime_seconds Service uptime",
        "# TYPE rimuru_data_ingest_uptime_seconds gauge",
        f"rimuru_data_ingest_uptime_seconds {uptime:.1f}",
        "# HELP rimuru_data_ingest_cache_entries Cached data entries",
        "# TYPE rimuru_data_ingest_cache_entries gauge",
        f"rimuru_data_ingest_cache_entries {len(cache)}",
        "# HELP rimuru_data_ingest_kraken_calls Total Kraken API calls",
        "# TYPE rimuru_data_ingest_kraken_calls counter",
        f"rimuru_data_ingest_kraken_calls {kraken.call_count if kraken else 0}",
    ]
    return JSONResponse(content="\n".join(lines), media_type="text/plain")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    logger.info("Rimuru Data Ingest starting on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
