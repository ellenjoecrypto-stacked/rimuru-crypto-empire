#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Interactive Credential Manager
Secure management of API keys, wallets, and secrets with encryption
"""

import os
import sys
import json
import getpass
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hmac

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Installing cryptography library...")
    os.system("pip install cryptography")
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend


class CredentialType(Enum):
    """Types of credentials"""
    EXCHANGE_API_KEY = "Exchange API Key"
    EXCHANGE_API_SECRET = "Exchange API Secret"
    WALLET_PRIVATE_KEY = "Wallet Private Key"
    WALLET_SEED = "Wallet Seed Phrase"
    DATABASE_PASSWORD = "Database Password"
    API_TOKEN = "API Token"
    WEBHOOK_SECRET = "Webhook Secret"
    JWT_SECRET = "JWT Secret"
    OTHER = "Other Secret"


@dataclass
class Credential:
    """Credential data structure"""
    name: str
    credential_type: str
    value: str
    description: str = ""
    exchange: str = ""
    created_at: str = ""
    last_used: str = ""
    metadata: Dict = None
    
    def __post_init__(self):
        if self.created_at == "":
            self.created_at = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


class CredentialManager:
    """Manages encrypted credentials"""
    
    def __init__(self, vault_path: str = "_SENSITIVE/VAULT_DATA"):
        self.vault_path = Path(vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)
        
        self.vault_file = self.vault_path / "credentials_vault.enc"
        self.master_key_file = self.vault_path / ".master_key"
        self.credentials: List[Credential] = []
        self.cipher = None
        self.master_password = ""
        
    def _derive_key(self, password: str, salt: bytes = None) -> tuple:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode())
        return Fernet(base64_encode(key)), salt
    
    def _setup_encryption(self, password: str) -> bool:
        """Set up encryption with password"""
        try:
            self.cipher, salt = self._derive_key(password)
            self.master_password = password
            
            # Store salt for later use (salt is not secret)
            salt_file = self.vault_path / ".salt"
            with open(salt_file, 'wb') as f:
                f.write(salt)
            
            return True
        except Exception as e:
            print(f"❌ Error setting up encryption: {e}")
            return False
    
    def _load_encryption(self, password: str) -> bool:
        """Load encryption with existing salt"""
        try:
            salt_file = self.vault_path / ".salt"
            if not salt_file.exists():
                return self._setup_encryption(password)
            
            with open(salt_file, 'rb') as f:
                salt = f.read()
            
            self.cipher, _ = self._derive_key(password, salt)
            self.master_password = password
            return True
        except Exception as e:
            print(f"❌ Error loading encryption: {e}")
            return False
    
    def encrypt_credential(self, credential: Credential) -> str:
        """Encrypt a credential"""
        if not self.cipher:
            print("❌ Encryption not initialized!")
            return ""
        
        try:
            cred_json = json.dumps(asdict(credential))
            encrypted = self.cipher.encrypt(cred_json.encode())
            return encrypted.decode()
        except Exception as e:
            print(f"❌ Encryption error: {e}")
            return ""
    
    def decrypt_credential(self, encrypted_data: str) -> Optional[Credential]:
        """Decrypt a credential"""
        if not self.cipher:
            print("❌ Encryption not initialized!")
            return None
        
        try:
            decrypted = self.cipher.decrypt(encrypted_data.encode())
            cred_dict = json.loads(decrypted.decode())
            return Credential(**cred_dict)
        except Exception as e:
            print(f"❌ Decryption error: {e}")
            return None
    
    def add_credential(self, name: str, cred_type: str, value: str, 
                      description: str = "", exchange: str = "") -> bool:
        """Add a new credential"""
        try:
            # Check for duplicates
            if any(c.name.lower() == name.lower() for c in self.credentials):
                print(f"❌ Credential '{name}' already exists!")
                return False
            
            credential = Credential(
                name=name,
                credential_type=cred_type,
                value=value,
                description=description,
                exchange=exchange
            )
            
            self.credentials.append(credential)
            print(f"✅ Added credential: {name}")
            return True
        except Exception as e:
            print(f"❌ Error adding credential: {e}")
            return False
    
    def save_vault(self) -> bool:
        """Save all credentials to encrypted vault file"""
        try:
            vault_data = {
                "credentials": [asdict(c) for c in self.credentials],
                "created_at": datetime.now().isoformat(),
                "count": len(self.credentials)
            }
            
            vault_json = json.dumps(vault_data, indent=2)
            encrypted = self.cipher.encrypt(vault_json.encode())
            
            with open(self.vault_file, 'wb') as f:
                f.write(encrypted)
            
            print(f"✅ Vault saved ({len(self.credentials)} credentials)")
            return True
        except Exception as e:
            print(f"❌ Error saving vault: {e}")
            return False
    
    def load_vault(self) -> bool:
        """Load credentials from encrypted vault file"""
        try:
            if not self.vault_file.exists():
                print("ℹ️  No vault file found. Starting fresh.")
                return True
            
            with open(self.vault_file, 'rb') as f:
                encrypted = f.read()
            
            decrypted = self.cipher.decrypt(encrypted)
            vault_data = json.loads(decrypted.decode())
            
            self.credentials = [
                Credential(**cred) for cred in vault_data['credentials']
            ]
            
            print(f"✅ Vault loaded ({len(self.credentials)} credentials)")
            return True
        except Exception as e:
            print(f"❌ Error loading vault: {e}")
            return False
    
    def list_credentials(self, show_values: bool = False) -> None:
        """List all credentials"""
        if not self.credentials:
            print("ℹ️  No credentials stored yet.")
            return
        
        print(f"\n{'='*80}")
        print(f"📋 CREDENTIALS ({len(self.credentials)} total)")
        print(f"{'='*80}\n")
        
        for i, cred in enumerate(self.credentials, 1):
            print(f"{i}. {cred.name}")
            print(f"   Type: {cred.credential_type}")
            if cred.exchange:
                print(f"   Exchange: {cred.exchange}")
            if cred.description:
                print(f"   Description: {cred.description}")
            print(f"   Created: {cred.created_at[:10]}")
            if show_values:
                value_preview = cred.value[:20] + "..." if len(cred.value) > 20 else cred.value
                print(f"   Value: {value_preview}")
            print()
    
    def get_credential(self, name: str) -> Optional[str]:
        """Get credential value by name"""
        for cred in self.credentials:
            if cred.name.lower() == name.lower():
                return cred.value
        return None
    
    def delete_credential(self, name: str) -> bool:
        """Delete a credential"""
        for i, cred in enumerate(self.credentials):
            if cred.name.lower() == name.lower():
                self.credentials.pop(i)
                print(f"✅ Deleted credential: {name}")
                return True
        
        print(f"❌ Credential '{name}' not found!")
        return False
    
    def update_credential(self, name: str, value: str) -> bool:
        """Update a credential value"""
        for cred in self.credentials:
            if cred.name.lower() == name.lower():
                cred.value = value
                cred.last_used = datetime.now().isoformat()
                print(f"✅ Updated credential: {name}")
                return True
        
        print(f"❌ Credential '{name}' not found!")
        return False


def base64_encode(data: bytes) -> bytes:
    """Encode bytes to base64"""
    import base64
    return base64.urlsafe_b64encode(data)


class InteractiveMenu:
    """Interactive menu system"""
    
    def __init__(self, manager: CredentialManager):
        self.manager = manager
    
    def clear_screen(self):
        """Clear screen"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self, title: str):
        """Print header"""
        print(f"\n{'='*80}")
        print(f"  🔒 {title}")
        print(f"{'='*80}\n")
    
    def print_menu(self, options: Dict[str, str]):
        """Print menu options"""
        for key, value in options.items():
            print(f"  {key}. {value}")
        print()
    
    def get_choice(self, prompt: str = "Enter your choice: ") -> str:
        """Get user choice"""
        return input(prompt).strip().lower()
    
    def add_credential_interactive(self):
        """Interactive credential addition"""
        self.print_header("Add New Credential")
        
        print("Select credential type:")
        for i, ctype in enumerate(CredentialType, 1):
            print(f"  {i}. {ctype.value}")
        print()
        
        type_choice = input("Enter number (1-9): ").strip()
        try:
            cred_type = list(CredentialType)[int(type_choice) - 1]
        except (ValueError, IndexError):
            print("❌ Invalid choice!")
            return
        
        name = input("Credential name (e.g., 'Binance API Key'): ").strip()
        if not name:
            print("❌ Name required!")
            return
        
        description = input("Description (optional): ").strip()
        exchange = input("Exchange name (optional): ").strip()
        
        print("\n⚠️  Enter the secret value:")
        print("   (This will NOT be echoed to screen for security)")
        value = getpass.getpass("Value: ").strip()
        
        if not value:
            print("❌ Value required!")
            return
        
        confirm = getpass.getpass("Confirm value: ").strip()
        if value != confirm:
            print("❌ Values don't match!")
            return
        
        if self.manager.add_credential(
            name=name,
            cred_type=cred_type.value,
            value=value,
            description=description,
            exchange=exchange
        ):
            self.manager.save_vault()
    
    def view_credential(self):
        """View a specific credential"""
        self.print_header("View Credential")
        self.manager.list_credentials(show_values=False)
        
        name = input("Enter credential name to view: ").strip()
        value = self.manager.get_credential(name)
        
        if value:
            print(f"\n✅ Credential: {name}")
            print(f"Value: {value}\n")
            input("Press Enter to continue (value will be hidden)...")
        else:
            print(f"❌ Credential '{name}' not found!")
    
    def delete_credential(self):
        """Delete a credential"""
        self.print_header("Delete Credential")
        self.manager.list_credentials(show_values=False)
        
        name = input("Enter credential name to delete: ").strip()
        confirm = input(f"Are you sure you want to delete '{name}'? (yes/no): ").strip().lower()
        
        if confirm == 'yes':
            if self.manager.delete_credential(name):
                self.manager.save_vault()
        else:
            print("❌ Deletion cancelled.")
    
    def export_vault_backup(self):
        """Export encrypted vault backup"""
        self.print_header("Export Vault Backup")
        
        backup_name = input("Backup filename (without extension): ").strip()
        if not backup_name:
            print("❌ Name required!")
            return
        
        backup_file = self.manager.vault_path / f"{backup_name}.vault.bak"
        
        try:
            import shutil
            shutil.copy(self.manager.vault_file, backup_file)
            print(f"✅ Backup created: {backup_file}")
        except Exception as e:
            print(f"❌ Error creating backup: {e}")
    
    def show_statistics(self):
        """Show vault statistics"""
        self.print_header("Vault Statistics")
        
        print(f"Total Credentials: {len(self.manager.credentials)}")
        print(f"Vault Location: {self.manager.vault_file}")
        print(f"Vault Size: {self.manager.vault_file.stat().st_size if self.manager.vault_file.exists() else 0} bytes")
        print(f"Created At: {self.manager.credentials[0].created_at[:10] if self.manager.credentials else 'N/A'}")
        print()
        
        if self.manager.credentials:
            types = {}
            for cred in self.manager.credentials:
                types[cred.credential_type] = types.get(cred.credential_type, 0) + 1
            
            print("Credentials by Type:")
            for ctype, count in types.items():
                print(f"  • {ctype}: {count}")
    
    def main_menu(self):
        """Main menu loop"""
        while True:
            self.clear_screen()
            self.print_header("CREDENTIAL MANAGER - Main Menu")
            
            options = {
                '1': 'Add New Credential',
                '2': 'View All Credentials',
                '3': 'View Specific Credential',
                '4': 'Update Credential',
                '5': 'Delete Credential',
                '6': 'Export Backup',
                '7': 'Statistics',
                '8': 'Exit'
            }
            
            self.print_menu(options)
            choice = self.get_choice("Enter your choice: ")
            
            if choice == '1':
                self.add_credential_interactive()
                input("\nPress Enter to continue...")
            elif choice == '2':
                self.print_header("All Credentials")
                self.manager.list_credentials(show_values=False)
                input("Press Enter to continue...")
            elif choice == '3':
                self.view_credential()
            elif choice == '4':
                self.print_header("Update Credential")
                self.manager.list_credentials(show_values=False)
                name = input("Enter credential name: ").strip()
                print("\n⚠️  Enter new value (will not be echoed):")
                new_value = getpass.getpass("New value: ").strip()
                confirm = getpass.getpass("Confirm value: ").strip()
                if new_value == confirm:
                    if self.manager.update_credential(name, new_value):
                        self.manager.save_vault()
                else:
                    print("❌ Values don't match!")
                input("\nPress Enter to continue...")
            elif choice == '5':
                self.delete_credential()
                input("\nPress Enter to continue...")
            elif choice == '6':
                self.export_vault_backup()
                input("\nPress Enter to continue...")
            elif choice == '7':
                self.show_statistics()
                input("\nPress Enter to continue...")
            elif choice == '8':
                print("\n✅ Goodbye!\n")
                sys.exit(0)
            else:
                print("❌ Invalid choice!")
                input("\nPress Enter to continue...")


def main():
    """Main function"""
    print("\n" + "="*80)
    print("  🔐 RIMURU CRYPTO EMPIRE - CREDENTIAL MANAGER")
    print("="*80 + "\n")
    
    # Initialize manager
    manager = CredentialManager()
    
    # Get or create master password
    print("🔑 Master Password Setup\n")
    if manager.vault_file.exists():
        print("Vault file found. Initializing with existing encryption...\n")
        while True:
            password = getpass.getpass("Enter master password: ").strip()
            if manager._load_encryption(password):
                if manager.load_vault():
                    break
            else:
                print("❌ Incorrect password! Try again.\n")
    else:
        print("Creating new vault with master password encryption...\n")
        while True:
            password = getpass.getpass("Create master password (min 12 characters): ").strip()
            if len(password) < 12:
                print("❌ Password must be at least 12 characters!")
                continue
            
            confirm = getpass.getpass("Confirm password: ").strip()
            if password != confirm:
                print("❌ Passwords don't match!")
                continue
            
            if manager._setup_encryption(password):
                manager.save_vault()
                print("✅ Vault created successfully!\n")
                break
    
    # Start interactive menu
    menu = InteractiveMenu(manager)
    menu.main_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}\n")
        sys.exit(1)
