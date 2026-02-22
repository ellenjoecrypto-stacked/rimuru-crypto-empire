"""
Comprehensive Crypto Data Scanner & Database Builder
Scans all user directories for crypto credentials, wallets, seeds, and API keys
Saves everything to SQLite database for analysis
"""

import logging
import os
import re
import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import time

logger = logging.getLogger(__name__)


class CryptoFindingsDB:
    """SQLite database for storing all crypto findings"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables"""
        cursor = self.conn.cursor()
        
        # Wallets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE,
                blockchain TEXT,
                source_file TEXT,
                discovered_at TEXT,
                balance_checked INTEGER DEFAULT 0,
                balance_eth REAL DEFAULT 0,
                balance_usd REAL DEFAULT 0
            )
        ''')
        
        # API Keys table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_type TEXT,
                key_hash TEXT UNIQUE,
                key_preview TEXT,
                source_file TEXT,
                exchange TEXT,
                discovered_at TEXT,
                is_valid INTEGER DEFAULT -1
            )
        ''')
        
        # Seed phrases / mnemonics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seed_phrases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phrase_hash TEXT UNIQUE,
                word_count INTEGER,
                source_file TEXT,
                discovered_at TEXT,
                verified INTEGER DEFAULT 0
            )
        ''')
        
        # Scanned files
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scanned_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE,
                file_size INTEGER,
                file_type TEXT,
                has_crypto_data INTEGER DEFAULT 0,
                wallets_found INTEGER DEFAULT 0,
                keys_found INTEGER DEFAULT 0,
                scanned_at TEXT
            )
        ''')
        
        # Summary
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT,
                total_files INTEGER,
                total_wallets INTEGER,
                total_api_keys INTEGER,
                total_seeds INTEGER,
                total_usd_value REAL DEFAULT 0
            )
        ''')
        
        self.conn.commit()
    
    def add_wallet(self, address: str, blockchain: str, source_file: str):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO wallets (address, blockchain, source_file, discovered_at)
                VALUES (?, ?, ?, ?)
            ''', (address, blockchain, source_file, datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception as e:
            pass
    
    def add_api_key(self, key_type: str, key_value: str, source_file: str, exchange: str = None):
        cursor = self.conn.cursor()
        key_hash = hashlib.sha256(key_value.encode()).hexdigest()
        key_preview = key_value[:8] + "..." + key_value[-4:] if len(key_value) > 12 else "***"
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO api_keys (key_type, key_hash, key_preview, source_file, exchange, discovered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (key_type, key_hash, key_preview, source_file, exchange, datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception as e:
            pass
    
    def add_seed_phrase(self, phrase: str, source_file: str):
        cursor = self.conn.cursor()
        phrase_hash = hashlib.sha256(phrase.encode()).hexdigest()
        word_count = len(phrase.split())
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO seed_phrases (phrase_hash, word_count, source_file, discovered_at)
                VALUES (?, ?, ?, ?)
            ''', (phrase_hash, word_count, source_file, datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception as e:
            pass
    
    def add_scanned_file(self, file_path: str, file_size: int, file_type: str, 
                         has_crypto: bool, wallets: int, keys: int):
        cursor = self.conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO scanned_files 
                (file_path, file_size, file_type, has_crypto_data, wallets_found, keys_found, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (file_path, file_size, file_type, int(has_crypto), wallets, keys, 
                  datetime.utcnow().isoformat()))
            self.conn.commit()
        except Exception as e:
            pass
    
    def get_summary(self) -> Dict:
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM api_keys")
        total_keys = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM seed_phrases")
        total_seeds = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM scanned_files")
        total_files = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(balance_usd) FROM wallets")
        total_usd = cursor.fetchone()[0] or 0
        
        return {
            'total_wallets': total_wallets,
            'total_api_keys': total_keys,
            'total_seed_phrases': total_seeds,
            'total_files_scanned': total_files,
            'total_usd_value': total_usd
        }
    
    def get_all_wallets(self) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT address, blockchain, source_file, balance_usd FROM wallets")
        return [{'address': r[0], 'blockchain': r[1], 'source': r[2], 'usd': r[3]} 
                for r in cursor.fetchall()]
    
    def close(self):
        self.conn.close()


class ComprehensiveCryptoScanner:
    """Scans all directories for crypto data"""
    
    # BIP39 word list (first 100 common words for detection)
    BIP39_WORDS = {
        'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb', 'abstract',
        'absurd', 'abuse', 'access', 'accident', 'account', 'accuse', 'achieve', 'acid',
        'acoustic', 'acquire', 'across', 'act', 'action', 'actor', 'actress', 'actual',
        'adapt', 'add', 'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
        'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again', 'age', 'agent',
        'agree', 'ahead', 'aim', 'air', 'airport', 'aisle', 'alarm', 'album',
        'alcohol', 'alert', 'alien', 'all', 'alley', 'allow', 'almost', 'alone',
        'alpha', 'already', 'also', 'alter', 'always', 'amateur', 'amazing', 'among',
        'amount', 'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle', 'angry',
        'animal', 'ankle', 'announce', 'annual', 'another', 'answer', 'antenna', 'antique',
        'anxiety', 'any', 'apart', 'apology', 'appear', 'apple', 'approve', 'april',
        'arch', 'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor',
        'army', 'around', 'arrange', 'arrest', 'arrive', 'arrow', 'art', 'artefact',
        'artist', 'artwork', 'ask', 'aspect', 'assault', 'asset', 'assist', 'assume',
        'asthma', 'atom', 'attack', 'attend', 'attitude', 'attract', 'auction', 'audit',
        'august', 'aunt', 'author', 'auto', 'autumn', 'average', 'avocado', 'avoid',
        'awake', 'aware', 'away', 'awesome', 'awful', 'awkward', 'axis', 'baby',
        'bachelor', 'bacon', 'badge', 'bag', 'balance', 'balcony', 'ball', 'bamboo',
        'banana', 'banner', 'bar', 'barely', 'bargain', 'barrel', 'base', 'basic',
        'basket', 'battle', 'beach', 'bean', 'beauty', 'because', 'become', 'beef',
        'before', 'begin', 'behave', 'behind', 'believe', 'below', 'belt', 'bench',
        'benefit', 'best', 'betray', 'better', 'between', 'beyond', 'bicycle', 'bid',
        'bike', 'bind', 'biology', 'bird', 'birth', 'bitter', 'black', 'blade',
        'blame', 'blanket', 'blast', 'bleak', 'bless', 'blind', 'blood', 'blossom',
        'blouse', 'blue', 'blur', 'blush', 'board', 'boat', 'body', 'boil',
        'bomb', 'bone', 'bonus', 'book', 'boost', 'border', 'boring', 'borrow',
        'boss', 'bottom', 'bounce', 'box', 'boy', 'bracket', 'brain', 'brand',
        'brass', 'brave', 'bread', 'breeze', 'brick', 'bridge', 'brief', 'bright',
        'bring', 'brisk', 'broccoli', 'broken', 'bronze', 'broom', 'brother', 'brown',
        'brush', 'bubble', 'buddy', 'budget', 'buffalo', 'build', 'bulb', 'bulk',
        'bullet', 'bundle', 'bunker', 'burden', 'burger', 'burst', 'bus', 'business',
        'busy', 'butter', 'buyer', 'buzz', 'cabbage', 'cabin', 'cable', 'cactus',
        'cage', 'cake', 'call', 'calm', 'camera', 'camp', 'can', 'canal',
        'cancel', 'candy', 'cannon', 'canoe', 'canvas', 'canyon', 'capable', 'capital',
        'captain', 'car', 'carbon', 'card', 'cargo', 'carpet', 'carry', 'cart',
        'case', 'cash', 'casino', 'castle', 'casual', 'cat', 'catalog', 'catch',
    }
    
    # Patterns
    PATTERNS = {
        'eth_address': r'0x[a-fA-F0-9]{40}',
        'btc_address': r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}',
        'private_key_hex': r'[a-fA-F0-9]{64}',
        'api_key': r'[\'"]?(?:api[_-]?key|apikey)[\'"]?\s*[:=]\s*[\'"]?([a-zA-Z0-9_-]{20,})[\'"]?',
        'secret_key': r'[\'"]?(?:secret[_-]?key|secretkey)[\'"]?\s*[:=]\s*[\'"]?([a-zA-Z0-9_-]{20,})[\'"]?',
    }
    
    SCAN_EXTENSIONS = {'.py', '.js', '.ts', '.json', '.yaml', '.yml', '.env', '.txt', '.md', '.cfg', '.ini', '.toml'}
    
    IGNORE_DIRS = {'node_modules', '__pycache__', '.git', 'venv', 'env', '.vscode', 
                   '.idea', 'dist', 'build', '.next', 'AppData'}
    
    def __init__(self, db: CryptoFindingsDB):
        self.db = db
        self.files_scanned = 0
        self.wallets_found = 0
        self.keys_found = 0
        self.seeds_found = 0
    
    def scan_directory(self, base_path: str, max_files: int = 5000):
        """Recursively scan directory for crypto data"""

        logger.info(f"\n📁 Scanning: {base_path}")

        try:
            for root, dirs, files in os.walk(base_path):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]

                for file in files:
                    if self.files_scanned >= max_files:
                        logger.info(f"   Reached max files limit ({max_files})")
                        return

                    file_path = os.path.join(root, file)

                    # Check extension or specific file names
                    ext = os.path.splitext(file)[1].lower()
                    name_lower = file.lower()

                    should_scan = (
                        ext in self.SCAN_EXTENSIONS or
                        'wallet' in name_lower or
                        'seed' in name_lower or
                        'key' in name_lower or
                        'secret' in name_lower or
                        'crypto' in name_lower or
                        'mnemonic' in name_lower or
                        'backup' in name_lower or
                        '.env' in name_lower
                    )

                    if should_scan:
                        self._scan_file(file_path)

        except PermissionError:
            logger.warning(f"   ⚠️ Permission denied: {base_path}")
        except Exception as e:
            logger.error(f"   ❌ Error: {e}")
    
    def _scan_file(self, file_path: str):
        """Scan individual file for crypto data"""
        
        try:
            # Skip large files
            size = os.path.getsize(file_path)
            if size > 1000000:  # 1MB
                return
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            self.files_scanned += 1
            
            wallets_in_file = 0
            keys_in_file = 0
            
            # Find ETH addresses
            eth_matches = re.findall(self.PATTERNS['eth_address'], content)
            for addr in set(eth_matches):
                if not self._is_common_address(addr):
                    self.db.add_wallet(addr, 'ETH', file_path)
                    wallets_in_file += 1
                    self.wallets_found += 1
            
            # Find BTC addresses
            btc_matches = re.findall(self.PATTERNS['btc_address'], content)
            for addr in set(btc_matches):
                if len(addr) >= 26:
                    self.db.add_wallet(addr, 'BTC', file_path)
                    wallets_in_file += 1
                    self.wallets_found += 1
            
            # Find API keys
            api_keys = re.findall(self.PATTERNS['api_key'], content, re.IGNORECASE)
            for key in set(api_keys):
                if not self._is_placeholder(key):
                    self.db.add_api_key('api_key', key, file_path)
                    keys_in_file += 1
                    self.keys_found += 1
            
            # Find secret keys
            secret_keys = re.findall(self.PATTERNS['secret_key'], content, re.IGNORECASE)
            for key in set(secret_keys):
                if not self._is_placeholder(key):
                    self.db.add_api_key('secret_key', key, file_path)
                    keys_in_file += 1
                    self.keys_found += 1
            
            # Find potential seed phrases (12 or 24 BIP39 words)
            seed_phrases = self._find_seed_phrases(content)
            for phrase in seed_phrases:
                self.db.add_seed_phrase(phrase, file_path)
                self.seeds_found += 1
            
            # Record file scan
            ext = os.path.splitext(file_path)[1].lower()
            has_crypto = wallets_in_file > 0 or keys_in_file > 0 or len(seed_phrases) > 0
            self.db.add_scanned_file(file_path, size, ext, has_crypto, wallets_in_file, keys_in_file)
            
            if has_crypto:
                logger.info(f"   ✅ {os.path.basename(file_path)}: {wallets_in_file} wallets, {keys_in_file} keys")
                
        except Exception as e:
            pass
    
    def _is_common_address(self, addr: str) -> bool:
        """Check if address is a common contract/example"""
        common = {
            '0x0000000000000000000000000000000000000000',
            '0x1111111111111111111111111111111111111111',
            '0xffffffffffffffffffffffffffffffffffffffff',
            '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',  # USDC
            '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # USDT
            '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',  # UNI
        }
        return addr.lower() in [a.lower() for a in common]
    
    def _is_placeholder(self, key: str) -> bool:
        """Check if key is a placeholder"""
        placeholders = ['your_', 'test_', 'xxx', 'placeholder', 'example', 'demo', 'sample']
        key_lower = key.lower()
        return any(p in key_lower for p in placeholders)
    
    def _find_seed_phrases(self, content: str) -> List[str]:
        """Find potential BIP39 seed phrases"""
        phrases = []
        words = content.lower().split()
        
        # Look for sequences of 12 or 24 BIP39 words
        for i in range(len(words) - 11):
            for length in [12, 24]:
                if i + length <= len(words):
                    sequence = words[i:i+length]
                    bip39_count = sum(1 for w in sequence if w in self.BIP39_WORDS)
                    
                    # If most words are BIP39 words, likely a seed phrase
                    if bip39_count >= length * 0.8:
                        phrase = ' '.join(sequence)
                        if phrase not in phrases:
                            phrases.append(phrase)
        
        return phrases
    
    def print_progress(self):
        """Log current progress."""
        logger.info(f"\n📊 Progress: {self.files_scanned} files | {self.wallets_found} wallets | {self.keys_found} keys | {self.seeds_found} seeds")


def main():
    logging.basicConfig(level=logging.INFO)
    logger.info("=" * 60)
    logger.info("🔍 COMPREHENSIVE CRYPTO DATA SCANNER")
    logger.info("=" * 60)

    # Database path — configurable via environment variable
    db_path = os.getenv(
        "CRYPTO_DB_PATH",
        os.path.join("data", "crypto_findings.db"),
    )

    # Initialize database
    logger.info(f"\n📝 Creating database: {db_path}")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db = CryptoFindingsDB(db_path)

    # Initialize scanner
    scanner = ComprehensiveCryptoScanner(db)

    # Directories to scan — configurable via environment variable
    base = os.getenv("SCAN_BASE_DIR", os.path.expanduser("~"))
    scan_dirs = [
        os.path.join(base, "OneDrive"),
        os.path.join(base, "Documents"),
        os.path.join(base, "source"),
        os.path.join(base, "Desktop"),
    ]

    # Scan each directory
    for directory in scan_dirs:
        if os.path.exists(directory):
            scanner.scan_directory(directory, max_files=3000)
            scanner.print_progress()

    # Get and log summary
    summary = db.get_summary()

    logger.info("\n" + "=" * 60)
    logger.info("📊 FINAL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files scanned:  {summary['total_files_scanned']}")
    logger.info(f"Total wallets found:  {summary['total_wallets']}")
    logger.info(f"Total API keys found: {summary['total_api_keys']}")
    logger.info(f"Total seed phrases:   {summary['total_seed_phrases']}")
    logger.info(f"Total USD value:      ${summary['total_usd_value']:,.2f}")

    # Show all wallets found
    wallets = db.get_all_wallets()
    if wallets:
        logger.info("\n🔐 WALLETS FOUND:")
        for w in wallets[:30]:
            logger.info(f"   [{w['blockchain']}] {w['address'][:20]}...{w['address'][-8:]}")

    logger.info(f"\n✅ Results saved to: {db_path}")
    
    db.close()
    return summary


if __name__ == "__main__":
    main()
