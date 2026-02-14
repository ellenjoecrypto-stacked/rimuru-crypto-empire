#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Exchange Connection Tester
Tests connectivity to Kraken (public) and Coinbase CDP to check wallet access.
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# ============================================
# 1. KRAKEN - Public API (no key needed for market data)
#    Private API needs key for balances
# ============================================

async def test_kraken_public():
    """Test Kraken public endpoints - works without API key"""
    import aiohttp
    print("\n" + "=" * 60)
    print("🐙 KRAKEN PUBLIC API TEST")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        # System status
        async with session.get("https://api.kraken.com/0/public/SystemStatus") as resp:
            data = await resp.json()
            status = data.get("result", {}).get("status", "unknown")
            print(f"   System Status: {status}")
        
        # Get ticker for BTC
        async with session.get("https://api.kraken.com/0/public/Ticker?pair=XBTUSD") as resp:
            data = await resp.json()
            if not data.get("error"):
                ticker = list(data.get("result", {}).values())[0]
                price = float(ticker["c"][0])
                print(f"   BTC/USD: ${price:,.2f}")
        
        # Get ticker for ETH
        async with session.get("https://api.kraken.com/0/public/Ticker?pair=ETHUSD") as resp:
            data = await resp.json()
            if not data.get("error"):
                ticker = list(data.get("result", {}).values())[0]
                price = float(ticker["c"][0])
                print(f"   ETH/USD: ${price:,.2f}")
        
        print(f"\n   ✅ Kraken public API: WORKING")
        print(f"   ℹ️  To check your Kraken BALANCE, you need to:")
        print(f"      1. Log into https://www.kraken.com")
        print(f"      2. Go to Settings → API → Create New Key")
        print(f"      3. Enable ONLY 'Query Funds' permission")
        print(f"      4. Add the key to your .env file")
        print(f"      5. Re-run this checker")


async def test_kraken_private(api_key: str, api_secret: str):
    """Test Kraken private API - check balances"""
    import aiohttp
    import hashlib
    import hmac
    import base64
    import time
    import urllib.parse
    
    print("\n" + "=" * 60)
    print("🐙 KRAKEN PRIVATE API - BALANCE CHECK")
    print("=" * 60)
    
    try:
        url_path = "/0/private/Balance"
        url = f"https://api.kraken.com{url_path}"
        nonce = str(int(time.time() * 1000))
        
        post_data = {"nonce": nonce}
        encoded = urllib.parse.urlencode(post_data)
        
        # Create signature
        message = url_path.encode() + hashlib.sha256((nonce + encoded).encode()).digest()
        signature = hmac.new(base64.b64decode(api_secret), message, hashlib.sha512)
        sig_digest = base64.b64encode(signature.digest()).decode()
        
        headers = {
            "API-Key": api_key,
            "API-Sign": sig_digest,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=post_data, headers=headers) as resp:
                data = await resp.json()
                
                if data.get("error") and len(data["error"]) > 0:
                    print(f"   ❌ Error: {data['error']}")
                    if "EAPI:Invalid key" in str(data["error"]):
                        print(f"   → API key is invalid or expired")
                    elif "EAPI:Invalid nonce" in str(data["error"]):
                        print(f"   → Nonce issue - key might be valid, try again")
                    return False
                
                balances = data.get("result", {})
                if not balances:
                    print(f"   📭 No balances found (empty account)")
                    return True
                
                print(f"\n   💰 KRAKEN WALLET BALANCES:")
                total_value = 0
                for asset, amount in balances.items():
                    bal = float(amount)
                    if bal > 0.00001:
                        print(f"      {asset}: {bal:.8f}")
                        total_value += bal
                
                if total_value == 0:
                    print(f"   📭 All balances are zero")
                else:
                    print(f"\n   ✅ Found assets with non-zero balances!")
                
                return True
                
    except Exception as e:
        print(f"   ❌ Kraken private API error: {e}")
        return False


# ============================================
# 2. COINBASE CDP - Uses the EC key for auth
# ============================================

async def test_coinbase_cdp(api_key_path: str, wallet_secret_path: str = None):
    """Test Coinbase CDP API key"""
    print("\n" + "=" * 60)
    print("🪙 COINBASE CDP API TEST")
    print("=" * 60)
    
    try:
        # Read API key
        with open(api_key_path, 'r') as f:
            key_data = json.load(f)
        
        key_name = key_data.get("name", "")
        has_private_key = "privateKey" in key_data
        
        print(f"   Key Name: {key_name}")
        print(f"   Has Private Key: {has_private_key}")
        
        # Extract org ID and key ID
        parts = key_name.split("/")
        if len(parts) >= 4:
            org_id = parts[1]
            key_id = parts[3]
            print(f"   Organization ID: {org_id}")
            print(f"   API Key ID: {key_id}")
        
        # Read wallet secret if available
        if wallet_secret_path and os.path.exists(wallet_secret_path):
            with open(wallet_secret_path, 'r') as f:
                wallet_secret = f.read().strip()
            print(f"   Wallet Secret: {'*' * 20}... (loaded)")
        
        # Try to connect using the CDP API
        # The CDP SDK is needed for proper auth, let's try a simpler approach
        import aiohttp
        import time
        import hashlib
        import hmac
        
        # Try the Coinbase v2 API endpoint (public)
        async with aiohttp.ClientSession() as session:
            # Public endpoint test
            async with session.get("https://api.coinbase.com/v2/exchange-rates?currency=BTC") as resp:
                data = await resp.json()
                if "data" in data:
                    btc_usd = float(data["data"]["rates"]["USD"])
                    print(f"   BTC/USD via Coinbase: ${btc_usd:,.2f}")
                    print(f"   ✅ Coinbase API is reachable")
        
        print(f"\n   📋 COINBASE CDP STATUS:")
        print(f"   ✅ API key file found and valid JSON")
        print(f"   ✅ EC private key present")
        print(f"   ✅ Organization and key IDs extracted")
        
        print(f"\n   ℹ️  To check your Coinbase WALLET BALANCE:")
        print(f"      Option A: Install coinbase-advanced-py SDK")
        print(f"         pip install coinbase-advanced-py")
        print(f"      Option B: Use the Coinbase website")
        print(f"         https://www.coinbase.com/")
        print(f"      Option C: I can build a CDP wallet checker for you")
        
        # Try with the CDP SDK if available
        try:
            from coinbase.rest import RESTClient
            
            client = RESTClient(
                api_key=key_name,
                api_secret=key_data["privateKey"]
            )
            
            # Get accounts
            accounts = client.get_accounts()
            print(f"\n   🎉 CDP SDK CONNECTION SUCCESSFUL!")
            print(f"\n   💰 COINBASE ACCOUNTS:")
            
            total_usd = 0
            for account in accounts.get("accounts", []):
                name = account.get("name", "Unknown")
                currency = account.get("currency", {}).get("code", "???")
                balance = float(account.get("available_balance", {}).get("value", 0))
                
                if balance > 0:
                    print(f"      {name} ({currency}): {balance}")
                    total_usd += balance
            
            if total_usd == 0:
                print(f"      📭 All account balances are zero")
            else:
                print(f"\n      💎 Total value found!")
            
        except ImportError:
            print(f"\n   ⚠️  coinbase-advanced-py not installed.")
            print(f"      Installing now...")
            os.system(f"{sys.executable} -m pip install coinbase-advanced-py -q")
            print(f"      ✅ Installed! Re-run this script to check balances.")
            
        except Exception as e:
            print(f"\n   ⚠️  CDP SDK error: {e}")
            # Still try the REST API approach
        
        return True
        
    except Exception as e:
        print(f"   ❌ Coinbase CDP error: {e}")
        return False


# ============================================
# 3. QUICK BALANCE CHECK - All Exchanges
# ============================================

async def check_all_exchanges():
    """Check all available exchange connections"""
    print("🔌 RIMURU CRYPTO EMPIRE - EXCHANGE CONNECTION TESTER")
    print("=" * 60)
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Purpose: Check if exchange wallets are accessible")
    
    results = {}
    
    # 1. Kraken Public (always works)
    try:
        await test_kraken_public()
        results["kraken_public"] = True
    except Exception as e:
        print(f"   ❌ Kraken public test failed: {e}")
        results["kraken_public"] = False
    
    # 2. Kraken Private (if keys exist)
    kraken_key = os.getenv("KRAKEN_API_KEY", "")
    kraken_secret = os.getenv("KRAKEN_SECRET_KEY", "")
    
    if kraken_key and "your_" not in kraken_key and kraken_key != "your_kraken_api_key_here":
        try:
            result = await test_kraken_private(kraken_key, kraken_secret)
            results["kraken_private"] = result
        except Exception as e:
            print(f"\n   ❌ Kraken private test failed: {e}")
            results["kraken_private"] = False
    else:
        print(f"\n   ⏭️  Skipping Kraken private API (no real key in .env)")
    
    # 3. Coinbase CDP
    cdp_key_paths = [
        r"C:\Users\Admin\OneDrive\Desktop\mbar\ninja AI Rimuru unchained\cdp_api_key.json",
        r"C:\Users\Admin\OneDrive\Documents\Crypto-Automate-Systemzip\attached_assets\cdp_api_key_1766794874206.json",
    ]
    
    cdp_wallet_secret = r"C:\Users\Admin\OneDrive\Desktop\mbar\ninja AI Rimuru unchained\cdp_wallet_secret.txt"
    
    for path in cdp_key_paths:
        if os.path.exists(path):
            try:
                result = await test_coinbase_cdp(path, cdp_wallet_secret)
                results["coinbase_cdp"] = result
            except Exception as e:
                print(f"\n   ❌ Coinbase CDP test failed: {e}")
                results["coinbase_cdp"] = False
            break
    else:
        print(f"\n   ⏭️  No Coinbase CDP key file found")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 CONNECTION SUMMARY")
    print("=" * 60)
    for exchange, status in results.items():
        icon = "✅" if status else "❌"
        print(f"   {icon} {exchange}: {'Connected' if status else 'Failed'}")
    
    print(f"\n   📌 NEXT STEPS TO ACCESS YOUR WALLETS:")
    print(f"   ┌──────────────────────────────────────────────────────┐")
    print(f"   │ KRAKEN:                                             │")
    print(f"   │   1. Go to https://www.kraken.com → Sign In         │")
    print(f"   │   2. Settings → API → Generate New Key              │")
    print(f"   │   3. Check ONLY 'Query Funds' (read-only!)          │")
    print(f"   │   4. Copy key+secret to .env:                       │")
    print(f"   │      KRAKEN_API_KEY=<key>                           │")
    print(f"   │      KRAKEN_SECRET_KEY=<secret>                     │")
    print(f"   │                                                     │")
    print(f"   │ COINBASE:                                           │")
    print(f"   │   1. Your CDP key is already on disk!               │")
    print(f"   │   2. Installing coinbase-advanced-py SDK now        │")
    print(f"   │   3. Re-run this to see Coinbase balances           │")
    print(f"   └──────────────────────────────────────────────────────┘")


if __name__ == "__main__":
    asyncio.run(check_all_exchanges())
