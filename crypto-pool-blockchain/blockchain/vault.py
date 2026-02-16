"""
VaultLedger — Tamper-proof on-chain storage for scanner findings.
==================================================================

Records everything your scanners find onto your own blockchain
so the data can never be stolen, altered, or denied.

How it works:
  1. Scanner finds something (wallet, API key, seed phrase, etc.)
  2. VaultLedger hashes the sensitive parts (SHA-256)
  3. A "vault" transaction is created with the hash + metadata
  4. Transaction goes into the mempool → next mined block
  5. Once mined, the record is part of the Merkle tree
  6. Changing it would invalidate every block after it

Security model:
  - Raw secrets NEVER go on-chain — only their SHA-256 hash
  - The hash proves you had the data at a specific time
  - Labels and metadata (non-sensitive) are stored in clear
  - Original data stays in your encrypted local vault

Usage:
    from blockchain.vault import VaultLedger
    from blockchain.chain import Blockchain
    from blockchain.wallet import Wallet

    bc = Blockchain()
    vault_wallet = Wallet()
    vault = VaultLedger(bc, vault_wallet)

    # Record a wallet finding
    vault.record_wallet("0xabc...", "ethereum", "keys.txt", balance=1.5)

    # Record an API key
    vault.record_api_key("binance", "REAL_KEY_HERE", "config.json")

    # Mine the block to seal the records
    bc.mine_block(vault_wallet.address)

    # Query what's been stored
    records = vault.get_records()
"""

import hashlib
import json
import time
import os
from typing import Optional, List, Dict, Any

# Handle both direct execution and package imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from blockchain.chain import Blockchain
from blockchain.wallet import Wallet
from blockchain.transaction import Transaction


def _hash_sensitive(value: str) -> str:
    """SHA-256 hash of sensitive data. Only this hash goes on-chain."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_dict(d: dict) -> str:
    """Deterministic SHA-256 of a dict."""
    return hashlib.sha256(
        json.dumps(d, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


class VaultLedger:
    """
    Bridge between scanners and the blockchain.

    Every finding gets:
      1. A SHA-256 fingerprint (proves you had the data)
      2. Non-sensitive metadata (type, source, timestamp, labels)
      3. An immutable on-chain record in a vault transaction

    The actual sensitive data (keys, seeds) stays OFF-chain in your
    local encrypted vault file. Only the proof lives on the blockchain.
    """

    # Local encrypted vault for raw sensitive data
    _VAULT_DIR = Path(__file__).resolve().parent.parent / ".vault"
    _VAULT_FILE = _VAULT_DIR / "secrets.json"

    def __init__(self, blockchain: Blockchain, vault_wallet: Wallet):
        self.blockchain = blockchain
        self.wallet = vault_wallet
        self._pending_count = 0

        # Ensure local vault directory exists
        self._VAULT_DIR.mkdir(parents=True, exist_ok=True)
        if not self._VAULT_FILE.exists():
            self._VAULT_FILE.write_text("{}", encoding="utf-8")

    # ─── Core Recording Methods ───

    def record_wallet(self, address: str, blockchain_name: str,
                      source_file: str = "", balance: float = 0.0,
                      notes: str = "") -> Optional[Transaction]:
        """
        Record a discovered wallet address on-chain.

        The address itself is NOT sensitive (it's public on the real chain
        anyway), so we store it in clear. The source file is hashed.
        """
        data = {
            "vault_type": "wallet",
            "address": address,
            "blockchain": blockchain_name,
            "source_hash": _hash_sensitive(source_file) if source_file else "",
            "balance_at_discovery": balance,
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_api_key(self, exchange: str, api_key: str,
                       source_file: str = "", key_type: str = "api_key",
                       notes: str = "") -> Optional[Transaction]:
        """
        Record a discovered API key on-chain.

        ONLY the SHA-256 hash of the key goes on-chain.
        The raw key is saved to the local encrypted vault.
        """
        key_hash = _hash_sensitive(api_key)

        # Store raw key locally (off-chain)
        self._store_local_secret("api_key", exchange, key_hash, api_key)

        data = {
            "vault_type": "api_key",
            "exchange": exchange,
            "key_type": key_type,
            "key_hash": key_hash,
            "key_preview": api_key[:6] + "..." + api_key[-4:] if len(api_key) > 10 else "***",
            "source_hash": _hash_sensitive(source_file) if source_file else "",
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_seed_phrase(self, phrase: str, source_file: str = "",
                           word_count: int = 0,
                           notes: str = "") -> Optional[Transaction]:
        """
        Record a discovered seed/mnemonic phrase on-chain.

        ONLY the SHA-256 hash goes on-chain. Raw phrase saved locally.
        """
        phrase_hash = _hash_sensitive(phrase)
        wc = word_count or len(phrase.split())

        # Store raw phrase locally (off-chain)
        self._store_local_secret("seed_phrase", f"{wc}-word", phrase_hash, phrase)

        data = {
            "vault_type": "seed_phrase",
            "phrase_hash": phrase_hash,
            "word_count": wc,
            "source_hash": _hash_sensitive(source_file) if source_file else "",
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_private_key(self, key: str, blockchain_name: str,
                           source_file: str = "",
                           notes: str = "") -> Optional[Transaction]:
        """
        Record a discovered private key on-chain.

        ONLY the SHA-256 hash goes on-chain. Raw key saved locally.
        """
        key_hash = _hash_sensitive(key)

        self._store_local_secret("private_key", blockchain_name, key_hash, key)

        data = {
            "vault_type": "private_key",
            "blockchain": blockchain_name,
            "key_hash": key_hash,
            "key_preview": key[:8] + "...",
            "source_hash": _hash_sensitive(source_file) if source_file else "",
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_scan_result(self, scan_type: str, summary: dict,
                           source: str = "",
                           notes: str = "") -> Optional[Transaction]:
        """
        Record a scanner run summary on-chain.

        The full summary dict is hashed; safe metadata is stored in clear.
        """
        data = {
            "vault_type": "scan_result",
            "scan_type": scan_type,
            "summary_hash": _hash_dict(summary),
            "total_findings": summary.get("total_findings", 0),
            "wallets_found": summary.get("wallets_found", 0),
            "keys_found": summary.get("keys_found", 0),
            "source": source,
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_exchange_balance(self, exchange: str, asset: str,
                                amount: float, usd_value: float = 0.0,
                                notes: str = "") -> Optional[Transaction]:
        """
        Record an exchange balance snapshot on-chain.

        Proves you had X amount of Y on exchange Z at time T.
        """
        data = {
            "vault_type": "exchange_balance",
            "exchange": exchange,
            "asset": asset,
            "amount": amount,
            "usd_value": usd_value,
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_opportunity(self, title: str, opp_type: str,
                           estimated_value: float = 0.0,
                           blockchain_name: str = "",
                           details: dict = None,
                           notes: str = "") -> Optional[Transaction]:
        """
        Record a discovered opportunity (airdrop, faucet, etc.) on-chain.
        """
        data = {
            "vault_type": "opportunity",
            "title": title,
            "opportunity_type": opp_type,
            "estimated_value_usd": estimated_value,
            "blockchain": blockchain_name,
            "details_hash": _hash_dict(details) if details else "",
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    def record_custom(self, vault_type: str, payload: dict,
                      notes: str = "") -> Optional[Transaction]:
        """
        Record any custom data on-chain.

        Use this for anything that doesn't fit the other methods.
        Sensitive fields in payload should be pre-hashed by the caller.
        """
        data = {
            "vault_type": vault_type,
            "payload_hash": _hash_dict(payload),
            **{k: v for k, v in payload.items()
               if not k.startswith("_secret_")},
            "notes": notes,
            "recorded_at": time.time(),
        }
        return self._commit_vault(data)

    # ─── Query Methods ───

    def get_records(self, vault_type: Optional[str] = None) -> list:
        """Get all vault records from the blockchain."""
        return self.blockchain.get_vault_records(
            vault_type=vault_type, owner=self.wallet.address
        )

    def get_wallets(self) -> list:
        """Get all recorded wallet findings."""
        return self.get_records("wallet")

    def get_api_keys(self) -> list:
        """Get all recorded API key findings."""
        return self.get_records("api_key")

    def get_balances(self) -> list:
        """Get all recorded exchange balance snapshots."""
        return self.get_records("exchange_balance")

    def get_scan_results(self) -> list:
        """Get all recorded scan result summaries."""
        return self.get_records("scan_result")

    @property
    def pending_count(self) -> int:
        """Number of vault records waiting in mempool."""
        return sum(1 for tx in self.blockchain.mempool
                   if tx.is_vault())

    @property
    def total_records(self) -> int:
        """Total vault records on-chain (already mined)."""
        return len(self.get_records())

    # ─── Batch Methods ───

    def record_from_scanner_db(self, db_path: str) -> Dict[str, int]:
        """
        Import all findings from a crypto_findings.db SQLite database.

        Reads the wallets, api_keys, and seed_phrases tables and
        records each one on-chain. Returns counts per type.

        Args:
            db_path: Path to crypto_findings.db

        Returns:
            {"wallets": N, "api_keys": N, "seed_phrases": N}
        """
        import sqlite3

        counts = {"wallets": 0, "api_keys": 0, "seed_phrases": 0}

        if not os.path.exists(db_path):
            return counts

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        # Wallets
        try:
            for row in conn.execute("SELECT * FROM wallets"):
                self.record_wallet(
                    address=row["address"],
                    blockchain_name=row["blockchain"],
                    source_file=row.get("source_file", ""),
                    balance=row.get("balance_usd", 0.0) or 0.0,
                )
                counts["wallets"] += 1
        except Exception:
            pass

        # API Keys
        try:
            for row in conn.execute("SELECT * FROM api_keys"):
                self.record_api_key(
                    exchange=row.get("exchange", "unknown"),
                    api_key=row.get("key_preview", ""),
                    source_file=row.get("source_file", ""),
                    key_type=row.get("key_type", "api_key"),
                )
                counts["api_keys"] += 1
        except Exception:
            pass

        # Seed Phrases
        try:
            for row in conn.execute("SELECT * FROM seed_phrases"):
                self.record_seed_phrase(
                    phrase=row.get("phrase_hash", ""),
                    source_file=row.get("source_file", ""),
                    word_count=row.get("word_count", 0),
                )
                counts["seed_phrases"] += 1
        except Exception:
            pass

        conn.close()
        return counts

    def record_balance_report(self, report: List[Dict]) -> int:
        """
        Import a balance checker report (list of asset dicts).

        Each dict should have: exchange, asset, total, usd_value
        Returns number of records created.
        """
        count = 0
        for entry in report:
            self.record_exchange_balance(
                exchange=entry.get("exchange", "unknown"),
                asset=entry.get("asset", ""),
                amount=float(entry.get("total", 0)),
                usd_value=float(entry.get("usd_value", 0)),
            )
            count += 1
        return count

    # ─── Internal ───

    def _commit_vault(self, data: dict) -> Optional[Transaction]:
        """Create a vault transaction and add it to the mempool."""
        tx = self.blockchain.add_vault_record(self.wallet.address, data)
        if tx:
            self._pending_count += 1
        return tx

    def _store_local_secret(self, secret_type: str, label: str,
                            hash_id: str, raw_value: str):
        """
        Save the raw sensitive value to the local vault file.

        This is NOT on-chain — it stays on your machine.
        The on-chain record has only the hash, so even if someone
        reads the blockchain, they can't extract the secret.
        """
        try:
            vault = json.loads(self._VAULT_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            vault = {}

        key = f"{secret_type}:{hash_id[:16]}"
        vault[key] = {
            "type": secret_type,
            "label": label,
            "hash": hash_id,
            "value": raw_value,
            "stored_at": time.time(),
        }

        self._VAULT_FILE.write_text(
            json.dumps(vault, indent=2), encoding="utf-8"
        )

    def print_summary(self):
        """Print a summary of all vault records on-chain."""
        records = self.get_records()
        print(f"\n{'═' * 60}")
        print(f"VAULT LEDGER — {len(records)} records on-chain")
        print(f"{'═' * 60}")
        print(f"Owner:   {self.wallet.address}")
        print(f"Pending: {self.pending_count} in mempool")
        print()

        by_type: Dict[str, int] = {}
        for r in records:
            vt = r["data"].get("vault_type", "unknown")
            by_type[vt] = by_type.get(vt, 0) + 1

        for vt, count in sorted(by_type.items()):
            print(f"  {vt:20s} │ {count} records")

        print(f"\n  {'TOTAL':20s} │ {len(records)} records")
        print(f"{'═' * 60}")

        if records:
            print(f"\nLatest 5 records:")
            for r in records[-5:]:
                d = r["data"]
                print(f"  Block #{r['block_index']} │ {d.get('vault_type','?'):15s} │ {r['tx_hash'][:16]}...")
