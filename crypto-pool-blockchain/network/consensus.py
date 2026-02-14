"""
Consensus Mechanisms — How blockchains agree on truth.
=======================================================

The "Byzantine Generals Problem": How do independent parties agree
on a single version of truth when some might be lying?

Blockchain solved this with consensus mechanisms:

═══════════════════════════════════════════════════════════════════

1. Proof of Work (PoW) — "Prove you did the work"
   ─────────────────────────────────────────────────
   Used by: Bitcoin, Litecoin, Dogecoin, Monero

   How: Find a nonce where SHA256(block_header + nonce) < target
   Security: An attacker needs >50% of global hashpower
   Energy: HIGH — entire networks of ASICs running 24/7
   Decentralization: Anyone with hardware can mine

   The "longest chain" rule:
     If two miners find a block simultaneously → fork
     Miners build on whichever block they see first
     Eventually one fork gets ahead → the other is abandoned
     This is why you wait for "6 confirmations" — very unlikely
     to reorganize 6 blocks deep.

═══════════════════════════════════════════════════════════════════

2. Proof of Stake (PoS) — "Prove you have skin in the game"
   ──────────────────────────────────────────────────────────
   Used by: Ethereum (since 2022), Cardano, Solana*, Polkadot

   How: Validators lock up (stake) tokens as collateral.
        They're randomly selected to propose blocks based on stake.
        If they cheat, their stake is "slashed" (destroyed).
   Security: An attacker needs >33% of all staked tokens
   Energy: LOW — no mining hardware needed
   Decentralization: Concerns about "rich get richer"

   *Solana uses Proof of History + PoS hybrid

═══════════════════════════════════════════════════════════════════

3. Delegated Proof of Stake (DPoS)
   ─────────────────────────────────
   Used by: EOS, Tron, Lisk

   How: Token holders vote for "delegates" who produce blocks.
   Like a representative democracy for blockchains.

═══════════════════════════════════════════════════════════════════
"""

import hashlib
import json
import time
import random
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("rimuru.consensus")


class ProofOfWork:
    """
    Proof of Work consensus mechanism.

    The core algorithm that Bitcoin uses to secure its blockchain.
    Miners compete to find a hash below the target difficulty.
    The first one to find it gets to add the next block.
    """

    def __init__(self, difficulty: int = 4):
        self.difficulty = difficulty
        self.target = "0" * difficulty

    def mine(self, block_data: str) -> Tuple[int, str]:
        """
        Find a nonce that produces a valid hash.

        This is the actual mining process:
          for nonce in 0, 1, 2, 3, ... infinity:
              hash = SHA256(block_data + nonce)
              if hash < target:
                  return nonce, hash

        Returns (nonce, hash).
        """
        nonce = 0
        while True:
            attempt = f"{block_data}:{nonce}"
            hash_val = hashlib.sha256(attempt.encode()).hexdigest()

            if hash_val.startswith(self.target):
                return nonce, hash_val

            nonce += 1

    def verify(self, block_data: str, nonce: int) -> bool:
        """Verify that a nonce produces a valid hash."""
        attempt = f"{block_data}:{nonce}"
        hash_val = hashlib.sha256(attempt.encode()).hexdigest()
        return hash_val.startswith(self.target)

    def estimate_hashrate(self, block_data: str, duration_sec: float = 1.0) -> float:
        """
        Estimate the hashrate (hashes per second).

        This is what mining pools measure to estimate earnings.
        
        Real hashrates:
          CPU:     ~10 MH/s    (10 million hashes/sec)
          GPU:     ~100 MH/s   (100 million hashes/sec)
          ASIC:    ~100 TH/s   (100 trillion hashes/sec)
          Python:  ~100 KH/s   (100 thousand hashes/sec) 😅
        """
        count = 0
        start = time.time()

        while time.time() - start < duration_sec:
            hashlib.sha256(f"{block_data}:{count}".encode()).hexdigest()
            count += 1

        return count / duration_sec

    @staticmethod
    def difficulty_to_target(difficulty: int) -> int:
        """
        Convert difficulty to a numeric target.

        In Bitcoin, difficulty represents how many times harder it is
        to find a block compared to the easiest possible target.

        Difficulty 1: target = 0x00000000FFFF...
        Difficulty 2: target = 0x000000007FFF...
        
        Higher difficulty = lower target = harder to mine
        """
        max_target = 2 ** 256 - 1
        return max_target // (2 ** difficulty)


class ProofOfStake:
    """
    Proof of Stake consensus mechanism.

    Instead of burning electricity (PoW), validators lock up tokens.
    The probability of being selected to create a block is proportional
    to the amount staked.

    Key concepts:
      - Staking: Locking tokens as collateral
      - Validators: Nodes that stake and produce blocks
      - Slashing: Penalty for malicious behavior (lose staked tokens)
      - Epochs: Fixed time periods where validators rotate
      - Finality: Once a block is finalized, it can NEVER be reversed
    """

    MIN_STAKE = 32.0  # Minimum stake requirement (like Ethereum's 32 ETH)
    SLASH_PENALTY_PCT = 10.0  # Lose 10% of stake for bad behavior
    ANNUAL_YIELD_PCT = 5.0  # Staking rewards (~5% APY)

    def __init__(self):
        self.validators: Dict[str, float] = {}  # address → staked amount
        self.slashed: Dict[str, float] = {}  # address → total slashed
        self.blocks_produced: Dict[str, int] = {}  # address → blocks created
        self.total_staked = 0.0

    def stake(self, address: str, amount: float) -> bool:
        """
        Become a validator by staking tokens.

        In Ethereum:
          - Minimum 32 ETH (~$80,000 at current prices)
          - Tokens are locked for months/years
          - You earn ~5% APY in staking rewards
          - If you go offline, you slowly lose stake
          - If you cheat, you lose everything (slashed)
        """
        if amount < self.MIN_STAKE:
            logger.warning(
                "Stake too low: %.2f < %.2f minimum", amount, self.MIN_STAKE
            )
            return False

        self.validators[address] = self.validators.get(address, 0) + amount
        self.total_staked += amount
        self.blocks_produced.setdefault(address, 0)

        logger.info(
            "Validator %s staked %.2f (total stake: %.2f)",
            address[:16], amount, self.validators[address],
        )
        return True

    def unstake(self, address: str) -> float:
        """
        Stop being a validator and withdraw stake.

        In real PoS, there's a "cooldown period" (days to weeks)
        to prevent validators from staking, cheating, and running.
        """
        if address not in self.validators:
            return 0.0

        amount = self.validators.pop(address)
        self.total_staked -= amount

        logger.info("Validator %s unstaked %.2f", address[:16], amount)
        return amount

    def select_validator(self) -> Optional[str]:
        """
        Select a validator to produce the next block.

        Selection is weighted by stake amount:
          - Alice stakes 100 tokens → 50% chance
          - Bob stakes 60 tokens   → 30% chance
          - Carol stakes 40 tokens → 20% chance

        Real PoS adds randomness sources (VRF, RANDAO) to prevent
        prediction and manipulation.

        Ethereum uses committees of 128+ validators for each slot,
        with a randomly selected proposer.
        """
        if not self.validators:
            return None

        addresses = list(self.validators.keys())
        stakes = list(self.validators.values())
        total = sum(stakes)

        if total == 0:
            return None

        # Weighted random selection
        weights = [s / total for s in stakes]
        selected = random.choices(addresses, weights=weights, k=1)[0]

        return selected

    def produce_block(self, validator_address: str, block_data: str) -> dict:
        """
        Produce a new block (selected validator creates it).

        Unlike PoW, there's no mining — the validator just assembles
        the block and signs it. This is why PoS uses >99% less energy.

        The block is valid if:
          1. The validator was properly selected
          2. The block data is correct
          3. The validator's signature is valid
        """
        if validator_address not in self.validators:
            raise ValueError(f"{validator_address} is not a validator")

        block_hash = hashlib.sha256(
            f"{block_data}:{validator_address}:{time.time()}".encode()
        ).hexdigest()

        self.blocks_produced[validator_address] = (
            self.blocks_produced.get(validator_address, 0) + 1
        )

        return {
            "validator": validator_address,
            "block_hash": block_hash,
            "stake": self.validators[validator_address],
            "timestamp": time.time(),
        }

    def slash(self, address: str, reason: str) -> float:
        """
        Slash a validator for bad behavior.

        Reasons for slashing:
          - Double-signing: proposing two different blocks at the same height
          - Surround voting: casting contradictory attestations
          - Being offline: not participating when selected

        In Ethereum, slashing can destroy up to 100% of stake
        for coordinated attacks.
        """
        if address not in self.validators:
            return 0.0

        stake = self.validators[address]
        penalty = stake * (self.SLASH_PENALTY_PCT / 100)

        self.validators[address] -= penalty
        self.total_staked -= penalty
        self.slashed[address] = self.slashed.get(address, 0) + penalty

        logger.warning(
            "SLASHED %s for %s: lost %.2f (%.1f%% of stake)",
            address[:16], reason, penalty, self.SLASH_PENALTY_PCT,
        )

        # Remove if stake drops below minimum
        if self.validators[address] < self.MIN_STAKE:
            remaining = self.validators.pop(address)
            self.total_staked -= remaining
            logger.warning(
                "Validator %s removed — stake below minimum after slashing",
                address[:16],
            )

        return penalty

    def calculate_rewards(self, blocks_this_epoch: int) -> Dict[str, float]:
        """
        Calculate staking rewards for an epoch.

        Rewards incentivize validators to stay online and honest.
        Annual yield is ~5% of stake, distributed per block.
        """
        if not self.validators or blocks_this_epoch == 0:
            return {}

        # Annual yield converted to per-block
        blocks_per_year = 365 * 24 * 60  # Assuming 1 block per minute
        reward_rate = self.ANNUAL_YIELD_PCT / 100 / blocks_per_year

        rewards = {}
        for address, stake in self.validators.items():
            blocks_by_validator = self.blocks_produced.get(address, 0)
            if blocks_by_validator > 0:
                rewards[address] = round(stake * reward_rate * blocks_this_epoch, 8)

        return rewards

    def get_stats(self) -> dict:
        """Get PoS statistics."""
        return {
            "total_staked": self.total_staked,
            "validator_count": len(self.validators),
            "validators": [
                {
                    "address": addr[:20] + "...",
                    "stake": stake,
                    "pct": round(stake / self.total_staked * 100, 1) if self.total_staked > 0 else 0,
                    "blocks": self.blocks_produced.get(addr, 0),
                }
                for addr, stake in sorted(
                    self.validators.items(), key=lambda x: -x[1]
                )
            ],
        }


# ──────────────────────────────────────────────
# DEMO: Compare PoW vs PoS
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("CONSENSUS MECHANISMS DEMO")
    print("=" * 60)

    # ── Proof of Work ──
    print("\n╔══════════════════════════════╗")
    print("║     PROOF OF WORK (PoW)      ║")
    print("╚══════════════════════════════╝")

    pow_engine = ProofOfWork(difficulty=4)
    block_data = "block_header_with_transactions"

    print(f"Difficulty: {pow_engine.difficulty} (need {pow_engine.target} prefix)")

    # Estimate hashrate
    hashrate = pow_engine.estimate_hashrate(block_data, 0.5)
    print(f"Hashrate: {hashrate:,.0f} H/s")

    # Mine a block
    start = time.time()
    nonce, hash_val = pow_engine.mine(block_data)
    elapsed = time.time() - start

    print(f"Mined in {elapsed:.2f}s!")
    print(f"  Nonce: {nonce:,}")
    print(f"  Hash:  {hash_val[:32]}...")
    print(f"  Valid: {pow_engine.verify(block_data, nonce)}")

    # ── Proof of Stake ──
    print("\n╔══════════════════════════════╗")
    print("║    PROOF OF STAKE (PoS)      ║")
    print("╚══════════════════════════════╝")

    pos = ProofOfStake()

    # Validators stake tokens
    pos.stake("alice_validator", 100.0)
    pos.stake("bob_validator", 60.0)
    pos.stake("carol_validator", 40.0)

    # Simulate block production
    selection_count = {"alice_validator": 0, "bob_validator": 0, "carol_validator": 0}
    rounds = 1000

    for _ in range(rounds):
        selected = pos.select_validator()
        if selected:
            selection_count[selected] += 1

    print(f"\nAfter {rounds} rounds of validator selection:")
    for addr, count in sorted(selection_count.items(), key=lambda x: -x[1]):
        pct = count / rounds * 100
        stake = pos.validators.get(addr, 0)
        stake_pct = stake / pos.total_staked * 100
        print(f"  {addr:20s}: selected {pct:5.1f}% (stake: {stake_pct:.1f}%)")

    # Demonstrate slashing
    print("\n--- Slashing Demo ---")
    penalty = pos.slash("bob_validator", "double-signing")
    print(f"Bob slashed {penalty:.2f} tokens for double-signing")
    print(f"Bob remaining stake: {pos.validators.get('bob_validator', 0):.2f}")

    print(f"\n--- Final Stats ---")
    stats = pos.get_stats()
    print(f"Total staked: {stats['total_staked']:.2f}")
    for v in stats["validators"]:
        print(f"  {v['address']} — {v['stake']:.2f} ({v['pct']}%)")
