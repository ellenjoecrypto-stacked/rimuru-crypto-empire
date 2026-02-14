#!/usr/bin/env python3
"""
Test fresh CDP API key with EC private key - check all Coinbase balances
"""
import json
import time
import secrets
import requests

# Load key
KEY_NAME = "organizations/761837f6-e032-4a33-9a7f-20b39bc890b6/apiKeys/c62fad2a-7a0e-4761-8460-beecf4cc615c"
PRIVATE_KEY = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIG7vP0woDot5TtVm25y811OEkNKJoj6Si0FWhszdOUrsoAoGCCqGSM49\nAwEHoUQDQgAE3/6Cxa66KxrNlAFOJUgjb8F6Dvfg8HvqLnPgAw68asRwEnsH7vo4\notQCCX0XlBfx9VQZKliK7ORZxyp/j9g0Dw==\n-----END EC PRIVATE KEY-----\n"

print("=" * 60)
print("COINBASE FRESH CDP KEY - BALANCE CHECK")
print("=" * 60)

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
print("\n[1] Checking user identity...")
resp = cdp_request("GET", "/v2/user")
print(f"  Status: {resp.status_code}")
if resp.status_code == 200:
    user = resp.json().get('data', {})
    print(f"  Name: {user.get('name', '?')}")
    print(f"  Email: {user.get('email', '?')}")
    print(f"  Country: {user.get('country', {}).get('name', '?')}")
    print(f"  AUTH WORKING!")
else:
    print(f"  Response: {resp.text[:300]}")

# ============================================================
# 2. Check v2 accounts (consumer/retail)
# ============================================================
print("\n[2] Checking v2 accounts (retail)...")
resp2 = cdp_request("GET", "/v2/accounts?limit=100")
print(f"  Status: {resp2.status_code}")
if resp2.status_code == 200:
    data = resp2.json()
    accounts = data.get('data', [])
    print(f"  Found {len(accounts)} accounts!")
    
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
            print(f"    {name} ({code}): {bal} = ${native:,.2f} {native_curr}")
    
    if not funded:
        print("  All retail balances are $0")
        # Show first few accounts anyway
        for acct in accounts[:10]:
            name = acct.get('name', '?')
            currency = acct.get('currency', {})
            code = currency.get('code', '?') if isinstance(currency, dict) else str(currency)
            print(f"    {name} ({code}): $0")
    else:
        print(f"\n  TOTAL RETAIL VALUE: ${total_usd:,.2f}")
        
    # Check for more pages
    pagination = data.get('pagination', {})
    next_uri = pagination.get('next_uri')
    if next_uri:
        print(f"  (more accounts available: {next_uri})")
else:
    print(f"  Response: {resp2.text[:300]}")

# ============================================================
# 3. Check v3 brokerage accounts (Advanced Trade)
# ============================================================
print("\n[3] Checking v3 brokerage accounts (Advanced Trade)...")
resp3 = cdp_request("GET", "/api/v3/brokerage/accounts?limit=250")
print(f"  Status: {resp3.status_code}")
if resp3.status_code == 200:
    data = resp3.json()
    v3_accounts = data.get('accounts', [])
    print(f"  Found {len(v3_accounts)} trading accounts!")
    
    for acct in v3_accounts:
        currency = acct.get('currency', '?')
        avail = float(acct.get('available_balance', {}).get('value', '0'))
        hold = float(acct.get('hold', {}).get('value', '0'))
        if avail > 0 or hold > 0:
            print(f"    {currency}: available={avail}, hold={hold}")
else:
    print(f"  Response: {resp3.text[:300]}")

# ============================================================
# 4. Check recent transactions
# ============================================================
if resp2.status_code == 200 and funded:
    print("\n[4] Recent transactions for funded accounts...")
    for acct in funded[:5]:
        acct_id = acct['id']
        tx_resp = cdp_request("GET", f"/v2/accounts/{acct_id}/transactions?limit=5")
        if tx_resp.status_code == 200:
            txs = tx_resp.json().get('data', [])
            if txs:
                print(f"\n  {acct['name']} ({acct['code']}):")
                for tx in txs:
                    tx_type = tx.get('type', '?')
                    amount = tx.get('amount', {}).get('amount', '0')
                    currency = tx.get('amount', {}).get('currency', '?')
                    status = tx.get('status', '?')
                    created = tx.get('created_at', '?')[:10]
                    native = tx.get('native_amount', {}).get('amount', '0')
                    print(f"    {created} {tx_type}: {amount} {currency} (${native}) [{status}]")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
