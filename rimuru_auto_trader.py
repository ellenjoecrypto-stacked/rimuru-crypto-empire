"""
RIMURU AUTO-TRADER v2.0 — TRADE GOD EDITION
============================================
Autonomous Kraken Trading Engine powered by Trade God 1.0 intelligence.
Runs 24/7, scans markets, detects opportunities, executes trades.
Designed for small accounts ($25-100+) scaling to empire.

=== TRADE GOD STRATEGIES (7 engines) ===
1. Momentum Scalp          - EMA crossover + RSI + volume (5m)
2. Mean Reversion           - Bollinger Band bounces (15m)
3. Trend Following          - EMA20 + MACD + hourly confirmation (1h)
4. Fibonacci Retracement    - Golden ratio entries at 61.8%/50%/38.2% (15m+1h)
5. Golden Cross / Death Cross - 50/200 SMA crossover (1h)
6. Stochastic Reversal      - %K/%D oversold/overbought zones (15m)
7. Trade God Confluence      - ALL indicators weighted meta-strategy

=== ADVANCED FEATURES ===
- ATR-based dynamic stop-loss/take-profit (adapts to volatility)
- Kelly Criterion position sizing (optimal bet sizing)
- Market Regime Detection (trending/ranging/volatile)
- Crypto Fear & Greed Index (market sentiment via API)
- Performance Analytics (Sharpe, Sortino, Max Drawdown, Profit Factor)
- Self-Adapting Engine (learns which strategies win, adjusts weights)
- Portfolio rotation (sell weak, buy strong)
- Multi-timeframe analysis (5m/15m/1h)
- ADX trend strength filtering
- Williams %R momentum confirmation
- VWAP institutional level tracking

Usage:
  python rimuru_auto_trader.py              # Dry run (default safe mode)
  python rimuru_auto_trader.py --live       # LIVE trading with real money
  python rimuru_auto_trader.py --dry-run    # Paper trading (no real orders)
  python rimuru_auto_trader.py --aggressive # Lower thresholds, more trades
  python rimuru_auto_trader.py --status     # Show current status + analytics
"""

import os
import sys
import json
import time
import math
import signal
import hashlib
import hmac
import base64
import urllib.request
import urllib.parse
import logging
import traceback
import statistics
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

VERSION = "2.0.0-TRADE-GOD"

# ============================================
# Configuration
# ============================================

class Config:
    """All tunable parameters — Trade God Edition"""
    
    # === Scan Intervals ===
    SCAN_INTERVAL_SEC = 60           # Full market scan every 60s
    FAST_CHECK_SEC = 15              # Quick price check every 15s when in position
    HEARTBEAT_SEC = 300              # Status log every 5 min
    
    # === Risk Management ===
    MAX_POSITION_PCT = 0.80          # Max 80% of available USD in one trade
    MAX_DAILY_LOSS_PCT = 0.10        # Stop trading if down 10% today
    MAX_DRAWDOWN_PCT = 0.15          # Stop trading if down 15% from peak
    MAX_OPEN_POSITIONS = 3           # Max 3 concurrent positions
    MIN_TRADE_USD = 0.50             # Don't trade less than $0.50
    MAX_TRADE_USD = 50.00            # Cap per trade
    ENABLE_ROTATION = True           # Sell weak holdings to buy stronger ones
    USE_KELLY_SIZING = True          # Use Kelly Criterion for position sizing
    USE_ATR_STOPS = True             # Use ATR-based dynamic SL/TP
    ATR_SL_MULTIPLIER = 1.5          # Stop loss = ATR * this multiplier
    ATR_TP_MULTIPLIER = 2.5          # Take profit = ATR * this multiplier
    
    # === Strategy Thresholds ===
    MIN_CONFIDENCE = 0.55            # Minimum signal confidence to trade
    MIN_SPREAD_PCT = 0.001           # Skip pairs with spread > 0.5%
    MAX_SPREAD_PCT = 0.50
    
    # === Profit / Loss (fallback if ATR not available) ===
    TAKE_PROFIT_PCT = 0.025          # 2.5% take profit
    STOP_LOSS_PCT = 0.02             # 2% stop loss
    TRAILING_STOP_PCT = 0.015        # 1.5% trailing stop (activates after 1% profit)
    TRAILING_ACTIVATE_PCT = 0.01     # Activate trailing stop after 1% gain
    
    # === Cooldowns ===
    TRADE_COOLDOWN_SEC = 120         # Wait 2 min between trades
    LOSS_COOLDOWN_SEC = 600          # Wait 10 min after a loss
    ERROR_COOLDOWN_SEC = 120         # Wait 2 min after API error
    INSUFFICIENT_FUNDS_COOLDOWN = 300  # Wait 5 min after insufficient funds
    
    # === Strategy Weights (self-adapting baseline) ===
    STRATEGY_WEIGHTS = {
        'momentum': 1.0,
        'mean_rev': 1.0,
        'trend': 1.0,
        'fibonacci': 1.0,
        'golden_cross': 1.0,
        'stochastic': 1.0,
        'trade_god': 1.5,   # Meta-strategy gets higher base weight
    }
    
    # === Sentiment ===
    FEAR_GREED_ENABLED = True        # Fetch crypto fear & greed index
    FEAR_GREED_CACHE_SEC = 3600      # Cache for 1 hour
    
    # === Market Regime ===
    REGIME_LOOKBACK = 50             # Candles for regime detection
    
    # === Aggressive Mode Overrides ===
    AGGRESSIVE = {
        'MIN_CONFIDENCE': 0.40,
        'TAKE_PROFIT_PCT': 0.015,
        'STOP_LOSS_PCT': 0.025,
        'TRADE_COOLDOWN_SEC': 90,
        'MAX_POSITION_PCT': 0.50,
        'SCAN_INTERVAL_SEC': 45,
    }
    
    # === Pairs ===
    TRADEABLE_PAIRS = {
        'SOL':  'SOLUSD',
        'PEPE': 'PEPEUSD',
        'DOGE': 'XDGUSD',
        'BTC':  'XXBTZUSD',
        'ETH':  'XETHZUSD',
    }
    
    # Kraken minimum order sizes
    MIN_ORDER = {
        'SOLUSD':   0.05,
        'PEPEUSD':  100000,
        'XDGUSD':   50,
        'XXBTZUSD': 0.00005,
        'XETHZUSD': 0.004,
    }
    
    # Kraken asset name mapping
    ASSET_MAP = {
        'SOL': 'SOL', 'PEPE': 'PEPE', 'DOGE': 'XXDG',
        'BTC': 'XXBT', 'ETH': 'XETH',
    }
    
    REVERSE_MAP = {v: k for k, v in ASSET_MAP.items()}


# ============================================
# Logging Setup
# ============================================

def setup_logging(data_dir: Path):
    log_file = data_dir / f"auto_trader_{datetime.now().strftime('%Y%m%d')}.log"
    
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '\033[36m%(asctime)s\033[0m [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    console_handler.setLevel(logging.INFO)
    
    logger = logging.getLogger('rimuru')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


# ============================================
# Data Classes
# ============================================

class PositionStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"


@dataclass
class Position:
    pair: str
    side: str                   # 'long'
    entry_price: float
    volume: float
    entry_time: str
    strategy: str
    order_id: str = ''
    highest_price: float = 0    # For trailing stop
    current_price: float = 0
    pnl_pct: float = 0
    pnl_usd: float = 0
    status: str = 'open'
    exit_price: float = 0
    exit_time: str = ''
    exit_reason: str = ''
    
    def update(self, price: float):
        self.current_price = price
        if price > self.highest_price:
            self.highest_price = price
        self.pnl_pct = (price - self.entry_price) / self.entry_price
        self.pnl_usd = (price - self.entry_price) * self.volume


@dataclass
class DailyStats:
    date: str
    starting_balance: float = 0
    current_balance: float = 0
    peak_balance: float = 0
    trades_executed: int = 0
    trades_won: int = 0
    trades_lost: int = 0
    total_pnl_usd: float = 0
    total_fees_usd: float = 0
    largest_win: float = 0
    largest_loss: float = 0
    last_trade_time: str = ''


# ============================================
# Kraken Client (standalone)
# ============================================

class KrakenClient:
    BASE_URL = "https://api.kraken.com"
    
    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret
        self._call_count = 0
        self._last_call = 0
    
    def _rate_limit(self):
        """Respect Kraken rate limits"""
        elapsed = time.time() - self._last_call
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_call = time.time()
        self._call_count += 1
    
    def _sign(self, urlpath: str, data: dict) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode('utf-8')
        message = urlpath.encode('utf-8') + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode('utf-8')
    
    def _private(self, endpoint: str, data: dict = None) -> dict:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        if data is None:
            data = {}
        data['nonce'] = str(int(time.time() * 1000))
        
        sig = self._sign(endpoint, data)
        postdata = urllib.parse.urlencode(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=postdata, method='POST')
        req.add_header('API-Key', self.key)
        req.add_header('API-Sign', sig)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get('error'):
            raise Exception(f"Kraken API: {result['error']}")
        return result.get('result', {})
    
    def _public(self, endpoint: str, params: dict = None) -> dict:
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += '?' + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode())
        if result.get('error'):
            raise Exception(f"Kraken API: {result['error']}")
        return result.get('result', {})
    
    def balance(self) -> dict:
        return self._private('/0/private/Balance')
    
    def trade_balance(self) -> dict:
        return self._private('/0/private/TradeBalance', {'asset': 'ZUSD'})
    
    def open_orders(self) -> dict:
        result = self._private('/0/private/OpenOrders')
        return result.get('open', {})
    
    def ticker(self, pairs: list) -> dict:
        return self._public('/0/public/Ticker', {'pair': ','.join(pairs)})
    
    def ohlc(self, pair: str, interval: int = 5) -> list:
        result = self._public('/0/public/OHLC', {'pair': pair, 'interval': interval})
        for k, v in result.items():
            if isinstance(v, list):
                return v
        return []
    
    def orderbook(self, pair: str, count: int = 10) -> dict:
        result = self._public('/0/public/Depth', {'pair': pair, 'count': count})
        for k, v in result.items():
            if isinstance(v, dict):
                return v
        return {}
    
    def place_order(self, pair: str, side: str, order_type: str,
                    volume: float, price: float = None, validate: bool = False) -> dict:
        """Place an order. Returns full API result dict."""
        data = {
            'pair': pair,
            'type': side,
            'ordertype': order_type,
            'volume': str(volume),
        }
        if price is not None:
            data['price'] = str(price)
        if validate:
            data['validate'] = 'true'
        
        return self._private('/0/private/AddOrder', data)
    
    def cancel_order(self, txid: str) -> dict:
        return self._private('/0/private/CancelOrder', {'txid': txid})


# ============================================
# Technical Analysis
# ============================================

class TA:
    @staticmethod
    def sma(prices: list, period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    @staticmethod
    def ema(prices: list, period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    @staticmethod
    def rsi(prices: list, period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
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
        return (sma - std_dev * std, sma, sma + std_dev * std)
    
    @staticmethod
    def momentum(prices: list, period: int = 10) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        return (prices[-1] - prices[-period - 1]) / prices[-period - 1] * 100
    
    @staticmethod
    def atr(candles: list, period: int = 14) -> Optional[float]:
        """Average True Range from OHLC candles"""
        if len(candles) < period + 1:
            return None
        trs = []
        for i in range(1, len(candles)):
            high = float(candles[i][2])
            low = float(candles[i][3])
            prev_close = float(candles[i-1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period
    
    @staticmethod
    def volume_trend(candles: list, period: int = 10) -> Optional[float]:
        """Volume trend: positive = increasing, negative = decreasing"""
        if len(candles) < period * 2:
            return None
        recent_vol = sum(float(c[6]) for c in candles[-period:]) / period
        older_vol = sum(float(c[6]) for c in candles[-period*2:-period]) / period
        if older_vol == 0:
            return 0
        return (recent_vol - older_vol) / older_vol * 100
    
    @staticmethod
    def macd(prices: list, fast=12, slow=26, signal_period=9):
        """MACD indicator"""
        if len(prices) < slow + signal_period:
            return None
        
        fast_ema = TA.ema(prices, fast)
        slow_ema = TA.ema(prices, slow)
        if fast_ema is None or slow_ema is None:
            return None
        
        macd_line = fast_ema - slow_ema
        
        # Calculate MACD for signal line
        macd_values = []
        for i in range(slow, len(prices)):
            fe = TA.ema(prices[:i+1], fast)
            se = TA.ema(prices[:i+1], slow)
            if fe and se:
                macd_values.append(fe - se)
        
        signal_line = TA.ema(macd_values, signal_period) if len(macd_values) >= signal_period else None
        histogram = macd_line - signal_line if signal_line else None
        
        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}
    
    # ====== NEW TRADE GOD INDICATORS ======
    
    @staticmethod
    def stochastic(candles: list, k_period: int = 14, d_period: int = 3) -> Optional[dict]:
        """
        Stochastic Oscillator (%K and %D).
        %K = (Close - Lowest Low) / (Highest High - Lowest Low) * 100
        %D = SMA of %K (signal line)
        
        Overbought > 80, Oversold < 20
        BUY when %K crosses above %D below 20
        SELL when %K crosses below %D above 80
        """
        if len(candles) < k_period + d_period:
            return None
        
        k_values = []
        for i in range(k_period - 1, len(candles)):
            window = candles[i - k_period + 1:i + 1]
            highest = max(float(c[2]) for c in window)  # High
            lowest = min(float(c[3]) for c in window)    # Low
            close = float(candles[i][4])
            
            if highest == lowest:
                k_values.append(50.0)
            else:
                k_values.append((close - lowest) / (highest - lowest) * 100)
        
        if len(k_values) < d_period:
            return None
        
        # %D is SMA of %K
        k_current = k_values[-1]
        k_prev = k_values[-2] if len(k_values) >= 2 else k_current
        d_current = sum(k_values[-d_period:]) / d_period
        d_prev = sum(k_values[-d_period-1:-1]) / d_period if len(k_values) >= d_period + 1 else d_current
        
        # Detect crossovers
        k_crossed_above_d = k_prev <= d_prev and k_current > d_current
        k_crossed_below_d = k_prev >= d_prev and k_current < d_current
        
        return {
            'k': round(k_current, 2),
            'd': round(d_current, 2),
            'k_prev': round(k_prev, 2),
            'd_prev': round(d_prev, 2),
            'overbought': k_current > 80,
            'oversold': k_current < 20,
            'bullish_cross': k_crossed_above_d,
            'bearish_cross': k_crossed_below_d,
            'zone': 'overbought' if k_current > 80 else ('oversold' if k_current < 20 else 'neutral'),
        }
    
    @staticmethod
    def adx(candles: list, period: int = 14) -> Optional[dict]:
        """
        Average Directional Index — measures TREND STRENGTH (not direction).
        ADX > 25 = strong trend, ADX < 20 = weak/ranging
        +DI > -DI = bullish trend, -DI > +DI = bearish trend
        """
        if len(candles) < period * 2 + 1:
            return None
        
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []
        
        for i in range(1, len(candles)):
            high = float(candles[i][2])
            low = float(candles[i][3])
            prev_high = float(candles[i-1][2])
            prev_low = float(candles[i-1][3])
            prev_close = float(candles[i-1][4])
            
            # True Range
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
            
            # +DM and -DM
            up_move = high - prev_high
            down_move = prev_low - low
            
            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0
            
            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
        
        if len(tr_list) < period:
            return None
        
        # Smoothed averages using Wilder's method
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
        
        # ADX is smoothed DX (simplified: use the final DX value)
        adx_val = dx
        
        return {
            'adx': round(adx_val, 2),
            'plus_di': round(plus_di, 2),
            'minus_di': round(minus_di, 2),
            'strong_trend': adx_val > 25,
            'very_strong': adx_val > 40,
            'weak_trend': adx_val < 20,
            'bullish': plus_di > minus_di,
            'bearish': minus_di > plus_di,
        }
    
    @staticmethod
    def vwap(candles: list, period: int = 20) -> Optional[dict]:
        """
        Volume Weighted Average Price.
        Institutional reference level — price above VWAP = bullish, below = bearish.
        """
        if len(candles) < period:
            return None
        
        recent = candles[-period:]
        total_volume = 0
        total_vp = 0
        
        for c in recent:
            high = float(c[2])
            low = float(c[3])
            close = float(c[4])
            volume = float(c[6])
            
            typical_price = (high + low + close) / 3
            total_vp += typical_price * volume
            total_volume += volume
        
        if total_volume == 0:
            return None
        
        vwap_val = total_vp / total_volume
        current = float(candles[-1][4])
        deviation = (current - vwap_val) / vwap_val * 100
        
        return {
            'vwap': round(vwap_val, 6),
            'price': current,
            'deviation_pct': round(deviation, 3),
            'above_vwap': current > vwap_val,
            'below_vwap': current < vwap_val,
        }
    
    @staticmethod
    def williams_r(candles: list, period: int = 14) -> Optional[float]:
        """
        Williams %R: Similar to stochastic but inverted.
        Range: -100 to 0. Overbought > -20, Oversold < -80.
        """
        if len(candles) < period:
            return None
        
        recent = candles[-period:]
        highest = max(float(c[2]) for c in recent)
        lowest = min(float(c[3]) for c in recent)
        close = float(candles[-1][4])
        
        if highest == lowest:
            return -50.0
        
        return round((highest - close) / (highest - lowest) * -100, 2)
    
    @staticmethod
    def market_regime(candles: list, lookback: int = 50) -> Optional[dict]:
        """
        Detect market regime: TRENDING, RANGING, or VOLATILE.
        Uses ADX + Bollinger Band width + volatility ratio.
        """
        if len(candles) < lookback:
            return None
        
        closes = [float(c[4]) for c in candles[-lookback:]]
        
        # Volatility: ratio of recent vs historical
        recent_returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes))]
        if len(recent_returns) < 20:
            return None
        
        recent_vol = statistics.stdev(recent_returns[-10:]) if len(recent_returns) >= 10 else 0
        hist_vol = statistics.stdev(recent_returns) if len(recent_returns) >= 2 else 0
        vol_ratio = recent_vol / hist_vol if hist_vol > 0 else 1.0
        
        # Bollinger Band width (proxy for range vs trend)
        bb = TA.bollinger(closes, 20, 2.0)
        bb_width = 0
        if bb:
            lower, mid, upper = bb
            bb_width = (upper - lower) / mid * 100 if mid > 0 else 0
        
        # ADX for trend strength
        adx_data = TA.adx(candles[-lookback:])
        adx_val = adx_data['adx'] if adx_data else 15
        
        # Determine regime
        if adx_val > 30 and vol_ratio < 1.5:
            regime = 'TRENDING'
            confidence = min(0.95, adx_val / 50)
        elif bb_width < 2.0 and adx_val < 20:
            regime = 'RANGING'
            confidence = min(0.95, (20 - adx_val) / 20)
        elif vol_ratio > 1.5 or bb_width > 5.0:
            regime = 'VOLATILE'
            confidence = min(0.95, vol_ratio / 2)
        else:
            regime = 'MIXED'
            confidence = 0.3
        
        # Best strategies per regime
        best_strategies = {
            'TRENDING': ['trend', 'golden_cross', 'momentum'],
            'RANGING': ['mean_rev', 'stochastic', 'fibonacci'],
            'VOLATILE': ['fibonacci', 'mean_rev'],
            'MIXED': ['trade_god'],
        }
        
        return {
            'regime': regime,
            'confidence': round(confidence, 2),
            'adx': round(adx_val, 2),
            'bb_width': round(bb_width, 2),
            'vol_ratio': round(vol_ratio, 2),
            'recent_vol': round(recent_vol * 100, 3),
            'best_strategies': best_strategies.get(regime, []),
        }
    
    @staticmethod
    def fibonacci(candles: list, lookback: int = 50) -> Optional[dict]:
        """
        Fibonacci Retracement & Extension levels.
        Finds the most recent significant swing high/low and calculates levels.
        
        Returns dict with:
          - swing_high, swing_low
          - retracement levels: 0.236, 0.382, 0.500, 0.618, 0.786
          - extension levels: 1.272, 1.618, 2.618
          - current_zone: which fib zone price is in
          - trend: 'up' (measuring pullback from rally) or 'down' (measuring bounce from drop)
        """
        if not candles or len(candles) < lookback:
            return None
        
        recent = candles[-lookback:]
        highs = [float(c[2]) for c in recent]
        lows = [float(c[3]) for c in recent]
        closes = [float(c[4]) for c in recent]
        current = closes[-1]
        
        # Find swing high and swing low positions
        swing_high = max(highs)
        swing_low = min(lows)
        high_idx = highs.index(swing_high)
        low_idx = lows.index(swing_low)
        
        if swing_high == swing_low:
            return None
        
        diff = swing_high - swing_low
        
        # Determine trend direction:
        # If high came BEFORE low → downtrend (we measure bounce from bottom)
        # If low came BEFORE high → uptrend (we measure pullback from top)
        if low_idx > high_idx:
            # Downtrend: high first, then dropped. Fib from top down.
            trend = 'down'
            levels = {
                '0.000': swing_low,      # Bottom (0%)
                '0.236': swing_low + diff * 0.236,
                '0.382': swing_low + diff * 0.382,
                '0.500': swing_low + diff * 0.500,
                '0.618': swing_low + diff * 0.618,
                '0.786': swing_low + diff * 0.786,
                '1.000': swing_high,     # Top (100%)
            }
            extensions = {
                '1.272': swing_high + diff * 0.272,
                '1.618': swing_high + diff * 0.618,
                '2.618': swing_high + diff * 1.618,
            }
        else:
            # Uptrend: low first, then rallied. Fib retracement from top.
            trend = 'up'
            levels = {
                '1.000': swing_high,     # Top (100%)
                '0.786': swing_high - diff * 0.214,
                '0.618': swing_high - diff * 0.382,
                '0.500': swing_high - diff * 0.500,
                '0.382': swing_high - diff * 0.618,
                '0.236': swing_high - diff * 0.764,
                '0.000': swing_low,      # Bottom (0%)
            }
            extensions = {
                '1.272': swing_high + diff * 0.272,
                '1.618': swing_high + diff * 0.618,
                '2.618': swing_high + diff * 1.618,
            }
        
        # Determine which zone the current price is in
        fib_ratios = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        if trend == 'up':
            # In uptrend, price position relative to retracement
            if current >= swing_high:
                zone = 'above_high'
                fib_position = 1.0 + (current - swing_high) / diff
            elif current <= swing_low:
                zone = 'below_low'
                fib_position = 0
            else:
                fib_position = (current - swing_low) / diff
                if fib_position > 0.786:
                    zone = 'near_high'
                elif fib_position > 0.618:
                    zone = '618_786'   # Between golden ratio and 78.6%
                elif fib_position > 0.5:
                    zone = '500_618'   # Between 50% and golden ratio
                elif fib_position > 0.382:
                    zone = '382_500'   # Key reversal zone
                elif fib_position > 0.236:
                    zone = '236_382'
                else:
                    zone = 'near_low'
        else:
            # Downtrend bounce
            fib_position = (current - swing_low) / diff if diff > 0 else 0
            if fib_position < 0.236:
                zone = 'near_low'
            elif fib_position < 0.382:
                zone = '236_382'
            elif fib_position < 0.5:
                zone = '382_500'
            elif fib_position < 0.618:
                zone = '500_618'
            elif fib_position < 0.786:
                zone = '618_786'
            else:
                zone = 'near_high'
        
        # Find nearest support and resistance fib levels
        all_levels = sorted(levels.values())
        support = max((l for l in all_levels if l < current), default=swing_low)
        resistance = min((l for l in all_levels if l > current), default=swing_high)
        
        return {
            'swing_high': round(swing_high, 6),
            'swing_low': round(swing_low, 6),
            'trend': trend,
            'levels': {k: round(v, 6) for k, v in levels.items()},
            'extensions': {k: round(v, 6) for k, v in extensions.items()},
            'zone': zone,
            'fib_position': round(fib_position, 4),
            'support': round(support, 6),
            'resistance': round(resistance, 6),
            'range_pct': round(diff / swing_low * 100, 2),  # Range as % of low
        }


# ============================================
# Signal Generator
# ============================================

@dataclass
class Signal:
    pair: str
    action: str          # 'buy', 'sell', 'hold'
    confidence: float    # 0-1
    reason: str
    strategy: str
    price: float = 0
    suggested_volume: float = 0
    stop_loss: float = 0
    take_profit: float = 0

class SignalEngine:
    """Generates trading signals from multi-strategy analysis — Trade God Edition"""
    
    def __init__(self, config: Config, strategy_weights: dict = None):
        self.config = config
        self.strategy_weights = strategy_weights or dict(Config.STRATEGY_WEIGHTS)
        self.fear_greed_cache = {'value': 50, 'label': 'neutral', 'timestamp': 0}
        self.market_regimes = {}  # Cache per pair
    
    def analyze(self, pair: str, candles_5m: list, candles_15m: list,
                candles_1h: list, available_usd: float, 
                existing_positions: List[Position]) -> Signal:
        """
        Multi-timeframe, multi-strategy analysis.
        Returns the strongest signal.
        """
        closes_5m = [float(c[4]) for c in candles_5m] if candles_5m else []
        closes_15m = [float(c[4]) for c in candles_15m] if candles_15m else []
        closes_1h = [float(c[4]) for c in candles_1h] if candles_1h else []
        
        current = closes_5m[-1] if closes_5m else 0
        if not current:
            return Signal(pair=pair, action='hold', confidence=0,
                         reason='No price data', strategy='none')
        
        signals = []
        
        # Strategy 1: Momentum Scalp (5m timeframe)
        if len(closes_5m) >= 20:
            signals.append(self._momentum_signal(pair, closes_5m, candles_5m, current, available_usd))
        
        # Strategy 2: Mean Reversion (15m timeframe)
        if len(closes_15m) >= 20:
            signals.append(self._mean_reversion_signal(pair, closes_15m, current, available_usd))
        
        # Strategy 3: Trend Following (1h for confirmation)
        if len(closes_1h) >= 30:
            signals.append(self._trend_signal(pair, closes_1h, candles_1h, current, available_usd))
        
        # Strategy 4: Fibonacci Retracement (15m + 1h)
        if len(candles_15m) >= 50:
            fib_sig = self._fibonacci_signal(pair, candles_15m, candles_1h, current, available_usd)
            if fib_sig:
                signals.append(fib_sig)
        
        # Strategy 5: Golden Cross / Death Cross (1h SMA 50/200)
        if len(closes_1h) >= 200:
            signals.append(self._golden_cross_signal(pair, closes_1h, candles_1h, current, available_usd))
        
        # Strategy 6: Stochastic Reversal (15m)
        if len(candles_15m) >= 20:
            signals.append(self._stochastic_signal(pair, candles_15m, closes_15m, current, available_usd))
        
        # Strategy 7: Trade God Confluence (meta-strategy, ALL indicators)
        if len(candles_15m) >= 30 and len(candles_1h) >= 30:
            god_sig = self._trade_god_confluence(pair, candles_5m, candles_15m, candles_1h, current, available_usd)
            if god_sig:
                signals.append(god_sig)
        
        # Apply strategy weights to confidence scores
        for s in signals:
            weight = self.strategy_weights.get(s.strategy, 1.0)
            s.confidence *= weight
            s.confidence = min(0.99, s.confidence)  # Cap at 99%
        
        # Filter to actionable signals
        actionable = [s for s in signals if s.action in ('buy', 'sell') and s.confidence >= self.config.MIN_CONFIDENCE]
        
        if not actionable:
            reasons = [f"{s.strategy}: {s.reason}" for s in signals]
            return Signal(pair=pair, action='hold', confidence=0,
                         reason=' | '.join(reasons) or 'No signal', strategy='multi')
        
        # Return highest confidence signal
        best = max(actionable, key=lambda s: s.confidence)
        
        # Apply position sizing (Kelly Criterion if enabled)
        if best.action == 'buy':
            if self.config.USE_KELLY_SIZING:
                max_usd = self._kelly_size(available_usd, best.confidence)
            else:
                max_usd = min(available_usd * self.config.MAX_POSITION_PCT, self.config.MAX_TRADE_USD)
            
            if max_usd < self.config.MIN_TRADE_USD:
                return Signal(pair=pair, action='hold', confidence=0,
                             reason=f'Insufficient funds (${max_usd:.2f})', strategy='multi')
            
            best.suggested_volume = max_usd / current
            min_vol = Config.MIN_ORDER.get(pair, 0)
            if best.suggested_volume < min_vol:
                return Signal(pair=pair, action='hold', confidence=0,
                             reason=f'Below minimum order ({best.suggested_volume:.8f} < {min_vol})',
                             strategy='multi')
        
        # Set ATR-based dynamic stop loss and take profit
        if best.stop_loss == 0 or best.take_profit == 0:  # Only if strategy didn't set custom levels
            if self.config.USE_ATR_STOPS and candles_15m:
                atr = TA.atr(candles_15m)
                if atr and atr > 0:
                    best.stop_loss = current - (atr * self.config.ATR_SL_MULTIPLIER)
                    best.take_profit = current + (atr * self.config.ATR_TP_MULTIPLIER)
                else:
                    best.stop_loss = current * (1 - self.config.STOP_LOSS_PCT)
                    best.take_profit = current * (1 + self.config.TAKE_PROFIT_PCT)
            else:
                best.stop_loss = current * (1 - self.config.STOP_LOSS_PCT)
                best.take_profit = current * (1 + self.config.TAKE_PROFIT_PCT)
        best.price = current
        
        return best
    
    def _momentum_signal(self, pair, closes, candles, current, available_usd) -> Signal:
        ema_fast = TA.ema(closes, 5)
        ema_slow = TA.ema(closes, 15)
        rsi = TA.rsi(closes)
        mom = TA.momentum(closes, 5)
        vol_trend = TA.volume_trend(candles, 5)
        atr = TA.atr(candles)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='momentum', price=current)
        
        if not all([ema_fast, ema_slow, rsi]):
            sig.reason = 'Insufficient data'
            return sig
        
        score = 0
        reasons = []
        
        # EMA crossover
        if ema_fast > ema_slow:
            ema_spread = (ema_fast - ema_slow) / ema_slow * 100
            if ema_spread > 0.1:
                score += 0.25
                reasons.append(f'EMA bull +{ema_spread:.2f}%')
        else:
            ema_spread = (ema_slow - ema_fast) / ema_slow * 100
            if ema_spread > 0.2:
                score -= 0.3
                reasons.append(f'EMA bear -{ema_spread:.2f}%')
        
        # RSI
        if rsi < 30:
            score += 0.3
            reasons.append(f'RSI oversold {rsi:.0f}')
        elif rsi < 40:
            score += 0.15
            reasons.append(f'RSI low {rsi:.0f}')
        elif rsi > 75:
            score -= 0.3
            reasons.append(f'RSI overbought {rsi:.0f}')
        elif rsi > 65:
            score -= 0.1
            reasons.append(f'RSI high {rsi:.0f}')
        
        # Momentum
        if mom and mom > 0.5:
            score += 0.2
            reasons.append(f'Mom +{mom:.1f}%')
        elif mom and mom < -0.5:
            score -= 0.15
            reasons.append(f'Mom {mom:.1f}%')
        
        # Volume confirmation
        if vol_trend and vol_trend > 20:
            score += 0.15
            reasons.append(f'Vol up {vol_trend:.0f}%')
        
        if score > 0:
            sig.action = 'buy'
            sig.confidence = min(0.95, score)
        elif score < -0.3:
            sig.action = 'sell'
            sig.confidence = min(0.95, abs(score))
        
        sig.reason = ', '.join(reasons) or 'No momentum signal'
        return sig
    
    def _mean_reversion_signal(self, pair, closes, current, available_usd) -> Signal:
        bb = TA.bollinger(closes)
        rsi = TA.rsi(closes)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='mean_rev', price=current)
        
        if not bb or not rsi:
            sig.reason = 'Insufficient data'
            return sig
        
        lower, mid, upper = bb
        bb_width = (upper - lower) / mid * 100
        
        # Price at lower band + oversold RSI = buy
        if current <= lower * 1.005 and rsi < 35:
            sig.action = 'buy'
            sig.confidence = min(0.85, 0.4 + (35 - rsi) / 50 + (lower - current) / lower * 10)
            sig.reason = f'At lower BB ({lower:.4f}), RSI={rsi:.0f}, width={bb_width:.1f}%'
        elif current >= upper * 0.995 and rsi > 70:
            sig.action = 'sell'
            sig.confidence = 0.7
            sig.reason = f'At upper BB ({upper:.4f}), RSI={rsi:.0f}'
        else:
            bb_pos = (current - lower) / (upper - lower) * 100 if upper != lower else 50
            sig.reason = f'BB pos {bb_pos:.0f}%, RSI={rsi:.0f}'
        
        return sig
    
    def _trend_signal(self, pair, closes, candles, current, available_usd) -> Signal:
        """Hourly trend confirmation"""
        ema_20 = TA.ema(closes, 20)
        rsi = TA.rsi(closes)
        macd = TA.macd(closes)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='trend', price=current)
        
        if not ema_20 or not rsi:
            sig.reason = 'Insufficient data'
            return sig
        
        score = 0
        reasons = []
        
        # Price above/below 20 EMA
        if current > ema_20:
            dist = (current - ema_20) / ema_20 * 100
            if dist < 3:  # Not too extended
                score += 0.2
                reasons.append(f'Above EMA20 +{dist:.1f}%')
        else:
            dist = (ema_20 - current) / ema_20 * 100
            if dist > 2:
                score -= 0.2
                reasons.append(f'Below EMA20 -{dist:.1f}%')
        
        # MACD
        if macd and macd.get('histogram'):
            if macd['histogram'] > 0:
                score += 0.2
                reasons.append('MACD bull')
            else:
                score -= 0.15
                reasons.append('MACD bear')
        
        # RSI trend
        if rsi < 40:
            score += 0.2
            reasons.append(f'H1 RSI {rsi:.0f}')
        elif rsi > 65:
            score -= 0.15
            reasons.append(f'H1 RSI {rsi:.0f}')
        
        if score >= 0.3:
            sig.action = 'buy'
            sig.confidence = min(0.9, score)
        elif score <= -0.3:
            sig.action = 'sell'
            sig.confidence = min(0.9, abs(score))
        
        sig.reason = ', '.join(reasons) or 'No trend signal'
        return sig
    
    def _fibonacci_signal(self, pair, candles_15m, candles_1h, current, available_usd) -> Optional[Signal]:
        """
        Fibonacci Strategy:
        - Buy at 61.8% retracement (golden ratio) in uptrend with RSI confirmation
        - Buy at 50% retracement with strong momentum confirmation  
        - Buy at 38.2% retracement only with very strong confluence
        - Enhanced stops/targets using fib extensions
        """
        fib_15m = TA.fibonacci(candles_15m, 50)
        fib_1h = TA.fibonacci(candles_1h, 50) if candles_1h and len(candles_1h) >= 50 else None
        
        if not fib_15m:
            return None
        
        closes_15m = [float(c[4]) for c in candles_15m]
        rsi = TA.rsi(closes_15m)
        mom = TA.momentum(closes_15m, 5)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='fibonacci', price=current)
        
        if not rsi:
            return sig
        
        score = 0
        reasons = []
        zone = fib_15m['zone']
        trend = fib_15m['trend']
        fib_pos = fib_15m['fib_position']
        support = fib_15m['support']
        resistance = fib_15m['resistance']
        range_pct = fib_15m['range_pct']
        
        # Need decent range to trade fib (at least 1% swing)
        if range_pct < 1.0:
            sig.reason = f'Fib range too small ({range_pct:.1f}%)'
            return sig
        
        reasons.append(f'Fib {zone} ({fib_pos:.2f})')
        
        if trend == 'up':
            # UPTREND: looking for pullback entries
            
            # Golden ratio zone (0.618) — highest probability
            if 0.58 <= fib_pos <= 0.66:
                score += 0.40
                reasons.append('AT GOLDEN RATIO 61.8%')
                if rsi < 40:
                    score += 0.25
                    reasons.append(f'RSI confirms {rsi:.0f}')
                elif rsi < 50:
                    score += 0.10
                
                # Set targets using fib extensions
                sig.take_profit = fib_15m['extensions'].get('1.272', resistance)
                sig.stop_loss = fib_15m['levels'].get('0.236', support * 0.98)
            
            # 50% retracement — good with confirmation
            elif 0.46 <= fib_pos <= 0.54:
                score += 0.30
                reasons.append('AT 50% LEVEL')
                if rsi < 40:
                    score += 0.20
                    reasons.append(f'RSI {rsi:.0f}')
                if mom and mom > 0:
                    score += 0.10
                    reasons.append(f'Mom reversing +{mom:.1f}%')
                
                sig.take_profit = fib_15m['levels'].get('1.000', resistance)
                sig.stop_loss = fib_15m['levels'].get('0.382', support * 0.98)
            
            # 38.2% retracement — shallow, need strong confluence
            elif 0.35 <= fib_pos <= 0.42:
                score += 0.20
                reasons.append('AT 38.2%')
                if rsi < 35:
                    score += 0.20
                    reasons.append(f'RSI oversold {rsi:.0f}')
                if mom and mom > 0.5:
                    score += 0.15
                    reasons.append(f'Strong mom +{mom:.1f}%')
                
                sig.take_profit = fib_15m['levels'].get('0.786', resistance)
                sig.stop_loss = fib_15m['levels'].get('0.236', support * 0.98)
            
            # Near the high — sell signal
            elif fib_pos > 0.9:
                score -= 0.25
                reasons.append('Near swing high')
                if rsi > 70:
                    score -= 0.20
                    reasons.append(f'Overbought RSI {rsi:.0f}')
            
        else:
            # DOWNTREND: looking for bounce plays (riskier)
            
            # Price near swing low with oversold RSI — bounce play
            if fib_pos < 0.15 and rsi < 30:
                score += 0.30
                reasons.append(f'Bounce play near low, RSI={rsi:.0f}')
                sig.take_profit = fib_15m['levels'].get('0.382', resistance)
                sig.stop_loss = fib_15m['swing_low'] * 0.98
            
            # 23.6% bounce in downtrend
            elif 0.20 <= fib_pos <= 0.28 and rsi < 35:
                score += 0.20
                reasons.append(f'23.6% bounce, RSI={rsi:.0f}')
                sig.take_profit = fib_15m['levels'].get('0.382', resistance)
                sig.stop_loss = fib_15m['swing_low'] * 0.985
        
        # Higher timeframe confluence (1h fib)
        if fib_1h and score > 0:
            h1_zone = fib_1h['zone']
            h1_trend = fib_1h['trend']
            if h1_trend == 'up' and h1_zone in ('382_500', '500_618', '618_786'):
                score += 0.15
                reasons.append(f'H1 fib confluence ({h1_zone})')
            elif h1_trend == 'down' and h1_zone in ('near_high', '618_786'):
                score -= 0.10
                reasons.append(f'H1 downtrend caution')
        
        if score > 0:
            sig.action = 'buy'
            sig.confidence = min(0.95, score)
        elif score < -0.3:
            sig.action = 'sell'
            sig.confidence = min(0.95, abs(score))
        
        sig.reason = ', '.join(reasons)
        return sig
    
    # ====== TRADE GOD NEW STRATEGIES ======
    
    def _golden_cross_signal(self, pair, closes, candles, current, available_usd) -> Signal:
        """
        Strategy 5: Golden Cross / Death Cross (50/200 SMA).
        The most reliable long-term trend signal in trading history.
        Golden Cross (50 SMA > 200 SMA) = strong bullish
        Death Cross (50 SMA < 200 SMA) = strong bearish
        """
        sma_50 = TA.sma(closes, 50)
        sma_200 = TA.sma(closes, 200)
        rsi = TA.rsi(closes)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='golden_cross', price=current)
        
        if not sma_50 or not sma_200 or not rsi:
            sig.reason = 'Need 200+ candles'
            return sig
        
        score = 0
        reasons = []
        
        # Check for recent crossover (look at previous values)
        prev_closes = closes[:-1]
        prev_sma_50 = TA.sma(prev_closes, 50)
        prev_sma_200 = TA.sma(prev_closes, 200)
        
        if prev_sma_50 and prev_sma_200:
            # Fresh Golden Cross
            if prev_sma_50 <= prev_sma_200 and sma_50 > sma_200:
                score += 0.60
                reasons.append('GOLDEN CROSS! SMA50 crossed above SMA200')
            # Fresh Death Cross
            elif prev_sma_50 >= prev_sma_200 and sma_50 < sma_200:
                score -= 0.60
                reasons.append('DEATH CROSS! SMA50 crossed below SMA200')
            # Already in golden cross territory
            elif sma_50 > sma_200:
                spread = (sma_50 - sma_200) / sma_200 * 100
                if spread > 0.5 and current > sma_50:
                    score += 0.30
                    reasons.append(f'Golden zone, SMA50 +{spread:.1f}% above SMA200')
                elif current < sma_50 and current > sma_200:
                    score += 0.20
                    reasons.append(f'Pullback to SMA50 in golden zone')
            # In death cross territory
            elif sma_50 < sma_200:
                score -= 0.25
                reasons.append(f'Death cross active')
        
        # RSI confirmation
        if score > 0 and rsi < 40:
            score += 0.15
            reasons.append(f'RSI oversold {rsi:.0f}')
        elif score > 0 and rsi > 75:
            score -= 0.10
            reasons.append(f'RSI overbought {rsi:.0f}')
        
        # Price above both SMAs = extra confidence
        if current > sma_50 > sma_200:
            score += 0.10
            reasons.append('Price > SMA50 > SMA200')
        
        if score > 0:
            sig.action = 'buy'
            sig.confidence = min(0.95, score)
        elif score < -0.3:
            sig.action = 'sell'
            sig.confidence = min(0.95, abs(score))
        
        sig.reason = ', '.join(reasons) or 'No golden cross signal'
        return sig
    
    def _stochastic_signal(self, pair, candles, closes, current, available_usd) -> Signal:
        """
        Strategy 6: Stochastic Oscillator Reversal.
        Buy when %K crosses above %D in oversold zone (<20).
        Sell when %K crosses below %D in overbought zone (>80).
        """
        stoch = TA.stochastic(candles)
        rsi = TA.rsi(closes)
        
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='stochastic', price=current)
        
        if not stoch or not rsi:
            sig.reason = 'Insufficient data'
            return sig
        
        score = 0
        reasons = []
        
        k, d = stoch['k'], stoch['d']
        reasons.append(f'Stoch %K={k:.0f} %D={d:.0f}')
        
        # Bullish crossover in oversold zone — strongest signal
        if stoch['bullish_cross'] and stoch['oversold']:
            score += 0.55
            reasons.append('BULLISH CROSS in oversold!')
        # Bullish crossover in neutral zone
        elif stoch['bullish_cross'] and k < 50:
            score += 0.25
            reasons.append('Bullish cross below 50')
        # Oversold but no cross yet
        elif stoch['oversold']:
            score += 0.15
            reasons.append('Oversold, waiting for cross')
        
        # Bearish crossover in overbought zone
        if stoch['bearish_cross'] and stoch['overbought']:
            score -= 0.50
            reasons.append('BEARISH CROSS in overbought!')
        elif stoch['overbought']:
            score -= 0.20
            reasons.append('Overbought')
        
        # RSI confluence
        if score > 0 and rsi and rsi < 35:
            score += 0.20
            reasons.append(f'RSI confirms oversold {rsi:.0f}')
        elif score < 0 and rsi and rsi > 70:
            score += -0.15  # Make more negative
            reasons.append(f'RSI confirms overbought {rsi:.0f}')
        
        if score > 0:
            sig.action = 'buy'
            sig.confidence = min(0.95, score)
        elif score < -0.3:
            sig.action = 'sell'
            sig.confidence = min(0.95, abs(score))
        
        sig.reason = ', '.join(reasons)
        return sig
    
    def _trade_god_confluence(self, pair, candles_5m, candles_15m, candles_1h,
                              current, available_usd) -> Optional[Signal]:
        """
        Strategy 7: TRADE GOD CONFLUENCE — The Ultimate Meta-Strategy.
        Combines ALL indicators with weighted scoring.
        Only fires when multiple independent signals agree.
        This is the pinnacle of the Trade God 1.0 system.
        """
        sig = Signal(pair=pair, action='hold', confidence=0, reason='',
                    strategy='trade_god', price=current)
        
        closes_15m = [float(c[4]) for c in candles_15m] if candles_15m else []
        closes_1h = [float(c[4]) for c in candles_1h] if candles_1h else []
        
        if len(closes_15m) < 30:
            return None
        
        bull_score = 0
        bear_score = 0
        confluence_count = 0
        reasons = []
        
        # 1. RSI (weight: 15%)
        rsi = TA.rsi(closes_15m)
        if rsi:
            if rsi < 30:
                bull_score += 0.15
                confluence_count += 1
                reasons.append(f'RSI oversold {rsi:.0f}')
            elif rsi < 40:
                bull_score += 0.08
                confluence_count += 1
            elif rsi > 70:
                bear_score += 0.15
                confluence_count += 1
                reasons.append(f'RSI overbought {rsi:.0f}')
            elif rsi > 60:
                bear_score += 0.05
        
        # 2. Bollinger Bands (weight: 15%)
        bb = TA.bollinger(closes_15m)
        if bb:
            lower, mid, upper = bb
            if current <= lower * 1.005:
                bull_score += 0.15
                confluence_count += 1
                reasons.append('At lower BB')
            elif current >= upper * 0.995:
                bear_score += 0.15
                confluence_count += 1
                reasons.append('At upper BB')
        
        # 3. MACD (weight: 12%)
        macd = TA.macd(closes_15m)
        if macd:
            if macd.get('histogram') and macd['histogram'] > 0:
                bull_score += 0.12
                confluence_count += 1
                reasons.append('MACD bullish')
            elif macd.get('histogram') and macd['histogram'] < 0:
                bear_score += 0.12
                confluence_count += 1
        
        # 4. Stochastic (weight: 12%)
        stoch = TA.stochastic(candles_15m)
        if stoch:
            if stoch['oversold'] and stoch['bullish_cross']:
                bull_score += 0.12
                confluence_count += 1
                reasons.append('Stoch bull cross oversold')
            elif stoch['overbought'] and stoch['bearish_cross']:
                bear_score += 0.12
                confluence_count += 1
                reasons.append('Stoch bear cross overbought')
            elif stoch['oversold']:
                bull_score += 0.06
                confluence_count += 1
        
        # 5. EMA trend (weight: 12%)
        ema_fast = TA.ema(closes_15m, 8)
        ema_slow = TA.ema(closes_15m, 21)
        if ema_fast and ema_slow:
            if ema_fast > ema_slow:
                bull_score += 0.12
                confluence_count += 1
                reasons.append('EMA8 > EMA21')
            else:
                bear_score += 0.12
                confluence_count += 1
        
        # 6. Volume (weight: 10%)
        vol_trend = TA.volume_trend(candles_15m, 5)
        if vol_trend and vol_trend > 20:
            if bull_score > bear_score:
                bull_score += 0.10
                confluence_count += 1
                reasons.append(f'Vol rising +{vol_trend:.0f}%')
        
        # 7. Fibonacci (weight: 10%)
        fib = TA.fibonacci(candles_15m, 50)
        if fib:
            if fib['zone'] in ('500_618', '618_786') and fib['trend'] == 'up':
                bull_score += 0.10
                confluence_count += 1
                reasons.append(f'Fib golden zone {fib["fib_position"]:.2f}')
            elif fib['zone'] == 'near_high' and fib['trend'] == 'up':
                bear_score += 0.08
                reasons.append('Fib near high')
        
        # 8. VWAP (weight: 7%)
        vwap = TA.vwap(candles_15m, 20)
        if vwap:
            if vwap['above_vwap'] and bull_score > bear_score:
                bull_score += 0.07
                reasons.append('Above VWAP')
            elif vwap['below_vwap'] and bear_score > bull_score:
                bear_score += 0.07
        
        # 9. ADX trend strength (weight: 7%)
        adx = TA.adx(candles_15m)
        if adx:
            if adx['strong_trend'] and adx['bullish']:
                bull_score += 0.07
                confluence_count += 1
                reasons.append(f'ADX {adx["adx"]:.0f} bullish')
            elif adx['strong_trend'] and adx['bearish']:
                bear_score += 0.07
                confluence_count += 1
                reasons.append(f'ADX {adx["adx"]:.0f} bearish')
        
        # 10. Hourly trend confirmation bonus
        if closes_1h and len(closes_1h) >= 20:
            h1_ema = TA.ema(closes_1h, 20)
            h1_rsi = TA.rsi(closes_1h)
            if h1_ema and current > h1_ema and h1_rsi and h1_rsi < 65:
                bull_score += 0.05
                reasons.append('H1 trend aligned')
            elif h1_ema and current < h1_ema:
                bear_score += 0.05
        
        # === CONFLUENCE REQUIREMENT ===
        # Need at least 4 independent indicators agreeing
        net_score = bull_score - bear_score
        
        if net_score > 0 and confluence_count >= 4:
            sig.action = 'buy'
            sig.confidence = min(0.95, net_score * (1 + confluence_count * 0.05))
            reasons.insert(0, f'TRADE GOD: {confluence_count} indicators aligned')
        elif net_score < -0.3 and confluence_count >= 3:
            sig.action = 'sell'
            sig.confidence = min(0.95, abs(net_score) * (1 + confluence_count * 0.05))
            reasons.insert(0, f'TRADE GOD SELL: {confluence_count} indicators')
        else:
            reasons.insert(0, f'Confluence: {confluence_count} (need 4+)')
        
        sig.reason = ', '.join(reasons[:5])  # Limit reason length
        return sig
    
    def _kelly_size(self, available_usd: float, confidence: float) -> float:
        """
        Kelly Criterion position sizing.
        Optimal bet = (bp - q) / b
        where b=win/loss ratio, p=win probability, q=loss probability
        We use half-Kelly for safety.
        """
        win_prob = min(0.8, confidence)  # Cap at 80%
        loss_prob = 1 - win_prob
        # Assume 1.5:1 reward/risk ratio
        b = self.config.ATR_TP_MULTIPLIER / self.config.ATR_SL_MULTIPLIER
        
        kelly_pct = (b * win_prob - loss_prob) / b
        kelly_pct = max(0.05, min(0.5, kelly_pct))  # 5-50% range
        
        # Use HALF Kelly for safety
        half_kelly = kelly_pct * 0.5
        
        position = available_usd * half_kelly
        return min(position, self.config.MAX_TRADE_USD)
    
    def _get_fear_greed(self) -> dict:
        """Fetch Crypto Fear & Greed Index (cached)."""
        now = time.time()
        if now - self.fear_greed_cache['timestamp'] < self.config.FEAR_GREED_CACHE_SEC:
            return self.fear_greed_cache
        
        try:
            url = "https://api.alternative.me/fng/?limit=1"
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'RimuruBot/2.0')
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read().decode())
            if data.get('data'):
                entry = data['data'][0]
                self.fear_greed_cache = {
                    'value': int(entry['value']),
                    'label': entry['value_classification'],
                    'timestamp': now,
                }
        except:
            pass  # Use cached/default
        
        return self.fear_greed_cache


# ============================================
# Strategy Performance Tracker (Self-Adapting)
# ============================================

class StrategyTracker:
    """Tracks win/loss per strategy and adapts weights over time."""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.file = data_dir / 'strategy_performance.json'
        self.performance = self._load()
    
    def _load(self) -> dict:
        if self.file.exists():
            try:
                return json.loads(self.file.read_text())
            except:
                pass
        return {}
    
    def _save(self):
        self.file.write_text(json.dumps(self.performance, indent=2))
    
    def record(self, strategy: str, pnl_usd: float, pnl_pct: float):
        """Record a trade result for a strategy."""
        if strategy not in self.performance:
            self.performance[strategy] = {
                'wins': 0, 'losses': 0, 'total_pnl': 0,
                'trades': 0, 'avg_win': 0, 'avg_loss': 0,
                'returns': [],
            }
        
        s = self.performance[strategy]
        s['trades'] += 1
        s['total_pnl'] += pnl_usd
        
        if pnl_usd >= 0:
            s['wins'] += 1
            s['avg_win'] = (s['avg_win'] * (s['wins'] - 1) + pnl_pct) / s['wins']
        else:
            s['losses'] += 1
            s['avg_loss'] = (s['avg_loss'] * (s['losses'] - 1) + pnl_pct) / s['losses'] if s['losses'] > 0 else pnl_pct
        
        s['returns'].append(round(pnl_pct, 4))
        s['returns'] = s['returns'][-100:]
        
        self._save()
    
    def get_adapted_weights(self, base_weights: dict) -> dict:
        """Dynamically adjust strategy weights based on recent performance."""
        weights = dict(base_weights)
        
        for strategy, data in self.performance.items():
            if strategy not in weights or data['trades'] < 3:
                continue
            
            win_rate = data['wins'] / data['trades'] if data['trades'] > 0 else 0.5
            
            if win_rate > 0.7:
                weights[strategy] *= 1.5
            elif win_rate > 0.55:
                weights[strategy] *= 1.2
            elif win_rate < 0.3:
                weights[strategy] *= 0.7
            elif win_rate < 0.4:
                weights[strategy] *= 0.85
            
            weights[strategy] = max(0.3, min(3.0, weights[strategy]))
        
        return weights
    
    def get_analytics(self) -> dict:
        """Performance analytics: Sharpe, Sortino, Max Drawdown, Profit Factor."""
        all_returns = []
        total_trades = 0
        total_wins = 0
        total_pnl = 0
        
        for s, data in self.performance.items():
            all_returns.extend(data.get('returns', []))
            total_trades += data.get('trades', 0)
            total_wins += data.get('wins', 0)
            total_pnl += data.get('total_pnl', 0)
        
        if not all_returns or total_trades == 0:
            return {'sharpe': 0, 'sortino': 0, 'max_drawdown_pct': 0, 'win_rate': 0,
                    'profit_factor': 0, 'total_trades': 0}
        
        mean_ret = statistics.mean(all_returns)
        std_ret = statistics.stdev(all_returns) if len(all_returns) > 1 else 1
        sharpe = (mean_ret / std_ret * math.sqrt(365 * 24)) if std_ret > 0 else 0
        
        downside = [r for r in all_returns if r < 0]
        downside_std = statistics.stdev(downside) if len(downside) > 1 else 1
        sortino = (mean_ret / downside_std * math.sqrt(365 * 24)) if downside_std > 0 else 0
        
        cumulative = []
        running = 0
        for r in all_returns:
            running += r
            cumulative.append(running)
        peak = cumulative[0]
        max_dd = 0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = (peak - val)
            if dd > max_dd:
                max_dd = dd
        
        gross_wins = sum(r for r in all_returns if r > 0)
        gross_losses = abs(sum(r for r in all_returns if r < 0))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        
        win_rate = total_wins / total_trades if total_trades > 0 else 0
        
        return {
            'sharpe': round(sharpe, 2),
            'sortino': round(sortino, 2),
            'max_drawdown_pct': round(max_dd, 4),
            'win_rate': round(win_rate, 3),
            'profit_factor': round(profit_factor, 2),
            'total_trades': total_trades,
            'total_pnl': round(total_pnl, 4),
            'mean_return': round(mean_ret, 4),
        }


# ============================================
# Auto Trader Engine — Trade God v2.0
# ============================================

class RimuruAutoTrader:
    """
    The autonomous trading brain.
    
    Loop:
    1. Check risk limits → abort if breached
    2. Update positions (check stops/targets)
    3. Scan markets for new signals
    4. Execute best opportunity
    5. Log everything
    6. Sleep and repeat
    """
    
    def __init__(self, dry_run: bool = False, aggressive: bool = False):
        self.dry_run = dry_run
        self.config = Config()
        self.bot_name = os.environ.get('RIMURU_BOT_NAME', 'MAIN')
        
        # Apply aggressive overrides
        if aggressive:
            for k, v in Config.AGGRESSIVE.items():
                setattr(self.config, k, v)
        
        # Data directory (unique per bot name for Docker)
        self.data_dir = Path(__file__).parent / 'data' / 'auto_trader'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.log = setup_logging(self.data_dir)
        self.log.info(f"Bot: RIMURU-{self.bot_name} | v{VERSION}")
        
        # Load API keys
        self.api_key, self.api_secret = self._load_keys()
        self.client = KrakenClient(self.api_key, self.api_secret)
        
        # Strategy focus from environment (Docker per-bot specialization)
        strategy_focus = os.environ.get('RIMURU_STRATEGY_FOCUS', '')
        base_weights = dict(Config.STRATEGY_WEIGHTS)
        if strategy_focus:
            focus_list = [s.strip() for s in strategy_focus.split(',')]
            self.log.info(f"Strategy focus: {focus_list}")
            for strat in base_weights:
                if strat in focus_list:
                    base_weights[strat] *= 2.0  # Double weight for focused strategies
                else:
                    base_weights[strat] *= 0.5  # Halve weight for non-focused
        
        # Signal engine with self-adapting weights
        self.strategy_tracker = StrategyTracker(self.data_dir)
        adapted_weights = self.strategy_tracker.get_adapted_weights(base_weights)
        self.signals = SignalEngine(self.config, adapted_weights)
        
        # State
        self.positions: List[Position] = []
        self.closed_positions: List[Position] = []
        self.daily_stats = DailyStats(date=datetime.now(timezone.utc).strftime('%Y-%m-%d'))
        self.running = True
        self.last_trade_time = 0
        self.last_scan_time = 0
        self.last_heartbeat = 0
        self.error_count = 0
        self.cycle_count = 0
        
        # Load saved state
        self._load_state()
        
        # Graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)
    
    def _load_keys(self) -> Tuple[str, str]:
        key_file = Path(__file__).parent / '_SENSITIVE' / 'kraken_keys.txt'
        api_key = os.getenv('KRAKEN_API_KEY', '')
        api_secret = os.getenv('KRAKEN_API_SECRET', '')
        
        if key_file.exists():
            for line in key_file.read_text().splitlines():
                line = line.strip()
                if line.startswith('KRAKEN_API_KEY='):
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('KRAKEN_API_SECRET='):
                    api_secret = line.split('=', 1)[1].strip()
        
        if not api_key or not api_secret:
            raise RuntimeError("No Kraken API keys found! Check _SENSITIVE/kraken_keys.txt")
        
        return api_key, api_secret
    
    def _shutdown(self, signum, frame):
        self.log.warning("Shutdown signal received - closing gracefully...")
        self.running = False
    
    def _load_state(self):
        state_file = self.data_dir / 'state.json'
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                for p in data.get('positions', []):
                    self.positions.append(Position(**p))
                stats = data.get('daily_stats', {})
                if stats.get('date') == datetime.now(timezone.utc).strftime('%Y-%m-%d'):
                    self.daily_stats = DailyStats(**stats)
                self.log.info(f"Loaded state: {len(self.positions)} open positions")
            except Exception as e:
                self.log.warning(f"Could not load state: {e}")
    
    def _save_state(self):
        state_file = self.data_dir / 'state.json'
        data = {
            'positions': [asdict(p) for p in self.positions],
            'daily_stats': asdict(self.daily_stats),
            'last_save': datetime.now(timezone.utc).isoformat(),
        }
        state_file.write_text(json.dumps(data, indent=2))
    
    def _log_trade(self, action: str, pair: str, volume: float, price: float,
                   reason: str, result: dict, dry_run: bool):
        entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'action': action,
            'pair': pair,
            'volume': volume,
            'price': price,
            'value_usd': round(volume * price, 4),
            'reason': reason,
            'dry_run': dry_run,
            'result': result,
        }
        log_file = self.data_dir / f"trades_{datetime.now().strftime('%Y%m%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    # ==========================================
    # Portfolio & Balance
    # ==========================================
    
    def get_full_portfolio(self) -> dict:
        """Get full portfolio breakdown: USD available, holdings with values"""
        try:
            balances = self.client.balance()
            non_zero = {k: float(v) for k, v in balances.items() if float(v) > 0.000001}
            
            if not non_zero:
                return {'usd_available': 0, 'total_usd': 0, 'holdings': {}}
            
            # Get prices
            pairs_needed = []
            asset_pair_map = {}
            for asset in non_zero:
                name = Config.REVERSE_MAP.get(asset)
                if name:
                    pair = Config.TRADEABLE_PAIRS[name]
                    pairs_needed.append(pair)
                    asset_pair_map[asset] = pair
            
            prices = self.client.ticker(pairs_needed) if pairs_needed else {}
            
            usd_available = 0
            total = 0
            holdings = {}
            
            for asset, amount in non_zero.items():
                if asset in ('USDG', 'USD.HOLD', 'ZUSD'):
                    usd_available += amount
                    total += amount
                elif asset in asset_pair_map:
                    pair = asset_pair_map[asset]
                    price = 0
                    for pname, pdata in prices.items():
                        if pair.replace('ZUSD', 'USD') in pname or pair in pname:
                            price = float(pdata['c'][0])
                            break
                    value = amount * price
                    total += value
                    name = Config.REVERSE_MAP.get(asset, asset)
                    holdings[asset] = {
                        'name': name,
                        'pair': pair,
                        'amount': amount,
                        'price': price,
                        'value_usd': round(value, 4),
                    }
            
            return {
                'usd_available': round(usd_available, 4),
                'total_usd': round(total, 4),
                'holdings': holdings,
            }
        except Exception as e:
            self.log.error(f"Portfolio error: {e}")
            return {'usd_available': 0, 'total_usd': 0, 'holdings': {}}
    
    def get_portfolio_value(self) -> float:
        """Get total portfolio value in USD"""
        return self.get_full_portfolio().get('total_usd', 0)
    
    def get_available_usd(self) -> float:
        """Get actual spendable USD balance (USDG/ZUSD/USD.HOLD)"""
        return self.get_full_portfolio().get('usd_available', 0)
    
    def find_weakest_holding(self, portfolio: dict, exclude_pair: str = '') -> Optional[dict]:
        """Find the weakest performing holding to sell for rotation"""
        holdings = portfolio.get('holdings', {})
        if not holdings:
            return None
        
        weakest = None
        worst_score = 999
        
        for asset, info in holdings.items():
            if info['pair'] == exclude_pair:
                continue
            if info['value_usd'] < 0.50:  # Skip dust
                continue
            
            # Check momentum of this holding
            try:
                candles = self.client.ohlc(info['pair'], 15)
                if candles and len(candles) >= 15:
                    closes = [float(c[4]) for c in candles]
                    rsi = TA.rsi(closes)
                    mom = TA.momentum(closes, 5)
                    
                    # Higher RSI + negative momentum = weaker (sell candidate)
                    score = 0
                    if rsi and rsi > 65:
                        score -= (rsi - 50) / 50  # Overbought = sell
                    if mom and mom < 0:
                        score += mom / 10  # Negative momentum = sell
                    if rsi and rsi < 40:
                        score += 0.5  # Oversold = keep
                    
                    if score < worst_score:
                        worst_score = score
                        weakest = {
                            'asset': asset,
                            'pair': info['pair'],
                            'name': info['name'],
                            'amount': info['amount'],
                            'value_usd': info['value_usd'],
                            'score': score,
                            'rsi': rsi,
                            'momentum': mom,
                        }
                time.sleep(0.3)
            except:
                continue
        
        return weakest
    
    # ==========================================
    # Risk Management
    # ==========================================
    
    def check_risk_limits(self) -> Tuple[bool, str]:
        """Check all risk limits. Returns (ok, reason)"""
        
        # Daily loss limit
        if self.daily_stats.starting_balance > 0:
            day_pnl_pct = (self.daily_stats.total_pnl_usd / self.daily_stats.starting_balance)
            if day_pnl_pct < -self.config.MAX_DAILY_LOSS_PCT:
                return False, f"Daily loss limit hit: {day_pnl_pct*100:.1f}%"
        
        # Max drawdown
        if self.daily_stats.peak_balance > 0 and self.daily_stats.current_balance > 0:
            drawdown = (self.daily_stats.peak_balance - self.daily_stats.current_balance) / self.daily_stats.peak_balance
            if drawdown > self.config.MAX_DRAWDOWN_PCT:
                return False, f"Max drawdown hit: {drawdown*100:.1f}%"
        
        # Max positions
        if len(self.positions) >= self.config.MAX_OPEN_POSITIONS:
            return False, f"Max positions ({self.config.MAX_OPEN_POSITIONS}) reached"
        
        # Trade cooldown
        time_since_trade = time.time() - self.last_trade_time
        cooldown = self.config.TRADE_COOLDOWN_SEC
        
        # Extra cooldown after loss
        if self.daily_stats.trades_lost > self.daily_stats.trades_won:
            cooldown = self.config.LOSS_COOLDOWN_SEC
        
        if time_since_trade < cooldown:
            remaining = int(cooldown - time_since_trade)
            return False, f"Trade cooldown: {remaining}s remaining"
        
        return True, "OK"
    
    # ==========================================
    # Position Management
    # ==========================================
    
    def update_positions(self):
        """Check all open positions for stop loss / take profit"""
        if not self.positions:
            return
        
        # Get current prices for all position pairs
        pairs = list(set(p.pair for p in self.positions))
        try:
            prices = self.client.ticker(pairs)
        except Exception as e:
            self.log.error(f"Price fetch error: {e}")
            return
        
        for pos in self.positions[:]:
            # Find current price
            current_price = None
            for pname, pdata in prices.items():
                if pos.pair.replace('ZUSD', 'USD') in pname or pos.pair in pname:
                    current_price = float(pdata['c'][0])
                    break
            
            if current_price is None:
                continue
            
            pos.update(current_price)
            
            exit_reason = None
            
            # Check take profit
            if pos.pnl_pct >= self.config.TAKE_PROFIT_PCT:
                exit_reason = f"TAKE PROFIT: +{pos.pnl_pct*100:.2f}%"
            
            # Check stop loss
            elif pos.pnl_pct <= -self.config.STOP_LOSS_PCT:
                exit_reason = f"STOP LOSS: {pos.pnl_pct*100:.2f}%"
            
            # Check trailing stop (only if we've hit activation threshold)
            elif pos.pnl_pct > 0 and pos.highest_price > 0:
                highest_pnl = (pos.highest_price - pos.entry_price) / pos.entry_price
                if highest_pnl >= self.config.TRAILING_ACTIVATE_PCT:
                    drop_from_high = (pos.highest_price - current_price) / pos.highest_price
                    if drop_from_high >= self.config.TRAILING_STOP_PCT:
                        exit_reason = f"TRAILING STOP: dropped {drop_from_high*100:.2f}% from high ${pos.highest_price:.4f}"
            
            if exit_reason:
                self._close_position(pos, current_price, exit_reason)
    
    def _close_position(self, pos: Position, exit_price: float, reason: str):
        """Close a position by selling"""
        self.log.info(f"CLOSING {pos.pair}: {reason}")
        
        result = {}
        if not self.dry_run:
            try:
                result = self.client.place_order(
                    pair=pos.pair,
                    side='sell',
                    order_type='market',
                    volume=pos.volume,
                )
                self.log.info(f"SELL ORDER: {result}")
            except Exception as e:
                self.log.error(f"SELL ERROR: {e}")
                # Don't remove position if sell failed
                return
        else:
            result = {'descr': f'[DRY RUN] sell {pos.volume} {pos.pair} @ market'}
            self.log.info(f"[DRY RUN] SELL {pos.volume:.8f} {pos.pair} @ ${exit_price:.4f}")
        
        # Update position
        pos.exit_price = exit_price
        pos.exit_time = datetime.now(timezone.utc).isoformat()
        pos.exit_reason = reason
        pos.status = 'closed'
        pos.update(exit_price)
        
        # Move to closed
        self.positions.remove(pos)
        self.closed_positions.append(pos)
        
        # Update stats
        self.daily_stats.trades_executed += 1
        self.daily_stats.total_pnl_usd += pos.pnl_usd
        if pos.pnl_usd >= 0:
            self.daily_stats.trades_won += 1
            self.daily_stats.largest_win = max(self.daily_stats.largest_win, pos.pnl_usd)
        else:
            self.daily_stats.trades_lost += 1
            self.daily_stats.largest_loss = min(self.daily_stats.largest_loss, pos.pnl_usd)
        
        # Record for self-adapting engine
        self.strategy_tracker.record(pos.strategy, pos.pnl_usd, pos.pnl_pct)
        # Update signal engine weights
        self.signals.strategy_weights = self.strategy_tracker.get_adapted_weights(Config.STRATEGY_WEIGHTS)
        
        emoji = "+" if pos.pnl_usd >= 0 else ""
        self.log.info(f"  P&L: {emoji}${pos.pnl_usd:.4f} ({emoji}{pos.pnl_pct*100:.2f}%)")
        
        self._log_trade('sell', pos.pair, pos.volume, exit_price, reason, result, self.dry_run)
        self._save_state()
    
    # ==========================================
    # Trade Execution
    # ==========================================
    
    def _execute_buy(self, signal: Signal):
        """Execute a buy signal using actual available USD"""
        pair = signal.pair
        price = signal.price
        
        # Get REAL available USD to size the order properly
        real_usd = self.get_available_usd()
        max_spend = min(real_usd * self.config.MAX_POSITION_PCT, self.config.MAX_TRADE_USD)
        
        if max_spend < self.config.MIN_TRADE_USD:
            self.log.debug(f"Only ${real_usd:.2f} USD available, need ${self.config.MIN_TRADE_USD:.2f}")
            return
        
        # Calculate volume from actual USD
        volume = max_spend / price if price > 0 else 0
        
        # Round volume to appropriate precision
        if 'BTC' in pair or 'XBT' in pair:
            volume = round(volume, 8)
        elif 'ETH' in pair:
            volume = round(volume, 6)
        elif 'PEPE' in pair:
            volume = round(volume, 0)
        elif 'DOGE' in pair or 'XDG' in pair:
            volume = round(volume, 2)
        else:
            volume = round(volume, 4)
        
        # Check minimum
        min_vol = Config.MIN_ORDER.get(pair, 0)
        if volume < min_vol:
            self.log.warning(f"Volume {volume} below minimum {min_vol} for {pair} (${max_spend:.2f} USD)")
            return
        
        value_usd = volume * price
        self.log.info(f"{'[DRY RUN] ' if self.dry_run else ''}BUY {volume} {pair} @ ${price:.4f} (${value_usd:.2f})")
        self.log.info(f"  Strategy: {signal.strategy} | Confidence: {signal.confidence:.0%}")
        self.log.info(f"  Reason: {signal.reason}")
        self.log.info(f"  Stop: ${signal.stop_loss:.4f} | Target: ${signal.take_profit:.4f}")
        
        result = {}
        order_id = ''
        
        if not self.dry_run:
            try:
                result = self.client.place_order(
                    pair=pair,
                    side='buy',
                    order_type='market',
                    volume=volume,
                )
                self.log.info(f"BUY ORDER RESULT: {result}")
                # Extract order ID
                txid = result.get('txid', [])
                if txid:
                    order_id = txid[0]
            except Exception as e:
                self.log.error(f"BUY ERROR: {e}")
                self.error_count += 1
                # If insufficient funds, set long cooldown to avoid spam
                if 'Insufficient funds' in str(e):
                    self.log.warning(f"Insufficient funds - cooling down {self.config.INSUFFICIENT_FUNDS_COOLDOWN}s")
                    self.last_trade_time = time.time() + self.config.INSUFFICIENT_FUNDS_COOLDOWN - self.config.TRADE_COOLDOWN_SEC
                return
        else:
            result = {'descr': f'[DRY RUN] buy {volume} {pair} @ market'}
        
        # Create position
        pos = Position(
            pair=pair,
            side='long',
            entry_price=price,
            volume=volume,
            entry_time=datetime.now(timezone.utc).isoformat(),
            strategy=signal.strategy,
            order_id=order_id,
            highest_price=price,
            current_price=price,
        )
        self.positions.append(pos)
        
        # Update stats
        self.daily_stats.trades_executed += 1
        self.daily_stats.last_trade_time = datetime.now(timezone.utc).isoformat()
        self.last_trade_time = time.time()
        
        self._log_trade('buy', pair, volume, price, signal.reason, result, self.dry_run)
        self._save_state()
    
    # ==========================================
    # Market Scanner
    # ==========================================
    
    def scan_markets(self) -> Optional[Signal]:
        """Scan all pairs and return best signal. Uses actual USD balance."""
        portfolio = self.get_full_portfolio()
        available = portfolio['usd_available']
        total = portfolio['total_usd']
        
        self.log.debug(f"Scan: ${available:.2f} USD available, ${total:.2f} total portfolio")
        
        # If no USD available, try rotation
        need_rotation = available < self.config.MIN_TRADE_USD and self.config.ENABLE_ROTATION
        
        if available < self.config.MIN_TRADE_USD and not need_rotation:
            self.log.debug(f"Available USD: ${available:.2f} - below minimum, no rotation enabled")
            return None
        
        best_signal = None
        
        for name, pair in Config.TRADEABLE_PAIRS.items():
            try:
                # Skip pairs we already have positions in
                if any(p.pair == pair for p in self.positions):
                    continue
                
                # Get candle data
                candles_5m = self.client.ohlc(pair, 5)
                time.sleep(0.3)
                candles_15m = self.client.ohlc(pair, 15)
                time.sleep(0.3)
                candles_1h = self.client.ohlc(pair, 60)
                time.sleep(0.3)
                
                # Check spread
                book = self.client.orderbook(pair, 5)
                if book:
                    bids = book.get('bids', [])
                    asks = book.get('asks', [])
                    if bids and asks:
                        spread = (float(asks[0][0]) - float(bids[0][0])) / float(bids[0][0]) * 100
                        if spread > self.config.MAX_SPREAD_PCT:
                            self.log.debug(f"{pair}: spread {spread:.3f}% too wide, skipping")
                            continue
                
                # Use actual USD available (or total if rotating)
                funds_for_signal = available if available >= self.config.MIN_TRADE_USD else total * 0.4
                
                signal = self.signals.analyze(
                    pair, candles_5m, candles_15m, candles_1h,
                    funds_for_signal, self.positions
                )
                
                if signal.action == 'buy' and signal.confidence >= self.config.MIN_CONFIDENCE:
                    if best_signal is None or signal.confidence > best_signal.confidence:
                        best_signal = signal
                
                self.log.debug(f"{pair}: {signal.action} conf={signal.confidence:.2f} - {signal.reason}")
                
                time.sleep(0.3)
                
            except Exception as e:
                self.log.error(f"Scan error on {pair}: {e}")
                continue
        
        # If we found a signal but no USD, do rotation: sell weakest to fund buy
        if best_signal and available < self.config.MIN_TRADE_USD and need_rotation:
            weakest = self.find_weakest_holding(portfolio, exclude_pair=best_signal.pair)
            if weakest and weakest['value_usd'] >= self.config.MIN_TRADE_USD:
                self.log.info(f"ROTATION: Selling {weakest['name']} (${weakest['value_usd']:.2f}, "
                             f"RSI={weakest.get('rsi', '?')}, Mom={weakest.get('momentum', '?')}) "
                             f"to buy {best_signal.pair}")
                self._execute_rotation_sell(weakest, best_signal)
                return None  # Buy will happen next cycle after sell settles
            else:
                self.log.debug(f"No suitable holding to rotate out")
                return None  # Can't buy, no USD, no rotation candidate
        
        # If we have a signal but not enough USD and can't rotate, skip
        if best_signal and available < self.config.MIN_TRADE_USD:
            self.log.debug(f"Signal found but only ${available:.2f} USD available")
            return None
        
        return best_signal
    
    def _execute_rotation_sell(self, holding: dict, target_signal: Signal):
        """Sell a holding to free up USD for a better opportunity"""
        pair = holding['pair']
        amount = holding['amount']
        
        self.log.info(f"{'[DRY RUN] ' if self.dry_run else ''}ROTATION SELL {amount} {pair} "
                     f"(${holding['value_usd']:.2f})")
        
        if not self.dry_run:
            try:
                # Round volume appropriately
                if 'BTC' in pair or 'XBT' in pair:
                    amount = round(amount, 8)
                elif 'ETH' in pair:
                    amount = round(amount, 6)
                elif 'PEPE' in pair:
                    amount = round(amount, 0)
                elif 'DOGE' in pair or 'XDG' in pair:
                    amount = round(amount, 2)
                else:
                    amount = round(amount, 4)
                
                # Check minimum order size
                min_vol = Config.MIN_ORDER.get(pair, 0)
                if amount < min_vol:
                    self.log.warning(f"Rotation sell volume {amount} below min {min_vol}")
                    return
                
                result = self.client.place_order(
                    pair=pair,
                    side='sell',
                    order_type='market',
                    volume=amount,
                )
                self.log.info(f"ROTATION SELL RESULT: {result}")
                self.last_trade_time = time.time()
                self.daily_stats.trades_executed += 1
                self._log_trade('rotation_sell', pair, amount, holding.get('price', 0),
                              f"Rotating to {target_signal.pair}", result, False)
            except Exception as e:
                self.log.error(f"ROTATION SELL ERROR: {e}")
        else:
            self.log.info(f"[DRY RUN] Would sell {amount} {pair} to fund {target_signal.pair}")
            self.last_trade_time = time.time()
    
    # ==========================================
    # Main Loop
    # ==========================================
    
    def start(self):
        """Main auto-trading loop"""
        mode = "DRY RUN" if self.dry_run else "LIVE"
        aggressive = " (AGGRESSIVE)" if hasattr(self.config, '_aggressive') else ""
        
        banner = f"""
╔══════════════════════════════════════════════════════════════╗
║    RIMURU-{self.bot_name:<8} AUTO-TRADER v2.0 — TRADE GOD EDITION   ║
║    Mode: {mode:<10}{aggressive:<30}       ║
║    Strategies: 7 engines | Pairs: {len(Config.TRADEABLE_PAIRS)} markets                 ║
║    ATR stops: {'ON' if self.config.USE_ATR_STOPS else 'OFF':<4} | Kelly sizing: {'ON' if self.config.USE_KELLY_SIZING else 'OFF':<4}                 ║
╚══════════════════════════════════════════════════════════════╝"""
        
        print(banner)
        self.log.info(f"Starting Rimuru Auto-Trader [{mode}]")
        
        # Get initial balance
        try:
            initial_balance = self.get_portfolio_value()
            if self.daily_stats.starting_balance == 0:
                self.daily_stats.starting_balance = initial_balance
            self.daily_stats.current_balance = initial_balance
            self.daily_stats.peak_balance = max(self.daily_stats.peak_balance, initial_balance)
            self.log.info(f"Portfolio: ${initial_balance:.2f}")
            self.log.info(f"Risk limits: {self.config.MAX_DAILY_LOSS_PCT*100:.0f}% daily loss, "
                         f"{self.config.MAX_DRAWDOWN_PCT*100:.0f}% max drawdown")
            self.log.info(f"Targets: +{self.config.TAKE_PROFIT_PCT*100:.1f}% TP, "
                         f"-{self.config.STOP_LOSS_PCT*100:.1f}% SL, "
                         f"{self.config.TRAILING_STOP_PCT*100:.1f}% trailing")
        except Exception as e:
            self.log.error(f"Initial balance check failed: {e}")
            initial_balance = 0
        
        self.log.info(f"Scan interval: {self.config.SCAN_INTERVAL_SEC}s | "
                     f"Min confidence: {self.config.MIN_CONFIDENCE:.0%}")
        self.log.info("Press Ctrl+C to stop gracefully")
        self.log.info("-" * 50)
        
        while self.running:
            try:
                self.cycle_count += 1
                now = time.time()
                
                # === 1. Update positions (fast check) ===
                if self.positions:
                    self.update_positions()
                
                # === 2. Heartbeat log ===
                if now - self.last_heartbeat >= self.config.HEARTBEAT_SEC:
                    self._heartbeat()
                    self.last_heartbeat = now
                
                # === 3. Full market scan ===
                if now - self.last_scan_time >= self.config.SCAN_INTERVAL_SEC:
                    self.last_scan_time = now
                    
                    # Check risk limits first
                    ok, reason = self.check_risk_limits()
                    if not ok:
                        self.log.debug(f"Risk check: {reason}")
                        if 'loss limit' in reason or 'drawdown' in reason:
                            self.log.warning(f"TRADING HALTED: {reason}")
                            time.sleep(60)
                            continue
                    else:
                        # Scan and maybe trade
                        signal = self.scan_markets()
                        
                        if signal and signal.action == 'buy':
                            self.log.info(f"SIGNAL: {signal.action.upper()} {signal.pair} "
                                        f"conf={signal.confidence:.0%} [{signal.strategy}]")
                            self._execute_buy(signal)
                        else:
                            if signal:
                                self.log.debug(f"Signal: {signal.action} {signal.pair} "
                                             f"(conf too low: {signal.confidence:.2f})")
                
                # === 4. Update portfolio value ===
                if self.cycle_count % 10 == 0:
                    try:
                        val = self.get_portfolio_value()
                        self.daily_stats.current_balance = val
                        self.daily_stats.peak_balance = max(self.daily_stats.peak_balance, val)
                        self._save_state()
                    except:
                        pass
                
                # Reset error count on successful cycle
                self.error_count = 0
                
                # Sleep
                sleep_time = self.config.FAST_CHECK_SEC if self.positions else self.config.SCAN_INTERVAL_SEC
                # But don't sleep longer than remaining scan interval
                remaining = self.config.SCAN_INTERVAL_SEC - (time.time() - self.last_scan_time)
                sleep_time = min(sleep_time, max(remaining, 5))
                
                time.sleep(max(5, sleep_time))
                
            except KeyboardInterrupt:
                self.running = False
            except Exception as e:
                self.error_count += 1
                self.log.error(f"Cycle error: {e}")
                self.log.debug(traceback.format_exc())
                
                if self.error_count >= 5:
                    self.log.error("Too many errors, pausing 5 minutes...")
                    time.sleep(300)
                    self.error_count = 0
                else:
                    time.sleep(self.config.ERROR_COOLDOWN_SEC)
        
        # Shutdown
        self._shutdown_report()
    
    def _heartbeat(self):
        """Periodic status log"""
        stats = self.daily_stats
        portfolio = self.get_full_portfolio()
        usd_avail = portfolio.get('usd_available', 0)
        
        pos_str = "None"
        if self.positions:
            parts = []
            for p in self.positions:
                pnl = f"+{p.pnl_pct*100:.2f}%" if p.pnl_pct >= 0 else f"{p.pnl_pct*100:.2f}%"
                parts.append(f"{p.pair} {pnl}")
            pos_str = " | ".join(parts)
        
        holdings_str = ""
        for asset, info in portfolio.get('holdings', {}).items():
            if info['value_usd'] > 0.01:
                holdings_str += f" {info['name']}=${info['value_usd']:.2f}"
        
        self.log.info(
            f"HEARTBEAT [{self.bot_name}] | Total: ${stats.current_balance:.2f} | USD: ${usd_avail:.2f} |{holdings_str} | "
            f"Positions: {pos_str} | "
            f"Trades: {stats.trades_executed} (W:{stats.trades_won} L:{stats.trades_lost}) | "
            f"P&L: ${stats.total_pnl_usd:+.4f}"
        )
    
    def _shutdown_report(self):
        """Final report on shutdown"""
        self.log.info("=" * 50)
        self.log.info(f"RIMURU-{self.bot_name} AUTO-TRADER SHUTDOWN REPORT")
        self.log.info("=" * 50)
        
        stats = self.daily_stats
        self.log.info(f"Session duration: {self.cycle_count} cycles")
        self.log.info(f"Starting balance: ${stats.starting_balance:.2f}")
        self.log.info(f"Ending balance:   ${stats.current_balance:.2f}")
        self.log.info(f"Total P&L:        ${stats.total_pnl_usd:+.4f}")
        self.log.info(f"Peak balance:     ${stats.peak_balance:.2f}")
        self.log.info(f"Trades executed:  {stats.trades_executed}")
        self.log.info(f"Win/Loss:         {stats.trades_won}/{stats.trades_lost}")
        if stats.trades_executed > 0:
            win_rate = stats.trades_won / stats.trades_executed * 100
            self.log.info(f"Win rate:         {win_rate:.0f}%")
        self.log.info(f"Largest win:      ${stats.largest_win:.4f}")
        self.log.info(f"Largest loss:     ${stats.largest_loss:.4f}")
        
        if self.positions:
            self.log.warning(f"OPEN POSITIONS ({len(self.positions)}):")
            for p in self.positions:
                self.log.warning(f"  {p.pair}: {p.volume} @ ${p.entry_price:.4f} "
                               f"(P&L: {p.pnl_pct*100:+.2f}%)")
        
        self.log.info("=" * 50)
        self._save_state()
    
    def status(self):
        """Print current status + Trade God analytics"""
        print("\n" + "=" * 60)
        print(f"  RIMURU AUTO-TRADER v{VERSION} STATUS")
        print("=" * 60)
        
        try:
            portfolio = self.get_full_portfolio()
            total = portfolio.get('total_usd', 0)
            usd = portfolio.get('usd_available', 0)
            print(f"\n  Portfolio: ${total:.2f} (${usd:.2f} USD available)")
            for asset, info in portfolio.get('holdings', {}).items():
                if info['value_usd'] > 0.01:
                    print(f"    {info['name']}: {info['amount']:.6f} = ${info['value_usd']:.2f}")
        except:
            print("\n  Portfolio: [error fetching]")
        
        s = self.daily_stats
        print(f"\n  Today ({s.date}):")
        print(f"    Starting:  ${s.starting_balance:.2f}")
        print(f"    Current:   ${s.current_balance:.2f}")
        print(f"    P&L:       ${s.total_pnl_usd:+.4f}")
        print(f"    Trades:    {s.trades_executed} (W:{s.trades_won} L:{s.trades_lost})")
        
        analytics = self.strategy_tracker.get_analytics()
        if analytics['total_trades'] > 0:
            print(f"\n  Analytics:")
            print(f"    Sharpe Ratio:  {analytics['sharpe']:.2f}")
            print(f"    Sortino Ratio: {analytics['sortino']:.2f}")
            print(f"    Win Rate:      {analytics['win_rate']*100:.1f}%")
            print(f"    Profit Factor: {analytics['profit_factor']:.2f}")
            print(f"    Max Drawdown:  {analytics['max_drawdown_pct']*100:.2f}%")
        
        weights = self.signals.strategy_weights
        print(f"\n  Strategy Weights:")
        for strat, weight in sorted(weights.items()):
            bar = "#" * int(weight * 10)
            print(f"    {strat:<14} {weight:.2f} {bar}")
        
        if self.positions:
            print(f"\n  Open Positions:")
            for p in self.positions:
                pnl = f"+{p.pnl_pct*100:.2f}%" if p.pnl_pct >= 0 else f"{p.pnl_pct*100:.2f}%"
                print(f"    {p.pair}: {p.volume:.8f} @ ${p.entry_price:.4f} ({pnl}) [{p.strategy}]")
        else:
            print(f"\n  No open positions")
        
        state_file = self.data_dir / 'state.json'
        if state_file.exists():
            mod_time = datetime.fromtimestamp(state_file.stat().st_mtime)
            print(f"\n  Last state: {mod_time.strftime('%H:%M:%S')}")
        
        print("\n" + "=" * 60)


# ============================================
# Entry Point
# ============================================

def main():
    args = sys.argv[1:]
    
    dry_run = '--dry-run' in args or '-d' in args
    aggressive = '--aggressive' in args or '-a' in args
    status_only = '--status' in args or '-s' in args
    live = '--live' in args or '-l' in args
    
    # Support env var override for Docker containers
    if os.environ.get('RIMURU_LIVE') == '1':
        live = True
    if os.environ.get('RIMURU_AGGRESSIVE') == '1':
        aggressive = True
    
    if not dry_run and not live:
        dry_run = True
        print(f"\n  [!] Rimuru v{VERSION} — Defaulting to DRY RUN mode")
        print("  [!] Use --live to execute real trades\n")
    
    if live:
        dry_run = False
        print(f"\n  [!!!] RIMURU v{VERSION} — LIVE TRADING MODE [!!!]")
        print("  [!!!] Real money at risk [!!!]\n")
        # 3 second countdown (faster for Docker)
        countdown = 3 if os.environ.get('RIMURU_DOCKER') else 5
        for i in range(countdown, 0, -1):
            print(f"  Starting in {i}...", end='\r')
            time.sleep(1)
        print("  Starting now!            ")
    
    trader = RimuruAutoTrader(dry_run=dry_run, aggressive=aggressive)
    
    if status_only:
        trader.status()
        return
    
    trader.start()


if __name__ == '__main__':
    main()
