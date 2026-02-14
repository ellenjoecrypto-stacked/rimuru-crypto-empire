#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Scanner + Price Pipeline
=================================================
Bridges the crypto scanner findings with the price engine.
Takes discovered wallets/tokens from scanner DB and enriches them
with live prices, portfolio valuation, and alert monitoring.

This is the glue between:
  - full_crypto_scanner.py (finds wallets/tokens in files)
  - price_engine.py (gets live prices from 4+ sources)
  - crypto_findings.db (scanner results)
  - prices.db (price history)
"""

import asyncio
import sqlite3
import json
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.price_engine import PriceEngine, PricePoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scanner_pipeline")

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
SCANNER_DB = BASE_DIR / "crypto_findings.db"
PRICES_DB = BASE_DIR / "data" / "prices.db"
REPORT_PATH = BASE_DIR / "data" / "enriched_scan_report.json"


class ScannerPricePipeline:
    """
    Pipeline that:
    1. Reads scanner findings (wallets, tokens discovered)
    2. Gets live prices for all discovered tokens
    3. Checks wallet balances with current ETH price
    4. Generates enriched report with USD values
    5. Sets up alerts for tokens found in projects
    """
    
    def __init__(self):
        self.engine: PriceEngine = None
        self.scanner_db_path = str(SCANNER_DB)
        self.discovered_tokens: List[str] = []
        self.discovered_wallets: List[str] = []
        self.enriched_data: Dict[str, Any] = {}
    
    async def run(self):
        """Run full pipeline"""
        print("=" * 70)
        print("  RIMURU SCANNER + PRICE PIPELINE")
        print("=" * 70)
        
        # Initialize price engine
        self.engine = PriceEngine(db_path=str(PRICES_DB))
        await self.engine.start()
        
        try:
            # Step 1: Load scanner findings
            self._load_scanner_data()
            
            # Step 2: Get live prices for discovered tokens
            await self._enrich_with_prices()
            
            # Step 3: Check wallet balances
            await self._check_wallet_balances()
            
            # Step 4: Get market overview
            await self._get_market_context()
            
            # Step 5: Generate enriched report
            self._generate_report()
            
            # Step 6: Set up monitoring alerts
            self._setup_alerts()
            
        finally:
            await self.engine.stop()
    
    def _load_scanner_data(self):
        """Load data from crypto_findings.db"""
        print("\n[1/6] Loading scanner findings...")
        
        if not os.path.exists(self.scanner_db_path):
            print(f"  Scanner DB not found: {self.scanner_db_path}")
            print("  Run full_crypto_scanner.py first!")
            return
        
        conn = sqlite3.connect(self.scanner_db_path)
        cursor = conn.cursor()
        
        # Get wallet counts
        cursor.execute("SELECT blockchain, COUNT(*) FROM wallets GROUP BY blockchain")
        wallet_counts = dict(cursor.fetchall())
        
        # Get ETH wallets for balance checking
        cursor.execute("SELECT address FROM wallets WHERE blockchain = 'ETH' LIMIT 50")
        self.discovered_wallets = [r[0] for r in cursor.fetchall()]
        
        # Get API key info
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        api_count = cursor.fetchone()[0]
        
        # Try to extract token symbols from source files
        cursor.execute("SELECT DISTINCT source_file FROM wallets")
        source_files = [r[0] for r in cursor.fetchall()]
        
        conn.close()
        
        # Common tokens to always track
        self.discovered_tokens = [
            "BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC", "LINK",
            "UNI", "AAVE", "DOGE", "XRP", "LTC", "BNB", "ATOM", "NEAR",
            "ARB", "OP", "CRV", "COMP", "MKR", "SNX", "SUSHI", "YFI",
        ]
        
        print(f"  Wallets: {sum(wallet_counts.values())} ({wallet_counts})")
        print(f"  API Keys: {api_count}")
        print(f"  Source Files: {len(source_files)}")
        print(f"  Tokens to track: {len(self.discovered_tokens)}")
    
    async def _enrich_with_prices(self):
        """Get live prices for all discovered tokens"""
        print("\n[2/6] Fetching live prices...")
        
        prices = await self.engine.get_prices_batch(self.discovered_tokens)
        
        self.enriched_data["token_prices"] = {}
        total_mcap = 0
        
        for symbol, price in prices.items():
            self.enriched_data["token_prices"][symbol] = {
                "name": price.name,
                "price_usd": price.price_usd,
                "change_24h": price.change_24h,
                "change_7d": price.change_7d,
                "market_cap": price.market_cap,
                "volume_24h": price.volume_24h,
                "rank": price.rank,
            }
            total_mcap += price.market_cap
            
            change_icon = "+" if price.change_24h >= 0 else ""
            print(f"  {symbol:>6}: ${price.price_usd:>12,.2f}  {change_icon}{price.change_24h:.2f}%  (#{price.rank})")
        
        self.enriched_data["tokens_tracked"] = len(prices)
        self.enriched_data["combined_market_cap"] = total_mcap
        print(f"\n  Total tokens priced: {len(prices)}")
        print(f"  Combined market cap: ${total_mcap:,.0f}")
    
    async def _check_wallet_balances(self):
        """Check balances for discovered wallets"""
        print("\n[3/6] Checking wallet balances...")
        
        self.enriched_data["wallets"] = []
        total_value = 0
        wallets_with_funds = 0
        
        # Only check first 20 to avoid rate limits
        check_wallets = self.discovered_wallets[:20]
        
        for i, addr in enumerate(check_wallets):
            try:
                result = await self.engine.get_wallet_value(addr)
                if result["balance_eth"] > 0.0001:
                    wallets_with_funds += 1
                    total_value += result["value_usd"]
                    self.enriched_data["wallets"].append(result)
                    print(f"  FOUND: {addr[:16]}... = {result['balance_eth']:.4f} ETH (${result['value_usd']:,.2f})")
                
                if (i + 1) % 10 == 0:
                    print(f"  Checked {i + 1}/{len(check_wallets)}...")
                
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Wallet check error: {e}")
        
        self.enriched_data["wallet_summary"] = {
            "checked": len(check_wallets),
            "with_funds": wallets_with_funds,
            "total_value_usd": round(total_value, 2),
        }
        
        print(f"\n  Checked: {len(check_wallets)} wallets")
        print(f"  With funds: {wallets_with_funds}")
        print(f"  Total value: ${total_value:,.2f}")
    
    async def _get_market_context(self):
        """Get overall market context"""
        print("\n[4/6] Getting market context...")
        
        # Get top 50 for market overview
        top = await self.engine.get_top_coins(50)
        
        if top:
            total_mcap = sum(p.market_cap for p in top)
            total_vol = sum(p.volume_24h for p in top)
            avg_change = sum(p.change_24h for p in top) / len(top)
            
            btc = next((p for p in top if p.symbol == "BTC"), None)
            eth = next((p for p in top if p.symbol == "ETH"), None)
            
            self.enriched_data["market"] = {
                "total_market_cap": total_mcap,
                "total_volume_24h": total_vol,
                "avg_change_24h": round(avg_change, 2),
                "btc_price": btc.price_usd if btc else 0,
                "eth_price": eth.price_usd if eth else 0,
                "btc_dominance": round((btc.market_cap / total_mcap * 100) if btc and total_mcap else 0, 2),
                "sentiment": "bullish" if avg_change > 1 else ("bearish" if avg_change < -1 else "neutral"),
                "top_5_gainers": [
                    {"symbol": p.symbol, "change": p.change_24h}
                    for p in sorted(top, key=lambda x: x.change_24h, reverse=True)[:5]
                ],
                "top_5_losers": [
                    {"symbol": p.symbol, "change": p.change_24h}
                    for p in sorted(top, key=lambda x: x.change_24h)[:5]
                ],
            }
            
            print(f"  BTC: ${btc.price_usd:,.2f}" if btc else "  BTC: N/A")
            print(f"  ETH: ${eth.price_usd:,.2f}" if eth else "  ETH: N/A")
            print(f"  Market Cap: ${total_mcap:,.0f}")
            print(f"  Sentiment: {self.enriched_data['market']['sentiment']}")
        
        # Gas prices
        gas = await self.engine.get_gas()
        if gas:
            self.enriched_data["gas"] = {
                "slow": gas.slow_gwei,
                "standard": gas.standard_gwei,
                "fast": gas.fast_gwei,
                "base_fee": gas.base_fee_gwei,
                "costs": gas.estimated_cost_usd,
            }
            print(f"  Gas: {gas.standard_gwei:.0f} gwei (transfer: ${gas.estimated_cost_usd.get('transfer_fast', 0):.2f})")
    
    def _generate_report(self):
        """Generate enriched report JSON"""
        print("\n[5/6] Generating enriched report...")
        
        self.enriched_data["generated_at"] = datetime.utcnow().isoformat() + "Z"
        self.enriched_data["pipeline"] = "scanner_price_pipeline v1.0"
        
        os.makedirs(REPORT_PATH.parent, exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(self.enriched_data, f, indent=2, default=str)
        
        print(f"  Report saved: {REPORT_PATH}")
    
    def _setup_alerts(self):
        """Set up monitoring alerts for key tokens"""
        print("\n[6/6] Setting up price alerts...")
        
        alerts_config = [
            ("BTC", "above", 100000, "BTC hit $100K!"),
            ("BTC", "below", 50000, "BTC dropped below $50K"),
            ("ETH", "above", 5000, "ETH hit $5K!"),
            ("ETH", "below", 2000, "ETH dropped below $2K"),
            ("SOL", "above", 300, "SOL hit $300!"),
            ("SOL", "percent_change", 15, "SOL moved 15%+ in 24h"),
        ]
        
        for symbol, alert_type, threshold, message in alerts_config:
            alert = self.engine.add_alert(symbol, alert_type, threshold, message)
            print(f"  Alert: {message}")
        
        print(f"\n  {len(alerts_config)} alerts configured")
    
    def print_summary(self):
        """Print final summary"""
        print("\n" + "=" * 70)
        print("  PIPELINE COMPLETE - SUMMARY")
        print("=" * 70)
        
        tokens = self.enriched_data.get("token_prices", {})
        wallet_sum = self.enriched_data.get("wallet_summary", {})
        market = self.enriched_data.get("market", {})
        
        print(f"\n  Tokens Tracked:    {len(tokens)}")
        print(f"  Wallets Checked:   {wallet_sum.get('checked', 0)}")
        print(f"  Wallets w/ Funds:  {wallet_sum.get('with_funds', 0)}")
        print(f"  Total Wallet Value: ${wallet_sum.get('total_value_usd', 0):,.2f}")
        print(f"  Market Sentiment:  {market.get('sentiment', 'unknown')}")
        print(f"  BTC Dominance:     {market.get('btc_dominance', 0):.1f}%")
        
        print(f"\n  Price DB:   {PRICES_DB}")
        print(f"  Scanner DB: {SCANNER_DB}")
        print(f"  Report:     {REPORT_PATH}")
        print("=" * 70)


async def main():
    pipeline = ScannerPricePipeline()
    await pipeline.run()
    pipeline.print_summary()


if __name__ == "__main__":
    asyncio.run(main())
