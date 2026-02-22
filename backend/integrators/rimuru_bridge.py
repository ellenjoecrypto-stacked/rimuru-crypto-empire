#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Rimuru Bridge
Connects all microservices to the Rimuru AI Core.
Acts as the central nervous system feeding data to Rimuru's brain.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

try:
    from core.rimuru_ai import RimuruAICore
except ImportError:
    try:
        import sys
        _backend_path = str(Path(__file__).parent.parent)
        if _backend_path not in sys.path:
            sys.path.insert(0, _backend_path)
        from core.rimuru_ai import RimuruAICore
    except ImportError:
        RimuruAICore = None  # type: ignore[assignment,misc]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Module-level cached AI core instance so learned state is preserved between calls
_ai_core: Optional["RimuruAICore"] = None  # type: ignore[type-arg]


def _get_ai_core(model_path: str) -> Optional["RimuruAICore"]:  # type: ignore[type-arg]
    """Return a cached RimuruAICore instance, creating it on first call."""
    global _ai_core
    if _ai_core is None and RimuruAICore is not None:
        _ai_core = RimuruAICore(model_path=model_path)
    return _ai_core


class RimuruBridge:
    """
    Bridge that connects scanner, price engine, wallet checker,
    and trading bots to the Rimuru AI Core for unified intelligence.
    
    Data Flow:
        Scanner → findings → Bridge → Rimuru AI → Decisions
        Price Engine → prices → Bridge → Rimuru AI → Alerts
        Wallet Checker → balances → Bridge → Portfolio View
        Trading Bots ← Bridge ← Rimuru AI (decisions)
    """
    
    def __init__(self):
        self.data_dir = Path(os.getenv("DATA_DIR", "data"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Service endpoints (Docker service names)
        self.price_service_url = os.getenv("PRICE_SERVICE_URL", "http://price-service:8100")
        self.wallet_service_url = os.getenv("WALLET_SERVICE_URL", "http://wallet-service:8200")
        self.ai_service_url = os.getenv("AI_SERVICE_URL", "http://ai-service:8300")
        self.bot_service_url = os.getenv("BOT_SERVICE_URL", "http://bot-service:8400")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        
        # State
        self.scanner_findings = {}
        self.price_data = {}
        self.wallet_data = {}
        self.ai_decisions = []
        self.active_alerts = []
        
        # Knowledge DB
        self.db_path = self.data_dir / "rimuru_bridge.db"
        self._init_db()
        
        logger.info("🔗 Rimuru Bridge initialized")
    
    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS bridge_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source_service TEXT NOT NULL,
                data TEXT,
                processed BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS ai_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                risk_level TEXT,
                predicted_return REAL,
                executed BOOLEAN DEFAULT 0,
                outcome REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_usd REAL,
                positions TEXT,
                snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS learning_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_id INTEGER,
                outcome REAL,
                lesson TEXT,
                model_version TEXT,
                logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
    
    # ============================================
    # Data Ingestion from Services
    # ============================================
    
    async def ingest_scanner_findings(self, findings: Dict) -> Dict:
        """
        Ingest findings from the asset scanner.
        Enriches Rimuru's knowledge of discovered wallets and keys.
        """
        self.scanner_findings = findings
        
        summary = {
            "wallets_found": len(findings.get("wallets", [])),
            "api_keys_found": len(findings.get("api_keys", [])),
            "seeds_found": len(findings.get("seed_phrases", [])),
            "files_scanned": findings.get("files_scanned", 0),
            "ingested_at": datetime.now().isoformat()
        }
        
        # Log event
        self._log_event("scanner_findings", "scanner", json.dumps(summary))
        
        # Auto-track discovered wallets
        wallets = findings.get("wallets", [])
        for wallet in wallets:
            if wallet.get("type") == "eth" and len(wallet.get("address", "")) == 42:
                self._log_event("wallet_discovered", "scanner", json.dumps({
                    "address": wallet["address"],
                    "chain": "eth",
                    "source_file": wallet.get("file", "unknown")
                }))
        
        logger.info(f"📥 Ingested scanner findings: {summary['wallets_found']} wallets, {summary['api_keys_found']} keys")
        return summary
    
    async def ingest_price_data(self, prices: Dict) -> Dict:
        """
        Ingest live price data from price engine.
        Updates Rimuru's market awareness.
        """
        self.price_data = prices
        
        # Extract key metrics
        market_summary = {
            "coins_tracked": len(prices),
            "btc_price": prices.get("BTC", {}).get("price", 0),
            "eth_price": prices.get("ETH", {}).get("price", 0),
            "market_sentiment": self._assess_market_sentiment(prices),
            "updated_at": datetime.now().isoformat()
        }
        
        self._log_event("price_update", "price_engine", json.dumps(market_summary))
        
        # Check for significant moves
        alerts_triggered = self._check_price_alerts(prices)
        if alerts_triggered:
            self._log_event("price_alerts", "price_engine", json.dumps(alerts_triggered))
        
        logger.info(f"📊 Ingested price data: {market_summary['coins_tracked']} coins, BTC ${market_summary['btc_price']:,.2f}")
        return market_summary
    
    async def ingest_wallet_balances(self, balances: List[Dict]) -> Dict:
        """
        Ingest wallet balance data.
        Updates portfolio tracking.
        """
        self.wallet_data = {b["address"]: b for b in balances}
        
        total_usd = sum(b.get("balance_usd", 0) for b in balances)
        non_zero = [b for b in balances if b.get("balance", 0) > 0]
        
        portfolio = {
            "total_wallets": len(balances),
            "non_zero_wallets": len(non_zero),
            "total_usd": total_usd,
            "updated_at": datetime.now().isoformat()
        }
        
        # Save portfolio snapshot
        self._save_portfolio_snapshot(total_usd, balances)
        self._log_event("wallet_balances", "wallet_service", json.dumps(portfolio))
        
        logger.info(f"💰 Ingested wallet data: {len(non_zero)} active wallets, ${total_usd:,.2f} total")
        return portfolio
    
    # ============================================
    # AI Decision Pipeline
    # ============================================
    
    async def request_ai_decision(self, symbol: str, market_data: Dict = None, indicators: Dict = None) -> Dict:
        """
        Request trading decision from Rimuru AI Core.
        Combines all available data sources for maximum intelligence.
        """
        # Build context from all data sources
        context = self._build_ai_context(symbol, market_data, indicators)
        
        # Use local AI core (cached singleton)
        try:
            ai = _get_ai_core(str(self.data_dir / "ai_models"))
            
            if not market_data:
                market_data = {
                    "price": self.price_data.get(symbol, {}).get("price", 0),
                    "volume": self.price_data.get(symbol, {}).get("volume_24h", 0),
                    "change_24h": self.price_data.get(symbol, {}).get("change_24h", 0)
                }
            
            if not indicators:
                indicators = self._generate_basic_indicators(market_data)
            
            decision = await ai.make_decision(market_data, indicators)
            
            result = {
                "symbol": symbol,
                "action": decision.action,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "risk_assessment": decision.risk_assessment,
                "predicted_return": decision.predicted_return,
                "model_version": decision.model_version,
                "context_used": list(context.keys()),
                "timestamp": datetime.now().isoformat()
            }
            
            # Save decision
            self._save_decision(result)
            self.ai_decisions.append(result)
            
            logger.info(f"🧠 AI Decision for {symbol}: {decision.action.upper()} ({decision.confidence:.1%})")
            return result
            
        except Exception as e:
            logger.error(f"AI decision failed: {e}")
            return {
                "symbol": symbol,
                "action": "hold",
                "confidence": 0,
                "reasoning": f"Error: {str(e)}",
                "risk_assessment": "unknown",
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_full_analysis(self) -> Dict:
        """
        Run complete analysis pipeline:
        1. Gather all data
        2. Feed to Rimuru AI
        3. Generate decisions for top assets
        4. Create comprehensive report
        """
        logger.info("🚀 Running full Rimuru analysis pipeline...")
        
        report = {
            "pipeline_started": datetime.now().isoformat(),
            "stages": {}
        }
        
        # Stage 1: Scanner data
        scanner_db = self.data_dir / "crypto_findings.db"
        if scanner_db.exists():
            findings = self._load_scanner_db(str(scanner_db))
            stage1 = await self.ingest_scanner_findings(findings)
            report["stages"]["scanner"] = stage1
        
        # Stage 2: Price data
        try:
            from services.price_engine import PriceEngine
            
            engine = PriceEngine()
            prices = await engine.get_top_coins(25)
            price_dict = {p["symbol"]: p for p in prices}
            stage2 = await self.ingest_price_data(price_dict)
            report["stages"]["prices"] = stage2
        except Exception as e:
            logger.error(f"Price stage failed: {e}")
            report["stages"]["prices"] = {"error": str(e)}
        
        # Stage 3: AI Decisions for top coins
        decisions = []
        top_symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]
        for symbol in top_symbols:
            if symbol in self.price_data:
                decision = await self.request_ai_decision(symbol)
                decisions.append(decision)
                await asyncio.sleep(0.5)
        
        report["stages"]["ai_decisions"] = {
            "count": len(decisions),
            "decisions": decisions
        }
        
        # Stage 4: Summary
        report["pipeline_completed"] = datetime.now().isoformat()
        report["summary"] = {
            "wallets_tracked": len(self.wallet_data),
            "prices_monitored": len(self.price_data),
            "decisions_made": len(decisions),
            "alerts_active": len(self.active_alerts),
            "market_sentiment": self._assess_market_sentiment(self.price_data)
        }
        
        # Save report
        report_path = self.data_dir / "rimuru_analysis_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"✅ Full analysis complete → {report_path}")
        return report
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def _build_ai_context(self, symbol: str, market_data: Dict = None, indicators: Dict = None) -> Dict:
        context = {}
        if symbol in self.price_data:
            context["price"] = self.price_data[symbol]
        if market_data:
            context["market_data"] = market_data
        if indicators:
            context["indicators"] = indicators
        if self.scanner_findings:
            context["scanner_summary"] = {
                "wallets": len(self.scanner_findings.get("wallets", [])),
                "keys": len(self.scanner_findings.get("api_keys", []))
            }
        return context
    
    def _generate_basic_indicators(self, market_data: Dict) -> Dict:
        """Generate basic indicators when none provided"""
        price = market_data.get("price", 0)
        change = market_data.get("change_24h", 0)
        
        # Simple RSI approximation from 24h change
        rsi = 50 + (change * 2)
        rsi = max(0, min(100, rsi))
        
        return {
            "rsi": rsi,
            "macd": change * 10,
            "ma_fast": price * (1 + change / 200),
            "ma_slow": price * (1 - change / 200),
            "bb_upper": price * 1.02,
            "bb_lower": price * 0.98,
            "price": price
        }
    
    def _assess_market_sentiment(self, prices: Dict) -> str:
        if not prices:
            return "neutral"
        changes = [p.get("change_24h", 0) for p in prices.values() if isinstance(p, dict)]
        if not changes:
            return "neutral"
        avg_change = sum(changes) / len(changes)
        if avg_change > 3:
            return "very_bullish"
        elif avg_change > 1:
            return "bullish"
        elif avg_change < -3:
            return "very_bearish"
        elif avg_change < -1:
            return "bearish"
        return "neutral"
    
    def _check_price_alerts(self, prices: Dict) -> List[Dict]:
        triggered = []
        alert_thresholds = {
            "BTC": {"high": 100000, "low": 50000},
            "ETH": {"high": 5000, "low": 1500},
            "SOL": {"high": 300, "low": 50}
        }
        for symbol, thresholds in alert_thresholds.items():
            if symbol in prices:
                price = prices[symbol].get("price", 0)
                if price >= thresholds["high"]:
                    triggered.append({"symbol": symbol, "type": "high", "price": price, "threshold": thresholds["high"]})
                elif price <= thresholds["low"]:
                    triggered.append({"symbol": symbol, "type": "low", "price": price, "threshold": thresholds["low"]})
        self.active_alerts.extend(triggered)
        return triggered
    
    def _load_scanner_db(self, db_path: str) -> Dict:
        findings = {"wallets": [], "api_keys": [], "seed_phrases": [], "files_scanned": 0}
        try:
            conn = sqlite3.connect(db_path)
            wallets = conn.execute("SELECT address, type, source_file FROM wallets").fetchall()
            findings["wallets"] = [{"address": w[0], "type": w[1], "file": w[2]} for w in wallets]
            
            keys = conn.execute("SELECT key_type, key_value, source_file FROM api_keys").fetchall()
            findings["api_keys"] = [{"type": k[0], "value": k[1][:8] + "...", "file": k[2]} for k in keys]
            
            try:
                count = conn.execute("SELECT COUNT(*) FROM scan_files").fetchone()
                findings["files_scanned"] = count[0] if count else 0
            except Exception:
                pass
            
            conn.close()
        except Exception as e:
            logger.error(f"Failed to load scanner DB: {e}")
        return findings
    
    def _save_decision(self, decision: Dict):
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "INSERT INTO ai_decisions (symbol, action, confidence, reasoning, risk_level, predicted_return) VALUES (?, ?, ?, ?, ?, ?)",
                (decision["symbol"], decision["action"], decision["confidence"], decision["reasoning"], decision["risk_assessment"], decision.get("predicted_return", 0))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save decision: {e}")
    
    def _save_portfolio_snapshot(self, total_usd: float, positions: List[Dict]):
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "INSERT INTO portfolio_snapshots (total_usd, positions) VALUES (?, ?)",
                (total_usd, json.dumps(positions, default=str))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save portfolio snapshot: {e}")
    
    def _log_event(self, event_type: str, source: str, data: str):
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "INSERT INTO bridge_events (event_type, source_service, data) VALUES (?, ?, ?)",
                (event_type, source, data)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log event: {e}")
    
    def get_decision_history(self, limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(str(self.db_path))
        rows = conn.execute(
            "SELECT symbol, action, confidence, reasoning, risk_level, predicted_return, executed, outcome, created_at FROM ai_decisions ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [{
            "symbol": r[0], "action": r[1], "confidence": r[2], "reasoning": r[3],
            "risk_level": r[4], "predicted_return": r[5], "executed": bool(r[6]),
            "outcome": r[7], "created_at": r[8]
        } for r in rows]
    
    def get_system_status(self) -> Dict:
        return {
            "bridge": "active",
            "scanner_findings": bool(self.scanner_findings),
            "price_data_count": len(self.price_data),
            "wallet_data_count": len(self.wallet_data),
            "decisions_made": len(self.ai_decisions),
            "active_alerts": len(self.active_alerts),
            "timestamp": datetime.now().isoformat()
        }


# ============================================
# Standalone test
# ============================================

if __name__ == "__main__":
    async def test_bridge():
        logger.info("🔗 RIMURU BRIDGE TEST")
        logger.info("=" * 60)

        bridge = RimuruBridge()

        # Run full analysis
        report = await bridge.run_full_analysis()

        logger.info("\n📋 Analysis Summary:")
        summary = report.get("summary", {})
        for key, value in summary.items():
            logger.info(f"   {key}: {value}")

        decisions = report.get("stages", {}).get("ai_decisions", {}).get("decisions", [])
        if decisions:
            logger.info("\n🧠 AI Decisions:")
            for d in decisions:
                logger.info(f"   {d['symbol']}: {d['action'].upper()} ({d['confidence']:.1%}) - Risk: {d['risk_assessment']}")

        logger.info("\n✅ Bridge test complete!")
        logger.info(f"   Status: {bridge.get_system_status()}")

    asyncio.run(test_bridge())
