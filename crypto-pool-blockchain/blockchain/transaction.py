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
        signature:  ECDSA (DER) signature proving ownership
        public_key: Compressed public key of the signer (hex, 33 bytes)
    """

    def __init__(self, tx_hash: str, output_idx: int,
                 signature: str = "", public_key: str = ""):
        self.tx_hash = tx_hash
        self.output_idx = output_idx
        self.signature = signature
        self.public_key = public_key  # signer's compressed pubkey (hex)

    def to_dict(self) -> dict:
        return {
            "tx_hash": self.tx_hash,
            "output_idx": self.output_idx,
            "signature": self.signature,
            "public_key": self.public_key,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TxInput":
        return cls(
            data["tx_hash"], data["output_idx"],
            data.get("signature", ""), data.get("public_key", ""),
        )


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
        data: Optional[dict] = None,
    ):
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = timestamp or time.time()
        self.tx_type = tx_type  # "transfer", "coinbase", "vault"
        self.data = data  # optional metadata (vault records, labels, hashes)
        self.tx_hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Unique identifier for this transaction."""
        hash_data = {
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
            "timestamp": self.timestamp,
            "tx_type": self.tx_type,
        }
        if self.data:
            hash_data["data"] = self.data
        return hashlib.sha256(
            json.dumps(hash_data, sort_keys=True).encode()
        ).hexdigest()

    def signable_dict(self) -> dict:
        """
        Return the canonical data to be signed (excludes signatures, pubkeys, tx_hash).

        This is what the sender signs with their private key.
        It's stable — it doesn't change when signatures are attached.
        """
        d = {
            "inputs": [
                {"tx_hash": inp.tx_hash, "output_idx": inp.output_idx}
                for inp in self.inputs
            ],
            "outputs": [out.to_dict() for out in self.outputs],
            "timestamp": self.timestamp,
            "tx_type": self.tx_type,
        }
        if self.data:
            d["data"] = self.data
        return d

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
        d = {
            "tx_hash": self.tx_hash,
            "tx_type": self.tx_type,
            "timestamp": self.timestamp,
            "inputs": [inp.to_dict() for inp in self.inputs],
            "outputs": [out.to_dict() for out in self.outputs],
        }
        if self.data:
            d["data"] = self.data
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        tx = cls(
            inputs=[TxInput.from_dict(i) for i in d["inputs"]],
            outputs=[TxOutput.from_dict(o) for o in d["outputs"]],
            timestamp=d["timestamp"],
            tx_type=d["tx_type"],
            data=d.get("data"),
        )
        tx.tx_hash = d["tx_hash"]
        return tx

    @classmethod
    def create_vault(cls, owner_address: str, data: dict,
                     timestamp: Optional[float] = None) -> "Transaction":
        """
        Create a vault transaction — data-only, no value transfer.

        Vault records anchor data hashes on-chain for tamper-proof provenance.
        The data dict is embedded directly in the transaction and becomes
        part of the block's Merkle tree, making it impossible to alter
        without invalidating the entire chain.

        Typical data fields:
            vault_type:  "wallet", "api_key", "seed_phrase", "scan_result", etc.
            data_hash:   SHA-256 of the original sensitive data
            label:       Human-readable description (non-sensitive)
            source:      Where the finding came from
        """
        return cls(
            inputs=[],
            outputs=[TxOutput(owner_address, 0.0)],  # zero-value marker
            tx_type="vault",
            timestamp=timestamp,
            data=data,
        )

    def is_vault(self) -> bool:
        """Is this a vault (data-only) transaction?"""
        return self.tx_type == "vault"

    def __repr__(self) -> str:
        if self.is_coinbase():
            return f"CoinbaseTx({self.outputs[0].amount} → {self.outputs[0].address[:12]}...)"
        if self.is_vault():
            vtype = self.data.get('vault_type', 'unknown') if self.data else 'unknown'
            return f"VaultTx({vtype} → {self.outputs[0].address[:12]}...)"
        return (
            f"Tx({len(self.inputs)} inputs → {len(self.outputs)} outputs, "
            f"total={self.total_output_value():.4f})")


# ──────────────────────────────────────────────
# DEMO
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("= - transaction.py:264" * 60)
    print("TRANSACTION DEMO - transaction.py:265")
    print("= - transaction.py:266" * 60)

    # 1. Coinbase (mining reward)
    coinbase = Transaction.create_coinbase("miner_alice_addr", 50.0, 1)
    print(f"\n1. Mining reward: {coinbase} - transaction.py:270")
    print(f"Hash: {coinbase.tx_hash[:32]}... - transaction.py:271")

    # 2. Alice sends 10 to Bob (spending from coinbase)
    tx = Transaction(
        inputs=[TxInput(coinbase.tx_hash, 0)],
        outputs=[
            TxOutput("bob_address", 10.0),      # 10 to Bob
            TxOutput("alice_address", 39.5),     # 39.5 change to Alice
        ],                                        # 0.5 implicit fee
    )
    print(f"\n2. Transfer: {tx} - transaction.py:281")
    print(f"Hash: {tx.tx_hash[:32]}... - transaction.py:282")

    # 3. Check fee
    utxo_set = {(coinbase.tx_hash, 0): coinbase.outputs[0]}
    print(f"Fee:  {tx.fee(utxo_set):.1f} coins (goes to miner) - transaction.py:286")
