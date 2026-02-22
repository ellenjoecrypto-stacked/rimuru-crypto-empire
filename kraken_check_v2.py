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
import logging
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
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
    logger.info("Secret decoded: %s bytes (expected 64)", len(decoded))
except Exception as e:
    logger.error("Secret decode error: %s", e)

logger.info("=" * 60)
logger.info("  KRAKEN BALANCE CHECK v2")
logger.info("=" * 60)

# Test with simple Balance endpoint
logger.info("\n[1] Checking Balance...")
result = kraken_request('/0/private/Balance')
logger.info("  Raw response: %s", json.dumps(result, indent=2))

if not result.get('error') or len(result['error']) == 0:
    balances = result.get('result', {})
    if not balances:
        logger.info("  >> No balances (empty account)")
    else:
        total_usd = 0
        logger.info("\n  Found %s asset(s):", len(balances))
        for asset, amount in sorted(balances.items()):
            amt = float(amount)
            marker = " *** HAS BALANCE ***" if amt > 0 else ""
            logger.info("    %s: %s%s", asset, amount, marker)

    # Trade Balance
    logger.info("\n[2] Checking Trade Balance...")
    result2 = kraken_request('/0/private/TradeBalance', {'asset': 'ZUSD'})
    if not result2.get('error') or len(result2['error']) == 0:
        tb = result2.get('result', {})
        logger.info("  Equivalent Balance: $%s", tb.get('eb', '0'))
        logger.info("  Trade Balance: $%s", tb.get('tb', '0'))
        logger.info("  Free Margin: $%s", tb.get('mf', '0'))
        logger.info("  Unrealized P&L: $%s", tb.get('n', '0'))
    else:
        logger.error("  ERROR: %s", result2['error'])

    # Open Orders
    logger.info("\n[3] Open Orders...")
    result3 = kraken_request('/0/private/OpenOrders')
    if not result3.get('error') or len(result3['error']) == 0:
        orders = result3.get('result', {}).get('open', {})
        logger.info("  Open orders: %s", len(orders))
    else:
        logger.error("  ERROR: %s", result3['error'])

    # Closed Orders (recent)
    logger.info("\n[4] Recent Closed Orders...")
    result4 = kraken_request('/0/private/ClosedOrders')
    if not result4.get('error') or len(result4['error']) == 0:
        closed = result4.get('result', {}).get('closed', {})
        count = result4.get('result', {}).get('count', 0)
        logger.info("  Total closed orders: %s", count)
        for oid, order in list(closed.items())[:3]:
            desc = order.get('descr', {})
            status = order.get('status', '?')
            logger.info("    [%s] %s", status, desc.get('order', 'N/A'))
    else:
        logger.error("  ERROR: %s", result4['error'])

    # Ledger
    logger.info("\n[5] Recent Ledger...")
    result5 = kraken_request('/0/private/Ledgers')
    if not result5.get('error') or len(result5['error']) == 0:
        ledger = result5.get('result', {}).get('ledger', {})
        count = result5.get('result', {}).get('count', 0)
        logger.info("  Total entries: %s", count)
        for lid, entry in list(ledger.items())[:5]:
            t = entry.get('type', '?')
            asset = entry.get('asset', '?')
            amt = entry.get('amount', '0')
            fee = entry.get('fee', '0')
            logger.info("    %s: %s %s (fee: %s)", t, asset, amt, fee)
    else:
        logger.error("  ERROR: %s", result5['error'])

else:
    logger.error("\n  Auth failed: %s", result['error'])
    logger.info("\n  Debugging signature computation...")
    
    # Try with microsecond nonce
    logger.info("\n  Trying microsecond nonce...")
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
        logger.info("  Result: %s", raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        logger.info("  Result: HTTP %s: %s", e.code, body)
    
    # Try with OTP field
    logger.info("\n  Trying with otp=000000...")
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
        logger.info("  Result: %s", raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        logger.info("  Result: HTTP %s: %s", e.code, body)

# Prices for reference
logger.info("\n[PRICES] Current Market...")
try:
    req = urllib.request.Request("https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    for pair, info in data.get('result', {}).items():
        last = info.get('c', ['?'])[0]
        logger.info("  %s: $%s", pair, "{:,.2f}".format(float(last)))
except Exception as e:
    logger.debug("Skipped: %s", e)

logger.info("%s", "\n" + "=" * 60)
