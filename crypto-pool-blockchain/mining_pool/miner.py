"""
Miner Worker — The actual hash-crunching machine.
===================================================

This simulates what mining hardware (ASICs/GPUs) does:

1. Get work from the pool (block header + nonce range)
2. Hash the block header with different nonces — millions per second
3. Check if the hash meets the difficulty target
4. If it meets POOL difficulty → submit as a share
5. If it meets NETWORK difficulty → you found a block!
6. Repeat forever

Mining hardware evolution:
  - 2009: CPU mining (MH/s)
  - 2010: GPU mining (hundreds of MH/s)
  - 2013: ASIC mining (TH/s)
  - 2024: Modern ASICs (hundreds of TH/s)

One ASIC does ~200 trillion hashes per second.
This Python miner does maybe 100,000 per second.
"""

import os
import sys
import time
import json
import hashlib
import logging
import threading
from typing import Optional

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from blockchain.wallet import Wallet

logger = logging.getLogger("rimuru.miner")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class Miner:
    """
    A mining worker that connects to a pool and mines for shares.

    In a real setup:
      - The miner connects via Stratum protocol (TCP)
      - Receives work notifications in real-time
      - Submits shares as fast as they're found
      - Multiple workers can run on one machine (one per GPU/ASIC)

    This implementation uses HTTP polling against the pool server.
    """

    def __init__(self, pool_url: str = "http://localhost:8050",
                 worker_name: str = "worker1"):
        self.pool_url = pool_url
        self.wallet = Wallet()
        self.worker_name = worker_name

        # Stats
        self.hashes_computed = 0
        self.shares_found = 0
        self.blocks_found = 0
        self.start_time = time.time()
        self.running = False

    def register(self) -> bool:
        """Register with the mining pool."""
        import urllib.request

        data = json.dumps({
            "address": self.wallet.address,
            "worker_name": self.worker_name,
        }).encode()

        req = urllib.request.Request(
            f"{self.pool_url}/register",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            result = json.loads(resp.read().decode())
            logger.info("Registered with pool: %s", result["status"])
            return True
        except Exception as e:
            logger.error("Failed to register: %s", e)
            return False

    def get_work(self) -> Optional[dict]:
        """Request a work unit from the pool."""
        import urllib.request

        url = (f"{self.pool_url}/work"
               f"?miner_address={self.wallet.address}"
               f"&worker_name={self.worker_name}")

        try:
            resp = urllib.request.urlopen(url, timeout=10)
            return json.loads(resp.read().decode())
        except Exception as e:
            logger.error("Failed to get work: %s", e)
            return None

    def submit_share(self, block_index: int, nonce: int, hash_val: str) -> dict:
        """Submit a share to the pool."""
        import urllib.request

        data = json.dumps({
            "miner_address": self.wallet.address,
            "worker_name": self.worker_name,
            "block_index": block_index,
            "nonce": nonce,
            "hash": hash_val,
        }).encode()

        req = urllib.request.Request(
            f"{self.pool_url}/submit",
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )

        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read().decode())
        except Exception as e:
            logger.error("Failed to submit share: %s", e)
            return {"status": "error", "reason": str(e)}

    def mine_work_unit(self, work: dict) -> list:
        """
        Mine a work unit — the core hashing loop.

        This is what GPUs/ASICs do at incredible speed:
          1. Take the block header
          2. Try nonce = 0, 1, 2, 3, ...
          3. Hash each attempt
          4. Check if hash < target
          5. Found one? That's a share. Submit it.

        Returns list of (nonce, hash) pairs that met pool difficulty.
        """
        work_data = work["work"]
        nonce_start = work["nonce_start"]
        nonce_end = work["nonce_end"]
        pool_target = work["target_prefix"]

        # Block header template
        header_template = json.dumps({
            "index": work_data["block_index"],
            "previous_hash": work_data["previous_hash"],
            "merkle_root": hashlib.sha256(
                json.dumps(work_data["transactions"], sort_keys=True).encode()
            ).hexdigest(),
            "difficulty": work_data["network_difficulty"],
        }, sort_keys=True)

        shares = []

        for nonce in range(nonce_start, nonce_end):
            self.hashes_computed += 1

            # Hash the header with this nonce
            attempt = f"{header_template}:{nonce}"
            hash_val = hashlib.sha256(attempt.encode()).hexdigest()

            # Check if it meets pool difficulty
            if hash_val.startswith(pool_target):
                shares.append((nonce, hash_val))
                self.shares_found += 1

                # Check if it also meets network difficulty
                network_target = "0" * work_data["network_difficulty"]
                if hash_val.startswith(network_target):
                    self.blocks_found += 1
                    logger.info("BLOCK FOUND! nonce=%d hash=%s", nonce, hash_val[:24])

        return shares

    def mine_loop(self, rounds: int = 10):
        """
        Main mining loop.

        1. Get work from pool
        2. Mine the nonce range
        3. Submit any shares found
        4. Request new work
        5. Repeat
        """
        self.running = True
        self.start_time = time.time()

        logger.info("Starting mining loop (%d rounds)", rounds)
        logger.info("Miner address: %s", self.wallet.address[:24])

        for round_num in range(rounds):
            if not self.running:
                break

            # Get work
            work = self.get_work()
            if not work:
                time.sleep(1)
                continue

            pool_diff = work["work"]["pool_difficulty"]
            net_diff = work["work"]["network_difficulty"]

            # Mine it
            round_start = time.time()
            shares = self.mine_work_unit(work)
            round_time = time.time() - round_start

            # Submit shares
            for nonce, hash_val in shares:
                result = self.submit_share(
                    work["work"]["block_index"], nonce, hash_val
                )

                if result.get("status") == "block_found":
                    logger.info(
                        "BLOCK FOUND! Block #%d, Reward: %s",
                        result.get("block_index"), result.get("reward"),
                    )
                elif result.get("status") == "accepted":
                    pass  # Normal share

            # Stats
            elapsed = time.time() - self.start_time
            hashrate = self.hashes_computed / elapsed if elapsed > 0 else 0

            logger.info(
                "Round %d/%d: %d shares, %.1f H/s, %d total hashes",
                round_num + 1, rounds, len(shares), hashrate, self.hashes_computed,
            )

        self.running = False

    def get_stats(self) -> dict:
        """Get miner statistics."""
        elapsed = time.time() - self.start_time
        hashrate = self.hashes_computed / elapsed if elapsed > 0 else 0

        return {
            "address": self.wallet.address,
            "worker": self.worker_name,
            "hashes_computed": self.hashes_computed,
            "shares_found": self.shares_found,
            "blocks_found": self.blocks_found,
            "hashrate": f"{hashrate:.1f} H/s",
            "uptime_seconds": round(elapsed, 1),
            "running": self.running,
        }

    def stop(self):
        """Stop the miner."""
        self.running = False


# ──────────────────────────────────────────────
# STANDALONE MINER DEMO (without pool)
# ──────────────────────────────────────────────

def solo_mine_demo():
    """
    Demonstrate mining without a pool.
    
    Solo mining means you try to find a block entirely on your own.
    If you find one, you get the FULL reward.
    But with network hashrate in the exahashes, you might wait years.
    """
    print("=" * 60)
    print("SOLO MINING DEMO (no pool)")
    print("=" * 60)

    from blockchain.chain import Blockchain

    bc = Blockchain()
    miner = Wallet()

    print(f"Miner address: {miner.address}")
    print(f"Difficulty: {bc.difficulty}")
    print(f"Reward: {bc.block_reward}")

    for i in range(5):
        start = time.time()
        block = bc.mine_block(miner.address)
        elapsed = time.time() - start

        print(f"\n  Block #{block.index} mined in {elapsed:.2f}s")
        print(f"  Hash:  {block.hash[:32]}...")
        print(f"  Nonce: {block.nonce}")

    balance = bc.get_balance(miner.address)
    print(f"\nFinal balance: {balance:.2f} coins")
    print(f"Chain valid: {bc.validate_chain()}")


if __name__ == "__main__":
    import sys
    if "--solo" in sys.argv:
        solo_mine_demo()
    else:
        # Pool mining mode
        pool_url = os.getenv("POOL_URL", "http://localhost:8050")
        worker = os.getenv("WORKER_NAME", "worker1")
        rounds = int(os.getenv("MINE_ROUNDS", "10"))

        miner = Miner(pool_url=pool_url, worker_name=worker)

        if miner.register():
            miner.mine_loop(rounds=rounds)
            print(json.dumps(miner.get_stats(), indent=2))
        else:
            print("Failed to register with pool. Is the pool server running?")
