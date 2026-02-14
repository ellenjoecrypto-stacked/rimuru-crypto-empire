"""Check ETH balances for all wallets in database"""
import sqlite3
import requests
import time

def check_balances():
    # Connect to database
    db_path = r"C:\Users\Admin\OneDrive\Videos\rimuru_empire\crypto_findings.db"
    db = sqlite3.connect(db_path)
    cursor = db.cursor()

    # Get all ETH wallets
    cursor.execute("SELECT address FROM wallets WHERE blockchain = 'ETH'")
    eth_wallets = [r[0] for r in cursor.fetchall()]

    print(f"Checking {len(eth_wallets)} ETH wallets...")
    print("=" * 60)

    total_eth = 0
    total_usd = 0
    eth_price = 3450  # Approximate ETH price

    wallets_with_balance = []
    checked = 0

    for addr in eth_wallets:
        try:
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={addr}&tag=latest"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            
            if data.get("status") == "1":
                wei = int(data.get("result", 0))
                eth = wei / 1e18
                
                if eth > 0.0001:
                    usd = eth * eth_price
                    total_eth += eth
                    total_usd += usd
                    wallets_with_balance.append((addr, eth, usd))
                    print(f"FOUND: {addr}: {eth:.6f} ETH (~${usd:,.2f})")
                    
                    # Update database
                    cursor.execute(
                        "UPDATE wallets SET balance_eth=?, balance_usd=? WHERE address=?",
                        (eth, usd, addr)
                    )
            
            checked += 1
            if checked % 20 == 0:
                print(f"  Checked {checked}/{len(eth_wallets)}...")
                db.commit()
            
            time.sleep(0.25)  # Rate limit
            
        except Exception as e:
            print(f"Error checking {addr[:20]}...: {e}")

    db.commit()

    print("=" * 60)
    print(f"Total ETH wallets checked: {checked}")
    print(f"Wallets with balance > 0.0001 ETH: {len(wallets_with_balance)}")
    print(f"Total ETH found: {total_eth:.6f}")
    print(f"Total USD value: ${total_usd:,.2f}")
    print("=" * 60)
    
    if wallets_with_balance:
        print("\nWALLETS WITH FUNDS:")
        for addr, eth, usd in wallets_with_balance:
            print(f"  {addr}")
            print(f"    Balance: {eth:.6f} ETH (${usd:,.2f})")
    else:
        print("\nNo wallets found with significant balance.")
        print("Most addresses appear to be contract addresses or examples from code.")

    db.close()

if __name__ == "__main__":
    check_balances()
