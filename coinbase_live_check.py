#!/usr/bin/env python3
"""
Test fresh CDP API key with EC private key - check all Coinbase balances
"""
import json
import time
import secrets
import requests
import os
from dotenv import load_dotenv
import logging
load_dotenv()

# Load key
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
KEY_NAME = os.getenv("COINBASE_CDP_KEY_NAME", "")
PRIVATE_KEY = os.getenv("COINBASE_CDP_PRIVATE_KEY", "").replace("\\n", "\n")

if not KEY_NAME or not PRIVATE_KEY:
    raise EnvironmentError("COINBASE_CDP_KEY_NAME and COINBASE_CDP_PRIVATE_KEY must be set in .env")

logger.info("=" * 60)
logger.info("COINBASE FRESH CDP KEY - BALANCE CHECK")
logger.info("=" * 60)

def make_jwt(method, path):
    """Create ES256 JWT for CDP authentication"""
    import jwt as pyjwt
    
    timestamp = int(time.time())
    uri = f"{method} api.coinbase.com{path}"
    
    payload = {
        "sub": KEY_NAME,
        "iss": "cdp",
        "aud": ["cdp_service"],
        "nbf": timestamp,
        "exp": timestamp + 120,
        "uris": [uri],
    }
    
    headers = {
        "kid": KEY_NAME,
        "typ": "JWT",
        "nonce": secrets.token_hex(16),
    }
    
    token = pyjwt.encode(payload, PRIVATE_KEY, algorithm="ES256", headers=headers)
    return token

def cdp_request(method, path):
    """Make authenticated CDP request"""
    token = make_jwt(method, path)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"https://api.coinbase.com{path}"
    if method == "GET":
        return requests.get(url, headers=headers, timeout=15)
    return requests.post(url, headers=headers, timeout=15)

# ============================================================
# 1. Check user identity
# ============================================================
logger.info("\n[1] Checking user identity...")
resp = cdp_request("GET", "/v2/user")
logger.info("  Status: %s", resp.status_code)
if resp.status_code == 200:
    user = resp.json().get('data', {})
    logger.info("  Name: %s", user.get('name', '?'))
    logger.info("  Email: %s", user.get('email', '?'))
    logger.info("  Country: %s", user.get('country', {}).get('name', '?'))
    logger.info("  AUTH WORKING!")
else:
    logger.info("  Response: %s", resp.text[:300])

# ============================================================
# 2. Check v2 accounts (consumer/retail)
# ============================================================
logger.info("\n[2] Checking v2 accounts (retail)...")
resp2 = cdp_request("GET", "/v2/accounts?limit=100")
logger.info("  Status: %s", resp2.status_code)
if resp2.status_code == 200:
    data = resp2.json()
    accounts = data.get('data', [])
    logger.info("  Found %s accounts!", len(accounts))
    
    total_usd = 0
    funded = []
    
    for acct in accounts:
        name = acct.get('name', '?')
        currency = acct.get('currency', {})
        code = currency.get('code', '?') if isinstance(currency, dict) else str(currency)
        bal = float(acct.get('balance', {}).get('amount', '0'))
        native = float(acct.get('native_balance', {}).get('amount', '0'))
        native_curr = acct.get('native_balance', {}).get('currency', 'USD')
        
        if bal > 0:
            total_usd += native
            funded.append({'name': name, 'code': code, 'balance': bal, 'usd': native, 'id': acct.get('id')})
            logger.info("    %s (%s): %s = $%s %s", name, code, bal, "{:,.2f}".format(native), native_curr)
    
    if not funded:
        logger.info("  All retail balances are $0")
        # Show first few accounts anyway
        for acct in accounts[:10]:
            name = acct.get('name', '?')
            currency = acct.get('currency', {})
            code = currency.get('code', '?') if isinstance(currency, dict) else str(currency)
            logger.info("    %s (%s): $0", name, code)
    else:
        logger.info("\n  TOTAL RETAIL VALUE: $%s", "{:,.2f}".format(total_usd))
        
    # Check for more pages
    pagination = data.get('pagination', {})
    next_uri = pagination.get('next_uri')
    if next_uri:
        logger.info("  (more accounts available: %s)", next_uri)
else:
    logger.info("  Response: %s", resp2.text[:300])

# ============================================================
# 3. Check v3 brokerage accounts (Advanced Trade)
# ============================================================
logger.info("\n[3] Checking v3 brokerage accounts (Advanced Trade)...")
resp3 = cdp_request("GET", "/api/v3/brokerage/accounts?limit=250")
logger.info("  Status: %s", resp3.status_code)
if resp3.status_code == 200:
    data = resp3.json()
    v3_accounts = data.get('accounts', [])
    logger.info("  Found %s trading accounts!", len(v3_accounts))
    
    for acct in v3_accounts:
        currency = acct.get('currency', '?')
        avail = float(acct.get('available_balance', {}).get('value', '0'))
        hold = float(acct.get('hold', {}).get('value', '0'))
        if avail > 0 or hold > 0:
            logger.info("    %s: available=%s, hold=%s", currency, avail, hold)
else:
    logger.info("  Response: %s", resp3.text[:300])

# ============================================================
# 4. Check recent transactions
# ============================================================
if resp2.status_code == 200 and funded:
    logger.info("\n[4] Recent transactions for funded accounts...")
    for acct in funded[:5]:
        acct_id = acct['id']
        tx_resp = cdp_request("GET", f"/v2/accounts/{acct_id}/transactions?limit=5")
        if tx_resp.status_code == 200:
            txs = tx_resp.json().get('data', [])
            if txs:
                logger.info("\n  %s (%s):", acct['name'], acct['code'])
                for tx in txs:
                    tx_type = tx.get('type', '?')
                    amount = tx.get('amount', {}).get('amount', '0')
                    currency = tx.get('amount', {}).get('currency', '?')
                    status = tx.get('status', '?')
                    created = tx.get('created_at', '?')[:10]
                    native = tx.get('native_amount', {}).get('amount', '0')
                    logger.info("    %s %s: %s %s ($%s) [%s]", created, tx_type, amount, currency, native, status)

logger.info("%s", "\n" + "=" * 60)
logger.info("DONE")
logger.info("=" * 60)
