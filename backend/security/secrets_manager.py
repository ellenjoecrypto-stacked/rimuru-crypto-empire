"""
Secure Secrets Management System for Rimuru Crypto Empire
Implements AES-256-GCM encryption with Argon2id key derivation
"""

import os
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict
from enum import Enum
import threading

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import logging

logger = logging.getLogger(__name__)


class SecretType(Enum):
    """Types of secrets stored in vault"""
    API_KEY = "api_key"
    PRIVATE_KEY = "private_key"
    WALLET_SEED = "wallet_seed"
    MASTER_PASSWORD = "master_password"
    WEBHOOK_SECRET = "webhook_secret"


@dataclass
class Secret:
    """Represents an encrypted secret"""
    id: str
    name: str
    type: SecretType
    encrypted_value: bytes
    iv: bytes
    auth_tag: bytes
    salt: bytes
    created_at: str
    modified_at: str
    created_by: str
    access_count: int = 0
    last_accessed: Optional[str] = None


@dataclass
class VaultMetadata:
    """Metadata for encrypted vault"""
    version: str = "1.0"
    created_at: str = ""
    modified_at: str = ""
    key_rotation_date: str = ""
    total_secrets: int = 0


class SecretsManager:
    """
    Secure secrets management with AES-256-GCM encryption
    
    Features:
    - AES-256-GCM authenticated encryption
    - Argon2id key derivation (memory-hard)
    - Per-secret unique IVs and salts
    - Access logging
    - Automatic key rotation support
    - Master password protection
    """
    
    # Argon2id parameters (OWASP recommendations)
    ARGON2_TIME_COST = 3  # iterations
    ARGON2_MEMORY_COST = 65_540  # KiB (~64 MB)
    ARGON2_PARALLELISM = 4
    
    def __init__(self, vault_path: str):
        """Initialize secrets manager
        
        Args:
            vault_path: Path to encrypted vault file
        """
        self.vault_path = vault_path
        self.secrets: Dict[str, Secret] = {}
        self.metadata = VaultMetadata()
        self.master_key: Optional[bytes] = None
        self.is_unlocked = False
        self._lock = threading.RLock()
        
        # Load vault if exists
        if os.path.exists(vault_path):
            self._load_vault()
    
    def create_vault(self, master_password: str) -> bool:
        """Create new encrypted vault
        
        Args:
            master_password: Master password to protect vault
            
        Returns:
            True if vault created successfully
        """
        with self._lock:
            try:
                # Generate salt for key derivation
                vault_salt = secrets.token_bytes(32)
                
                # Derive master key from password
                self.master_key = self._derive_key(
                    master_password,
                    vault_salt,
                    salt_iterations=100_000
                )
                
                # Initialize metadata
                self.metadata = VaultMetadata(
                    version="1.0",
                    created_at=datetime.utcnow().isoformat() + "Z",
                    modified_at=datetime.utcnow().isoformat() + "Z",
                    key_rotation_date=datetime.utcnow().isoformat() + "Z"
                )
                
                self.secrets = {}
                self.is_unlocked = True
                
                # Save vault
                self._save_vault(vault_salt)
                logger.info(f"Vault created: {self.vault_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error creating vault: {e}")
                self.is_unlocked = False
                return False
    
    def unlock(self, master_password: str) -> bool:
        """Unlock vault with master password
        
        Args:
            master_password: Master password
            
        Returns:
            True if vault unlocked successfully
        """
        with self._lock:
            try:
                if not os.path.exists(self.vault_path):
                    logger.error("Vault file not found")
                    return False
                
                with open(self.vault_path, 'rb') as f:
                    vault_data = json.loads(f.read())
                
                # Extract salt and derive key
                vault_salt = bytes.fromhex(vault_data['salt'])
                self.master_key = self._derive_key(
                    master_password,
                    vault_salt,
                    salt_iterations=100_000
                )
                
                # Try to decrypt metadata to verify password
                metadata_encrypted = bytes.fromhex(vault_data['metadata_encrypted'])
                metadata_iv = bytes.fromhex(vault_data['metadata_iv'])
                metadata_tag = bytes.fromhex(vault_data['metadata_tag'])
                
                try:
                    metadata_json = self._decrypt(
                        metadata_encrypted,
                        metadata_iv,
                        metadata_tag,
                        self.master_key
                    )
                    self.metadata = VaultMetadata(**json.loads(metadata_json))
                except Exception:
                    logger.error("Invalid master password")
                    self.is_unlocked = False
                    return False
                
                # Load secrets
                self.secrets = {}
                if 'secrets' in vault_data:
                    for secret_data in vault_data['secrets']:
                        secret = Secret(
                            id=secret_data['id'],
                            name=secret_data['name'],
                            type=SecretType(secret_data['type']),
                            encrypted_value=bytes.fromhex(secret_data['encrypted_value']),
                            iv=bytes.fromhex(secret_data['iv']),
                            auth_tag=bytes.fromhex(secret_data['auth_tag']),
                            salt=bytes.fromhex(secret_data['salt']),
                            created_at=secret_data['created_at'],
                            modified_at=secret_data['modified_at'],
                            created_by=secret_data['created_by'],
                            access_count=secret_data.get('access_count', 0),
                            last_accessed=secret_data.get('last_accessed')
                        )
                        self.secrets[secret.id] = secret
                
                self.is_unlocked = True
                logger.info(f"Vault unlocked successfully. Loaded {len(self.secrets)} secrets")
                return True
                
            except Exception as e:
                logger.error(f"Error unlocking vault: {e}")
                self.is_unlocked = False
                return False
    
    def add_secret(self, name: str, value: str, secret_type: SecretType,
                   created_by: str) -> Optional[str]:
        """Add new secret to vault
        
        Args:
            name: Human-readable name
            value: Secret value
            secret_type: Type of secret
            created_by: Operator who created it
            
        Returns:
            Secret ID if successful, None otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return None
        
        with self._lock:
            try:
                # Generate unique ID
                secret_id = f"{secret_type.value}_{secrets.token_hex(8)}"
                
                # Generate encryption parameters
                secret_salt = secrets.token_bytes(32)
                secret_iv = secrets.token_bytes(12)
                
                # Derive per-secret key
                secret_key = self._derive_key(value, secret_salt)
                
                # Encrypt secret
                encrypted_value, auth_tag = self._encrypt(value, secret_iv, secret_key)
                
                # Create secret object
                now = datetime.utcnow().isoformat() + "Z"
                secret = Secret(
                    id=secret_id,
                    name=name,
                    type=secret_type,
                    encrypted_value=encrypted_value,
                    iv=secret_iv,
                    auth_tag=auth_tag,
                    salt=secret_salt,
                    created_at=now,
                    modified_at=now,
                    created_by=created_by
                )
                
                self.secrets[secret_id] = secret
                self.metadata.total_secrets = len(self.secrets)
                self.metadata.modified_at = now
                self._save_vault()
                
                logger.info(f"Secret added: {secret_id} ({name})")
                return secret_id
                
            except Exception as e:
                logger.error(f"Error adding secret: {e}")
                return None
    
    def get_secret(self, secret_id: str, operator: str) -> Optional[str]:
        """Retrieve and decrypt secret
        
        Args:
            secret_id: ID of secret to retrieve
            operator: Operator retrieving secret (for audit)
            
        Returns:
            Decrypted secret value if successful, None otherwise
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return None
        
        with self._lock:
            try:
                if secret_id not in self.secrets:
                    logger.error(f"Secret not found: {secret_id}")
                    return None
                
                secret = self.secrets[secret_id]
                
                # Derive per-secret key
                secret_key = self._derive_key(
                    self.master_key.hex(),  # Use master key as base
                    secret.salt
                )
                
                # Decrypt secret
                decrypted_value = self._decrypt(
                    secret.encrypted_value,
                    secret.iv,
                    secret.auth_tag,
                    secret_key
                )
                
                # Update access log
                secret.access_count += 1
                secret.last_accessed = datetime.utcnow().isoformat() + "Z"
                self._save_vault()
                
                logger.info(f"Secret retrieved: {secret_id} by {operator}")
                return decrypted_value
                
            except Exception as e:
                logger.error(f"Error retrieving secret: {e}")
                return None
    
    def list_secrets(self) -> List[Dict]:
        """List all secrets (without values)
        
        Returns:
            List of secret metadata
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return []
        
        with self._lock:
            return [
                {
                    'id': s.id,
                    'name': s.name,
                    'type': s.type.value,
                    'created_at': s.created_at,
                    'modified_at': s.modified_at,
                    'created_by': s.created_by,
                    'access_count': s.access_count,
                    'last_accessed': s.last_accessed
                }
                for s in self.secrets.values()
            ]
    
    def delete_secret(self, secret_id: str, operator: str) -> bool:
        """Delete secret from vault
        
        Args:
            secret_id: ID of secret to delete
            operator: Operator performing deletion
            
        Returns:
            True if deleted successfully
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        with self._lock:
            try:
                if secret_id not in self.secrets:
                    logger.error(f"Secret not found: {secret_id}")
                    return False
                
                secret = self.secrets[secret_id]
                del self.secrets[secret_id]
                self.metadata.total_secrets = len(self.secrets)
                self.metadata.modified_at = datetime.utcnow().isoformat() + "Z"
                self._save_vault()
                
                logger.info(f"Secret deleted: {secret_id} by {operator}")
                return True
                
            except Exception as e:
                logger.error(f"Error deleting secret: {e}")
                return False
    
    def rotate_keys(self, new_master_password: str) -> bool:
        """Rotate vault master key
        
        Args:
            new_master_password: New master password
            
        Returns:
            True if rotation successful
        """
        if not self.is_unlocked:
            logger.error("Vault is locked")
            return False
        
        with self._lock:
            try:
                # Generate new salt
                new_vault_salt = secrets.token_bytes(32)
                
                # Derive new master key
                new_master_key = self._derive_key(
                    new_master_password,
                    new_vault_salt,
                    salt_iterations=100_000
                )
                
                # Update metadata
                self.metadata.modified_at = datetime.utcnow().isoformat() + "Z"
                self.metadata.key_rotation_date = self.metadata.modified_at
                
                # Update master key
                self.master_key = new_master_key
                
                # Save with new key
                self._save_vault(new_vault_salt)
                logger.info("Vault keys rotated successfully")
                return True
                
            except Exception as e:
                logger.error(f"Error rotating keys: {e}")
                return False
    
    def lock(self) -> None:
        """Lock vault (clear master key from memory)"""
        with self._lock:
            self.is_unlocked = False
            self.master_key = None
            logger.info("Vault locked")
    
    # Private methods
    
    def _derive_key(self, password: str, salt: bytes,
                   salt_iterations: int = 100_000) -> bytes:
        """Derive encryption key from password using Argon2id
        
        Args:
            password: Password to derive from
            salt: Salt for key derivation
            salt_iterations: Pre-hash iterations (for master password)
            
        Returns:
            Derived encryption key (32 bytes)
        """
        # Pre-hash password for PBKDF2 compatibility
        password_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            salt_iterations
        )
        
        # Derive key using Argon2id
        kdf = Argon2id(
            algorithm=hashes.SHA256(),
            time_cost=self.ARGON2_TIME_COST,
            memory_cost=self.ARGON2_MEMORY_COST,
            parallelism=self.ARGON2_PARALLELISM,
            salt=salt,
            length=32,
            backend=default_backend()
        )
        
        return kdf.derive(password_hash)
    
    def _encrypt(self, plaintext: str, iv: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """Encrypt data using AES-256-GCM
        
        Args:
            plaintext: Data to encrypt
            iv: Initialization vector
            key: Encryption key
            
        Returns:
            Tuple of (ciphertext, auth_tag)
        """
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode(), None)
        
        # Extract auth tag (last 16 bytes)
        auth_tag = ciphertext[-16:]
        encrypted_data = ciphertext[:-16]
        
        return encrypted_data, auth_tag
    
    def _decrypt(self, ciphertext: bytes, iv: bytes, auth_tag: bytes,
                key: bytes) -> str:
        """Decrypt data using AES-256-GCM
        
        Args:
            ciphertext: Encrypted data
            iv: Initialization vector
            auth_tag: Authentication tag
            key: Decryption key
            
        Returns:
            Decrypted plaintext
        """
        aesgcm = AESGCM(key)
        
        # Reconstruct full ciphertext with auth tag
        full_ciphertext = ciphertext + auth_tag
        
        plaintext = aesgcm.decrypt(iv, full_ciphertext, None)
        return plaintext.decode()
    
    def _save_vault(self, vault_salt: Optional[bytes] = None) -> None:
        """Save encrypted vault to disk
        
        Args:
            vault_salt: Vault salt (if provided, save to file)
        """
        if not self.master_key:
            raise ValueError("Master key not set")
        
        # Encrypt metadata
        metadata_iv = secrets.token_bytes(12)
        metadata_json = json.dumps(asdict(self.metadata))
        metadata_encrypted, metadata_tag = self._encrypt(
            metadata_json,
            metadata_iv,
            self.master_key
        )
        
        # If no salt provided, reload from file
        if not vault_salt:
            with open(self.vault_path, 'rb') as f:
                vault_data = json.loads(f.read())
            vault_salt = bytes.fromhex(vault_data['salt'])
        
        # Build vault data
        vault_data = {
            'version': '1.0',
            'salt': vault_salt.hex(),
            'metadata_encrypted': metadata_encrypted.hex(),
            'metadata_iv': metadata_iv.hex(),
            'metadata_tag': metadata_tag.hex(),
            'secrets': [
                {
                    'id': s.id,
                    'name': s.name,
                    'type': s.type.value,
                    'encrypted_value': s.encrypted_value.hex(),
                    'iv': s.iv.hex(),
                    'auth_tag': s.auth_tag.hex(),
                    'salt': s.salt.hex(),
                    'created_at': s.created_at,
                    'modified_at': s.modified_at,
                    'created_by': s.created_by,
                    'access_count': s.access_count,
                    'last_accessed': s.last_accessed
                }
                for s in self.secrets.values()
            ]
        }
        
        # Create directory if needed
        os.makedirs(os.path.dirname(self.vault_path), exist_ok=True)
        
        # Write vault file
        with open(self.vault_path, 'w') as f:
            f.write(json.dumps(vault_data, indent=2))
        
        # Secure file permissions
        os.chmod(self.vault_path, 0o600)
    
    def _load_vault(self) -> None:
        """Load vault metadata from disk"""
        try:
            with open(self.vault_path, 'rb') as f:
                vault_data = json.loads(f.read())
            logger.info(f"Vault loaded: {self.vault_path}")
        except Exception as e:
            logger.error(f"Error loading vault: {e}")


# CLI Interface
if __name__ == "__main__":
    import sys
    
    vault_manager = SecretsManager("vault.enc")
    
    if len(sys.argv) < 2:
        print("Usage: secrets_manager.py <command> [args]")
        print("Commands:")
        print("  create <password>              - Create new vault")
        print("  unlock <password>              - Unlock vault")
        print("  add <name> <value> <type>     - Add secret")
        print("  get <secret_id>                - Retrieve secret")
        print("  list                           - List all secrets")
        print("  delete <secret_id>             - Delete secret")
        print("  rotate <new_password>          - Rotate keys")
        print("  lock                           - Lock vault")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        password = sys.argv[2]
        success = vault_manager.create_vault(password)
        print(f"Vault created: {success}")
    
    elif command == "unlock":
        password = sys.argv[2]
        success = vault_manager.unlock(password)
        print(f"Vault unlocked: {success}")
    
    elif command == "add":
        name, value, secret_type = sys.argv[2], sys.argv[3], sys.argv[4]
        secret_id = vault_manager.add_secret(
            name, value, SecretType(secret_type), "admin"
        )
        print(f"Secret added: {secret_id}")
    
    elif command == "get":
        secret_id = sys.argv[2]
        value = vault_manager.get_secret(secret_id, "admin")
        print(f"Secret value: {value}")
    
    elif command == "list":
        secrets = vault_manager.list_secrets()
        print(json.dumps(secrets, indent=2))
    
    elif command == "delete":
        secret_id = sys.argv[2]
        success = vault_manager.delete_secret(secret_id, "admin")
        print(f"Secret deleted: {success}")
    
    elif command == "rotate":
        new_password = sys.argv[2]
        success = vault_manager.rotate_keys(new_password)
        print(f"Keys rotated: {success}")
    
    elif command == "lock":
        vault_manager.lock()
        print("Vault locked")
