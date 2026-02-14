"""
Merkle Tree — Efficient transaction verification.
===================================================

A Merkle tree is a binary tree of hashes. It lets you verify that a
specific transaction is included in a block WITHOUT downloading every
transaction in that block.

How it works:
              Merkle Root
              /          \\
          Hash(AB)      Hash(CD)
          /     \\      /     \\
       Hash(A) Hash(B) Hash(C) Hash(D)
         |       |       |       |
        Tx A   Tx B    Tx C    Tx D

To verify Tx B is in the block, you only need:
  1. Hash(A) — the sibling
  2. Hash(CD) — the uncle
  3. Merkle Root — from the block header

This is O(log n) instead of O(n). Bitcoin SPV (light) wallets use this
to verify transactions without downloading the entire blockchain.
"""

import hashlib
from typing import List, Optional


class MerkleTree:
    """
    Binary Merkle tree built from a list of data items.

    Each leaf is SHA-256(data). Parent nodes are SHA-256(left + right).
    If the number of items is odd, the last item is duplicated.
    """

    def __init__(self, data_list: List[str]):
        """
        Build a Merkle tree from a list of strings (usually serialized transactions).
        """
        self.leaves = [self._hash(d) for d in data_list]
        self.tree: List[List[str]] = []
        self.root = self._build_tree()

    @staticmethod
    def _hash(data: str) -> str:
        """SHA-256 hash of a string."""
        return hashlib.sha256(data.encode()).hexdigest()

    @staticmethod
    def _hash_pair(left: str, right: str) -> str:
        """Hash two child hashes together to form a parent."""
        combined = left + right
        return hashlib.sha256(combined.encode()).hexdigest()

    def _build_tree(self) -> str:
        """
        Build the tree bottom-up.

        Layer 0: leaf hashes
        Layer 1: pairs of leaves hashed together
        Layer 2: pairs of layer 1 hashed together
        ... until one root remains
        """
        if not self.leaves:
            return self._hash("empty")

        current_level = self.leaves[:]
        self.tree = [current_level[:]]

        while len(current_level) > 1:
            # If odd number, duplicate the last hash
            if len(current_level) % 2 == 1:
                current_level.append(current_level[-1])

            next_level = []
            for i in range(0, len(current_level), 2):
                parent = self._hash_pair(current_level[i], current_level[i + 1])
                next_level.append(parent)

            current_level = next_level
            self.tree.append(current_level[:])

        return current_level[0]

    def get_proof(self, index: int) -> List[dict]:
        """
        Generate a Merkle proof for the item at `index`.

        A proof is a list of sibling hashes + their position (left/right).
        The verifier can reconstruct the root from just this proof.

        This is how SPV wallets work — they ask a full node for the proof,
        then verify it locally without trusting the node.
        """
        if index < 0 or index >= len(self.leaves):
            raise IndexError(f"Index {index} out of range (0-{len(self.leaves) - 1})")

        proof = []
        idx = index

        for level in self.tree[:-1]:  # Skip root level
            # If odd number of items, duplicate last
            if len(level) % 2 == 1:
                level = level + [level[-1]]

            # Sibling is the paired node
            if idx % 2 == 0:
                sibling_idx = idx + 1
                position = "right"
            else:
                sibling_idx = idx - 1
                position = "left"

            if sibling_idx < len(level):
                proof.append({
                    "hash": level[sibling_idx],
                    "position": position,
                })

            # Move up to the parent index
            idx = idx // 2

        return proof

    @classmethod
    def verify_proof(cls, leaf_data: str, proof: List[dict], expected_root: str) -> bool:
        """
        Verify a Merkle proof.

        Given:
          - The original data (transaction)
          - The proof (sibling hashes)
          - The expected root (from the block header)

        Returns True if the proof is valid.
        """
        current = cls._hash(leaf_data)

        for step in proof:
            sibling = step["hash"]
            if step["position"] == "left":
                current = cls._hash_pair(sibling, current)
            else:
                current = cls._hash_pair(current, sibling)

        return current == expected_root

    @classmethod
    def build_root(cls, data_list: List[str]) -> str:
        """Convenience method — build tree and return just the root."""
        tree = cls(data_list)
        return tree.root

    def pretty_print(self):
        """Visualize the Merkle tree."""
        print(f"\n{'=' * 60}")
        print(f"Merkle Tree ({len(self.leaves)} leaves, {len(self.tree)} levels)")
        print(f"{'=' * 60}")

        for level_idx in range(len(self.tree) - 1, -1, -1):
            level = self.tree[level_idx]
            label = "ROOT" if level_idx == len(self.tree) - 1 else f"L{level_idx}"
            indent = "  " * (len(self.tree) - 1 - level_idx)
            print(f"\n  {label}:")
            for i, h in enumerate(level):
                print(f"  {indent}  [{i}] {h[:16]}...")


# ──────────────────────────────────────────────
# DEMO
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("MERKLE TREE DEMO")
    print("=" * 60)

    # Build tree from 4 transactions
    transactions = [
        '{"from": "Alice", "to": "Bob", "amount": 10}',
        '{"from": "Bob", "to": "Charlie", "amount": 5}',
        '{"from": "Charlie", "to": "Dave", "amount": 3}',
        '{"from": "Dave", "to": "Eve", "amount": 1}',
    ]

    tree = MerkleTree(transactions)
    tree.pretty_print()

    print(f"\nMerkle Root: {tree.root}")

    # Generate and verify proof for transaction #1 (Bob → Charlie)
    print(f"\n--- Verifying transaction #1 ---")
    proof = tree.get_proof(1)
    print(f"Proof ({len(proof)} steps):")
    for step in proof:
        print(f"  {step['position']}: {step['hash'][:16]}...")

    valid = MerkleTree.verify_proof(transactions[1], proof, tree.root)
    print(f"Valid: {valid}")

    # Try to verify a FAKE transaction
    print(f"\n--- Verifying FAKE transaction ---")
    valid = MerkleTree.verify_proof(
        '{"from": "Hacker", "to": "Hacker", "amount": 9999}',
        proof, tree.root
    )
    print(f"Valid: {valid}  (correctly rejected!)")
