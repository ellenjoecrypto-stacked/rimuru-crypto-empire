#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Price Service API Gateway
==================================================
Standalone FastAPI service exposing the price engine via REST API.
Runs independently as a microservice on port 8100.

Endpoints:
  GET  /prices/{symbol}          - Get current price
  GET  /prices/batch             - Get multiple prices
  GET  /prices/top               - Top coins by market cap
  GET  /prices/history/{symbol}  - Price history
  GET  /gas                      - Ethereum gas prices
  GET  /wallet/{address}         - Wallet ETH balance
  POST /alerts                   - Create price alert
  GET  /alerts                   - List alerts
  GET  /portfolio                - Portfolio valuation
  POST /portfolio                - Update portfolio holdings
  GET  /health                   - Service health check
  WS   /ws/prices                - WebSocket live price stream
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import asdict

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from services.price_engine import PriceEngine, PriceAlert, AlertType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("price_api")

# ============================================================================
# APP SETUP
# ============================================================================

app = FastAPI(
    title="Rimuru Price Service",
    description="Real-time cryptocurrency price engine with multi-source aggregation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global engine instance
engine: Optional[PriceEngine] = None
ws_clients: List[WebSocket] = []
bg_task = None


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PriceResponse(BaseModel):
    symbol: str
    name: str = ""
    price_usd: float
    price_btc: float = 0
    volume_24h: float = 0
    market_cap: float = 0
    change_1h: float = 0
    change_24h: float = 0
    change_7d: float = 0
    change_30d: float = 0
    high_24h: float = 0
    low_24h: float = 0
    ath: float = 0
    rank: int = 0
    source: str = ""
    timestamp: str = ""


class BatchPriceRequest(BaseModel):
    symbols: List[str]


class AlertRequest(BaseModel):
    symbol: str
    alert_type: str  # "above", "below", "percent_change"
    threshold: float
    message: str = ""


class PortfolioRequest(BaseModel):
    holdings: Dict[str, float]  # {"BTC": 0.5, "ETH": 10}


class GasResponse(BaseModel):
    slow_gwei: float
    standard_gwei: float
    fast_gwei: float
    rapid_gwei: float
    base_fee_gwei: float
    estimated_cost_usd: Dict[str, float]
    timestamp: str


class WalletResponse(BaseModel):
    address: str
    balance_eth: float
    eth_price: float
    value_usd: float
    timestamp: str


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    uptime_seconds: float
    prices_cached: int
    sources_active: int
    timestamp: str


# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

_start_time = None


@app.on_event("startup")
async def startup():
    global engine, _start_time, bg_task
    _start_time = datetime.utcnow()
    
    db_path = os.environ.get(
        "PRICE_DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "..", "data", "prices.db")
    )
    etherscan_key = os.environ.get("ETHERSCAN_API_KEY", "")
    
    engine = PriceEngine(db_path=db_path, etherscan_key=etherscan_key)
    await engine.start()
    
    # Start background price updates
    bg_task = asyncio.create_task(background_updates())
    
    logger.info("Price service started on port 8100")


@app.on_event("shutdown")
async def shutdown():
    global engine, bg_task
    if bg_task:
        bg_task.cancel()
    if engine:
        await engine.stop()
    logger.info("Price service stopped")


async def background_updates():
    """Background task: update prices and push to WebSocket clients"""
    while True:
        try:
            if engine:
                prices = await engine.get_top_coins(25)
                
                # Push to WebSocket clients
                if ws_clients and prices:
                    data = json.dumps({
                        "type": "price_update",
                        "data": [asdict(p) for p in prices[:10]],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    })
                    dead = []
                    for ws in ws_clients:
                        try:
                            await ws.send_text(data)
                        except Exception:
                            dead.append(ws)
                    for ws in dead:
                        ws_clients.remove(ws)
            
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Background update error: {e}")
            await asyncio.sleep(60)


# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check"""
    uptime = (datetime.utcnow() - _start_time).total_seconds() if _start_time else 0
    return HealthResponse(
        status="healthy",
        service="rimuru-price-service",
        version="1.0.0",
        uptime_seconds=round(uptime, 1),
        prices_cached=len(engine._latest_prices) if engine else 0,
        sources_active=len(engine._adapters) if engine else 0,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/prices/{symbol}", response_model=PriceResponse)
async def get_price(symbol: str):
    """Get current price for a cryptocurrency"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    price = await engine.get_price(symbol.upper())
    if not price:
        raise HTTPException(404, f"Price not found for {symbol}")
    
    return PriceResponse(**{
        k: v for k, v in asdict(price).items()
        if k in PriceResponse.model_fields
    })


@app.get("/prices", response_model=List[PriceResponse])
async def get_prices_batch(
    symbols: str = Query(..., description="Comma-separated symbols, e.g. BTC,ETH,SOL")
):
    """Get prices for multiple symbols"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    prices = await engine.get_prices_batch(symbol_list)
    
    return [
        PriceResponse(**{k: v for k, v in asdict(p).items() if k in PriceResponse.model_fields})
        for p in prices.values()
    ]


@app.get("/prices/top/{limit}", response_model=List[PriceResponse])
async def get_top_coins(limit: int = 25):
    """Get top coins by market cap"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    prices = await engine.get_top_coins(min(limit, 250))
    
    return [
        PriceResponse(**{k: v for k, v in asdict(p).items() if k in PriceResponse.model_fields})
        for p in prices
    ]


@app.get("/prices/history/{symbol}")
async def get_price_history(symbol: str, hours: int = Query(24, ge=1, le=720)):
    """Get price history for a symbol"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    history = await engine.get_price_history(symbol.upper(), hours)
    return {"symbol": symbol.upper(), "hours": hours, "data": history}


@app.get("/gas", response_model=GasResponse)
async def get_gas_prices():
    """Get current Ethereum gas prices"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    gas = await engine.get_gas()
    if not gas:
        raise HTTPException(503, "Gas price unavailable")
    
    return GasResponse(**asdict(gas))


@app.get("/wallet/{address}", response_model=WalletResponse)
async def get_wallet_balance(address: str):
    """Get ETH wallet balance and USD value"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(400, "Invalid Ethereum address")
    
    result = await engine.get_wallet_value(address)
    return WalletResponse(**result)


@app.post("/alerts")
async def create_alert(req: AlertRequest):
    """Create a price alert"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    valid_types = ["above", "below", "percent_change", "volume_spike"]
    if req.alert_type not in valid_types:
        raise HTTPException(400, f"Invalid alert type. Use: {valid_types}")
    
    alert = engine.add_alert(req.symbol, req.alert_type, req.threshold, req.message)
    return {"status": "created", "alert": asdict(alert)}


@app.get("/alerts")
async def list_alerts():
    """List all price alerts"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    alerts = engine.get_alerts()
    return {
        "total": len(alerts),
        "triggered": sum(1 for a in alerts if a.triggered),
        "alerts": [asdict(a) for a in alerts],
    }


@app.post("/portfolio")
async def calculate_portfolio(req: PortfolioRequest):
    """Calculate portfolio value from holdings"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    summary = await engine.update_portfolio(req.holdings)
    return {
        "total_value_usd": summary.total_value_usd,
        "positions": [asdict(p) for p in summary.positions],
        "best_performer": summary.best_performer,
        "worst_performer": summary.worst_performer,
        "last_updated": summary.last_updated,
    }


# ============================================================================
# WEBSOCKET
# ============================================================================

@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    """WebSocket endpoint for live price streaming"""
    await websocket.accept()
    ws_clients.append(websocket)
    logger.info(f"WebSocket client connected ({len(ws_clients)} total)")
    
    try:
        # Send initial data
        if engine and engine._latest_prices:
            initial = json.dumps({
                "type": "initial",
                "data": {s: asdict(p) for s, p in list(engine._latest_prices.items())[:25]},
                "timestamp": datetime.utcnow().isoformat() + "Z",
            })
            await websocket.send_text(initial)
        
        # Keep connection alive, handle commands
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=300)
                cmd = json.loads(msg)
                
                if cmd.get("action") == "subscribe":
                    symbol = cmd.get("symbol", "").upper()
                    if engine and symbol:
                        price = await engine.get_price(symbol)
                        if price:
                            await websocket.send_text(json.dumps({
                                "type": "price",
                                "data": asdict(price),
                            }))
                
                elif cmd.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
                
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ws_clients:
            ws_clients.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_clients)} remaining)")


# ============================================================================
# COMPARISON & ANALYSIS ENDPOINTS
# ============================================================================

@app.get("/compare")
async def compare_prices(
    symbols: str = Query(..., description="Comma-separated, e.g. BTC,ETH,SOL")
):
    """Compare multiple cryptocurrencies side by side"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    prices = await engine.get_prices_batch(symbol_list)
    
    comparison = []
    for symbol in symbol_list:
        p = prices.get(symbol)
        if p:
            comparison.append({
                "symbol": p.symbol,
                "name": p.name,
                "price_usd": p.price_usd,
                "change_1h": p.change_1h,
                "change_24h": p.change_24h,
                "change_7d": p.change_7d,
                "change_30d": p.change_30d,
                "market_cap": p.market_cap,
                "volume_24h": p.volume_24h,
                "rank": p.rank,
                "volume_to_mcap_ratio": round(p.volume_24h / p.market_cap * 100, 2) if p.market_cap else 0,
            })
    
    return {
        "comparison": comparison,
        "best_24h": max(comparison, key=lambda x: x["change_24h"])["symbol"] if comparison else None,
        "worst_24h": min(comparison, key=lambda x: x["change_24h"])["symbol"] if comparison else None,
        "highest_volume": max(comparison, key=lambda x: x["volume_24h"])["symbol"] if comparison else None,
    }


@app.get("/market/overview")
async def market_overview():
    """Overall crypto market status"""
    if not engine:
        raise HTTPException(500, "Engine not initialized")
    
    prices = await engine.get_top_coins(50)
    
    if not prices:
        raise HTTPException(503, "Market data unavailable")
    
    total_mcap = sum(p.market_cap for p in prices)
    total_volume = sum(p.volume_24h for p in prices)
    avg_change = sum(p.change_24h for p in prices) / len(prices)
    
    gainers = sorted(prices, key=lambda p: p.change_24h, reverse=True)[:5]
    losers = sorted(prices, key=lambda p: p.change_24h)[:5]
    
    btc = next((p for p in prices if p.symbol == "BTC"), None)
    btc_dominance = (btc.market_cap / total_mcap * 100) if btc and total_mcap else 0
    
    return {
        "total_market_cap": round(total_mcap, 0),
        "total_volume_24h": round(total_volume, 0),
        "avg_change_24h": round(avg_change, 2),
        "btc_dominance": round(btc_dominance, 2),
        "btc_price": btc.price_usd if btc else 0,
        "eth_price": next((p.price_usd for p in prices if p.symbol == "ETH"), 0),
        "top_gainers": [
            {"symbol": p.symbol, "name": p.name, "change_24h": p.change_24h, "price": p.price_usd}
            for p in gainers
        ],
        "top_losers": [
            {"symbol": p.symbol, "name": p.name, "change_24h": p.change_24h, "price": p.price_usd}
            for p in losers
        ],
        "coins_tracked": len(prices),
        "market_sentiment": "bullish" if avg_change > 1 else ("bearish" if avg_change < -1 else "neutral"),
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PRICE_SERVICE_PORT", 8100))
    print(f"\n{'=' * 60}")
    print(f"  RIMURU PRICE SERVICE")
    print(f"  Starting on http://localhost:{port}")
    print(f"  Docs: http://localhost:{port}/docs")
    print(f"  WebSocket: ws://localhost:{port}/ws/prices")
    print(f"{'=' * 60}\n")
    
    uvicorn.run(
        "price_service:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
