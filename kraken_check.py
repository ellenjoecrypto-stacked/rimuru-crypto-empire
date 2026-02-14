"""
Kraken Balance Checker - Tests fresh API keys
"""
import urllib.request
import urllib.parse
import hashlib
import hmac
import base64
import time
import json

KRAKEN_KEY = "tWIl09svL9gZrfbuJImQZLc05F/OOtjmoQ6H1ONGi0LzPgvI7Xn8/yUw"
KRAKEN_SECRET = "k9AjtU6jTO/3Yz5l6H3KRcBQP11+/la66QyP9WhMN+GEsojlHzzG0/rtQnIP3a3fAprcvI7CR4JZbc6GVYN9Uw=="

def kraken_signature(urlpath, data, secret):
    postdata = urllib.parse.urlencode(data)
    encoded = (str(data['nonce']) + postdata).encode()
    message = urlpath.encode() + hashlib.sha256(encoded).digest()
    mac = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    return base64.b64encode(mac.digest()).decode()

def kraken_request(endpoint, data=None):
    url = f"https://api.kraken.com{endpoint}"
    if data is None:
        data = {}
    data['nonce'] = str(int(time.time() * 1000))
    
    sig = kraken_signature(endpoint, data, KRAKEN_SECRET)
    postdata = urllib.parse.urlencode(data).encode()
    
    req = urllib.request.Request(url, data=postdata)
    req.add_header('API-Key', KRAKEN_KEY)
    req.add_header('API-Sign', sig)
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return {"error": [f"HTTP {e.code}: {body}"]}
    except Exception as e:
        return {"error": [str(e)]}

print("=" * 60)
print("  KRAKEN BALANCE CHECK")
print("=" * 60)

# 1. Check Balance
print("\n[1] Checking Balance...")
result = kraken_request('/0/private/Balance')
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    balances = result.get('result', {})
    if not balances:
        print("  No balances found (empty account)")
    else:
        print(f"  Found {len(balances)} asset(s):")
        for asset, amount in balances.items():
            amt = float(amount)
            if amt > 0:
                print(f"    {asset}: {amount} ***HAS BALANCE***")
            else:
                print(f"    {asset}: {amount}")

# 2. Trade Balance
print("\n[2] Checking Trade Balance...")
result = kraken_request('/0/private/TradeBalance', {'asset': 'ZUSD'})
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    tb = result.get('result', {})
    if tb:
        equiv = tb.get('eb', '0')
        trade_bal = tb.get('tb', '0')
        margin = tb.get('m', '0')
        unrealized = tb.get('n', '0')
        print(f"  Equivalent Balance: ${equiv}")
        print(f"  Trade Balance: ${trade_bal}")
        print(f"  Margin Used: ${margin}")
        print(f"  Unrealized P&L: ${unrealized}")

# 3. Open Orders
print("\n[3] Checking Open Orders...")
result = kraken_request('/0/private/OpenOrders')
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    orders = result.get('result', {}).get('open', {})
    print(f"  Open orders: {len(orders)}")
    for oid, order in orders.items():
        desc = order.get('descr', {})
        print(f"    {oid}: {desc.get('type')} {desc.get('order')}")

# 4. Deposit Methods
print("\n[4] Checking Deposit Methods...")
result = kraken_request('/0/private/DepositMethods', {'asset': 'ZUSD'})
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    methods = result.get('result', [])
    print(f"  Available deposit methods: {len(methods)}")
    for m in methods:
        print(f"    - {m.get('method')}: min={m.get('minimum', 'N/A')}, fee={m.get('fee', 'N/A')}")

# 5. Withdrawal Info
print("\n[5] Checking Deposit Addresses (BTC)...")
result = kraken_request('/0/private/DepositAddresses', {'asset': 'XXBT', 'method': 'Bitcoin'})
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    addrs = result.get('result', [])
    print(f"  BTC deposit addresses: {len(addrs)}")
    for a in addrs:
        print(f"    {a.get('address', 'N/A')} (new={a.get('new', False)})")

# 6. Staking
print("\n[6] Checking Staking Assets...")
result = kraken_request('/0/private/Staking/Assets')
if result.get('error') and len(result['error']) > 0:
    # Try alternate endpoint
    result2 = kraken_request('/0/private/Stake', {'asset': 'ETH', 'amount': '0', 'method': 'no-method'})
    if 'Permission denied' in str(result2):
        print("  Staking endpoint: Permission denied (key doesn't have staking perms)")
    else:
        print(f"  Staking check: {result2.get('error', 'N/A')}")
else:
    print(f"  Staking assets: {result.get('result', {})}")

# 7. Ledger (recent transactions)
print("\n[7] Checking Recent Ledger Entries...")
result = kraken_request('/0/private/Ledgers')
if result.get('error') and len(result['error']) > 0:
    print(f"  ERROR: {result['error']}")
else:
    ledger = result.get('result', {}).get('ledger', {})
    count = result.get('result', {}).get('count', 0)
    print(f"  Total ledger entries: {count}")
    for lid, entry in list(ledger.items())[:5]:
        print(f"    {entry.get('type')}: {entry.get('asset')} {entry.get('amount')} (fee: {entry.get('fee')})")

# Get prices for context
print("\n[8] Current Prices (public)...")
try:
    req = urllib.request.Request("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    tickers = data.get('result', {})
    for pair, info in tickers.items():
        last = info.get('c', ['?'])[0]
        print(f"  {pair}: ${float(last):,.2f}")
except:
    print("  Could not fetch prices")

print("\n" + "=" * 60)
print("  KRAKEN CHECK COMPLETE")
print("=" * 60)
