"""
Rimuru Crypto Empire — Orchestrator Service
The brain. Coordinates data ingestion, indicator computation,
strategy fanout, signal aggregation, position sizing, and execution.
Runs the 24/7 trading loop.
"""

import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import ServiceConfig
from shared.models import (
    StrategySignal, EnsembleSignal, SignalAction,
    ServiceHealth,
)
from shared.security import secure_app, get_auth_headers

logger = logging.getLogger("rimuru.orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Orchestrator", version="2.0.0")
secure_app(app)
START_TIME = time.time()

# --------------- Config ---------------
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SEC", "60"))
PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() in ("true", "1")
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.45"))
STRATEGY_WEIGHTS = {
    "ma_crossover": float(os.getenv("W_MA", "1.0")),
    "rsi": float(os.getenv("W_RSI", "1.0")),
    "bollinger": float(os.getenv("W_BOLLINGER", "1.0")),
    "momentum": float(os.getenv("W_MOMENTUM", "1.0")),
    "volume": float(os.getenv("W_VOLUME", "1.0")),
    "lstm": float(os.getenv("W_LSTM", "1.5")),
}

# Service URLs
DATA_URL = os.getenv("DATA_INGEST_URL", "http://data-ingest:8000")
INDICATOR_URL = os.getenv("INDICATORS_URL", "http://indicators:8001")
EXECUTOR_URL = os.getenv("EXECUTOR_URL", "http://executor:8020")
STRATEGY_URLS = {
    "ma_crossover": os.getenv("STRATEGY_MA_URL", "http://strategy-ma:8010"),
    "rsi": os.getenv("STRATEGY_RSI_URL", "http://strategy-rsi:8011"),
    "bollinger": os.getenv("STRATEGY_BOLLINGER_URL", "http://strategy-bollinger:8012"),
    "momentum": os.getenv("STRATEGY_MOMENTUM_URL", "http://strategy-momentum:8013"),
    "volume": os.getenv("STRATEGY_VOLUME_URL", "http://strategy-volume:8014"),
    "lstm": os.getenv("STRATEGY_LSTM_URL", "http://strategy-lstm:8015"),
}

# State
scan_count = 0
last_signals: Dict[str, EnsembleSignal] = {}
running = False
fear_greed_cache = {"value": 50, "timestamp": 0}


# --------------- HTTP helpers ---------------

def _post_json(url: str, data: dict, timeout: int = 15) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in get_auth_headers().items():
        req.add_header(k, v)
    resp = urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


def _get_json(url: str, timeout: int = 10) -> dict:
    req = Request(url)
    for k, v in get_auth_headers().items():
        req.add_header(k, v)
    resp = urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


# --------------- Fear & Greed ---------------

def _get_fear_greed() -> int:
    if time.time() - fear_greed_cache["timestamp"] < 3600:
        return fear_greed_cache["value"]
    try:
        data = _get_json("https://api.alternative.me/fng/?limit=1", timeout=5)
        val = int(data["data"][0]["value"])
        fear_greed_cache["value"] = val
        fear_greed_cache["timestamp"] = time.time()
        return val
    except Exception:
        return fear_greed_cache["value"]


# --------------- Core Logic ---------------

def _fetch_candles(pair: str) -> dict:
    """Fetch multi-timeframe candles from data-ingest"""
    try:
        return _get_json(f"{DATA_URL}/multi-ohlc/{pair}")
    except Exception as e:
        logger.error(f"Data fetch error for {pair}: {e}")
        return {}


def _compute_indicators(pair: str, candles: List[dict]) -> Optional[dict]:
    """Send candles to indicators service"""
    try:
        return _post_json(f"{INDICATOR_URL}/compute", {
            "pair": pair,
            "candles": candles,
            "indicators": ["all"],
        })
    except Exception as e:
        logger.error(f"Indicator error for {pair}: {e}")
        return None


def _get_strategy_signal(strategy: str, url: str, req_data: dict) -> Optional[dict]:
    """Get signal from a strategy service"""
    try:
        return _post_json(f"{url}/signal", req_data, timeout=10)
    except Exception as e:
        logger.warning(f"Strategy {strategy} error: {e}")
        return None


def _kelly_size(confidence: float, available_usd: float) -> float:
    """Half-Kelly Criterion position sizing"""
    win_rate = 0.5 + (confidence - 0.5) * 0.5
    win_loss_ratio = 1.5
    kelly = win_rate - (1 - win_rate) / win_loss_ratio
    kelly = max(0, min(kelly * 0.5, 0.25))  # Half-Kelly, cap at 25%
    return available_usd * kelly


def _scan_pair(pair: str, pair_name: str, available_usd: float, open_positions: int) -> Optional[EnsembleSignal]:
    """Full analysis pipeline for a single pair"""
    # 1. Fetch candles
    multi = _fetch_candles(pair)
    if not multi:
        return None

    # Extract candle arrays for each timeframe
    candles_15m = multi.get("15m", {})
    if isinstance(candles_15m, dict):
        candles_15m = candles_15m.get("candles", [])
    candles_5m = multi.get("5m", {})
    if isinstance(candles_5m, dict):
        candles_5m = candles_5m.get("candles", [])
    candles_1h = multi.get("1h", {})
    if isinstance(candles_1h, dict):
        candles_1h = candles_1h.get("candles", [])

    if not candles_15m:
        return None

    # 2. Compute indicators on 15m (primary timeframe)
    indicators = _compute_indicators(pair, candles_15m)
    if not indicators:
        return None

    # 3. Fan out to all strategy services
    strat_request = {
        "pair": pair,
        "indicators": indicators,
        "candles_5m": candles_5m if isinstance(candles_5m, list) else [],
        "candles_15m": candles_15m if isinstance(candles_15m, list) else [],
        "candles_1h": candles_1h if isinstance(candles_1h, list) else [],
        "available_usd": available_usd,
        "open_positions": open_positions,
    }

    signals = []
    for strat_name, strat_url in STRATEGY_URLS.items():
        sig = _get_strategy_signal(strat_name, strat_url, strat_request)
        if sig:
            # Apply weight
            weight = STRATEGY_WEIGHTS.get(strat_name, 1.0)
            if sig.get("confidence"):
                sig["confidence"] = min(0.99, sig["confidence"] * weight)
            signals.append(sig)

    if not signals:
        return None

    # 4. Aggregate signals
    buy_signals = [s for s in signals if s.get("action") == "buy"]
    sell_signals = [s for s in signals if s.get("action") == "sell"]

    fear_greed = _get_fear_greed()
    current_price = indicators.get("current_price", 0)
    regime = indicators.get("market_regime", {})

    if len(buy_signals) > len(sell_signals) and buy_signals:
        best = max(buy_signals, key=lambda s: s.get("confidence", 0))
        ensemble = EnsembleSignal(
            pair=pair,
            action=SignalAction.BUY,
            confidence=best.get("confidence", 0),
            strategies_agree=len(buy_signals),
            strategies_total=len(signals),
            best_strategy=best.get("strategy", ""),
            reason=best.get("reason", ""),
            price=current_price,
            stop_loss=best.get("stop_loss", 0),
            take_profit=best.get("take_profit", 0),
            suggested_volume=_kelly_size(best.get("confidence", 0), available_usd) / current_price if current_price > 0 else 0,
            individual_signals=[StrategySignal(**s) for s in signals],
            market_regime=regime.get("regime", "") if isinstance(regime, dict) else "",
            fear_greed=fear_greed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    elif len(sell_signals) > len(buy_signals) and sell_signals:
        best = max(sell_signals, key=lambda s: s.get("confidence", 0))
        ensemble = EnsembleSignal(
            pair=pair,
            action=SignalAction.SELL,
            confidence=best.get("confidence", 0),
            strategies_agree=len(sell_signals),
            strategies_total=len(signals),
            best_strategy=best.get("strategy", ""),
            reason=best.get("reason", ""),
            price=current_price,
            individual_signals=[StrategySignal(**s) for s in signals],
            market_regime=regime.get("regime", "") if isinstance(regime, dict) else "",
            fear_greed=fear_greed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    else:
        ensemble = EnsembleSignal(
            pair=pair,
            action=SignalAction.HOLD,
            strategies_total=len(signals),
            price=current_price,
            reason="No consensus",
            individual_signals=[StrategySignal(**s) for s in signals],
            market_regime=regime.get("regime", "") if isinstance(regime, dict) else "",
            fear_greed=fear_greed,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return ensemble


def _execute_signal(signal: EnsembleSignal):
    """Send signal to executor if actionable"""
    if signal.action == SignalAction.HOLD:
        return

    if signal.confidence < MIN_CONFIDENCE:
        logger.info(f"{signal.pair}: {signal.action.value} confidence {signal.confidence:.2f} < {MIN_CONFIDENCE} — skip")
        return

    # Fear & Greed filter: extreme fear = buy more, extreme greed = buy less
    fg = signal.fear_greed
    if signal.action == SignalAction.BUY and fg > 80:
        logger.info(f"{signal.pair}: Extreme greed ({fg}) — reducing position")
        signal.suggested_volume *= 0.5

    order = {
        "pair": signal.pair,
        "side": signal.action.value,
        "order_type": "market",
        "volume": signal.suggested_volume,
        "price": signal.price,
        "stop_loss": signal.stop_loss,
        "take_profit": signal.take_profit,
        "strategy": signal.best_strategy,
        "signal_confidence": signal.confidence,
        "validate_only": PAPER_MODE,
    }

    try:
        result = _post_json(f"{EXECUTOR_URL}/execute", order)
        if result.get("success"):
            logger.info(
                f"EXECUTED {signal.action.value.upper()} {signal.pair} "
                f"vol={signal.suggested_volume:.6f} via {signal.best_strategy} "
                f"({signal.strategies_agree}/{signal.strategies_total} agree)"
            )
        else:
            logger.warning(f"Execution failed: {result.get('error', 'unknown')}")
    except Exception as e:
        logger.error(f"Executor call failed: {e}")


def _scan_loop():
    """Main 24/7 scanning loop"""
    global scan_count, running
    running = True
    logger.info(f"Scan loop started [{'PAPER' if PAPER_MODE else 'LIVE'}] — interval {SCAN_INTERVAL}s")

    while running:
        try:
            scan_count += 1
            logger.info(f"--- Scan #{scan_count} ---")

            # Get portfolio state
            try:
                portfolio = _get_json(f"{EXECUTOR_URL}/portfolio")
                available_usd = portfolio.get("available_usd", 0)
                open_positions = len(portfolio.get("open_positions", []))
            except Exception:
                available_usd = 10.0
                open_positions = 0

            # Scan all pairs
            for name, pair in ServiceConfig.TRADEABLE_PAIRS.items():
                try:
                    signal = _scan_pair(pair, name, available_usd, open_positions)
                    if signal:
                        last_signals[pair] = signal
                        _execute_signal(signal)
                except Exception as e:
                    logger.error(f"Error scanning {name}: {e}")

                time.sleep(2)  # Rate limit between pairs

        except Exception as e:
            logger.error(f"Scan loop error: {e}")

        time.sleep(SCAN_INTERVAL)


# --------------- API Endpoints ---------------

@app.get("/health")
def health():
    return ServiceHealth(
        service="orchestrator",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={
            "scan_count": scan_count,
            "running": running,
            "paper_mode": PAPER_MODE,
            "pairs": list(ServiceConfig.TRADEABLE_PAIRS.keys()),
            "strategies": list(STRATEGY_URLS.keys()),
        },
    )


@app.get("/signals")
def get_signals():
    """Get latest signals for all pairs"""
    return {k: v.model_dump() for k, v in last_signals.items()}


@app.get("/signals/{pair}")
def get_signal(pair: str):
    if pair in last_signals:
        return last_signals[pair]
    raise HTTPException(status_code=404, detail=f"No signals for {pair}")


@app.post("/scan/{pair}")
def manual_scan(pair: str):
    """Trigger a manual scan for a specific pair"""
    try:
        portfolio = _get_json(f"{EXECUTOR_URL}/portfolio")
        available_usd = portfolio.get("available_usd", 0)
        open_positions = len(portfolio.get("open_positions", []))
    except Exception:
        available_usd = 10.0
        open_positions = 0

    signal = _scan_pair(pair, pair, available_usd, open_positions)
    if signal:
        last_signals[pair] = signal
        return signal
    raise HTTPException(status_code=500, detail="Scan failed")


@app.post("/start")
def start_scanning():
    global running
    if running:
        return {"status": "already running"}
    thread = threading.Thread(target=_scan_loop, daemon=True)
    thread.start()
    return {"status": "started", "paper_mode": PAPER_MODE}


@app.post("/stop")
def stop_scanning():
    global running
    running = False
    return {"status": "stopped"}


@app.get("/status")
def get_status():
    """Full system status"""
    services = {}
    for name, url in {
        "data-ingest": DATA_URL,
        "indicators": INDICATOR_URL,
        "executor": EXECUTOR_URL,
        **{f"strategy-{k}": v for k, v in STRATEGY_URLS.items()},
    }.items():
        try:
            h = _get_json(f"{url}/health")
            services[name] = {"status": "healthy", "uptime": h.get("uptime_seconds", 0)}
        except Exception:
            services[name] = {"status": "DOWN"}

    return {
        "orchestrator": {
            "running": running,
            "scan_count": scan_count,
            "paper_mode": PAPER_MODE,
            "uptime": round(time.time() - START_TIME, 1),
        },
        "services": services,
        "last_signals": {k: {"action": v.action.value, "confidence": v.confidence, "pair": v.pair}
                        for k, v in last_signals.items()},
        "fear_greed": fear_greed_cache["value"],
    }


@app.get("/metrics")
def prometheus_metrics():
    lines = [
        f"rimuru_orchestrator_uptime {time.time()-START_TIME:.1f}",
        f"rimuru_orchestrator_scans {scan_count}",
        f"rimuru_orchestrator_running {int(running)}",
        f"rimuru_orchestrator_paper_mode {int(PAPER_MODE)}",
        f"rimuru_orchestrator_fear_greed {fear_greed_cache['value']}",
    ]
    for pair, sig in last_signals.items():
        lines.append(f'rimuru_signal_confidence{{pair="{pair}"}} {sig.confidence:.4f}')
    return JSONResponse(content="\n".join(lines), media_type="text/plain")


@app.on_event("startup")
def startup():
    """Start scanning loop on service startup"""
    auto_start = os.getenv("AUTO_START", "true").lower() in ("true", "1")
    if auto_start:
        thread = threading.Thread(target=_scan_loop, daemon=True)
        thread.start()
        logger.info("Auto-started scan loop")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8030"))
    logger.info(f"Rimuru Orchestrator starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
