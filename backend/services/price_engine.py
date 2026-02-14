#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Price Engine Core
=========================================
Multi-source real-time cryptocurrency price engine with caching,
historical tracking, alerts, and portfolio valuation.

This is the CORE engine - handles all price data fetching, normalization,
caching, and storage. Used by both the standalone service and the API gateway.

Sources:
  1. CoinGecko (free, 30 calls/min)
  2. CoinCap (free, no key needed)
  3. Kraken (free, public API)
  4. Etherscan (ETH gas + prices)
  5. Blockchain.info (BTC price)
"""

import asyncio
import aiohttp
import sqlite3
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s"
)
logger = logging.getLogger("price_engine")


# ============================================================================
# DATA MODELS
# ============================================================================

class PriceSource(Enum):
    """Available price data sources"""
    COINGECKO = "coingecko"
    COINCAP = "coincap"
    KRAKEN = "kraken"
    ETHERSCAN = "etherscan"
    BLOCKCHAIN_INFO = "blockchain_info"
    AGGREGATE = "aggregate"  # Weighted average of all sources


class TimeFrame(Enum):
    """Chart/history time frames"""
    MINUTE_1 = "1m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    HOUR_1 = "1h"
    HOUR_4 = "4h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


class AlertType(Enum):
    """Price alert types"""
    ABOVE = "above"
    BELOW = "below"
    PERCENT_CHANGE = "percent_change"
    VOLUME_SPIKE = "volume_spike"


@dataclass
class PricePoint:
    """Single price data point"""
    symbol: str
    price_usd: float
    price_btc: float
    price_eth: float
    volume_24h: float
    market_cap: float
    change_1h: float
    change_24h: float
    change_7d: float
    change_30d: float
    high_24h: float
    low_24h: float
    ath: float
    ath_date: str
    circulating_supply: float
    total_supply: float
    source: str
    timestamp: str
    rank: int = 0
    name: str = ""
    image_url: str = ""


@dataclass
class GasPrice:
    """Ethereum gas price data"""
    slow_gwei: float
    standard_gwei: float
    fast_gwei: float
    rapid_gwei: float
    base_fee_gwei: float
    estimated_cost_usd: Dict[str, float]  # tx type -> cost
    timestamp: str
    source: str


@dataclass
class PriceAlert:
    """Price alert configuration"""
    id: str
    symbol: str
    alert_type: AlertType
    threshold: float
    current_value: float
    triggered: bool
    triggered_at: Optional[str]
    created_at: str
    message: str


@dataclass
class PortfolioPosition:
    """Single portfolio position"""
    symbol: str
    amount: float
    avg_buy_price: float
    current_price: float
    value_usd: float
    pnl_usd: float
    pnl_percent: float
    allocation_percent: float


@dataclass
class PortfolioSummary:
    """Full portfolio summary"""
    total_value_usd: float
    total_cost_basis: float
    total_pnl_usd: float
    total_pnl_percent: float
    positions: List[PortfolioPosition]
    last_updated: str
    best_performer: str
    worst_performer: str


# ============================================================================
# PRICE DATABASE
# ============================================================================

class PriceDatabase:
    """SQLite database for price history, alerts, and portfolio"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).parent.parent.parent / "data" / "prices.db")
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price_usd REAL NOT NULL,
                price_btc REAL,
                volume_24h REAL,
                market_cap REAL,
                change_24h REAL,
                source TEXT,
                timestamp TEXT NOT NULL,
                UNIQUE(symbol, timestamp, source)
            );
            
            CREATE TABLE IF NOT EXISTS price_cache (
                symbol TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                ttl_seconds INTEGER DEFAULT 60
            );
            
            CREATE TABLE IF NOT EXISTS gas_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slow_gwei REAL,
                standard_gwei REAL,
                fast_gwei REAL,
                base_fee_gwei REAL,
                timestamp TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS price_alerts (
                id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                threshold REAL NOT NULL,
                triggered INTEGER DEFAULT 0,
                triggered_at TEXT,
                created_at TEXT NOT NULL,
                message TEXT
            );
            
            CREATE TABLE IF NOT EXISTS portfolio (
                symbol TEXT PRIMARY KEY,
                amount REAL NOT NULL DEFAULT 0,
                avg_buy_price REAL NOT NULL DEFAULT 0,
                last_updated TEXT
            );
            
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                added_at TEXT NOT NULL,
                notes TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_price_symbol ON price_history(symbol);
            CREATE INDEX IF NOT EXISTS idx_price_timestamp ON price_history(timestamp);
            CREATE INDEX IF NOT EXISTS idx_price_source ON price_history(source);
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Price database initialized: {self.db_path}")
    
    def save_price(self, price: PricePoint):
        """Save a price point to history"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO price_history 
                   (symbol, price_usd, price_btc, volume_24h, market_cap, change_24h, source, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (price.symbol, price.price_usd, price.price_btc, price.volume_24h,
                 price.market_cap, price.change_24h, price.source, price.timestamp)
            )
            conn.commit()
        finally:
            conn.close()
    
    def save_prices_batch(self, prices: List[PricePoint]):
        """Save multiple price points in a single transaction"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """INSERT OR REPLACE INTO price_history 
                   (symbol, price_usd, price_btc, volume_24h, market_cap, change_24h, source, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [(p.symbol, p.price_usd, p.price_btc, p.volume_24h,
                  p.market_cap, p.change_24h, p.source, p.timestamp) for p in prices]
            )
            conn.commit()
        finally:
            conn.close()
    
    def cache_price(self, symbol: str, data: dict, ttl: int = 60):
        """Cache price data with TTL"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT OR REPLACE INTO price_cache (symbol, data_json, updated_at, ttl_seconds)
                   VALUES (?, ?, ?, ?)""",
                (symbol.upper(), json.dumps(data), datetime.utcnow().isoformat(), ttl)
            )
            conn.commit()
        finally:
            conn.close()
    
    def get_cached_price(self, symbol: str) -> Optional[dict]:
        """Get cached price if not expired"""
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT data_json, updated_at, ttl_seconds FROM price_cache WHERE symbol = ?",
                (symbol.upper(),)
            ).fetchone()
            
            if not row:
                return None
            
            data, updated_at, ttl = row
            age = (datetime.utcnow() - datetime.fromisoformat(updated_at)).total_seconds()
            
            if age > ttl:
                return None
            
            return json.loads(data)
        finally:
            conn.close()
    
    def get_price_history(self, symbol: str, hours: int = 24) -> List[dict]:
        """Get price history for a symbol"""
        conn = sqlite3.connect(self.db_path)
        try:
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            rows = conn.execute(
                """SELECT price_usd, volume_24h, change_24h, source, timestamp 
                   FROM price_history 
                   WHERE symbol = ? AND timestamp > ?
                   ORDER BY timestamp ASC""",
                (symbol.upper(), since)
            ).fetchall()
            
            return [
                {"price": r[0], "volume": r[1], "change": r[2], "source": r[3], "time": r[4]}
                for r in rows
            ]
        finally:
            conn.close()
    
    def save_gas(self, gas: GasPrice):
        """Save gas price data"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """INSERT INTO gas_history (slow_gwei, standard_gwei, fast_gwei, base_fee_gwei, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (gas.slow_gwei, gas.standard_gwei, gas.fast_gwei, gas.base_fee_gwei, gas.timestamp)
            )
            conn.commit()
        finally:
            conn.close()


# ============================================================================
# PRICE SOURCE ADAPTERS
# ============================================================================

class CoinGeckoAdapter:
    """CoinGecko free API adapter (30 calls/min)"""
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Map common symbols to CoinGecko IDs
    SYMBOL_MAP = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "ADA": "cardano", "DOT": "polkadot", "AVAX": "avalanche-2",
        "MATIC": "matic-network", "LINK": "chainlink", "UNI": "uniswap",
        "AAVE": "aave", "CRV": "curve-dao-token", "DOGE": "dogecoin",
        "XRP": "ripple", "LTC": "litecoin", "ATOM": "cosmos",
        "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
        "OP": "optimism", "FTM": "fantom", "ALGO": "algorand",
        "XLM": "stellar", "VET": "vechain", "HBAR": "hedera-hashgraph",
        "ICP": "internet-computer", "FIL": "filecoin", "SAND": "the-sandbox",
        "MANA": "decentraland", "AXS": "axie-infinity", "SHIB": "shiba-inu",
        "LDO": "lido-dao", "MKR": "maker", "SNX": "havven",
        "COMP": "compound-governance-token", "YFI": "yearn-finance",
        "SUSHI": "sushi", "1INCH": "1inch", "BAL": "balancer",
        "ENS": "ethereum-name-service", "GRT": "the-graph",
        "USDT": "tether", "USDC": "usd-coin", "DAI": "dai",
        "WBTC": "wrapped-bitcoin", "WETH": "weth",
        "BNB": "binancecoin", "TRX": "tron", "TON": "the-open-network",
        "PEPE": "pepe", "WIF": "dogwifcoin", "BONK": "bonk",
        "RENDER": "render-token", "INJ": "injective-protocol",
        "SUI": "sui", "SEI": "sei-network", "TIA": "celestia",
        "JUP": "jupiter-exchange-solana", "PYTH": "pyth-network",
        "JTO": "jito-governance-token", "WLD": "worldcoin-wld",
        "STRK": "starknet", "BLUR": "blur",
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self._last_call = 0
        self._rate_limit = 2.0  # seconds between calls
    
    async def _rate_limited_get(self, url: str, params: dict = None) -> dict:
        """Rate-limited GET request"""
        elapsed = time.time() - self._last_call
        if elapsed < self._rate_limit:
            await asyncio.sleep(self._rate_limit - elapsed)
        
        self._last_call = time.time()
        async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 429:
                logger.warning("CoinGecko rate limited, waiting 60s...")
                await asyncio.sleep(60)
                return await self._rate_limited_get(url, params)
            resp.raise_for_status()
            return await resp.json()
    
    def _get_id(self, symbol: str) -> str:
        """Convert symbol to CoinGecko ID"""
        return self.SYMBOL_MAP.get(symbol.upper(), symbol.lower())
    
    async def get_price(self, symbol: str) -> Optional[PricePoint]:
        """Get current price for a single symbol"""
        coin_id = self._get_id(symbol)
        try:
            data = await self._rate_limited_get(
                f"{self.BASE_URL}/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "false"
                }
            )
            
            market = data.get("market_data", {})
            
            return PricePoint(
                symbol=symbol.upper(),
                name=data.get("name", ""),
                price_usd=market.get("current_price", {}).get("usd", 0),
                price_btc=market.get("current_price", {}).get("btc", 0),
                price_eth=market.get("current_price", {}).get("eth", 0),
                volume_24h=market.get("total_volume", {}).get("usd", 0),
                market_cap=market.get("market_cap", {}).get("usd", 0),
                change_1h=market.get("price_change_percentage_1h_in_currency", {}).get("usd", 0),
                change_24h=market.get("price_change_percentage_24h", 0),
                change_7d=market.get("price_change_percentage_7d", 0),
                change_30d=market.get("price_change_percentage_30d", 0),
                high_24h=market.get("high_24h", {}).get("usd", 0),
                low_24h=market.get("low_24h", {}).get("usd", 0),
                ath=market.get("ath", {}).get("usd", 0),
                ath_date=str(market.get("ath_date", {}).get("usd", "")),
                circulating_supply=market.get("circulating_supply", 0) or 0,
                total_supply=market.get("total_supply", 0) or 0,
                rank=data.get("market_cap_rank", 0) or 0,
                image_url=data.get("image", {}).get("small", ""),
                source=PriceSource.COINGECKO.value,
                timestamp=datetime.utcnow().isoformat() + "Z",
            )
        except Exception as e:
            logger.error(f"CoinGecko error for {symbol}: {e}")
            return None
    
    async def get_prices_batch(self, symbols: List[str]) -> List[PricePoint]:
        """Get prices for multiple symbols in one call"""
        ids = ",".join(self._get_id(s) for s in symbols)
        try:
            data = await self._rate_limited_get(
                f"{self.BASE_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ids,
                    "order": "market_cap_desc",
                    "per_page": 250,
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h,7d,30d"
                }
            )
            
            prices = []
            for coin in data:
                symbol = coin.get("symbol", "").upper()
                prices.append(PricePoint(
                    symbol=symbol,
                    name=coin.get("name", ""),
                    price_usd=coin.get("current_price", 0) or 0,
                    price_btc=0,  # Not in markets endpoint
                    price_eth=0,
                    volume_24h=coin.get("total_volume", 0) or 0,
                    market_cap=coin.get("market_cap", 0) or 0,
                    change_1h=coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                    change_24h=coin.get("price_change_percentage_24h", 0) or 0,
                    change_7d=coin.get("price_change_percentage_7d_in_currency", 0) or 0,
                    change_30d=coin.get("price_change_percentage_30d_in_currency", 0) or 0,
                    high_24h=coin.get("high_24h", 0) or 0,
                    low_24h=coin.get("low_24h", 0) or 0,
                    ath=coin.get("ath", 0) or 0,
                    ath_date=str(coin.get("ath_date", "")),
                    circulating_supply=coin.get("circulating_supply", 0) or 0,
                    total_supply=coin.get("total_supply", 0) or 0,
                    rank=coin.get("market_cap_rank", 0) or 0,
                    image_url=coin.get("image", ""),
                    source=PriceSource.COINGECKO.value,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))
            
            return prices
        except Exception as e:
            logger.error(f"CoinGecko batch error: {e}")
            return []
    
    async def get_top_coins(self, limit: int = 100) -> List[PricePoint]:
        """Get top coins by market cap"""
        try:
            data = await self._rate_limited_get(
                f"{self.BASE_URL}/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": min(limit, 250),
                    "page": 1,
                    "sparkline": "false",
                    "price_change_percentage": "1h,24h,7d,30d"
                }
            )
            
            prices = []
            for coin in data:
                prices.append(PricePoint(
                    symbol=coin.get("symbol", "").upper(),
                    name=coin.get("name", ""),
                    price_usd=coin.get("current_price", 0) or 0,
                    price_btc=0,
                    price_eth=0,
                    volume_24h=coin.get("total_volume", 0) or 0,
                    market_cap=coin.get("market_cap", 0) or 0,
                    change_1h=coin.get("price_change_percentage_1h_in_currency", 0) or 0,
                    change_24h=coin.get("price_change_percentage_24h", 0) or 0,
                    change_7d=coin.get("price_change_percentage_7d_in_currency", 0) or 0,
                    change_30d=coin.get("price_change_percentage_30d_in_currency", 0) or 0,
                    high_24h=coin.get("high_24h", 0) or 0,
                    low_24h=coin.get("low_24h", 0) or 0,
                    ath=coin.get("ath", 0) or 0,
                    ath_date=str(coin.get("ath_date", "")),
                    circulating_supply=coin.get("circulating_supply", 0) or 0,
                    total_supply=coin.get("total_supply", 0) or 0,
                    rank=coin.get("market_cap_rank", 0) or 0,
                    image_url=coin.get("image", ""),
                    source=PriceSource.COINGECKO.value,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                ))
            
            return prices
        except Exception as e:
            logger.error(f"CoinGecko top coins error: {e}")
            return []


class CoinCapAdapter:
    """CoinCap.io API adapter (free, no key needed)"""
    
    BASE_URL = "https://api.coincap.io/v2"
    
    SYMBOL_MAP = {
        "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
        "ADA": "cardano", "DOT": "polkadot", "AVAX": "avalanche",
        "MATIC": "polygon", "LINK": "chainlink", "UNI": "uniswap",
        "DOGE": "dogecoin", "XRP": "xrp", "LTC": "litecoin",
        "BNB": "binance-coin", "SHIB": "shiba-inu",
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
    
    async def get_price(self, symbol: str) -> Optional[PricePoint]:
        """Get price from CoinCap"""
        asset_id = self.SYMBOL_MAP.get(symbol.upper(), symbol.lower())
        try:
            async with self.session.get(
                f"{self.BASE_URL}/assets/{asset_id}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    return None
                result = await resp.json()
                data = result.get("data", {})
                
                return PricePoint(
                    symbol=data.get("symbol", symbol).upper(),
                    name=data.get("name", ""),
                    price_usd=float(data.get("priceUsd", 0) or 0),
                    price_btc=0,
                    price_eth=0,
                    volume_24h=float(data.get("volumeUsd24Hr", 0) or 0),
                    market_cap=float(data.get("marketCapUsd", 0) or 0),
                    change_1h=0,
                    change_24h=float(data.get("changePercent24Hr", 0) or 0),
                    change_7d=0,
                    change_30d=0,
                    high_24h=0,
                    low_24h=0,
                    ath=0,
                    ath_date="",
                    circulating_supply=float(data.get("supply", 0) or 0),
                    total_supply=float(data.get("maxSupply", 0) or 0),
                    rank=int(data.get("rank", 0) or 0),
                    source=PriceSource.COINCAP.value,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
        except Exception as e:
            logger.error(f"CoinCap error for {symbol}: {e}")
            return None
    
    async def get_top_coins(self, limit: int = 100) -> List[PricePoint]:
        """Get top coins from CoinCap"""
        try:
            async with self.session.get(
                f"{self.BASE_URL}/assets",
                params={"limit": limit},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                result = await resp.json()
                prices = []
                for coin in result.get("data", []):
                    prices.append(PricePoint(
                        symbol=coin.get("symbol", "").upper(),
                        name=coin.get("name", ""),
                        price_usd=float(coin.get("priceUsd", 0) or 0),
                        price_btc=0,
                        price_eth=0,
                        volume_24h=float(coin.get("volumeUsd24Hr", 0) or 0),
                        market_cap=float(coin.get("marketCapUsd", 0) or 0),
                        change_1h=0,
                        change_24h=float(coin.get("changePercent24Hr", 0) or 0),
                        change_7d=0,
                        change_30d=0,
                        high_24h=0,
                        low_24h=0,
                        ath=0,
                        ath_date="",
                        circulating_supply=float(coin.get("supply", 0) or 0),
                        total_supply=float(coin.get("maxSupply", 0) or 0),
                        rank=int(coin.get("rank", 0) or 0),
                        source=PriceSource.COINCAP.value,
                        timestamp=datetime.utcnow().isoformat() + "Z",
                    ))
                return prices
        except Exception as e:
            logger.error(f"CoinCap top coins error: {e}")
            return []


class KrakenAdapter:
    """Kraken public API adapter (free, no key needed)"""
    
    BASE_URL = "https://api.kraken.com/0/public"
    
    SYMBOL_MAP = {
        "BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD",
        "ADA": "ADAUSD", "DOT": "DOTUSD", "LINK": "LINKUSD",
        "UNI": "UNIUSD", "DOGE": "DOGEUSD", "XRP": "XRPUSD",
        "LTC": "LTCUSD", "AVAX": "AVAXUSD", "MATIC": "MATICUSD",
        "ATOM": "ATOMUSD", "AAVE": "AAVEUSD", "ALGO": "ALGOUSD",
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
    
    async def get_price(self, symbol: str) -> Optional[PricePoint]:
        """Get price from Kraken"""
        pair = self.SYMBOL_MAP.get(symbol.upper())
        if not pair:
            return None
        
        try:
            async with self.session.get(
                f"{self.BASE_URL}/Ticker",
                params={"pair": pair},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                
                if data.get("error"):
                    return None
                
                result = data.get("result", {})
                ticker = list(result.values())[0] if result else {}
                
                last_price = float(ticker.get("c", [0])[0])
                volume = float(ticker.get("v", [0, 0])[1])  # 24h volume
                high = float(ticker.get("h", [0, 0])[1])
                low = float(ticker.get("l", [0, 0])[1])
                open_price = float(ticker.get("o", 0))
                
                change_24h = ((last_price - open_price) / open_price * 100) if open_price else 0
                
                return PricePoint(
                    symbol=symbol.upper(),
                    price_usd=last_price,
                    price_btc=0,
                    price_eth=0,
                    volume_24h=volume * last_price,
                    market_cap=0,
                    change_1h=0,
                    change_24h=change_24h,
                    change_7d=0,
                    change_30d=0,
                    high_24h=high,
                    low_24h=low,
                    ath=0,
                    ath_date="",
                    circulating_supply=0,
                    total_supply=0,
                    source=PriceSource.KRAKEN.value,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
        except Exception as e:
            logger.error(f"Kraken error for {symbol}: {e}")
            return None


class EtherscanAdapter:
    """Etherscan adapter for ETH price and gas"""
    
    BASE_URL = "https://api.etherscan.io/api"
    
    def __init__(self, session: aiohttp.ClientSession, api_key: str = ""):
        self.session = session
        self.api_key = api_key
    
    async def get_eth_price(self) -> Optional[PricePoint]:
        """Get ETH price from Etherscan"""
        try:
            params = {"module": "stats", "action": "ethprice"}
            if self.api_key:
                params["apikey"] = self.api_key
            
            async with self.session.get(
                self.BASE_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                result = data.get("result", {})
                
                return PricePoint(
                    symbol="ETH",
                    name="Ethereum",
                    price_usd=float(result.get("ethusd", 0)),
                    price_btc=float(result.get("ethbtc", 0)),
                    price_eth=1.0,
                    volume_24h=0,
                    market_cap=0,
                    change_1h=0,
                    change_24h=0,
                    change_7d=0,
                    change_30d=0,
                    high_24h=0,
                    low_24h=0,
                    ath=0,
                    ath_date="",
                    circulating_supply=0,
                    total_supply=0,
                    source=PriceSource.ETHERSCAN.value,
                    timestamp=datetime.utcnow().isoformat() + "Z",
                )
        except Exception as e:
            logger.error(f"Etherscan price error: {e}")
            return None
    
    async def get_gas_prices(self) -> Optional[GasPrice]:
        """Get current gas prices"""
        try:
            params = {"module": "gastracker", "action": "gasoracle"}
            if self.api_key:
                params["apikey"] = self.api_key
            
            async with self.session.get(
                self.BASE_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                result = data.get("result", {})
                
                # Etherscan returns a string error when rate limited or no key
                if isinstance(result, str):
                    logger.warning(f"Etherscan gas returned string: {result}")
                    return None
                
                slow = float(result.get("SafeGasPrice", 0))
                standard = float(result.get("ProposeGasPrice", 0))
                fast = float(result.get("FastGasPrice", 0))
                base = float(result.get("suggestBaseFee", 0))
                
                # Estimate costs (21000 gas for simple transfer)
                eth_price_resp = await self.get_eth_price()
                eth_price = eth_price_resp.price_usd if eth_price_resp else 3000
                
                gas_limit_transfer = 21000
                gas_limit_swap = 150000
                gas_limit_nft = 250000
                
                def calc_cost(gwei, gas_limit):
                    return (gwei * gas_limit / 1e9) * eth_price
                
                return GasPrice(
                    slow_gwei=slow,
                    standard_gwei=standard,
                    fast_gwei=fast,
                    rapid_gwei=fast * 1.2,
                    base_fee_gwei=base,
                    estimated_cost_usd={
                        "transfer_slow": round(calc_cost(slow, gas_limit_transfer), 2),
                        "transfer_fast": round(calc_cost(fast, gas_limit_transfer), 2),
                        "swap_slow": round(calc_cost(slow, gas_limit_swap), 2),
                        "swap_fast": round(calc_cost(fast, gas_limit_swap), 2),
                        "nft_slow": round(calc_cost(slow, gas_limit_nft), 2),
                        "nft_fast": round(calc_cost(fast, gas_limit_nft), 2),
                    },
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    source=PriceSource.ETHERSCAN.value,
                )
        except Exception as e:
            logger.error(f"Etherscan gas error: {e}")
            return None
    
    async def get_wallet_balance(self, address: str) -> float:
        """Get ETH balance for a wallet"""
        try:
            params = {
                "module": "account",
                "action": "balance",
                "address": address,
                "tag": "latest"
            }
            if self.api_key:
                params["apikey"] = self.api_key
            
            async with self.session.get(
                self.BASE_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("status") == "1":
                    return int(data.get("result", 0)) / 1e18
                return 0
        except Exception as e:
            logger.error(f"Etherscan balance error: {e}")
            return 0


# ============================================================================
# PRICE ENGINE - CORE ORCHESTRATOR
# ============================================================================

class PriceEngine:
    """
    Central price engine that orchestrates all sources, caching,
    aggregation, alerts, and portfolio tracking.
    """
    
    # Default watchlist
    DEFAULT_WATCHLIST = [
        "BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC", "LINK",
        "UNI", "AAVE", "DOGE", "XRP", "LTC", "BNB", "ATOM", "NEAR",
        "ARB", "OP", "INJ", "SUI", "SEI", "TIA", "RENDER",
    ]
    
    def __init__(self, db_path: str = None, etherscan_key: str = ""):
        self.db = PriceDatabase(db_path)
        self.etherscan_key = etherscan_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._adapters: Dict[str, Any] = {}
        self._running = False
        self._update_interval = 60  # seconds
        self._alerts: List[PriceAlert] = []
        self._latest_prices: Dict[str, PricePoint] = {}
        self._latest_gas: Optional[GasPrice] = None
    
    async def start(self):
        """Initialize session and adapters"""
        self._session = aiohttp.ClientSession(
            headers={"Accept": "application/json"}
        )
        self._adapters = {
            "coingecko": CoinGeckoAdapter(self._session),
            "coincap": CoinCapAdapter(self._session),
            "kraken": KrakenAdapter(self._session),
            "etherscan": EtherscanAdapter(self._session, self.etherscan_key),
        }
        logger.info("Price engine started with 4 sources")
    
    async def stop(self):
        """Cleanup"""
        self._running = False
        if self._session:
            await self._session.close()
        logger.info("Price engine stopped")
    
    async def get_price(self, symbol: str, use_cache: bool = True) -> Optional[PricePoint]:
        """
        Get price for a symbol with multi-source fallback.
        Priority: Cache -> CoinGecko -> CoinCap -> Kraken -> Etherscan
        """
        symbol = symbol.upper()
        
        # Check cache first
        if use_cache:
            cached = self.db.get_cached_price(symbol)
            if cached:
                return PricePoint(**cached)
        
        # Check in-memory latest
        if symbol in self._latest_prices:
            return self._latest_prices[symbol]
        
        # Try sources in order
        price = None
        
        for source_name, adapter in self._adapters.items():
            try:
                if source_name == "etherscan":
                    if symbol == "ETH":
                        price = await adapter.get_eth_price()
                    else:
                        continue
                elif hasattr(adapter, "get_price"):
                    price = await adapter.get_price(symbol)
                
                if price and price.price_usd > 0:
                    logger.debug(f"Got {symbol} price from {source_name}: ${price.price_usd}")
                    break
            except Exception as e:
                logger.debug(f"Source {source_name} failed for {symbol}: {e}")
                continue
        
        if price:
            # Cache and store
            self.db.cache_price(symbol, asdict(price), ttl=60)
            self.db.save_price(price)
            self._latest_prices[symbol] = price
            
            # Check alerts
            await self._check_alerts(price)
        
        return price
    
    async def get_prices_batch(self, symbols: List[str]) -> Dict[str, PricePoint]:
        """Get prices for multiple symbols efficiently"""
        results = {}
        uncached = []
        
        # Check cache first
        for symbol in symbols:
            cached = self.db.get_cached_price(symbol.upper())
            if cached:
                results[symbol.upper()] = PricePoint(**cached)
            else:
                uncached.append(symbol)
        
        if uncached:
            # Try CoinGecko batch first
            try:
                batch = await self._adapters["coingecko"].get_prices_batch(uncached)
                for price in batch:
                    results[price.symbol] = price
                    self.db.cache_price(price.symbol, asdict(price))
                    self._latest_prices[price.symbol] = price
            except Exception as e:
                logger.error(f"Batch fetch failed: {e}")
                # Fall back to individual lookups
                for symbol in uncached:
                    if symbol.upper() not in results:
                        price = await self.get_price(symbol, use_cache=False)
                        if price:
                            results[symbol.upper()] = price
        
        # Save all to history
        self.db.save_prices_batch(list(results.values()))
        
        return results
    
    async def get_top_coins(self, limit: int = 50) -> List[PricePoint]:
        """Get top coins by market cap"""
        try:
            prices = await self._adapters["coingecko"].get_top_coins(limit)
            if prices:
                self.db.save_prices_batch(prices)
                for p in prices:
                    self._latest_prices[p.symbol] = p
                    self.db.cache_price(p.symbol, asdict(p))
            return prices
        except Exception:
            # Fallback to CoinCap
            return await self._adapters["coincap"].get_top_coins(limit)
    
    async def get_gas(self) -> Optional[GasPrice]:
        """Get current Ethereum gas prices"""
        gas = await self._adapters["etherscan"].get_gas_prices()
        if gas:
            self._latest_gas = gas
            self.db.save_gas(gas)
        return gas
    
    async def get_wallet_value(self, address: str) -> Dict[str, Any]:
        """Get wallet ETH balance and USD value"""
        balance = await self._adapters["etherscan"].get_wallet_balance(address)
        eth_price = await self.get_price("ETH")
        
        usd_value = balance * (eth_price.price_usd if eth_price else 0)
        
        return {
            "address": address,
            "balance_eth": balance,
            "eth_price": eth_price.price_usd if eth_price else 0,
            "value_usd": round(usd_value, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    
    async def get_price_history(self, symbol: str, hours: int = 24) -> List[dict]:
        """Get price history from database"""
        return self.db.get_price_history(symbol.upper(), hours)
    
    # ------ ALERTS ------
    
    def add_alert(self, symbol: str, alert_type: str, threshold: float, message: str = "") -> PriceAlert:
        """Add a price alert"""
        alert = PriceAlert(
            id=hashlib.md5(f"{symbol}{alert_type}{threshold}{time.time()}".encode()).hexdigest()[:12],
            symbol=symbol.upper(),
            alert_type=AlertType(alert_type),
            threshold=threshold,
            current_value=0,
            triggered=False,
            triggered_at=None,
            created_at=datetime.utcnow().isoformat() + "Z",
            message=message or f"{symbol} {alert_type} {threshold}",
        )
        self._alerts.append(alert)
        
        conn = sqlite3.connect(self.db.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO price_alerts (id, symbol, alert_type, threshold, created_at, message) VALUES (?, ?, ?, ?, ?, ?)",
            (alert.id, alert.symbol, alert.alert_type.value, alert.threshold, alert.created_at, alert.message)
        )
        conn.commit()
        conn.close()
        
        logger.info(f"Alert added: {alert.message}")
        return alert
    
    async def _check_alerts(self, price: PricePoint):
        """Check if any alerts should trigger"""
        for alert in self._alerts:
            if alert.triggered or alert.symbol != price.symbol:
                continue
            
            alert.current_value = price.price_usd
            triggered = False
            
            if alert.alert_type == AlertType.ABOVE and price.price_usd >= alert.threshold:
                triggered = True
            elif alert.alert_type == AlertType.BELOW and price.price_usd <= alert.threshold:
                triggered = True
            elif alert.alert_type == AlertType.PERCENT_CHANGE:
                if abs(price.change_24h) >= alert.threshold:
                    triggered = True
            
            if triggered:
                alert.triggered = True
                alert.triggered_at = datetime.utcnow().isoformat() + "Z"
                logger.warning(f"ALERT TRIGGERED: {alert.message} (${price.price_usd:,.2f})")
    
    def get_alerts(self) -> List[PriceAlert]:
        """Get all alerts"""
        return self._alerts
    
    # ------ PORTFOLIO ------
    
    async def update_portfolio(self, holdings: Dict[str, float]) -> PortfolioSummary:
        """
        Calculate portfolio value from holdings.
        holdings: {"BTC": 0.5, "ETH": 10, "SOL": 100}
        """
        symbols = list(holdings.keys())
        prices = await self.get_prices_batch(symbols)
        
        positions = []
        total_value = 0
        
        for symbol, amount in holdings.items():
            price = prices.get(symbol.upper())
            if not price:
                continue
            
            value = amount * price.price_usd
            total_value += value
            
            positions.append(PortfolioPosition(
                symbol=symbol.upper(),
                amount=amount,
                avg_buy_price=0,  # Would need trade history
                current_price=price.price_usd,
                value_usd=round(value, 2),
                pnl_usd=0,
                pnl_percent=price.change_24h,
                allocation_percent=0,  # Calculated below
            ))
        
        # Calculate allocation percentages
        for pos in positions:
            pos.allocation_percent = round((pos.value_usd / total_value * 100) if total_value else 0, 2)
        
        # Sort by value
        positions.sort(key=lambda p: p.value_usd, reverse=True)
        
        best = max(positions, key=lambda p: p.pnl_percent) if positions else None
        worst = min(positions, key=lambda p: p.pnl_percent) if positions else None
        
        return PortfolioSummary(
            total_value_usd=round(total_value, 2),
            total_cost_basis=0,
            total_pnl_usd=0,
            total_pnl_percent=0,
            positions=positions,
            last_updated=datetime.utcnow().isoformat() + "Z",
            best_performer=best.symbol if best else "",
            worst_performer=worst.symbol if worst else "",
        )
    
    # ------ CONTINUOUS LOOP ------
    
    async def run_continuous(self, interval: int = 60):
        """Run continuous price updates"""
        self._running = True
        self._update_interval = interval
        
        logger.info(f"Starting continuous price updates every {interval}s")
        
        cycle = 0
        while self._running:
            try:
                cycle += 1
                logger.info(f"Price update cycle #{cycle}")
                
                # Fetch top coins
                prices = await self.get_top_coins(50)
                logger.info(f"Updated {len(prices)} coin prices")
                
                # Fetch gas every 5 cycles
                if cycle % 5 == 0:
                    gas = await self.get_gas()
                    if gas:
                        logger.info(f"Gas: slow={gas.slow_gwei} standard={gas.standard_gwei} fast={gas.fast_gwei}")
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Update cycle error: {e}")
                await asyncio.sleep(interval)
        
        logger.info("Continuous updates stopped")


# ============================================================================
# STANDALONE CLI
# ============================================================================

async def main():
    """Standalone price engine demo"""
    print("=" * 70)
    print("  RIMURU CRYPTO EMPIRE - PRICE ENGINE")
    print("=" * 70)
    
    engine = PriceEngine()
    await engine.start()
    
    try:
        # Fetch top 25 coins
        print("\nFetching top 25 coins by market cap...\n")
        prices = await engine.get_top_coins(25)
        
        if prices:
            print(f"{'#':<4} {'Symbol':<8} {'Name':<18} {'Price':>14} {'24h %':>9} {'Market Cap':>16} {'Volume 24h':>16}")
            print("-" * 90)
            
            for p in prices:
                change_color = "+" if p.change_24h >= 0 else ""
                print(f"{p.rank:<4} {p.symbol:<8} {p.name[:17]:<18} ${p.price_usd:>12,.2f} "
                      f"{change_color}{p.change_24h:>7.2f}% ${p.market_cap:>14,.0f} ${p.volume_24h:>14,.0f}")
        
        # Gas prices
        print("\n" + "=" * 70)
        print("  ETHEREUM GAS PRICES")
        print("=" * 70)
        
        gas = await engine.get_gas()
        if gas:
            print(f"\n  Slow:     {gas.slow_gwei:.1f} gwei  (Transfer: ${gas.estimated_cost_usd.get('transfer_slow', 0):.2f})")
            print(f"  Standard: {gas.standard_gwei:.1f} gwei  (Transfer: ${gas.estimated_cost_usd.get('transfer_fast', 0):.2f})")
            print(f"  Fast:     {gas.fast_gwei:.1f} gwei")
            print(f"  Base Fee: {gas.base_fee_gwei:.1f} gwei")
            print(f"\n  Estimated Costs:")
            print(f"    Swap (slow):  ${gas.estimated_cost_usd.get('swap_slow', 0):.2f}")
            print(f"    Swap (fast):  ${gas.estimated_cost_usd.get('swap_fast', 0):.2f}")
            print(f"    NFT (slow):   ${gas.estimated_cost_usd.get('nft_slow', 0):.2f}")
            print(f"    NFT (fast):   ${gas.estimated_cost_usd.get('nft_fast', 0):.2f}")
        
        # Quick price checks
        print("\n" + "=" * 70)
        print("  INDIVIDUAL PRICE CHECKS")
        print("=" * 70)
        
        for symbol in ["BTC", "ETH", "SOL", "DOGE"]:
            price = await engine.get_price(symbol)
            if price:
                print(f"\n  {price.name} ({price.symbol}):")
                print(f"    Price:  ${price.price_usd:,.2f}")
                print(f"    24h:    {price.change_24h:+.2f}%")
                print(f"    7d:     {price.change_7d:+.2f}%")
                print(f"    ATH:    ${price.ath:,.2f}")
                print(f"    MCap:   ${price.market_cap:,.0f}")
        
        print("\n" + "=" * 70)
        print(f"  Database: {engine.db.db_path}")
        print(f"  Prices cached and stored to SQLite")
        print("=" * 70)
        
    finally:
        await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
