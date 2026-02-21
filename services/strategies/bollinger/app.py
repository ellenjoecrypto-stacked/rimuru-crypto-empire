"""
Rimuru Strategy — Bollinger Bands
Mean reversion with Bollinger Band bounces.
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
app = FastAPI(title="Rimuru Strategy - Bollinger", version="2.0.0")
secure_app(app)
START_TIME = time.time()
signal_count = 0


@app.get("/health")
def health():
    return ServiceHealth(
        service="strategy-bollinger",
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
        pair=req.pair, strategy="bollinger", timeframe="15m", price=ind.current_price
    )

    if ind.bollinger is None:
        sig.reason = "Bollinger data not available"
        return sig

    score = 0.0
    reasons = []
    price = ind.current_price
    lower = ind.bollinger.get("lower", 0)
    upper = ind.bollinger.get("upper", 0)
    width = ind.bollinger.get("width", 0)

    if not lower or not upper:
        sig.reason = "Invalid Bollinger values"
        return sig

    bb_range = upper - lower
    position = (price - lower) / bb_range if bb_range > 0 else 0.5

    # Price near or below lower band — BUY signal
    if price < lower:
        score += 0.40
        reasons.append(f"BELOW lower BB ({position:.2f})")
    elif position < 0.15:
        score += 0.30
        reasons.append(f"Near lower BB ({position:.2f})")
    elif position < 0.30:
        score += 0.15
        reasons.append(f"Low BB zone ({position:.2f})")

    # Price near or above upper band — SELL signal
    if price > upper:
        score -= 0.40
        reasons.append(f"ABOVE upper BB ({position:.2f})")
    elif position > 0.85:
        score -= 0.30
        reasons.append(f"Near upper BB ({position:.2f})")
    elif position > 0.70:
        score -= 0.15
        reasons.append(f"High BB zone ({position:.2f})")

    # Squeeze detection (low width = breakout coming)
    if width < 1.5:
        reasons.append(f"BB squeeze! Width={width:.2f}%")

    # RSI confirmation
    if ind.rsi is not None:
        if ind.rsi < 30 and score > 0:
            score += 0.15
            reasons.append(f"RSI confirms oversold {ind.rsi:.0f}")
        elif ind.rsi > 70 and score < 0:
            score += 0.15  # enhances sell
            reasons.append(f"RSI confirms overbought {ind.rsi:.0f}")

    # VWAP confirmation
    if ind.vwap and ind.vwap.get("below_vwap") and score > 0:
        score += 0.10
        reasons.append("Below VWAP (institutional support)")

    sig.reason = " | ".join(reasons)
    if score > 0.25:
        sig.action = SignalAction.BUY
        sig.confidence = min(0.95, score)
    elif score < -0.25:
        sig.action = SignalAction.SELL
        sig.confidence = min(0.95, abs(score))
    else:
        sig.action = SignalAction.HOLD
        sig.confidence = abs(score)

    return sig


@app.get("/metrics")
def metrics():
    return JSONResponse(
        content=f"rimuru_strategy_bollinger_signals {signal_count}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8012"))
    uvicorn.run(app, host="0.0.0.0", port=port)
