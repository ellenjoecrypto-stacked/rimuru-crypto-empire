#!/usr/bin/env python3
"""
FIND MY MONEY - Check all real credentials for actual balances
"""
import time
import hashlib
import hmac
import base64
import urllib.parse
import requests
import json
import os
from dotenv import load_dotenv
load_dotenv()

print("=" * 60)
print("FIND MY MONEY - Checking ALL Real Credentials")
print("=" * 60)

# ============================================================
# 1. KRAKEN PRIVATE API - Check actual account balance
# ============================================================
print("\n" + "=" * 60)
print("1. KRAKEN PRIVATE API - Real Keys")
print("=" * 60)

KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_API_SECRET = os.getenv("KRAKEN_SECRET_KEY", "")

def kraken_signature(urlpath, data, secret):
    """Create Kraken API signature"""
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data['nonce']) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    sigdigest = base64.b64encode(mac.digest())
    return sigdigest.decode()

def kraken_request(endpoint, data=None):
    """Make authenticated Kraken API request"""
    url = f"https://api.kraken.com{endpoint}"
    if data is None:
        data = {}
    data['nonce'] = str(int(time.time() * 1000))
    
    headers = {
        'API-Key': KRAKEN_API_KEY,
        'API-Sign': kraken_signature(endpoint, data, KRAKEN_API_SECRET),
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    try:
        resp = requests.post(url, headers=headers, data=urllib.parse.urlencode(data), timeout=15)
        return resp.json()
    except Exception as e:
        return {'error': [str(e)]}

# Check balance
print("\nChecking Kraken account balance...")
result = kraken_request('/0/private/Balance')
if result.get('error') and len(result['error']) > 0:
    print(f"  Error: {result['error']}")
else:
    balances = result.get('result', {})
    if balances:
        print(f"  Found {len(balances)} assets!")
        total_usd = 0
        
        # Get current prices for conversion
        try:
            prices_resp = requests.get('https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD,XRPUSD,DOTUSD,ADAUSD,LINKUSD,LTCUSD', timeout=10)
            prices_data = prices_resp.json().get('result', {})
        except:
            prices_data = {}
        
        # Map Kraken asset names to price pairs
        price_map = {}
        for pair_name, pair_data in prices_data.items():
            price_map[pair_name] = float(pair_data['c'][0])  # Last trade price
        
        for asset, amount in balances.items():
            amount_f = float(amount)
            if amount_f > 0:
                usd_val = 0
                # Try to map to USD price
                if asset in ('ZUSD', 'USD', 'USDT', 'USDC'):
                    usd_val = amount_f
                elif asset in ('XXBT', 'XBT', 'BTC'):
                    usd_val = amount_f * price_map.get('XXBTZUSD', price_map.get('XBTUSD', 0))
                elif asset in ('XETH', 'ETH'):
                    usd_val = amount_f * price_map.get('XETHZUSD', price_map.get('ETHUSD', 0))
                elif asset in ('SOL',):
                    usd_val = amount_f * price_map.get('SOLUSD', 0)
                elif asset in ('XRP', 'XXRP'):
                    usd_val = amount_f * price_map.get('XXRPZUSD', price_map.get('XRPUSD', 0))
                elif asset in ('DOT', 'XDOT'):
                    usd_val = amount_f * price_map.get('DOTUSD', 0)
                elif asset in ('ADA',):
                    usd_val = amount_f * price_map.get('ADAUSD', 0)
                elif asset in ('LINK',):
                    usd_val = amount_f * price_map.get('LINKUSD', 0)
                elif asset in ('LTC', 'XLTC'):
                    usd_val = amount_f * price_map.get('XLTCZUSD', price_map.get('LTCUSD', 0))
                
                total_usd += usd_val
                usd_str = f" (~${usd_val:,.2f})" if usd_val > 0 else ""
                print(f"    {asset}: {amount_f:.8f}{usd_str}")
        
        print(f"\n  TOTAL ESTIMATED VALUE: ${total_usd:,.2f}")
    else:
        print("  Account exists but no balances found")

# Check trade balance
print("\nChecking Kraken trade balance...")
result2 = kraken_request('/0/private/TradeBalance', {'asset': 'ZUSD'})
if result2.get('error') and len(result2['error']) > 0:
    print(f"  Error: {result2['error']}")
else:
    tb = result2.get('result', {})
    if tb:
        equiv_balance = float(tb.get('eb', 0))
        trade_balance = float(tb.get('tb', 0))
        margin_amount = float(tb.get('m', 0))
        unrealized_pnl = float(tb.get('n', 0))
        print(f"  Equivalent Balance: ${equiv_balance:,.2f}")
        print(f"  Trade Balance:      ${trade_balance:,.2f}")
        print(f"  Margin Used:        ${margin_amount:,.2f}")
        print(f"  Unrealized P&L:     ${unrealized_pnl:,.2f}")

# Check open orders
print("\nChecking Kraken open orders...")
result3 = kraken_request('/0/private/OpenOrders')
if result3.get('error') and len(result3['error']) > 0:
    print(f"  Error: {result3['error']}")
else:
    orders = result3.get('result', {}).get('open', {})
    if orders:
        print(f"  Found {len(orders)} open orders!")
        for oid, order in orders.items():
            desc = order.get('descr', {})
            print(f"    {desc.get('type', '?')} {desc.get('ordertype', '?')} {desc.get('pair', '?')}: {desc.get('order', '?')}")
    else:
        print("  No open orders")

# ============================================================
# 2. COINBASE v2 API - Key/Secret format (NOT CDP)
# ============================================================
print("\n" + "=" * 60)
print("2. COINBASE v2 API - Key/Secret")
print("=" * 60)

CB_API_KEY = os.getenv("COINBASE_API_KEY", "")
CB_API_SECRET = os.getenv("COINBASE_SECRET_KEY", "")

def coinbase_v2_request(path):
    """Make Coinbase v2 API request with API key/secret"""
    timestamp = str(int(time.time()))
    message = timestamp + 'GET' + path + ''
    
    # Try HMAC-SHA256 with the secret as-is (UUID format)
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
    
    try:
        resp = requests.get(f'https://api.coinbase.com{path}', headers=headers, timeout=15)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {'error': str(e)}

# Test user endpoint
print("\nTesting Coinbase v2 /v2/user...")
status, data = coinbase_v2_request('/v2/user')
print(f"  Status: {status}")
if status == 200:
    user = data.get('data', {})
    print(f"  Name: {user.get('name', '?')}")
    print(f"  Email: {user.get('email', '?')}")
    print(f"  Country: {user.get('country', {}).get('name', '?')}")
else:
    print(f"  Response: {str(data)[:200]}")

# Test accounts endpoint
print("\nTesting Coinbase v2 /v2/accounts...")
status2, data2 = coinbase_v2_request('/v2/accounts?limit=100')
print(f"  Status: {status2}")
if status2 == 200:
    accounts = data2.get('data', [])
    print(f"  Found {len(accounts)} accounts!")
    total_coinbase = 0
    for acct in accounts:
        name = acct.get('name', '?')
        currency = acct.get('currency', {})
        if isinstance(currency, dict):
            code = currency.get('code', '?')
        else:
            code = currency
        bal = acct.get('balance', {}).get('amount', '0')
        native = acct.get('native_balance', {}).get('amount', '0')
        native_curr = acct.get('native_balance', {}).get('currency', 'USD')
        
        bal_f = float(bal)
        native_f = float(native)
        
        if bal_f > 0:
            total_coinbase += native_f
            print(f"    {name} ({code}): {bal_f} = ${native_f:,.2f} {native_curr}")
    
    if total_coinbase > 0:
        print(f"\n  TOTAL COINBASE VALUE: ${total_coinbase:,.2f}")
    else:
        print("  All account balances are $0")
else:
    print(f"  Response: {str(data2)[:300]}")

# ============================================================
# 3. DECRYPT ENCRYPTED WALLETS
# ============================================================
print("\n" + "=" * 60)
print("3. DECRYPTING encrypted_wallets.json")
print("=" * 60)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    with open(r'C:\Users\Admin\OneDrive\Desktop\encrypted_wallets.json', 'r') as f:
        encrypted_data = f.read().strip()
    
    # Try common master passwords  
    passwords = [
        "CHANGE_ME_IN_PRODUCTION",
        "rimuru",
        "rimuru_crypto_empire",
        "admin",
        "password",
        "123456",
        "master",
        "",
    ]
    
    for pwd in passwords:
        try:
            salt = b'rimuru_crypto_empire_salt_v1'
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(pwd.encode()))
            cipher = Fernet(key)
            decrypted = cipher.decrypt(encrypted_data.encode())
            print(f"  DECRYPTED with password: '{pwd}'")
            decoded = decrypted.decode('utf-8')
            print(f"  Content preview: {decoded[:500]}")
            
            # Try to parse as JSON
            try:
                wallet_data = json.loads(decoded)
                if isinstance(wallet_data, list):
                    print(f"  Found {len(wallet_data)} wallets!")
                    for w in wallet_data:
                        print(f"    {w}")
                elif isinstance(wallet_data, dict):
                    for k, v in wallet_data.items():
                        print(f"    {k}: {str(v)[:100]}")
            except:
                pass
            break
        except Exception as e:
            continue
    else:
        print("  Could not decrypt with common passwords")
        print("  The file needs the vault master password to unlock")
        print("  Check _SENSITIVE folder for password hints")
        
except ImportError:
    print("  cryptography package not installed")
except FileNotFoundError:
    print("  encrypted_wallets.json not found")
except Exception as e:
    print(f"  Error: {e}")

# ============================================================  
# 4. CHECK _SENSITIVE FOLDER
# ============================================================
print("\n" + "=" * 60)
print("4. CHECKING _SENSITIVE FOLDER")
print("=" * 60)

import os
sensitive_path = r'C:\Users\Admin\OneDrive\Videos\rimuru_empire\_SENSITIVE'
if os.path.exists(sensitive_path):
    for f in os.listdir(sensitive_path):
        fpath = os.path.join(sensitive_path, f)
        size = os.path.getsize(fpath)
        print(f"  {f} ({size} bytes)")
        
        # Try to read non-encrypted files
        if f.endswith('.txt') or f.endswith('.backup'):
            try:
                with open(fpath, 'r', errors='ignore') as fh:
                    content = fh.read()[:500]
                if content.strip():
                    print(f"    Content: {content[:300]}")
            except:
                pass

# ============================================================
# 5. COINGECKO API KEY CHECK
# ============================================================
print("\n" + "=" * 60)
print("5. COINGECKO API KEY")
print("=" * 60)

CG_KEY = "CG-WikGurCJSdfty6R4NyPdGD9K"
try:
    resp = requests.get(
        'https://api.coingecko.com/api/v3/simple/price',
        params={'ids': 'bitcoin,ethereum', 'vs_currencies': 'usd'},
        headers={'x-cg-demo-api-key': CG_KEY},
        timeout=10
    )
    print(f"  Status: {resp.status_code}")
    if resp.status_code == 200:
        prices = resp.json()
        print(f"  BTC: ${prices.get('bitcoin', {}).get('usd', '?'):,.2f}")
        print(f"  ETH: ${prices.get('ethereum', {}).get('usd', '?'):,.2f}")
        print(f"  CoinGecko API key is WORKING!")
    else:
        print(f"  Response: {resp.text[:200]}")
except Exception as e:
    print(f"  Error: {e}")

# ============================================================
# 6. BRIGHT DATA PROXY KEY
# ============================================================
print("\n" + "=" * 60)
print("6. BRIGHT DATA WEB UNLOCKER")
print("=" * 60)
BD_KEY = "wss://brd-customer-hl_2b60c791-zone-scraping_browser1:ZONE_PASSWORD@brd.superproxy.io:9222"
print(f"  Customer: brd-customer-hl_2b60c791")
print(f"  Zone: scraping_browser1")
print(f"  Note: Password is 'ZONE_PASSWORD' (placeholder)")
print(f"  Status: Needs real zone password to be usable")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("CASHOUT SUMMARY")
print("=" * 60)
