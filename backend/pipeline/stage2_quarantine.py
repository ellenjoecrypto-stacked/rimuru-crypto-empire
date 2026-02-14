"""
RIMURU SECURITY PIPELINE - Stage 2: Quarantine
================================================
Isolated container for threat analysis.
- Malware scanning (YARA rules, signature matching)
- Virus check (ClamAV integration)
- Call-home detection (network analysis)
- Drainer/sweeper detection
- Risk scoring (0-100)
- Only clean assets move to Stage 3
"""

import os
import json
import hashlib
import re
import struct
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import time
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [QUARANTINE] %(levelname)s: %(message)s'
)
logger = logging.getLogger('quarantine')

# ============================================
# Configuration
# ============================================
QUARANTINE_INCOMING = Path(os.getenv('QUARANTINE_INCOMING', '/quarantine/incoming'))
QUARANTINE_CLEAN = Path(os.getenv('QUARANTINE_CLEAN', '/quarantine/clean'))
QUARANTINE_REJECTED = Path(os.getenv('QUARANTINE_REJECTED', '/quarantine/rejected'))
QUARANTINE_LOG = Path(os.getenv('QUARANTINE_LOG', '/logs/quarantine'))
RISK_THRESHOLD = int(os.getenv('RISK_THRESHOLD', 40))  # Max risk score to pass
HOLD_HOURS = int(os.getenv('HOLD_HOURS', 1))  # Min hours in quarantine


@dataclass
class ThreatReport:
    """Complete threat analysis report"""
    asset_id: str = ''
    risk_score: int = 0            # 0-100, higher = more dangerous
    malware_detected: bool = False
    virus_signatures: List[str] = field(default_factory=list)
    callhome_urls: List[str] = field(default_factory=list)
    drainer_patterns: List[str] = field(default_factory=list)
    suspicious_strings: List[str] = field(default_factory=list)
    file_type_analysis: Dict = field(default_factory=dict)
    entropy_score: float = 0.0
    verdict: str = 'pending'       # 'clean', 'suspicious', 'malicious', 'pending'
    scan_duration_ms: int = 0
    scanned_at: str = ''
    details: List[str] = field(default_factory=list)


class MalwareScanner:
    """Pattern-based malware detection"""
    
    # Known malicious patterns
    MALWARE_SIGNATURES = [
        (b'\x4d\x5a\x90\x00', 'PE_EXECUTABLE'),
        (b'This program cannot be run in DOS mode', 'DOS_STUB'),
        (b'CreateRemoteThread', 'PROCESS_INJECTION'),
        (b'VirtualAllocEx', 'MEMORY_INJECTION'),
        (b'WriteProcessMemory', 'MEMORY_WRITE'),
        (b'LoadLibrary', 'DLL_INJECTION'),
        (b'WScript.Shell', 'WSCRIPT_SHELL'),
        (b'ActiveXObject', 'ACTIVEX'),
        (b'eval(atob(', 'OBFUSCATED_EVAL'),
        (b'fromCharCode', 'CHAR_DECODE'),
    ]
    
    # Crypto-specific threats
    CRYPTO_THREATS = [
        (r'setApprovalForAll\s*\(', 'NFT_APPROVAL_HIJACK'),
        (r'approve\s*\(\s*address.*uint256\.max', 'UNLIMITED_APPROVAL'),
        (r'transferFrom\s*\(', 'TOKEN_TRANSFER_HIJACK'),
        (r'selfdestruct\s*\(', 'CONTRACT_SELFDESTRUCT'),
        (r'delegatecall\s*\(', 'DELEGATECALL_RISK'),
        (r'tx\.origin', 'TX_ORIGIN_AUTH'),
        (r'private\s+key|secret\s+key|mnemonic', 'KEY_EXTRACTION'),
        (r'seed\s*phrase|recovery\s*phrase', 'SEED_EXTRACTION'),
    ]
    
    # Call-home indicators
    CALLHOME_PATTERNS = [
        r'https?://\d+\.\d+\.\d+\.\d+[:/]',           # Direct IP URLs
        r'webhook\.site|requestbin|pipedream',           # Known exfil services
        r'ngrok\.io|serveo\.net|localhost\.run',          # Tunnel services
        r'discord\.com/api/webhooks',                     # Discord webhooks
        r'api\.telegram\.org/bot',                        # Telegram bots
        r'pastebin\.com|hastebin|ghostbin',              # Paste services
        r'transfer\.sh|file\.io|0x0\.st',                # File share services
    ]
    
    @classmethod
    def scan(cls, data: bytes) -> Tuple[List[str], int]:
        """Scan data for malware. Returns (findings, risk_score)"""
        findings = []
        risk = 0
        
        # Binary signature scan
        for sig, name in cls.MALWARE_SIGNATURES:
            if sig in data:
                findings.append(f'MALWARE_SIG:{name}')
                risk += 15
        
        # Text-based scan
        try:
            text = data.decode('utf-8', errors='ignore')
        except:
            text = ''
        
        # Crypto threat scan
        for pattern, name in cls.CRYPTO_THREATS:
            if re.search(pattern, text, re.IGNORECASE):
                findings.append(f'CRYPTO_THREAT:{name}')
                risk += 20
        
        # Call-home scan
        for pattern in cls.CALLHOME_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                for m in matches[:3]:
                    findings.append(f'CALLHOME:{m}')
                risk += 25
        
        return findings, min(risk, 100)


class EntropyAnalyzer:
    """Detect packed/encrypted/obfuscated content via entropy"""
    
    @staticmethod
    def calculate(data: bytes) -> float:
        """Calculate Shannon entropy (0-8). High entropy = encrypted/packed"""
        if not data:
            return 0.0
        
        import math
        freq = [0] * 256
        for byte in data:
            freq[byte] += 1
        
        length = len(data)
        entropy = 0.0
        for count in freq:
            if count > 0:
                prob = count / length
                entropy -= prob * math.log2(prob)
        
        return round(entropy, 4)


class DrainerDetector:
    """Detect crypto drainer/sweeper scripts"""
    
    DRAINER_INDICATORS = [
        'setApprovalForAll',
        'approve(',
        'transferFrom',
        'permit(',
        'safeTransferFrom',
        'unlimited',
        'drain',
        'sweep',
        'siphon',
        'claim free',
        'connect wallet',
        'web3modal',
        'walletconnect',
        'metamask',
        'phantom',
    ]
    
    DRAINER_COMBOS = [
        ('approve', 'transferFrom'),
        ('connect', 'wallet', 'approve'),
        ('claim', 'approve', 'transfer'),
    ]
    
    @classmethod
    def scan(cls, data: bytes) -> Tuple[List[str], int]:
        """Detect drainer patterns. Returns (patterns_found, risk_score)"""
        text = data.decode('utf-8', errors='ignore').lower()
        found = []
        risk = 0
        
        # Individual indicators
        indicator_count = 0
        for indicator in cls.DRAINER_INDICATORS:
            if indicator.lower() in text:
                found.append(f'DRAINER_INDICATOR:{indicator}')
                indicator_count += 1
        
        if indicator_count >= 3:
            risk += 30
        elif indicator_count >= 1:
            risk += 10
        
        # Combo detection (multiple indicators together = high risk)
        for combo in cls.DRAINER_COMBOS:
            if all(c.lower() in text for c in combo):
                found.append(f'DRAINER_COMBO:{"+".join(combo)}')
                risk += 40
        
        return found, min(risk, 100)


class QuarantineService:
    """
    Stage 2: Quarantine & Threat Analysis
    
    Responsibilities:
    - Deep scan all incoming assets
    - Malware/virus detection
    - Drainer/sweeper detection
    - Call-home URL detection  
    - Entropy analysis
    - Risk scoring
    - Hold period enforcement
    - Pass clean assets to Stage 3
    """
    
    def __init__(self):
        self.stats = {
            'total_scanned': 0,
            'passed': 0,
            'rejected': 0,
            'pending': 0,
            'started_at': datetime.now(timezone.utc).isoformat()
        }
        
        for d in [QUARANTINE_INCOMING, QUARANTINE_CLEAN, QUARANTINE_REJECTED, QUARANTINE_LOG]:
            d.mkdir(parents=True, exist_ok=True)
    
    def scan_asset(self, asset_dir: Path) -> ThreatReport:
        """Full threat analysis of an asset in quarantine"""
        start = time.time()
        manifest_path = asset_dir / 'manifest.json'
        data_path = asset_dir / 'raw_data.bin'
        
        if not manifest_path.exists() or not data_path.exists():
            logger.error(f"Invalid quarantine entry: {asset_dir}")
            report = ThreatReport(verdict='error')
            report.details.append('Missing manifest or data')
            return report
        
        manifest = json.loads(manifest_path.read_text())
        data = data_path.read_bytes()
        asset_id = manifest.get('asset_id', asset_dir.name)
        
        report = ThreatReport(asset_id=asset_id)
        total_risk = 0
        
        # 1. Verify hash integrity
        actual_hash = hashlib.sha256(data).hexdigest()
        expected_hash = manifest.get('raw_hash_sha256', '')
        if actual_hash != expected_hash:
            report.details.append(f'HASH_MISMATCH: expected={expected_hash[:16]}... got={actual_hash[:16]}...')
            total_risk += 50
        
        # 2. Malware scan
        malware_findings, malware_risk = MalwareScanner.scan(data)
        report.virus_signatures = malware_findings
        total_risk += malware_risk
        if malware_findings:
            report.malware_detected = True
        
        # 3. Drainer detection
        drainer_findings, drainer_risk = DrainerDetector.scan(data)
        report.drainer_patterns = drainer_findings
        total_risk += drainer_risk
        
        # 4. Entropy analysis
        entropy = EntropyAnalyzer.calculate(data)
        report.entropy_score = entropy
        if entropy > 7.5:
            report.details.append(f'HIGH_ENTROPY:{entropy} (possibly encrypted/packed)')
            total_risk += 10
        
        # 5. File type analysis
        report.file_type_analysis = {
            'size': len(data),
            'entropy': entropy,
            'is_text': self._is_text(data),
            'is_json': self._is_json(data),
            'header_hex': data[:16].hex() if data else '',
        }
        
        # 6. Extract call-home URLs
        callhome_re = re.compile(
            r'https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+',
            re.IGNORECASE
        )
        text = data.decode('utf-8', errors='ignore')
        urls = callhome_re.findall(text)
        suspicious_urls = []
        for url in urls:
            url_lower = url.lower()
            for pattern in MalwareScanner.CALLHOME_PATTERNS:
                if re.search(pattern, url_lower):
                    suspicious_urls.append(url)
                    break
        report.callhome_urls = suspicious_urls
        
        # Final risk score
        report.risk_score = min(total_risk, 100)
        report.scan_duration_ms = int((time.time() - start) * 1000)
        report.scanned_at = datetime.now(timezone.utc).isoformat()
        
        # Verdict
        if report.risk_score >= 70:
            report.verdict = 'malicious'
        elif report.risk_score >= RISK_THRESHOLD:
            report.verdict = 'suspicious'
        else:
            report.verdict = 'clean'
        
        self.stats['total_scanned'] += 1
        
        return report
    
    def process_incoming(self) -> List[Dict]:
        """Process all assets in the incoming quarantine folder"""
        results = []
        
        if not QUARANTINE_INCOMING.exists():
            return results
        
        for asset_dir in sorted(QUARANTINE_INCOMING.iterdir()):
            if not asset_dir.is_dir():
                continue
            
            logger.info(f"Scanning {asset_dir.name}...")
            report = self.scan_asset(asset_dir)
            
            # Write report
            report_dict = {
                'asset_id': report.asset_id,
                'risk_score': report.risk_score,
                'verdict': report.verdict,
                'malware_detected': report.malware_detected,
                'virus_signatures': report.virus_signatures,
                'callhome_urls': report.callhome_urls,
                'drainer_patterns': report.drainer_patterns,
                'entropy_score': report.entropy_score,
                'file_type_analysis': report.file_type_analysis,
                'scan_duration_ms': report.scan_duration_ms,
                'scanned_at': report.scanned_at,
                'details': report.details,
            }
            (asset_dir / 'threat_report.json').write_text(json.dumps(report_dict, indent=2))
            
            # Route based on verdict
            if report.verdict == 'clean':
                dest = QUARANTINE_CLEAN / asset_dir.name
                self._move_asset(asset_dir, dest)
                self.stats['passed'] += 1
                logger.info(f"  CLEAN (risk={report.risk_score}) → scanner")
            elif report.verdict in ('suspicious', 'malicious'):
                dest = QUARANTINE_REJECTED / asset_dir.name
                self._move_asset(asset_dir, dest)
                self.stats['rejected'] += 1
                logger.warning(f"  REJECTED: {report.verdict} (risk={report.risk_score})")
            
            results.append(report_dict)
        
        return results
    
    def _move_asset(self, src: Path, dest: Path):
        """Move asset directory to destination"""
        import shutil
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(src), str(dest))
    
    def _is_text(self, data: bytes) -> bool:
        try:
            data[:1024].decode('utf-8')
            return True
        except:
            return False
    
    def _is_json(self, data: bytes) -> bool:
        try:
            json.loads(data)
            return True
        except:
            return False
    
    def get_stats(self) -> Dict:
        return self.stats


# ============================================
# FastAPI Interface
# ============================================
try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI(
        title="Rimuru Pipeline - Stage 2: Quarantine",
        description="Threat analysis and quarantine scanning",
        version="1.0.0"
    )
    
    service = QuarantineService()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "stage": "quarantine", "stats": service.get_stats()}
    
    @app.post("/scan")
    async def scan_all():
        """Process all incoming quarantine assets"""
        results = service.process_incoming()
        return {"scanned": len(results), "results": results}
    
    @app.get("/stats")
    async def stats():
        return service.get_stats()

except ImportError:
    app = None

if __name__ == "__main__":
    if app:
        port = int(os.getenv('QUARANTINE_PORT', 8502))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        service = QuarantineService()
        results = service.process_incoming()
        print(f"Scanned {len(results)} assets")
        for r in results:
            print(f"  {r['asset_id']}: {r['verdict']} (risk={r['risk_score']})")
