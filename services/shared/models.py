"""
Rimuru Crypto Empire — Shared Data Models
All microservices use these Pydantic models for API communication.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum
from datetime import datetime


# ============================================
# Enums
# ============================================

class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"

class MarketRegime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    MIXED = "MIXED"

class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    STOPPED = "stopped"


# ============================================
# OHLCV / Market Data
# ============================================

class OHLCV(BaseModel):
    timestamp: float
    open: float
    high: float
    low: float
    close: float
    vwap: float = 0.0
    volume: float
    count: int = 0

class TickerData(BaseModel):
    pair: str
    ask: float
    bid: float
    last: float
    volume_24h: float = 0.0
    high_24h: float = 0.0
    low_24h: float = 0.0
    spread_pct: float = 0.0

class OrderBookEntry(BaseModel):
    price: float
    volume: float

class OrderBook(BaseModel):
    pair: str
    asks: List[OrderBookEntry] = []
    bids: List[OrderBookEntry] = []

class MarketDataRequest(BaseModel):
    pair: str
    interval: int = 5  # minutes
    count: int = 200

class MarketDataResponse(BaseModel):
    pair: str
    interval: int
    candles: List[OHLCV]
    ticker: Optional[TickerData] = None


# ============================================
# Indicator Results
# ============================================

class IndicatorRequest(BaseModel):
    pair: str
    candles: List[OHLCV]
    indicators: List[str] = ["all"]  # e.g. ["rsi", "macd", "bollinger"] or ["all"]

class IndicatorResult(BaseModel):
    pair: str
    timestamp: str = ""
    current_price: float = 0.0
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_5: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[Dict] = None         # {macd, signal, histogram}
    bollinger: Optional[Dict] = None    # {lower, middle, upper, width}
    atr: Optional[float] = None
    stochastic: Optional[Dict] = None   # {k, d, overbought, oversold, bullish_cross, bearish_cross}
    adx: Optional[Dict] = None          # {adx, plus_di, minus_di, strong_trend, bullish}
    vwap: Optional[Dict] = None         # {vwap, deviation_pct, above_vwap}
    williams_r: Optional[float] = None
    momentum: Optional[float] = None
    volume_trend: Optional[float] = None
    fibonacci: Optional[Dict] = None
    market_regime: Optional[Dict] = None


# ============================================
# Strategy Signals
# ============================================

class StrategySignal(BaseModel):
    pair: str
    action: SignalAction = SignalAction.HOLD
    confidence: float = 0.0         # 0.0 to 1.0
    strategy: str = ""
    reason: str = ""
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    suggested_volume: float = 0.0
    timeframe: str = ""             # "5m", "15m", "1h"
    timestamp: str = ""

class StrategyRequest(BaseModel):
    pair: str
    indicators: IndicatorResult
    candles_5m: List[OHLCV] = []
    candles_15m: List[OHLCV] = []
    candles_1h: List[OHLCV] = []
    available_usd: float = 0.0
    open_positions: int = 0

class EnsembleSignal(BaseModel):
    """Aggregated signal from all strategies"""
    pair: str
    action: SignalAction = SignalAction.HOLD
    confidence: float = 0.0
    strategies_agree: int = 0
    strategies_total: int = 0
    best_strategy: str = ""
    reason: str = ""
    price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    suggested_volume: float = 0.0
    individual_signals: List[StrategySignal] = []
    market_regime: str = ""
    fear_greed: int = 50
    timestamp: str = ""


# ============================================
# Executor / Orders
# ============================================

class OrderRequest(BaseModel):
    pair: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    volume: float
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy: str = ""
    signal_confidence: float = 0.0
    validate_only: bool = False     # paper mode

class OrderResult(BaseModel):
    success: bool = False
    order_id: str = ""
    pair: str = ""
    side: str = ""
    volume: float = 0.0
    price: float = 0.0
    cost_usd: float = 0.0
    fee: float = 0.0
    error: str = ""
    timestamp: str = ""

class Position(BaseModel):
    pair: str
    side: str = "long"
    entry_price: float
    volume: float
    entry_time: str
    strategy: str
    order_id: str = ""
    highest_price: float = 0.0
    current_price: float = 0.0
    pnl_pct: float = 0.0
    pnl_usd: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    status: PositionStatus = PositionStatus.OPEN

class PortfolioState(BaseModel):
    total_usd: float = 0.0
    available_usd: float = 0.0
    open_positions: List[Position] = []
    daily_pnl: float = 0.0
    daily_trades: int = 0
    balances: Dict[str, float] = {}


# ============================================
# Backtester
# ============================================

class BacktestRequest(BaseModel):
    pair: str
    strategy: str = "all"
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100.0
    interval: int = 15              # minutes

class BacktestTrade(BaseModel):
    entry_time: str
    exit_time: str
    pair: str
    side: str
    entry_price: float
    exit_price: float
    volume: float
    pnl_pct: float
    pnl_usd: float
    strategy: str

class BacktestResult(BaseModel):
    strategy: str
    pair: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl_pct: float = 0.0
    total_pnl_usd: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    trades: List[BacktestTrade] = []


# ============================================
# Health / Status
# ============================================

class ServiceHealth(BaseModel):
    service: str
    status: str = "healthy"
    version: str = "2.0.0"
    uptime_seconds: float = 0
    last_activity: str = ""
    details: Dict = {}
