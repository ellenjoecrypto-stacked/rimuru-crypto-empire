#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - AI Service API
FastAPI standalone service for Rimuru AI Core.
Provides AI trading decisions, learning, and Ollama integration.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# Models
# ============================================

class MarketData(BaseModel):
    price: float
    volume: float = 0
    change_24h: float = 0

class Indicators(BaseModel):
    rsi: float = 50
    macd: float = 0
    ma_fast: float = 0
    ma_slow: float = 0
    bb_upper: float = 0
    bb_lower: float = 0

class DecisionRequest(BaseModel):
    symbol: str
    market_data: MarketData
    indicators: Optional[Indicators] = None

class LearningInput(BaseModel):
    decision_action: str
    confidence: float
    outcome: float

class OllamaQuery(BaseModel):
    prompt: str
    model: str = "llama2"

# ============================================
# App
# ============================================

app = FastAPI(
    title="Rimuru AI Service",
    description="Self-learning AI core with Ollama integration for crypto trading decisions",
    version="1.0.0"
)

# Lazy-load AI core
_ai_core = None

def get_ai_core():
    global _ai_core
    if _ai_core is None:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.rimuru_ai import RimuruAICore
        _ai_core = RimuruAICore(model_path=os.getenv("AI_MODEL_PATH", "data/ai_models"))
    return _ai_core

# ============================================
# Endpoints
# ============================================

@app.get("/health")
async def health():
    ai = get_ai_core()
    ollama = await ai.check_ollama_connection()
    return {
        "status": "healthy",
        "service": "ai-service",
        "model_trained": ai.model_trained,
        "ollama_connected": ollama,
        "performance": ai.get_performance_stats(),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/decide")
async def make_decision(req: DecisionRequest):
    """Get AI trading decision for a symbol"""
    ai = get_ai_core()
    
    market_data = {
        "price": req.market_data.price,
        "volume": req.market_data.volume,
        "change_24h": req.market_data.change_24h
    }
    
    indicators = {}
    if req.indicators:
        indicators = {
            "rsi": req.indicators.rsi,
            "macd": req.indicators.macd,
            "ma_fast": req.indicators.ma_fast,
            "ma_slow": req.indicators.ma_slow,
            "bb_upper": req.indicators.bb_upper,
            "bb_lower": req.indicators.bb_lower
        }
    else:
        # Generate basic indicators
        price = market_data["price"]
        change = market_data["change_24h"]
        indicators = {
            "rsi": max(0, min(100, 50 + change * 2)),
            "macd": change * 10,
            "ma_fast": price * (1 + change / 200),
            "ma_slow": price * (1 - change / 200),
            "bb_upper": price * 1.02,
            "bb_lower": price * 0.98
        }
    
    decision = await ai.make_decision(market_data, indicators)
    
    return {
        "symbol": req.symbol,
        "action": decision.action,
        "confidence": decision.confidence,
        "reasoning": decision.reasoning,
        "risk_assessment": decision.risk_assessment,
        "predicted_return": decision.predicted_return,
        "model_version": decision.model_version,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/learn")
async def learn_outcome(input: LearningInput):
    """Feed trade outcome back to AI for learning"""
    ai = get_ai_core()
    
    from core.rimuru_ai import AIDecision
    decision = AIDecision(
        action=input.decision_action,
        confidence=input.confidence,
        reasoning="",
        risk_assessment="",
        predicted_return=0,
        model_version="1.0"
    )
    
    ai.learn_from_outcome(decision, input.outcome)
    stats = ai.get_performance_stats()
    
    return {
        "learned": True,
        "stats": stats,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/stats")
async def get_stats():
    """Get AI performance statistics"""
    ai = get_ai_core()
    return {
        "performance": ai.get_performance_stats(),
        "knowledge_base_size": len(ai.knowledge_base.get("lessons", [])),
        "timestamp": datetime.now().isoformat()
    }

@app.post("/ollama/query")
async def query_ollama(query: OllamaQuery):
    """Query Ollama LLM directly"""
    ai = get_ai_core()
    
    connected = await ai.check_ollama_connection()
    if not connected:
        raise HTTPException(status_code=503, detail="Ollama not connected")
    
    # Temporarily set model
    original_model = ai.ollama_model
    ai.ollama_model = query.model
    
    response = await ai.query_ollama(query.prompt)
    
    ai.ollama_model = original_model
    
    return {
        "model": query.model,
        "response": response,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/ollama/analyze")
async def analyze_market(req: DecisionRequest):
    """Use Ollama to analyze market data"""
    ai = get_ai_core()
    
    market_data = {
        "price": req.market_data.price,
        "volume": req.market_data.volume,
        "change_24h": req.market_data.change_24h
    }
    
    indicators = {}
    if req.indicators:
        indicators = {
            "rsi": req.indicators.rsi,
            "macd": req.indicators.macd,
            "ma_fast": req.indicators.ma_fast,
            "ma_slow": req.indicators.ma_slow,
            "bb_upper": req.indicators.bb_upper,
            "bb_lower": req.indicators.bb_lower
        }
    
    analysis = await ai.analyze_with_ollama(market_data, indicators)
    
    return {
        "symbol": req.symbol,
        "analysis": analysis,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/knowledge/save")
async def save_knowledge():
    """Save AI knowledge base"""
    ai = get_ai_core()
    ai.save_knowledge()
    return {"saved": True, "timestamp": datetime.now().isoformat()}

@app.get("/ollama/status")
async def ollama_status():
    """Check Ollama connection and available models"""
    ai = get_ai_core()
    connected = await ai.check_ollama_connection()
    
    models = []
    if connected:
        try:
            import requests
            resp = requests.get(f"{ai.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
        except:
            pass
    
    return {
        "connected": connected,
        "url": ai.ollama_url,
        "default_model": ai.ollama_model,
        "available_models": models,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    port = int(os.getenv("AI_SERVICE_PORT", "8300"))
    print(f"🧠 Rimuru AI Service starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
