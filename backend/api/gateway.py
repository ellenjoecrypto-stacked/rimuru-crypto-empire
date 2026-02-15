"""
API Gateway - FastAPI server for opportunity management and human approval workflow
Provides REST endpoints for reviewing, approving, and claiming crypto opportunities
"""

from fastapi import FastAPI, HTTPException, Depends, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session
import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any, Generator
from pydantic import BaseModel
import os

# Ensure aggregators directory is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "aggregators"))

from aggregators.opportunity_scanner import (
    OpportunityAggregator, 
    Opportunity, 
    OpportunityType,
    ApprovalStatus
)

# Logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Rimuru Opportunity Aggregator",
    description="Scan and manage crypto opportunities with human approval workflow",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rimuru_user:secure_password@localhost:5432/rimuru_opportunities"
)

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Global aggregator
aggregator = OpportunityAggregator(db_connection=engine)

# Pydantic Models
class OpportunityResponse(BaseModel):
    id: str
    title: str
    description: str
    type: str
    source: str
    estimated_value_usd: float
    total_supply: str
    claiming_deadline: Optional[str]
    requirement: str
    effort_level: str
    approval_status: str
    estimated_roi: float
    blockchain: str
    contract_address: Optional[str]
    url: str
    discovered_at: str
    class Config:
        from_attributes = True

class ApprovalRequest(BaseModel):
    opportunity_id: str
    operator: str
    status: str  # "approved" or "rejected"
    notes: Optional[str] = None

class ClaimRequest(BaseModel):
    opportunity_id: str
    claimed_by: str
    notes: Optional[str] = None
    tx_hash: Optional[str] = None
    amount_received: Optional[float] = None

class ScanRequest(BaseModel):
    scan_sources: Optional[List[str]] = None  # ["airdrops", "faucets", "whales"]

# Routes

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/opportunities")
async def list_opportunities(
    type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """List all opportunities with optional filtering"""
    
    try:
        # Filter opportunities
        filtered = aggregator.all_opportunities
        
        if type:
            filtered = [o for o in filtered if o.type.value == type]
        
        if status:
            filtered = [o for o in filtered if o.approval_status.value == status]
        
        # Apply pagination
        total = len(filtered)
        paginated = filtered[offset:offset+limit]
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "description": o.description,
                    "type": o.type.value,
                    "source": o.source,
                    "estimated_value_usd": o.estimated_value_usd,
                    "effort_level": o.effort_level,
                    "approval_status": o.approval_status.value,
                    "estimated_roi": o.estimated_roi,
                    "blockchain": o.blockchain,
                    "url": o.url,
                    "discovered_at": o.discovered_at
                }
                for o in paginated
            ]
        }
    except Exception as e:
        logger.error(f"Error listing opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/opportunities/{opportunity_id}")
async def get_opportunity(opportunity_id: str, db: Session = Depends(get_db)):
    """Get specific opportunity details"""
    
    try:
        for opp in aggregator.all_opportunities:
            if opp.id == opportunity_id:
                return {
                    "id": opp.id,
                    "title": opp.title,
                    "description": opp.description,
                    "type": opp.type.value,
                    "source": opp.source,
                    "estimated_value_usd": opp.estimated_value_usd,
                    "total_supply": opp.total_supply,
                    "claiming_deadline": opp.claiming_deadline,
                    "requirement": opp.requirement,
                    "effort_level": opp.effort_level,
                    "approval_status": opp.approval_status.value,
                    "estimated_roi": opp.estimated_roi,
                    "blockchain": opp.blockchain,
                    "contract_address": opp.contract_address,
                    "url": opp.url,
                    "discovered_at": opp.discovered_at,
                    "approved_by": opp.approved_by,
                    "approved_at": opp.approved_at,
                }
        
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    except Exception as e:
        logger.error(f"Error getting opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/opportunities/{opportunity_id}/approve")
async def approve_opportunity(
    opportunity_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """Approve opportunity for claiming"""
    
    try:
        success = aggregator.approve_opportunity(opportunity_id, request.operator)
        
        if not success:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        # Log to database
        logger.info(f"Opportunity {opportunity_id} approved by {request.operator}")
        
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "approved_by": request.operator,
            "approved_at": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error approving opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/opportunities/{opportunity_id}/reject")
async def reject_opportunity(
    opportunity_id: str,
    request: ApprovalRequest,
    db: Session = Depends(get_db)
):
    """Reject opportunity"""
    
    try:
        success = aggregator.reject_opportunity(opportunity_id, request.operator)
        
        if not success:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        logger.info(f"Opportunity {opportunity_id} rejected by {request.operator}")
        
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "rejected_by": request.operator,
            "rejected_at": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error rejecting opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/opportunities/{opportunity_id}/claim")
async def claim_opportunity(
    opportunity_id: str,
    request: ClaimRequest,
    db: Session = Depends(get_db)
):
    """Mark opportunity as claimed"""
    
    try:
        success = aggregator.mark_claimed(opportunity_id, request.notes or "")
        
        if not success:
            raise HTTPException(status_code=404, detail="Opportunity not found")
        
        logger.info(f"Opportunity {opportunity_id} claimed by {request.claimed_by}")
        
        return {
            "status": "success",
            "opportunity_id": opportunity_id,
            "claimed_by": request.claimed_by,
            "claimed_at": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error claiming opportunity: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/opportunities/pending/approval")
async def get_pending_approval(db: Session = Depends(get_db)):
    """Get all opportunities pending approval"""
    
    try:
        pending = aggregator.analyzer.get_pending_approval()
        
        return {
            "count": len(pending),
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "type": o.type.value,
                    "estimated_value_usd": o.estimated_value_usd,
                    "effort_level": o.effort_level,
                    "estimated_roi": o.estimated_roi,
                    "url": o.url
                }
                for o in pending
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting pending approvals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/opportunities/top")
async def get_top_opportunities(
    limit: int = Query(10, le=100),
    db: Session = Depends(get_db)
):
    """Get top opportunities by score"""
    
    try:
        top = aggregator.analyzer.get_top_opportunities(limit)
        
        return {
            "count": len(top),
            "opportunities": [
                {
                    "id": o.id,
                    "title": o.title,
                    "type": o.type.value,
                    "estimated_value_usd": o.estimated_value_usd,
                    "effort_level": o.effort_level,
                    "estimated_roi": o.estimated_roi,
                    "url": o.url
                }
                for o in top
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting top opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/statistics")
async def get_statistics(db: Session = Depends(get_db)):
    """Get aggregated statistics"""
    
    try:
        total = len(aggregator.all_opportunities)
        by_type = aggregator._count_by_type()
        approved = len(aggregator.analyzer.get_approved())
        pending = len(aggregator.analyzer.get_pending_approval())
        
        total_value = sum(o.estimated_value_usd for o in aggregator.all_opportunities)
        avg_roi = sum(o.estimated_roi for o in aggregator.all_opportunities) / total if total > 0 else 0
        
        return {
            "total_opportunities": total,
            "by_type": by_type,
            "approved_count": approved,
            "pending_count": pending,
            "total_estimated_value_usd": round(total_value, 2),
            "average_roi": round(avg_roi, 4)
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scan")
async def start_scan(request: ScanRequest):
    """Trigger full opportunity scan"""
    
    try:
        logger.info("Starting opportunity scan...")
        
        results = await aggregator.run_full_scan()
        
        return {
            "status": "success",
            "scan_results": results
        }
        
    except Exception as e:
        logger.error(f"Error during scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/export")
async def export_opportunities():
    """Export all opportunities as JSON"""
    
    try:
        json_data = aggregator.export_json()
        
        return JSONResponse(
            content=json_data,
            headers={
                "Content-Disposition": "attachment; filename=opportunities.json"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    logger.info("Rimuru Opportunity Aggregator API started")
    
    # Optional: Run initial scan on startup
    # asyncio.create_task(aggregator.run_full_scan())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info"
    )
