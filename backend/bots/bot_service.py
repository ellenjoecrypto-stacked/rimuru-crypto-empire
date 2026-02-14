#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Trading Bot Service
Standalone service for automated trading, farming, and collection bots.
Enhanced with SuperNinja automation patterns.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# Models
# ============================================

class BotConfig(BaseModel):
    bot_type: str  # "spot_trader", "farmer", "collector", "sniper"
    symbol: str = "BTC/USDT"
    exchange: str = "kraken"
    strategy: str = "conservative"
    max_position_usd: float = 100.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    enabled: bool = False  # Safety: disabled by default

class BotStatus(BaseModel):
    bot_id: str
    bot_type: str
    status: str
    symbol: str
    exchange: str
    pnl: float
    trades: int
    uptime_seconds: float

class TradeSignal(BaseModel):
    symbol: str
    action: str  # buy, sell
    price: float
    quantity: float
    confidence: float
    source: str  # ai, manual, strategy

# ============================================
# Bot Engine
# ============================================

class BotEngine:
    """
    Manages multiple trading bots with safety controls.
    All bots require explicit enable + human approval before executing trades.
    """
    
    def __init__(self):
        self.bots: Dict[str, Dict] = {}
        self.signals: List[Dict] = []
        self.trade_log: List[Dict] = []
        self.human_approval_required = True  # Safety first
        self.data_dir = Path(os.getenv("BOT_DATA_DIR", "data/bots"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Bot templates from SuperNinja spec
        self.bot_templates = {
            "spot_trader": {
                "description": "Spot market trader with configurable strategy",
                "strategies": ["conservative", "moderate", "aggressive"],
                "requires_exchange_key": True
            },
            "farmer": {
                "description": "DeFi yield farming bot - auto-compounds rewards",
                "strategies": ["stable_yield", "high_risk_farm", "liquidity_provision"],
                "requires_exchange_key": True
            },
            "collector": {
                "description": "Automated airdrop/faucet collector",
                "strategies": ["airdrop_hunter", "faucet_collector", "reward_claimer"],
                "requires_exchange_key": False
            },
            "sniper": {
                "description": "New listing sniper bot",
                "strategies": ["dex_sniper", "cex_listing", "token_launch"],
                "requires_exchange_key": True
            },
            "dca": {
                "description": "Dollar cost averaging bot",
                "strategies": ["daily", "weekly", "volatility_adjusted"],
                "requires_exchange_key": True
            },
            "arbitrage": {
                "description": "Cross-exchange arbitrage scanner",
                "strategies": ["spot_arb", "triangular", "dex_cex"],
                "requires_exchange_key": True
            }
        }
        
        logger.info(f"🤖 Bot Engine initialized with {len(self.bot_templates)} bot templates")
    
    def create_bot(self, config: BotConfig) -> Dict:
        """Create a new bot instance (does NOT start it without approval)"""
        bot_id = f"{config.bot_type}_{config.symbol.replace('/', '_')}_{len(self.bots)}"
        
        if config.bot_type not in self.bot_templates:
            return {"error": f"Unknown bot type: {config.bot_type}", "available": list(self.bot_templates.keys())}
        
        bot = {
            "bot_id": bot_id,
            "config": config.dict(),
            "status": "created",  # created → pending_approval → running → stopped
            "created_at": datetime.now().isoformat(),
            "pnl": 0.0,
            "trades": 0,
            "signals_received": 0,
            "last_signal": None,
            "approval_status": "pending" if self.human_approval_required else "approved"
        }
        
        self.bots[bot_id] = bot
        self._save_bot_state()
        
        logger.info(f"🤖 Bot created: {bot_id} ({config.bot_type}) - Awaiting approval")
        return bot
    
    def approve_bot(self, bot_id: str) -> Dict:
        """Human approval to allow bot to trade"""
        if bot_id not in self.bots:
            return {"error": f"Bot not found: {bot_id}"}
        
        self.bots[bot_id]["approval_status"] = "approved"
        self.bots[bot_id]["status"] = "approved"
        self.bots[bot_id]["approved_at"] = datetime.now().isoformat()
        self._save_bot_state()
        
        logger.info(f"✅ Bot approved: {bot_id}")
        return self.bots[bot_id]
    
    def start_bot(self, bot_id: str) -> Dict:
        """Start an approved bot"""
        if bot_id not in self.bots:
            return {"error": f"Bot not found: {bot_id}"}
        
        bot = self.bots[bot_id]
        if bot["approval_status"] != "approved":
            return {"error": f"Bot not approved. Current status: {bot['approval_status']}"}
        
        if not bot["config"].get("enabled", False):
            return {"error": "Bot is disabled. Set enabled=true in config."}
        
        bot["status"] = "running"
        bot["started_at"] = datetime.now().isoformat()
        self._save_bot_state()
        
        logger.info(f"▶️ Bot started: {bot_id}")
        return bot
    
    def stop_bot(self, bot_id: str) -> Dict:
        """Stop a running bot"""
        if bot_id not in self.bots:
            return {"error": f"Bot not found: {bot_id}"}
        
        self.bots[bot_id]["status"] = "stopped"
        self.bots[bot_id]["stopped_at"] = datetime.now().isoformat()
        self._save_bot_state()
        
        logger.info(f"⏹️ Bot stopped: {bot_id}")
        return self.bots[bot_id]
    
    def process_signal(self, bot_id: str, signal: TradeSignal) -> Dict:
        """Process a trade signal for a bot"""
        if bot_id not in self.bots:
            return {"error": f"Bot not found: {bot_id}"}
        
        bot = self.bots[bot_id]
        
        if bot["status"] != "running":
            return {"error": f"Bot not running. Status: {bot['status']}"}
        
        # Record signal
        signal_data = {
            "bot_id": bot_id,
            "signal": signal.dict(),
            "received_at": datetime.now().isoformat(),
            "executed": False,
            "reason": ""
        }
        
        # Safety checks
        max_position = bot["config"].get("max_position_usd", 100)
        trade_value = signal.price * signal.quantity
        
        if trade_value > max_position:
            signal_data["reason"] = f"Trade value ${trade_value:.2f} exceeds max position ${max_position:.2f}"
            self.signals.append(signal_data)
            return {"status": "rejected", "reason": signal_data["reason"]}
        
        if signal.confidence < 0.6:
            signal_data["reason"] = f"Low confidence: {signal.confidence:.1%}"
            self.signals.append(signal_data)
            return {"status": "rejected", "reason": signal_data["reason"]}
        
        # In production: execute trade via exchange API
        # For now: log as simulated
        signal_data["executed"] = True
        signal_data["reason"] = "Simulated execution (paper trading)"
        
        bot["signals_received"] += 1
        bot["last_signal"] = signal_data
        bot["trades"] += 1
        
        self.signals.append(signal_data)
        self.trade_log.append({
            "bot_id": bot_id,
            "action": signal.action,
            "symbol": signal.symbol,
            "price": signal.price,
            "quantity": signal.quantity,
            "value_usd": trade_value,
            "simulated": True,
            "timestamp": datetime.now().isoformat()
        })
        
        self._save_bot_state()
        
        logger.info(f"📊 Signal processed: {bot_id} - {signal.action} {signal.symbol} @ ${signal.price}")
        return {"status": "executed_simulated", "trade": self.trade_log[-1]}
    
    def get_all_bots(self) -> List[Dict]:
        return list(self.bots.values())
    
    def get_bot(self, bot_id: str) -> Optional[Dict]:
        return self.bots.get(bot_id)
    
    def get_trade_log(self, bot_id: str = None, limit: int = 50) -> List[Dict]:
        if bot_id:
            return [t for t in self.trade_log if t["bot_id"] == bot_id][-limit:]
        return self.trade_log[-limit:]
    
    def _save_bot_state(self):
        try:
            state_file = self.data_dir / "bot_state.json"
            with open(state_file, "w") as f:
                json.dump({
                    "bots": self.bots,
                    "trade_count": len(self.trade_log),
                    "saved_at": datetime.now().isoformat()
                }, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save bot state: {e}")


# ============================================
# FastAPI Bot Service
# ============================================

app = FastAPI(
    title="Rimuru Bot Service",
    description="Automated trading, farming, and collection bots with human approval workflow",
    version="1.0.0"
)

engine = BotEngine()

@app.get("/health")
async def health():
    running = [b for b in engine.bots.values() if b["status"] == "running"]
    return {
        "status": "healthy",
        "service": "bot-service",
        "total_bots": len(engine.bots),
        "running_bots": len(running),
        "total_trades": len(engine.trade_log),
        "human_approval_required": engine.human_approval_required,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/templates")
async def get_templates():
    """Get available bot templates"""
    return engine.bot_templates

@app.get("/bots")
async def list_bots():
    """List all bots"""
    return engine.get_all_bots()

@app.get("/bots/{bot_id}")
async def get_bot(bot_id: str):
    """Get bot details"""
    bot = engine.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot

@app.post("/bots")
async def create_bot(config: BotConfig):
    """Create a new bot (requires approval before running)"""
    result = engine.create_bot(config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/bots/{bot_id}/approve")
async def approve_bot(bot_id: str):
    """Approve bot for trading"""
    result = engine.approve_bot(bot_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/bots/{bot_id}/start")
async def start_bot(bot_id: str):
    """Start an approved bot"""
    result = engine.start_bot(bot_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/bots/{bot_id}/stop")
async def stop_bot(bot_id: str):
    """Stop a running bot"""
    result = engine.stop_bot(bot_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.post("/bots/{bot_id}/signal")
async def send_signal(bot_id: str, signal: TradeSignal):
    """Send a trade signal to a bot"""
    result = engine.process_signal(bot_id, signal)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/trades")
async def get_trades(bot_id: str = None, limit: int = 50):
    """Get trade log"""
    return engine.get_trade_log(bot_id, limit)


if __name__ == "__main__":
    port = int(os.getenv("BOT_SERVICE_PORT", "8400"))
    print(f"🤖 Rimuru Bot Service starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
