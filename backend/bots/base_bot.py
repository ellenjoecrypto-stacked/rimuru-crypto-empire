#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Base Bot Framework
Abstract base class for all trading bots
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BotStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"

class BotType(Enum):
    SPOT_TRADER = "spot_trader"
    DEFIFARMER = "defi_farmer"
    ARBITRAGE = "arbitrage"
    STAKING = "staking"

@dataclass
class BotConfig:
    """Base configuration for all bots"""
    name: str
    bot_type: BotType
    exchange: str
    symbol: str
    enabled: bool = True
    paper_trading: bool = True
    max_position_size: float = 0.1  # 10% of portfolio
    max_daily_loss: float = 0.02  # 2% of portfolio
    stop_loss_percent: float = 0.05  # 5%
    take_profit_percent: float = 0.10  # 10%
    check_interval: int = 60  # seconds

@dataclass
class BotState:
    """Current state of a bot"""
    status: BotStatus
    started_at: Optional[datetime] = None
    last_run: Optional[datetime] = None
    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    current_positions: List[Dict] = field(default_factory=list)
    error_message: Optional[str] = None

class BaseBot(ABC):
    """
    Abstract base class for all trading bots
    
    All bots must inherit from this class and implement
    the abstract methods for trading logic.
    """
    
    def __init__(self, config: BotConfig, exchange_manager):
        self.config = config
        self.exchange_manager = exchange_manager
        self.state = BotState(status=BotStatus.STOPPED)
        self.running = False
        self.paused = False
        self.task: Optional[asyncio.Task] = None
        
        # Performance tracking
        self.daily_pnl = 0.0
        self.daily_trades = 0
        
        # State persistence
        self.state_file = Path(f"data/bot_states/{config.name}_state.json")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ Bot '{config.name}' initialized")
    
    @abstractmethod
    async def analyze_market(self) -> Dict[str, Any]:
        """
        Analyze market conditions and generate trading signals
        
        Returns:
            Dictionary with analysis results and signals
        """
        pass
    
    @abstractmethod
    async def execute_trade(self, signal: Dict[str, Any]) -> bool:
        """
        Execute a trade based on signal
        
        Args:
            signal: Trading signal with action, price, amount, etc.
            
        Returns:
            bool: Success status
        """
        pass
    
    async def start(self) -> bool:
        """Start the bot"""
        try:
            if self.running:
                logger.warning(f"⚠️ Bot '{self.config.name}' is already running")
                return False
            
            self.state.status = BotStatus.STARTING
            self.running = True
            self.paused = False
            
            # Start main loop
            self.task = asyncio.create_task(self._main_loop())
            
            self.state.status = BotStatus.RUNNING
            self.state.started_at = datetime.now()
            
            logger.info(f"🚀 Bot '{self.config.name}' started")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting bot '{self.config.name}': {e}")
            self.state.status = BotStatus.ERROR
            self.state.error_message = str(e)
            return False
    
    async def stop(self) -> bool:
        """Stop the bot"""
        try:
            if not self.running:
                logger.warning(f"⚠️ Bot '{self.config.name}' is not running")
                return False
            
            self.state.status = BotStatus.STOPPING
            self.running = False
            
            # Cancel main loop task
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            
            # Save state
            await self._save_state()
            
            self.state.status = BotStatus.STOPPED
            logger.info(f"🛑 Bot '{self.config.name}' stopped")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot '{self.config.name}': {e}")
            self.state.status = BotStatus.ERROR
            return False
    
    async def pause(self) -> bool:
        """Pause the bot"""
        if not self.running:
            logger.warning(f"⚠️ Bot '{self.config.name}' is not running")
            return False
        
        self.paused = True
        self.state.status = BotStatus.PAUSED
        logger.info(f"⏸️ Bot '{self.config.name}' paused")
        return True
    
    async def resume(self) -> bool:
        """Resume the bot"""
        if not self.paused:
            logger.warning(f"⚠️ Bot '{self.config.name}' is not paused")
            return False
        
        self.paused = False
        self.state.status = BotStatus.RUNNING
        logger.info(f"▶️ Bot '{self.config.name}' resumed")
        return True
    
    async def _main_loop(self):
        """Main bot execution loop"""
        while self.running:
            try:
                if not self.paused:
                    # Run bot logic
                    await self._run_once()
                    
                    # Update last run time
                    self.state.last_run = datetime.now()
                
                # Sleep for configured interval
                await asyncio.sleep(self.config.check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in bot '{self.config.name}' main loop: {e}")
                self.state.status = BotStatus.ERROR
                self.state.error_message = str(e)
                await asyncio.sleep(10)  # Wait before retrying
    
    async def _run_once(self):
        """Execute one iteration of bot logic"""
        try:
            # Analyze market
            analysis = await self.analyze_market()
            
            # Check if signal should be executed
            if self._should_execute_trade(analysis):
                # Execute trade
                success = await self.execute_trade(analysis)
                
                if success:
                    self.state.successful_trades += 1
                    self.daily_trades += 1
                else:
                    self.state.failed_trades += 1
                
                self.state.total_trades += 1
            
            # Save state periodically
            if self.state.total_trades % 10 == 0:
                await self._save_state()
                
        except Exception as e:
            logger.error(f"❌ Error in bot execution: {e}")
    
    def _should_execute_trade(self, analysis: Dict[str, Any]) -> bool:
        """
        Determine if trade should be executed based on analysis
        
        Override in child classes for custom logic
        """
        # Default: check if there's a clear signal
        return analysis.get('signal') is not None and analysis.get('confidence', 0) > 0.7
    
    async def _save_state(self):
        """Save bot state to file"""
        try:
            state_dict = {
                'status': self.state.status.value,
                'started_at': self.state.started_at.isoformat() if self.state.started_at else None,
                'last_run': self.state.last_run.isoformat() if self.state.last_run else None,
                'total_trades': self.state.total_trades,
                'successful_trades': self.state.successful_trades,
                'failed_trades': self.state.failed_trades,
                'total_profit': self.state.total_profit,
                'total_loss': self.state.total_loss,
                'current_positions': self.state.current_positions,
                'daily_pnl': self.daily_pnl,
                'daily_trades': self.daily_trades
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Error saving state: {e}")
    
    async def _load_state(self):
        """Load bot state from file"""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    state_dict = json.load(f)
                
                self.state.status = BotStatus(state_dict.get('status', BotStatus.STOPPED.value))
                self.state.total_trades = state_dict.get('total_trades', 0)
                self.state.successful_trades = state_dict.get('successful_trades', 0)
                self.state.failed_trades = state_dict.get('failed_trades', 0)
                self.state.total_profit = state_dict.get('total_profit', 0.0)
                self.state.total_loss = state_dict.get('total_loss', 0.0)
                self.state.current_positions = state_dict.get('current_positions', [])
                self.daily_pnl = state_dict.get('daily_pnl', 0.0)
                self.daily_trades = state_dict.get('daily_trades', 0)
                
                logger.info(f"✅ Loaded state for bot '{self.config.name}'")
                
        except Exception as e:
            logger.error(f"❌ Error loading state: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current bot status"""
        return {
            'name': self.config.name,
            'type': self.config.bot_type.value,
            'status': self.state.status.value,
            'running': self.running,
            'paused': self.paused,
            'started_at': self.state.started_at.isoformat() if self.state.started_at else None,
            'last_run': self.state.last_run.isoformat() if self.state.last_run else None,
            'total_trades': self.state.total_trades,
            'successful_trades': self.state.successful_trades,
            'failed_trades': self.state.failed_trades,
            'total_profit': self.state.total_profit,
            'total_loss': self.state.total_loss,
            'daily_pnl': self.daily_pnl,
            'current_positions': self.state.current_positions
        }
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        logger.info(f"📊 Daily stats reset for bot '{self.config.name}'")


class BotManager:
    """Manager for multiple bots"""
    
    def __init__(self):
        self.bots: Dict[str, BaseBot] = {}
        self.exchange_manager = None
    
    def set_exchange_manager(self, exchange_manager):
        """Set exchange manager for all bots"""
        self.exchange_manager = exchange_manager
    
    def add_bot(self, bot: BaseBot) -> bool:
        """Add a bot to the manager"""
        if bot.config.name in self.bots:
            logger.warning(f"⚠️ Bot '{bot.config.name}' already exists")
            return False
        
        self.bots[bot.config.name] = bot
        logger.info(f"✅ Bot '{bot.config.name}' added to manager")
        return True
    
    def remove_bot(self, name: str) -> bool:
        """Remove a bot from the manager"""
        if name not in self.bots:
            logger.warning(f"⚠️ Bot '{name}' not found")
            return False
        
        del self.bots[name]
        logger.info(f"✅ Bot '{name}' removed from manager")
        return True
    
    async def start_bot(self, name: str) -> bool:
        """Start a specific bot"""
        if name not in self.bots:
            logger.error(f"❌ Bot '{name}' not found")
            return False
        
        return await self.bots[name].start()
    
    async def stop_bot(self, name: str) -> bool:
        """Stop a specific bot"""
        if name not in self.bots:
            logger.error(f"❌ Bot '{name}' not found")
            return False
        
        return await self.bots[name].stop()
    
    async def start_all_bots(self) -> Dict[str, bool]:
        """Start all enabled bots"""
        results = {}
        for name, bot in self.bots.items():
            if bot.config.enabled:
                results[name] = await bot.start()
        return results
    
    async def stop_all_bots(self) -> Dict[str, bool]:
        """Stop all running bots"""
        results = {}
        for name, bot in self.bots.items():
            if bot.running:
                results[name] = await bot.stop()
        return results
    
    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all bots"""
        return {name: bot.get_status() for name, bot in self.bots.items()}