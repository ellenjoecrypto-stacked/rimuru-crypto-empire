"""
Rimuru Crypto Empire — Backtester Service
Walk-forward backtesting engine with metrics: Sharpe, Sortino, Max Drawdown, Profit Factor.
"""

import os, sys, time, json, math, statistics, logging
from pathlib import Path
from datetime import datetime, timezone
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from shared.config import ServiceConfig
from shared.models import (
    BacktestRequest, BacktestResult, BacktestTrade,
    OHLCV, IndicatorRequest, ServiceHealth,
)
from shared.security import secure_app, get_auth_headers

logger = logging.getLogger("rimuru.backtester")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Backtester", version="2.0.0")
secure_app(app)
START_TIME = time.time()
test_count = 0

# Service URLs
DATA_URL = os.getenv("DATA_INGEST_URL", "http://data-ingest:8000")
INDICATOR_URL = os.getenv("INDICATORS_URL", "http://indicators:8001")


def _post_json(url, data, timeout=15):
    import urllib.request
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in get_auth_headers().items():
        req.add_header(k, v)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


def _get_json(url, timeout=10):
    import urllib.request
    req = urllib.request.Request(url)
    for k, v in get_auth_headers().items():
        req.add_header(k, v)
    resp = urllib.request.urlopen(req, timeout=timeout)
    return json.loads(resp.read().decode())


# --------------- Backtest Engine ---------------

class SimpleBacktester:
    """Walk-forward backtesting with configurable strategy rules"""

    def __init__(self, candles: List[OHLCV], capital: float = 100.0):
        self.candles = candles
        self.initial_capital = capital
        self.capital = capital
        self.position = None  # {entry_price, volume, entry_idx}
        self.trades: List[BacktestTrade] = []
        self.equity_curve: List[float] = [capital]

    def _rsi(self, closes, period=14):
        if len(closes) < period + 1:
            return None
        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas[-period:]]
        losses = [-d if d < 0 else 0 for d in deltas[-period:]]
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100
        return 100 - (100 / (1 + avg_gain / avg_loss))

    def _sma(self, prices, period):
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period

    def _ema(self, prices, period):
        if len(prices) < period:
            return None
        mul = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p - ema) * mul + ema
        return ema

    def _bollinger(self, prices, period=20, std_dev=2.0):
        if len(prices) < period:
            return None
        sma = sum(prices[-period:]) / period
        var = sum((p - sma)**2 for p in prices[-period:]) / period
        std = math.sqrt(var)
        return sma - std_dev * std, sma, sma + std_dev * std

    def run_rsi(self, buy_threshold=30, sell_threshold=70):
        """RSI strategy backtest"""
        closes = []
        for i, c in enumerate(self.candles):
            close = c.close if isinstance(c, OHLCV) else c["close"]
            closes.append(close)
            rsi = self._rsi(closes)
            if rsi is None:
                continue
            if self.position is None and rsi < buy_threshold:
                vol = (self.capital * 0.5) / close
                self.position = {"entry_price": close, "volume": vol, "entry_idx": i}
            elif self.position and rsi > sell_threshold:
                self._close_position(i, close, "rsi")
            self.equity_curve.append(self._equity(close))
        if self.position:
            self._close_position(len(self.candles)-1, closes[-1], "rsi")

    def run_ma_crossover(self, fast=50, slow=200):
        """MA crossover backtest"""
        closes = []
        for i, c in enumerate(self.candles):
            close = c.close if isinstance(c, OHLCV) else c["close"]
            closes.append(close)
            sma_f = self._sma(closes, fast)
            sma_s = self._sma(closes, slow)
            if sma_f is None or sma_s is None:
                continue
            if self.position is None and sma_f > sma_s:
                vol = (self.capital * 0.5) / close
                self.position = {"entry_price": close, "volume": vol, "entry_idx": i}
            elif self.position and sma_f < sma_s:
                self._close_position(i, close, "ma_crossover")
            self.equity_curve.append(self._equity(close))
        if self.position:
            self._close_position(len(self.candles)-1, closes[-1], "ma_crossover")

    def run_bollinger(self):
        """Bollinger band mean reversion backtest"""
        closes = []
        for i, c in enumerate(self.candles):
            close = c.close if isinstance(c, OHLCV) else c["close"]
            closes.append(close)
            bb = self._bollinger(closes)
            if bb is None:
                continue
            lower, mid, upper = bb
            if self.position is None and close < lower:
                vol = (self.capital * 0.5) / close
                self.position = {"entry_price": close, "volume": vol, "entry_idx": i}
            elif self.position and close > mid:
                self._close_position(i, close, "bollinger")
            self.equity_curve.append(self._equity(close))
        if self.position:
            self._close_position(len(self.candles)-1, closes[-1], "bollinger")

    def run_momentum(self, period=10):
        """Momentum strategy backtest"""
        closes = []
        for i, c in enumerate(self.candles):
            close = c.close if isinstance(c, OHLCV) else c["close"]
            closes.append(close)
            if len(closes) < period + 1:
                continue
            mom = (closes[-1] - closes[-period - 1]) / closes[-period - 1] * 100
            rsi = self._rsi(closes)
            if self.position is None and mom > 1.0 and (rsi and rsi < 65):
                vol = (self.capital * 0.5) / close
                self.position = {"entry_price": close, "volume": vol, "entry_idx": i}
            elif self.position and (mom < -0.5 or (rsi and rsi > 75)):
                self._close_position(i, close, "momentum")
            self.equity_curve.append(self._equity(close))
        if self.position:
            self._close_position(len(self.candles)-1, closes[-1], "momentum")

    def run_volume(self, surge_pct=50):
        """Volume surge strategy backtest"""
        volumes = []
        closes = []
        for i, c in enumerate(self.candles):
            close = c.close if isinstance(c, OHLCV) else c["close"]
            vol = c.volume if isinstance(c, OHLCV) else c["volume"]
            closes.append(close)
            volumes.append(vol)
            if len(volumes) < 20:
                continue
            avg_vol = sum(volumes[-20:-1]) / 19
            if avg_vol == 0:
                continue
            vol_ratio = (vol / avg_vol - 1) * 100
            mom = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0
            if self.position is None and vol_ratio > surge_pct and mom > 0:
                trade_vol = (self.capital * 0.5) / close
                self.position = {"entry_price": close, "volume": trade_vol, "entry_idx": i}
            elif self.position:
                pnl_pct = (close - self.position["entry_price"]) / self.position["entry_price"]
                if pnl_pct > 0.025 or pnl_pct < -0.02:
                    self._close_position(i, close, "volume")
            self.equity_curve.append(self._equity(close))
        if self.position:
            self._close_position(len(self.candles)-1, closes[-1], "volume")

    def _close_position(self, idx, price, strategy):
        if not self.position:
            return
        pnl_pct = (price - self.position["entry_price"]) / self.position["entry_price"]
        pnl_usd = (price - self.position["entry_price"]) * self.position["volume"]
        fee = abs(pnl_usd) * 0.0026 * 2  # entry + exit
        pnl_usd -= fee
        self.capital += pnl_usd
        self.trades.append(BacktestTrade(
            entry_time=str(self.position["entry_idx"]),
            exit_time=str(idx),
            pair="",
            side="long",
            entry_price=self.position["entry_price"],
            exit_price=price,
            volume=self.position["volume"],
            pnl_pct=round(pnl_pct * 100, 4),
            pnl_usd=round(pnl_usd, 4),
            strategy=strategy,
        ))
        self.position = None

    def _equity(self, current_price):
        eq = self.capital
        if self.position:
            eq += (current_price - self.position["entry_price"]) * self.position["volume"]
        return eq

    def results(self, strategy: str, pair: str) -> BacktestResult:
        wins = [t for t in self.trades if t.pnl_usd > 0]
        losses = [t for t in self.trades if t.pnl_usd <= 0]
        returns = [t.pnl_pct for t in self.trades]

        sharpe = 0.0
        sortino = 0.0
        if len(returns) > 1:
            mean_r = statistics.mean(returns)
            std_r = statistics.stdev(returns)
            if std_r > 0:
                sharpe = (mean_r / std_r) * math.sqrt(252)
            neg_returns = [r for r in returns if r < 0]
            if neg_returns:
                downside = statistics.stdev(neg_returns)
                if downside > 0:
                    sortino = (mean_r / downside) * math.sqrt(252)

        max_dd = 0
        peak = self.initial_capital
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd

        gross_profit = sum(t.pnl_usd for t in wins)
        gross_loss = abs(sum(t.pnl_usd for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0

        return BacktestResult(
            strategy=strategy,
            pair=pair,
            total_trades=len(self.trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            win_rate=len(wins) / len(self.trades) * 100 if self.trades else 0,
            total_pnl_pct=round((self.capital - self.initial_capital) / self.initial_capital * 100, 2),
            total_pnl_usd=round(self.capital - self.initial_capital, 2),
            sharpe_ratio=round(sharpe, 2),
            sortino_ratio=round(sortino, 2),
            max_drawdown=round(max_dd * 100, 2),
            profit_factor=round(profit_factor, 2),
            avg_win=round(statistics.mean([t.pnl_usd for t in wins]), 4) if wins else 0,
            avg_loss=round(statistics.mean([t.pnl_usd for t in losses]), 4) if losses else 0,
            trades=self.trades,
        )


# --------------- Endpoints ---------------

@app.get("/health")
def health():
    return ServiceHealth(
        service="backtester", status="healthy",
        uptime_seconds=round(time.time() - START_TIME, 1),
        details={"tests_run": test_count},
    )


@app.post("/backtest")
def run_backtest(req: BacktestRequest):
    global test_count
    test_count += 1

    # Fetch historical candles
    try:
        data = _get_json(f"{DATA_URL}/ohlc/{req.pair}?interval={req.interval}&count=720")
        candles = data.get("candles", []) if isinstance(data, dict) else []
        if not candles:
            raise HTTPException(status_code=400, detail="No candle data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data fetch error: {e}")

    # Convert to OHLCV
    ohlcv = [OHLCV(**c) if isinstance(c, dict) else c for c in candles]

    strategies_to_run = ["rsi", "ma_crossover", "bollinger", "momentum", "volume"]
    if req.strategy != "all":
        strategies_to_run = [req.strategy]

    results = []
    for strat in strategies_to_run:
        bt = SimpleBacktester(ohlcv, req.initial_capital)
        if strat == "rsi":
            bt.run_rsi()
        elif strat == "ma_crossover":
            bt.run_ma_crossover()
        elif strat == "bollinger":
            bt.run_bollinger()
        elif strat == "momentum":
            bt.run_momentum()
        elif strat == "volume":
            bt.run_volume()
        else:
            continue
        results.append(bt.results(strat, req.pair))

    return {"results": [r.model_dump() for r in results]}


@app.post("/walk-forward")
def walk_forward(req: BacktestRequest):
    """Walk-forward test: train on 70%, test on 30%"""
    global test_count
    test_count += 1

    try:
        data = _get_json(f"{DATA_URL}/ohlc/{req.pair}?interval={req.interval}&count=720")
        candles = data.get("candles", []) if isinstance(data, dict) else []
        if len(candles) < 100:
            raise HTTPException(status_code=400, detail="Need 100+ candles")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ohlcv = [OHLCV(**c) if isinstance(c, dict) else c for c in candles]
    split = int(len(ohlcv) * 0.7)
    train = ohlcv[:split]
    test = ohlcv[split:]

    results = {}
    for strat in ["rsi", "ma_crossover", "bollinger", "momentum", "volume"]:
        # Train
        bt_train = SimpleBacktester(train, req.initial_capital)
        getattr(bt_train, f"run_{strat}")()
        train_result = bt_train.results(strat, req.pair)

        # Test
        bt_test = SimpleBacktester(test, req.initial_capital)
        getattr(bt_test, f"run_{strat}")()
        test_result = bt_test.results(strat, req.pair)

        results[strat] = {
            "train": train_result.model_dump(),
            "test": test_result.model_dump(),
            "overfit_risk": "HIGH" if train_result.total_pnl_pct > 0 and test_result.total_pnl_pct < 0 else "LOW",
        }

    return {"pair": req.pair, "train_size": len(train), "test_size": len(test), "results": results}


@app.get("/metrics")
def metrics():
    return JSONResponse(
        content=f"rimuru_backtester_tests {test_count}\nrimuru_backtester_uptime {time.time()-START_TIME:.1f}",
        media_type="text/plain",
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8040"))
    logger.info(f"Rimuru Backtester starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
