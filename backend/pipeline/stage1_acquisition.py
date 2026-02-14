"""
RIMURU SECURITY PIPELINE - Stage 1: Acquisition
================================================
Isolated container for bot-based asset acquisition.
- VPN/proxy rotation
- Anti-malware pre-screening
- Zero knowledge of internal systems
- Drops assets into quarantine volume only
"""

import os
import json
import hashlib
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional, List
from dataclasses import dataclass, asdict, field
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [ACQUISITION] %(levelname)s: %(message)s'
)
logger = logging.getLogger('acquisition')

# ============================================
# Configuration - Zero trust, no internal knowledge
# ============================================
QUARANTINE_DROP = Path(os.getenv('QUARANTINE_DROP', '/quarantine/incoming'))
ACQUISITION_LOG = Path(os.getenv('ACQUISITION_LOG', '/logs/acquisition'))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB default
PROXY_LIST = os.getenv('PROXY_LIST', '').split(',')
USER_AGENT_ROTATE = True


@dataclass
class AcquiredAsset:
    """Represents a raw acquired asset before quarantine"""
    asset_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_type: str = ''          # 'bot_scrape', 'api_pull', 'manual_drop'
    source_url: str = ''
    asset_type: str = 'unknown'    # 'crypto_key', 'wallet_file', 'gift_card', 'token_data'
    raw_data: bytes = b''
    raw_hash_sha256: str = ''
    raw_hash_md5: str = ''
    file_size: int = 0
    acquired_at: str = ''
    proxy_used: str = ''
    metadata: Dict = field(default_factory=dict)
    risk_flags: List[str] = field(default_factory=list)


class ProxyRotator:
    """Rotate through proxy/VPN connections"""
    
    def __init__(self, proxies: List[str]):
        self.proxies = [p.strip() for p in proxies if p.strip()]
        self.current_idx = 0
        self.failed = set()
    
    def get_next(self) -> Optional[str]:
        if not self.proxies:
            return None
        available = [p for p in self.proxies if p not in self.failed]
        if not available:
            self.failed.clear()
            available = self.proxies
        proxy = available[self.current_idx % len(available)]
        self.current_idx += 1
        return proxy
    
    def mark_failed(self, proxy: str):
        self.failed.add(proxy)


class PreScreener:
    """Pre-screen acquired data before quarantine drop"""
    
    DANGEROUS_EXTENSIONS = {'.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.scr', '.com'}
    DANGEROUS_SIGNATURES = [
        b'MZ',                    # PE executable
        b'\x7fELF',              # ELF binary
        b'#!/',                   # Script with shebang
        b'<script',              # Embedded JS
        b'powershell',           # PowerShell commands
        b'cmd /c',               # CMD commands
    ]
    
    @classmethod
    def scan(cls, data: bytes, filename: str = '') -> List[str]:
        """Return list of risk flags"""
        flags = []
        
        # Check file extension
        ext = Path(filename).suffix.lower() if filename else ''
        if ext in cls.DANGEROUS_EXTENSIONS:
            flags.append(f'dangerous_extension:{ext}')
        
        # Check file signatures
        header = data[:256].lower() if data else b''
        for sig in cls.DANGEROUS_SIGNATURES:
            if sig.lower() in header:
                flags.append(f'dangerous_signature:{sig[:10]}')
        
        # Size check
        if len(data) > MAX_FILE_SIZE:
            flags.append(f'oversized:{len(data)}')
        
        # Check for known drainer patterns
        data_str = data[:4096].decode('utf-8', errors='ignore').lower()
        drainer_patterns = [
            'setapprovalforall', 'transferfrom', 'approve(', 
            'unlimited allowance', 'drain', 'sweeper'
        ]
        for pattern in drainer_patterns:
            if pattern in data_str:
                flags.append(f'drainer_pattern:{pattern}')
        
        # Check for call-home URLs
        callhome_patterns = [
            'webhook.site', 'requestbin', 'pipedream',
            'ngrok.io', 'serveo.net', 'localhost.run'
        ]
        for pattern in callhome_patterns:
            if pattern in data_str:
                flags.append(f'callhome_url:{pattern}')
        
        return flags


class AcquisitionService:
    """
    Stage 1: Asset Acquisition
    
    Responsibilities:
    - Acquire assets from external sources (bots, APIs, manual)
    - Pre-screen for obvious threats
    - Hash and tag all incoming data
    - Drop into quarantine volume
    - Log everything, trust nothing
    """
    
    def __init__(self):
        self.proxy = ProxyRotator(PROXY_LIST)
        self.screener = PreScreener()
        self.stats = {
            'total_acquired': 0,
            'dropped_to_quarantine': 0,
            'rejected_prescreeen': 0,
            'started_at': datetime.now(timezone.utc).isoformat()
        }
        
        # Ensure directories exist
        QUARANTINE_DROP.mkdir(parents=True, exist_ok=True)
        ACQUISITION_LOG.mkdir(parents=True, exist_ok=True)
    
    def acquire(self, data: bytes, source_type: str, source_url: str = '',
                asset_type: str = 'unknown', metadata: Dict = None) -> Optional[AcquiredAsset]:
        """
        Acquire raw data and prepare for quarantine.
        Returns AcquiredAsset if accepted, None if rejected.
        """
        self.stats['total_acquired'] += 1
        
        asset = AcquiredAsset(
            source_type=source_type,
            source_url=source_url,
            asset_type=asset_type,
            raw_data=data,
            raw_hash_sha256=hashlib.sha256(data).hexdigest(),
            raw_hash_md5=hashlib.md5(data).hexdigest(),
            file_size=len(data),
            acquired_at=datetime.now(timezone.utc).isoformat(),
            proxy_used=self.proxy.get_next() or 'direct',
            metadata=metadata or {},
        )
        
        # Pre-screen
        risk_flags = self.screener.scan(data, metadata.get('filename', '') if metadata else '')
        asset.risk_flags = risk_flags
        
        critical_flags = [f for f in risk_flags if 'drainer' in f or 'callhome' in f]
        if critical_flags:
            logger.warning(f"REJECTED asset {asset.asset_id}: {critical_flags}")
            self.stats['rejected_prescreeen'] += 1
            self._log_rejection(asset)
            return None
        
        # Drop to quarantine
        self._drop_to_quarantine(asset)
        self.stats['dropped_to_quarantine'] += 1
        logger.info(f"ACQUIRED {asset.asset_id} | type={asset_type} | size={asset.file_size} | flags={len(risk_flags)}")
        
        return asset
    
    def _drop_to_quarantine(self, asset: AcquiredAsset):
        """Write asset to quarantine drop volume"""
        drop_dir = QUARANTINE_DROP / asset.asset_id
        drop_dir.mkdir(parents=True, exist_ok=True)
        
        # Write raw data
        (drop_dir / 'raw_data.bin').write_bytes(asset.raw_data)
        
        # Write manifest (no raw data in manifest)
        manifest = {
            'asset_id': asset.asset_id,
            'source_type': asset.source_type,
            'source_url': asset.source_url,
            'asset_type': asset.asset_type,
            'raw_hash_sha256': asset.raw_hash_sha256,
            'raw_hash_md5': asset.raw_hash_md5,
            'file_size': asset.file_size,
            'acquired_at': asset.acquired_at,
            'proxy_used': asset.proxy_used,
            'metadata': asset.metadata,
            'risk_flags': asset.risk_flags,
            'stage': 'quarantine_pending',
        }
        (drop_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    
    def _log_rejection(self, asset: AcquiredAsset):
        """Log rejected assets"""
        log_file = ACQUISITION_LOG / f"rejected_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
        entry = {
            'asset_id': asset.asset_id,
            'source_type': asset.source_type,
            'risk_flags': asset.risk_flags,
            'rejected_at': datetime.now(timezone.utc).isoformat(),
            'hash': asset.raw_hash_sha256,
        }
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def get_stats(self) -> Dict:
        return self.stats


# ============================================
# FastAPI Interface (runs inside container)
# ============================================
try:
    from fastapi import FastAPI, UploadFile, File, Form, HTTPException
    from fastapi.responses import JSONResponse
    import uvicorn
    
    app = FastAPI(
        title="Rimuru Pipeline - Stage 1: Acquisition",
        description="Isolated asset acquisition with pre-screening",
        version="1.0.0"
    )
    
    service = AcquisitionService()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "stage": "acquisition", "stats": service.get_stats()}
    
    @app.post("/acquire")
    async def acquire_asset(
        file: UploadFile = File(...),
        source_type: str = Form(default="manual_drop"),
        source_url: str = Form(default=""),
        asset_type: str = Form(default="unknown"),
    ):
        data = await file.read()
        metadata = {'filename': file.filename, 'content_type': file.content_type}
        
        result = service.acquire(data, source_type, source_url, asset_type, metadata)
        if result is None:
            raise HTTPException(status_code=403, detail="Asset rejected by pre-screening")
        
        return {
            "asset_id": result.asset_id,
            "status": "quarantine_pending",
            "hash": result.raw_hash_sha256,
            "risk_flags": result.risk_flags,
        }
    
    @app.get("/stats")
    async def stats():
        return service.get_stats()

except ImportError:
    app = None

if __name__ == "__main__":
    if app:
        port = int(os.getenv('ACQUISITION_PORT', 8501))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        logger.info("FastAPI not available. Running in library mode.")
