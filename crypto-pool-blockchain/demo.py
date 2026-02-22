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
logger = logging.getLogger(__name__)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(message)s')


def banner(title: str):
    logger.info("\n%s", '═' * 64)
    logger.info("  %s", title)
    logger.info("%s", '═' * 64)


def section(title: str):
    logger.info("\n  ── %s %s", title, '─' * (50 - len(title)))


def pause():
    logger.info("")
    input("  [Press Enter to continue...]")


def demo_blockchain():
    banner("1. BLOCKCHAIN — Building Blocks & Mining")
    
    from blockchain.chain import Blockchain
    from blockchain.wallet import Wallet
    
    logger.info("""
  A blockchain is a chain of blocks where each block contains:
  \u2022 Transactions (data)
  \u2022 A hash of the previous block (the "chain" part)
  \u2022 A nonce (number used once \u2014 found by mining)

  Mining = finding a nonce where SHA256(block) starts with N zeros.
  More zeros = harder to find = more security.
    """)
    
    bc = Blockchain()
    miner = Wallet()
    
    logger.info("  Genesis block created automatically:")
    logger.info("  • Hash:  %s...", bc.chain[0].hash[:40])
    logger.info("  • This is block #0 — every blockchain starts here")
    
    section("Mining Blocks")
    logger.info("  Difficulty: %s (hash must start with %s)", bc.difficulty, '0' * bc.difficulty)
    
    for i in range(3):
        start = time.time()
        block = bc.mine_block(miner.address)
        elapsed = time.time() - start
        logger.info("\n  Block #%s mined in %.2fs", block.index, elapsed)
        logger.info("  • Hash:     %s...", block.hash[:40])
        logger.info("  • Previous: %s...", block.previous_hash[:40])
        logger.info("  • Nonce:    %s", "{:,}".format(block.nonce))
        logger.info("  • Txs:      %s (1 coinbase = mining reward)", len(block.transactions))
    
    logger.info("\n  Miner balance: %.2f coins", bc.get_balance(miner.address))
    logger.info("  Chain valid: %s", bc.validate_chain())
    
    return bc, miner


def demo_transactions(bc, miner):
    banner("2. TRANSACTIONS — Moving Coins")
    
    from blockchain.wallet import Wallet
    
    logger.info("""
  Transactions use the UTXO model (like Bitcoin):
  \u2022 UTXO = Unspent Transaction Output
  \u2022 To send coins, you "spend" previous outputs
  \u2022 You get change back to your own address
  \u2022 Fee = inputs - outputs (goes to the miner)
    """)
    
    alice = Wallet()
    bob = Wallet()
    
    logger.info("  Miner:  %s...", miner.address[:30])
    logger.info("  Alice:  %s...", alice.address[:30])
    logger.info("  Bob:    %s...", bob.address[:30])
    
    section("Transfer: Miner → Alice (25 coins)")
    tx = bc.create_transaction(miner, alice.address, 25.0, fee=0.5)
    if tx:
        logger.info("  Tx hash: %s...", tx.tx_hash[:32])
        logger.info("  Inputs:  %s", len(tx.inputs))
        logger.info("  Outputs: %s (25 to Alice + change to Miner)", len(tx.outputs))
        logger.info("  Fee:     0.5 coins")
        
        block = bc.mine_block(miner.address)
        logger.info("  Confirmed in block #%s", block.index)
    
    section("Transfer: Alice → Bob (10 coins)")
    tx = bc.create_transaction(alice, bob.address, 10.0, fee=0.1)
    if tx:
        block = bc.mine_block(miner.address)
        logger.info("  Confirmed in block #%s", block.index)
    
    section("Balances")
    logger.info("  Miner: %.2f coins", bc.get_balance(miner.address))
    logger.info("  Alice: %.2f coins", bc.get_balance(alice.address))
    logger.info("  Bob:   %.2f coins", bc.get_balance(bob.address))


def demo_merkle():
    banner("3. MERKLE TREE — Efficient Verification")
    
    from blockchain.merkle import MerkleTree
    
    logger.info("""
  A Merkle tree lets you verify a transaction is in a block
  WITHOUT downloading every transaction. Used by SPV (light) wallets.

  Structure:
              Root Hash
              /       \\\\
          Hash(AB)   Hash(CD)
          /    \\\\     /    \\\\
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
    logger.info("  Root:    %s...", tree.root[:40])
    logger.info("  Leaves:  %s", len(tree.leaves))
    logger.info("  Levels:  %s", len(tree.tree))
    
    section("Proof Verification")
    proof = tree.get_proof(1)
    valid = MerkleTree.verify_proof(txs[1], proof, tree.root)
    logger.info("  Verifying Tx #1 (Bob → Charlie):")
    logger.info("  Proof size: %s hashes (vs %s total txs)", len(proof), len(txs))
    logger.info("  Valid: %s", valid)
    
    fake_valid = MerkleTree.verify_proof(
        '{"from": "Hacker", "to": "Hacker", "amount": 9999}',
        proof, tree.root
    )
    logger.info("\n  Verifying FAKE transaction:")
    logger.info("  Valid: %s  ← Correctly rejected!", fake_valid)
    logger.info("\n  With millions of transactions, proof is only ~20 hashes!")


def demo_wallets():
    banner("4. WALLETS — Real ECDSA (secp256k1)")
    
    from blockchain.wallet import Wallet, validate_address, HDWallet
    
    logger.info("""
  PRODUCTION wallet using real ECDSA on secp256k1 (same as Bitcoin).

  Private Key (32 bytes)  \u2192  Public Key (33 bytes compressed)  \u2192  Address

  \u2022 Private key: 256-bit random on secp256k1 curve
  \u2022 Public key:  Elliptic curve point (compressed: 02/03 + x)
  \u2022 Address:     Base58Check(RIPEMD160(SHA256(pubkey)))
  \u2022 Signatures:  DER-encoded ECDSA with SHA-256 digest

  "Not your keys, not your coins"
    """)
    
    wallet = Wallet()
    
    logger.info("  Private Key:  %s...%s  (32 bytes)", wallet.private_key[:16], wallet.private_key[-8:])
    logger.info("  Public Key:   %s...%s  (33 bytes compressed)", wallet.public_key[:16], wallet.public_key[-8:])
    logger.info("  Address:      %s", wallet.address)
    logger.info("  Valid addr:   %s", validate_address(wallet.address))
    
    section("ECDSA Signing & Verification")
    message = "Send 10 coins to Bob"
    signature = wallet.sign(message)
    logger.info("  Message:   \"%s\"", message)
    logger.info("  Signature: %s...  (DER encoded, %s bytes)", signature[:32], len(bytes.fromhex(signature)))
    
    valid = Wallet.verify(wallet.public_key, message, signature)
    tampered = Wallet.verify(wallet.public_key, "Send 10000 coins to Hacker", signature)
    logger.info("  Valid signature:   %s", valid)
    logger.info("  Tampered message:  %s  ← Real crypto catches this!", tampered)
    
    section("Key Determinism")
    wallet2 = Wallet(wallet.private_key)
    logger.info("  Same private key → Same address: %s", wallet.address == wallet2.address)
    logger.info("  Same private key → Same pubkey:  %s", wallet.public_key == wallet2.public_key)
    
    section("BIP-39 Seed Phrase")
    phrase = Wallet.generate_seed_phrase(128)
    sw = Wallet(seed_phrase=phrase)
    logger.info("  Seed phrase:  %s", phrase)
    logger.info("  Address:      %s", sw.address)
    sw2 = Wallet(seed_phrase=phrase)
    logger.info("  Same phrase → Same wallet: %s", sw.address == sw2.address)
    
    section("HD Wallet (BIP-32/44)")
    hd = HDWallet()
    logger.info("  1 seed → unlimited addresses:")
    for i in range(3):
        w = hd.derive_wallet()
        logger.info("    m/44'/999'/0'/0/%s → %s", i, w.address)


def demo_consensus():
    banner("5. CONSENSUS — How Networks Agree")
    
    from network.consensus import ProofOfWork, ProofOfStake
    
    logger.info("""
  The "Byzantine Generals Problem": How do strangers agree on truth
  when some might be lying?

  Two main solutions:

  PoW (Proof of Work):  "I burned electricity to prove I'm serious"
    \u2192 Used by: Bitcoin, Litecoin, Dogecoin
    \u2192 Secure but energy-intensive

  PoS (Proof of Stake): "I locked up money as collateral"
    \u2192 Used by: Ethereum, Cardano, Solana
    \u2192 Energy efficient but "rich get richer" concerns
    """)
    
    section("Proof of Work")
    pow_engine = ProofOfWork(difficulty=4)
    
    hashrate = pow_engine.estimate_hashrate("test_data", 0.5)
    logger.info("  Your hashrate: %s H/s", "{:,.0f}".format(hashrate))
    logger.info("  A Bitcoin ASIC: ~200,000,000,000,000 H/s")
    logger.info("  You are %sx slower than an ASIC 😅", "{:,.0f}".format(200_000_000_000_000 / hashrate))
    
    start = time.time()
    nonce, hash_val = pow_engine.mine("block_data")
    elapsed = time.time() - start
    logger.info("\n  Mined block in %.2fs (nonce=%s)", elapsed, "{:,}".format(nonce))
    logger.info("  Hash: %s...", hash_val[:40])
    
    section("Proof of Stake")
    pos = ProofOfStake()
    pos.stake("alice", 100.0)
    pos.stake("bob", 60.0)
    pos.stake("carol", 40.0)
    
    selections = {}
    for _ in range(1000):
        v = pos.select_validator()
        selections[v] = selections.get(v, 0) + 1
    
    logger.info("  Validator selection probability (1000 rounds):")
    for addr, count in sorted(selections.items(), key=lambda x: -x[1]):
        pct = count / 10
        stake_pct = pos.validators[addr] / pos.total_staked * 100
        bar = "█" * int(pct / 2)
        logger.info("  %8s: %5.1f%% selected (stake: %.0f%%) %s", addr, pct, stake_pct, bar)
    
    section("Slashing")
    penalty = pos.slash("bob", "tried to double-sign a block")
    logger.info("  Bob caught double-signing!")
    logger.info("  Penalty: %.2f tokens destroyed", penalty)
    logger.info("  Bob's remaining stake: %.2f", pos.validators.get('bob', 0))


def demo_p2p_network():
    banner("6. P2P NETWORK — Decentralized Communication")
    
    from network.node import Network
    
    logger.info("""
  Blockchain is a P2P (peer-to-peer) network:
  \u2022 No central server \u2014 every node is equal
  \u2022 Each node keeps a full copy of the blockchain
  \u2022 New blocks/transactions are "gossiped" to peers
  \u2022 If two chains disagree \u2192 longest valid chain wins
    """)
    
    network = Network()
    node_a = network.add_node("Tokyo")
    node_b = network.add_node("London")
    node_c = network.add_node("New-York")
    
    logger.info("  Network: %s", list(network.nodes.keys()))
    
    section("Mining & Propagation")
    logger.info("  Tokyo mines 2 blocks...")
    for _ in range(2):
        block = node_a.mine_block()
        logger.info("    Block #%s → propagated to all peers", block.index)
    
    logger.info("\n  London mines 1 block...")
    block = node_b.mine_block()
    logger.info("    Block #%s → propagated to all peers", block.index)
    
    section("Chain Sync Status")
    for name, node in network.nodes.items():
        valid = node.blockchain.validate_chain()
        logger.info("  %10s: height=%s, valid=%s, msgs_recv=%s", name, node.blockchain.height, valid, node.messages_received)
    
    all_same_height = len(set(n.blockchain.height for n in network.nodes.values())) == 1
    logger.info("\n  All nodes at same height: %s", all_same_height)


def demo_mining_pool_rewards():
    banner("7. MINING POOL — Reward Distribution")
    
    from mining_pool.reward import RewardDistributor, PayoutScheme
    
    logger.info("""
  Mining pools let miners combine hashpower and split rewards.

  Without a pool: You mine alone, might wait YEARS for a block.
  With a pool: Steady smaller payments based on your contribution.

  Three payout schemes:
  \u2022 PPS:  Fixed pay per share (steady income, pool takes risk)
  \u2022 PPLNS: Pay based on last N shares (anti-pool-hopping)
  \u2022 PROP: Simple proportional split (fair but hoppable)
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
        
        logger.info("  Block reward: %s | Pool fee: %s | To miners: %s", block_reward, pool_fee, distributable)
        
        for addr, amount in payouts.items():
            name = addr.replace("_addr", "")
            shares = miners_data.get(name, 0)
            pct = (shares / sum(miners_data.values())) * 100
            logger.info("    %10s: %4d shares (%.0f%%) → %8.4f coins", name, shares, pct, amount)


def demo_immutability():
    banner("8. IMMUTABILITY — Why Blockchain Can't Be Hacked")
    
    from blockchain.chain import Blockchain
    from blockchain.wallet import Wallet
    
    logger.info("""
  What happens if you try to change a past transaction?

  The answer: EVERYTHING BREAKS.

  Changing any data in block #2 changes its hash.
  But block #3 stores block #2's hash \u2014 now they don't match.
  Block #4 stores block #3's hash \u2014 also broken.
  And so on, all the way to the latest block.

  To fake a change, you'd need to re-mine EVERY subsequent block
  faster than the entire rest of the network. Practically impossible.
    """)
    
    bc = Blockchain()
    miner = Wallet()
    
    # Mine 5 blocks
    for _ in range(5):
        bc.mine_block(miner.address)
    
    logger.info("  Chain with %s blocks — Valid: %s", bc.height, bc.validate_chain())
    
    section("Tampering Attempt")
    original_hash = bc.chain[2].hash
    logger.info("  Original block #2 hash: %s...", original_hash[:32])
    
    # Tamper with block #2 — add a fake transaction
    bc.chain[2].transactions.append({"fake": "transaction", "amount": 9999})
    
    # Recalculate merkle root (attacker must do this to update the hash)
    from blockchain.merkle import MerkleTree
    bc.chain[2].merkle_root = MerkleTree.build_root(
        [json.dumps(tx, sort_keys=True) for tx in bc.chain[2].transactions]
    )
    bc.chain[2].hash = bc.chain[2].compute_hash()
    
    new_hash = bc.chain[2].hash
    logger.info("  Tampered block #2 hash: %s...", new_hash[:32])
    hashes_differ = original_hash != new_hash
    logger.info("  Hashes differ: %s  ← hash changed!", hashes_differ)
    
    valid = bc.validate_chain()
    logger.info("\n  Chain valid after tampering: %s  ← CAUGHT!", valid)
    logger.info("\n  The chain detected the tampering because block #3's")
    logger.info("  'previous_hash' no longer matches block #2's new hash.")
    logger.info("  This is why blockchain is considered immutable.")


def main():
    logger.info("""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551   RIMURU CRYPTO POOL & BLOCKCHAIN \u2014 FULL DEMO   \u2551
\u2551                                                  \u2551
\u2551   Learn how blockchains and mining pools work    \u2551
\u2551   by building them from scratch in Python.       \u2551
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d

This demo walks through every component:
  1. Blockchain \u2014 Blocks, mining, and chain validation
  2. Transactions \u2014 UTXO model, fees, and transfers
  3. Merkle Tree \u2014 Efficient transaction verification
  4. Wallets \u2014 Keys, signatures, and addresses
  5. Consensus \u2014 Proof of Work vs Proof of Stake
  6. P2P Network \u2014 Decentralized node communication
  7. Mining Pool \u2014 Reward distribution (PPS/PPLNS/PROP)
  8. Immutability \u2014 Why you can't hack a blockchain
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
    logger.info("""
  You've seen how a PRODUCTION-GRADE blockchain works from the ground up:

  \u2713 Real ECDSA signatures on secp256k1 (same as Bitcoin)
  \u2713 Base58Check addresses with RIPEMD-160
  \u2713 BIP-39 mnemonic seed phrases
  \u2713 BIP-32/44 HD wallet key derivation
  \u2713 UTXO transaction model with real signature verification
  \u2713 Merkle trees for efficient verification
  \u2713 Proof of Work & Proof of Stake consensus
  \u2713 P2P networking and chain synchronization
  \u2713 Mining pool reward distribution (PPS/PPLNS/PROP)
  \u2713 Tamper-proof immutability

  Next steps:
  \u2022 Run individual modules: python -m blockchain.chain
  \u2022 Start the pool server: python -m mining_pool.pool_server
  \u2022 Connect miners: python -m mining_pool.miner
  \u2022 Read the source code \u2014 it's heavily commented!

  Part of the Rimuru Crypto Empire \U0001f3f0
    """)


if __name__ == "__main__":
    main()
