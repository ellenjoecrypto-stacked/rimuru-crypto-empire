"""
Kraken Full Balance Report - Fresh keys working!
"""
import krakenex
import json
import urllib.request

KEY = "IhmgBPPPOo/MdJ+c9l6jm2LtaZEdnOvjTIp7jqbXnbd6fqno9VSOE5Xi"
SECRET = "szEbzhHThEmcpYDlATJdxX09CEQ6zS/3zD2DNgn6uaoyYeJvBPr52BqEfJFLAv4wnBV9xxaFCOHUbe6HJfYkQg=="

k = krakenex.API()
k.key = KEY
k.secret = SECRET

print("=" * 60)
print("  KRAKEN ACCOUNT - FULL BALANCE REPORT")
print("=" * 60)

# 1. Get balances
bal = k.query_private('Balance')
if bal['error']:
    print(f"ERROR: {bal['error']}")
    exit()

balances = bal['result']
print(f"\nFound {len(balances)} asset(s):\n")

# Map Kraken asset names to standard tickers for price lookup
asset_map = {
    'XXBT': ('BTC', 'XXBTZUSD'),
    'XETH': ('ETH', 'XETHZUSD'),
    'SOL': ('SOL', 'SOLUSD'),
    'PEPE': ('PEPE', 'PEPEUSD'),
    'XXDG': ('DOGE', 'XDGUSD'),
    'PAXG': ('PAXG', 'PAXGUSD'),
    'BABY': ('BABY', 'BABYUSD'),
    'USDG': ('USDG', None),  # stablecoin ~$1
    'USD.HOLD': ('USD', None),
}

# Get all prices at once
pairs = [v[1] for v in asset_map.values() if v[1]]
pair_str = ','.join(pairs)

try:
    req = urllib.request.Request(f"https://api.kraken.com/0/public/Ticker?pair={pair_str}")
    resp = urllib.request.urlopen(req, timeout=10)
    price_data = json.loads(resp.read().decode()).get('result', {})
except:
    price_data = {}

# Calculate values
total_usd = 0
print(f"  {'Asset':<10} {'Amount':>18} {'Price':>12} {'Value':>12}")
print(f"  {'-'*10} {'-'*18} {'-'*12} {'-'*12}")

for kraken_name, amount_str in sorted(balances.items()):
    amount = float(amount_str)
    if amount <= 0:
        continue
    
    info = asset_map.get(kraken_name)
    if info:
        ticker, pair = info
        if pair and pair in price_data:
            price = float(price_data[pair]['c'][0])
            value = amount * price
        elif pair:
            # Try alternate pair name
            for pname, pdata in price_data.items():
                if ticker.upper() in pname.upper():
                    price = float(pdata['c'][0])
                    value = amount * price
                    break
            else:
                price = 0
                value = 0
        else:
            # Stablecoin or USD
            price = 1.0
            value = amount
    else:
        ticker = kraken_name
        price = 0
        value = 0
    
    total_usd += value
    price_str = f"${price:,.4f}" if price > 0 else "N/A"
    value_str = f"${value:,.4f}" if value > 0 else "$0.00"
    print(f"  {ticker:<10} {amount:>18.10f} {price_str:>12} {value_str:>12}")

print(f"\n  {'TOTAL USD VALUE':>42} ${total_usd:,.4f}")

# 2. Trade Balance
print(f"\n{'='*60}")
print("  TRADE BALANCE")
tb = k.query_private('TradeBalance', {'asset': 'ZUSD'})
if not tb['error']:
    r = tb['result']
    print(f"  Equivalent Balance: ${r.get('eb', '0')}")
    print(f"  Trade Balance:      ${r.get('tb', '0')}")
    print(f"  Free Margin:        ${r.get('mf', '0')}")
    print(f"  Unrealized P&L:     ${r.get('n', '0')}")

# 3. Open Orders
print(f"\n{'='*60}")
print("  OPEN ORDERS")
oo = k.query_private('OpenOrders')
if not oo['error']:
    orders = oo['result'].get('open', {})
    if orders:
        for oid, o in orders.items():
            d = o.get('descr', {})
            print(f"  {d.get('order', 'N/A')} | status: {o.get('status')}")
    else:
        print("  No open orders")

# 4. Recent Closed Orders
print(f"\n{'='*60}")
print("  RECENT CLOSED ORDERS")
co = k.query_private('ClosedOrders')
if not co['error']:
    closed = co['result'].get('closed', {})
    count = co['result'].get('count', 0)
    print(f"  Total closed: {count}")
    for oid, o in list(closed.items())[:5]:
        d = o.get('descr', {})
        print(f"  [{o.get('status')}] {d.get('order', 'N/A')}")

# 5. Ledger
print(f"\n{'='*60}")
print("  RECENT LEDGER ENTRIES")
lg = k.query_private('Ledgers')
if not lg['error']:
    ledger = lg['result'].get('ledger', {})
    count = lg['result'].get('count', 0)
    print(f"  Total entries: {count}")
    for lid, e in list(ledger.items())[:10]:
        t = e.get('type', '?')
        asset = e.get('asset', '?')
        amt = e.get('amount', '0')
        fee = e.get('fee', '0')
        ts = e.get('time', 0)
        print(f"  {t:>10}: {asset:<6} {amt:>18} (fee: {fee})")

print(f"\n{'='*60}")
print("  REPORT COMPLETE")
print("=" * 60)
