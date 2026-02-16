"""
Rimuru Empire Runner — Mining + Tracking + Vault in one command.
================================================================

Starts the auto-miner and tracker together:
  1. Creates blockchain, wallet, vault
  2. Mines blocks continuously (earns coins)
  3. Scans for whale movements, airdrops, faucets
  4. Records ALL findings on-chain via VaultLedger
  5. Prints live stats

Usage:
    python run_empire.py                  # Mine 20 blocks + 1 scan
    python run_empire.py --blocks 50      # Mine 50 blocks
    python run_empire.py --continuous     # Run forever
"""

import sys
import time
import json
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from blockchain.chain import Blockchain
from blockchain.wallet import Wallet, HDWallet
from blockchain.vault import VaultLedger
from mining.auto_miner import AutoMiner
from trackers.whale_tracker import RimuruTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("rimuru.empire")


def run_empire(blocks: int = 20, scan_rounds: int = 1, continuous: bool = False):
    """
    Run the full Rimuru Empire stack.

    Args:
        blocks:      Number of blocks to mine
        scan_rounds: Number of tracker scan rounds
        continuous:  Run indefinitely if True
    """
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║           RIMURU CRYPTO EMPIRE — FULL STACK                ║")
    print("║       Mining • Whale Tracking • Airdrops • Faucets         ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # ── Setup ──
    bc = Blockchain()
    hd = HDWallet()
    miner_wallet = hd.derive_wallet(index=0)
    vault_wallet = hd.derive_wallet(index=1)
    vault = VaultLedger(bc, vault_wallet)

    print(f"  HD Seed:      {hd.seed_phrase[:30]}...")
    print(f"  Miner Wallet: {miner_wallet.address}")
    print(f"  Vault Wallet: {vault_wallet.address}")
    print(f"  Chain Height: {bc.height}")
    print()

    # ── Record wallet on vault ──
    vault.record_wallet(miner_wallet.address, "rimuru-chain", notes="Mining wallet")
    vault.record_wallet(vault_wallet.address, "rimuru-chain", notes="Vault wallet")

    # ── Phase 1: Mining ──
    print("═" * 60)
    print("PHASE 1: MINING")
    print("═" * 60)

    miner = AutoMiner(bc, miner_wallet, vault, mine_interval=0.05)

    target = blocks if not continuous else 999999999
    mined = 0
    batch_size = min(10, target)

    while mined < target:
        to_mine = min(batch_size, target - mined)
        for _ in range(to_mine):
            info = miner.mine_one_block()
            mined += 1
            if info and mined % 5 == 0:
                print(f"  Block #{info['block_index']:>4d} | "
                      f"{info['mine_time']:.3f}s | "
                      f"reward={info['reward']:.2f} | "
                      f"height={info['chain_height']}")

        # Mine vault records into a block
        if miner.stats.vault_records_created > 0:
            bc.mine_block(miner_wallet.address)
            mined += 1

        if not continuous:
            break

    miner.print_stats()
    print()

    # ── Phase 2: Whale Tracking & Opportunity Scanning ──
    print("═" * 60)
    print("PHASE 2: WHALE TRACKING & OPPORTUNITY HUNTING")
    print("═" * 60)

    tracker = RimuruTracker(bc, vault_wallet, vault)

    for i in range(scan_rounds):
        print(f"\n  Scan round {i + 1}/{scan_rounds}...")
        report = tracker.run_full_scan()

        # Mine to seal tracker findings
        bc.mine_block(miner_wallet.address)

        print(f"  Whales:   {report['whale_alerts']['count']} "
              f"({report['whale_alerts']['bullish']} bullish, "
              f"{report['whale_alerts']['bearish']} bearish)")
        print(f"  Airdrops: {report['airdrops']['count']} tracked, "
              f"${report['airdrops']['total_estimated_usd']:,.0f} est. value")
        print(f"  Faucets:  {report['faucets']['count']} found, "
              f"~${report['faucets']['daily_estimate_usd']:.2f}/day")
        print(f"  Vaulted:  {report['vault']['records_created']} records sealed on-chain")

    tracker.print_report()
    print()

    # ── Final Summary ──
    print("═" * 60)
    print("FINAL EMPIRE STATE")
    print("═" * 60)
    print(f"  Chain Height:     {bc.height}")
    print(f"  Chain Valid:      {bc.validate_chain()}")
    print(f"  Miner Balance:    {bc.get_balance(miner_wallet.address):.2f} coins")
    print(f"  Vault Balance:    {bc.get_balance(vault_wallet.address):.2f} coins")
    print(f"  Blocks Mined:     {miner.stats.blocks_mined}")
    print(f"  Total Reward:     {miner.stats.total_reward:.2f} coins")
    print(f"  UTXOs:            {len(bc.utxo_set)}")
    print(f"  Vault Records:    {vault.total_records}")
    print(f"  Mempool Pending:  {len(bc.mempool)}")

    vault.print_summary()

    print()
    print("Empire is running. All findings are sealed on your blockchain.")
    print()

    return bc, miner, tracker, vault


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rimuru Crypto Empire Runner")
    parser.add_argument("--blocks", type=int, default=20, help="Blocks to mine")
    parser.add_argument("--scans", type=int, default=1, help="Tracker scan rounds")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    args = parser.parse_args()

    run_empire(blocks=args.blocks, scan_rounds=args.scans, continuous=args.continuous)
