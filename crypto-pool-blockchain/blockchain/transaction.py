"""
Transaction — How value moves on a blockchain.
================================================

Two models exist in crypto:

1. **Account-based** (Ethereum) — Like a bank: you have a balance, you subtract.
2. **UTXO-based** (Bitcoin) — You spend "coins" you received, and get change back.

This implementation uses a simplified UTXO model:
  - Each transaction has INPUTS (coins being spent) and OUTPUTS (new coins created)
  - Inputs reference previous transaction outputs
  - The sum of inputs must equal the sum of outputs (+ miner fee)
  - Each transaction is signed by the sender using ECDSA

A coinbase transaction (mining reward) has no inputs — coins appear from nowhere.
This is how new coins enter circulation.
"""

import hashlib
import json
import time
from typing import List, Optional


class TxInput:
    """
    A transaction input — references a previous output being spent.

    Fields:
        tx_hash:    Hash of the transaction containing the output
        output_idx: Index of the output in that transaction
        signature:  ECDSA signature proving ownership
    """

    def __init__(self, tx_hash: str, output_idx: int, signature: str = ""):
        self.tx_hash = tx_hash
        self.output_idx = output_idx
        self.signature = signature

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "output_idx": self.output_idx,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TxInput":
        return cls(data["tx_hash"], data["output_idx"], data.get("signature", ""))


class TxOutput:
    """
    A transaction output — coins sent to an address.

    Fields:
        address: Recipient's public address (hash of public key)
        amount:  Number of coins sent
    """

    def __init__(self, address: str, amount: float):
        self.address = address
        self.amount = amount

    def to_dict(self) -> dict:
        return {"address": self.address, "amount": self.amount}

    @classmethod
    def from_dict(cls, data: dict) -> "TxOutput":
        return cls(data["address"], data["amount"])


class Transaction:
    """
    A full transaction with inputs, outputs, and metadata.

    How it works:
        1. Alice wants to send 5 coins to Bob
        2. Alice has a previous output of 10 coins (from tx "abc123", output 0)
        3. She creates:
           - Input:  references tx "abc123" output 0 (10 coins)
           - Output 1: 5 coins to Bob's address
           - Output 2: 5 coins back to Alice's address (change)
        4. She signs the transaction with her private key
        5. Anyone can verify the signature using her public key

    The fee is implicit: sum(inputs) - sum(outputs) = miner fee
    """

    def __init__(
        self,
        inputs: List[TxInput],
        outputs: List[TxOutput],
        timestamp: Optional[float] = None,
        tx_type: str = "transfer",
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = timestamp or time.time()
        self.tx_type = tx_type  # "transfer", "coinbase"
        self.tx_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Unique identifier for this transaction."""
        data = json.dumps({
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "timestamp": self.timestamp,
            "tx_type": self.tx_type,
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    @classmethod
    def create_coinbase(cls, miner_address: str, reward: float, block_index: int,
                        timestamp: Optional[float] = None) -> "Transaction":
        """
        Coinbase transaction — the mining reward.

        This is the ONLY way new coins enter the system.
        It has no inputs (coins come from nowhere).

        In Bitcoin:
          - Started at 50 BTC per block
          - Halves every 210,000 blocks (~4 years)
          - Currently 3.125 BTC (after 4 halvings)
        """
        return cls(
            inputs=[],
            outputs=[TxOutput(miner_address, reward)],
            tx_type="coinbase",
            timestamp=timestamp,
        )

    def total_input_value(self, utxo_set: dict) -> float:
        """
        Calculate total input value by looking up UTXOs.
        
        utxo_set: {(tx_hash, output_idx): TxOutput}
        """
        total = 0.0
        for inp in self.inputs:
            key = (inp.tx_hash, inp.output_idx)
            if key in utxo_set:
                total += utxo_set[key].amount
        return total

    def total_output_value(self) -> float:
        """Sum of all output amounts."""
        return sum(out.amount for out in self.outputs)

    def fee(self, utxo_set: dict) -> float:
        """Transaction fee = inputs - outputs."""
        if self.tx_type == "coinbase":
            return 0.0
        return self.total_input_value(utxo_set) - self.total_output_value()

    def is_coinbase(self) -> bool:
        return self.tx_type == "coinbase"

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "tx_type": self.tx_type,
            "timestamp": self.timestamp,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Transaction":
        tx = cls(
            inputs=[TxInput.from_dict(i) for i in data["inputs"]],
            outputs=[TxOutput.from_dict(o) for o in data["outputs"]],
            timestamp=data["timestamp"],
            tx_type=data["tx_type"],
        )
        tx.tx_hash = data["tx_hash"]
        return tx

    def __repr__(self) -> str:
        if self.is_coinbase():
            return f"CoinbaseTx({self.outputs[0].amount} → {self.outputs[0].address[:12]}...)"
        return (
            f"Tx({len(self.inputs)} inputs → {len(self.outputs)} outputs, "
            f"total={self.total_output_value():.4f})"
        )


# ──────────────────────────────────────────────
# DEMO
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("TRANSACTION DEMO")
    print("=" * 60)

    # 1. Coinbase (mining reward)
    coinbase = Transaction.create_coinbase("miner_alice_addr", 50.0, 1)
    print(f"\n1. Mining reward: {coinbase}")
    print(f"   Hash: {coinbase.tx_hash[:32]}...")

    # 2. Alice sends 10 to Bob (spending from coinbase)
    tx = Transaction(
        inputs=[TxInput(coinbase.tx_hash, 0)],
        outputs=[
            TxOutput("bob_address", 10.0),      # 10 to Bob
            TxOutput("alice_address", 39.5),     # 39.5 change to Alice
        ],                                        # 0.5 implicit fee
    )
    print(f"\n2. Transfer: {tx}")
    print(f"   Hash: {tx.tx_hash[:32]}...")

    # 3. Check fee
    utxo_set = {(coinbase.tx_hash, 0): coinbase.outputs[0]}
    print(f"   Fee:  {tx.fee(utxo_set):.1f} coins (goes to miner)")
