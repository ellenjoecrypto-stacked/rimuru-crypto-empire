#!/usr/bin/env python3
"""
Probe all Coinbase endpoints to find what permissions this key has
"""
import json
import time
import secrets
import requests
import jwt as pyjwt
import os
from dotenv import load_dotenv
load_dotenv()

KEY_NAME = os.getenv("COINBASE_CDP_KEY_NAME", "")
PRIVATE_KEY = os.getenv("COINBASE_CDP_PRIVATE_KEY", "").replace("\\n", "\n")

if not KEY_NAME or not PRIVATE_KEY:
    raise EnvironmentError("COINBASE_CDP_KEY_NAME and COINBASE_CDP_PRIVATE_KEY must be set in .env")

def cdp_get(path):
    timestamp = int(time.time())
    uri = f"GET api.coinbase.com{path}"
    payload = {
        "sub": KEY_NAME, "iss": "cdp", "aud": ["cdp_service"],
        "nbf": timestamp, "exp": timestamp + 120, "uris": [uri],
    }
    headers_jwt = {"kid": KEY_NAME, "typ": "JWT", "nonce": secrets.token_hex(16)}
    token = pyjwt.encode(payload, PRIVATE_KEY, algorithm="ES256", headers=headers_jwt)
    resp = requests.get(f"https://api.coinbase.com{path}",
                       headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       timeout=15)
    return resp.status_code, resp

print("=" * 60)
print("COINBASE PERMISSION PROBE")
print("=" * 60)
print("User: Marke Standoak / ellenjoecrypto@gmail.com")
print()

# Test various endpoints
endpoints = [
    # User info
    ("/v2/user", "User identity"),
    ("/v2/user/auth", "Auth info / permissions"),
    
    # Accounts (need wallet:accounts:read)
    ("/v2/accounts", "Retail accounts"),
    ("/v2/accounts?limit=100", "Retail accounts (limit 100)"),
    
    # Advanced Trade
    ("/api/v3/brokerage/accounts", "Advanced Trade accounts"),
    ("/api/v3/brokerage/portfolios", "Portfolios"),
    ("/api/v3/brokerage/best_bid_ask?product_ids=BTC-USD", "Market data"),
    
    # Exchange rates (public-ish)
    ("/v2/exchange-rates?currency=BTC", "Exchange rates"),
    ("/v2/prices/BTC-USD/spot", "BTC spot price"),
    ("/v2/currencies", "Currencies list"),
    
    # Payment methods
    ("/v2/payment-methods", "Payment methods (banks)"),
    
    # CDP specific
    ("/platform/v1/wallets", "CDP wallets"),
]

for path, desc in endpoints:
    status, resp = cdp_get(path)
    
    if status == 200:
        try:
            data = resp.json()
            # Summarize the response
            if 'data' in data:
                d = data['data']
                if isinstance(d, list):
                    summary = f"{len(d)} items"
                    # Show first item details
                    if d and isinstance(d[0], dict):
                        keys = list(d[0].keys())[:5]
                        summary += f" (keys: {keys})"
                elif isinstance(d, dict):
                    preview = {k: str(v)[:50] for k, v in list(d.items())[:5]}
                    summary = str(preview)
                else:
                    summary = str(d)[:100]
            elif 'accounts' in data:
                summary = f"{len(data['accounts'])} accounts"
            elif 'portfolios' in data:
                summary = f"{len(data['portfolios'])} portfolios"
            else:
                summary = str(data)[:150]
            
            print(f"  200 {desc}: {summary}")
        except:
            print(f"  200 {desc}: {resp.text[:100]}")
    else:
        print(f"  {status} {desc}")
    
    time.sleep(0.2)

# If we got auth info, show permissions
print("\n" + "=" * 60)
print("CHECKING AUTH DETAILS...")
status, resp = cdp_get("/v2/user/auth")
if status == 200:
    auth = resp.json().get('data', {})
    print(f"  Method: {auth.get('method', '?')}")
    print(f"  Scopes: {auth.get('scopes', [])}")
    print(f"  OAuth meta: {auth.get('oauth_meta', {})}")
else:
    print(f"  Auth info: {status}")

print("\n" + "=" * 60)
print("\nIf accounts return 401, the CDP key needs these scopes:")
print("  wallet:accounts:read")
print("  wallet:transactions:read")
print("  wallet:payment-methods:read")
print("\nGo to: https://portal.cdp.coinbase.com/access/api")
print("Edit your key or create a new one with those scopes.")
print("=" * 60)
