"""
Rimuru Auto-Miner — Continuously mines blocks on your blockchain.
=================================================================

Runs a background mining loop that:
  1. Mines blocks at a configurable interval
  2. Records every mined block in the VaultLedger
  3. Tracks hashrate, blocks found, rewards earned
  4. Supports solo mining and pool-connected modes
  5. Auto-vaults all mining rewards for tamper-proof records

Usage:
    from mining.auto_miner import AutoMiner

    miner = AutoMiner(blockchain, wallet, vault_ledger)
    miner.start()          # begins mining in background thread
    miner.stop()           # graceful stop
    miner.get_stats()      # mining statistics

    # Or run directly:
    python -m mining.auto_miner
"""

import sys
import time
import json
import hashlib
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blockchain.chain import Blockchain
from blockchain.wallet import Wallet
from blockchain.vault import VaultLedger

logger = logging.getLogger("rimuru.auto_miner")


class MiningStats:
    """Tracks mining performance metrics."""

    def __init__(self):
        self.blocks_mined = 0
        self.total_reward = 0.0
        self.total_hashes = 0
        self.total_fees_collected = 0.0
        self.start_time = time.time()
        self.block_times = []
        self.last_block_time = 0.0
        self.vault_records_created = 0

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    @property
    def avg_block_time(self) -> float:
        return sum(self.block_times) / len(self.block_times) if self.block_times else 0.0

    @property
    def hashrate(self) -> float:
        return self.total_hashes / self.uptime if self.uptime > 0 else 0.0

    @property
    def blocks_per_hour(self) -> float:
        hours = self.uptime / 3600
        return self.blocks_mined / hours if hours > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "blocks_mined": self.blocks_mined,
            "total_reward": round(self.total_reward, 4),
            "total_fees_collected": round(self.total_fees_collected, 4),
            "uptime_seconds": round(self.uptime, 1),
            "avg_block_time": round(self.avg_block_time, 3),
            "hashrate": f"{self.hashrate:.0f} H/s",
            "blocks_per_hour": round(self.blocks_per_hour, 2),
            "vault_records": self.vault_records_created,
            "last_block_time": round(self.last_block_time, 3),
        }


class AutoMiner:
    """
    Continuous block miner with vault integration.

    Mines blocks on the Rimuru blockchain and records every
    reward in the VaultLedger for tamper-proof accounting.
    """

    def __init__(self, blockchain: Blockchain, wallet: Wallet,
                 vault: Optional[VaultLedger] = None,
                 mine_interval: float = 0.5,
                 auto_vault: bool = True):
        """
        Args:
            blockchain:    The chain to mine on
            wallet:        Miner's wallet (receives rewards)
            vault:         VaultLedger for recording mining results
            mine_interval: Seconds between mining attempts
            auto_vault:    Record every block in vault automatically
        """
        self.blockchain = blockchain
        self.wallet = wallet
        self.vault = vault
        self.mine_interval = mine_interval
        self.auto_vault = auto_vault

        self.stats = MiningStats()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def mine_one_block(self) -> Optional[dict]:
        """
        Mine a single block and optionally vault the result.

        Returns block info dict or None on failure.
        """
        start = time.time()

        try:
            block = self.blockchain.mine_block(self.wallet.address)
            elapsed = time.time() - start

            # Parse reward from coinbase tx
            coinbase = block.transactions[0]
            reward = coinbase["outputs"][0]["amount"]
            num_txs = len(block.transactions)
            fees = reward - self.blockchain.block_reward if num_txs > 1 else 0.0

            # Update stats
            with self._lock:
                self.stats.blocks_mined += 1
                self.stats.total_reward += reward
                self.stats.total_fees_collected += fees
                self.stats.block_times.append(elapsed)
                self.stats.last_block_time = elapsed

            block_info = {
                "block_index": block.index,
                "block_hash": block.hash,
                "reward": reward,
                "fees": fees,
                "transactions": num_txs,
                "nonce": block.nonce,
                "difficulty": block.difficulty,
                "mine_time": round(elapsed, 4),
                "miner": self.wallet.address,
                "chain_height": self.blockchain.height,
                "timestamp": time.time(),
            }

            # Auto-vault the mining result
            if self.auto_vault and self.vault:
                self.vault.record_custom("mining_reward", {
                    "block_index": block.index,
                    "block_hash": block.hash[:32],
                    "reward": reward,
                    "fees": fees,
                    "difficulty": block.difficulty,
                    "mine_time_seconds": round(elapsed, 4),
                    "chain_height": self.blockchain.height,
                })
                with self._lock:
                    self.stats.vault_records_created += 1

            logger.info(
                "Block #%d mined in %.3fs | reward=%.2f | txs=%d | height=%d",
                block.index, elapsed, reward, num_txs, self.blockchain.height,
            )

            return block_info

        except Exception as e:
            logger.error("Mining error: %s", e)
            return None

    def start(self, max_blocks: int = 0):
        """
        Start continuous mining in a background thread.

        Args:
            max_blocks: Stop after this many blocks (0 = unlimited)
        """
        if self._running:
            logger.warning("Miner already running")
            return

        self._running = True
        self.stats = MiningStats()

        def _mine_loop():
            blocks = 0
            logger.info("Auto-miner started | address=%s | interval=%.1fs",
                        self.wallet.address[:20] + "...", self.mine_interval)

            while self._running:
                self.mine_one_block()
                blocks += 1

                if max_blocks > 0 and blocks >= max_blocks:
                    logger.info("Reached target of %d blocks, stopping", max_blocks)
                    self._running = False
                    break

                time.sleep(self.mine_interval)

            logger.info("Auto-miner stopped | %d blocks mined | %.2f coins earned",
                        self.stats.blocks_mined, self.stats.total_reward)

        self._thread = threading.Thread(target=_mine_loop, daemon=True, name="rimuru-miner")
        self._thread.start()

    def stop(self):
        """Stop the mining loop gracefully."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)
        logger.info("Miner stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        """Get current mining statistics."""
        with self._lock:
            stats = self.stats.to_dict()
        stats["is_running"] = self.is_running
        stats["miner_address"] = self.wallet.address
        stats["current_balance"] = self.blockchain.get_balance(self.wallet.address)
        stats["chain_height"] = self.blockchain.height
        stats["difficulty"] = self.blockchain.difficulty
        stats["block_reward"] = self.blockchain.block_reward
        return stats

    def print_stats(self):
        """Pretty-print mining stats."""
        s = self.get_stats()
        print(f"\n{'═' * 60}")
        print(f"RIMURU AUTO-MINER STATS")
        print(f"{'═' * 60}")
        print(f"  Status:        {'MINING' if s['is_running'] else 'STOPPED'}")
        print(f"  Address:       {s['miner_address'][:24]}...")
        print(f"  Blocks Mined:  {s['blocks_mined']}")
        print(f"  Total Reward:  {s['total_reward']:.4f} coins")
        print(f"  Current Bal:   {s['current_balance']:.4f} coins")
        print(f"  Avg Block:     {s['avg_block_time']:.3f}s")
        print(f"  Hashrate:      {s['hashrate']}")
        print(f"  Chain Height:  {s['chain_height']}")
        print(f"  Difficulty:    {s['difficulty']}")
        print(f"  Block Reward:  {s['block_reward']:.2f}")
        print(f"  Vault Records: {s['vault_records']}")
        print(f"  Uptime:        {s['uptime_seconds']:.0f}s")
        print(f"{'═' * 60}")


# ──────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("RIMURU AUTO-MINER")
    print("=" * 60)

    bc = Blockchain()
    wallet = Wallet()
    vault = VaultLedger(bc, wallet)

    print(f"Miner address: {wallet.address}")
    print(f"Chain height:  {bc.height}")
    print()

    miner = AutoMiner(bc, wallet, vault, mine_interval=0.1)

    # Mine 10 blocks
    print("Mining 10 blocks...")
    for i in range(10):
        info = miner.mine_one_block()
        if info:
            print(f"  Block #{info['block_index']} | {info['mine_time']:.3f}s | reward={info['reward']:.2f}")

    # Mine the vault records into a block
    bc.mine_block(wallet.address)

    miner.print_stats()
    vault.print_summary()

    print(f"\nFinal balance: {bc.get_balance(wallet.address):.2f} coins")
    print(f"Chain valid: {bc.validate_chain()}")
