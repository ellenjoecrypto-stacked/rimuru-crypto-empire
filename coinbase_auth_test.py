#!/usr/bin/env python3
"""Try ALL Coinbase auth methods with the new API key"""
import time
import hashlib
import hmac
import base64
import requests
import json

CB_KEY = "c9faf522-e1a1-4de0-805d-160daf2abf75"
CB_SECRET = "1e979c54-0b78-4f62-9c9b-c7c8dd560501"

ENDPOINTS = [
    ('GET', '/v2/user'),
    ('GET', '/v2/accounts'),
    ('GET', '/api/v3/brokerage/accounts'),
]

print("=" * 60)
print("COINBASE AUTH METHOD TESTER")
print("=" * 60)

# ============================================================
# METHOD 1: HMAC-SHA256 with secret as UTF-8 string
# ============================================================
def method1(method, path):
    timestamp = str(int(time.time()))
    message = timestamp + method + path + ''
    signature = hmac.new(CB_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'CB-ACCESS-KEY': CB_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-VERSION': '2024-01-01',
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

# ============================================================
# METHOD 2: HMAC-SHA256 with base64-decoded secret
# ============================================================
def method2(method, path):
    timestamp = str(int(time.time()))
    message = timestamp + method + path + ''
    try:
        secret_bytes = base64.b64decode(CB_SECRET)
        signature = hmac.new(secret_bytes, message.encode('utf-8'), hashlib.sha256).hexdigest()
    except:
        return None
    headers = {
        'CB-ACCESS-KEY': CB_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-VERSION': '2024-01-01',
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

# ============================================================
# METHOD 3: HMAC-SHA256 with secret bytes (hex decode)
# ============================================================
def method3(method, path):
    timestamp = str(int(time.time()))
    message = timestamp + method + path + ''
    try:
        # Remove dashes from UUID and decode as hex
        secret_hex = CB_SECRET.replace('-', '')
        secret_bytes = bytes.fromhex(secret_hex)
        signature = hmac.new(secret_bytes, message.encode('utf-8'), hashlib.sha256).hexdigest()
    except:
        return None
    headers = {
        'CB-ACCESS-KEY': CB_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'CB-VERSION': '2024-01-01',
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

# ============================================================
# METHOD 4: OAuth Bearer token style (maybe it's an OAuth token)
# ============================================================
def method4(method, path):
    headers = {
        'Authorization': f'Bearer {CB_SECRET}',
        'CB-VERSION': '2024-01-01',
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

# ============================================================
# METHOD 5: No CB-VERSION header
# ============================================================
def method5(method, path):
    timestamp = str(int(time.time()))
    message = timestamp + method + path + ''
    signature = hmac.new(CB_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'CB-ACCESS-KEY': CB_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

# ============================================================
# METHOD 6: JWT ES256 (CDP style) - try with secret as HMAC
# ============================================================
def method6(method, path):
    try:
        import jwt as pyjwt
        timestamp = int(time.time())
        
        # Try HMAC-based JWT
        payload = {
            'sub': CB_KEY,
            'iss': 'coinbase-cloud',
            'aud': ['cdp_service'],
            'nbf': timestamp,
            'exp': timestamp + 120,
            'uris': [f'{method} api.coinbase.com{path}'],
        }
        
        token = pyjwt.encode(payload, CB_SECRET, algorithm='HS256')
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)
    except:
        return None

# ============================================================
# METHOD 7: Coinbase Advanced Trade - different signing
# ============================================================
def method7(method, path):
    timestamp = str(int(time.time()))
    # Advanced Trade signs: timestamp + method + request_path  
    message = timestamp + method + path
    signature = hmac.new(CB_SECRET.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {
        'CB-ACCESS-KEY': CB_KEY,
        'CB-ACCESS-SIGN': signature,
        'CB-ACCESS-TIMESTAMP': timestamp,
        'Content-Type': 'application/json'
    }
    return requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=10)

methods = [
    ("HMAC-SHA256 (secret as string)", method1),
    ("HMAC-SHA256 (base64 decoded)", method2),
    ("HMAC-SHA256 (hex decoded UUID)", method3),
    ("OAuth Bearer token", method4),
    ("HMAC no CB-VERSION", method5),
    ("JWT HS256", method6),
    ("Advanced Trade signing", method7),
]

for name, func in methods:
    print(f"\n--- {name} ---")
    for method, path in ENDPOINTS:
        try:
            resp = func(method, path)
            if resp is None:
                print(f"  {path}: SKIPPED (decode error)")
                continue
            status = resp.status_code
            
            # Show response details
            try:
                body = resp.json()
                if status == 200:
                    print(f"  {path}: {status} SUCCESS!")
                    if 'data' in body:
                        d = body['data']
                        if isinstance(d, dict) and 'name' in d:
                            print(f"    User: {d.get('name')} / {d.get('email')}")
                        elif isinstance(d, list):
                            print(f"    Accounts: {len(d)}")
                    elif 'accounts' in body:
                        print(f"    Accounts: {len(body['accounts'])}")
                else:
                    err_msg = str(body)[:150]
                    print(f"  {path}: {status} - {err_msg}")
            except:
                print(f"  {path}: {status} - {resp.text[:100]}")
        except Exception as e:
            print(f"  {path}: ERROR - {e}")
        
        # Don't hammer the API
        time.sleep(0.3)

print("\n" + "=" * 60)
print("If all methods fail, the key may need specific permissions")
print("or it might be from Coinbase Developer Platform (CDP)")
print("which requires a different key format with EC private key.")
print("=" * 60)
