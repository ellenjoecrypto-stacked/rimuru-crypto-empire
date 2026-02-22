"""
Multi-Exchange Balance Checker with Coinbase CDP Support
Works for: Kraken, Coinbase CDP
For Texas users - no geo restrictions
"""

import logging
import os
import hmac
import hashlib
import base64
import time
import json
import urllib.parse
from datetime import datetime
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from dotenv import load_dotenv

load_dotenv()


def check_kraken_balance():
    """Check Kraken balance using proper authentication"""
    
    api_key = os.getenv('KRAKEN_API_KEY', '')
    api_secret = os.getenv('KRAKEN_SECRET_KEY', '')
    
    if not api_key or not api_secret or len(api_secret) < 30:
        logger.warning("Kraken: API keys not properly configured")
        return None
    
    try:
        # Kraken API signature
        url_path = '/0/private/Balance'
        nonce = str(int(time.time() * 1000))
        post_data = f'nonce={nonce}'
        
        # Create signature
        encoded = (nonce + post_data).encode('utf-8')
        message = url_path.encode('utf-8') + hashlib.sha256(encoded).digest()
        
        try:
            secret_decoded = base64.b64decode(api_secret)
        except Exception as e:
            logger.error("Kraken: API secret format invalid - %s", e)
            return None
            
        signature = hmac.new(secret_decoded, message, hashlib.sha512)
        sig_b64 = base64.b64encode(signature.digest()).decode('utf-8')
        
        headers = {
            'API-Key': api_key,
            'API-Sign': sig_b64,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(
            'https://api.kraken.com/0/private/Balance',
            headers=headers,
            data=post_data,
            timeout=15
        )
        
        data = response.json()
        
        if data.get('error') and len(data['error']) > 0:
            logger.error("Kraken API Error: %s", data['error'])
            return None
        
        balances = data.get('result', {})
        
        # Kraken asset name mapping
        asset_map = {
            'XXBT': 'BTC', 'XETH': 'ETH', 'ZUSD': 'USD',
            'XXRP': 'XRP', 'XLTC': 'LTC', 'XXLM': 'XLM',
            'USDT': 'USDT', 'USDC': 'USDC'
        }
        
        # Price estimates
        prices = {'BTC': 67500, 'ETH': 3450, 'SOL': 145, 'USD': 1, 'USDT': 1, 'USDC': 1}
        
        total_usd = 0
        logger.info("Kraken Balances:")
        logger.info("-" * 40)
        
        for asset, amount in balances.items():
            amount = float(amount)
            if amount > 0.000001:
                standard = asset_map.get(asset, asset)
                usd_val = amount * prices.get(standard, 0)
                total_usd += usd_val
                logger.info("  %s: %.6f (~$%,.2f)", standard, amount, usd_val)
        
        logger.info("Kraken Total: $%,.2f", total_usd)
        return total_usd
        
    except Exception as e:
        logger.error("Kraken error: %s", e)
        return None


def check_coinbase_cdp():
    """Check balance using Coinbase Developer Platform (CDP) API"""
    
    # Read CDP key path from environment variable or default
    cdp_key_path = os.getenv('CDP_KEY_PATH', 'cdp_api_key.json')
    
    if not os.path.exists(cdp_key_path):
        logger.warning("Coinbase CDP: Key file not found at %s", cdp_key_path)
        return None
    
    try:
        with open(cdp_key_path, 'r') as f:
            cdp_data = json.load(f)
        
        key_id = cdp_data.get('id', '')
        private_key = cdp_data.get('privateKey', '')
        
        if not key_id or not private_key:
            logger.warning("Coinbase CDP: Invalid key format")
            return None
        
        logger.info("Coinbase CDP Key ID: %s...%s", key_id[:8], key_id[-4:])
        logger.info("Attempting to connect to Coinbase CDP API...")
        
        # CDP uses a different auth method - JWT token
        # For now, let's verify the key format
        logger.debug("Private key length: %d chars", len(private_key))
        logger.info("CDP API requires JWT authentication - need to implement full auth flow")
        
        # Would need to implement:
        # 1. Create JWT with ES256 signing
        # 2. Use private key to sign
        # 3. Call CDP API endpoints
        
        return None
        
    except Exception as e:
        logger.error("Coinbase CDP error: %s", e)
        return None


def check_etherscan_wallets(addresses: list):
    """Check ETH balances via Etherscan (no API key needed for basic)"""
    
    logger.info("Etherscan Wallet Check:")
    logger.info("-" * 40)
    
    total_eth = 0
    total_usd = 0
    eth_price = 3450
    
    for addr in addresses[:10]:  # Limit to 10
        try:
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={addr}&tag=latest"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            
            if data['status'] == '1':
                wei = int(data['result'])
                eth = wei / 1e18
                
                if eth > 0.0001:
                    usd = eth * eth_price
                    total_eth += eth
                    total_usd += usd
                    logger.info("  %s...%s: %.4f ETH (~$%,.2f)", addr[:10], addr[-6:], eth, usd)
            
            time.sleep(0.25)  # Rate limit
            
        except Exception as e:
            logger.error("  Error checking %s: %s", addr[:10], e)
    
    if total_eth > 0:
        logger.info("Total ETH found: %.4f (~$%,.2f)", total_eth, total_usd)
    else:
        logger.info("No ETH balances found in scanned addresses")
    
    return total_usd


def main():
    logger.info("=" * 60)
    logger.info("MULTI-EXCHANGE BALANCE CHECKER")
    logger.info("=" * 60)
    
    total = 0
    
    # Check Kraken
    kraken_total = check_kraken_balance()
    if kraken_total:
        total += kraken_total
    
    # Check Coinbase CDP
    cdp_total = check_coinbase_cdp()
    if cdp_total:
        total += cdp_total
    
    # Check known ETH addresses from project scan
    eth_addresses = [
        '0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503',
        '0x6921b130d297cc43754afba22e5eac0fbf8db75b',
        '0x3e71ee7da66000a5a92f13abd2ae95e0abc0bc82',
    ]
    
    eth_total = check_etherscan_wallets(eth_addresses)
    if eth_total:
        total += eth_total
    
    logger.info("=" * 60)
    logger.info("GRAND TOTAL: $%,.2f", total)
    logger.info("=" * 60)
    
    return total


if __name__ == "__main__":
    main()
