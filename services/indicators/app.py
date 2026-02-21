"""
Rimuru Crypto Empire — Indicators Service
Computes all technical analysis indicators from OHLCV data.
Exposes a REST API consumed by strategy services.
"""

import logging
import math
import os
from pathlib import Path
import statistics
import sys
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.models import IndicatorRequest, IndicatorResult, ServiceHealth
from shared.security import secure_app

logger = logging.getLogger("rimuru.indicators")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Indicators", version="2.0.0")
secure_app(app)
START_TIME = time.time()
calc_count = 0


# ============================================
# Technical Analysis Library
# ============================================


class TA:
    @staticmethod
    def sma(prices: list, period: int) -> float | None:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    @staticmethod
    def ema(prices: list, period: int) -> float | None:
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    @staticmethod
    def rsi(prices: list, period: int = 14) -> float | None:
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def bollinger(prices: list, period: int = 20, std_dev: float = 2.0):
        if len(prices) < period:
            return None
        sma = sum(prices[-period:]) / period
        variance = sum((p - sma) ** 2 for p in prices[-period:]) / period
        std = math.sqrt(variance)
        return {
            "lower": sma - std_dev * std,
            "middle": sma,
            "upper": sma + std_dev * std,
            "width": (2 * std_dev * std) / sma * 100 if sma else 0,
        }

    @staticmethod
    def momentum(prices: list, period: int = 10) -> float | None:
        if len(prices) < period + 1:
            return None
        return (prices[-1] - prices[-period - 1]) / prices[-period - 1] * 100

    @staticmethod
    def atr(candles: list, period: int = 14) -> float | None:
        if len(candles) < period + 1:
            return None
        trs = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period

    @staticmethod
    def volume_trend(candles: list, period: int = 10) -> float | None:
        if len(candles) < period * 2:
            return None
        recent_vol = sum(c.volume for c in candles[-period:]) / period
        older_vol = sum(c.volume for c in candles[-period * 2 : -period]) / period
        if older_vol == 0:
            return 0
        return (recent_vol - older_vol) / older_vol * 100

    @staticmethod
    def macd(prices: list, fast=12, slow=26, signal_period=9):
        if len(prices) < slow + signal_period:
            return None
        fast_ema = TA.ema(prices, fast)
        slow_ema = TA.ema(prices, slow)
        if fast_ema is None or slow_ema is None:
            return None
        macd_line = fast_ema - slow_ema
        macd_values = []
        for i in range(slow, len(prices)):
            fe = TA.ema(prices[: i + 1], fast)
            se = TA.ema(prices[: i + 1], slow)
            if fe and se:
                macd_values.append(fe - se)
        signal_line = (
            TA.ema(macd_values, signal_period) if len(macd_values) >= signal_period else None
        )
        histogram = macd_line - signal_line if signal_line else None
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}

    @staticmethod
    def stochastic(candles: list, k_period: int = 14, d_period: int = 3) -> dict | None:
        if len(candles) < k_period + d_period:
            return None
        k_values = []
        for i in range(k_period - 1, len(candles)):
            window = candles[i - k_period + 1 : i + 1]
            highest = max(c.high for c in window)
            lowest = min(c.low for c in window)
            close = candles[i].close
            if highest == lowest:
                k_values.append(50.0)
            else:
                k_values.append((close - lowest) / (highest - lowest) * 100)
        if len(k_values) < d_period:
            return None
        k_current = k_values[-1]
        k_prev = k_values[-2] if len(k_values) >= 2 else k_current
        d_current = sum(k_values[-d_period:]) / d_period
        d_prev = (
            sum(k_values[-d_period - 1 : -1]) / d_period
            if len(k_values) >= d_period + 1
            else d_current
        )
        return {
            "k": round(k_current, 2),
            "d": round(d_current, 2),
            "k_prev": round(k_prev, 2),
            "d_prev": round(d_prev, 2),
            "overbought": k_current > 80,
            "oversold": k_current < 20,
            "bullish_cross": k_prev <= d_prev and k_current > d_current,
            "bearish_cross": k_prev >= d_prev and k_current < d_current,
            "zone": "overbought"
            if k_current > 80
            else ("oversold" if k_current < 20 else "neutral"),
        }

    @staticmethod
    def adx(candles: list, period: int = 14) -> dict | None:
        if len(candles) < period * 2 + 1:
            return None
        plus_dm_list, minus_dm_list, tr_list = [], [], []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_high = candles[i - 1].high
            prev_low = candles[i - 1].low
            prev_close = candles[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
            up_move = high - prev_high
            down_move = prev_low - low
            plus_dm_list.append(up_move if (up_move > down_move and up_move > 0) else 0)
            minus_dm_list.append(down_move if (down_move > up_move and down_move > 0) else 0)
        if len(tr_list) < period:
            return None
        atr_val = sum(tr_list[:period]) / period
        plus_di_smooth = sum(plus_dm_list[:period]) / period
        minus_di_smooth = sum(minus_dm_list[:period]) / period
        for i in range(period, len(tr_list)):
            atr_val = (atr_val * (period - 1) + tr_list[i]) / period
            plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm_list[i]) / period
            minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm_list[i]) / period
        if atr_val == 0:
            return None
        plus_di = (plus_di_smooth / atr_val) * 100
        minus_di = (minus_di_smooth / atr_val) * 100
        di_sum = plus_di + minus_di
        dx = abs(plus_di - minus_di) / di_sum * 100 if di_sum > 0 else 0
        return {
            "adx": round(dx, 2),
            "plus_di": round(plus_di, 2),
            "minus_di": round(minus_di, 2),
            "strong_trend": dx > 25,
            "very_strong": dx > 40,
            "weak_trend": dx < 20,
            "bullish": plus_di > minus_di,
            "bearish": minus_di > plus_di,
        }

    @staticmethod
    def vwap(candles: list, period: int = 20) -> dict | None:
        if len(candles) < period:
            return None
        recent = candles[-period:]
        total_volume = sum(c.volume for c in recent)
        total_vp = sum(((c.high + c.low + c.close) / 3) * c.volume for c in recent)
        if total_volume == 0:
            return None
        vwap_val = total_vp / total_volume
        current = candles[-1].close
        deviation = (current - vwap_val) / vwap_val * 100
        return {
            "vwap": round(vwap_val, 6),
            "price": current,
            "deviation_pct": round(deviation, 3),
            "above_vwap": current > vwap_val,
            "below_vwap": current < vwap_val,
        }

    @staticmethod
    def williams_r(candles: list, period: int = 14) -> float | None:
        if len(candles) < period:
            return None
        recent = candles[-period:]
        highest = max(c.high for c in recent)
        lowest = min(c.low for c in recent)
        close = candles[-1].close
        if highest == lowest:
            return -50.0
        return round((highest - close) / (highest - lowest) * -100, 2)

    @staticmethod
    def fibonacci(candles: list, lookback: int = 50) -> dict | None:
        if not candles or len(candles) < lookback:
            return None
        recent = candles[-lookback:]
        highs = [c.high for c in recent]
        lows = [c.low for c in recent]
        closes = [c.close for c in recent]
        current = closes[-1]
        swing_high = max(highs)
        swing_low = min(lows)
        if swing_high == swing_low:
            return None
        diff = swing_high - swing_low
        high_idx = highs.index(swing_high)
        low_idx = lows.index(swing_low)
        trend = "down" if low_idx > high_idx else "up"
        levels = {
            "0.236": swing_low + diff * 0.236,
            "0.382": swing_low + diff * 0.382,
            "0.500": swing_low + diff * 0.500,
            "0.618": swing_low + diff * 0.618,
            "0.786": swing_low + diff * 0.786,
        }
        extensions = {
            "1.272": swing_high + diff * 0.272,
            "1.618": swing_high + diff * 0.618,
        }
        fib_position = (current - swing_low) / diff if diff else 0
        support = max((lv for lv in levels.values() if lv < current), default=swing_low)
        resistance = min((lv for lv in levels.values() if lv > current), default=swing_high)
        return {
            "swing_high": round(swing_high, 6),
            "swing_low": round(swing_low, 6),
            "trend": trend,
            "levels": {k: round(v, 6) for k, v in levels.items()},
            "extensions": {k: round(v, 6) for k, v in extensions.items()},
            "fib_position": round(fib_position, 4),
            "support": round(support, 6),
            "resistance": round(resistance, 6),
            "range_pct": round(diff / swing_low * 100, 2),
        }

    @staticmethod
    def market_regime(candles: list, lookback: int = 50) -> dict | None:
        if len(candles) < lookback:
            return None
        closes = [c.close for c in candles[-lookback:]]
        recent_returns = [
            (closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))
        ]
        if len(recent_returns) < 20:
            return None
        recent_vol = statistics.stdev(recent_returns[-10:])
        hist_vol = statistics.stdev(recent_returns)
        vol_ratio = recent_vol / hist_vol if hist_vol > 0 else 1.0
        bb = TA.bollinger(closes, 20, 2.0)
        bb_width = bb["width"] if bb else 0
        adx_data = TA.adx(candles[-lookback:])
        adx_val = adx_data["adx"] if adx_data else 15
        if adx_val > 30 and vol_ratio < 1.5:
            regime = "TRENDING"
            confidence = min(0.95, adx_val / 50)
        elif bb_width < 2.0 and adx_val < 20:
            regime = "RANGING"
            confidence = min(0.95, (20 - adx_val) / 20)
        elif vol_ratio > 1.5 or bb_width > 5.0:
            regime = "VOLATILE"
            confidence = min(0.95, vol_ratio / 2)
        else:
            regime = "MIXED"
            confidence = 0.3
        return {
            "regime": regime,
            "confidence": round(confidence, 2),
            "adx": round(adx_val, 2),
            "bb_width": round(bb_width, 2),
            "vol_ratio": round(vol_ratio, 2),
        }


# ============================================
# API Endpoints
# ============================================


@app.get("/health")
def health():
    return ServiceHealth(
        service="indicators",
        status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={"calculations": calc_count},
    )


@app.post("/compute")
def compute_indicators(req: IndicatorRequest):
    """Compute all requested indicators from candle data"""
    global calc_count
    calc_count += 1

    candles = req.candles
    if not candles:
        raise HTTPException(status_code=400, detail="No candle data provided")

    closes = [c.close for c in candles]
    current = closes[-1] if closes else 0
    want_all = "all" in req.indicators

    result = IndicatorResult(pair=req.pair, current_price=current)

    if want_all or "sma" in req.indicators:
        result.sma_20 = TA.sma(closes, 20)
        result.sma_50 = TA.sma(closes, 50)
        result.sma_200 = TA.sma(closes, 200)

    if want_all or "ema" in req.indicators:
        result.ema_5 = TA.ema(closes, 5)
        result.ema_12 = TA.ema(closes, 12)
        result.ema_26 = TA.ema(closes, 26)

    if want_all or "rsi" in req.indicators:
        result.rsi = TA.rsi(closes)

    if want_all or "macd" in req.indicators:
        result.macd = TA.macd(closes)

    if want_all or "bollinger" in req.indicators:
        result.bollinger = TA.bollinger(closes)

    if want_all or "atr" in req.indicators:
        result.atr = TA.atr(candles)

    if want_all or "stochastic" in req.indicators:
        result.stochastic = TA.stochastic(candles)

    if want_all or "adx" in req.indicators:
        result.adx = TA.adx(candles)

    if want_all or "vwap" in req.indicators:
        result.vwap = TA.vwap(candles)

    if want_all or "williams_r" in req.indicators:
        result.williams_r = TA.williams_r(candles)

    if want_all or "momentum" in req.indicators:
        result.momentum = TA.momentum(closes)

    if want_all or "volume_trend" in req.indicators:
        result.volume_trend = TA.volume_trend(candles)

    if want_all or "fibonacci" in req.indicators:
        result.fibonacci = TA.fibonacci(candles)

    if want_all or "market_regime" in req.indicators:
        result.market_regime = TA.market_regime(candles)

    return result


@app.get("/metrics")
def prometheus_metrics():
    uptime = time.time() - START_TIME
    lines = [
        "# HELP rimuru_indicators_uptime_seconds Service uptime",
        "# TYPE rimuru_indicators_uptime_seconds gauge",
        f"rimuru_indicators_uptime_seconds {uptime:.1f}",
        "# HELP rimuru_indicators_calculations Total indicator calculations",
        "# TYPE rimuru_indicators_calculations counter",
        f"rimuru_indicators_calculations {calc_count}",
    ]
    return JSONResponse(content="\n".join(lines), media_type="text/plain")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8001"))
    logger.info("Rimuru Indicators Service starting on port %s", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
