"""
Wallet -- Production-grade ECDSA key generation, signing, and address derivation.
=================================================================================

UPGRADED from simulation to real cryptography:

  OLD (simulation):  HMAC-SHA256 signatures, SHA-256 public key derivation
  NEW (production):  secp256k1 ECDSA signatures, elliptic curve public keys,
                     Base58Check addresses, BIP-39 mnemonic seed phrases,
                     BIP-32 HD key derivation

How real crypto wallets work:

  1. GENERATE a seed phrase (12/24 random words from BIP-39 wordlist)
  2. DERIVE a master private key from the seed (HMAC-SHA512)
  3. DERIVE child keys using BIP-32 hierarchical deterministic paths
  4. COMPUTE public key via elliptic curve multiplication (secp256k1)
  5. DERIVE address: Base58Check(RIPEMD160(SHA256(public_key)))

  The private key is the ONLY thing you need to control your coins.
  "Not your keys, not your coins"
"""

import hashlib
import hmac as hmac_mod
import json
import os
import struct
from typing import Tuple, Optional, List

from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.util import sigencode_der, sigdecode_der
import base58

# Try to import mnemonic for BIP-39 seed phrases
try:
    from mnemonic import Mnemonic
    HAS_MNEMONIC = True
except ImportError:
    HAS_MNEMONIC = False


# ====================================================================
#  ADDRESS ENCODING -- Base58Check (same as Bitcoin)
# ====================================================================

def _ripemd160(data: bytes) -> bytes:
    """RIPEMD-160 hash (used in Bitcoin address derivation)."""
    h = hashlib.new("ripemd160")
    h.update(data)
    return h.digest()


def _hash160(data: bytes) -> bytes:
    """Hash160 = RIPEMD160(SHA256(data)) -- Bitcoin's address hash."""
    return _ripemd160(hashlib.sha256(data).digest())


def _checksum(payload: bytes) -> bytes:
    """First 4 bytes of double-SHA256 -- error detection in addresses."""
    return hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]


def pubkey_to_address(public_key_bytes: bytes, version: int = 0x52) -> str:
    """
    Derive a Rimuru address from a public key.

    Process (same as Bitcoin, different version byte):
      1. SHA-256(public_key)
      2. RIPEMD-160(step 1)  ->  20-byte hash
      3. Prepend version byte (0x52 = 'R' prefix in Base58)
      4. Append 4-byte checksum
      5. Base58 encode

    Args:
        public_key_bytes: Compressed or uncompressed public key
        version: Version byte (0x52 gives 'R' prefix for Rimuru)

    Returns:
        Base58Check encoded address string
    """
    key_hash = _hash160(public_key_bytes)
    payload = bytes([version]) + key_hash
    return base58.b58encode(payload + _checksum(payload)).decode()


def validate_address(address: str) -> bool:
    """Validate a Base58Check address (checksum verification)."""
    try:
        decoded = base58.b58decode(address)
        payload, check = decoded[:-4], decoded[-4:]
        return _checksum(payload) == check
    except Exception:
        return False


# ====================================================================
#  WALLET -- Real ECDSA on secp256k1
# ====================================================================

class Wallet:
    """
    Production cryptocurrency wallet using real ECDSA (secp256k1).

    Features:
      - secp256k1 elliptic curve key pairs (same curve as Bitcoin/Ethereum)
      - DER-encoded ECDSA signatures
      - Base58Check addresses with checksum validation
      - BIP-39 mnemonic seed phrase support
      - Deterministic key derivation from seed
      - Transaction signing and verification

    Security properties:
      - Private key: 256-bit random number (32 bytes)
      - Public key: Point on secp256k1 curve (33 bytes compressed)
      - Signing: ECDSA with SHA-256 message digest
      - Verification: Anyone can verify with only the public key
      - Address: Base58Check(RIPEMD160(SHA256(compressed_pubkey)))
    """

    def __init__(self, private_key: str = None, seed_phrase: str = None):
        """
        Create or import a wallet.

        Args:
            private_key: Hex-encoded 32-byte private key (import existing)
            seed_phrase: BIP-39 mnemonic phrase (derive from seed)
        """
        self.seed_phrase: Optional[str] = None

        if seed_phrase:
            # Derive from BIP-39 seed phrase
            self._signing_key = self._from_seed_phrase(seed_phrase)
            self.seed_phrase = seed_phrase
        elif private_key:
            # Import existing private key
            key_bytes = bytes.fromhex(private_key)
            self._signing_key = SigningKey.from_string(key_bytes, curve=SECP256k1)
        else:
            # Generate new random key pair
            self._signing_key = SigningKey.generate(curve=SECP256k1)

        # Derive public key via elliptic curve multiplication
        # private_key x G = public_key (where G is the generator point)
        self._verifying_key = self._signing_key.get_verifying_key()

        # Store keys in standard formats
        self.private_key = self._signing_key.to_string().hex()
        self.public_key = self._compressed_public_key().hex()

        # Derive address from compressed public key
        self.address = pubkey_to_address(self._compressed_public_key())

    def _from_seed_phrase(self, phrase: str) -> SigningKey:
        """
        Derive a private key from a BIP-39 seed phrase.

        BIP-39 process:
          1. Validate mnemonic words against wordlist
          2. PBKDF2(mnemonic, "mnemonic" + passphrase, 2048 rounds, SHA-512)
          3. Result = 512-bit seed
          4. HMAC-SHA512(seed, "Bitcoin seed") -> master key + chain code
          5. First 32 bytes = master private key
        """
        if HAS_MNEMONIC:
            m = Mnemonic("english")
            if not m.check(phrase):
                raise ValueError("Invalid mnemonic phrase")
            # BIP-39 seed derivation
            seed = hashlib.pbkdf2_hmac(
                "sha512",
                phrase.encode("utf-8"),
                ("mnemonic" + "").encode("utf-8"),  # empty passphrase
                2048,
            )
        else:
            # Fallback: simple deterministic derivation
            seed = hashlib.sha512(phrase.encode("utf-8")).digest()

        # BIP-32: master key derivation
        # HMAC-SHA512("Bitcoin seed", seed) -> (key, chain_code)
        I = hmac_mod.new(b"Bitcoin seed", seed, hashlib.sha512).digest()
        master_key = I[:32]  # First 32 bytes = private key

        return SigningKey.from_string(master_key, curve=SECP256k1)

    def _compressed_public_key(self) -> bytes:
        """
        Get the compressed public key (33 bytes).

        Uncompressed: 04 + x (32 bytes) + y (32 bytes) = 65 bytes
        Compressed:   02/03 + x (32 bytes) = 33 bytes
          - 02 if y is even, 03 if y is odd

        Compressed keys save ~50% space and are the standard format.
        """
        point = self._verifying_key.pubkey.point
        x = point.x()
        y = point.y()
        prefix = b'\x02' if y % 2 == 0 else b'\x03'
        return prefix + x.to_bytes(32, 'big')

    @staticmethod
    def generate_seed_phrase(strength: int = 128) -> str:
        """
        Generate a new BIP-39 mnemonic seed phrase.

        Args:
            strength: Entropy bits (128=12 words, 256=24 words)

        Returns:
            Space-separated mnemonic words

        The seed phrase IS your wallet. Write it down and store it safely.
        Anyone with these words controls all your funds. Forever.
        """
        if HAS_MNEMONIC:
            m = Mnemonic("english")
            return m.generate(strength)
        else:
            # Fallback: generate random words (NOT BIP-39 compatible)
            entropy = os.urandom(strength // 8)
            return hashlib.sha256(entropy).hexdigest()

    def sign(self, message: str) -> str:
        """
        Sign a message using ECDSA on secp256k1.

        ECDSA signing process:
          1. Hash the message: z = SHA-256(message)
          2. Pick random k (nonce)
          3. Compute curve point R = k x G
          4. r = R.x mod n
          5. s = k^-1 x (z + r x private_key) mod n
          6. Signature = DER(r, s)

        The signature proves ownership of the private key
        WITHOUT revealing the private key itself.

        Returns:
            Hex-encoded DER signature
        """
        msg_hash = hashlib.sha256(message.encode()).digest()
        signature = self._signing_key.sign_digest(
            msg_hash,
            sigencode=sigencode_der,
        )
        return signature.hex()

    @staticmethod
    def verify(public_key_hex: str, message: str, signature_hex: str) -> bool:
        """
        Verify an ECDSA signature using only the public key.

        ECDSA verification:
          1. Hash the message: z = SHA-256(message)
          2. Parse signature (r, s)
          3. Compute u1 = z x s^-1 mod n
          4. Compute u2 = r x s^-1 mod n
          5. Compute point P = u1 x G + u2 x public_key
          6. Valid if P.x == r (mod n)

        ANYONE can verify -- no private key needed.
        This is the foundation of trustless verification.

        Args:
            public_key_hex: Hex-encoded compressed public key (33 bytes)
            message: The original message that was signed
            signature_hex: Hex-encoded DER signature

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            pub_bytes = bytes.fromhex(public_key_hex)

            # Handle compressed public key (33 bytes)
            if len(pub_bytes) == 33:
                vk = VerifyingKey.from_string(pub_bytes, curve=SECP256k1)
            else:
                vk = VerifyingKey.from_string(pub_bytes, curve=SECP256k1)

            msg_hash = hashlib.sha256(message.encode()).digest()
            sig_bytes = bytes.fromhex(signature_hex)

            return vk.verify_digest(
                sig_bytes,
                msg_hash,
                sigdecode=sigdecode_der,
            )
        except (BadSignatureError, Exception):
            return False

    def sign_transaction(self, tx_data: dict) -> str:
        """
        Sign a transaction's data.

        Process:
          1. Serialize transaction data (canonical JSON, sorted keys)
          2. SHA-256 hash the serialized data
          3. ECDSA sign the hash
          4. Return DER-encoded signature

        The signature is attached to each input, proving the spender
        owns the UTXO being consumed.
        """
        clean_data = json.dumps(tx_data, sort_keys=True)
        return self.sign(clean_data)

    def verify_transaction(self, tx_data: dict, signature: str) -> bool:
        """Verify a transaction signature against this wallet's public key."""
        clean_data = json.dumps(tx_data, sort_keys=True)
        return self.verify(self.public_key, clean_data, signature)

    def export_keys(self) -> dict:
        """
        Export wallet keys for backup.

        WARNING: The private key gives full control over all funds.
        Store it encrypted and offline. Never share it.
        """
        result = {
            "private_key": self.private_key,
            "public_key": self.public_key,
            "address": self.address,
        }
        if self.seed_phrase:
            result["seed_phrase"] = self.seed_phrase
        return result

    def __repr__(self) -> str:
        return f"Wallet(address={self.address[:16]}...)"


# ====================================================================
#  HD WALLET -- BIP-32 Hierarchical Deterministic Wallet
# ====================================================================

class HDWallet:
    """
    BIP-32 Hierarchical Deterministic Wallet.

    From a single seed phrase, derive unlimited addresses:

      Seed Phrase (12/24 words)
        -- Master Key (m)
            |-- Account 0 (m/44'/0'/0')
            |   |-- External chain (m/44'/0'/0'/0)
            |   |   |-- Address 0  (m/44'/0'/0'/0/0)
            |   |   |-- Address 1  (m/44'/0'/0'/0/1)
            |   |   +-- ...
            |   +-- Internal chain (m/44'/0'/0'/1)  <- change addresses
            |       |-- Address 0  (m/44'/0'/0'/1/0)
            |       +-- ...
            +-- Account 1 (m/44'/0'/1')
                +-- ...

    Benefits:
      - Single backup (seed phrase) covers ALL addresses
      - New addresses can be generated without the private key
      - Privacy: each transaction uses a fresh address
    """

    # BIP-44 purpose constant
    PURPOSE = 44
    # Rimuru coin type (custom -- Bitcoin=0, Ethereum=60)
    COIN_TYPE = 999

    def __init__(self, seed_phrase: str = None):
        """
        Create an HD wallet from a seed phrase.

        Args:
            seed_phrase: BIP-39 mnemonic (generates new if None)
        """
        if seed_phrase is None:
            self.seed_phrase = Wallet.generate_seed_phrase(128)
        else:
            self.seed_phrase = seed_phrase

        # Derive master key from seed phrase
        self._master_seed = self._mnemonic_to_seed(self.seed_phrase)
        I = hmac_mod.new(b"Bitcoin seed", self._master_seed, hashlib.sha512).digest()
        self._master_key = I[:32]
        self._master_chain_code = I[32:]

        # Track derived wallets
        self._wallets: List[Wallet] = []
        self._next_index = 0

    def _mnemonic_to_seed(self, mnemonic: str, passphrase: str = "") -> bytes:
        """BIP-39: Convert mnemonic to 512-bit seed using PBKDF2."""
        return hashlib.pbkdf2_hmac(
            "sha512",
            mnemonic.encode("utf-8"),
            ("mnemonic" + passphrase).encode("utf-8"),
            2048,
        )

    def _derive_child_key(self, parent_key: bytes, parent_chain: bytes,
                          index: int) -> Tuple[bytes, bytes]:
        """
        BIP-32 child key derivation.

        For normal (non-hardened) derivation:
          1. data = serialize_public_key(parent_key) + index_bytes
          2. I = HMAC-SHA512(parent_chain_code, data)
          3. child_key = (parse(I[:32]) + parent_key) mod n
          4. child_chain_code = I[32:]

        For hardened derivation (index >= 0x80000000):
          1. data = 0x00 + parent_key + index_bytes
          2. Same HMAC process

        Hardened keys are more secure -- the parent public key cannot
        derive child keys. Used for account-level keys.
        """
        if index >= 0x80000000:
            # Hardened: use private key directly
            data = b'\x00' + parent_key + struct.pack('>I', index)
        else:
            # Normal: use public key
            sk = SigningKey.from_string(parent_key, curve=SECP256k1)
            vk = sk.get_verifying_key()
            # Compressed public key
            point = vk.pubkey.point
            prefix = b'\x02' if point.y() % 2 == 0 else b'\x03'
            pub_compressed = prefix + point.x().to_bytes(32, 'big')
            data = pub_compressed + struct.pack('>I', index)

        I = hmac_mod.new(parent_chain, data, hashlib.sha512).digest()
        child_key_int = (int.from_bytes(I[:32], 'big') +
                        int.from_bytes(parent_key, 'big')) % SECP256k1.order
        child_key = child_key_int.to_bytes(32, 'big')
        child_chain = I[32:]

        return child_key, child_chain

    def derive_wallet(self, account: int = 0, index: int = None) -> Wallet:
        """
        Derive a wallet at BIP-44 path: m/44'/999'/account'/0/index

        Args:
            account: Account number (default 0)
            index: Address index (auto-increments if None)

        Returns:
            Wallet at the derived path
        """
        if index is None:
            index = self._next_index
            self._next_index += 1

        # m/44' (purpose)
        key, chain = self._derive_child_key(
            self._master_key, self._master_chain_code,
            self.PURPOSE + 0x80000000
        )
        # m/44'/999' (coin type)
        key, chain = self._derive_child_key(key, chain, self.COIN_TYPE + 0x80000000)
        # m/44'/999'/account' (account)
        key, chain = self._derive_child_key(key, chain, account + 0x80000000)
        # m/44'/999'/account'/0 (external chain)
        key, chain = self._derive_child_key(key, chain, 0)
        # m/44'/999'/account'/0/index (address)
        key, chain = self._derive_child_key(key, chain, index)

        wallet = Wallet(private_key=key.hex())
        self._wallets.append(wallet)
        return wallet

    def get_wallets(self) -> List[Wallet]:
        """Get all derived wallets."""
        return self._wallets.copy()

    def export_seed(self) -> dict:
        """
        Export the seed phrase for backup.

        THIS IS THE MASTER KEY. Anyone with these words
        can derive ALL your addresses and spend ALL your funds.
        Store it offline, in a fireproof safe, on metal if possible.
        """
        return {
            "seed_phrase": self.seed_phrase,
            "derived_addresses": [w.address for w in self._wallets],
            "warning": "NEVER share this seed phrase. It controls ALL funds.",
        }


class WalletManager:
    """
    Manages multiple wallets with optional HD wallet backing.

    Can operate in two modes:
      1. HD mode: All wallets derived from a single seed phrase
      2. Manual mode: Individual wallets created/imported separately
    """

    def __init__(self, seed_phrase: str = None):
        self.wallets: dict = {}  # address -> Wallet
        self.hd_wallet: Optional[HDWallet] = None

        if seed_phrase or HAS_MNEMONIC:
            try:
                self.hd_wallet = HDWallet(seed_phrase)
            except Exception:
                pass

    def create_wallet(self) -> Wallet:
        """Create a new wallet (from HD tree if available)."""
        if self.hd_wallet:
            wallet = self.hd_wallet.derive_wallet()
        else:
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


# ------------------------------------------
# DEMO
# ------------------------------------------

if __name__ == "__main__":
    print("=" * 64)
    print("  PRODUCTION WALLET DEMO -- Real ECDSA (secp256k1)")
    print("=" * 64)

    # 1. Create wallets
    alice = Wallet()
    bob = Wallet()

    print(f"\n--- Key Generation ---")
    print(f"  Alice:")
    print(f"    Private Key:  {alice.private_key[:16]}...{alice.private_key[-8:]}  (32 bytes)")
    print(f"    Public Key:   {alice.public_key[:16]}...{alice.public_key[-8:]}  (33 bytes compressed)")
    print(f"    Address:      {alice.address}")
    print(f"    Valid addr:   {validate_address(alice.address)}")

    print(f"\n  Bob:")
    print(f"    Address:      {bob.address}")

    # 2. ECDSA signing & verification
    print(f"\n--- ECDSA Signing ---")
    message = "Send 10 RIMURU to Bob"
    signature = alice.sign(message)
    print(f"  Message:   '{message}'")
    print(f"  Signature: {signature[:32]}...  (DER encoded)")
    print(f"  Sig bytes: {len(bytes.fromhex(signature))}")

    # 3. Verify (anyone can do this with just the public key)
    print(f"\n--- ECDSA Verification ---")
    valid = Wallet.verify(alice.public_key, message, signature)
    print(f"  Alice's pubkey verifies:  {valid}")

    # Tamper with message
    fake_valid = Wallet.verify(alice.public_key, "Send 1000 RIMURU to Bob", signature)
    print(f"  Tampered message:         {fake_valid}  (different message)")

    # Wrong public key
    wrong_valid = Wallet.verify(bob.public_key, message, signature)
    print(f"  Bob's pubkey verifies:    {wrong_valid}  (wrong signer)")

    # 4. Transaction signing
    print(f"\n--- Transaction Signing ---")
    tx_data = {"from": alice.address, "to": bob.address, "amount": 10.0}
    tx_sig = alice.sign_transaction(tx_data)
    tx_valid = alice.verify_transaction(tx_data, tx_sig)
    print(f"  Tx signature valid: {tx_valid}")

    # 5. Deterministic key derivation
    print(f"\n--- Deterministic Keys ---")
    alice2 = Wallet(alice.private_key)
    print(f"  Same private key -> Same address: {alice.address == alice2.address}")
    print(f"  Same private key -> Same pubkey:  {alice.public_key == alice2.public_key}")

    # 6. Seed phrase wallet
    print(f"\n--- BIP-39 Seed Phrase ---")
    if HAS_MNEMONIC:
        phrase = Wallet.generate_seed_phrase(128)
        print(f"  Seed phrase: {phrase}")
        sw1 = Wallet(seed_phrase=phrase)
        sw2 = Wallet(seed_phrase=phrase)
        print(f"  Same phrase -> Same address: {sw1.address == sw2.address}")
        print(f"  Address: {sw1.address}")
    else:
        print("  (install 'mnemonic' package for BIP-39 support)")

    # 7. HD Wallet
    print(f"\n--- HD Wallet (BIP-32/44) ---")
    hd = HDWallet()
    print(f"  Seed: {hd.seed_phrase[:40]}...")
    for i in range(5):
        w = hd.derive_wallet()
        print(f"  m/44'/999'/0'/0/{i} -> {w.address}")

    # Verify deterministic: same seed -> same addresses
    hd2 = HDWallet(hd.seed_phrase)
    addrs1 = [hd2.derive_wallet(index=i).address for i in range(5)]
    addrs2 = [hd.get_wallets()[i].address for i in range(5)]
    print(f"\n  Same seed -> Same 5 addresses: {addrs1 == addrs2}")

    # 8. Address validation
    print(f"\n--- Address Validation ---")
    print(f"  Valid address:    {validate_address(alice.address)}")
    print(f"  Corrupted 'XXXX': {validate_address('XXXX')}")
    print(f"  Empty string:     {validate_address('')}")
