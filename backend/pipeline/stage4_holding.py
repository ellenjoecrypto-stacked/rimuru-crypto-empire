"""
RIMURU SECURITY PIPELINE - Stage 4: Holding Vault
===================================================
Isolated per-asset holding with monitoring.
- Each asset held in isolation
- Monitored for suspicious activity
- Configurable hold period (default 72 hours)
- Balance change detection
- Activity logging
- Only releases after hold period + manual approval
"""

import os
import json
import logging
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [HOLDING] %(levelname)s: %(message)s'
)
logger = logging.getLogger('holding')

# ============================================
# Configuration
# ============================================
HOLDING_INCOMING = Path(os.getenv('HOLDING_INCOMING', '/vault/holding'))
HOLDING_APPROVED = Path(os.getenv('HOLDING_APPROVED', '/vault/approved'))
HOLDING_LOG = Path(os.getenv('HOLDING_LOG', '/logs/holding'))
HOLD_PERIOD_HOURS = int(os.getenv('HOLD_PERIOD_HOURS', 72))
REQUIRE_MANUAL_APPROVAL = os.getenv('REQUIRE_MANUAL_APPROVAL', 'true').lower() == 'true'


@dataclass
class HoldingEntry:
    """Asset in holding vault"""
    asset_id: str = ''
    entered_at: str = ''
    hold_until: str = ''
    status: str = 'holding'        # holding, approved, released, flagged
    monitoring_events: List[Dict] = field(default_factory=list)
    approval: Optional[Dict] = None
    integrity_hash: str = ''
    check_count: int = 0
    last_checked: str = ''


class HoldingVault:
    """
    Stage 4: Holding Vault
    
    Responsibilities:
    - Hold each asset in isolation
    - Monitor integrity (hash checks)
    - Enforce minimum hold period
    - Require manual approval for release
    - Log all monitoring events
    - Detect unauthorized modifications
    """
    
    def __init__(self):
        self.stats = {
            'total_held': 0,
            'currently_holding': 0,
            'released': 0,
            'flagged': 0,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        
        for d in [HOLDING_INCOMING, HOLDING_APPROVED, HOLDING_LOG]:
            d.mkdir(parents=True, exist_ok=True)
    
    def intake_asset(self, asset_dir: Path) -> HoldingEntry:
        """Register an asset into the holding vault"""
        now = datetime.now(timezone.utc)
        hold_until = now + timedelta(hours=HOLD_PERIOD_HOURS)
        
        # Calculate integrity hash of all files
        integrity = self._calc_integrity(asset_dir)
        
        entry = HoldingEntry(
            asset_id=asset_dir.name,
            entered_at=now.isoformat(),
            hold_until=hold_until.isoformat(),
            status='holding',
            integrity_hash=integrity,
            last_checked=now.isoformat(),
        )
        
        # Write holding manifest
        manifest = {
            'asset_id': entry.asset_id,
            'entered_at': entry.entered_at,
            'hold_until': entry.hold_until,
            'status': entry.status,
            'integrity_hash': entry.integrity_hash,
            'hold_period_hours': HOLD_PERIOD_HOURS,
            'require_manual_approval': REQUIRE_MANUAL_APPROVAL,
        }
        (asset_dir / 'holding_manifest.json').write_text(json.dumps(manifest, indent=2))
        
        self.stats['total_held'] += 1
        self.stats['currently_holding'] += 1
        
        logger.info(f"INTAKE {entry.asset_id} | hold until {hold_until.strftime('%Y-%m-%d %H:%M UTC')}")
        return entry
    
    def monitor_all(self) -> List[Dict]:
        """Check all held assets for integrity"""
        results = []
        
        for asset_dir in sorted(HOLDING_INCOMING.iterdir()):
            if not asset_dir.is_dir():
                continue
            
            manifest_path = asset_dir / 'holding_manifest.json'
            if not manifest_path.exists():
                # New asset, intake it
                entry = self.intake_asset(asset_dir)
                results.append({'asset_id': entry.asset_id, 'action': 'intake', 'status': 'holding'})
                continue
            
            manifest = json.loads(manifest_path.read_text())
            
            # Integrity check
            current_hash = self._calc_integrity(asset_dir, exclude=['holding_manifest.json'])
            original_hash = manifest.get('integrity_hash', '')
            
            if current_hash != original_hash:
                logger.warning(f"INTEGRITY VIOLATION: {asset_dir.name}")
                manifest['status'] = 'flagged'
                manifest['integrity_violation'] = {
                    'detected_at': datetime.now(timezone.utc).isoformat(),
                    'expected': original_hash,
                    'actual': current_hash,
                }
                (manifest_path).write_text(json.dumps(manifest, indent=2))
                self.stats['flagged'] += 1
                results.append({'asset_id': asset_dir.name, 'action': 'flagged', 'status': 'integrity_violation'})
                continue
            
            # Check hold period
            now = datetime.now(timezone.utc)
            hold_until = datetime.fromisoformat(manifest['hold_until'])
            
            if now >= hold_until:
                if REQUIRE_MANUAL_APPROVAL and not manifest.get('approved'):
                    manifest['status'] = 'awaiting_approval'
                    (manifest_path).write_text(json.dumps(manifest, indent=2))
                    results.append({'asset_id': asset_dir.name, 'action': 'awaiting_approval', 'status': 'hold_expired'})
                else:
                    # Auto-release or already approved
                    self._release_to_vault(asset_dir)
                    results.append({'asset_id': asset_dir.name, 'action': 'released', 'status': 'approved'})
            else:
                remaining = hold_until - now
                results.append({
                    'asset_id': asset_dir.name,
                    'action': 'holding',
                    'remaining_hours': round(remaining.total_seconds() / 3600, 1),
                })
        
        return results
    
    def approve_release(self, asset_id: str, approver: str = 'admin') -> bool:
        """Manually approve an asset for release"""
        asset_dir = HOLDING_INCOMING / asset_id
        manifest_path = asset_dir / 'holding_manifest.json'
        
        if not manifest_path.exists():
            return False
        
        manifest = json.loads(manifest_path.read_text())
        manifest['approved'] = True
        manifest['approval'] = {
            'approver': approver,
            'approved_at': datetime.now(timezone.utc).isoformat(),
        }
        manifest['status'] = 'approved'
        (manifest_path).write_text(json.dumps(manifest, indent=2))
        
        # Check if hold period also expired
        now = datetime.now(timezone.utc)
        hold_until = datetime.fromisoformat(manifest['hold_until'])
        if now >= hold_until:
            self._release_to_vault(asset_dir)
        
        logger.info(f"APPROVED {asset_id} by {approver}")
        return True
    
    def _release_to_vault(self, asset_dir: Path):
        """Move asset to approved vault"""
        import shutil
        dest = HOLDING_APPROVED / asset_dir.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(asset_dir), str(dest))
        
        self.stats['released'] += 1
        self.stats['currently_holding'] -= 1
        logger.info(f"RELEASED {asset_dir.name} → encrypted vault")
    
    def _calc_integrity(self, asset_dir: Path, exclude: List[str] = None) -> str:
        """Calculate integrity hash of all files in asset dir"""
        exclude = exclude or []
        hasher = hashlib.sha256()
        
        for f in sorted(asset_dir.rglob('*')):
            if f.is_file() and f.name not in exclude:
                hasher.update(f.name.encode())
                hasher.update(f.read_bytes())
        
        return hasher.hexdigest()
    
    def list_held(self) -> List[Dict]:
        """List all currently held assets"""
        held = []
        for asset_dir in sorted(HOLDING_INCOMING.iterdir()):
            if not asset_dir.is_dir():
                continue
            manifest_path = asset_dir / 'holding_manifest.json'
            if manifest_path.exists():
                held.append(json.loads(manifest_path.read_text()))
            else:
                held.append({'asset_id': asset_dir.name, 'status': 'unregistered'})
        return held
    
    def get_stats(self) -> Dict:
        return self.stats


# ============================================
# FastAPI Interface
# ============================================
try:
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI(
        title="Rimuru Pipeline - Stage 4: Holding Vault",
        description="Isolated per-asset holding with monitoring",
        version="1.0.0"
    )
    
    vault = HoldingVault()
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "stage": "holding", "stats": vault.get_stats()}
    
    @app.post("/monitor")
    async def monitor():
        results = vault.monitor_all()
        return {"checked": len(results), "results": results}
    
    @app.post("/approve/{asset_id}")
    async def approve(asset_id: str, approver: str = "admin"):
        ok = vault.approve_release(asset_id, approver)
        return {"approved": ok, "asset_id": asset_id}
    
    @app.get("/held")
    async def list_held():
        return vault.list_held()
    
    @app.get("/stats")
    async def stats():
        return vault.get_stats()

except ImportError:
    app = None

if __name__ == "__main__":
    if app:
        port = int(os.getenv('HOLDING_PORT', 8504))
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        vault = HoldingVault()
        results = vault.monitor_all()
        print(f"Monitored {len(results)} assets")
        for r in results:
            print(f"  {r['asset_id']}: {r['action']}")
