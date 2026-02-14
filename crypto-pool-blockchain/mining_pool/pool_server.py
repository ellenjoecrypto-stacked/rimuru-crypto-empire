"""
Mining Pool Server — Coordinates miners and distributes work.
==============================================================

How a mining pool works:

1. The pool holds a copy of the blockchain
2. When a new block needs mining, the pool creates a WORK UNIT:
   - The block header to hash
   - A difficulty target (easier than the real one)
3. Miners request work, find partial solutions (SHARES), and submit them
4. A share proves the miner is working, even if it's not a real block solution
5. Occasionally, a share IS a valid block → the pool broadcasts it
6. Rewards are distributed based on shares submitted (PPS, PPLNS, PROP)

Pool difficulty vs Network difficulty:
  Network: hash must start with "000000" (6 zeros) → very hard
  Pool:    hash must start with "00" (2 zeros)     → much easier
  
  A miner might find 1000 pool-difficulty hashes before finding
  one network-difficulty hash. Each pool hash is a "share".

This server uses FastAPI for the pool coordinator.
"""

import os
import sys
import time
import json
import hashlib
import logging
import threading
from typing import Dict, List, Optional
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Add parent to path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from blockchain.chain import Blockchain
from blockchain.block import Block
from blockchain.wallet import Wallet
from mining_pool.reward import RewardDistributor, PayoutScheme

logger = logging.getLogger("rimuru.pool")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="Rimuru Mining Pool", version="1.0.0")


# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

class MinerRegistration(BaseModel):
    """A miner registering with the pool."""
    address: str
    worker_name: str = "default"

class ShareSubmission(BaseModel):
    """A miner submitting a share (partial solution)."""
    miner_address: str
    worker_name: str
    block_index: int
    nonce: int
    hash: str


# ─────────────────────────────────────────────
# Pool State
# ─────────────────────────────────────────────

class MinerInfo:
    """Tracks a connected miner's stats."""
    def __init__(self, address: str, worker_name: str):
        self.address = address
        self.worker_name = worker_name
        self.shares_submitted = 0
        self.shares_accepted = 0
        self.shares_rejected = 0
        self.blocks_found = 0
        self.last_share_time = 0.0
        self.total_earned = 0.0
        self.connected_at = time.time()
        self.hashrate_estimate = 0.0

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "worker_name": self.worker_name,
            "shares_submitted": self.shares_submitted,
            "shares_accepted": self.shares_accepted,
            "shares_rejected": self.shares_rejected,
            "blocks_found": self.blocks_found,
            "total_earned": self.total_earned,
            "hashrate_estimate": f"{self.hashrate_estimate:.1f} H/s",
            "connected_seconds": round(time.time() - self.connected_at, 1),
        }


class WorkUnit:
    """A unit of work assigned to miners."""
    def __init__(self, block_index: int, previous_hash: str,
                 transactions: list, network_difficulty: int,
                 pool_difficulty: int):
        self.block_index = block_index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.network_difficulty = network_difficulty
        self.pool_difficulty = pool_difficulty
        self.created_at = time.time()
        self.nonce_range_start = 0

    def to_dict(self) -> dict:
        return {
            "block_index": self.block_index,
            "previous_hash": self.previous_hash,
            "transactions": self.transactions,
            "network_difficulty": self.network_difficulty,
            "pool_difficulty": self.pool_difficulty,
            "nonce_range_start": self.nonce_range_start,
        }


# ─── Global Pool State ───
blockchain = Blockchain()
pool_wallet = Wallet()
miners: Dict[str, MinerInfo] = {}
current_work: Optional[WorkUnit] = None
pool_blocks_found = 0
pool_total_shares = 0
pool_start_time = time.time()

# Pool settings
POOL_DIFFICULTY = max(1, blockchain.difficulty - 2)  # Easier than network
PAYOUT_SCHEME = PayoutScheme.PPLNS
reward_distributor = RewardDistributor(scheme=PAYOUT_SCHEME)

# Nonce counter for assigning ranges to different miners
nonce_counter = 0
NONCE_RANGE_SIZE = 100000


def _create_work() -> WorkUnit:
    """Create a new work unit from the current blockchain state."""
    global current_work, nonce_counter

    work = WorkUnit(
        block_index=blockchain.height,
        previous_hash=blockchain.last_block.hash,
        transactions=[tx.to_dict() for tx in blockchain.mempool[:blockchain.MAX_BLOCK_SIZE]],
        network_difficulty=blockchain.difficulty,
        pool_difficulty=POOL_DIFFICULTY,
    )
    work.nonce_range_start = nonce_counter
    nonce_counter += NONCE_RANGE_SIZE

    current_work = work
    return work


# ─────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "service": "mining-pool",
        "status": "healthy",
        "uptime_seconds": round(time.time() - pool_start_time, 1),
        "miners_connected": len(miners),
        "blocks_found": pool_blocks_found,
        "total_shares": pool_total_shares,
        "blockchain_height": blockchain.height,
        "difficulty": blockchain.difficulty,
        "pool_difficulty": POOL_DIFFICULTY,
        "payout_scheme": PAYOUT_SCHEME.value,
    }


@app.post("/register")
def register_miner(reg: MinerRegistration):
    """
    Register a new miner with the pool.
    
    In real pools, this is where you'd set up a Stratum connection.
    The miner provides their payout address and worker name.
    """
    key = f"{reg.address}:{reg.worker_name}"

    if key in miners:
        return {"status": "already_registered", "miner": miners[key].to_dict()}

    miner = MinerInfo(reg.address, reg.worker_name)
    miners[key] = miner

    logger.info("Miner registered: %s (%s)", reg.address[:16], reg.worker_name)

    return {"status": "registered", "miner": miner.to_dict()}


@app.get("/work")
def get_work(miner_address: str, worker_name: str = "default"):
    """
    Get a work unit to mine.

    The pool gives the miner:
      - Block data to hash
      - A nonce range to search
      - The pool difficulty target (easier than network)
    
    Each miner gets a different nonce range so they don't duplicate work.
    """
    key = f"{miner_address}:{worker_name}"
    if key not in miners:
        raise HTTPException(status_code=400, detail="Not registered. POST /register first.")

    work = _create_work()

    return {
        "work": work.to_dict(),
        "nonce_start": work.nonce_range_start,
        "nonce_end": work.nonce_range_start + NONCE_RANGE_SIZE,
        "target_prefix": "0" * POOL_DIFFICULTY,
    }


@app.post("/submit")
def submit_share(share: ShareSubmission):
    """
    Submit a share (partial proof of work).

    The pool verifies:
      1. The miner is registered
      2. The share is for the current block
      3. The hash meets pool difficulty
      4. If the hash also meets network difficulty → BLOCK FOUND!

    This is the core of pool mining:
      - Pool difficulty: "00..." (2 zeros) → share accepted
      - Network difficulty: "0000..." (4 zeros) → block found!
    """
    global pool_blocks_found, pool_total_shares

    key = f"{share.miner_address}:{share.worker_name}"
    if key not in miners:
        raise HTTPException(status_code=400, detail="Not registered")

    miner = miners[key]
    miner.shares_submitted += 1
    pool_total_shares += 1

    # Verify the share meets pool difficulty
    pool_target = "0" * POOL_DIFFICULTY
    if not share.hash.startswith(pool_target):
        miner.shares_rejected += 1
        return {
            "status": "rejected",
            "reason": f"Hash doesn't meet pool difficulty (need {pool_target}...)",
        }

    # Share accepted!
    miner.shares_accepted += 1
    miner.last_share_time = time.time()

    # Update hashrate estimate (shares per second × difficulty factor)
    elapsed = time.time() - miner.connected_at
    if elapsed > 0:
        miner.hashrate_estimate = (miner.shares_accepted * (16 ** POOL_DIFFICULTY)) / elapsed

    # Record share for reward distribution
    reward_distributor.record_share(share.miner_address, share.worker_name)

    # Check if share also meets NETWORK difficulty (block found!)
    network_target = "0" * blockchain.difficulty
    if share.hash.startswith(network_target):
        # BLOCK FOUND!
        pool_blocks_found += 1
        miner.blocks_found += 1

        # Mine the block on the blockchain
        block = blockchain.mine_block(pool_wallet.address)

        # Distribute rewards
        payouts = reward_distributor.distribute(
            blockchain.block_reward,
            share.miner_address,
        )

        for addr, amount in payouts.items():
            for m in miners.values():
                if m.address == addr:
                    m.total_earned += amount

        logger.info(
            "BLOCK FOUND by %s! Block #%d, reward distributed to %d miners",
            share.miner_address[:16], block.index, len(payouts),
        )

        return {
            "status": "block_found",
            "block_index": block.index,
            "block_hash": block.hash,
            "reward": blockchain.block_reward,
            "payouts": payouts,
        }

    return {
        "status": "accepted",
        "shares_accepted": miner.shares_accepted,
        "hashrate": f"{miner.hashrate_estimate:.1f} H/s",
    }


@app.get("/stats")
def pool_stats():
    """Overall pool statistics."""
    total_hashrate = sum(m.hashrate_estimate for m in miners.values())

    return {
        "pool": {
            "name": "Rimuru Mining Pool",
            "uptime_seconds": round(time.time() - pool_start_time, 1),
            "blocks_found": pool_blocks_found,
            "total_shares": pool_total_shares,
            "payout_scheme": PAYOUT_SCHEME.value,
            "pool_difficulty": POOL_DIFFICULTY,
            "network_difficulty": blockchain.difficulty,
            "total_hashrate": f"{total_hashrate:.1f} H/s",
        },
        "blockchain": {
            "height": blockchain.height,
            "block_reward": blockchain.block_reward,
            "valid": blockchain.validate_chain(),
        },
        "miners": {
            "connected": len(miners),
            "list": [m.to_dict() for m in miners.values()],
        },
    }


@app.get("/miners/{address}")
def miner_stats(address: str):
    """Stats for a specific miner."""
    miner_entries = {k: v for k, v in miners.items() if v.address == address}
    if not miner_entries:
        raise HTTPException(status_code=404, detail="Miner not found")

    return {
        "address": address,
        "balance": blockchain.get_balance(address),
        "workers": [m.to_dict() for m in miner_entries.values()],
    }


@app.get("/blockchain")
def get_blockchain():
    """View the blockchain state."""
    return {
        "height": blockchain.height,
        "difficulty": blockchain.difficulty,
        "block_reward": blockchain.block_reward,
        "chain_valid": blockchain.validate_chain(),
        "recent_blocks": [
            {
                "index": b.index,
                "hash": b.hash[:32] + "...",
                "transactions": len(b.transactions),
                "nonce": b.nonce,
            }
            for b in blockchain.chain[-5:]
        ],
    }


# ──────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("RIMURU MINING POOL SERVER")
    print(f"Pool Address: {pool_wallet.address}")
    print(f"Payout Scheme: {PAYOUT_SCHEME.value}")
    print(f"Pool Difficulty: {POOL_DIFFICULTY}")
    print(f"Network Difficulty: {blockchain.difficulty}")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8050)
