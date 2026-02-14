"""
Block — The fundamental unit of a blockchain.
============================================

A block contains:
  - index:         Position in the chain (0 = genesis)
  - timestamp:     When the block was created (UTC)
  - transactions:  List of validated transactions
  - previous_hash: SHA-256 hash of the previous block (forms the chain)
  - nonce:         Number that miners adjust to find a valid hash
  - merkle_root:   Single hash representing all transactions
  - difficulty:    Number of leading zeros required in the hash
  - hash:          SHA-256 hash of this block's header

The hash is computed from:
  SHA256(index + timestamp + previous_hash + merkle_root + nonce + difficulty)

To be valid, the hash must start with `difficulty` number of zeros.
This is the foundation of Proof of Work.
"""

import hashlib
import json
import time
from typing import List, Optional


class Block:
    """
    A single block in the blockchain.

    The block header consists of metadata (index, timestamp, prev_hash, 
    merkle_root, nonce, difficulty). The body holds the raw transactions.

    Mining a block means finding a nonce such that the block's hash
    starts with `difficulty` zeros.
    """

    def __init__(
        self,
        index: int,
        transactions: List[dict],
        previous_hash: str,
        difficulty: int = 4,
        timestamp: Optional[float] = None,
        nonce: int = 0,
    ):
        self.index = index
        self.timestamp = timestamp or time.time()
        self.transactions = transactions
        self.previous_hash = previous_hash
        self.difficulty = difficulty
        self.nonce = nonce

        # Calculate Merkle root from transactions
        from blockchain.merkle import MerkleTree
        self.merkle_root = MerkleTree.build_root(
            [json.dumps(tx, sort_keys=True) for tx in transactions]
        ) if transactions else hashlib.sha256(b"empty").hexdigest()

        # Hash is computed after all fields are set
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """
        SHA-256 hash of the block header.
        
        The header includes everything EXCEPT the hash itself.
        Changing ANY field changes the hash completely (avalanche effect).
        """
        header = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
        }, sort_keys=True)

        return hashlib.sha256(header.encode()).hexdigest()

    def mine(self) -> int:
        """
        Proof of Work — find a nonce that produces a hash with 
        `difficulty` leading zeros.

        This is intentionally slow. The only way to find the nonce
        is brute force — try millions of values until one works.

        Returns:
            The number of attempts it took to find the valid nonce.
        """
        target = "0" * self.difficulty
        attempts = 0

        while True:
            attempts += 1
            self.hash = self.compute_hash()

            if self.hash.startswith(target):
                return attempts

            self.nonce += 1

    def is_valid_proof(self) -> bool:
        """Check if this block's hash satisfies the difficulty target."""
        return (
            self.hash == self.compute_hash()
            and self.hash.startswith("0" * self.difficulty)
        )

    def to_dict(self) -> dict:
        """Serialize block to dictionary."""
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "merkle_root": self.merkle_root,
            "nonce": self.nonce,
            "difficulty": self.difficulty,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        """Deserialize block from dictionary."""
        block = cls(
            index=data["index"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            difficulty=data["difficulty"],
            timestamp=data["timestamp"],
            nonce=data["nonce"],
        )
        block.hash = data["hash"]
        block.merkle_root = data["merkle_root"]
        return block

    def __repr__(self) -> str:
        return (
            f"Block(#{self.index}, txs={len(self.transactions)}, "
            f"nonce={self.nonce}, hash={self.hash[:16]}...)"
        )


# ──────────────────────────────────────────────
# DEMO: Run this file directly to see a block being mined
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BLOCK MINING DEMO")
    print("=" * 60)

    # Create a block with some sample transactions
    txs = [
        {"from": "Alice", "to": "Bob", "amount": 10},
        {"from": "Bob", "to": "Charlie", "amount": 5},
    ]

    block = Block(
        index=1,
        transactions=txs,
        previous_hash="0" * 64,  # Genesis previous hash
        difficulty=4,
    )

    print(f"\nMining block #{block.index} with difficulty {block.difficulty}...")
    print(f"Target: hash must start with {'0' * block.difficulty}")

    start = time.time()
    attempts = block.mine()
    elapsed = time.time() - start

    print(f"\n✓ Block mined!")
    print(f"  Nonce:    {block.nonce}")
    print(f"  Hash:     {block.hash}")
    print(f"  Attempts: {attempts:,}")
    print(f"  Time:     {elapsed:.2f}s")
    print(f"  Valid:    {block.is_valid_proof()}")
    print(f"\n  Merkle Root: {block.merkle_root}")
    print(f"  Transactions: {len(block.transactions)}")
