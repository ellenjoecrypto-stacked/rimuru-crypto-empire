#!/usr/bin/env python3
"""Test new Coinbase API key and check all balances"""
import time
import hashlib
import hmac
import requests
import json
import os
from dotenv import load_dotenv
import logging
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
CB_API_KEY = os.getenv("COINBASE_API_KEY", "")
CB_API_SECRET = os.getenv("COINBASE_SECRET_KEY", "")

if not CB_API_KEY or not CB_API_SECRET:
    raise EnvironmentError("COINBASE_API_KEY and COINBASE_SECRET_KEY must be set in .env")

def coinbase_request(method, path, body=''):
    """Make authenticated Coinbase v2 API request"""
    timestamp = str(int(time.time()))
    message = timestamp + method + path + body
    
    signature = hmac.new(
        CB_API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        'CB-ACCESS-KEY': CB_API_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-VERSION': '2024-01-01',
        'Content-Type': 'application/json'
    }
    
    url = f'https://api.coinbase.com{path}'
    if method == 'GET':
        resp = requests.get(url, headers=headers, timeout=15)
    else:
        resp = requests.post(url, headers=headers, data=body, timeout=15)
    return resp

logger.info("=" * 60)
logger.info("COINBASE BALANCE CHECK - Fresh API Key")
logger.info("=" * 60)

# Test auth first
logger.info("\n[1] Testing authentication...")
resp = coinbase_request('GET', '/v2/user')
logger.info("  Status: %s", resp.status_code)

if resp.status_code == 200:
    user = resp.json().get('data', {})
    logger.info("  Name: %s", user.get('name', '?'))
    logger.info("  Email: %s", user.get('email', '?'))
    logger.info("  Country: %s", user.get('country', {}).get('name', '?'))
    logger.info("  AUTH WORKING!")
elif resp.status_code == 401:
    logger.error("  401 Unauthorized - key may not be active yet")
    logger.info("  Response: %s", resp.text[:300])
    
    # Try v3 API format instead
    logger.info("\n  Trying Coinbase Advanced (v3) format...")
    resp3 = coinbase_request('GET', '/api/v3/brokerage/accounts')
    logger.info("  v3 Status: %s", resp3.status_code)
    if resp3.status_code == 200:
        logger.info("  v3 API WORKING!")
    else:
        logger.info("  v3 Response: %s", resp3.text[:300])
else:
    logger.info("  Response: %s", resp.text[:300])

# Check accounts/balances
logger.info("\n[2] Checking all accounts...")
resp2 = coinbase_request('GET', '/v2/accounts?limit=100')
logger.info("  Status: %s", resp2.status_code)

if resp2.status_code == 200:
    data = resp2.json()
    accounts = data.get('data', [])
    logger.info("  Found %s accounts!", len(accounts))
    
    total_usd = 0
    funded_accounts = []
    
    for acct in accounts:
        name = acct.get('name', '?')
        currency = acct.get('currency', {})
        if isinstance(currency, dict):
            code = currency.get('code', '?')
        else:
            code = str(currency)
        
        bal_info = acct.get('balance', {})
        bal = float(bal_info.get('amount', '0'))
        
        native_info = acct.get('native_balance', {})
        native_amt = float(native_info.get('amount', '0'))
        native_curr = native_info.get('currency', 'USD')
        
        if bal > 0:
            total_usd += native_amt
            funded_accounts.append({
                'name': name,
                'code': code,
                'balance': bal,
                'usd_value': native_amt,
                'id': acct.get('id', '?')
            })
            logger.info("    %s (%s): %s = $%s %s", name, code, bal, "{:,.2f}".format(native_amt), native_curr)
    
    if not funded_accounts:
        logger.info("  All account balances are $0.00")
        logger.info("\n  Listing all accounts anyway:")
        for acct in accounts[:20]:
            name = acct.get('name', '?')
            currency = acct.get('currency', {})
            code = currency.get('code', '?') if isinstance(currency, dict) else str(currency)
            logger.info("    %s (%s)", name, code)
    
    logger.info("\n  TOTAL PORTFOLIO VALUE: $%s", "{:,.2f}".format(total_usd))
    
    # Check for pending transactions
    if funded_accounts:
        logger.info("\n[3] Checking recent transactions for funded accounts...")
        for acct in funded_accounts:
            acct_id = acct['id']
            tx_resp = coinbase_request('GET', f'/v2/accounts/{acct_id}/transactions?limit=5')
            if tx_resp.status_code == 200:
                txs = tx_resp.json().get('data', [])
                if txs:
                    logger.info("\n  Recent transactions for %s:", acct['name'])
                    for tx in txs:
                        tx_type = tx.get('type', '?')
                        amount = tx.get('amount', {}).get('amount', '0')
                        currency = tx.get('amount', {}).get('currency', '?')
                        status = tx.get('status', '?')
                        created = tx.get('created_at', '?')[:10]
                        native = tx.get('native_amount', {}).get('amount', '0')
                        logger.info("    %s %s: %s %s ($%s) [%s]", created, tx_type, amount, currency, native, status)
else:
    logger.error("  Response: %s", resp2.text[:500])

# Also try v3 brokerage accounts
logger.info("\n[4] Checking Coinbase Advanced/Pro accounts...")
resp4 = coinbase_request('GET', '/api/v3/brokerage/accounts?limit=100')
logger.info("  Status: %s", resp4.status_code)
if resp4.status_code == 200:
    v3_data = resp4.json()
    v3_accounts = v3_data.get('accounts', [])
    logger.info("  Found %s trading accounts!", len(v3_accounts))
    for acct in v3_accounts:
        avail = float(acct.get('available_balance', {}).get('value', '0'))
        hold = float(acct.get('hold', {}).get('value', '0'))
        currency = acct.get('currency', '?')
        if avail > 0 or hold > 0:
            logger.info("    %s: available=%s, hold=%s", currency, avail, hold)
else:
    logger.info("  Response: %s", resp4.text[:300])

logger.info("%s", "\n" + "=" * 60)
