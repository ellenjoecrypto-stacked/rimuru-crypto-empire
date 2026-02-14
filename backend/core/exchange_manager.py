#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Exchange Manager
Unified interface for multiple cryptocurrency exchanges
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

try:
    import ccxt.async_support as ccxt
except ImportError:
    print("Installing ccxt...")
    import os
    os.system("pip install ccxt")
    import ccxt.async_support as ccxt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExchangeType(Enum):
    BINANCE = "binance"
    KRAKEN = "kraken"
    COINBASE = "coinbase"
    BYBIT = "bybit"
    OKX = "okx"

@dataclass
class ExchangeConfig:
    """Exchange configuration"""
    exchange_type: ExchangeType
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    sandbox: bool = False
    enable_rate_limit: bool = True
    timeout: int = 30000

@dataclass
class Ticker:
    """Market ticker data"""
    symbol: str
    last_price: float
    bid_price: float
    ask_price: float
    volume_24h: float
    timestamp: datetime

@dataclass
class Balance:
    """Account balance"""
    currency: str
    free: float
    used: float
    total: float

@dataclass
class Order:
    """Order information"""
    id: str
    symbol: str
    side: str
    type: str
    amount: float
    price: float
    status: str
    timestamp: datetime

class ExchangeManager:
    """
    Unified exchange manager supporting multiple exchanges
    
    Features:
    - Multi-exchange support via CCXT
    - Connection pooling
    - Rate limiting
    - Error handling and retries
    - Unified API interface
    """
    
    def __init__(self):
        self.exchanges: Dict[str, ccxt.Exchange] = {}
        self.exchange_configs: Dict[str, ExchangeConfig] = {}
        self.active_connections: Dict[str, bool] = {}
        
    async def add_exchange(self, name: str, config: ExchangeConfig) -> bool:
        """
        Add exchange connection
        
        Args:
            name: Unique identifier for this exchange
            config: Exchange configuration
            
        Returns:
            bool: Success status
        """
        try:
            # Create exchange instance
            exchange_class = getattr(ccxt, config.exchange_type.value)
            exchange = exchange_class({
                'apiKey': config.api_key,
                'secret': config.secret_key,
                'password': config.passphrase,
                'sandbox': config.sandbox,
                'enableRateLimit': config.enable_rate_limit,
                'timeout': config.timeout,
            })
            
            # Test connection
            await exchange.load_markets()
            
            # Store exchange
            self.exchanges[name] = exchange
            self.exchange_configs[name] = config
            self.active_connections[name] = True
            
            logger.info(f"✅ Exchange '{name}' ({config.exchange_type.value}) connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to exchange '{name}': {e}")
            self.active_connections[name] = False
            return False
    
    async def remove_exchange(self, name: str) -> bool:
        """Remove exchange connection"""
        if name in self.exchanges:
            await self.exchanges[name].close()
            del self.exchanges[name]
            del self.exchange_configs[name]
            del self.active_connections[name]
            logger.info(f"✅ Exchange '{name}' removed")
            return True
        return False
    
    async def get_ticker(self, exchange_name: str, symbol: str) -> Optional[Ticker]:
        """
        Get ticker for a symbol
        
        Args:
            exchange_name: Name of exchange
            symbol: Trading pair (e.g., 'BTC/USDT')
            
        Returns:
            Ticker object or None
        """
        try:
            exchange = self.exchanges[exchange_name]
            ticker_data = await exchange.fetch_ticker(symbol)
            
            return Ticker(
                symbol=symbol,
                last_price=ticker_data['last'],
                bid_price=ticker_data['bid'],
                ask_price=ticker_data['ask'],
                volume_24h=ticker_data['baseVolume'],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error fetching ticker for {symbol} on {exchange_name}: {e}")
            return None
    
    async def get_balance(self, exchange_name: str) -> Dict[str, Balance]:
        """Get account balance"""
        try:
            exchange = self.exchanges[exchange_name]
            balance_data = await exchange.fetch_balance()
            
            balances = {}
            for currency, data in balance_data.items():
                if currency not in ['info', 'datetime', 'timestamp', 'free', 'used', 'total']:
                    if data.get('total', 0) > 0:
                        balances[currency] = Balance(
                            currency=currency,
                            free=data.get('free', 0),
                            used=data.get('used', 0),
                            total=data.get('total', 0)
                        )
            
            return balances
            
        except Exception as e:
            logger.error(f"❌ Error fetching balance from {exchange_name}: {e}")
            return {}
    
    async def place_order(self, exchange_name: str, symbol: str, side: str, 
                         order_type: str, amount: float, price: Optional[float] = None) -> Optional[Order]:
        """
        Place an order
        
        Args:
            exchange_name: Name of exchange
            symbol: Trading pair
            side: 'buy' or 'sell'
            order_type: 'market', 'limit', etc.
            amount: Order amount
            price: Price (required for limit orders)
            
        Returns:
            Order object or None
        """
        try:
            exchange = self.exchanges[exchange_name]
            
            if order_type == 'market':
                order_data = await exchange.create_market_order(symbol, side, amount)
            elif order_type == 'limit':
                if price is None:
                    raise ValueError("Price required for limit orders")
                order_data = await exchange.create_limit_order(symbol, side, amount, price)
            else:
                raise ValueError(f"Unsupported order type: {order_type}")
            
            return Order(
                id=order_data['id'],
                symbol=order_data['symbol'],
                side=order_data['side'],
                type=order_data['type'],
                amount=order_data['amount'],
                price=order_data.get('price', 0),
                status=order_data['status'],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error placing order on {exchange_name}: {e}")
            return None
    
    async def cancel_order(self, exchange_name: str, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            exchange = self.exchanges[exchange_name]
            await exchange.cancel_order(order_id, symbol)
            logger.info(f"✅ Order {order_id} cancelled on {exchange_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Error cancelling order on {exchange_name}: {e}")
            return False
    
    async def get_open_orders(self, exchange_name: str, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders"""
        try:
            exchange = self.exchanges[exchange_name]
            orders_data = await exchange.fetch_open_orders(symbol)
            
            orders = []
            for order_data in orders_data:
                orders.append(Order(
                    id=order_data['id'],
                    symbol=order_data['symbol'],
                    side=order_data['side'],
                    type=order_data['type'],
                    amount=order_data['amount'],
                    price=order_data.get('price', 0),
                    status=order_data['status'],
                    timestamp=datetime.now()
                ))
            
            return orders
            
        except Exception as e:
            logger.error(f"❌ Error fetching open orders from {exchange_name}: {e}")
            return []
    
    async def get_trade_history(self, exchange_name: str, symbol: Optional[str] = None, 
                               limit: int = 100) -> List[Dict]:
        """Get trade history"""
        try:
            exchange = self.exchanges[exchange_name]
            trades = await exchange.fetch_my_trades(symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error(f"❌ Error fetching trade history from {exchange_name}: {e}")
            return []
    
    async def get_all_tickers(self, exchange_name: str) -> Dict[str, Ticker]:
        """Get all tickers from an exchange"""
        try:
            exchange = self.exchanges[exchange_name]
            tickers_data = await exchange.fetch_tickers()
            
            tickers = {}
            for symbol, data in tickers_data.items():
                if data.get('last'):
                    tickers[symbol] = Ticker(
                        symbol=symbol,
                        last_price=data['last'],
                        bid_price=data.get('bid', 0),
                        ask_price=data.get('ask', 0),
                        volume_24h=data.get('baseVolume', 0),
                        timestamp=datetime.now()
                    )
            
            return tickers
            
        except Exception as e:
            logger.error(f"❌ Error fetching all tickers from {exchange_name}: {e}")
            return {}
    
    async def get_connection_status(self, exchange_name: str) -> bool:
        """Check if exchange connection is active"""
        try:
            if exchange_name not in self.exchanges:
                return False
            await self.exchanges[exchange_name].load_markets()
            return True
        except:
            return False
    
    async def close_all_connections(self):
        """Close all exchange connections"""
        for name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                logger.info(f"✅ Closed connection to {name}")
            except Exception as e:
                logger.error(f"❌ Error closing connection to {name}: {e}")
        
        self.exchanges.clear()
        self.active_connections.clear()
    
    def get_exchange_info(self, exchange_name: str) -> Optional[Dict]:
        """Get exchange information"""
        if exchange_name in self.exchange_configs:
            config = self.exchange_configs[exchange_name]
            return {
                'name': exchange_name,
                'type': config.exchange_type.value,
                'sandbox': config.sandbox,
                'active': self.active_connections.get(exchange_name, False)
            }
        return None


# Example usage
if __name__ == "__main__":
    async def test_exchange_manager():
        print("🔄 EXCHANGE MANAGER TEST")
        print("=" * 60)
        
        manager = ExchangeManager()
        
        # Test with sandbox credentials (replace with your own)
        print("\n1. Adding exchange (sandbox mode)...")
        config = ExchangeConfig(
            exchange_type=ExchangeType.BINANCE,
            api_key="your_api_key",
            secret_key="your_secret_key",
            sandbox=True
        )
        
        # Note: This will fail with dummy credentials
        # success = await manager.add_exchange("test_binance", config)
        # if success:
        #     print("   ✅ Exchange added successfully")
        # else:
        #     print("   ⚠️  Could not add exchange (expected with dummy credentials)")
        
        print("\n2. Testing without credentials (read-only mode)...")
        # Create exchange without API keys for public data
        exchange = ccxt.binance({'enableRateLimit': True})
        try:
            ticker = await exchange.fetch_ticker('BTC/USDT')
            print(f"   ✅ BTC/USDT Price: ${ticker['last']:,.2f}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        finally:
            await exchange.close()
        
        print("\n" + "=" * 60)
        print("✅ Exchange manager test completed!")
    
    asyncio.run(test_exchange_manager())