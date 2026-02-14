"""
Rimuru Strategy — Volume Surge Detection
Detects unusual volume patterns that precede price moves.
"""

import os, sys, time, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.models import StrategyRequest, StrategySignal, SignalAction, ServiceHealth
from shared.security import secure_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = FastAPI(title="Rimuru Strategy - Volume", version="2.0.0")
secure_app(app)
START_TIME = time.time()
signal_count = 0


@app.get("/health")
def health():
    return ServiceHealth(service="strategy-volume", status="healthy",
                         uptime_seconds=round(time.time() - START_TIME, 1),
                         details={"signals_generated": signal_count})


@app.post("/signal")
def generate_signal(req: StrategyRequest):
    global signal_count
    signal_count += 1

    ind = req.indicators
    sig = StrategySignal(pair=req.pair, strategy="volume", timeframe="15m",
                         price=ind.current_price)

    score = 0.0
    reasons = []

    # Volume trend is the primary indicator
    if ind.volume_trend is None:
        sig.reason = "Volume data not available"
        return sig

    vt = ind.volume_trend

    # Major volume surge with price direction
    if vt > 50:
        reasons.append(f"MAJOR volume surge +{vt:.0f}%")
        # Need price confirmation
        if ind.momentum and ind.momentum > 0:
            score += 0.45
            reasons.append(f"Price rising +{ind.momentum:.1f}%")
        elif ind.momentum and ind.momentum < -1:
            score -= 0.35
            reasons.append(f"Capitulation selling {ind.momentum:.1f}%")
        else:
            score += 0.20
            reasons.append("Accumulation pattern")
    elif vt > 20:
        reasons.append(f"Volume surge +{vt:.0f}%")
        if ind.momentum and ind.momentum > 0:
            score += 0.30
            reasons.append("Bullish volume")
        elif ind.momentum and ind.momentum < 0:
            score -= 0.20
            reasons.append("Bearish volume")
    elif vt < -30:
        reasons.append(f"Volume drying up {vt:.0f}%")
        score -= 0.10
    else:
        reasons.append(f"Normal volume {vt:.0f}%")

    # VWAP confirmation — price above VWAP with volume = institutional buying
    if ind.vwap:
        if ind.vwap.get("above_vwap") and vt > 20:
            score += 0.15
            reasons.append("Above VWAP with volume")
        elif ind.vwap.get("below_vwap") and vt > 20:
            score -= 0.15
            reasons.append("Below VWAP with volume (distribution)")

    # ADX — Volume surge in strong trend
    if ind.adx and ind.adx.get("strong_trend"):
        if ind.adx.get("bullish") and score > 0:
            score += 0.10
            reasons.append("Strong bullish trend")
        elif ind.adx.get("bearish") and score < 0:
            score -= 0.10
            reasons.append("Strong bearish trend")

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
        content=f"rimuru_strategy_volume_signals {signal_count}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8014"))
    uvicorn.run(app, host="0.0.0.0", port=port)
