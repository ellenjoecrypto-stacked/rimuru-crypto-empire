"""
Rimuru Strategy — Momentum
EMA crossover + RSI + volume-based momentum scalping.
"""

import logging
import os
from pathlib import Path
import sys
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.models import ServiceHealth, SignalAction, StrategyRequest, StrategySignal
from shared.security import secure_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = FastAPI(title="Rimuru Strategy - Momentum", version="2.0.0")
secure_app(app)
START_TIME = time.time()
signal_count = 0


@app.get("/health")
def health():
    return ServiceHealth(
        service="strategy-momentum",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={"signals_generated": signal_count},
    )


@app.post("/signal")
def generate_signal(req: StrategyRequest):
    global signal_count
    signal_count += 1

    ind = req.indicators
    sig = StrategySignal(
        pair=req.pair, strategy="momentum", timeframe="5m", price=ind.current_price
    )

    score = 0.0
    reasons = []

    # EMA crossover (5 vs 12)
    ema_fast = ind.ema_5
    ema_slow = ind.ema_12
    if ema_fast and ema_slow:
        if ema_fast > ema_slow:
            spread = (ema_fast - ema_slow) / ema_slow * 100
            if spread > 0.1:
                score += 0.25
                reasons.append(f"EMA bull +{spread:.2f}%")
        else:
            spread = (ema_slow - ema_fast) / ema_slow * 100
            if spread > 0.2:
                score -= 0.30
                reasons.append(f"EMA bear -{spread:.2f}%")

    # RSI
    if ind.rsi is not None:
        if ind.rsi < 30:
            score += 0.30
            reasons.append(f"RSI oversold {ind.rsi:.0f}")
        elif ind.rsi < 40:
            score += 0.15
            reasons.append(f"RSI low {ind.rsi:.0f}")
        elif ind.rsi > 75:
            score -= 0.30
            reasons.append(f"RSI overbought {ind.rsi:.0f}")

    # Momentum indicator
    if ind.momentum is not None:
        if ind.momentum > 0.5:
            score += 0.20
            reasons.append(f"Mom +{ind.momentum:.1f}%")
        elif ind.momentum < -0.5:
            score -= 0.15
            reasons.append(f"Mom {ind.momentum:.1f}%")

    # Volume trend
    if ind.volume_trend is not None:
        if ind.volume_trend > 20:
            score += 0.15
            reasons.append(f"Vol surge +{ind.volume_trend:.0f}%")
        elif ind.volume_trend < -20:
            score -= 0.10
            reasons.append(f"Vol declining {ind.volume_trend:.0f}%")

    # ADX trend strength filter
    if ind.adx and ind.adx.get("strong_trend") and ind.adx.get("bullish") and score > 0:
        score += 0.10
        reasons.append(f"ADX strong trend {ind.adx['adx']}")

    sig.reason = " | ".join(reasons)
    if score > 0.3:
        sig.action = SignalAction.BUY
        sig.confidence = min(0.95, score)
    elif score < -0.3:
        sig.action = SignalAction.SELL
        sig.confidence = min(0.95, abs(score))
    else:
        sig.action = SignalAction.HOLD
        sig.confidence = abs(score)

    return sig


@app.get("/metrics")
def metrics():
    return JSONResponse(
        content=f"rimuru_strategy_momentum_signals {signal_count}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8013"))
    uvicorn.run(app, host="0.0.0.0", port=port)
