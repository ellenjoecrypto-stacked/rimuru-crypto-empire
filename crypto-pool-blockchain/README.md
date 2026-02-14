# Rimuru Crypto Pool & Blockchain — From Scratch

> **A complete educational project** that builds a working blockchain and mining pool
> in pure Python. No external crypto libraries — everything from first principles.

---

## What This Project Builds

| Component | What It Does |
|-----------|-------------|
| **Blockchain** | SHA-256 chained blocks, proof-of-work, immutability verification |
| **Transactions** | ECDSA-signed transfers with input/output model (like Bitcoin) |
| **Wallets** | Key generation, address derivation, transaction signing |
| **Merkle Tree** | Efficient transaction verification (how SPV nodes work) |
| **Mining Pool** | Coordinator server that distributes work to miners |
| **Miners** | Workers that find valid hashes and submit shares |
| **Reward System** | PPS, PPLNS, and Proportional payout schemes |
| **P2P Network** | Node discovery, block propagation, chain sync |
| **Consensus** | Proof-of-Work + Proof-of-Stake implementations |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    P2P NETWORK                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │  Node A  │◄──│  Node B  │──►│  Node C  │            │
│  └────┬─────┘   └────┬─────┘   └──────────┘            │
│       │              │                                   │
│  ┌────▼─────┐   ┌────▼─────┐                            │
│  │Blockchain│   │Blockchain│   (Each node has a copy)   │
│  └────┬─────┘   └──────────┘                            │
│       │                                                  │
│  ┌────▼──────────────────────┐                          │
│  │      MINING POOL          │                          │
│  │  ┌───────┐ ┌───────┐     │                          │
│  │  │Miner 1│ │Miner 2│ ... │  (Workers find hashes)   │
│  │  └───────┘ └───────┘     │                          │
│  │  ┌─────────────────────┐ │                          │
│  │  │  Reward Distributor │ │  (PPS / PPLNS / PROP)    │
│  │  └─────────────────────┘ │                          │
│  └───────────────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

---

## How a Blockchain Works (Explained)

### 1. Blocks
A block is a container that holds:
- **Transactions** — the actual data (who sent what to whom)
- **Previous hash** — the hash of the block before it (forms the chain)
- **Nonce** — a number miners change to find a valid hash
- **Merkle root** — a single hash representing all transactions
- **Timestamp** — when the block was created

### 2. Proof of Work
To add a block, a miner must find a nonce such that:
```
SHA256(block_header + nonce) < target
```
The "target" controls difficulty — lower target = harder to find.
This is intentionally slow and energy-intensive, which is what makes the chain secure.

### 3. Chain Immutability
Changing any transaction in block #50 would change its hash, which would
invalidate block #51's "previous hash", and #52's, and so on. An attacker
would need to re-mine every subsequent block faster than the rest of the
network — practically impossible.

### 4. Consensus
When two miners find a block at the same time, a fork occurs. The network
resolves this by always choosing the **longest valid chain** (most work done).

---

## How a Mining Pool Works (Explained)

### The Problem
Solo mining is like buying one lottery ticket. You might never win.
A mining pool lets miners combine their hashpower and split rewards.

### How Shares Work
The pool gives each miner an **easier target** to hit. When a miner finds
a hash below this easier target, it's called a "share". Shares prove the
miner is doing work, even if the hash isn't low enough for the real blockchain.

Occasionally, a share IS low enough for the real chain → the pool found a block!
The reward is then split among all miners based on their shares.

### Payout Schemes
| Scheme | How It Works | Risk |
|--------|-------------|------|
| **PPS** (Pay Per Share) | Fixed payment per share, regardless of blocks found | Pool takes the variance risk |
| **PPLNS** (Pay Per Last N Shares) | Payment based on shares in the last N window | Miners share the variance |
| **PROP** (Proportional) | Split block reward by share percentage | Hop-proof, fair |

---

## Quick Start

```bash
cd crypto-pool-blockchain

# Install dependencies
pip install -r requirements.txt

# Run the interactive demo
python demo.py

# Or run individual components:
python -m blockchain.demo_chain      # Watch blocks being mined
python -m mining_pool.demo_pool      # See pool mining in action
python -m network.demo_network       # Watch nodes sync
```

---

## Project Structure

```
crypto-pool-blockchain/
├── blockchain/
│   ├── __init__.py
│   ├── block.py           # Block with SHA-256 hashing
│   ├── chain.py           # Full blockchain + validation
│   ├── transaction.py     # Transaction model (inputs/outputs)
│   ├── wallet.py          # ECDSA key generation & signing
│   └── merkle.py          # Merkle tree implementation
├── mining_pool/
│   ├── __init__.py
│   ├── pool_server.py     # Pool coordinator (FastAPI)
│   ├── miner.py           # Mining worker
│   └── reward.py          # PPS / PPLNS / PROP payouts
├── network/
│   ├── __init__.py
│   ├── node.py            # P2P node with chain sync
│   └── consensus.py       # PoW + PoS mechanisms
├── demo.py                # Full interactive demo
├── requirements.txt
└── README.md              # This file
```

---

## Key Concepts You'll Learn

1. **Cryptographic hashing** — SHA-256, why it's one-way, avalanche effect
2. **Digital signatures** — ECDSA, public/private keys, verification
3. **Merkle trees** — How Bitcoin verifies transactions efficiently
4. **Proof of Work** — Mining, difficulty adjustment, nonce hunting
5. **Proof of Stake** — Validator selection by stake weight
6. **UTXO model** — Unspent Transaction Outputs (how Bitcoin tracks balances)
7. **Mining pools** — Share submission, work distribution, payout math
8. **P2P networking** — Gossip protocol, chain synchronization
9. **Consensus** — Longest chain rule, fork resolution
10. **Difficulty adjustment** — Keeping block times consistent

---

*Part of the Rimuru Crypto Empire*
