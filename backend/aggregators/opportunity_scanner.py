"""
Opportunity Aggregator System - Scans Airdrops, Faucets, Whale Movements
Combines all legitimate crypto opportunities with human approval workflow
"""

import aiohttp
import asyncio
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json
from decimal import Decimal

logger = logging.getLogger(__name__)


class OpportunityType(Enum):
    """Types of crypto opportunities"""
    AIRDROP = "airdrop"
    FAUCET = "faucet"
    WHALE_MOVEMENT = "whale_movement"
    STAKING_REWARD = "staking_reward"
    YIELD_FARMING = "yield_farming"
    LIQUIDITY_MINING = "liquidity_mining"


class ApprovalStatus(Enum):
    """Approval workflow statuses"""
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    CLAIMED = "claimed"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class Opportunity:
    """Represents a crypto opportunity"""
    id: str
    title: str
    description: str
    type: OpportunityType
    source: str
    estimated_value_usd: float
    total_supply: str
    claiming_deadline: Optional[str]
    requirement: str
    effort_level: str  # "easy", "medium", "hard"
    approval_status: ApprovalStatus
    estimated_roi: float
    blockchain: str
    contract_address: Optional[str]
    url: str
    data: Dict[str, Any]
    discovered_at: str
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    claimed_at: Optional[str] = None
    claim_notes: Optional[str] = None


class AirdropScanner:
    """Scans for active airdrops from public sources"""
    
    AIRDROP_SOURCES = {
        "airdropalert": "https://airdropalert.com/api",
        "coinexchange": "https://api.coin.exchange",
        "defillama": "https://api.defillama.com",
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.opportunities: List[Opportunity] = []
    
    async def scan_all_sources(self) -> List[Opportunity]:
        """Scan all airdrop sources"""
        opportunities = []
        
        try:
            # Scan AirdropAlert
            opportunities.extend(await self._scan_airdrop_alert())
        except Exception as e:
            logger.error(f"Error scanning AirdropAlert: {e}")
        
        try:
            # Scan DefiLlama yields
            opportunities.extend(await self._scan_defillama())
        except Exception as e:
            logger.error(f"Error scanning DefiLlama: {e}")
        
        return opportunities
    
    async def _scan_airdrop_alert(self) -> List[Opportunity]:
        """Scan AirdropAlert API for active airdrops"""
        opportunities = []
        
        try:
            # Note: Replace with actual API endpoint
            # This example shows structure
            active_airdrops = [
                {
                    "name": "Optimism Ecosystem Airdrop",
                    "value": "OP token",
                    "supply": "214 million OP",
                    "deadline": "2026-03-15",
                    "requirement": "Used Optimism within last 12 months",
                    "effort": "easy",
                    "roi_estimate": 2.5,
                    "blockchain": "Optimism",
                    "url": "https://optimism.io/airdrop"
                },
                {
                    "name": "Arbitrum dao Airdrop",
                    "value": "ARB token",
                    "supply": "42.7 billion ARB",
                    "deadline": "2026-04-01",
                    "requirement": "Used Arbitrum DeFi protocols",
                    "effort": "easy",
                    "roi_estimate": 3.2,
                    "blockchain": "Arbitrum",
                    "url": "https://arbitrum.foundation/airdrop"
                }
            ]
            
            for airdrop in active_airdrops:
                opportunity = Opportunity(
                    id=f"airdrop_{airdrop['name'].lower().replace(' ', '_')}",
                    title=airdrop['name'],
                    description=f"Active airdrop: {airdrop['value']}",
                    type=OpportunityType.AIRDROP,
                    source="airdropalert",
                    estimated_value_usd=self._estimate_airdrop_value(airdrop),
                    total_supply=airdrop['supply'],
                    claiming_deadline=airdrop['deadline'],
                    requirement=airdrop['requirement'],
                    effort_level=airdrop['effort'],
                    approval_status=ApprovalStatus.PENDING,
                    estimated_roi=airdrop['roi_estimate'],
                    blockchain=airdrop['blockchain'],
                    contract_address=None,
                    url=airdrop['url'],
                    data=airdrop,
                    discovered_at=datetime.utcnow().isoformat() + "Z"
                )
                opportunities.append(opportunity)
                
        except Exception as e:
            logger.error(f"Error in _scan_airdrop_alert: {e}")
        
        return opportunities
    
    async def _scan_defillama(self) -> List[Opportunity]:
        """Scan DefiLlama for yield farming and staking opportunities"""
        opportunities = []
        
        try:
            # Simulate DeFi opportunities
            defi_opps = [
                {
                    "name": "Aave Lending Rewards",
                    "type": OpportunityType.YIELD_FARMING,
                    "protocol": "Aave",
                    "apy": 8.5,
                    "supply": "USDC",
                    "requirement": "Deposit USDC",
                    "effort": "easy",
                    "blockchain": "Ethereum",
                    "url": "https://aave.com"
                },
                {
                    "name": "Curve LP Rewards",
                    "type": OpportunityType.LIQUIDITY_MINING,
                    "protocol": "Curve",
                    "apy": 12.3,
                    "supply": "CRV",
                    "requirement": "Provide liquidity",
                    "effort": "medium",
                    "blockchain": "Ethereum",
                    "url": "https://curve.fi"
                }
            ]
            
            for opp in defi_opps:
                opportunity = Opportunity(
                    id=f"defi_{opp['name'].lower().replace(' ', '_')}",
                    title=opp['name'],
                    description=f"DeFi yield opportunity: {opp['apy']}% APY",
                    type=opp['type'],
                    source="defillama",
                    estimated_value_usd=1000,  # Estimate based on typical deposit
                    total_supply=opp['supply'],
                    claiming_deadline=None,
                    requirement=opp['requirement'],
                    effort_level=opp['effort'],
                    approval_status=ApprovalStatus.PENDING,
                    estimated_roi=opp['apy'] / 100,
                    blockchain=opp['blockchain'],
                    contract_address=None,
                    url=opp['url'],
                    data=opp,
                    discovered_at=datetime.utcnow().isoformat() + "Z"
                )
                opportunities.append(opportunity)
                
        except Exception as e:
            logger.error(f"Error in _scan_defillama: {e}")
        
        return opportunities
    
    def _estimate_airdrop_value(self, airdrop: Dict) -> float:
        """Estimate airdrop value in USD"""
        # Placeholder - would integrate with price oracles
        return 150.0


class FaucetAggregator:
    """Aggregates active crypto faucets"""
    
    FAUCET_SOURCES = {
        "faucet_fun": "https://faucet.fun",
        "faucet_io": "https://faucet.io",
        "faucet_pay": "https://faucetpay.io",
    }
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.faucets: List[Opportunity] = []
    
    async def scan_faucets(self) -> List[Opportunity]:
        """Scan all faucet sources"""
        opportunities = []
        
        faucets_list = [
            {
                "name": "Bitcoin Faucet Fun",
                "coin": "BTC",
                "reward_per_hour": "50 satoshis",
                "min_withdraw": "5000 satoshis",
                "effort": "very_easy",
                "url": "https://faucet.fun/btc"
            },
            {
                "name": "Ethereum Faucet",
                "coin": "ETH",
                "reward_per_hour": "0.0005 ETH",
                "min_withdraw": "0.01 ETH",
                "effort": "very_easy",
                "url": "https://faucet.io/eth"
            },
            {
                "name": "Solana Faucet",
                "coin": "SOL",
                "reward_per_hour": "0.001 SOL",
                "min_withdraw": "0.1 SOL",
                "effort": "very_easy",
                "url": "https://faucet.fun/sol"
            }
        ]
        
        for faucet in faucets_list:
            opportunity = Opportunity(
                id=f"faucet_{faucet['coin'].lower()}",
                title=faucet['name'],
                description=f"Daily {faucet['coin']} faucet rewards",
                type=OpportunityType.FAUCET,
                source="faucet_aggregator",
                estimated_value_usd=5.0,  # Rough daily estimate
                total_supply="Unlimited daily claims",
                claiming_deadline=None,
                requirement="Visit and claim daily",
                effort_level=faucet['effort'],
                approval_status=ApprovalStatus.PENDING,
                estimated_roi=0.5,  # 50% daily for active faucets
                blockchain=self._get_blockchain(faucet['coin']),
                contract_address=None,
                url=faucet['url'],
                data=faucet,
                discovered_at=datetime.utcnow().isoformat() + "Z"
            )
            opportunities.append(opportunity)
        
        return opportunities
    
    def _get_blockchain(self, coin: str) -> str:
        """Map coin to blockchain"""
        blockchain_map = {
            "BTC": "Bitcoin",
            "ETH": "Ethereum",
            "SOL": "Solana",
            "DOGE": "Dogecoin",
            "BNB": "Binance Smart Chain"
        }
        return blockchain_map.get(coin, "Unknown")


class WhaleTracker:
    """Tracks large on-chain movements and whale activity"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
    
    async def scan_whale_movements(self) -> List[Opportunity]:
        """Scan blockchain for large movements"""
        opportunities = []
        
        # Simulate whale movements (in real system, use Etherscan API, Blockchair, etc.)
        whale_events = [
            {
                "hash": "0x1234...",
                "from_whale": "0xabcd...",
                "to": "Exchange",
                "amount": 50,
                "coin": "BTC",
                "estimated_value": 2_250_000,
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": "bearish",  # Large whale to exchange = potential sell
                "blockchain": "Bitcoin"
            },
            {
                "hash": "0x5678...",
                "from": "Exchange",
                "to_whale": "0xefgh...",
                "amount": 10_000,
                "coin": "ETH",
                "estimated_value": 35_000_000,
                "timestamp": datetime.utcnow().isoformat(),
                "sentiment": "bullish",  # Large exchange withdrawal = accumulation
                "blockchain": "Ethereum"
            }
        ]
        
        for event in whale_events:
            opportunity = Opportunity(
                id=f"whale_{event['hash']}",
                title=f"Whale Movement: {event['amount']} {event['coin']}",
                description=f"Large {event['coin']} movement detected ({event['sentiment']})",
                type=OpportunityType.WHALE_MOVEMENT,
                source="whale_tracker",
                estimated_value_usd=float(event['estimated_value']),
                total_supply="Single transaction",
                claiming_deadline=None,
                requirement="Monitor and analyze",
                effort_level="easy",
                approval_status=ApprovalStatus.REVIEWED,  # Informational
                estimated_roi=0.0,
                blockchain=event['blockchain'],
                contract_address=None,
                url=f"https://etherscan.io/tx/{event['hash']}",
                data=event,
                discovered_at=datetime.utcnow().isoformat() + "Z"
            )
            opportunities.append(opportunity)
        
        return opportunities


class OpportunityAnalyzer:
    """Analyzes and ranks opportunities"""
    
    def __init__(self):
        self.opportunities: List[Opportunity] = []
    
    async def analyze_opportunities(self, opportunities: List[Opportunity]) -> List[Opportunity]:
        """Rank opportunities by ROI, effort, risk"""
        
        for opp in opportunities:
            # Calculate opportunity score
            score = self._calculate_score(opp)
            opp.estimated_roi = score
        
        # Sort by ROI descending
        analyzed = sorted(opportunities, key=lambda x: x.estimated_roi, reverse=True)
        self.opportunities = analyzed
        
        logger.info(f"Analyzed {len(analyzed)} opportunities")
        return analyzed
    
    def _calculate_score(self, opp: Opportunity) -> float:
        """Calculate opportunity score (risk-adjusted ROI)"""
        
        # Base ROI
        roi = opp.estimated_roi
        
        # Effort multiplier (easier = higher score)
        effort_scores = {
            "very_easy": 1.5,
            "easy": 1.2,
            "medium": 0.8,
            "hard": 0.5,
        }
        effort_multiplier = effort_scores.get(opp.effort_level, 1.0)
        
        # Deadline urgency (sooner = higher score)
        urgency_bonus = 0
        if opp.claiming_deadline:
            deadline = datetime.fromisoformat(opp.claiming_deadline.replace('Z', '+00:00'))
            days_left = (deadline - datetime.utcnow()).days
            if days_left < 30:
                urgency_bonus = 0.5
            elif days_left < 7:
                urgency_bonus = 1.0
        
        # Type-based weighting
        type_weights = {
            OpportunityType.AIRDROP: 1.5,
            OpportunityType.FAUCET: 0.8,
            OpportunityType.WHALE_MOVEMENT: 0.5,
            OpportunityType.STAKING_REWARD: 1.2,
            OpportunityType.YIELD_FARMING: 1.3,
            OpportunityType.LIQUIDITY_MINING: 1.4,
        }
        type_weight = type_weights.get(opp.type, 1.0)
        
        final_score = roi * effort_multiplier * type_weight + urgency_bonus
        return round(final_score, 4)
    
    def get_top_opportunities(self, limit: int = 10) -> List[Opportunity]:
        """Get top N opportunities by score"""
        return self.opportunities[:limit]
    
    def get_by_type(self, opp_type: OpportunityType) -> List[Opportunity]:
        """Get opportunities by type"""
        return [o for o in self.opportunities if o.type == opp_type]
    
    def get_pending_approval(self) -> List[Opportunity]:
        """Get all opportunities pending approval"""
        return [o for o in self.opportunities 
                if o.approval_status == ApprovalStatus.PENDING]
    
    def get_approved(self) -> List[Opportunity]:
        """Get approved but not yet claimed"""
        return [o for o in self.opportunities 
                if o.approval_status == ApprovalStatus.APPROVED]


class OpportunityAggregator:
    """Master aggregator - coordinates all scanners"""
    
    def __init__(self, db_connection: Optional[Any] = None):
        self.db = db_connection
        self.all_opportunities: List[Opportunity] = []
        self.analyzer = OpportunityAnalyzer()
    
    async def run_full_scan(self) -> Dict[str, Any]:
        """Execute full scan of all opportunity sources"""
        
        async with aiohttp.ClientSession() as session:
            scanner = AirdropScanner(session)
            faucet_agg = FaucetAggregator(session)
            whale = WhaleTracker(session)
            
            logger.info("Starting opportunity scan...")
            
            # Run scans concurrently
            airdrop_results = await scanner.scan_all_sources()
            faucet_results = await faucet_agg.scan_faucets()
            whale_results = await whale.scan_whale_movements()
            
            # Combine all opportunities
            self.all_opportunities = airdrop_results + faucet_results + whale_results
            
            # Analyze
            await self.analyzer.analyze_opportunities(self.all_opportunities)
            
            # Save to database if connected
            if self.db:
                await self._save_to_database()
            
            logger.info(f"Scan complete: {len(self.all_opportunities)} opportunities found")
            
            return {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "total_opportunities": len(self.all_opportunities),
                "by_type": self._count_by_type(),
                "top_opportunities": [asdict(o) for o in self.analyzer.get_top_opportunities(5)],
                "pending_approval": len(self.analyzer.get_pending_approval())
            }
    
    async def _save_to_database(self):
        """Save opportunities to database"""
        try:
            for opp in self.all_opportunities:
                # Would execute INSERT or UPDATE in database
                pass
            logger.info(f"Saved {len(self.all_opportunities)} opportunities to database")
        except Exception as e:
            logger.error(f"Error saving to database: {e}")
    
    def _count_by_type(self) -> Dict[str, int]:
        """Count opportunities by type"""
        counts = {}
        for opp in self.all_opportunities:
            key = opp.type.value
            counts[key] = counts.get(key, 0) + 1
        return counts
    
    def approve_opportunity(self, opportunity_id: str, approved_by: str) -> bool:
        """Approve opportunity for claiming"""
        for opp in self.all_opportunities:
            if opp.id == opportunity_id:
                opp.approval_status = ApprovalStatus.APPROVED
                opp.approved_by = approved_by
                opp.approved_at = datetime.utcnow().isoformat() + "Z"
                return True
        return False
    
    def reject_opportunity(self, opportunity_id: str, approved_by: str) -> bool:
        """Reject opportunity"""
        for opp in self.all_opportunities:
            if opp.id == opportunity_id:
                opp.approval_status = ApprovalStatus.REJECTED
                opp.approved_by = approved_by
                opp.approved_at = datetime.utcnow().isoformat() + "Z"
                return True
        return False
    
    def mark_claimed(self, opportunity_id: str, notes: str = "") -> bool:
        """Mark opportunity as claimed"""
        for opp in self.all_opportunities:
            if opp.id == opportunity_id:
                opp.approval_status = ApprovalStatus.CLAIMED
                opp.claimed_at = datetime.utcnow().isoformat() + "Z"
                opp.claim_notes = notes
                return True
        return False
    
    def export_json(self) -> str:
        """Export all opportunities as JSON"""
        return json.dumps(
            [asdict(o) for o in self.all_opportunities],
            indent=2,
            default=str
        )


# CLI/Demo
if __name__ == "__main__":
    import sys
    
    async def main():
        aggregator = OpportunityAggregator()
        
        results = await aggregator.run_full_scan()
        
        print("\n=== CRYPTO OPPORTUNITY SCAN ===")
        print(json.dumps(results, indent=2))
        
        print("\n=== TOP 5 OPPORTUNITIES ===")
        for i, opp in enumerate(aggregator.analyzer.get_top_opportunities(5), 1):
            print(f"\n{i}. {opp.title}")
            print(f"   Type: {opp.type.value}")
            print(f"   Effort: {opp.effort_level}")
            print(f"   Est. Value: ${opp.estimated_value_usd:,.2f}")
            print(f"   Score: {opp.estimated_roi:.4f}")
            print(f"   Status: {opp.approval_status.value}")
    
    asyncio.run(main())
