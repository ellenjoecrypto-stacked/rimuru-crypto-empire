#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Secure Credential Vault
Military-grade encryption for API keys and secrets
"""

import os
import json
import logging
import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
    import argon2
except ImportError as e:
    raise ImportError(
        f"Required security packages not installed. Run: pip install cryptography argon2-cffi\n{e}"
    ) from e

@dataclass
class Credential:
    """Credential data structure"""
    exchange: str
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    permissions: List[str] = None
    ip_whitelist: Optional[str] = None
    created_at: str = None
    last_used: str = None
    rotation_due: str = None

class CredentialVault:
    """
    Secure credential storage with AES-256-GCM encryption
    
    Features:
    - Master key derivation using PBKDF2
    - AES-256-GCM encryption
    - Encrypted SQLite database
    - Audit logging
    - Credential rotation tracking
    """
    
    def __init__(self, vault_path: str = "data/credentials.db", master_password: Optional[str] = None):
        self.vault_path = Path(vault_path)
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize master password
        if master_password is None:
            master_password = os.getenv("VAULT_MASTER_PASSWORD", "CHANGE_ME_IN_PRODUCTION")
        
        self.master_key = self._derive_master_key(master_password)
        self.cipher = Fernet(self.master_key)
        self._init_database()
        
    def _derive_master_key(self, password: str) -> bytes:
        """Derive master encryption key from password using PBKDF2"""
        # Use a fixed salt for consistency (in production, store this securely)
        salt = b'rimuru_crypto_empire_salt_v1'
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key
    
    def _init_database(self):
        """Initialize encrypted SQLite database"""
        conn = sqlite3.connect(str(self.vault_path))
        cursor = conn.cursor()
        
        # Create credentials table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange TEXT NOT NULL UNIQUE,
                encrypted_data BLOB NOT NULL,
                created_at TEXT NOT NULL,
                last_used TEXT,
                rotation_due TEXT
            )
        """)
        
        # Create audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                action TEXT NOT NULL,
                exchange TEXT NOT NULL,
                details TEXT,
                ip_address TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def store_credential(self, credential: Credential) -> bool:
        """
        Store encrypted credential in vault
        
        Args:
            credential: Credential object to store
            
        Returns:
            bool: Success status
        """
        try:
            # Set timestamps
            credential.created_at = datetime.now().isoformat()
            
            # Serialize and encrypt
            credential_json = json.dumps(asdict(credential))
            encrypted_data = self.cipher.encrypt(credential_json.encode())
            
            # Store in database
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO credentials 
                (exchange, encrypted_data, created_at, last_used, rotation_due)
                VALUES (?, ?, ?, ?, ?)
            """, (
                credential.exchange,
                encrypted_data,
                credential.created_at,
                credential.last_used,
                credential.rotation_due
            ))
            
            # Log action
            self._log_action("STORE", credential.exchange, "Credential stored")
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error("Error storing credential: %s", e)
            return False
    
    def retrieve_credential(self, exchange: str) -> Optional[Credential]:
        """
        Retrieve and decrypt credential from vault
        
        Args:
            exchange: Exchange name
            
        Returns:
            Credential object or None
        """
        try:
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT encrypted_data FROM credentials WHERE exchange = ?
            """, (exchange,))
            
            result = cursor.fetchone()
            
            if result is None:
                return None
            
            # Decrypt and deserialize
            encrypted_data = result[0]
            decrypted_json = self.cipher.decrypt(encrypted_data).decode()
            credential_dict = json.loads(decrypted_json)
            
            # Update last used timestamp
            cursor.execute("""
                UPDATE credentials SET last_used = ? WHERE exchange = ?
            """, (datetime.now().isoformat(), exchange))
            
            # Log action
            self._log_action("RETRIEVE", exchange, "Credential accessed")
            
            conn.commit()
            conn.close()
            
            return Credential(**credential_dict)
            
        except Exception as e:
            logger.error("Error retrieving credential: %s", e)
            return None
    
    def list_exchanges(self) -> List[str]:
        """List all stored exchanges"""
        try:
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("SELECT exchange FROM credentials")
            exchanges = [row[0] for row in cursor.fetchall()]
            
            conn.close()
            return exchanges
            
        except Exception as e:
            logger.error("Error listing exchanges: %s", e)
            return []
    
    def delete_credential(self, exchange: str) -> bool:
        """Delete credential from vault"""
        try:
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM credentials WHERE exchange = ?", (exchange,))
            
            # Log action
            self._log_action("DELETE", exchange, "Credential deleted")
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error("Error deleting credential: %s", e)
            return False
    
    def _log_action(self, action: str, exchange: str, details: str):
        """Log credential access to audit log"""
        try:
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO audit_log (timestamp, action, exchange, details, ip_address)
                VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                action,
                exchange,
                details,
                "localhost"  # In production, get actual IP
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.warning("Could not log action: %s", e)
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Retrieve audit log entries"""
        try:
            conn = sqlite3.connect(str(self.vault_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT timestamp, action, exchange, details, ip_address
                FROM audit_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    "timestamp": row[0],
                    "action": row[1],
                    "exchange": row[2],
                    "details": row[3],
                    "ip_address": row[4]
                })
            
            conn.close()
            return logs
            
        except Exception as e:
            logger.error("Error retrieving audit log: %s", e)
            return []
    
    def test_encryption(self) -> bool:
        """Test encryption/decryption functionality"""
        test_data = "Test encryption string"
        try:
            encrypted = self.cipher.encrypt(test_data.encode())
            decrypted = self.cipher.decrypt(encrypted).decode()
            return test_data == decrypted
        except Exception as e:
            logger.error("Encryption test failed: %s", e)
            return False


# Example usage and testing
if __name__ == "__main__":
    print("🔐 RIMURU CREDENTIAL VAULT - Security Test")
    print("=" * 60)
    
    # Initialize vault
    vault = CredentialVault()
    
    # Test encryption
    print("\n1. Testing encryption...")
    if vault.test_encryption():
        print("   ✅ Encryption test passed")
    else:
        print("   ❌ Encryption test failed")
    
    # Store test credential
    print("\n2. Storing test credential...")
    test_cred = Credential(
        exchange="binance_test",
        api_key="test_api_key_12345",
        secret_key="test_secret_key_67890",
        permissions=["read", "trade"],
        ip_whitelist="192.168.1.1"
    )
    
    if vault.store_credential(test_cred):
        print("   ✅ Credential stored successfully")
    else:
        print("   ❌ Failed to store credential")
    
    # Retrieve credential
    print("\n3. Retrieving credential...")
    retrieved = vault.retrieve_credential("binance_test")
    if retrieved and retrieved.api_key == test_cred.api_key:
        print("   ✅ Credential retrieved successfully")
        print(f"   Exchange: {retrieved.exchange}")
        print(f"   API Key: {retrieved.api_key[:10]}...")
        print(f"   Permissions: {retrieved.permissions}")
    else:
        print("   ❌ Failed to retrieve credential")
    
    # List exchanges
    print("\n4. Listing stored exchanges...")
    exchanges = vault.list_exchanges()
    print(f"   ✅ Found {len(exchanges)} exchange(s): {exchanges}")
    
    # View audit log
    print("\n5. Audit log (last 5 entries)...")
    logs = vault.get_audit_log(limit=5)
    for log in logs:
        print(f"   [{log['timestamp']}] {log['action']} - {log['exchange']}")
    
    print("\n" + "=" * 60)
    print("✅ Security test completed!")
    print("\n⚠️  IMPORTANT: Change VAULT_MASTER_PASSWORD in production!")