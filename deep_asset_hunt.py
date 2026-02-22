#!/usr/bin/env python3
"""
DEEP ASSET HUNT - Find EVERYTHING that could have value
Searches for browser wallets, desktop wallets, private keys, 
exchange sessions, gift cards, and more.
"""
import logging
import os
import re
import json
import glob
import base64
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("=" * 60)
print("DEEP ASSET HUNT")
print("=" * 60)

BASE = r"C:\Users\Admin"

# ============================================================
# 1. TRY TO DECRYPT encrypted_wallets.json WITH VAULT PASSWORD
# ============================================================
print("\n[1] DECRYPTING encrypted_wallets.json with vault passwords...")
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    
    with open(os.path.join(BASE, r'OneDrive\Desktop\encrypted_wallets.json'), 'r') as f:
        enc_data = f.read().strip()
    
    # Try all possible passwords including the one from .env.backup
    passwords = [
        "ChangeMe_VeryStrongPassword2024!@#$%",
        "ChangeMe_AdminPassword2024!@#$%^",
        "CHANGE_ME_IN_PRODUCTION",
        "rimuru",
        "rimuru_crypto_empire",
        "RimuruEmpire2024",
        "admin",
        "password",
        "master",
        "",
        "your-super-secret-jwt-key-change-this-in-production",
    ]
    
    decrypted = False
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
            result = cipher.decrypt(enc_data.encode())
            decoded = result.decode('utf-8')
            print(f"  SUCCESS! Decrypted with: '{pwd}'")
            print(f"  Content: {decoded[:1000]}")
            decrypted = True
            break
        except Exception as e:
            logger.debug("Decryption attempt failed: %s", e)
            continue
        # Try with salt from _SENSITIVE folder
        salt_path = os.path.join(BASE, r'OneDrive\Videos\rimuru_empire\_SENSITIVE\VAULT_DATA\.salt')
        if os.path.exists(salt_path):
            with open(salt_path, 'rb') as f:
                custom_salt = f.read()
            print(f"  Found custom salt: {custom_salt.hex()} ({len(custom_salt)} bytes)")
            
            for pwd in passwords:
                try:
                    kdf = PBKDF2HMAC(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=custom_salt,
                        iterations=100000,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(pwd.encode()))
                    cipher = Fernet(key)
                    result = cipher.decrypt(enc_data.encode())
                    decoded = result.decode('utf-8')
                    print(f"  SUCCESS with custom salt! Password: '{pwd}'")
                    print(f"  Content: {decoded[:1000]}")
                    decrypted = True
                    break
                except Exception as e:
                    logger.debug("Decryption attempt failed: %s", e)
                    continue
        
        if not decrypted:
            print("  Could not decrypt - need the real master password")
            
except Exception as e:
    print(f"  Error: {e}")

# ============================================================
# 2. SEARCH FOR BROWSER WALLET DATA
# ============================================================
print("\n[2] SEARCHING FOR BROWSER WALLETS...")

browser_paths = {
    'MetaMask (Chrome)': os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Extensions\nkbihfbeogaeaoehlefnkodbefgpgknn'),
    'MetaMask (Edge)': os.path.join(BASE, r'AppData\Local\Microsoft\Edge\User Data\Default\Extensions\ejbalbakoplchlghecdalmeeeajnimhm'),
    'MetaMask (Brave)': os.path.join(BASE, r'AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Extensions\nkbihfbeogaeaoehlefnkodbefgpgknn'),
    'Coinbase Wallet (Chrome)': os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Extensions\hnfanknocfeofbddgcijnmhnfnkdnaad'),
    'Phantom (Chrome)': os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Extensions\bfnaelmomeimhlpmgjnjophhpkkoljpa'),
    'Rabby (Chrome)': os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Extensions\acmacodkjbdgmoleebolmdjonilkdbch'),
    'Trust Wallet (Chrome)': os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Extensions\egjidjbpglichdcondbcbdnbeeppgdph'),
}

# Also check Chrome profile IndexedDB for wallet data
chrome_profiles = [
    os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default'),
    os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Profile 1'),
    os.path.join(BASE, r'AppData\Local\Microsoft\Edge\User Data\Default'),
    os.path.join(BASE, r'AppData\Local\BraveSoftware\Brave-Browser\User Data\Default'),
]

for name, path in browser_paths.items():
    if os.path.exists(path):
        print(f"  FOUND: {name}")
        # List versions
        try:
            versions = os.listdir(path)
            print(f"    Versions: {versions}")
        except Exception as e:
            logger.debug("Could not list versions for %s: %s", name, e)
    else:
        print(f"  Not found: {name}")

# Check Chrome Local Storage / IndexedDB for wallet data
print("\n  Checking browser storage for wallet data...")
for profile in chrome_profiles:
    local_storage = os.path.join(profile, 'Local Storage', 'leveldb')
    indexed_db = os.path.join(profile, 'IndexedDB')
    
    if os.path.exists(local_storage):
        browser_name = 'Chrome' if 'Chrome' in profile else 'Edge' if 'Edge' in profile else 'Brave'
        print(f"  {browser_name} Local Storage exists")
    
    if os.path.exists(indexed_db):
        browser_name = 'Chrome' if 'Chrome' in profile else 'Edge' if 'Edge' in profile else 'Brave'
        # Look for wallet-related databases
        try:
            for db_dir in os.listdir(indexed_db):
                if any(w in db_dir.lower() for w in ['metamask', 'coinbase', 'phantom', 'wallet', 'rabby']):
                    print(f"  FOUND WALLET DB: {browser_name} / {db_dir}")
        except Exception as e:
            logger.debug("Could not list IndexedDB for %s: %s", browser_name, e)

# ============================================================
# 3. SEARCH FOR DESKTOP WALLETS
# ============================================================
print("\n[3] SEARCHING FOR DESKTOP WALLETS...")

desktop_wallets = {
    'Exodus': os.path.join(BASE, r'AppData\Roaming\Exodus'),
    'Electrum': os.path.join(BASE, r'AppData\Roaming\Electrum'),
    'Electrum-LTC': os.path.join(BASE, r'AppData\Roaming\Electrum-LTC'),
    'Atomic Wallet': os.path.join(BASE, r'AppData\Local\atomic'),
    'Ledger Live': os.path.join(BASE, r'AppData\Roaming\Ledger Live'),
    'Wasabi Wallet': os.path.join(BASE, r'AppData\Roaming\WasabiWallet'),
    'Bitcoin Core': os.path.join(BASE, r'AppData\Roaming\Bitcoin'),
    'Ethereum (Geth)': os.path.join(BASE, r'AppData\Roaming\Ethereum'),
    'Sollet': os.path.join(BASE, r'AppData\Roaming\Sollet'),
    'Daedalus': os.path.join(BASE, r'AppData\Roaming\Daedalus Mainnet'),
    'Trust Wallet Desktop': os.path.join(BASE, r'AppData\Roaming\trust-wallet'),
    'Coinomi': os.path.join(BASE, r'AppData\Roaming\Coinomi'),
    'MyEtherWallet': os.path.join(BASE, r'AppData\Roaming\MyEtherWallet'),
}

for name, path in desktop_wallets.items():
    if os.path.exists(path):
        print(f"  FOUND: {name} at {path}")
        try:
            total_size = sum(os.path.getsize(os.path.join(dp, f)) for dp, dn, fn in os.walk(path) for f in fn)
            file_count = sum(len(fn) for _, _, fn in os.walk(path))
            print(f"    Size: {total_size / 1024:.0f} KB, Files: {file_count}")
            
            # Look for keystore/wallet files
            for dp, dn, fn in os.walk(path):
                for f in fn:
                    fl = f.lower()
                    if any(kw in fl for kw in ['wallet', 'keystore', 'key', 'seed', 'backup', 'vault']):
                        fpath = os.path.join(dp, f)
                        print(f"    KEY FILE: {f} ({os.path.getsize(fpath)} bytes)")
        except Exception as e:
            logger.debug("Could not inspect wallet directory %s: %s", name, e)
    else:
        pass  # Only print found ones

# ============================================================
# 4. SEARCH FOR PRIVATE KEYS ON DISK
# ============================================================
print("\n[4] SCANNING FOR PRIVATE KEYS & SEEDS...")

# Look in common locations for key files
key_locations = [
    os.path.join(BASE, 'Desktop'),
    os.path.join(BASE, 'Documents'),
    os.path.join(BASE, 'Downloads'),
    os.path.join(BASE, r'OneDrive\Desktop'),
    os.path.join(BASE, r'OneDrive\Documents'),
    os.path.join(BASE, r'OneDrive\Videos\rimuru_empire'),
]

key_patterns = [
    r'(?:^|\s)((?:[a-z]+ ){11}[a-z]+)(?:\s|$)',  # 12-word seed phrase
    r'(?:^|\s)((?:[a-z]+ ){23}[a-z]+)(?:\s|$)',  # 24-word seed phrase
    r'(0x[a-fA-F0-9]{64})',  # ETH private key
    r'([5KL][1-9A-HJ-NP-Za-km-z]{50,51})',  # BTC private key (WIF)
]

found_keys = []
for loc in key_locations:
    if not os.path.exists(loc):
        continue
    try:
        for f in os.listdir(loc):
            if not os.path.isfile(os.path.join(loc, f)):
                continue
            fl = f.lower()
            ext = os.path.splitext(f)[1].lower()
            
            # Check interesting files
            if ext in ['.txt', '.json', '.key', '.pem', '.env', '.bak', '.backup', '.secret']:
                fpath = os.path.join(loc, f)
                try:
                    size = os.path.getsize(fpath)
                    if size > 1000000:  # skip >1MB
                        continue
                    with open(fpath, 'r', errors='ignore') as fh:
                        content = fh.read()
                    
                    # Check for private keys
                    for pattern in key_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            print(f"  POTENTIAL KEY in {f}: {len(matches)} match(es)")
                            for m in matches[:3]:
                                preview = m[:20] + "..." if len(m) > 20 else m
                                print(f"    {preview}")
                            found_keys.append((f, loc, matches))
                except Exception as e:
                    logger.debug("Skipped file during key scan: %s", e)
    except Exception as e:
        logger.debug("Skipped location during key scan: %s", e)

if not found_keys:
    print("  No private keys or seed phrases found in common locations")

# ============================================================
# 5. CHECK FOR EXCHANGE SESSIONS / COOKIES
# ============================================================
print("\n[5] CHECKING FOR ACTIVE EXCHANGE SESSIONS...")

# Check browser cookies for exchange sessions
cookie_dbs = [
    ('Chrome', os.path.join(BASE, r'AppData\Local\Google\Chrome\User Data\Default\Network\Cookies')),
    ('Edge', os.path.join(BASE, r'AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies')),
    ('Brave', os.path.join(BASE, r'AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Network\Cookies')),
]

exchange_domains = ['kraken.com', 'coinbase.com', 'binance.com', 'crypto.com', 
                    'kucoin.com', 'bybit.com', 'okx.com', 'gemini.com',
                    'robinhood.com', 'paypal.com', 'venmo.com', 'cashapp.com']

for browser_name, cookie_path in cookie_dbs:
    if os.path.exists(cookie_path):
        print(f"\n  {browser_name} cookies found")
        try:
            # Copy to temp to avoid lock
            import shutil
            temp_path = os.path.join(os.environ.get('TEMP', '.'), f'{browser_name}_cookies_tmp.db')
            shutil.copy2(cookie_path, temp_path)
            
            conn = sqlite3.connect(temp_path)
            cursor = conn.cursor()
            
            for domain in exchange_domains:
                cursor.execute("SELECT COUNT(*) FROM cookies WHERE host_key LIKE ?", (f'%{domain}%',))
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.execute("SELECT host_key, name, expires_utc FROM cookies WHERE host_key LIKE ? LIMIT 5", (f'%{domain}%',))
                    print(f"    {domain}: {count} cookies")
                    for row in cursor.fetchall():
                        # Check if session is still valid
                        exp = row[2]
                        if exp > 0:
                            # Chrome epoch is Jan 1, 1601
                            import datetime
                            try:
                                exp_date = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=exp)
                                is_valid = exp_date > datetime.datetime.now()
                                status = "ACTIVE" if is_valid else "expired"
                                print(f"      {row[1]}: {status} (exp: {exp_date.strftime('%Y-%m-%d')})")
                            except Exception as e:
                                logger.debug("Could not parse cookie expiry for %s: %s", row[1], e)
                                print(f"      {row[1]}: unknown expiry")
            
            conn.close()
            os.remove(temp_path)
        except Exception as e:
            print(f"    Error reading cookies: {e}")

# ============================================================
# 6. SCAN FOR GIFT CARDS & PREPAID CARDS
# ============================================================
print("\n[6] SCANNING FOR GIFT CARDS / PREPAID CARDS...")

gc_patterns = {
    'Amazon': r'[A-Z0-9]{4}-[A-Z0-9]{6}-[A-Z0-9]{4}',
    'iTunes/Apple': r'X[A-Z0-9]{15}',
    'Google Play': r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}',
    'Steam': r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}',
    'Xbox': r'[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}',
    'Visa/MC Prepaid': r'(?:4[0-9]{15}|5[1-5][0-9]{14})',
    'Generic Gift Card': r'(?:gift\s*card|prepaid|balance|redeem)\s*[:=]?\s*\$?[\d,.]+',
}

gc_found = []
scan_dirs = [
    os.path.join(BASE, 'Desktop'),
    os.path.join(BASE, 'Documents'),
    os.path.join(BASE, 'Downloads'),
    os.path.join(BASE, r'OneDrive\Desktop'),
    os.path.join(BASE, r'OneDrive\Documents'),
    os.path.join(BASE, 'Pictures'),
]

for scan_dir in scan_dirs:
    if not os.path.exists(scan_dir):
        continue
    try:
        for f in os.listdir(scan_dir):
            fl = f.lower()
            ext = os.path.splitext(f)[1].lower()
            
            # Check text files and files with gift card related names
            if ext in ['.txt', '.json', '.csv', '.md', '.html'] or \
               any(kw in fl for kw in ['gift', 'card', 'code', 'redeem', 'voucher', 'prepaid', 'reward']):
                fpath = os.path.join(scan_dir, f)
                try:
                    if os.path.getsize(fpath) > 500000:
                        continue
                    with open(fpath, 'r', errors='ignore') as fh:
                        content = fh.read()
                    
                    for gc_type, pattern in gc_patterns.items():
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        if matches and gc_type != 'Generic Gift Card':
                            print(f"  POTENTIAL {gc_type} in {f}: {len(matches)} match(es)")
                            gc_found.append((gc_type, f, matches[:3]))
                        elif matches and gc_type == 'Generic Gift Card':
                            for m in matches:
                                if 'example' not in m.lower() and 'test' not in m.lower():
                                    print(f"  {gc_type} reference in {f}: {m.strip()}")
                except Exception as e:
                    logger.debug("Skipped file during gift card scan: %s", e)
    except Exception as e:
        logger.debug("Skipped directory during gift card scan: %s", e)

if not gc_found:
    print("  No gift card codes found in common locations")

# ============================================================
# 7. CHECK FOR EXCHANGE APPS / TOOLS
# ============================================================
print("\n[7] CHECKING FOR EXCHANGE APPS...")

app_paths = {
    'Coinbase Desktop': os.path.join(BASE, r'AppData\Local\Programs\coinbase'),
    'Kraken Desktop': os.path.join(BASE, r'AppData\Local\kraken'),
    'Binance Desktop': os.path.join(BASE, r'AppData\Local\Binance'),
    'Exodus Desktop': os.path.join(BASE, r'AppData\Local\Programs\exodus'),
    'Ledger Live': os.path.join(BASE, r'AppData\Local\Programs\ledger-live'),
    'Trezor Suite': os.path.join(BASE, r'AppData\Local\Programs\@trezor'),
}

for name, path in app_paths.items():
    if os.path.exists(path):
        print(f"  FOUND: {name}")

# Also check Start Menu shortcuts
start_menu = os.path.join(BASE, r'AppData\Roaming\Microsoft\Windows\Start Menu\Programs')
if os.path.exists(start_menu):
    for root, dirs, files in os.walk(start_menu):
        for f in files:
            fl = f.lower()
            if any(kw in fl for kw in ['coinbase', 'kraken', 'binance', 'exodus', 'metamask', 
                                        'ledger', 'trezor', 'phantom', 'trust', 'crypto']):
                print(f"  SHORTCUT: {f}")

# ============================================================
# 8. CHECK FOR PAYPAL / VENMO / CASHAPP DATA
# ============================================================
print("\n[8] CHECKING FOR PAYMENT APP DATA...")
# Search for payment app configs/data
payment_dirs = [
    os.path.join(BASE, r'AppData\Local\Packages'),  # Windows Store apps
]

for pd in payment_dirs:
    if os.path.exists(pd):
        try:
            for d in os.listdir(pd):
                dl = d.lower()
                if any(kw in dl for kw in ['paypal', 'venmo', 'cashapp', 'cash.app', 'zelle']):
                    print(f"  FOUND: {d}")
        except Exception as e:
            logger.debug("Could not list payment app packages: %s", e)

# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("DEEP HUNT SUMMARY")
print("=" * 60)
print("Run complete. Check above for anything marked FOUND or POTENTIAL.")
print("To cash out, you need at least ONE of:")
print("  1. Working exchange account (Kraken/Coinbase/Binance)")
print("  2. Browser wallet (MetaMask/Phantom) with funds")
print("  3. Desktop wallet (Exodus/Electrum) with funds")
print("  4. Private key or seed phrase for a funded wallet")
print("  5. Gift cards with remaining balance")
