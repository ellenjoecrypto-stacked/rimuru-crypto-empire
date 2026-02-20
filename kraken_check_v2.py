"""
Kraken Balance Checker v2 - Fixed signature
"""
import urllib.request
import urllib.parse
import hashlib
import hmac
import base64
import time
import json
import os
from dotenv import load_dotenv
load_dotenv()

KRAKEN_KEY = os.getenv("KRAKEN_API_KEY", "")
KRAKEN_SECRET = os.getenv("KRAKEN_SECRET_KEY", "")

if not KRAKEN_KEY or not KRAKEN_SECRET:
    raise EnvironmentError("KRAKEN_API_KEY and KRAKEN_SECRET_KEY must be set in .env")

def kraken_signature(urlpath, data, secret):
    """Generate Kraken API signature per their docs:
    HMAC-SHA512 of (URI path + SHA256(nonce + POST data))
    using base64-decoded API secret as HMAC key
    """
    postdata = urllib.parse.urlencode(data)
    # SHA256(nonce + postdata)
    encoded = (str(data['nonce']) + postdata).encode('utf-8')
    sha256_hash = hashlib.sha256(encoded).digest()
    # HMAC-SHA512(urlpath + sha256hash, secret)
    message = urlpath.encode('utf-8') + sha256_hash
    secret_bytes = base64.b64decode(secret)
    mac = hmac.new(secret_bytes, message, hashlib.sha512)
    sigdigest = mac.digest()
    return base64.b64encode(sigdigest).decode('utf-8')

def kraken_request(endpoint, extra_data=None):
    url = f"https://api.kraken.com{endpoint}"
    nonce = str(int(time.time() * 1000))
    
    data = {'nonce': nonce}
    if extra_data:
        data.update(extra_data)
    
    sig = kraken_signature(endpoint, data, KRAKEN_SECRET)
    postdata = urllib.parse.urlencode(data).encode('utf-8')
    
    req = urllib.request.Request(url, data=postdata, method='POST')
    req.add_header('API-Key', KRAKEN_KEY)
    req.add_header('API-Sign', sig)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    req.add_header('User-Agent', 'Kraken Python Client')
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read().decode('utf-8')
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        return {"error": [f"HTTP {e.code}: {body}"]}
    except Exception as e:
        return {"error": [str(e)]}

# Debug: verify secret decodes correctly
try:
    decoded = base64.b64decode(KRAKEN_SECRET)
    print(f"Secret decoded: {len(decoded)} bytes (expected 64)")
except Exception as e:
    print(f"Secret decode error: {e}")

print("=" * 60)
print("  KRAKEN BALANCE CHECK v2")
print("=" * 60)

# Test with simple Balance endpoint
print("\n[1] Checking Balance...")
result = kraken_request('/0/private/Balance')
print(f"  Raw response: {json.dumps(result, indent=2)}")

if not result.get('error') or len(result['error']) == 0:
    balances = result.get('result', {})
    if not balances:
        print("  >> No balances (empty account)")
    else:
        total_usd = 0
        print(f"\n  Found {len(balances)} asset(s):")
        for asset, amount in sorted(balances.items()):
            amt = float(amount)
            marker = " *** HAS BALANCE ***" if amt > 0 else ""
            print(f"    {asset}: {amount}{marker}")

    # Trade Balance
    print("\n[2] Checking Trade Balance...")
    result2 = kraken_request('/0/private/TradeBalance', {'asset': 'ZUSD'})
    if not result2.get('error') or len(result2['error']) == 0:
        tb = result2.get('result', {})
        print(f"  Equivalent Balance: ${tb.get('eb', '0')}")
        print(f"  Trade Balance: ${tb.get('tb', '0')}")
        print(f"  Free Margin: ${tb.get('mf', '0')}")
        print(f"  Unrealized P&L: ${tb.get('n', '0')}")
    else:
        print(f"  ERROR: {result2['error']}")

    # Open Orders
    print("\n[3] Open Orders...")
    result3 = kraken_request('/0/private/OpenOrders')
    if not result3.get('error') or len(result3['error']) == 0:
        orders = result3.get('result', {}).get('open', {})
        print(f"  Open orders: {len(orders)}")
    else:
        print(f"  ERROR: {result3['error']}")

    # Closed Orders (recent)
    print("\n[4] Recent Closed Orders...")
    result4 = kraken_request('/0/private/ClosedOrders')
    if not result4.get('error') or len(result4['error']) == 0:
        closed = result4.get('result', {}).get('closed', {})
        count = result4.get('result', {}).get('count', 0)
        print(f"  Total closed orders: {count}")
        for oid, order in list(closed.items())[:3]:
            desc = order.get('descr', {})
            status = order.get('status', '?')
            print(f"    [{status}] {desc.get('order', 'N/A')}")
    else:
        print(f"  ERROR: {result4['error']}")

    # Ledger
    print("\n[5] Recent Ledger...")
    result5 = kraken_request('/0/private/Ledgers')
    if not result5.get('error') or len(result5['error']) == 0:
        ledger = result5.get('result', {}).get('ledger', {})
        count = result5.get('result', {}).get('count', 0)
        print(f"  Total entries: {count}")
        for lid, entry in list(ledger.items())[:5]:
            t = entry.get('type', '?')
            asset = entry.get('asset', '?')
            amt = entry.get('amount', '0')
            fee = entry.get('fee', '0')
            print(f"    {t}: {asset} {amt} (fee: {fee})")
    else:
        print(f"  ERROR: {result5['error']}")

else:
    print(f"\n  Auth failed: {result['error']}")
    print("\n  Debugging signature computation...")
    
    # Try with microsecond nonce
    print("\n  Trying microsecond nonce...")
    nonce = str(int(time.time() * 1000000))
    data = {'nonce': nonce}
    sig = kraken_signature('/0/private/Balance', data, KRAKEN_SECRET)
    postdata = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request("https://api.kraken.com/0/private/Balance", data=postdata, method='POST')
    req.add_header('API-Key', KRAKEN_KEY)
    req.add_header('API-Sign', sig)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read().decode('utf-8')
        print(f"  Result: {raw}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"  Result: HTTP {e.code}: {body}")
    
    # Try with OTP field
    print("\n  Trying with otp=000000...")
    nonce = str(int(time.time() * 1000))
    data = {'nonce': nonce, 'otp': '000000'}
    sig = kraken_signature('/0/private/Balance', data, KRAKEN_SECRET)
    postdata = urllib.parse.urlencode(data).encode('utf-8')
    req = urllib.request.Request("https://api.kraken.com/0/private/Balance", data=postdata, method='POST')
    req.add_header('API-Key', KRAKEN_KEY)
    req.add_header('API-Sign', sig)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        raw = resp.read().decode('utf-8')
        print(f"  Result: {raw}")
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f"  Result: HTTP {e.code}: {body}")

# Prices for reference
print("\n[PRICES] Current Market...")
try:
    req = urllib.request.Request("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    for pair, info in data.get('result', {}).items():
        last = info.get('c', ['?'])[0]
        print(f"  {pair}: ${float(last):,.2f}")
except:
    pass

print("\n" + "=" * 60)
