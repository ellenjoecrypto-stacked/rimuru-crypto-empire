"""
Rimuru Crypto Pool & Blockchain — Interactive Demo
====================================================

Runs through every component of the project with explanations.
Shows: blockchain creation, mining, transactions, wallets,
Merkle trees, consensus, P2P networking, and mining pool payouts.

Usage:
    cd crypto-pool-blockchain
    python demo.py
"""

import sys
import os
import time
import json
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.WARNING)


def banner(title: str):
    print(f"\n{'═' * 64}")
    print(f"  {title}")
    print(f"{'═' * 64}")


def section(title: str):
    print(f"\n  ── {title} {'─' * (50 - len(title))}")


def pause():
    print()
    input("  [Press Enter to continue...]")


def demo_blockchain():
    banner("1. BLOCKCHAIN — Building Blocks & Mining")
    
    from blockchain.chain import Blockchain
    from blockchain.wallet import Wallet
    
    print("""
  A blockchain is a chain of blocks where each block contains:
  • Transactions (data)
  • A hash of the previous block (the "chain" part)
  • A nonce (number used once — found by mining)
  
  Mining = finding a nonce where SHA256(block) starts with N zeros.
  More zeros = harder to find = more security.
    """)
    
    bc = Blockchain()
    miner = Wallet()
    
    print(f"  Genesis block created automatically:")
    print(f"  • Hash:  {bc.chain[0].hash[:40]}...")
    print(f"  • This is block #0 — every blockchain starts here")
    
    section("Mining Blocks")
    print(f"  Difficulty: {bc.difficulty} (hash must start with {'0' * bc.difficulty})")
    
    for i in range(3):
        start = time.time()
        block = bc.mine_block(miner.address)
        elapsed = time.time() - start
        print(f"\n  Block #{block.index} mined in {elapsed:.2f}s")
        print(f"  • Hash:     {block.hash[:40]}...")
        print(f"  • Previous: {block.previous_hash[:40]}...")
        print(f"  • Nonce:    {block.nonce:,}")
        print(f"  • Txs:      {len(block.transactions)} (1 coinbase = mining reward)")
    
    print(f"\n  Miner balance: {bc.get_balance(miner.address):.2f} coins")
    print(f"  Chain valid: {bc.validate_chain()}")
    
    return bc, miner


def demo_transactions(bc, miner):
    banner("2. TRANSACTIONS — Moving Coins")
    
    from blockchain.wallet import Wallet
    
    print("""
  Transactions use the UTXO model (like Bitcoin):
  • UTXO = Unspent Transaction Output
  • To send coins, you "spend" previous outputs
  • You get change back to your own address
  • Fee = inputs - outputs (goes to the miner)
    """)
    
    alice = Wallet()
    bob = Wallet()
    
    print(f"  Miner:  {miner.address[:30]}...")
    print(f"  Alice:  {alice.address[:30]}...")
    print(f"  Bob:    {bob.address[:30]}...")
    
    section("Transfer: Miner → Alice (25 coins)")
    tx = bc.create_transaction(miner, alice.address, 25.0, fee=0.5)
    if tx:
        print(f"  Tx hash: {tx.tx_hash[:32]}...")
        print(f"  Inputs:  {len(tx.inputs)}")
        print(f"  Outputs: {len(tx.outputs)} (25 to Alice + change to Miner)")
        print(f"  Fee:     0.5 coins")
        
        block = bc.mine_block(miner.address)
        print(f"  Confirmed in block #{block.index}")
    
    section("Transfer: Alice → Bob (10 coins)")
    tx = bc.create_transaction(alice, bob.address, 10.0, fee=0.1)
    if tx:
        block = bc.mine_block(miner.address)
        print(f"  Confirmed in block #{block.index}")
    
    section("Balances")
    print(f"  Miner: {bc.get_balance(miner.address):.2f} coins")
    print(f"  Alice: {bc.get_balance(alice.address):.2f} coins")
    print(f"  Bob:   {bc.get_balance(bob.address):.2f} coins")


def demo_merkle():
    banner("3. MERKLE TREE — Efficient Verification")
    
    from blockchain.merkle import MerkleTree
    
    print("""
  A Merkle tree lets you verify a transaction is in a block
  WITHOUT downloading every transaction. Used by SPV (light) wallets.
  
  Structure:
              Root Hash
              /       \\
          Hash(AB)   Hash(CD)
          /    \\     /    \\
      Hash(A) Hash(B) Hash(C) Hash(D)
        |       |       |       |
      Tx A    Tx B    Tx C    Tx D
    """)
    
    txs = [
        '{"from": "Alice", "to": "Bob", "amount": 10}',
        '{"from": "Bob", "to": "Charlie", "amount": 5}',
        '{"from": "Charlie", "to": "Dave", "amount": 3}',
        '{"from": "Dave", "to": "Eve", "amount": 1}',
    ]
    
    tree = MerkleTree(txs)
    
    section("Tree Built")
    print(f"  Root:    {tree.root[:40]}...")
    print(f"  Leaves:  {len(tree.leaves)}")
    print(f"  Levels:  {len(tree.tree)}")
    
    section("Proof Verification")
    proof = tree.get_proof(1)
    valid = MerkleTree.verify_proof(txs[1], proof, tree.root)
    print(f"  Verifying Tx #1 (Bob → Charlie):")
    print(f"  Proof size: {len(proof)} hashes (vs {len(txs)} total txs)")
    print(f"  Valid: {valid}")
    
    fake_valid = MerkleTree.verify_proof(
        '{"from": "Hacker", "to": "Hacker", "amount": 9999}',
        proof, tree.root
    )
    print(f"\n  Verifying FAKE transaction:")
    print(f"  Valid: {fake_valid}  ← Correctly rejected!")
    print(f"\n  With millions of transactions, proof is only ~20 hashes!")


def demo_wallets():
    banner("4. WALLETS — Keys & Signatures")
    
    from blockchain.wallet import Wallet
    
    print("""
  Wallet security is based on asymmetric cryptography:
  
  Private Key  →  Public Key  →  Address
  (secret)        (shareable)     (public identity)
  
  • Private key: 256-bit random number (NEVER share!)
  • Public key: Derived from private key (one-way function)
  • Address: Hash of public key (what you give people to pay you)
  
  "Not your keys, not your coins" — if you lose your private key,
  your coins are gone FOREVER. No customer support. No reset button.
    """)
    
    wallet = Wallet()
    
    print(f"  Private Key: {wallet.private_key[:20]}... (256-bit, KEEP SECRET)")
    print(f"  Public Key:  {wallet.public_key[:20]}... (derived from private)")
    print(f"  Address:     {wallet.address} (share freely)")
    
    section("Digital Signature")
    message = "Send 10 coins to Bob"
    signature = wallet.sign(message)
    print(f"  Message:   \"{message}\"")
    print(f"  Signature: {signature[:32]}...")
    print(f"  This proves you own the private key WITHOUT revealing it!")
    
    section("Key Determinism")
    wallet2 = Wallet(wallet.private_key)
    print(f"  Same private key → Same address: {wallet.address == wallet2.address}")
    print(f"  This is why you can restore wallets from backup/seed phrase")


def demo_consensus():
    banner("5. CONSENSUS — How Networks Agree")
    
    from network.consensus import ProofOfWork, ProofOfStake
    
    print("""
  The "Byzantine Generals Problem": How do strangers agree on truth
  when some might be lying?
  
  Two main solutions:
  
  PoW (Proof of Work):  "I burned electricity to prove I'm serious"
    → Used by: Bitcoin, Litecoin, Dogecoin
    → Secure but energy-intensive
  
  PoS (Proof of Stake): "I locked up money as collateral"
    → Used by: Ethereum, Cardano, Solana
    → Energy efficient but "rich get richer" concerns
    """)
    
    section("Proof of Work")
    pow_engine = ProofOfWork(difficulty=4)
    
    hashrate = pow_engine.estimate_hashrate("test_data", 0.5)
    print(f"  Your hashrate: {hashrate:,.0f} H/s")
    print(f"  A Bitcoin ASIC: ~200,000,000,000,000 H/s")
    print(f"  You are {200_000_000_000_000 / hashrate:,.0f}x slower than an ASIC 😅")
    
    start = time.time()
    nonce, hash_val = pow_engine.mine("block_data")
    elapsed = time.time() - start
    print(f"\n  Mined block in {elapsed:.2f}s (nonce={nonce:,})")
    print(f"  Hash: {hash_val[:40]}...")
    
    section("Proof of Stake")
    pos = ProofOfStake()
    pos.stake("alice", 100.0)
    pos.stake("bob", 60.0)
    pos.stake("carol", 40.0)
    
    selections = {}
    for _ in range(1000):
        v = pos.select_validator()
        selections[v] = selections.get(v, 0) + 1
    
    print(f"  Validator selection probability (1000 rounds):")
    for addr, count in sorted(selections.items(), key=lambda x: -x[1]):
        pct = count / 10
        stake_pct = pos.validators[addr] / pos.total_staked * 100
        bar = "█" * int(pct / 2)
        print(f"  {addr:8s}: {pct:5.1f}% selected (stake: {stake_pct:.0f}%) {bar}")
    
    section("Slashing")
    penalty = pos.slash("bob", "tried to double-sign a block")
    print(f"  Bob caught double-signing!")
    print(f"  Penalty: {penalty:.2f} tokens destroyed")
    print(f"  Bob's remaining stake: {pos.validators.get('bob', 0):.2f}")


def demo_p2p_network():
    banner("6. P2P NETWORK — Decentralized Communication")
    
    from network.node import Network
    
    print("""
  Blockchain is a P2P (peer-to-peer) network:
  • No central server — every node is equal
  • Each node keeps a full copy of the blockchain
  • New blocks/transactions are "gossiped" to peers
  • If two chains disagree → longest valid chain wins
    """)
    
    network = Network()
    node_a = network.add_node("Tokyo")
    node_b = network.add_node("London")
    node_c = network.add_node("New-York")
    
    print(f"  Network: {list(network.nodes.keys())}")
    
    section("Mining & Propagation")
    print(f"  Tokyo mines 2 blocks...")
    for _ in range(2):
        block = node_a.mine_block()
        print(f"    Block #{block.index} → propagated to all peers")
    
    print(f"\n  London mines 1 block...")
    block = node_b.mine_block()
    print(f"    Block #{block.index} → propagated to all peers")
    
    section("Chain Sync Status")
    for name, node in network.nodes.items():
        valid = node.blockchain.validate_chain()
        print(f"  {name:10s}: height={node.blockchain.height}, valid={valid}, msgs_recv={node.messages_received}")
    
    all_same_height = len(set(n.blockchain.height for n in network.nodes.values())) == 1
    print(f"\n  All nodes at same height: {all_same_height}")


def demo_mining_pool_rewards():
    banner("7. MINING POOL — Reward Distribution")
    
    from mining_pool.reward import RewardDistributor, PayoutScheme
    
    print("""
  Mining pools let miners combine hashpower and split rewards.
  
  Without a pool: You mine alone, might wait YEARS for a block.
  With a pool: Steady smaller payments based on your contribution.
  
  Three payout schemes:
  • PPS:  Fixed pay per share (steady income, pool takes risk)
  • PPLNS: Pay based on last N shares (anti-pool-hopping)
  • PROP: Simple proportional split (fair but hoppable)
    """)
    
    miners_data = {
        "Alice":   500,
        "Bob":     300,
        "Charlie": 200,
    }
    block_reward = 50.0
    
    for scheme_name, scheme in [
        ("PPS (Pay Per Share)", PayoutScheme.PPS),
        ("PPLNS (Pay Per Last N Shares)", PayoutScheme.PPLNS),
        ("Proportional", PayoutScheme.PROP),
    ]:
        section(scheme_name)
        
        dist = RewardDistributor(scheme=scheme)
        
        for name, shares in miners_data.items():
            for _ in range(shares):
                dist.record_share(f"{name}_addr", name)
        
        payouts = dist.distribute(block_reward, "Alice_addr")
        
        pool_fee = block_reward * (dist.POOL_FEE_PCT / 100)
        distributable = block_reward - pool_fee
        
        print(f"  Block reward: {block_reward} | Pool fee: {pool_fee} | To miners: {distributable}")
        
        for addr, amount in payouts.items():
            name = addr.replace("_addr", "")
            shares = miners_data.get(name, 0)
            pct = (shares / sum(miners_data.values())) * 100
            print(f"    {name:10s}: {shares:4d} shares ({pct:.0f}%) → {amount:8.4f} coins")


def demo_immutability():
    banner("8. IMMUTABILITY — Why Blockchain Can't Be Hacked")
    
    from blockchain.chain import Blockchain
    from blockchain.wallet import Wallet
    
    print("""
  What happens if you try to change a past transaction?
  
  The answer: EVERYTHING BREAKS.
  
  Changing any data in block #2 changes its hash.
  But block #3 stores block #2's hash — now they don't match.
  Block #4 stores block #3's hash — also broken.
  And so on, all the way to the latest block.
  
  To fake a change, you'd need to re-mine EVERY subsequent block
  faster than the entire rest of the network. Practically impossible.
    """)
    
    bc = Blockchain()
    miner = Wallet()
    
    # Mine 5 blocks
    for _ in range(5):
        bc.mine_block(miner.address)
    
    print(f"  Chain with {bc.height} blocks — Valid: {bc.validate_chain()}")
    
    section("Tampering Attempt")
    original_hash = bc.chain[2].hash
    print(f"  Original block #2 hash: {original_hash[:32]}...")
    
    # Tamper with block #2 — add a fake transaction
    bc.chain[2].transactions.append({"fake": "transaction", "amount": 9999})
    
    # Recalculate merkle root (attacker must do this to update the hash)
    from blockchain.merkle import MerkleTree
    bc.chain[2].merkle_root = MerkleTree.build_root(
        [json.dumps(tx, sort_keys=True) for tx in bc.chain[2].transactions]
    )
    bc.chain[2].hash = bc.chain[2].compute_hash()
    
    new_hash = bc.chain[2].hash
    print(f"  Tampered block #2 hash: {new_hash[:32]}...")
    hashes_differ = original_hash != new_hash
    print(f"  Hashes differ: {hashes_differ}  ← hash changed!")
    
    valid = bc.validate_chain()
    print(f"\n  Chain valid after tampering: {valid}  ← CAUGHT!")
    print(f"\n  The chain detected the tampering because block #3's")
    print(f"  'previous_hash' no longer matches block #2's new hash.")
    print(f"  This is why blockchain is considered immutable.")


def main():
    print("""
╔══════════════════════════════════════════════════╗
║   RIMURU CRYPTO POOL & BLOCKCHAIN — FULL DEMO   ║
║                                                  ║
║   Learn how blockchains and mining pools work    ║
║   by building them from scratch in Python.       ║
╚══════════════════════════════════════════════════╝

This demo walks through every component:
  1. Blockchain — Blocks, mining, and chain validation
  2. Transactions — UTXO model, fees, and transfers
  3. Merkle Tree — Efficient transaction verification
  4. Wallets — Keys, signatures, and addresses
  5. Consensus — Proof of Work vs Proof of Stake
  6. P2P Network — Decentralized node communication
  7. Mining Pool — Reward distribution (PPS/PPLNS/PROP)
  8. Immutability — Why you can't hack a blockchain
    """)
    
    pause()
    
    bc, miner = demo_blockchain()
    pause()
    
    demo_transactions(bc, miner)
    pause()
    
    demo_merkle()
    pause()
    
    demo_wallets()
    pause()
    
    demo_consensus()
    pause()
    
    demo_p2p_network()
    pause()
    
    demo_mining_pool_rewards()
    pause()
    
    demo_immutability()
    
    banner("DEMO COMPLETE")
    print("""
  You've seen how a blockchain works from the ground up:
  
  ✓ SHA-256 hashing and proof of work
  ✓ Transaction creation with the UTXO model
  ✓ Merkle trees for efficient verification
  ✓ Wallet key generation and digital signatures
  ✓ Proof of Work vs Proof of Stake consensus
  ✓ P2P networking and chain synchronization
  ✓ Mining pool reward distribution schemes
  ✓ Why blockchains are immutable (tamper-proof)
  
  Next steps:
  • Run individual modules: python -m blockchain.chain
  • Start the pool server: python -m mining_pool.pool_server
  • Connect miners: python -m mining_pool.miner
  • Read the source code — it's heavily commented!
  
  Part of the Rimuru Crypto Empire 🏰
    """)


if __name__ == "__main__":
    main()
