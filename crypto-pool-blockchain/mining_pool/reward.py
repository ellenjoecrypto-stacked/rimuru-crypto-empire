"""
Reward Distribution — How mining pools split block rewards.
============================================================

When a pool finds a block, the reward must be split among all miners
who contributed work (shares). There are several schemes:

═══════════════════════════════════════════════════════════════════

1. PPS (Pay Per Share)
   ───────────────────
   Each share has a FIXED payout value:
     payout_per_share = block_reward / expected_shares_per_block

   Example: Block reward = 50 coins, expected 1000 shares per block
     → Each share pays 0.05 coins, regardless of whether blocks are found

   Pro:  Miners get steady, predictable income
   Con:  Pool takes ALL the variance risk (might go bankrupt on bad luck)

═══════════════════════════════════════════════════════════════════

2. PPLNS (Pay Per Last N Shares)
   ──────────────────────────────
   When a block is found, the reward is split among the last N shares
   submitted (where N is typically 2× the expected shares per block).

   Example: Block found! Reward = 50 coins. Looking at last 2000 shares:
     Alice submitted 600 shares → gets 30% = 15 coins
     Bob submitted 400 shares   → gets 20% = 10 coins
     Charlie submitted 1000 shares → gets 50% = 25 coins

   Pro:  Discourages pool-hopping (switching pools for quick profit)
   Con:  Income is lumpy — depends on when blocks are found

═══════════════════════════════════════════════════════════════════

3. PROP (Proportional)
   ────────────────────
   The simplest scheme. When a block is found, look at ALL shares
   since the last block and split proportionally.

   Example: Since last block, 500 total shares:
     Alice: 200 shares (40%) → 40% of reward
     Bob: 150 shares (30%)   → 30% of reward
     Carol: 150 shares (30%) → 30% of reward

   Pro:  Simple and fair
   Con:  Vulnerable to pool-hopping
   
═══════════════════════════════════════════════════════════════════
"""

import time
import logging
from typing import Dict, List, Tuple
from enum import Enum
from collections import defaultdict, deque

logger = logging.getLogger("rimuru.rewards")


class PayoutScheme(Enum):
    PPS = "pps"
    PPLNS = "pplns"
    PROP = "proportional"


class Share:
    """A single share record."""
    def __init__(self, miner_address: str, worker_name: str, timestamp: float = None):
        self.miner_address = miner_address
        self.worker_name = worker_name
        self.timestamp = timestamp or time.time()


class RewardDistributor:
    """
    Distributes mining rewards to pool participants.

    Supports PPS, PPLNS, and Proportional payout schemes.
    """

    # Pool fee (percentage kept by the pool operator)
    POOL_FEE_PCT = 2.0  # 2% — typical for real pools (1-3%)

    # PPLNS window size (number of shares to consider)
    PPLNS_WINDOW = 2000

    # PPS: Expected shares per block (used to calculate per-share payout)
    EXPECTED_SHARES_PER_BLOCK = 1000

    def __init__(self, scheme: PayoutScheme = PayoutScheme.PPLNS):
        self.scheme = scheme

        # Share tracking
        self.all_shares: deque = deque(maxlen=100000)  # All historical shares
        self.round_shares: List[Share] = []             # Shares since last block
        self.share_counts: Dict[str, int] = defaultdict(int)  # Total per miner

        # PPS balance tracking
        self.pps_balances: Dict[str, float] = defaultdict(float)

        # Payout history
        self.payout_history: List[dict] = []
        self.total_distributed = 0.0

    def record_share(self, miner_address: str, worker_name: str):
        """
        Record a valid share from a miner.

        Called every time a miner submits an accepted share.
        """
        share = Share(miner_address, worker_name)
        self.all_shares.append(share)
        self.round_shares.append(share)
        self.share_counts[miner_address] += 1

        # For PPS: immediately credit the miner
        if self.scheme == PayoutScheme.PPS:
            pps_value = self._pps_share_value()
            self.pps_balances[miner_address] += pps_value

    def distribute(self, block_reward: float, finder_address: str) -> Dict[str, float]:
        """
        Distribute a block reward among miners.

        Called when the pool finds a valid block.
        Returns: {miner_address: payout_amount}
        """
        # Deduct pool fee
        pool_fee = block_reward * (self.POOL_FEE_PCT / 100)
        distributable = block_reward - pool_fee

        if self.scheme == PayoutScheme.PPS:
            payouts = self._distribute_pps(distributable)
        elif self.scheme == PayoutScheme.PPLNS:
            payouts = self._distribute_pplns(distributable)
        elif self.scheme == PayoutScheme.PROP:
            payouts = self._distribute_prop(distributable)
        else:
            payouts = {}

        # Record payout
        self.payout_history.append({
            "block_reward": block_reward,
            "pool_fee": pool_fee,
            "distributed": distributable,
            "scheme": self.scheme.value,
            "payouts": payouts,
            "timestamp": time.time(),
            "finder": finder_address,
        })
        self.total_distributed += distributable

        # Reset round shares (for PROP scheme)
        self.round_shares = []

        logger.info(
            "Reward distributed: %.2f coins to %d miners (fee: %.2f, scheme: %s)",
            distributable, len(payouts), pool_fee, self.scheme.value,
        )

        return payouts

    def _distribute_pps(self, distributable: float) -> Dict[str, float]:
        """
        PPS: Pay Per Share
        
        Each share has already been credited in record_share().
        At block time, we settle the accumulated balances.
        In practice, PPS pools pay miners continuously regardless of blocks.
        """
        payouts = dict(self.pps_balances)
        self.pps_balances.clear()
        return payouts

    def _distribute_pplns(self, distributable: float) -> Dict[str, float]:
        """
        PPLNS: Pay Per Last N Shares

        Look at the most recent N shares. Split the reward proportionally
        among miners based on their shares in that window.

        Why "Last N"?
          - Prevents pool-hopping: a miner can't jump in right before
            a block is found and grab a disproportionate reward
          - The window means only consistent miners get paid
        """
        # Get the last N shares
        window = list(self.all_shares)[-self.PPLNS_WINDOW:]

        if not window:
            return {}

        # Count shares per miner in the window
        counts: Dict[str, int] = defaultdict(int)
        for share in window:
            counts[share.miner_address] += 1

        total_shares = sum(counts.values())
        if total_shares == 0:
            return {}

        # Split proportionally
        payouts = {}
        for address, count in counts.items():
            proportion = count / total_shares
            payouts[address] = round(distributable * proportion, 8)

        return payouts

    def _distribute_prop(self, distributable: float) -> Dict[str, float]:
        """
        Proportional: Split based on shares since last block.

        This is the simplest scheme but is vulnerable to pool-hopping:
          1. Miner joins pool
          2. Waits until a block is about to be found (statistical analysis)
          3. Submits shares right before block is found
          4. Gets reward disproportionate to actual work
          5. Leaves for another pool

        PPLNS was invented to prevent this.
        """
        if not self.round_shares:
            return {}

        # Count shares per miner since last block
        counts: Dict[str, int] = defaultdict(int)
        for share in self.round_shares:
            counts[share.miner_address] += 1

        total_shares = sum(counts.values())
        if total_shares == 0:
            return {}

        # Split proportionally
        payouts = {}
        for address, count in counts.items():
            proportion = count / total_shares
            payouts[address] = round(distributable * proportion, 8)

        return payouts

    def _pps_share_value(self) -> float:
        """
        Calculate the value of one share in PPS mode.

        pps_value = block_reward / expected_shares_per_block

        This gives miners a deterministic payment per share,
        regardless of pool luck.
        """
        # Assume we know the expected block reward
        assumed_reward = 50.0  # Will be updated as halvings occur
        fee_adjusted = assumed_reward * (1 - self.POOL_FEE_PCT / 100)
        return fee_adjusted / self.EXPECTED_SHARES_PER_BLOCK

    def get_stats(self) -> dict:
        """Get reward distributor statistics."""
        return {
            "scheme": self.scheme.value,
            "pool_fee_pct": self.POOL_FEE_PCT,
            "total_shares_recorded": len(self.all_shares),
            "round_shares": len(self.round_shares),
            "total_distributed": round(self.total_distributed, 4),
            "payouts_count": len(self.payout_history),
            "unique_miners": len(self.share_counts),
            "share_counts": dict(
                sorted(self.share_counts.items(), key=lambda x: -x[1])[:10]
            ),
        }


# ──────────────────────────────────────────────
# DEMO: Compare all 3 payout schemes
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("REWARD DISTRIBUTION DEMO")
    print("=" * 60)

    # Simulate 3 miners submitting shares
    miners = {
        "Alice_addr":   {"shares": 500, "name": "Alice"},
        "Bob_addr":     {"shares": 300, "name": "Bob"},
        "Charlie_addr": {"shares": 200, "name": "Charlie"},
    }
    block_reward = 50.0

    for scheme_name, scheme in [
        ("PPS", PayoutScheme.PPS),
        ("PPLNS", PayoutScheme.PPLNS),
        ("PROPORTIONAL", PayoutScheme.PROP),
    ]:
        print(f"\n{'─' * 50}")
        print(f"Scheme: {scheme_name}")
        print(f"{'─' * 50}")

        dist = RewardDistributor(scheme=scheme)

        # Submit shares
        for addr, info in miners.items():
            for _ in range(info["shares"]):
                dist.record_share(addr, info["name"])

        # Block found! Distribute
        payouts = dist.distribute(block_reward, "Alice_addr")

        pool_fee = block_reward * (dist.POOL_FEE_PCT / 100)
        print(f"  Block reward: {block_reward} coins")
        print(f"  Pool fee ({dist.POOL_FEE_PCT}%): {pool_fee} coins")
        print(f"  Distributed: {block_reward - pool_fee} coins")
        print()

        for addr, amount in payouts.items():
            name = miners.get(addr, {}).get("name", addr)
            shares = miners.get(addr, {}).get("shares", "?")
            print(f"  {name:10s} ({shares:4d} shares) → {amount:8.4f} coins")
