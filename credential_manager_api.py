#!/usr/bin/env python3
"""
Credential Manager - Programmatic API
For integrating credential management into your applications
"""

import sys
from pathlib import Path
from credential_manager import CredentialManager, Credential
import json

class ProgrammaticCredentialManager:
    """Programmatic interface for credential management"""
    
    def __init__(self, vault_path: str = "_SENSITIVE/VAULT_DATA", master_password: str = ""):
        self.manager = CredentialManager(vault_path)
        if master_password:
            self._init_with_password(master_password)
    
    def _init_with_password(self, password: str) -> bool:
        """Initialize with password"""
        if not self.manager._load_encryption(password):
            print(f"❌ Failed to load encryption with provided password")
            return False
        
        if not self.manager.load_vault():
            print(f"❌ Failed to load vault")
            return False
        
        return True
    
    def add(self, name: str, value: str, cred_type: str = "Other Secret", 
            description: str = "", exchange: str = "") -> bool:
        """Add credential programmatically"""
        if self.manager.add_credential(name, cred_type, value, description, exchange):
            return self.manager.save_vault()
        return False
    
    def get(self, name: str) -> str:
        """Get credential value"""
        return self.manager.get_credential(name) or ""
    
    def list_all(self) -> list:
        """List all credentials"""
        return [
            {
                'name': c.name,
                'type': c.credential_type,
                'exchange': c.exchange,
                'description': c.description,
                'created': c.created_at
            }
            for c in self.manager.credentials
        ]
    
    def delete(self, name: str) -> bool:
        """Delete credential"""
        if self.manager.delete_credential(name):
            return self.manager.save_vault()
        return False
    
    def update(self, name: str, value: str) -> bool:
        """Update credential"""
        if self.manager.update_credential(name, value):
            return self.manager.save_vault()
        return False
    
    def export_json(self, filepath: str) -> bool:
        """Export credentials to JSON (encrypted file)"""
        try:
            data = {
                'credentials': [
                    {
                        'name': c.name,
                        'type': c.credential_type,
                        'exchange': c.exchange,
                        'description': c.description,
                        'created': c.created_at
                    }
                    for c in self.manager.credentials
                ]
            }
            
            json_str = json.dumps(data, indent=2)
            encrypted = self.manager.cipher.encrypt(json_str.encode())
            
            with open(filepath, 'wb') as f:
                f.write(encrypted)
            
            print(f"✅ Exported to {filepath}")
            return True
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False


# Example usage
if __name__ == "__main__":
    print("Credential Manager - Programmatic Interface")
    print("=" * 60)
    print("\nExample usage:\n")
    print("""
from credential_manager_api import ProgrammaticCredentialManager

# Initialize with password
cred_mgr = ProgrammaticCredentialManager(master_password="YourMasterPassword")

# Add credentials
cred_mgr.add(
    name="Binance API Key",
    value="your_api_key_here",
    cred_type="Exchange API Key",
    exchange="Binance"
)

# Get credentials
api_key = cred_mgr.get("Binance API Key")

# List all
all_creds = cred_mgr.list_all()
for cred in all_creds:
    print(f"{cred['name']}: {cred['type']}")

# Update
cred_mgr.update("Binance API Key", "new_key_value")

# Delete
cred_mgr.delete("Binance API Key")
    """)
