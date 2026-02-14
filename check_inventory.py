#!/usr/bin/env python3
"""Quick inventory check of all discovered assets"""
import sqlite3

db = sqlite3.connect('crypto_findings.db')
c = db.cursor()

# Get all wallets
c.execute('SELECT address, blockchain, balance_usd, source_file FROM wallets')
wallets = c.fetchall()
print(f'Total wallets in DB: {len(wallets)}')

# Count by blockchain
c.execute('SELECT blockchain, COUNT(*) FROM wallets GROUP BY blockchain')
for chain, count in c.fetchall():
    print(f'  {chain}: {count}')

# Any with balance?
c.execute('SELECT address, blockchain, balance_usd FROM wallets WHERE balance_usd > 0')
funded = c.fetchall()
print(f'\nWallets with balance > 0: {len(funded)}')
for w in funded:
    print(f'  [{w[1]}] {w[0]} = ${w[2]:.2f}')

# Show BTC addresses (haven't been checked yet)
c.execute("SELECT address, source_file FROM wallets WHERE blockchain = 'BTC' LIMIT 30")
btc = c.fetchall()
print(f'\nBTC addresses found ({len(btc)}):')
for addr, src in btc:
    fname = src.split('\\')[-1]
    print(f'  {addr}  from: {fname}')

# Show ETH addresses  
c.execute("SELECT address, source_file FROM wallets WHERE blockchain = 'ETH' LIMIT 10")
eth = c.fetchall()
c.execute("SELECT COUNT(*) FROM wallets WHERE blockchain = 'ETH'")
eth_total = c.fetchone()[0]
print(f'\nETH addresses ({eth_total} total, showing 10):')
for addr, src in eth:
    fname = src.split('\\')[-1]
    print(f'  {addr}  from: {fname}')

# API keys
c.execute('SELECT key_type, key_preview, exchange, source_file FROM api_keys')
keys = c.fetchall()
print(f'\nAPI Keys found: {len(keys)}')
for k in keys:
    fname = k[3].split('\\')[-1]
    print(f'  [{k[0]}] {k[1]} exchange={k[2]} from={fname}')

# Seed phrases
c.execute('SELECT COUNT(*) FROM seed_phrases')
seeds = c.fetchone()[0]
print(f'\nSeed phrases found: {seeds}')

db.close()
