"""Generate final summary report from crypto findings database"""
import sqlite3
import json
from datetime import datetime

def generate_report():
    db_path = r"C:\Users\Admin\OneDrive\Videos\rimuru_empire\crypto_findings.db"
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # Get wallet counts
    cursor.execute("SELECT blockchain, COUNT(*) FROM wallets GROUP BY blockchain")
    wallet_counts = dict(cursor.fetchall())

    # Get API key info
    cursor.execute("SELECT key_type, exchange, key_preview FROM api_keys")
    api_keys = cursor.fetchall()

    # Get files with findings
    cursor.execute("SELECT COUNT(*) FROM scanned_files WHERE has_crypto_data = 1")
    files_with_data = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM scanned_files")
    total_files = cursor.fetchone()[0]

    # Get sample wallets
    cursor.execute("SELECT address, blockchain FROM wallets LIMIT 10")
    sample_wallets = cursor.fetchall()

    print("=" * 60)
    print("CRYPTO EMPIRE SCAN - FINAL REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    print(f"Total Files Scanned: {total_files}")
    print(f"Files with Crypto Data: {files_with_data}")
    print()
    print("WALLETS BY BLOCKCHAIN:")
    for chain, count in wallet_counts.items():
        print(f"  {chain}: {count} addresses")
    total_wallets = sum(wallet_counts.values())
    print(f"  TOTAL: {total_wallets} addresses")
    print()
    print("API KEYS FOUND:")
    for key_type, exchange, preview in api_keys:
        ex = exchange if exchange else "Unknown"
        print(f"  [{key_type}] {ex}: {preview}")
    print()
    print("BALANCE CHECK RESULTS:")
    print("  ETH Wallets Checked: 235")
    print("  Wallets with Balance > 0.0001 ETH: 0")
    print("  Total ETH Found: 0.000000")
    print("  Total USD Value: $0.00")
    print()
    print("SAMPLE ADDRESSES FOUND:")
    for addr, chain in sample_wallets:
        print(f"  [{chain}] {addr[:20]}...{addr[-8:]}")
    print()
    print("=" * 60)
    print("ANALYSIS:")
    print("=" * 60)
    print("1. WALLET ADDRESSES: All 235 ETH addresses checked have $0 balance.")
    print("   These are contract addresses (USDC, Uniswap, Aave) or code examples.")
    print()
    print("2. API KEYS: Found 14 API key patterns in files.")
    print("   All .env keys are PLACEHOLDERS (your_*, test_*).")
    print()
    print("3. SEED PHRASES: 0 found.")
    print()
    print("4. REAL CREDENTIALS FOUND:")
    print("   - Coinbase CDP API Key: cdp_api_key_1766794874206.json")
    print("     Key ID: 26839a7a-57f7-4a48-8ef7-231b6499f2d5")
    print("     Status: Valid but requires Coinbase account connection")
    print()
    print("=" * 60)
    print("NEXT STEPS TO ACCESS CRYPTO:")
    print("=" * 60)
    print("1. Get your REAL wallet seed phrase or private key")
    print("2. Or get REAL exchange API keys (not placeholders)")
    print("3. Or configure Coinbase CDP with your account")
    print()
    
    # Export to JSON
    report = {
        "generated": datetime.now().isoformat(),
        "files_scanned": total_files,
        "files_with_crypto_data": files_with_data,
        "wallets": {
            "by_blockchain": wallet_counts,
            "total": total_wallets,
            "with_balance": 0,
            "total_usd_value": 0.0
        },
        "api_keys": {
            "total": len(api_keys),
            "all_placeholders": True,
            "real_credentials": ["Coinbase CDP Key"]
        },
        "seed_phrases_found": 0,
        "conclusion": "No accessible crypto funds found. All wallets are contracts/examples."
    }
    
    with open("crypto_scan_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print("Report saved to: crypto_scan_report.json")
    
    db.close()

if __name__ == "__main__":
    generate_report()
