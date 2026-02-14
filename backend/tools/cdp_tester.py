#!/usr/bin/env python3
"""Test all Coinbase CDP keys with both auth methods"""

import json
import time
import secrets
import hashlib
import hmac
import base64
import os
import sys

try:
    import jwt
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install PyJWT[crypto] requests -q")
    import jwt
    import requests


def test_ec_key(key_data):
    """Test EC key format (name + privateKey with BEGIN EC PRIVATE KEY)"""
    key_name = key_data.get("name", "")
    private_key = key_data.get("privateKey", "")
    
    print(f"  Key Name: {key_name}")
    print(f"  Key Type: EC (ES256)")
    
    endpoints = [
        ("v2/accounts", "GET api.coinbase.com/v2/accounts", "https://api.coinbase.com/v2/accounts"),
        ("v2/user", "GET api.coinbase.com/v2/user", "https://api.coinbase.com/v2/user"),
        ("v3/accounts", "GET api.coinbase.com/api/v3/brokerage/accounts", "https://api.coinbase.com/api/v3/brokerage/accounts"),
    ]
    
    for label, uri, url in endpoints:
        try:
            payload = {
                "sub": key_name,
                "iss": "cdp",
                "nbf": int(time.time()),
                "exp": int(time.time()) + 120,
                "uri": uri
            }
            
            token = jwt.encode(
                payload, private_key, algorithm="ES256",
                headers={"kid": key_name, "nonce": secrets.token_hex(16), "typ": "JWT"}
            )
            
            headers = {"Authorization": f"Bearer {token}"}
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"  {label}: {resp.status_code}")
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code != 401:
                print(f"    {resp.text[:200]}")
        except Exception as e:
            print(f"  {label}: Error - {e}")
    
    return None


def test_hmac_key(key_data):
    """Test HMAC key format (id + privateKey as base64)"""
    key_id = key_data.get("id", "")
    private_key = key_data.get("privateKey", "")
    
    print(f"  Key ID: {key_id}")
    print(f"  Key Type: HMAC (legacy)")
    
    endpoints = [
        ("/v2/accounts", "GET"),
        ("/v2/user", "GET"),
        ("/api/v3/brokerage/accounts", "GET"),
    ]
    
    for path, method in endpoints:
        try:
            timestamp = str(int(time.time()))
            message = timestamp + method + path
            
            key_bytes = base64.b64decode(private_key)
            sig = hmac.new(key_bytes, message.encode(), hashlib.sha256).hexdigest()
            
            headers = {
                "CB-ACCESS-KEY": key_id,
                "CB-ACCESS-SIGN": sig,
                "CB-ACCESS-TIMESTAMP": timestamp,
                "CB-VERSION": "2024-01-01",
                "Content-Type": "application/json"
            }
            
            url = f"https://api.coinbase.com{path}"
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"  HMAC {path}: {resp.status_code}")
            
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code != 401:
                print(f"    {resp.text[:200]}")
                
        except Exception as e:
            print(f"  HMAC {path}: Error - {e}")
    
    return None


# ============================================
# Main
# ============================================

print("=" * 60)
print("COINBASE CDP KEY TESTER - ALL KEYS, ALL AUTH METHODS")
print("=" * 60)

key_files = []

# Find all CDP key files
search_dirs = [
    r"C:\Users\Admin\OneDrive\Desktop\mbar\ninja AI Rimuru unchained",
    r"C:\Users\Admin\OneDrive\Documents\Crypto-Automate-Systemzip\attached_assets",
]

for d in search_dirs:
    if os.path.exists(d):
        for f in os.listdir(d):
            if "cdp_api_key" in f and f.endswith(".json"):
                key_files.append(os.path.join(d, f))

# Also walk the zip directory
zip_dir = r"C:\Users\Admin\OneDrive\Desktop\mbar\ninja AI Rimuru unchained\Crypto-Automate-Systemzip"
if os.path.exists(zip_dir):
    for root, dirs, files in os.walk(zip_dir):
        for f in files:
            if "cdp_api_key" in f and f.endswith(".json"):
                full = os.path.join(root, f)
                if full not in key_files:
                    key_files.append(full)

print(f"\nFound {len(key_files)} CDP key files\n")

any_success = False

for path in key_files:
    print(f"\n{'='*60}")
    fname = os.path.basename(path)
    print(f"FILE: {fname}")
    print(f"PATH: {path}")
    print("-" * 60)
    
    with open(path) as f:
        key_data = json.load(f)
    
    result = None
    
    # Determine key format
    if "name" in key_data and "BEGIN EC PRIVATE KEY" in key_data.get("privateKey", ""):
        result = test_ec_key(key_data)
    elif "id" in key_data:
        result = test_hmac_key(key_data)
        if not result:
            # Also try as EC if it has a private key
            print("  Trying EC format too...")
            kid = key_data["id"]
            mock_key = {
                "name": f"organizations/unknown/apiKeys/{kid}",
                "privateKey": key_data["privateKey"]
            }
            try:
                result = test_ec_key(mock_key)
            except Exception:
                pass
    
    if result:
        any_success = True
        print("\n  WALLET DATA FOUND!")
        
        # Handle v2 response
        if "data" in result:
            accounts = result["data"]
            if isinstance(accounts, list):
                count = len(accounts)
                print(f"  Found {count} accounts:")
                for acct in accounts:
                    name = acct.get("name", "?")
                    curr = acct.get("currency", "?")
                    if isinstance(curr, dict):
                        curr = curr.get("code", "?")
                    bal = acct.get("balance", {})
                    if isinstance(bal, dict):
                        amount = bal.get("amount", "0")
                    else:
                        amount = str(bal)
                    
                    if float(amount) > 0.000001:
                        print(f"    {name} ({curr}): {amount}")
            else:
                txt = json.dumps(accounts, indent=2)[:500]
                print(f"  User data: {txt}")
        
        # Handle v3 response
        elif "accounts" in result:
            accounts = result["accounts"]
            count = len(accounts)
            print(f"  Found {count} accounts:")
            for acct in accounts:
                name = acct.get("name", "?")
                curr = acct.get("currency", "?")
                avail = acct.get("available_balance", {}).get("value", "0")
                if float(avail) > 0.000001:
                    print(f"    {name} ({curr}): {avail}")
        
        break

if not any_success:
    print("\n" + "=" * 60)
    print("RESULT: All CDP keys returned 401 Unauthorized")
    print("=" * 60)
    print()
    print("This means the API keys have been REVOKED or EXPIRED.")
    print("They cannot be used to access your Coinbase wallet.")
    print()
    print("HOW TO FIX:")
    print("  1. Sign into https://portal.cdp.coinbase.com/")
    print("     (or https://www.coinbase.com/settings/api)")
    print("  2. Create a NEW API key")
    print("  3. For read-only balance checking, select:")
    print("     - wallet:accounts:read")
    print("     - wallet:user:read")
    print("  4. Download the new key JSON file")
    print("  5. Save to: rimuru_empire/_SENSITIVE/cdp_api_key.json")
    print("  6. Re-run: python backend/tools/exchange_tester.py")
    print()
    print("FOR KRAKEN:")
    print("  1. Sign into https://www.kraken.com/")
    print("  2. Security -> API -> Create Key")
    print("  3. Enable ONLY 'Query Funds' permission")
    print("  4. Add to .env:")
    print("     KRAKEN_API_KEY=your_key")
    print("     KRAKEN_SECRET_KEY=your_secret")
    print("  5. Re-run: python backend/tools/exchange_tester.py")
