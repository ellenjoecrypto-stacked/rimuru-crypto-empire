"""
Rimuru Strategy — MA Crossover (Golden Cross / Death Cross)
50/200 SMA crossover on hourly timeframe.
"""

import os, sys, time, logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.models import StrategyRequest, StrategySignal, SignalAction, ServiceHealth

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = FastAPI(title="Rimuru Strategy - MA Crossover", version="2.0.0")
START_TIME = time.time()
signal_count = 0


@app.get("/health")
def health():
    return ServiceHealth(service="strategy-ma", status="healthy",
                         uptime_seconds=round(time.time() - START_TIME, 1),
                         details={"signals_generated": signal_count})


@app.post("/signal")
def generate_signal(req: StrategyRequest):
    global signal_count
    signal_count += 1

    ind = req.indicators
    sig = StrategySignal(pair=req.pair, strategy="ma_crossover", timeframe="1h",
                         price=ind.current_price)

    sma_50 = ind.sma_50
    sma_200 = ind.sma_200

    if sma_50 is None or sma_200 is None:
        sig.reason = "Insufficient data for 50/200 SMA"
        return sig

    score = 0.0
    reasons = []

    # Golden Cross: SMA50 crosses above SMA200
    if sma_50 > sma_200:
        spread = (sma_50 - sma_200) / sma_200 * 100
        if spread < 1.0:
            score += 0.45
            reasons.append(f"GOLDEN CROSS fresh (+{spread:.2f}%)")
        else:
            score += 0.30
            reasons.append(f"SMA50 > SMA200 (+{spread:.2f}%)")
    else:
        spread = (sma_200 - sma_50) / sma_200 * 100
        if spread < 1.0:
            score -= 0.45
            reasons.append(f"DEATH CROSS fresh (-{spread:.2f}%)")
        else:
            score -= 0.30
            reasons.append(f"SMA50 < SMA200 (-{spread:.2f}%)")

    # RSI confirmation
    if ind.rsi is not None:
        if ind.rsi < 35:
            score += 0.15
            reasons.append(f"RSI oversold {ind.rsi:.0f}")
        elif ind.rsi > 70:
            score -= 0.15
            reasons.append(f"RSI overbought {ind.rsi:.0f}")

    # MACD confirmation
    if ind.macd and ind.macd.get("histogram"):
        if ind.macd["histogram"] > 0:
            score += 0.10
            reasons.append("MACD bullish")
        else:
            score -= 0.10
            reasons.append("MACD bearish")

    # Volume confirmation
    if ind.volume_trend is not None and ind.volume_trend > 20:
        score += 0.10
        reasons.append(f"Volume surge +{ind.volume_trend:.0f}%")

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
        content=f"rimuru_strategy_ma_signals {signal_count}\nrimuru_strategy_ma_uptime {time.time()-START_TIME:.1f}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8010"))
    uvicorn.run(app, host="0.0.0.0", port=port)
