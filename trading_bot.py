"""
RIMURU TRADING BOT - Kraken Scalper
====================================
Designed for small accounts ($25-100+). Strategies:
1. Momentum Scalping - ride short-term price moves
2. Mean Reversion - buy dips, sell rips on volatile pairs
3. DCA (Dollar Cost Average) - systematic accumulation
4. Grid Trading - place buy/sell orders at intervals

Uses Kraken API with real-time price monitoring.
"""

import os
import json
import time
import hashlib
import hmac
import base64
import urllib.request
import urllib.parse
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [TRADER] %(levelname)s: %(message)s'
)
logger = logging.getLogger('trader')

# ============================================
# Load keys from secure file
# ============================================
def load_keys():
    key_file = Path(__file__).parent / '_SENSITIVE' / 'kraken_keys.txt'
    if not key_file.exists():
        key_file = Path(os.getenv('KRAKEN_KEY_FILE', '_SENSITIVE/kraken_keys.txt'))
    
    api_key = os.getenv('KRAKEN_API_KEY', '')
    api_secret = os.getenv('KRAKEN_API_SECRET', '')
    
    if key_file.exists():
        for line in key_file.read_text().splitlines():
            line = line.strip()
            if line.startswith('KRAKEN_API_KEY='):
                api_key = line.split('=', 1)[1].strip()
            elif line.startswith('KRAKEN_API_SECRET='):
                api_secret = line.split('=', 1)[1].strip()
    
    return api_key, api_secret

API_KEY, API_SECRET = load_keys()

# ============================================
# Kraken API Client
# ============================================
class KrakenClient:
    """Full Kraken API client for trading"""
    
    BASE_URL = "https://api.kraken.com"
    
    def __init__(self, key: str = '', secret: str = ''):
        self.key = key or API_KEY
        self.secret = secret or API_SECRET
    
    def _sign(self, urlpath: str, data: dict) -> str:
        postdata = urllib.parse.urlencode(data)
        encoded = (str(data['nonce']) + postdata).encode('utf-8')
        message = urlpath.encode('utf-8') + hashlib.sha256(encoded).digest()
        mac = hmac.new(base64.b64decode(self.secret), message, hashlib.sha512)
        return base64.b64encode(mac.digest()).decode('utf-8')
    
    def _private(self, endpoint: str, data: dict = None) -> dict:
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
        
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            result = json.loads(resp.read().decode())
            if result.get('error'):
                logger.error(f"API error on {endpoint}: {result['error']}")
            return result
        except Exception as e:
            return {'error': [str(e)]}
    
    def _public(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        if params:
            url += '?' + urllib.parse.urlencode(params)
        try:
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read().decode())
        except Exception as e:
            return {'error': [str(e)]}
    
    # === Account ===
    def balance(self) -> dict:
        r = self._private('/0/private/Balance')
        return r.get('result', {}) if not r.get('error') else {}
    
    def trade_balance(self, asset='ZUSD') -> dict:
        r = self._private('/0/private/TradeBalance', {'asset': asset})
        return r.get('result', {}) if not r.get('error') else {}
    
    def open_orders(self) -> dict:
        r = self._private('/0/private/OpenOrders')
        return r.get('result', {}).get('open', {}) if not r.get('error') else {}
    
    # === Market Data ===
    def ticker(self, pairs: list) -> dict:
        r = self._public('/0/public/Ticker', {'pair': ','.join(pairs)})
        return r.get('result', {})
    
    def ohlc(self, pair: str, interval: int = 5) -> list:
        """Get OHLC candles. interval in minutes: 1,5,15,30,60,240,1440"""
        r = self._public('/0/public/OHLC', {'pair': pair, 'interval': interval})
        result = r.get('result', {})
        # Remove 'last' key
        for k, v in result.items():
            if isinstance(v, list):
                return v
        return []
    
    def orderbook(self, pair: str, count: int = 10) -> dict:
        r = self._public('/0/public/Depth', {'pair': pair, 'count': count})
        result = r.get('result', {})
        for k, v in result.items():
            if isinstance(v, dict):
                return v
        return {}
    
    def spread(self, pair: str) -> list:
        r = self._public('/0/public/Spread', {'pair': pair})
        result = r.get('result', {})
        for k, v in result.items():
            if isinstance(v, list):
                return v
        return []
    
    # === Trading ===
    def place_order(self, pair: str, side: str, order_type: str,
                    volume: float, price: float = None, validate: bool = False) -> dict:
        """
        Place an order.
        side: 'buy' or 'sell'
        order_type: 'market', 'limit', 'stop-loss', 'take-profit'
        validate: if True, validates but doesn't place
        """
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
        
        r = self._private('/0/private/AddOrder', data)
        return r
    
    def cancel_order(self, txid: str) -> dict:
        return self._private('/0/private/CancelOrder', {'txid': txid})
    
    def cancel_all(self) -> dict:
        return self._private('/0/private/CancelAll')


# ============================================
# Technical Analysis Helpers
# ============================================
class TechAnalysis:
    """Simple technical indicators for scalping"""
    
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
    def bollinger_bands(prices: list, period: int = 20, std_dev: float = 2.0) -> Optional[Tuple[float, float, float]]:
        if len(prices) < period:
            return None
        import math
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
    def vwap(candles: list) -> Optional[float]:
        """Volume-weighted average price from OHLC candles"""
        if not candles:
            return None
        total_pv = 0
        total_v = 0
        for c in candles:
            # Candle: [time, open, high, low, close, vwap, volume, count]
            try:
                typical = (float(c[2]) + float(c[3]) + float(c[4])) / 3
                vol = float(c[6])
                total_pv += typical * vol
                total_v += vol
            except:
                continue
        return total_pv / total_v if total_v > 0 else None


# ============================================
# Trading Strategies
# ============================================

@dataclass
class TradeSignal:
    pair: str
    action: str          # 'buy', 'sell', 'hold'
    confidence: float    # 0-1
    reason: str
    price: float
    volume: float
    strategy: str
    timestamp: str = ''


class MomentumScalper:
    """
    Momentum Scalping Strategy
    - Buy when short EMA crosses above long EMA with RSI confirmation
    - Sell when momentum reverses or target hit
    - Target: 1-3% profit per trade
    - Stop loss: 2% max
    """
    
    NAME = "momentum_scalp"
    
    def __init__(self, short_period=5, long_period=15, rsi_buy=35, rsi_sell=65,
                 profit_target=0.02, stop_loss=0.02):
        self.short_period = short_period
        self.long_period = long_period
        self.rsi_buy = rsi_buy
        self.rsi_sell = rsi_sell
        self.profit_target = profit_target
        self.stop_loss = stop_loss
        self.entry_price = None
        self.position = None
    
    def analyze(self, prices: list, current_price: float, pair: str, available_usd: float) -> TradeSignal:
        ta = TechAnalysis
        
        short_ema = ta.ema(prices, self.short_period)
        long_ema = ta.ema(prices, self.long_period)
        rsi = ta.rsi(prices)
        momentum = ta.momentum(prices, 5)
        
        signal = TradeSignal(
            pair=pair, action='hold', confidence=0, reason='',
            price=current_price, volume=0, strategy=self.NAME,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        if not all([short_ema, long_ema, rsi]):
            signal.reason = 'Insufficient data'
            return signal
        
        # Check exit conditions first
        if self.entry_price and self.position == 'long':
            pnl = (current_price - self.entry_price) / self.entry_price
            if pnl >= self.profit_target:
                signal.action = 'sell'
                signal.confidence = 0.9
                signal.reason = f'Target hit: +{pnl*100:.2f}%'
                signal.volume = 0  # Sell all
                return signal
            if pnl <= -self.stop_loss:
                signal.action = 'sell'
                signal.confidence = 0.95
                signal.reason = f'Stop loss: {pnl*100:.2f}%'
                signal.volume = 0
                return signal
        
        # Entry conditions
        if (short_ema > long_ema and rsi < self.rsi_buy and 
            momentum and momentum > 0 and not self.position):
            # Bullish crossover with oversold RSI and positive momentum
            signal.action = 'buy'
            signal.confidence = min(0.8, (self.rsi_buy - rsi) / 50 + 0.3)
            signal.reason = f'Bullish: EMA cross + RSI={rsi:.0f} + Mom={momentum:.1f}%'
            # Use 50% of available for safety
            signal.volume = (available_usd * 0.5) / current_price
            return signal
        
        if (short_ema < long_ema and rsi > self.rsi_sell and self.position == 'long'):
            signal.action = 'sell'
            signal.confidence = 0.7
            signal.reason = f'Bearish: EMA cross down + RSI={rsi:.0f}'
            return signal
        
        signal.reason = f'No signal (EMA_s={short_ema:.2f} EMA_l={long_ema:.2f} RSI={rsi:.0f})'
        return signal


class MeanReversionTrader:
    """
    Mean Reversion - Buy at lower Bollinger Band, sell at upper
    Good for ranging/sideways markets
    """
    
    NAME = "mean_reversion"
    
    def __init__(self, bb_period=20, bb_std=2.0, profit_target=0.015):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.profit_target = profit_target
        self.entry_price = None
        self.position = None
    
    def analyze(self, prices: list, current_price: float, pair: str, available_usd: float) -> TradeSignal:
        ta = TechAnalysis
        bb = ta.bollinger_bands(prices, self.bb_period, self.bb_std)
        rsi = ta.rsi(prices)
        
        signal = TradeSignal(
            pair=pair, action='hold', confidence=0, reason='',
            price=current_price, volume=0, strategy=self.NAME,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        if not bb or not rsi:
            signal.reason = 'Insufficient data'
            return signal
        
        lower, mid, upper = bb
        bb_width = (upper - lower) / mid * 100
        
        # Exit conditions
        if self.entry_price and self.position == 'long':
            pnl = (current_price - self.entry_price) / self.entry_price
            if current_price >= upper or pnl >= self.profit_target:
                signal.action = 'sell'
                signal.confidence = 0.85
                signal.reason = f'Mean reversion target: price at upper BB (+{pnl*100:.2f}%)'
                return signal
            if pnl <= -0.03:
                signal.action = 'sell'
                signal.confidence = 0.9
                signal.reason = f'Stop loss: {pnl*100:.2f}%'
                return signal
        
        # Entry: price at or below lower BB and RSI oversold
        if current_price <= lower and rsi < 40 and not self.position:
            signal.action = 'buy'
            signal.confidence = 0.7
            signal.reason = f'At lower BB ({lower:.2f}), RSI={rsi:.0f}, width={bb_width:.1f}%'
            signal.volume = (available_usd * 0.4) / current_price
            return signal
        
        signal.reason = f'No signal (BB: {lower:.2f}/{mid:.2f}/{upper:.2f} RSI={rsi:.0f})'
        return signal


class GridTrader:
    """
    Grid Trading - Place orders at fixed intervals
    Works in any market condition, profits from volatility
    """
    
    NAME = "grid"
    
    def __init__(self, grid_size_pct=0.01, num_levels=5):
        self.grid_size_pct = grid_size_pct
        self.num_levels = num_levels
        self.grid_orders = {}
    
    def generate_grid(self, current_price: float, pair: str, total_usd: float) -> List[Dict]:
        """Generate grid of buy/sell orders around current price"""
        orders = []
        usd_per_level = total_usd / self.num_levels
        
        for i in range(1, self.num_levels + 1):
            # Buy orders below current price
            buy_price = current_price * (1 - self.grid_size_pct * i)
            buy_volume = usd_per_level / buy_price
            orders.append({
                'side': 'buy',
                'price': round(buy_price, 4),
                'volume': round(buy_volume, 8),
                'level': -i,
                'pair': pair,
            })
            
            # Sell orders above current price
            sell_price = current_price * (1 + self.grid_size_pct * i)
            sell_volume = usd_per_level / sell_price
            orders.append({
                'side': 'sell',
                'price': round(sell_price, 4),
                'volume': round(sell_volume, 8),
                'level': i,
                'pair': pair,
            })
        
        return orders


# ============================================
# Main Trading Bot
# ============================================

class TradingBot:
    """
    Main trading bot orchestrator
    
    Features:
    - Multi-strategy (momentum, mean reversion, grid)
    - Real-time Kraken data
    - Position tracking
    - P&L monitoring
    - Configurable risk limits
    - Full trade logging
    """
    
    TRADEABLE_PAIRS = {
        'SOL': 'SOLUSD',
        'PEPE': 'PEPEUSD',
        'DOGE': 'XDGUSD',
        'BTC': 'XXBTZUSD',
        'ETH': 'XETHZUSD',
    }
    
    # Minimum order sizes on Kraken
    MIN_ORDER = {
        'SOLUSD': 0.05,
        'PEPEUSD': 100000,
        'XDGUSD': 50,
        'XXBTZUSD': 0.00005,
        'XETHZUSD': 0.004,
    }
    
    def __init__(self):
        self.client = KrakenClient()
        self.momentum = MomentumScalper()
        self.mean_rev = MeanReversionTrader()
        self.grid = GridTrader()
        self.trade_log = []
        self.start_balance = 0
        self.data_dir = Path(__file__).parent / 'data' / 'trading'
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_portfolio(self) -> Dict:
        """Get current portfolio with USD values"""
        balances = self.client.balance()
        if not balances:
            return {'error': 'Could not fetch balance'}
        
        # Get prices for all held assets
        non_zero = {k: float(v) for k, v in balances.items() if float(v) > 0}
        
        pairs_to_check = []
        asset_to_pair = {}
        for asset in non_zero:
            for name, pair in self.TRADEABLE_PAIRS.items():
                kraken_names = {
                    'SOL': 'SOL', 'PEPE': 'PEPE', 'DOGE': 'XXDG',
                    'BTC': 'XXBT', 'ETH': 'XETH',
                }
                if asset == kraken_names.get(name, ''):
                    pairs_to_check.append(pair)
                    asset_to_pair[asset] = pair
        
        prices = self.client.ticker(pairs_to_check) if pairs_to_check else {}
        
        portfolio = []
        total_usd = 0
        for asset, amount in sorted(non_zero.items()):
            pair = asset_to_pair.get(asset)
            if pair:
                # Find price in ticker result
                price = 0
                for pname, pdata in prices.items():
                    if pair.replace('ZUSD', 'USD') in pname or pair in pname:
                        price = float(pdata['c'][0])
                        break
                value = amount * price
            elif asset in ('USDG', 'USD.HOLD', 'ZUSD'):
                price = 1.0
                value = amount
            else:
                price = 0
                value = 0
            
            total_usd += value
            portfolio.append({
                'asset': asset,
                'amount': amount,
                'price': price,
                'value_usd': round(value, 4),
            })
        
        return {
            'assets': portfolio,
            'total_usd': round(total_usd, 4),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    def analyze_market(self, pair: str = 'SOLUSD') -> Dict:
        """Full market analysis for a pair"""
        # Get OHLC data
        candles_5m = self.client.ohlc(pair, 5)
        candles_15m = self.client.ohlc(pair, 15)
        candles_1h = self.client.ohlc(pair, 60)
        
        # Extract close prices
        closes_5m = [float(c[4]) for c in candles_5m] if candles_5m else []
        closes_15m = [float(c[4]) for c in candles_15m] if candles_15m else []
        closes_1h = [float(c[4]) for c in candles_1h] if candles_1h else []
        
        current = closes_5m[-1] if closes_5m else 0
        
        ta = TechAnalysis
        
        analysis = {
            'pair': pair,
            'price': current,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'timeframes': {}
        }
        
        for name, closes in [('5m', closes_5m), ('15m', closes_15m), ('1h', closes_1h)]:
            if len(closes) < 20:
                continue
            
            rsi = ta.rsi(closes)
            ema_short = ta.ema(closes, 5)
            ema_long = ta.ema(closes, 15)
            bb = ta.bollinger_bands(closes)
            mom = ta.momentum(closes, 5)
            
            trend = 'neutral'
            if ema_short and ema_long:
                if ema_short > ema_long:
                    trend = 'bullish'
                elif ema_short < ema_long:
                    trend = 'bearish'
            
            analysis['timeframes'][name] = {
                'rsi': round(rsi, 1) if rsi else None,
                'ema_short': round(ema_short, 4) if ema_short else None,
                'ema_long': round(ema_long, 4) if ema_long else None,
                'bb_lower': round(bb[0], 4) if bb else None,
                'bb_mid': round(bb[1], 4) if bb else None,
                'bb_upper': round(bb[2], 4) if bb else None,
                'momentum': round(mom, 2) if mom else None,
                'trend': trend,
                'candle_count': len(closes),
            }
        
        # Orderbook analysis
        book = self.client.orderbook(pair, 5)
        if book:
            bids = book.get('bids', [])
            asks = book.get('asks', [])
            if bids and asks:
                best_bid = float(bids[0][0])
                best_ask = float(asks[0][0])
                spread = (best_ask - best_bid) / best_bid * 100
                bid_depth = sum(float(b[1]) for b in bids)
                ask_depth = sum(float(a[1]) for a in asks)
                
                analysis['orderbook'] = {
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread_pct': round(spread, 4),
                    'bid_depth': round(bid_depth, 4),
                    'ask_depth': round(ask_depth, 4),
                    'bid_ask_ratio': round(bid_depth / ask_depth, 2) if ask_depth > 0 else 0,
                }
        
        # Overall signal
        bullish_count = sum(1 for tf in analysis['timeframes'].values() if tf.get('trend') == 'bullish')
        bearish_count = sum(1 for tf in analysis['timeframes'].values() if tf.get('trend') == 'bearish')
        
        if bullish_count > bearish_count:
            analysis['overall'] = 'BULLISH'
        elif bearish_count > bullish_count:
            analysis['overall'] = 'BEARISH'
        else:
            analysis['overall'] = 'NEUTRAL'
        
        return analysis
    
    def find_best_opportunity(self) -> Dict:
        """Analyze all tradeable pairs and find best opportunity"""
        portfolio = self.get_portfolio()
        available_usd = portfolio.get('total_usd', 0)
        
        opportunities = []
        
        for name, pair in self.TRADEABLE_PAIRS.items():
            try:
                analysis = self.analyze_market(pair)
                
                # Get close prices for strategy signals
                candles = self.client.ohlc(pair, 5)
                closes = [float(c[4]) for c in candles] if candles else []
                current = closes[-1] if closes else 0
                
                if len(closes) < 20:
                    continue
                
                # Get signals from all strategies
                mom_signal = self.momentum.analyze(closes, current, pair, available_usd)
                mr_signal = self.mean_rev.analyze(closes, current, pair, available_usd)
                
                best_signal = mom_signal if mom_signal.confidence > mr_signal.confidence else mr_signal
                
                opportunities.append({
                    'pair': pair,
                    'name': name,
                    'price': current,
                    'signal': best_signal.action,
                    'confidence': best_signal.confidence,
                    'reason': best_signal.reason,
                    'strategy': best_signal.strategy,
                    'overall_trend': analysis.get('overall', 'NEUTRAL'),
                    'spread': analysis.get('orderbook', {}).get('spread_pct', 999),
                })
                
                time.sleep(0.5)  # Rate limit
                
            except Exception as e:
                logger.error(f"Error analyzing {pair}: {e}")
        
        # Sort by confidence
        opportunities.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'portfolio': portfolio,
            'opportunities': opportunities,
            'best': opportunities[0] if opportunities else None,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
    
    def execute_trade(self, pair: str, side: str, order_type: str = 'market',
                      volume: float = 0, price: float = None,
                      validate_only: bool = True) -> Dict:
        """
        Execute a trade. Set validate_only=False for live execution.
        """
        if validate_only:
            logger.info(f"VALIDATE: {side} {volume} {pair} @ {order_type} {price or 'market'}")
        else:
            logger.info(f"EXECUTE: {side} {volume} {pair} @ {order_type} {price or 'market'}")
        
        result = self.client.place_order(
            pair=pair,
            side=side,
            order_type=order_type,
            volume=volume,
            price=price,
            validate=validate_only,
        )
        
        # Log trade
        trade_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'pair': pair,
            'side': side,
            'type': order_type,
            'volume': volume,
            'price': price,
            'validate_only': validate_only,
            'result': result,
        }
        self.trade_log.append(trade_entry)
        
        # Save to file
        log_file = self.data_dir / f"trades_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        with open(log_file, 'a') as f:
            f.write(json.dumps(trade_entry) + '\n')
        
        return result
    
    def run_scan(self) -> str:
        """Run a full market scan and return formatted report"""
        lines = []
        lines.append("=" * 60)
        lines.append("  RIMURU TRADING BOT - MARKET SCAN")
        lines.append("=" * 60)
        
        # Portfolio
        portfolio = self.get_portfolio()
        lines.append(f"\n  Portfolio: ${portfolio.get('total_usd', 0):.2f}")
        for a in portfolio.get('assets', []):
            if a['value_usd'] > 0.01:
                lines.append(f"    {a['asset']}: {a['amount']:.8f} (${a['value_usd']:.4f})")
        
        # Scan all pairs
        lines.append(f"\n  {'Pair':<12} {'Price':>12} {'Trend':>10} {'RSI':>6} {'Signal':>10} {'Conf':>6}")
        lines.append(f"  {'-'*12} {'-'*12} {'-'*10} {'-'*6} {'-'*10} {'-'*6}")
        
        best_opp = None
        best_conf = 0
        
        for name, pair in self.TRADEABLE_PAIRS.items():
            try:
                analysis = self.analyze_market(pair)
                candles = self.client.ohlc(pair, 5)
                closes = [float(c[4]) for c in candles] if candles else []
                current = closes[-1] if closes else 0
                
                if len(closes) < 20:
                    lines.append(f"  {pair:<12} {'N/A':>12} {'N/A':>10} {'N/A':>6} {'N/A':>10} {'N/A':>6}")
                    time.sleep(0.3)
                    continue
                
                rsi = TechAnalysis.rsi(closes)
                trend = analysis.get('overall', '?')
                
                mom_sig = self.momentum.analyze(closes, current, pair, portfolio.get('total_usd', 0))
                
                signal_str = mom_sig.action.upper()
                conf_str = f"{mom_sig.confidence:.0%}"
                
                lines.append(f"  {pair:<12} ${current:>10.4f} {trend:>10} {rsi:>5.0f} {signal_str:>10} {conf_str:>6}")
                
                if mom_sig.confidence > best_conf and mom_sig.action == 'buy':
                    best_conf = mom_sig.confidence
                    best_opp = {'pair': pair, 'signal': mom_sig}
                
                time.sleep(0.3)
            except Exception as e:
                lines.append(f"  {pair:<12} ERROR: {e}")
        
        if best_opp:
            sig = best_opp['signal']
            lines.append(f"\n  BEST OPPORTUNITY: {sig.action.upper()} {best_opp['pair']}")
            lines.append(f"  Reason: {sig.reason}")
            lines.append(f"  Confidence: {sig.confidence:.0%}")
        else:
            lines.append(f"\n  No strong opportunities right now. Market is quiet.")
        
        lines.append(f"\n{'='*60}")
        
        report = '\n'.join(lines)
        print(report)
        
        # Save report
        (self.data_dir / 'latest_scan.txt').write_text(report)
        
        return report


# ============================================
# CLI Interface
# ============================================
if __name__ == "__main__":
    import sys
    
    bot = TradingBot()
    
    if len(sys.argv) < 2 or sys.argv[1] == 'scan':
        bot.run_scan()
    
    elif sys.argv[1] == 'portfolio':
        p = bot.get_portfolio()
        print(json.dumps(p, indent=2))
    
    elif sys.argv[1] == 'analyze':
        pair = sys.argv[2] if len(sys.argv) > 2 else 'SOLUSD'
        a = bot.analyze_market(pair)
        print(json.dumps(a, indent=2))
    
    elif sys.argv[1] == 'opportunity':
        o = bot.find_best_opportunity()
        print(json.dumps(o, indent=2))
    
    elif sys.argv[1] == 'trade':
        # trade <pair> <buy/sell> <amount> [price]
        if len(sys.argv) < 5:
            print("Usage: trade <pair> <buy|sell> <volume> [price]")
            print("  Example: trade SOLUSD buy 0.1")
            print("  Example: trade SOLUSD sell 0.1 90.50")
            sys.exit(1)
        pair = sys.argv[2]
        side = sys.argv[3]
        vol = float(sys.argv[4])
        price = float(sys.argv[5]) if len(sys.argv) > 5 else None
        otype = 'limit' if price else 'market'
        
        # Validate first
        print(f"Validating: {side} {vol} {pair} @ {otype}...")
        r = bot.execute_trade(pair, side, otype, vol, price, validate_only=True)
        print(f"Validation: {json.dumps(r, indent=2)}")
        
        if not r.get('error'):
            confirm = input("Execute for real? (yes/no): ")
            if confirm.lower() == 'yes':
                r = bot.execute_trade(pair, side, otype, vol, price, validate_only=False)
                print(f"Result: {json.dumps(r, indent=2)}")
    
    else:
        print("Commands: scan | portfolio | analyze [pair] | opportunity | trade <pair> <buy|sell> <vol> [price]")
