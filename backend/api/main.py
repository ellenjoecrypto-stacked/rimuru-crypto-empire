#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Main API Server
FastAPI backend with WebSocket support for real-time updates
"""

import asyncio
import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import uvicorn

from ..core.exchange_manager import ExchangeManager, ExchangeConfig, ExchangeType
from ..core.risk_manager import RiskManager, RiskConfig
from ..bots.base_bot import BotManager, BaseBot
from ..bots.spot_trader import SpotTradingBot, SpotTradingConfig, TradingStrategy
from ..security.credential_vault import CredentialVault, Credential

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Rimuru Crypto Empire API",
    description="Comprehensive cryptocurrency automation platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Global instances
exchange_manager = ExchangeManager()
bot_manager = BotManager()
bot_manager.set_exchange_manager(exchange_manager)
risk_manager = RiskManager(RiskConfig())
credential_vault = CredentialVault()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

# Pydantic models
class ExchangeAddRequest(BaseModel):
    name: str
    exchange_type: str
    api_key: str
    secret_key: str
    passphrase: Optional[str] = None
    sandbox: bool = True

class BotCreateRequest(BaseModel):
    name: str
    exchange: str
    symbol: str
    strategy: str
    paper_trading: bool = True

class BotControlRequest(BaseModel):
    action: str  # start, stop, pause, resume

# Background task for real-time updates
async def background_updater():
    """Background task to send real-time updates"""
    while True:
        try:
            # Broadcast bot status
            bot_status = bot_manager.get_all_status()
            await manager.broadcast({
                "type": "bot_status",
                "data": bot_status
            })
            
            # Broadcast risk summary
            risk_summary = risk_manager.get_risk_summary()
            await manager.broadcast({
                "type": "risk_summary",
                "data": risk_summary
            })
            
            await asyncio.sleep(5)  # Update every 5 seconds
            
        except Exception as e:
            logger.error(f"❌ Error in background updater: {e}")
            await asyncio.sleep(10)

# API Routes

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Rimuru Crypto Empire API",
        "version": "1.0.0",
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "exchanges": len(exchange_manager.exchanges),
        "bots": len(bot_manager.bots)
    }

# Exchange endpoints

@app.post("/api/exchanges/add")
async def add_exchange(request: ExchangeAddRequest):
    """Add a new exchange connection"""
    try:
        config = ExchangeConfig(
            exchange_type=ExchangeType(request.exchange_type),
            api_key=request.api_key,
            secret_key=request.secret_key,
            passphrase=request.passphrase,
            sandbox=request.sandbox
        )
        
        success = await exchange_manager.add_exchange(request.name, config)
        
        if success:
            return {"status": "success", "message": f"Exchange '{request.name}' added successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to add exchange")
            
    except Exception as e:
        logger.error(f"❌ Error adding exchange: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/exchanges")
async def list_exchanges():
    """List all connected exchanges"""
    exchanges = []
    for name in exchange_manager.exchanges.keys():
        info = exchange_manager.get_exchange_info(name)
        if info:
            exchanges.append(info)
    return {"exchanges": exchanges}

@app.delete("/api/exchanges/{name}")
async def remove_exchange(name: str):
    """Remove an exchange connection"""
    success = await exchange_manager.remove_exchange(name)
    if success:
        return {"status": "success", "message": f"Exchange '{name}' removed"}
    else:
        raise HTTPException(status_code=404, detail="Exchange not found")

@app.get("/api/exchanges/{name}/balance")
async def get_balance(name: str):
    """Get account balance for an exchange"""
    balances = await exchange_manager.get_balance(name)
    return {"exchange": name, "balances": balances}

@app.get("/api/exchanges/{name}/ticker/{symbol}")
async def get_ticker(name: str, symbol: str):
    """Get ticker for a symbol"""
    ticker = await exchange_manager.get_ticker(name, symbol)
    if ticker:
        return {
            "exchange": name,
            "symbol": symbol,
            "last_price": ticker.last_price,
            "bid_price": ticker.bid_price,
            "ask_price": ticker.ask_price,
            "volume_24h": ticker.volume_24h
        }
    else:
        raise HTTPException(status_code=404, detail="Ticker not found")

# Bot endpoints

@app.post("/api/bots/create")
async def create_bot(request: BotCreateRequest):
    """Create a new trading bot"""
    try:
        config = SpotTradingConfig(
            name=request.name,
            bot_type=bot_manager.bots[request.name].config.bot_type if request.name in bot_manager.bots else None,
            exchange=request.exchange,
            symbol=request.symbol,
            strategy=TradingStrategy(request.strategy),
            paper_trading=request.paper_trading
        )
        
        bot = SpotTradingBot(config, exchange_manager)
        bot_manager.add_bot(bot)
        
        return {"status": "success", "message": f"Bot '{request.name}' created successfully"}
        
    except Exception as e:
        logger.error(f"❌ Error creating bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bots")
async def list_bots():
    """List all bots"""
    return {"bots": bot_manager.get_all_status()}

@app.post("/api/bots/{name}/control")
async def control_bot(name: str, request: BotControlRequest):
    """Control a bot (start, stop, pause, resume)"""
    try:
        if request.action == "start":
            success = await bot_manager.start_bot(name)
        elif request.action == "stop":
            success = await bot_manager.stop_bot(name)
        elif request.action == "pause":
            success = await bot_manager.bots[name].pause()
        elif request.action == "resume":
            success = await bot_manager.bots[name].resume()
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
        
        if success:
            return {"status": "success", "message": f"Bot '{name}' {request.action}ed"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to {request.action} bot")
            
    except KeyError:
        raise HTTPException(status_code=404, detail="Bot not found")
    except Exception as e:
        logger.error(f"❌ Error controlling bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bots/{name}/status")
async def get_bot_status(name: str):
    """Get bot status"""
    if name in bot_manager.bots:
        return bot_manager.bots[name].get_status()
    else:
        raise HTTPException(status_code=404, detail="Bot not found")

# Risk management endpoints

@app.get("/api/risk/summary")
async def get_risk_summary():
    """Get risk management summary"""
    return risk_manager.get_risk_summary()

@app.post("/api/risk/emergency-stop")
async def emergency_stop(reason: str = "Manual trigger"):
    """Trigger emergency stop"""
    risk_manager.trigger_emergency_stop(reason)
    return {"status": "success", "message": "Emergency stop triggered"}

@app.post("/api/risk/reset-emergency")
async def reset_emergency_stop():
    """Reset emergency stop"""
    risk_manager.reset_emergency_stop()
    return {"status": "success", "message": "Emergency stop reset"}

# Credential management endpoints

@app.post("/api/credentials/store")
async def store_credential(
    exchange: str,
    api_key: str,
    secret_key: str,
    passphrase: Optional[str] = None
):
    """Store encrypted credential"""
    try:
        credential = Credential(
            exchange=exchange,
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase
        )
        
        success = credential_vault.store_credential(credential)
        
        if success:
            return {"status": "success", "message": "Credential stored securely"}
        else:
            raise HTTPException(status_code=500, detail="Failed to store credential")
            
    except Exception as e:
        logger.error(f"❌ Error storing credential: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/credentials")
async def list_credentials():
    """List stored credentials (without exposing secrets)"""
    exchanges = credential_vault.list_exchanges()
    return {"exchanges": exchanges}

@app.get("/api/credentials/audit-log")
async def get_audit_log(limit: int = 100):
    """Get credential access audit log"""
    logs = credential_vault.get_audit_log(limit)
    return {"audit_log": logs}

# WebSocket endpoint

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Startup and shutdown events

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks"""
    logger.info("🚀 Starting Rimuru Crypto Empire API")
    
    # Start background updater
    asyncio.create_task(background_updater())
    
    logger.info("✅ API server started successfully")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("🛑 Shutting down Rimuru Crypto Empire API")
    await exchange_manager.close_all_connections()
    await bot_manager.stop_all_bots()
    logger.info("✅ Shutdown complete")

# Run server
if __name__ == "__main__":
    print("🚀 RIMURU CRYPTO EMPIRE - API SERVER")
    print("=" * 60)
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )