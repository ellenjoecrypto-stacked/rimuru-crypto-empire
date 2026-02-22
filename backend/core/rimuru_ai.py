#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Rimuru AI Core
Self-learning AI system with Ollama integration
"""

import asyncio
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import numpy as np

try:
    import requests
    import pandas as pd
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
except ImportError as e:
    raise ImportError(
        f"Required ML libraries not installed. Run: pip install scikit-learn pandas numpy requests\n{e}"
    ) from e

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class LearningData:
    """Data point for learning"""
    features: List[float]
    label: int  # 0: no action, 1: buy, 2: sell
    outcome: float  # PnL from following the signal
    timestamp: datetime
    confidence: float

@dataclass
class AIDecision:
    """AI decision result"""
    action: str  # 'buy', 'sell', 'hold'
    confidence: float
    reasoning: str
    risk_assessment: str
    predicted_return: float
    model_version: str

class RimuruAICore:
    """
    Self-learning AI core for cryptocurrency trading
    
    Features:
    - Machine learning models for signal generation
    - Pattern recognition in market data
    - Strategy optimization based on performance
    - Risk assessment integration
    - Continuous learning from outcomes
    - Ollama integration for advanced AI reasoning
    """
    
    def __init__(self, model_path: str = "data/ai_models"):
        self.model_path = Path(model_path)
        self.model_path.mkdir(parents=True, exist_ok=True)
        
        # ML models
        self.signal_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.model_trained = False
        
        # Learning data
        self.learning_data: List[LearningData] = []
        self.performance_history: List[Dict] = []
        
        # Ollama configuration
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "llama2"  # Default model
        
        # Knowledge base
        self.knowledge_base = {
            'strategies': {},
            'patterns': {},
            'lessons': []
        }
        
        logger.info("🧠 Rimuru AI Core initialized")
        self._model_version = "1.0"
        self._last_features: List[float] = []
        self.load_knowledge()
    
    async def check_ollama_connection(self) -> bool:
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            logger.warning("⚠️ Ollama not connected. Using local ML models only.")
            return False
    
    async def query_ollama(self, prompt: str) -> str:
        """
        Query Ollama for advanced AI reasoning
        
        Args:
            prompt: Input prompt for Ollama
            
        Returns:
            Ollama response text
        """
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '')
            else:
                logger.error(f"❌ Ollama query failed: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"❌ Error querying Ollama: {e}")
            return ""
    
    async def analyze_with_ollama(self, market_data: Dict, indicators: Dict) -> str:
        """
        Use Ollama to analyze market conditions
        
        Args:
            market_data: Current market data
            indicators: Technical indicators
            
        Returns:
            AI analysis and recommendation
        """
        prompt = f"""
        Analyze the following cryptocurrency market data and provide trading advice:
        
        Current Price: ${market_data.get('price', 0):,.2f}
        24h Volume: ${market_data.get('volume', 0):,.2f}
        Price Change (24h): {market_data.get('change_24h', 0):.2f}%
        
        Technical Indicators:
        - RSI: {indicators.get('rsi', 0):.2f}
        - MACD: {indicators.get('macd', 0):.2f}
        - Moving Average (Fast): ${indicators.get('ma_fast', 0):,.2f}
        - Moving Average (Slow): ${indicators.get('ma_slow', 0):,.2f}
        - Bollinger Upper: ${indicators.get('bb_upper', 0):,.2f}
        - Bollinger Lower: ${indicators.get('bb_lower', 0):,.2f}
        
        Provide a brief analysis (2-3 sentences) with a recommendation (BUY, SELL, or HOLD) and your confidence level.
        """
        
        return await self.query_ollama(prompt)
    
    def extract_features(self, market_data: Dict, indicators: Dict) -> List[float]:
        """
        Extract features for ML model
        
        Args:
            market_data: Market data
            indicators: Technical indicators
            
        Returns:
            Feature vector
        """
        features = [
            indicators.get('rsi', 50) / 100,  # Normalize RSI to 0-1
            indicators.get('macd', 0) / 1000,  # Normalize MACD
            (indicators.get('ma_fast', 0) - indicators.get('ma_slow', 0)) / indicators.get('ma_slow', 1),  # MA difference
            (indicators.get('bb_upper', 0) - indicators.get('price', 0)) / indicators.get('price', 1),  # Distance from BB upper
            market_data.get('volume', 0) / 1e9,  # Normalize volume
            market_data.get('change_24h', 0) / 100,  # Normalize price change
        ]

        self._last_features = features
        return features
    
    def train_model(self, data: List[LearningData]) -> bool:
        """
        Train the ML model on historical data
        
        Args:
            data: Learning data with features and labels
            
        Returns:
            Success status
        """
        try:
            if len(data) < 100:
                logger.warning("⚠️ Not enough data to train model (need at least 100 samples)")
                return False
            
            # Extract features and labels
            X = np.array([d.features for d in data])
            y = np.array([d.label for d in data])
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)
            
            # Train model
            self.signal_model.fit(X_train_scaled, y_train)
            
            # Evaluate
            accuracy = self.signal_model.score(X_test_scaled, y_test)
            logger.info(f"✅ Model trained with accuracy: {accuracy:.2%}")
            
            self.model_trained = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Error training model: {e}")
            return False
    
    async def make_decision(self, market_data: Dict, indicators: Dict) -> AIDecision:
        """
        Make a trading decision using AI
        
        Args:
            market_data: Current market data
            indicators: Technical indicators
            
        Returns:
            AI decision with confidence and reasoning
        """
        try:
            # Extract features
            features = self.extract_features(market_data, indicators)
            
            # ML prediction
            action = 'hold'
            confidence = 0.5
            reasoning = ""
            
            if self.model_trained:
                features_scaled = self.scaler.transform([features])
                prediction = self.signal_model.predict(features_scaled)[0]
                proba = self.signal_model.predict_proba(features_scaled)[0]
                
                # Map prediction to action
                if prediction == 1:
                    action = 'buy'
                    confidence = proba[1]
                elif prediction == 2:
                    action = 'sell'
                    confidence = proba[2]
                else:
                    action = 'hold'
                    confidence = proba[0]
                
                reasoning = f"ML model predicts {action.upper()} with {confidence:.1%} confidence"
            
            # Enhance with Ollama if available
            ollama_analysis = ""
            if await self.check_ollama_connection():
                ollama_analysis = await self.analyze_with_ollama(market_data, indicators)
                
                if ollama_analysis:
                    # Combine ML and Ollama reasoning
                    reasoning += f"\n\nOllama Analysis: {ollama_analysis}"
                    
                    # Override action if Ollama is confident
                    if "BUY" in ollama_analysis.upper():
                        action = 'buy'
                        confidence = max(confidence, 0.7)
                    elif "SELL" in ollama_analysis.upper():
                        action = 'sell'
                        confidence = max(confidence, 0.7)
            
            # Risk assessment
            risk_level = self._assess_risk(indicators)
            
            # Predicted return
            predicted_return = self._predict_return(indicators)
            
            return AIDecision(
                action=action,
                confidence=confidence,
                reasoning=reasoning,
                risk_assessment=risk_level,
                predicted_return=predicted_return,
                model_version="1.0"
            )
            
        except Exception as e:
            logger.error(f"❌ Error making decision: {e}")
            return AIDecision(
                action='hold',
                confidence=0.0,
                reasoning=f"Error: {str(e)}",
                risk_assessment="unknown",
                predicted_return=0.0,
                model_version="1.0"
            )
    
    def _assess_risk(self, indicators: Dict) -> str:
        """Assess risk level based on indicators"""
        rsi = indicators.get('rsi', 50)
        
        if rsi > 70 or rsi < 30:
            return "high"
        elif rsi > 60 or rsi < 40:
            return "medium"
        else:
            return "low"
    
    def _predict_return(self, indicators: Dict) -> float:
        """Predict potential return"""
        # Simplified prediction based on RSI
        rsi = indicators.get('rsi', 50)
        
        if rsi < 30:
            return 0.05  # 5% expected return on oversold
        elif rsi > 70:
            return -0.03  # -3% expected return on overbought
        else:
            return 0.01  # 1% expected return in normal conditions
    
    def learn_from_outcome(self, decision: AIDecision, outcome: float):
        """
        Learn from trade outcome

        Args:
            decision: The decision that was made
            outcome: The actual PnL from following the decision
        """
        try:
            # Create learning data point
            label = 1 if decision.action == "buy" else 2 if decision.action == "sell" else 0

            # Record outcome
            record = {
                "timestamp": datetime.now().isoformat(),
                "action": decision.action,
                "confidence": decision.confidence,
                "outcome": outcome,
                "model_version": decision.model_version,
                "label": label,
            }
            self.performance_history.append(record)

            # Accumulate learning data points from the last decision's features (if available)
            if hasattr(self, "_last_features") and self._last_features:
                self.learning_data.append(
                    LearningData(
                        features=self._last_features,
                        label=label,
                        outcome=outcome,
                        timestamp=datetime.now(),
                        confidence=decision.confidence,
                    )
                )

            logger.info(f"📚 Learned from outcome: {decision.action} -> ${outcome:.2f}")

            # Retrain model every 50 data points
            if len(self.learning_data) >= 50 and len(self.learning_data) % 50 == 0:
                logger.info("🔄 Retraining model with new data...")
                if self.train_model(self.learning_data):
                    # Increment model version
                    try:
                        version_parts = decision.model_version.split(".")
                        new_minor = int(version_parts[-1]) + 1
                        self._model_version = ".".join(version_parts[:-1] + [str(new_minor)])
                    except (ValueError, IndexError):
                        self._model_version = "1.1"
                    logger.info(f"✅ Model retrained. New version: {self._model_version}")
                    # Persist updated model
                    self.save_knowledge()

        except Exception as e:
            logger.error(f"❌ Error learning from outcome: {e}")
    
    def get_performance_stats(self) -> Dict:
        """Get AI performance statistics"""
        if not self.performance_history:
            return {
                'total_decisions': 0,
                'win_rate': 0,
                'average_return': 0,
                'total_return': 0
            }
        
        outcomes = [h['outcome'] for h in self.performance_history]
        wins = [o for o in outcomes if o > 0]
        
        return {
            'total_decisions': len(self.performance_history),
            'win_rate': len(wins) / len(outcomes) if outcomes else 0,
            'average_return': np.mean(outcomes) if outcomes else 0,
            'total_return': sum(outcomes),
            'model_trained': self.model_trained
        }
    
    def save_knowledge(self):
        """Save knowledge base, performance history, and learning data to disk."""
        try:
            knowledge_file = self.model_path / "knowledge_base.json"
            with open(knowledge_file, "w") as f:
                json.dump(self.knowledge_base, f, indent=2)

            perf_file = self.model_path / "performance_history.json"
            with open(perf_file, "w") as f:
                json.dump(self.performance_history, f, indent=2, default=str)

            learning_file = self.model_path / "learning_data.json"
            serializable = [
                {
                    "features": ld.features,
                    "label": ld.label,
                    "outcome": ld.outcome,
                    "timestamp": ld.timestamp.isoformat(),
                    "confidence": ld.confidence,
                }
                for ld in self.learning_data
            ]
            with open(learning_file, "w") as f:
                json.dump(serializable, f, indent=2)

            logger.info("✅ Knowledge base saved")
        except Exception as e:
            logger.error(f"❌ Error saving knowledge: {e}")

    def load_knowledge(self):
        """Reload persisted state (knowledge base, performance history, learning data) on init."""
        try:
            knowledge_file = self.model_path / "knowledge_base.json"
            if knowledge_file.exists():
                with open(knowledge_file) as f:
                    self.knowledge_base = json.load(f)

            perf_file = self.model_path / "performance_history.json"
            if perf_file.exists():
                with open(perf_file) as f:
                    self.performance_history = json.load(f)

            learning_file = self.model_path / "learning_data.json"
            if learning_file.exists():
                with open(learning_file) as f:
                    raw = json.load(f)
                self.learning_data = [
                    LearningData(
                        features=r["features"],
                        label=r["label"],
                        outcome=r["outcome"],
                        timestamp=datetime.fromisoformat(r["timestamp"]),
                        confidence=r["confidence"],
                    )
                    for r in raw
                ]

            logger.info(
                f"✅ Knowledge loaded: {len(self.performance_history)} history records, "
                f"{len(self.learning_data)} learning points"
            )
        except Exception as e:
            logger.error(f"❌ Error loading knowledge: {e}")


# Example usage
if __name__ == "__main__":
    async def test_rimuru_ai():
        logger.info("🧠 RIMURU AI CORE TEST")
        logger.info("=" * 60)

        ai = RimuruAICore()

        # Test Ollama connection
        logger.info("\n1. Testing Ollama connection...")
        ollama_connected = await ai.check_ollama_connection()
        logger.info(f"   Ollama connected: {ollama_connected}")

        # Test decision making
        logger.info("\n2. Testing AI decision making...")
        market_data = {
            'price': 50000,
            'volume': 1e9,
            'change_24h': 2.5
        }

        indicators = {
            'rsi': 45,
            'macd': 100,
            'ma_fast': 50500,
            'ma_slow': 49500,
            'bb_upper': 52000,
            'bb_lower': 48000
        }

        decision = await ai.make_decision(market_data, indicators)
        logger.info(f"   Action: {decision.action}")
        logger.info(f"   Confidence: {decision.confidence:.2%}")
        logger.info(f"   Risk Level: {decision.risk_assessment}")
        logger.info(f"   Predicted Return: {decision.predicted_return:.2%}")
        logger.info(f"   Reasoning: {decision.reasoning}")

        # Test learning
        logger.info("\n3. Testing learning from outcome...")
        ai.learn_from_outcome(decision, 500.0)
        stats = ai.get_performance_stats()
        logger.info(f"   Performance stats: {stats}")

        logger.info("\n" + "=" * 60)
        logger.info("✅ Rimuru AI Core test completed!")

    asyncio.run(test_rimuru_ai())