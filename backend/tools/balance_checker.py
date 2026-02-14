"""
Exchange Balance Checker - Query balances across configured exchanges
Supports: Binance, Kraken, Coinbase, Bybit, OKX
"""

import os
import hmac
import hashlib
import time
import urllib.parse
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import json
import asyncio

# Try to import aiohttp, fall back to requests
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from dotenv import load_dotenv

# Load environment
load_dotenv()


@dataclass
class ExchangeBalance:
    """Balance for a single asset"""
    asset: str
    free: float
    locked: float
    total: float
    usd_value: float = 0.0


@dataclass
class ExchangeResult:
    """Result from exchange query"""
    exchange: str
    success: bool
    balances: List[ExchangeBalance]
    total_usd: float
    error: Optional[str] = None


class BalanceChecker:
    """Check balances across multiple exchanges"""
    
    # Approximate USD prices (would use real API in production)
    PRICES_USD = {
        'BTC': 67500.0,
        'ETH': 3450.0,
        'SOL': 145.0,
        'ADA': 0.65,
        'MATIC': 0.95,
        'LINK': 18.5,
        'DOT': 8.2,
        'AVAX': 42.0,
        'UNI': 12.5,
        'AAVE': 285.0,
        'CRV': 0.55,
        'XRP': 0.62,
        'LTC': 85.0,
        'DOGE': 0.12,
        'USDT': 1.0,
        'USDC': 1.0,
        'BUSD': 1.0,
        'USD': 1.0,
        'EUR': 1.08,
    }
    
    def __init__(self):
        self.results: Dict[str, ExchangeResult] = {}
        
        # Load API keys from environment
        self.binance_key = os.getenv('BINANCE_API_KEY', '')
        self.binance_secret = os.getenv('BINANCE_SECRET_KEY', '')
        
        self.kraken_key = os.getenv('KRAKEN_API_KEY', '')
        self.kraken_secret = os.getenv('KRAKEN_SECRET_KEY', '')
        
        self.coinbase_key = os.getenv('COINBASE_API_KEY', '')
        self.coinbase_secret = os.getenv('COINBASE_SECRET_KEY', '')
        self.coinbase_passphrase = os.getenv('COINBASE_PASSPHRASE', '')
        
        self.bybit_key = os.getenv('BYBIT_API_KEY', '')
        self.bybit_secret = os.getenv('BYBIT_SECRET_KEY', '')
        
        self.okx_key = os.getenv('OKX_API_KEY', '')
        self.okx_secret = os.getenv('OKX_SECRET_KEY', '')
        self.okx_passphrase = os.getenv('OKX_PASSPHRASE', '')
    
    def _get_usd_value(self, asset: str, amount: float) -> float:
        """Get USD value for an asset"""
        asset = asset.upper()
        price = self.PRICES_USD.get(asset, 0.0)
        return amount * price
    
    async def check_binance(self) -> ExchangeResult:
        """Check Binance balance"""
        if not self.binance_key or not self.binance_secret:
            return ExchangeResult(
                exchange='Binance',
                success=False,
                balances=[],
                total_usd=0.0,
                error='API keys not configured'
            )
        
        try:
            timestamp = int(time.time() * 1000)
            query_string = f'timestamp={timestamp}'
            signature = hmac.new(
                self.binance_secret.encode('utf-8'),
                query_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            url = f'https://api.binance.com/api/v3/account?{query_string}&signature={signature}'
            headers = {'X-MBX-APIKEY': self.binance_key}
            
            if HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            data = await response.json()
                        else:
                            error_text = await response.text()
                            return ExchangeResult(
                                exchange='Binance',
                                success=False,
                                balances=[],
                                total_usd=0.0,
                                error=f'API error: {response.status} - {error_text[:100]}'
                            )
            elif HAS_REQUESTS:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                else:
                    return ExchangeResult(
                        exchange='Binance',
                        success=False,
                        balances=[],
                        total_usd=0.0,
                        error=f'API error: {response.status_code}'
                    )
            else:
                return ExchangeResult(
                    exchange='Binance',
                    success=False,
                    balances=[],
                    total_usd=0.0,
                    error='No HTTP library available'
                )
            
            balances = []
            total_usd = 0.0
            
            for balance in data.get('balances', []):
                free = float(balance.get('free', 0))
                locked = float(balance.get('locked', 0))
                total = free + locked
                
                if total > 0:
                    usd_value = self._get_usd_value(balance['asset'], total)
                    total_usd += usd_value
                    
                    balances.append(ExchangeBalance(
                        asset=balance['asset'],
                        free=free,
                        locked=locked,
                        total=total,
                        usd_value=usd_value
                    ))
            
            return ExchangeResult(
                exchange='Binance',
                success=True,
                balances=sorted(balances, key=lambda x: x.usd_value, reverse=True),
                total_usd=total_usd
            )
            
        except Exception as e:
            return ExchangeResult(
                exchange='Binance',
                success=False,
                balances=[],
                total_usd=0.0,
                error=str(e)
            )
    
    async def check_kraken(self) -> ExchangeResult:
        """Check Kraken balance"""
        if not self.kraken_key or not self.kraken_secret:
            return ExchangeResult(
                exchange='Kraken',
                success=False,
                balances=[],
                total_usd=0.0,
                error='API keys not configured'
            )
        
        try:
            import base64
            
            nonce = str(int(time.time() * 1000))
            url_path = '/0/private/Balance'
            post_data = f'nonce={nonce}'
            
            sha256_hash = hashlib.sha256((nonce + post_data).encode('utf-8')).digest()
            hmac_digest = hmac.new(
                base64.b64decode(self.kraken_secret),
                url_path.encode('utf-8') + sha256_hash,
                hashlib.sha512
            ).digest()
            signature = base64.b64encode(hmac_digest).decode('utf-8')
            
            url = f'https://api.kraken.com{url_path}'
            headers = {
                'API-Key': self.kraken_key,
                'API-Sign': signature,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            if HAS_REQUESTS:
                response = requests.post(url, headers=headers, data=post_data, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('error'):
                        return ExchangeResult(
                            exchange='Kraken',
                            success=False,
                            balances=[],
                            total_usd=0.0,
                            error=str(data['error'])
                        )
                else:
                    return ExchangeResult(
                        exchange='Kraken',
                        success=False,
                        balances=[],
                        total_usd=0.0,
                        error=f'API error: {response.status_code}'
                    )
            else:
                return ExchangeResult(
                    exchange='Kraken',
                    success=False,
                    balances=[],
                    total_usd=0.0,
                    error='requests library not available'
                )
            
            balances = []
            total_usd = 0.0
            
            # Kraken uses different asset names
            kraken_to_standard = {
                'XXBT': 'BTC', 'XETH': 'ETH', 'ZUSD': 'USD',
                'XXRP': 'XRP', 'XLTC': 'LTC', 'XXLM': 'XLM',
            }
            
            for asset, amount in data.get('result', {}).items():
                amount = float(amount)
                if amount > 0:
                    standard_asset = kraken_to_standard.get(asset, asset)
                    usd_value = self._get_usd_value(standard_asset, amount)
                    total_usd += usd_value
                    
                    balances.append(ExchangeBalance(
                        asset=standard_asset,
                        free=amount,
                        locked=0.0,
                        total=amount,
                        usd_value=usd_value
                    ))
            
            return ExchangeResult(
                exchange='Kraken',
                success=True,
                balances=sorted(balances, key=lambda x: x.usd_value, reverse=True),
                total_usd=total_usd
            )
            
        except Exception as e:
            return ExchangeResult(
                exchange='Kraken',
                success=False,
                balances=[],
                total_usd=0.0,
                error=str(e)
            )
    
    async def check_all(self) -> Dict[str, ExchangeResult]:
        """Check all configured exchanges"""
        
        print("Checking exchange balances...")
        print("=" * 50)
        
        # Check each exchange
        self.results['Binance'] = await self.check_binance()
        self.results['Kraken'] = await self.check_kraken()
        # Add more exchanges as needed
        
        return self.results
    
    def print_summary(self):
        """Print balance summary"""
        
        total_portfolio = 0.0
        
        for exchange, result in self.results.items():
            print(f"\n{exchange}:")
            print("-" * 30)
            
            if result.success:
                if result.balances:
                    for bal in result.balances[:10]:  # Top 10 assets
                        print(f"  {bal.asset}: {bal.total:.6f} (${bal.usd_value:.2f})")
                    
                    if len(result.balances) > 10:
                        print(f"  ... and {len(result.balances) - 10} more assets")
                    
                    print(f"  TOTAL: ${result.total_usd:,.2f}")
                    total_portfolio += result.total_usd
                else:
                    print("  No balances found")
            else:
                print(f"  ERROR: {result.error}")
        
        print("\n" + "=" * 50)
        print(f"TOTAL PORTFOLIO VALUE: ${total_portfolio:,.2f}")
        print("=" * 50)
        
        return total_portfolio
    
    def export_report(self, output_path: str):
        """Export balance report to JSON"""
        
        report = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'exchanges': {},
            'total_usd': 0.0
        }
        
        for exchange, result in self.results.items():
            report['exchanges'][exchange] = {
                'success': result.success,
                'total_usd': result.total_usd,
                'balances': [
                    {
                        'asset': b.asset,
                        'free': b.free,
                        'locked': b.locked,
                        'total': b.total,
                        'usd_value': b.usd_value
                    }
                    for b in result.balances
                ],
                'error': result.error
            }
            report['total_usd'] += result.total_usd
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\nReport exported to: {output_path}")


# CLI
if __name__ == "__main__":
    async def main():
        checker = BalanceChecker()
        await checker.check_all()
        total = checker.print_summary()
        
        # Export report
        checker.export_report('balance_report.json')
        
        return total
    
    asyncio.run(main())
