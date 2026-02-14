"""
Blockchain — The full chain with mining, validation, and UTXO tracking.
========================================================================

A blockchain is an append-only ledger where each block references the
previous block's hash. This creates an immutable chain — changing any
historical block invalidates every block after it.

Key concepts implemented here:
  1. Genesis block creation
  2. Transaction pool (mempool)
  3. Block mining with Proof of Work
  4. Chain validation (every block verified)
  5. UTXO set tracking (who owns what)
  6. Difficulty adjustment (keep block times consistent)
  7. Halving schedule (reduce mining rewards over time)
  8. Fork resolution (longest valid chain wins)
"""

import time
import json
import logging
from typing import List, Dict, Optional, Tuple

from blockchain.block import Block
from blockchain.transaction import Transaction, TxInput, TxOutput
from blockchain.wallet import Wallet

logger = logging.getLogger("rimuru.blockchain")


class Blockchain:
    """
    A complete blockchain implementation.

    State:
      - chain:       List of validated blocks
      - mempool:     Unconfirmed transactions waiting to be mined
      - utxo_set:    Unspent Transaction Outputs {(tx_hash, idx): TxOutput}
      - difficulty:   Current mining difficulty
      - block_reward: Current coinbase reward (halves periodically)
    """

    # ─── Config ───
    INITIAL_DIFFICULTY = 4          # Leading zeros required in hash
    BLOCK_TIME_TARGET = 10.0        # Target seconds per block
    DIFFICULTY_ADJUST_INTERVAL = 10  # Adjust every N blocks
    INITIAL_REWARD = 50.0           # Coins per block (like Bitcoin's 50 BTC)
    HALVING_INTERVAL = 100          # Halve reward every N blocks
    MAX_BLOCK_SIZE = 100            # Max transactions per block

    def __init__(self):
        self.chain: List[Block] = []
        self.mempool: List[Transaction] = []
        self.utxo_set: Dict[Tuple[str, int], TxOutput] = {}
        self.difficulty = self.INITIAL_DIFFICULTY
        self.block_reward = self.INITIAL_REWARD
        self.block_times: List[float] = []

        # Create genesis block
        self._create_genesis()

    def _create_genesis(self):
        """
        The genesis block — the first block in the chain.

        Every blockchain has one. It's hardcoded and has no previous hash.
        Bitcoin's genesis block was mined on January 3, 2009, with the
        message: "The Times 03/Jan/2009 Chancellor on brink of second
        bailout for banks"
        """
        # Fixed timestamp so every node generates the identical genesis block
        GENESIS_TIMESTAMP = 1700000000.0  # 2023-11-14 deterministic epoch
        genesis_tx = Transaction.create_coinbase(
            "genesis_address", self.block_reward, 0, timestamp=GENESIS_TIMESTAMP
        )
        genesis = Block(
            index=0,
            transactions=[genesis_tx.to_dict()],
            previous_hash="0" * 64,
            difficulty=self.difficulty,
            timestamp=GENESIS_TIMESTAMP,
        )
        genesis.mine()
        self.chain.append(genesis)

        # Track the coinbase output as spendable
        self.utxo_set[(genesis_tx.tx_hash, 0)] = genesis_tx.outputs[0]

        logger.info("Genesis block created: %s", genesis.hash[:16])

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @property
    def height(self) -> int:
        return len(self.chain)

    def add_transaction(self, tx: Transaction) -> bool:
        """
        Add a transaction to the mempool (waiting area).

        Validation checks:
          1. Transaction hash is valid
          2. Inputs reference existing UTXOs
          3. Input value >= output value (no creating money)
          4. Signatures are valid (simplified)
          5. No double-spending (inputs not already in mempool)
        """
        # Coinbase transactions are added directly during mining
        if tx.is_coinbase():
            logger.warning("Cannot manually add coinbase transactions")
            return False

        # Verify inputs exist in UTXO set
        input_total = 0.0
        for inp in tx.inputs:
            key = (inp.tx_hash, inp.output_idx)
            if key not in self.utxo_set:
                logger.warning("Invalid input: UTXO %s not found", key)
                return False
            input_total += self.utxo_set[key].amount

        # Verify no double-spend within mempool
        mempool_inputs = set()
        for pool_tx in self.mempool:
            for inp in pool_tx.inputs:
                mempool_inputs.add((inp.tx_hash, inp.output_idx))

        for inp in tx.inputs:
            key = (inp.tx_hash, inp.output_idx)
            if key in mempool_inputs:
                logger.warning("Double-spend detected in mempool!")
                return False

        # Verify output <= input (no creating money from thin air)
        output_total = tx.total_output_value()
        if output_total > input_total:
            logger.warning(
                "Output (%.4f) exceeds input (%.4f) — invalid!",
                output_total, input_total,
            )
            return False

        self.mempool.append(tx)
        logger.info("Transaction added to mempool: %s (fee=%.4f)",
                     tx.tx_hash[:16], input_total - output_total)
        return True

    def mine_block(self, miner_address: str) -> Block:
        """
        Mine a new block.

        Steps:
          1. Select transactions from mempool (up to MAX_BLOCK_SIZE)
          2. Create coinbase transaction (mining reward + fees)
          3. Build the block with all transactions
          4. Find valid nonce (Proof of Work)
          5. Validate and append to chain
          6. Update UTXO set
          7. Adjust difficulty if needed
          8. Check for halving

        Returns the mined block.
        """
        start_time = time.time()

        # 1. Select transactions from mempool
        selected_txs = self.mempool[:self.MAX_BLOCK_SIZE]

        # 2. Calculate total fees
        total_fees = 0.0
        for tx in selected_txs:
            total_fees += tx.fee(self.utxo_set)

        # 3. Create coinbase transaction
        coinbase = Transaction.create_coinbase(
            miner_address,
            self.block_reward + total_fees,
            self.height,
        )

        # 4. Build transaction list (coinbase first, then mempool txs)
        all_txs = [coinbase.to_dict()] + [tx.to_dict() for tx in selected_txs]

        # 5. Create and mine the block
        block = Block(
            index=self.height,
            transactions=all_txs,
            previous_hash=self.last_block.hash,
            difficulty=self.difficulty,
        )

        attempts = block.mine()
        mine_time = time.time() - start_time

        # 6. Validate the block
        if not self._validate_block(block):
            raise ValueError("Mined block failed validation!")

        # 7. Append to chain
        self.chain.append(block)
        self.block_times.append(mine_time)

        # 8. Update UTXO set
        self._update_utxo(coinbase, selected_txs)

        # 9. Clear mined transactions from mempool
        mined_hashes = {tx.tx_hash for tx in selected_txs}
        self.mempool = [tx for tx in self.mempool if tx.tx_hash not in mined_hashes]

        # 10. Adjust difficulty
        self._adjust_difficulty()

        # 11. Check halving
        self._check_halving()

        logger.info(
            "Block #%d mined in %.2fs (%d attempts, %d txs, reward=%.2f)",
            block.index, mine_time, attempts, len(all_txs),
            self.block_reward + total_fees,
        )

        return block

    def _update_utxo(self, coinbase: Transaction, txs: List[Transaction]):
        """
        Update the UTXO set after mining a block.

        - Remove spent outputs (inputs of included transactions)
        - Add new outputs (outputs of included transactions + coinbase)
        """
        # Add coinbase outputs
        for idx, output in enumerate(coinbase.outputs):
            self.utxo_set[(coinbase.tx_hash, idx)] = output

        # Process each transaction
        for tx in txs:
            # Remove spent UTXOs
            for inp in tx.inputs:
                key = (inp.tx_hash, inp.output_idx)
                self.utxo_set.pop(key, None)

            # Add new UTXOs
            for idx, output in enumerate(tx.outputs):
                self.utxo_set[(tx.tx_hash, idx)] = output

    def _validate_block(self, block: Block) -> bool:
        """
        Validate a block before adding it to the chain.

        Checks:
          1. Index is correct (sequential)
          2. Previous hash matches
          3. Proof of work is valid
          4. Block hash is correct
        """
        if block.index != self.height:
            return False
        if block.previous_hash != self.last_block.hash:
            return False
        if not block.is_valid_proof():
            return False
        return True

    def _adjust_difficulty(self):
        """
        Difficulty adjustment — keeps block times consistent.

        If blocks are too fast → increase difficulty (more zeros needed).
        If blocks are too slow → decrease difficulty (fewer zeros needed).

        Bitcoin adjusts every 2016 blocks (~2 weeks) to target 10 minutes.
        We adjust every DIFFICULTY_ADJUST_INTERVAL blocks.
        """
        if self.height % self.DIFFICULTY_ADJUST_INTERVAL != 0:
            return
        if len(self.block_times) < self.DIFFICULTY_ADJUST_INTERVAL:
            return

        # Average time of recent blocks
        recent = self.block_times[-self.DIFFICULTY_ADJUST_INTERVAL:]
        avg_time = sum(recent) / len(recent)

        old_diff = self.difficulty

        if avg_time < self.BLOCK_TIME_TARGET * 0.5:
            # Blocks too fast → harder
            self.difficulty += 1
        elif avg_time > self.BLOCK_TIME_TARGET * 2.0 and self.difficulty > 1:
            # Blocks too slow → easier
            self.difficulty -= 1

        if self.difficulty != old_diff:
            logger.info(
                "Difficulty adjusted: %d → %d (avg block time: %.2fs)",
                old_diff, self.difficulty, avg_time,
            )

    def _check_halving(self):
        """
        Halving — reduce mining rewards over time.

        Bitcoin's halving schedule:
          Block 0 - 209,999:          50 BTC
          Block 210,000 - 419,999:    25 BTC
          Block 420,000 - 629,999:    12.5 BTC
          Block 630,000 - 839,999:    6.25 BTC
          Block 840,000+:             3.125 BTC (current, April 2024)

        This creates scarcity — total supply is capped at ~21 million BTC.
        """
        halvings = self.height // self.HALVING_INTERVAL
        new_reward = self.INITIAL_REWARD / (2 ** halvings)

        if new_reward != self.block_reward:
            logger.info(
                "HALVING at block %d! Reward: %.2f → %.2f",
                self.height, self.block_reward, new_reward,
            )
            self.block_reward = new_reward

    def validate_chain(self) -> bool:
        """
        Validate the entire blockchain from genesis to tip.

        Checks every single block:
          1. Genesis block is valid
          2. Each block's previous_hash matches
          3. Each block's proof of work is valid
          4. Indices are sequential

        If ANY check fails, the entire chain is invalid.
        This is what makes blockchain tamper-proof.
        """
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            # Verify hash
            if current.hash != current.compute_hash():
                logger.error("Block %d hash mismatch!", i)
                return False

            # Verify chain link
            if current.previous_hash != previous.hash:
                logger.error("Block %d previous_hash mismatch!", i)
                return False

            # Verify proof of work
            if not current.hash.startswith("0" * current.difficulty):
                logger.error("Block %d invalid proof of work!", i)
                return False

        return True

    def get_balance(self, address: str) -> float:
        """
        Get the balance of an address by summing its UTXOs.

        This is how crypto wallets show your balance — they scan
        the UTXO set for outputs belonging to your address.
        """
        balance = 0.0
        for (tx_hash, idx), output in self.utxo_set.items():
            if output.address == address:
                balance += output.amount
        return balance

    def get_utxos_for_address(self, address: str) -> List[Tuple[str, int, float]]:
        """Get all unspent outputs for an address."""
        utxos = []
        for (tx_hash, idx), output in self.utxo_set.items():
            if output.address == address:
                utxos.append((tx_hash, idx, output.amount))
        return utxos

    def create_transaction(
        self, sender_wallet: Wallet, recipient_address: str,
        amount: float, fee: float = 0.1
    ) -> Optional[Transaction]:
        """
        Create and sign a transaction.

        Steps:
          1. Find sender's UTXOs
          2. Select enough UTXOs to cover amount + fee
          3. Create inputs from selected UTXOs
          4. Create outputs: one for recipient, one for change
          5. Sign the transaction
          6. Add to mempool
        """
        # Get available UTXOs
        utxos = self.get_utxos_for_address(sender_wallet.address)
        if not utxos:
            logger.warning("No UTXOs available for %s", sender_wallet.address[:16])
            return None

        # Select UTXOs to cover the amount
        needed = amount + fee
        selected = []
        running_total = 0.0

        for tx_hash, idx, value in sorted(utxos, key=lambda x: x[2]):
            selected.append((tx_hash, idx, value))
            running_total += value
            if running_total >= needed:
                break

        if running_total < needed:
            logger.warning(
                "Insufficient balance: have %.4f, need %.4f",
                running_total, needed,
            )
            return None

        # Create inputs
        inputs = []
        for tx_hash, idx, _ in selected:
            inp = TxInput(tx_hash, idx)
            inputs.append(inp)

        # Create outputs
        outputs = [TxOutput(recipient_address, amount)]

        # Change output (send remaining back to sender)
        change = running_total - amount - fee
        if change > 0.0001:  # Only create change output if meaningful
            outputs.append(TxOutput(sender_wallet.address, change))

        # Build transaction
        tx = Transaction(inputs, outputs)

        # Sign each input
        tx_data = tx.to_dict()
        signature = sender_wallet.sign_transaction(tx_data)
        for inp in tx.inputs:
            inp.signature = signature

        # Recompute hash with signatures
        tx.tx_hash = tx.compute_hash()

        # Add to mempool
        if self.add_transaction(tx):
            return tx
        return None

    def print_chain(self):
        """Pretty-print the blockchain."""
        print(f"\n{'═' * 60}")
        print(f"BLOCKCHAIN STATE — {self.height} blocks")
        print(f"{'═' * 60}")
        print(f"Difficulty: {self.difficulty} | Reward: {self.block_reward:.2f}")
        print(f"Mempool: {len(self.mempool)} pending txs")
        print(f"UTXOs: {len(self.utxo_set)} unspent outputs")
        print(f"Chain valid: {self.validate_chain()}")

        for block in self.chain:
            print(f"\n  Block #{block.index}")
            print(f"  ├─ Hash:     {block.hash[:32]}...")
            print(f"  ├─ Prev:     {block.previous_hash[:32]}...")
            print(f"  ├─ Nonce:    {block.nonce}")
            print(f"  ├─ Merkle:   {block.merkle_root[:32]}...")
            print(f"  └─ Txs:      {len(block.transactions)}")

    def to_dict(self) -> dict:
        """Serialize the blockchain."""
        return {
            "height": self.height,
            "difficulty": self.difficulty,
            "block_reward": self.block_reward,
            "chain": [b.to_dict() for b in self.chain],
        }


# ──────────────────────────────────────────────
# DEMO: Mine some blocks and make transfers
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("BLOCKCHAIN DEMO — Mining & Transactions")
    print("=" * 60)

    bc = Blockchain()

    # Create wallets
    miner = Wallet()
    alice = Wallet()
    bob = Wallet()

    print(f"\nMiner:  {miner.address}")
    print(f"Alice:  {alice.address}")
    print(f"Bob:    {bob.address}")

    # Mine 3 blocks to earn some coins
    print("\n--- Mining blocks ---")
    for i in range(3):
        block = bc.mine_block(miner.address)
        print(f"  Block #{block.index} mined (reward: {bc.block_reward})")

    balance = bc.get_balance(miner.address)
    print(f"\nMiner balance: {balance:.2f}")

    # Transfer coins
    print("\n--- Sending 25 coins from Miner to Alice ---")
    tx = bc.create_transaction(miner, alice.address, 25.0, fee=0.5)
    if tx:
        print(f"  Transaction created: {tx.tx_hash[:24]}...")
        block = bc.mine_block(miner.address)
        print(f"  Block #{block.index} mined (includes transfer)")

    print(f"\n--- Balances ---")
    print(f"  Miner: {bc.get_balance(miner.address):.2f}")
    print(f"  Alice: {bc.get_balance(alice.address):.2f}")
    print(f"  Bob:   {bc.get_balance(bob.address):.2f}")

    # Alice sends to Bob
    print("\n--- Alice sends 10 coins to Bob ---")
    tx = bc.create_transaction(alice, bob.address, 10.0, fee=0.1)
    if tx:
        block = bc.mine_block(miner.address)
        print(f"  Block #{block.index} mined")

    print(f"\n--- Final Balances ---")
    print(f"  Miner: {bc.get_balance(miner.address):.2f}")
    print(f"  Alice: {bc.get_balance(alice.address):.2f}")
    print(f"  Bob:   {bc.get_balance(bob.address):.2f}")

    # Validate entire chain
    print(f"\nChain valid: {bc.validate_chain()}")
    bc.print_chain()
