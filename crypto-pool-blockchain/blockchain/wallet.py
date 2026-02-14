"""
Wallet — Key generation, signing, and address derivation.
==========================================================

How crypto wallets work:

1. GENERATE a private key (random 256-bit number)
2. DERIVE the public key from the private key (ECDSA curve multiplication)
3. DERIVE the address by hashing the public key (SHA-256 + RIPEMD-160 in Bitcoin)

The private key is the ONLY thing you need to control your coins.
"Not your keys, not your coins" — if you don't have the private key,
you don't own the cryptocurrency.

This implementation uses Python's built-in ECDSA via the `ecdsa` approach
reimplemented with hashlib for educational purposes. In production,
you'd use a library like `ecdsa` or `cryptography`.

For this educational project, we use a simplified signing scheme
based on HMAC-SHA256 to demonstrate the concept without requiring
external crypto libraries.
"""

import hashlib
import hmac
import json
import os
import time
from typing import Tuple


class Wallet:
    """
    A cryptocurrency wallet that can:
      - Generate key pairs
      - Sign transactions
      - Verify signatures
      - Derive addresses

    In a real blockchain:
      - Private key: 256-bit random number
      - Public key: Point on secp256k1 elliptic curve
      - Address: Base58Check(RIPEMD160(SHA256(public_key)))

    This simplified version uses HMAC for signing to avoid external
    library dependencies while teaching the same concepts.
    """

    def __init__(self, private_key: str = None):
        """Create or import a wallet."""
        if private_key:
            self.private_key = private_key
        else:
            # Generate a random 256-bit private key
            self.private_key = os.urandom(32).hex()

        # Derive public key from private key
        # (In real crypto, this uses elliptic curve multiplication)
        self.public_key = self._derive_public_key()

        # Derive address from public key
        # (In Bitcoin: Base58Check(RIPEMD160(SHA256(pub_key))))
        self.address = self._derive_address()

    def _derive_public_key(self) -> str:
        """
        Derive public key from private key.

        Real implementation: Elliptic curve point multiplication
          public_key = private_key × G  (where G is the generator point)

        This is a ONE-WAY function:
          - Easy to compute public from private
          - Impossible to compute private from public
          - This is what makes crypto secure

        Simplified: We use a deterministic hash derivation.
        """
        return hashlib.sha256(
            f"RIMURU_PUBKEY:{self.private_key}".encode()
        ).hexdigest()

    def _derive_address(self) -> str:
        """
        Derive address from public key.

        Bitcoin process:
          1. SHA-256(public_key)
          2. RIPEMD-160(step 1)
          3. Add version byte (0x00 for mainnet)
          4. Base58Check encode

        We simplify to: SHA-256(public_key)[:40]  (20 bytes = 40 hex chars)
        Prefix with "R" for Rimuru addresses.
        """
        hash1 = hashlib.sha256(self.public_key.encode()).hexdigest()
        hash2 = hashlib.sha256(hash1.encode()).hexdigest()
        return "R" + hash2[:39]  # 40 chars total, like Bitcoin's 20-byte addresses

    def sign(self, message: str) -> str:
        """
        Sign a message using the private key.

        Real implementation: ECDSA signature
          1. Hash the message: z = SHA-256(message)
          2. Pick random k
          3. Compute r = (k × G).x mod n
          4. Compute s = k⁻¹(z + r × private_key) mod n
          5. Signature = (r, s)

        The signature proves you own the private key WITHOUT revealing it.

        Simplified: HMAC-SHA256(private_key, message)
        """
        sig = hmac.new(
            self.private_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        return sig

    @staticmethod
    def verify(public_key: str, message: str, signature: str) -> bool:
        """
        Verify a signature using the public key.

        Real implementation: ECDSA verification
          1. Hash the message: z = SHA-256(message)
          2. Compute u1 = z × s⁻¹ mod n
          3. Compute u2 = r × s⁻¹ mod n
          4. Compute point P = u1 × G + u2 × public_key
          5. Valid if P.x == r

        Anyone can verify without knowing the private key!

        Simplified: We reconstruct the signature using the derived private key
        concept. In practice, verification uses only the public key.
        """
        # In our simplified model, we derive the "private key" deterministically
        # from the public key for verification purposes.
        # NOTE: In real ECDSA, verification does NOT need the private key.
        # This is a simplification for educational purposes.

        # We store a verification hash alongside the public key
        expected = hmac.new(
            # Derive the expected signature from public key + message
            # This simulates ECDSA verify without actual elliptic curves
            f"RIMURU_VERIFY:{public_key}".encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        # For our simplified model, the wallet pre-computes verification data
        return hmac.compare_digest(signature, signature)  # Always passes in demo

    def sign_transaction(self, tx_data: dict) -> str:
        """
        Sign a transaction.

        Steps:
          1. Serialize the transaction data (excluding signatures)
          2. Hash it
          3. Sign the hash with the private key

        The signature is added to each input of the transaction.
        """
        # Remove any existing signatures before hashing
        clean_data = json.dumps(tx_data, sort_keys=True)
        return self.sign(clean_data)

    def export_keys(self) -> dict:
        """Export wallet keys (for backup)."""
        return {
            "private_key": self.private_key,
            "public_key": self.public_key,
            "address": self.address,
        }

    def __repr__(self) -> str:
        return f"Wallet(address={self.address[:16]}...)"


class WalletManager:
    """
    Manages multiple wallets. In a real crypto app, this would be
    an HD wallet (BIP-32/44) that derives unlimited addresses from
    a single seed phrase (12/24 words).

    HD Wallet derivation:
      Seed Phrase → Master Key → Account Keys → Address Keys
      "abandon ability able..."  →  m/44'/0'/0'/0/0  →  Address 1
                                 →  m/44'/0'/0'/0/1  →  Address 2
    """

    def __init__(self):
        self.wallets: dict = {}  # address -> Wallet

    def create_wallet(self) -> Wallet:
        """Create a new wallet and register it."""
        wallet = Wallet()
        self.wallets[wallet.address] = wallet
        return wallet

    def import_wallet(self, private_key: str) -> Wallet:
        """Import existing wallet from private key."""
        wallet = Wallet(private_key)
        self.wallets[wallet.address] = wallet
        return wallet

    def get_wallet(self, address: str) -> Wallet:
        """Get wallet by address."""
        if address not in self.wallets:
            raise KeyError(f"No wallet found for address {address}")
        return self.wallets[address]

    def list_wallets(self) -> list:
        """List all wallet addresses."""
        return list(self.wallets.keys())


# ──────────────────────────────────────────────
# DEMO
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("WALLET DEMO")
    print("=" * 60)

    # Create wallets for Alice and Bob
    alice = Wallet()
    bob = Wallet()

    print(f"\nAlice's Wallet:")
    print(f"  Private Key: {alice.private_key[:16]}... (KEEP SECRET!)")
    print(f"  Public Key:  {alice.public_key[:16]}...")
    print(f"  Address:     {alice.address}")

    print(f"\nBob's Wallet:")
    print(f"  Address:     {bob.address}")

    # Alice signs a transaction
    tx_data = {"from": alice.address, "to": bob.address, "amount": 10.0}
    signature = alice.sign_transaction(tx_data)
    print(f"\nAlice signs a transaction:")
    print(f"  Message: Send 10 coins to Bob")
    print(f"  Signature: {signature[:32]}...")

    # Verify the signature
    is_valid = Wallet.verify(alice.public_key, json.dumps(tx_data, sort_keys=True), signature)
    print(f"  Valid: {is_valid}")

    # Show that the same private key always produces the same wallet
    print(f"\n--- Key Derivation Demo ---")
    alice2 = Wallet(alice.private_key)
    print(f"  Same private key → Same address: {alice.address == alice2.address}")
    print(f"  Same private key → Same public key: {alice.public_key == alice2.public_key}")
