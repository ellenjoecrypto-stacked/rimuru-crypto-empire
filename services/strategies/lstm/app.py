"""
Rimuru Strategy — LSTM (Machine Learning Prediction)
Uses a simple LSTM-like model for price direction prediction.
In production, this loads a trained model from the model registry.
For now, uses a heuristic ensemble as a placeholder until training data
is collected by the backtester service.
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
app = FastAPI(title="Rimuru Strategy - LSTM", version="2.0.0")
secure_app(app)
START_TIME = time.time()
signal_count = 0
MODEL_LOADED = False


@app.get("/health")
def health():
    return ServiceHealth(
        service="strategy-lstm",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={"signals_generated": signal_count, "model_loaded": MODEL_LOADED},
    )


def _heuristic_prediction(ind) -> dict:
    """
    Weighted ensemble of all indicators as an ML proxy.
    Each indicator contributes a normalized score [-1, 1].
    This acts as a stand-in until a real LSTM model is trained.
    """
    weights = {
        "rsi": 0.15,
        "bollinger": 0.15,
        "macd": 0.12,
        "stochastic": 0.12,
        "ema": 0.12,
        "volume": 0.10,
        "fibonacci": 0.08,
        "vwap": 0.07,
        "adx": 0.05,
        "williams": 0.04,
    }
    signals = {}

    # RSI
    if ind.rsi is not None:
        if ind.rsi < 30:
            signals["rsi"] = 0.8
        elif ind.rsi < 40:
            signals["rsi"] = 0.3
        elif ind.rsi > 70:
            signals["rsi"] = -0.8
        elif ind.rsi > 60:
            signals["rsi"] = -0.3
        else:
            signals["rsi"] = 0.0

    # Bollinger
    if ind.bollinger:
        lower = ind.bollinger.get("lower", 0)
        upper = ind.bollinger.get("upper", 0)
        if lower and upper and (upper - lower) > 0:
            pos = (ind.current_price - lower) / (upper - lower)
            signals["bollinger"] = 1.0 - 2.0 * pos  # -1 at top, +1 at bottom

    # MACD
    if ind.macd and ind.macd.get("histogram") is not None:
        h = ind.macd["histogram"]
        signals["macd"] = max(-1, min(1, h / (abs(h) + 0.001) * 0.8))

    # Stochastic
    if ind.stochastic:
        k = ind.stochastic.get("k", 50)
        signals["stochastic"] = (50 - k) / 50

    # EMA
    if ind.ema_5 and ind.ema_26:
        spread = (ind.ema_5 - ind.ema_26) / ind.ema_26 * 100
        signals["ema"] = max(-1, min(1, spread / 2))

    # Volume
    if ind.volume_trend is not None:
        signals["volume"] = max(-1, min(1, ind.volume_trend / 50))

    # Fibonacci
    if ind.fibonacci:
        fp = ind.fibonacci.get("fib_position", 0.5)
        signals["fibonacci"] = 1.0 - 2.0 * fp

    # VWAP
    if ind.vwap:
        dev = ind.vwap.get("deviation_pct", 0)
        signals["vwap"] = max(-1, min(1, -dev / 2))

    # ADX
    if ind.adx:
        if ind.adx.get("bullish"):
            signals["adx"] = min(1, ind.adx["adx"] / 50)
        else:
            signals["adx"] = -min(1, ind.adx["adx"] / 50)

    # Williams Percent Range
    if ind.williams_r is not None:
        signals["williams"] = (-ind.williams_r - 50) / 50

    # Weighted sum
    total_score = 0.0
    total_weight = 0.0
    for key, val in signals.items():
        w = weights.get(key, 0.05)
        total_score += val * w
        total_weight += w

    final = total_score / total_weight if total_weight > 0 else 0
    return {"prediction": final, "indicators_used": len(signals), "signals": signals}


@app.post("/signal")
def generate_signal(req: StrategyRequest):
    global signal_count
    signal_count += 1

    ind = req.indicators
    sig = StrategySignal(pair=req.pair, strategy="lstm", timeframe="15m", price=ind.current_price)

    result = _heuristic_prediction(ind)
    prediction = result["prediction"]
    n_indicators = result["indicators_used"]

    if n_indicators < 4:
        sig.reason = f"Only {n_indicators} indicators available (need 4+)"
        return sig

    confidence = abs(prediction)
    reasons = [f"ML ensemble score={prediction:.3f} ({n_indicators} indicators)"]

    # Market regime filter
    if ind.market_regime:
        regime = ind.market_regime.get("regime", "MIXED")
        reasons.append(f"Regime: {regime}")
        if regime == "VOLATILE" and confidence < 0.4:
            reasons.append("Filtered: too volatile for weak signal")
            sig.reason = " | ".join(reasons)
            return sig

    sig.reason = " | ".join(reasons)
    if prediction > 0.15 and confidence > 0.2:
        sig.action = SignalAction.BUY
        sig.confidence = min(0.90, confidence)
    elif prediction < -0.15 and confidence > 0.2:
        sig.action = SignalAction.SELL
        sig.confidence = min(0.90, confidence)
    else:
        sig.action = SignalAction.HOLD
        sig.confidence = confidence

    return sig


@app.get("/metrics")
def metrics():
    return JSONResponse(
        content=f"rimuru_strategy_lstm_signals {signal_count}\nrimuru_strategy_lstm_model_loaded {int(MODEL_LOADED)}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8015"))
    uvicorn.run(app, host="0.0.0.0", port=port)
