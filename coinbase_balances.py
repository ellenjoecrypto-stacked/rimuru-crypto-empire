#!/usr/bin/env python3
"""
Pull ALL Coinbase balances - retail + advanced trade
Key is confirmed working!
"""
import json
import time
import secrets
import requests
import jwt as pyjwt

KEY_NAME = "organizations/761837f6-e032-4a33-9a7f-20b39bc890b6/apiKeys/c62fad2a-7a0e-4761-8460-beecf4cc615c"
PRIVATE_KEY = "-----BEGIN EC PRIVATE KEY-----\nMHcCAQEEIG7vP0woDot5TtVm25y811OEkNKJoj6Si0FWhszdOUrsoAoGCCqGSM49\nAwEHoUQDQgAE3/6Cxa66KxrNlAFOJUgjb8F6Dvfg8HvqLnPgAw68asRwEnsH7vo4\notQCCX0XlBfx9VQZKliK7ORZxyp/j9g0Dw==\n-----END EC PRIVATE KEY-----\n"

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
    return resp

print("=" * 60)
print("COINBASE FULL BALANCE REPORT")
print("Account: Marke Standoak / ellenjoecrypto@gmail.com")
print("=" * 60)

# ============================================================
# 1. RETAIL ACCOUNTS (v2)
# ============================================================
print("\n--- RETAIL ACCOUNTS ---")
resp = cdp_get("/v2/accounts")
total_retail = 0

if resp.status_code == 200:
    data = resp.json()
    accounts = data.get('data', [])
    print(f"Found {len(accounts)} accounts:\n")
    
    for acct in accounts:
        name = acct.get('name', '?')
        acct_id = acct.get('id', '?')
        currency = acct.get('currency', {})
        if isinstance(currency, dict):
            code = currency.get('code', '?')
            currency_name = currency.get('name', code)
        else:
            code = str(currency)
            currency_name = code
        
        bal = acct.get('balance', {})
        bal_amount = float(bal.get('amount', '0'))
        bal_currency = bal.get('currency', '?')
        
        native = acct.get('native_balance', {})
        native_amount = float(native.get('amount', '0'))
        native_currency = native.get('currency', 'USD')
        
        acct_type = acct.get('type', '?')
        primary = acct.get('primary', False)
        
        if bal_amount > 0:
            total_retail += native_amount
            marker = " ***HAS BALANCE***"
        else:
            marker = ""
        
        print(f"  {currency_name} ({code}) [{acct_type}]{'  PRIMARY' if primary else ''}{marker}")
        print(f"    Balance: {bal_amount} {bal_currency}")
        print(f"    Value:   ${native_amount:,.2f} {native_currency}")
        print(f"    ID:      {acct_id}")
        print()
    
    print(f"  TOTAL RETAIL: ${total_retail:,.2f}")
else:
    print(f"  Status {resp.status_code}: {resp.text[:200]}")

# ============================================================
# 2. ADVANCED TRADE ACCOUNTS (v3)
# ============================================================
print("\n--- ADVANCED TRADE ACCOUNTS ---")
resp3 = cdp_get("/api/v3/brokerage/accounts")
total_trade = 0

if resp3.status_code == 200:
    data = resp3.json()
    v3_accounts = data.get('accounts', [])
    print(f"Found {len(v3_accounts)} trading accounts:\n")
    
    for acct in v3_accounts:
        name = acct.get('name', '?')
        currency = acct.get('currency', '?')
        uuid = acct.get('uuid', '?')
        
        avail = acct.get('available_balance', {})
        avail_val = float(avail.get('value', '0'))
        avail_curr = avail.get('currency', '?')
        
        hold_info = acct.get('hold', {})
        hold_val = float(hold_info.get('value', '0'))
        
        acct_type = acct.get('type', '?')
        active = acct.get('active', False)
        
        if avail_val > 0 or hold_val > 0:
            marker = " ***HAS BALANCE***"
        else:
            marker = ""
        
        print(f"  {name} ({currency}) [{acct_type}] active={active}{marker}")
        print(f"    Available: {avail_val} {avail_curr}")
        print(f"    On Hold:   {hold_val}")
        print(f"    UUID:      {uuid}")
        print()
else:
    print(f"  Status {resp3.status_code}: {resp3.text[:200]}")

# ============================================================
# 3. PORTFOLIOS
# ============================================================
print("\n--- PORTFOLIOS ---")
resp4 = cdp_get("/api/v3/brokerage/portfolios")
if resp4.status_code == 200:
    portfolios = resp4.json().get('portfolios', [])
    for p in portfolios:
        print(f"  {p.get('name', '?')} (type={p.get('type', '?')})")
        print(f"    UUID: {p.get('uuid', '?')}")
        print(f"    Deleted: {p.get('deleted', False)}")
else:
    print(f"  Status {resp4.status_code}")

# ============================================================
# 4. BTC PRICE FOR CONTEXT
# ============================================================
print("\n--- CURRENT PRICES ---")
resp5 = cdp_get("/v2/prices/BTC-USD/spot")
if resp5.status_code == 200:
    price = resp5.json().get('data', {})
    print(f"  BTC: ${float(price.get('amount', 0)):,.2f}")

resp6 = cdp_get("/v2/prices/ETH-USD/spot")
if resp6.status_code == 200:
    price = resp6.json().get('data', {})
    print(f"  ETH: ${float(price.get('amount', 0)):,.2f}")

resp7 = cdp_get("/v2/prices/SOL-USD/spot")
if resp7.status_code == 200:
    price = resp7.json().get('data', {})
    print(f"  SOL: ${float(price.get('amount', 0)):,.2f}")

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("CASHOUT SUMMARY")
print("=" * 60)
if total_retail > 0:
    print(f"\n  TOTAL CASHABLE VALUE: ${total_retail:,.2f}")
    print(f"\n  To cash out, log into coinbase.com in Edge and:")
    print(f"  1. Sell crypto to USD")
    print(f"  2. Withdraw USD to your Chase/Frost bank")
else:
    print(f"\n  Retail balance: ${total_retail:,.2f}")
    print(f"  Check the account details above for any value")
