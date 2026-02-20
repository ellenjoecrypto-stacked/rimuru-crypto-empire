"""
Rimuru Strategy — RSI (Relative Strength Index)
Oversold/overbought reversals with trend confirmation.
"""

import os
import sys
import time
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.models import StrategyRequest, StrategySignal, SignalAction, ServiceHealth
from shared.security import secure_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
app = FastAPI(title="Rimuru Strategy - RSI", version="2.0.0")
secure_app(app)
START_TIME = time.time()
signal_count = 0


@app.get("/health")
def health():
    return ServiceHealth(service="strategy-rsi", status="healthy",
                         uptime_seconds=round(time.time() - START_TIME, 1),
                         details={"signals_generated": signal_count})


@app.post("/signal")
def generate_signal(req: StrategyRequest):
    global signal_count
    signal_count += 1

    ind = req.indicators
    sig = StrategySignal(pair=req.pair, strategy="rsi", timeframe="15m",
                         price=ind.current_price)

    if ind.rsi is None:
        sig.reason = "RSI not available"
        return sig

    score = 0.0
    reasons = []
    rsi = ind.rsi

    # Core RSI signal
    if rsi < 20:
        score += 0.50
        reasons.append(f"RSI extreme oversold {rsi:.1f}")
    elif rsi < 30:
        score += 0.35
        reasons.append(f"RSI oversold {rsi:.1f}")
    elif rsi < 40:
        score += 0.15
        reasons.append(f"RSI low {rsi:.1f}")
    elif rsi > 80:
        score -= 0.50
        reasons.append(f"RSI extreme overbought {rsi:.1f}")
    elif rsi > 70:
        score -= 0.35
        reasons.append(f"RSI overbought {rsi:.1f}")
    elif rsi > 60:
        score -= 0.10
        reasons.append(f"RSI high {rsi:.1f}")
    else:
        reasons.append(f"RSI neutral {rsi:.1f}")

    # Bollinger confirmation
    if ind.bollinger:
        price = ind.current_price
        lower = ind.bollinger.get("lower", 0)
        upper = ind.bollinger.get("upper", 0)
        if lower and price < lower:
            score += 0.20
            reasons.append("Below lower Bollinger")
        elif upper and price > upper:
            score -= 0.20
            reasons.append("Above upper Bollinger")

    # Stochastic confirmation
    if ind.stochastic:
        if ind.stochastic.get("oversold") and ind.stochastic.get("bullish_cross"):
            score += 0.15
            reasons.append("Stoch bullish cross in oversold")
        elif ind.stochastic.get("overbought") and ind.stochastic.get("bearish_cross"):
            score -= 0.15
            reasons.append("Stoch bearish cross in overbought")

    # Williams %R confirmation
    if ind.williams_r is not None:
        if ind.williams_r < -80:
            score += 0.10
            reasons.append(f"Williams %R oversold {ind.williams_r}")
        elif ind.williams_r > -20:
            score -= 0.10
            reasons.append(f"Williams %R overbought {ind.williams_r}")

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
        content=f"rimuru_strategy_rsi_signals {signal_count}\nrimuru_strategy_rsi_uptime {time.time()-START_TIME:.1f}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8011"))
    uvicorn.run(app, host="0.0.0.0", port=port)
