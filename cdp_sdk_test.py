#!/usr/bin/env python3
"""
Test Coinbase CDP SDK with new API keys
Uses the proper CDP authentication flow
"""
import requests
import json
import time

CDP_API_KEY_ID = "c9faf522-e1a1-4de0-805d-160daf2abf75"
CDP_API_KEY_SECRET = "1e979c54-0b78-4f62-9c9b-c7c8dd560501"

print("=" * 60)
print("COINBASE CDP SDK TEST")
print("=" * 60)

# ============================================================
# METHOD 1: Try coinbase-advanced-py with CDP keys
# ============================================================
print("\n[1] Testing with coinbase-advanced-py SDK...")
try:
    from coinbase.rest import RESTClient
    
    # CDP keys can be used directly with the REST client
    client = RESTClient(api_key=CDP_API_KEY_ID, api_secret=CDP_API_KEY_SECRET)
    
    # Try to get accounts
    print("  Getting accounts...")
    accounts = client.get_accounts()
    print(f"  Response type: {type(accounts)}")
    
    if hasattr(accounts, 'accounts'):
        acct_list = accounts.accounts
        print(f"  Found {len(acct_list)} accounts!")
        total_usd = 0
        for acct in acct_list:
            currency = getattr(acct, 'currency', '?')
            avail = getattr(acct, 'available_balance', None)
            if avail:
                val = float(getattr(avail, 'value', '0'))
                if val > 0:
                    print(f"    {currency}: {val}")
                    if currency == 'USD' or currency == 'USDC' or currency == 'USDT':
                        total_usd += val
        if total_usd > 0:
            print(f"\n  TOTAL USD-equivalent: ${total_usd:,.2f}")
        else:
            print("  All trading balances are $0")
    else:
        print(f"  Raw response: {str(accounts)[:500]}")
        
except Exception as e:
    print(f"  Error: {e}")

# ============================================================
# METHOD 2: Try cdp-sdk 
# ============================================================
print("\n[2] Testing with cdp-sdk...")
try:
    from cdp import CdpClient
    
    client = CdpClient(api_key_id=CDP_API_KEY_ID, api_key_secret=CDP_API_KEY_SECRET)
    print(f"  CDP Client created successfully")
    
    # Try to list wallets
    if hasattr(client, 'wallets'):
        wallets = client.wallets.list()
        print(f"  Wallets: {wallets}")
    
    if hasattr(client, 'list_wallets'):
        wallets = client.list_wallets()
        print(f"  Wallets: {wallets}")
        
except Exception as e:
    print(f"  Error: {e}")

# ============================================================
# METHOD 3: Direct CDP REST API with proper JWT
# ============================================================
print("\n[3] Testing direct CDP REST API...")
try:
    import jwt as pyjwt
    import secrets
    
    # CDP uses ES256 JWT but with the secret as the signing key
    # For API keys created on portal.cdp.coinbase.com, the flow is:
    # JWT signed with HMAC using the key secret
    
    timestamp = int(time.time())
    
    # Build JWT for CDP
    uri = "GET api.coinbase.com/api/v3/brokerage/accounts"
    
    payload = {
        "sub": CDP_API_KEY_ID,
        "iss": "cdp",
        "aud": ["cdp_service"],
        "nbf": timestamp,
        "exp": timestamp + 120,
        "uris": [uri],
    }
    
    # Sign with HMAC-SHA256 using the secret
    token = pyjwt.encode(payload, CDP_API_KEY_SECRET, algorithm="HS256",
                          headers={"kid": CDP_API_KEY_ID, "typ": "JWT", "nonce": secrets.token_hex(16)})
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    resp = requests.get("https://api.coinbase.com/api/v3/brokerage/accounts", 
                       headers=headers, timeout=15)
    print(f"  v3 JWT Status: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        accts = data.get('accounts', [])
        print(f"  Found {len(accts)} accounts!")
        for a in accts:
            curr = a.get('currency', '?')
            avail = float(a.get('available_balance', {}).get('value', '0'))
            hold = float(a.get('hold', {}).get('value', '0'))
            if avail > 0 or hold > 0:
                print(f"    {curr}: available={avail}, hold={hold}")
    else:
        print(f"  Response: {resp.text[:300]}")

    # Also try v2 with Bearer
    print("\n  Trying v2 with Bearer JWT...")
    uri2 = "GET api.coinbase.com/v2/accounts"
    payload2 = {
        "sub": CDP_API_KEY_ID,
        "iss": "cdp",
        "aud": ["cdp_service"],
        "nbf": timestamp,
        "exp": timestamp + 120,
        "uris": [uri2],
    }
    token2 = pyjwt.encode(payload2, CDP_API_KEY_SECRET, algorithm="HS256",
                           headers={"kid": CDP_API_KEY_ID, "typ": "JWT", "nonce": secrets.token_hex(16)})
    headers2 = {
        "Authorization": f"Bearer {token2}",
        "CB-VERSION": "2024-01-01",
        "Content-Type": "application/json"
    }
    resp2 = requests.get("https://api.coinbase.com/v2/accounts", headers=headers2, timeout=15)
    print(f"  v2 JWT Status: {resp2.status_code}")
    if resp2.status_code == 200:
        data = resp2.json()
        accounts = data.get('data', [])
        print(f"  Found {len(accounts)} accounts!")
        for acct in accounts:
            name = acct.get('name', '?')
            currency = acct.get('currency', {})
            code = currency.get('code', '?') if isinstance(currency, dict) else str(currency)
            bal = float(acct.get('balance', {}).get('amount', '0'))
            native = float(acct.get('native_balance', {}).get('amount', '0'))
            if bal > 0:
                print(f"    {name} ({code}): {bal} = ${native:,.2f}")
    else:
        print(f"  Response: {resp2.text[:300]}")
        
except Exception as e:
    print(f"  Error: {e}")

# ============================================================
# METHOD 4: OAuth style with CDP API key as Bearer directly
# ============================================================
print("\n[4] Testing OAuth Bearer with API secret directly...")
resp4 = requests.get("https://api.coinbase.com/v2/accounts",
                     headers={
                         "Authorization": f"Bearer {CDP_API_KEY_SECRET}",
                         "CB-VERSION": "2024-01-01",
                         "Content-Type": "application/json"
                     }, timeout=15)
print(f"  Status: {resp4.status_code}")
if resp4.status_code == 200:
    data = resp4.json()
    print(f"  SUCCESS! Accounts: {len(data.get('data', []))}")
else:
    print(f"  Response: {resp4.text[:200]}")

print("\n" + "=" * 60)
