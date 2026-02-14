#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Risk Management System
Comprehensive risk controls for trading operations
"""

import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_position_size_pct: float = 0.10  # 10% of portfolio
    max_daily_loss_pct: float = 0.02  # 2% of portfolio
    max_drawdown_pct: float = 0.10  # 10% from peak
    max_open_positions: int = 10
    max_correlation: float = 0.7  # Maximum correlation between positions
    stop_loss_pct: float = 0.05  # 5%
    take_profit_pct: float = 0.10  # 10%
    emergency_stop_enabled: bool = True

@dataclass
class Position:
    """Trading position"""
    symbol: str
    side: str
    entry_price: float
    amount: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    timestamp: datetime

@dataclass
class RiskAssessment:
    """Risk assessment result"""
    allowed: bool
    risk_level: RiskLevel
    confidence: float
    reasons: List[str]
    suggested_size: float
    warnings: List[str]

class RiskManager:
    """
    Comprehensive risk management system
    
    Features:
    - Position sizing limits
    - Daily loss limits
    - Drawdown protection
    - Correlation analysis
    - Stop-loss/take-profit management
    - Emergency stop mechanism
    """
    
    def __init__(self, config: RiskConfig):
        self.config = config
        self.positions: List[Position] = []
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.peak_portfolio_value = 0.0
        self.current_portfolio_value = 0.0
        self.emergency_stop_triggered = False
        
        # Trading history
        self.trade_history: List[Dict] = []
        
        logger.info("✅ Risk Manager initialized")
    
    def check_trade_allowed(self, symbol: str, side: str, amount: float, 
                           price: float, portfolio_value: float) -> RiskAssessment:
        """
        Check if a trade is allowed based on risk parameters
        
        Args:
            symbol: Trading symbol
            side: 'buy' or 'sell'
            amount: Trade amount
            price: Trade price
            portfolio_value: Current portfolio value
            
        Returns:
            RiskAssessment with decision and reasons
        """
        reasons = []
        warnings = []
        allowed = True
        risk_level = RiskLevel.LOW
        confidence = 1.0
        
        # Calculate trade value
        trade_value = amount * price
        position_size_pct = trade_value / portfolio_value if portfolio_value > 0 else 0
        
        # 1. Check position size limit
        if position_size_pct > self.config.max_position_size_pct:
            allowed = False
            reasons.append(f"Position size ({position_size_pct:.2%}) exceeds maximum ({self.config.max_position_size_pct:.2%})")
            risk_level = RiskLevel.HIGH
        elif position_size_pct > self.config.max_position_size_pct * 0.8:
            warnings.append(f"Position size ({position_size_pct:.2%}) approaching maximum")
            risk_level = RiskLevel.MEDIUM
            confidence = 0.8
        
        # 2. Check daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / portfolio_value if portfolio_value > 0 else 0
        if daily_loss_pct > self.config.max_daily_loss_pct:
            allowed = False
            reasons.append(f"Daily loss ({daily_loss_pct:.2%}) exceeds maximum ({self.config.max_daily_loss_pct:.2%})")
            risk_level = RiskLevel.CRITICAL
        elif daily_loss_pct > self.config.max_daily_loss_pct * 0.8:
            warnings.append(f"Daily loss ({daily_loss_pct:.2%}) approaching maximum")
            risk_level = RiskLevel.HIGH
            confidence = 0.7
        
        # 3. Check drawdown limit
        if self.peak_portfolio_value > 0:
            drawdown = (self.peak_portfolio_value - self.current_portfolio_value) / self.peak_portfolio_value
            if drawdown > self.config.max_drawdown_pct:
                allowed = False
                reasons.append(f"Drawdown ({drawdown:.2%}) exceeds maximum ({self.config.max_drawdown_pct:.2%})")
                risk_level = RiskLevel.CRITICAL
            elif drawdown > self.config.max_drawdown_pct * 0.8:
                warnings.append(f"Drawdown ({drawdown:.2%}) approaching maximum")
                risk_level = RiskLevel.HIGH
                confidence = 0.7
        
        # 4. Check number of open positions
        if len(self.positions) >= self.config.max_open_positions:
            allowed = False
            reasons.append(f"Maximum open positions ({self.config.max_open_positions}) reached")
            risk_level = RiskLevel.HIGH
        elif len(self.positions) >= self.config.max_open_positions * 0.8:
            warnings.append(f"Open positions ({len(self.positions)}) approaching maximum")
            risk_level = RiskLevel.MEDIUM
            confidence = 0.8
        
        # 5. Check correlation with existing positions
        correlation_risk = self._check_correlation(symbol)
        if correlation_risk > self.config.max_correlation:
            warnings.append(f"High correlation ({correlation_risk:.2%}) with existing positions")
            risk_level = RiskLevel.MEDIUM
            confidence = 0.6
        
        # 6. Emergency stop check
        if self.emergency_stop_triggered and self.config.emergency_stop_enabled:
            allowed = False
            reasons.append("Emergency stop is triggered - no new trades allowed")
            risk_level = RiskLevel.CRITICAL
            confidence = 0.0
        
        # Calculate suggested position size
        suggested_size = portfolio_value * self.config.max_position_size_pct
        if not allowed:
            suggested_size = 0
        elif risk_level == RiskLevel.HIGH or risk_level == RiskLevel.CRITICAL:
            suggested_size = suggested_size * 0.5  # Reduce size by 50%
        
        return RiskAssessment(
            allowed=allowed,
            risk_level=risk_level,
            confidence=confidence,
            reasons=reasons,
            suggested_size=suggested_size,
            warnings=warnings
        )
    
    def _check_correlation(self, symbol: str) -> float:
        """
        Check correlation with existing positions
        
        This is a simplified version - in production, use actual correlation
        calculations based on historical price data
        """
        # Simplified correlation check
        # In production, use pandas correlation matrix
        correlated_pairs = {
            'BTC': ['ETH', 'SOL', 'ADA'],
            'ETH': ['BTC', 'SOL', 'MATIC'],
            'SOL': ['BTC', 'ETH', 'AVAX'],
        }
        
        max_correlation = 0.0
        base_symbol = symbol.split('/')[0]  # Extract base currency
        
        for position in self.positions:
            pos_base = position.symbol.split('/')[0]
            
            if base_symbol in correlated_pairs.get(pos_base, []):
                max_correlation = max(max_correlation, 0.8)
            elif base_symbol == pos_base:
                max_correlation = max(max_correlation, 1.0)
        
        return max_correlation
    
    def calculate_position_size(self, symbol: str, portfolio_value: float, 
                               risk_level: RiskLevel) -> float:
        """
        Calculate optimal position size based on risk level
        
        Args:
            symbol: Trading symbol
            portfolio_value: Current portfolio value
            risk_level: Current risk level
            
        Returns:
            Position size in currency units
        """
        base_size = portfolio_value * self.config.max_position_size_pct
        
        # Adjust based on risk level
        multipliers = {
            RiskLevel.LOW: 1.0,
            RiskLevel.MEDIUM: 0.7,
            RiskLevel.HIGH: 0.4,
            RiskLevel.CRITICAL: 0.0
        }
        
        return base_size * multipliers.get(risk_level, 0.5)
    
    def calculate_stop_loss(self, entry_price: float, side: str) -> float:
        """Calculate stop loss price"""
        if side.lower() == 'buy':
            return entry_price * (1 - self.config.stop_loss_pct)
        else:
            return entry_price * (1 + self.config.stop_loss_pct)
    
    def calculate_take_profit(self, entry_price: float, side: str) -> float:
        """Calculate take profit price"""
        if side.lower() == 'buy':
            return entry_price * (1 + self.config.take_profit_pct)
        else:
            return entry_price * (1 - self.config.take_profit_pct)
    
    def add_position(self, symbol: str, side: str, entry_price: float, amount: float):
        """Add a position to tracking"""
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            amount=amount,
            current_price=entry_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            timestamp=datetime.now()
        )
        
        self.positions.append(position)
        logger.info(f"✅ Added position: {symbol} {side} {amount} @ {entry_price}")
    
    def update_position(self, symbol: str, current_price: float):
        """Update position PnL"""
        for position in self.positions:
            if position.symbol == symbol:
                position.current_price = current_price
                
                if position.side.lower() == 'buy':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.amount
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.amount
                
                position.unrealized_pnl_pct = position.unrealized_pnl / (position.entry_price * position.amount)
                
                logger.info(f"📊 Updated position {symbol}: PnL={position.unrealized_pnl:.2f} ({position.unrealized_pnl_pct:.2%})")
    
    def close_position(self, symbol: str, exit_price: float) -> float:
        """
        Close a position and return realized PnL
        
        Args:
            symbol: Symbol to close
            exit_price: Exit price
            
        Returns:
            Realized PnL
        """
        for i, position in enumerate(self.positions):
            if position.symbol == symbol:
                # Calculate realized PnL
                if position.side.lower() == 'buy':
                    realized_pnl = (exit_price - position.entry_price) * position.amount
                else:
                    realized_pnl = (position.entry_price - exit_price) * position.amount
                
                # Update daily PnL
                self.daily_pnl += realized_pnl
                
                # Add to trade history
                self.trade_history.append({
                    'symbol': symbol,
                    'side': position.side,
                    'entry_price': position.entry_price,
                    'exit_price': exit_price,
                    'amount': position.amount,
                    'pnl': realized_pnl,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Remove position
                self.positions.pop(i)
                
                logger.info(f"✅ Closed position {symbol}: PnL={realized_pnl:.2f}")
                return realized_pnl
        
        return 0.0
    
    def check_stop_loss_take_profit(self) -> List[Tuple[str, str]]:
        """
        Check if any positions hit stop loss or take profit
        
        Returns:
            List of (symbol, action) tuples where action is 'stop_loss' or 'take_profit'
        """
        actions = []
        
        for position in self.positions:
            if position.side.lower() == 'buy':
                stop_loss = self.calculate_stop_loss(position.entry_price, 'buy')
                take_profit = self.calculate_take_profit(position.entry_price, 'buy')
                
                if position.current_price <= stop_loss:
                    actions.append((position.symbol, 'stop_loss'))
                elif position.current_price >= take_profit:
                    actions.append((position.symbol, 'take_profit'))
            else:
                stop_loss = self.calculate_stop_loss(position.entry_price, 'sell')
                take_profit = self.calculate_take_profit(position.entry_price, 'sell')
                
                if position.current_price >= stop_loss:
                    actions.append((position.symbol, 'stop_loss'))
                elif position.current_price <= take_profit:
                    actions.append((position.symbol, 'take_profit'))
        
        return actions
    
    def trigger_emergency_stop(self, reason: str = "Manual trigger"):
        """Trigger emergency stop - halt all trading"""
        self.emergency_stop_triggered = True
        logger.error(f"🚨 EMERGENCY STOP TRIGGERED: {reason}")
        
        # In a real system, this would:
        # 1. Cancel all open orders
        # 2. Close all positions (optional)
        # 3. Disable all bots
        # 4. Send alerts
    
    def reset_emergency_stop(self):
        """Reset emergency stop (requires manual intervention)"""
        self.emergency_stop_triggered = False
        logger.info("✅ Emergency stop reset - trading can resume")
    
    def get_risk_summary(self) -> Dict:
        """Get current risk summary"""
        total_unrealized_pnl = sum(p.unrealized_pnl for p in self.positions)
        total_exposure = sum(p.amount * p.current_price for p in self.positions)
        
        return {
            'positions_count': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'daily_trades': self.daily_trades,
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_exposure': total_exposure,
            'peak_portfolio_value': self.peak_portfolio_value,
            'current_portfolio_value': self.current_portfolio_value,
            'emergency_stop_triggered': self.emergency_stop_triggered,
            'positions': [
                {
                    'symbol': p.symbol,
                    'side': p.side,
                    'entry_price': p.entry_price,
                    'current_price': p.current_price,
                    'unrealized_pnl': p.unrealized_pnl,
                    'unrealized_pnl_pct': p.unrealized_pnl_pct
                }
                for p in self.positions
            ]
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info("📊 Daily statistics reset")
    
    def update_portfolio_value(self, value: float):
        """Update portfolio value and track peak"""
        self.current_portfolio_value = value
        if value > self.peak_portfolio_value:
            self.peak_portfolio_value = value
            logger.info(f"📈 New portfolio peak: {value:.2f}")


# Example usage
if __name__ == "__main__":
    print("🛡️ RISK MANAGEMENT SYSTEM TEST")
    print("=" * 60)
    
    # Initialize risk manager
    config = RiskConfig(
        max_position_size_pct=0.10,
        max_daily_loss_pct=0.02,
        max_drawdown_pct=0.10,
        max_open_positions=5
    )
    
    risk_manager = RiskManager(config)
    
    # Test trade approval
    print("\n1. Testing trade approval...")
    assessment = risk_manager.check_trade_allowed(
        symbol="BTC/USDT",
        side="buy",
        amount=0.1,
        price=50000,
        portfolio_value=100000
    )
    
    print(f"   Allowed: {assessment.allowed}")
    print(f"   Risk Level: {assessment.risk_level.value}")
    print(f"   Confidence: {assessment.confidence:.2f}")
    print(f"   Suggested Size: ${assessment.suggested_size:.2f}")
    if assessment.reasons:
        print(f"   Reasons: {assessment.reasons}")
    if assessment.warnings:
        print(f"   Warnings: {assessment.warnings}")
    
    # Test position tracking
    print("\n2. Testing position tracking...")
    risk_manager.add_position("BTC/USDT", "buy", 50000, 0.1)
    risk_manager.update_position("BTC/USDT", 52000)
    
    # Test stop loss/take profit
    print("\n3. Testing stop loss/take profit...")
    actions = risk_manager.check_stop_loss_take_profit()
    print(f"   Actions: {actions}")
    
    # Get risk summary
    print("\n4. Risk Summary...")
    summary = risk_manager.get_risk_summary()
    for key, value in summary.items():
        if key != 'positions':
            print(f"   {key}: {value}")
    
    print("\n" + "=" * 60)
    print("✅ Risk management test completed!")