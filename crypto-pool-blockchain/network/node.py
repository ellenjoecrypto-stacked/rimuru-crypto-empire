"""
P2P Node — Peer-to-peer networking for blockchain.
=====================================================

How blockchain nodes communicate:

1. DISCOVERY: Nodes find each other (DNS seeds, hardcoded peers, mDNS)
2. HANDSHAKE: Exchange version info and capabilities
3. SYNC: Download blockchain from peers (longest valid chain wins)
4. PROPAGATION: New blocks and transactions are "gossiped" to peers
5. VALIDATION: Each node independently validates everything

The gossip protocol:
  - When a node creates a transaction → broadcast to all peers
  - Each peer validates it → broadcasts to THEIR peers
  - Within seconds, the entire network knows about the transaction

Fork resolution:
  - Two miners find a block at the same time → temporary fork
  - Each node follows the chain it saw first
  - Eventually one chain grows longer → the network converges
  - The shorter fork's blocks become "orphan blocks" (discarded)

This implementation simulates a P2P network using in-memory connections
(no actual TCP/UDP) for educational purposes.
"""

import time
import json
import logging
import hashlib
import threading
from typing import Dict, List, Set, Optional
from copy import deepcopy

import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from blockchain.chain import Blockchain
from blockchain.block import Block
from blockchain.transaction import Transaction
from blockchain.wallet import Wallet

logger = logging.getLogger("rimuru.node")


class Message:
    """A message sent between nodes."""
    def __init__(self, msg_type: str, payload: dict, sender: str):
        self.msg_type = msg_type  # "new_block", "new_tx", "request_chain", "chain_response"
        self.payload = payload
        self.sender = sender
        self.timestamp = time.time()
        self.msg_id = hashlib.sha256(
            f"{msg_type}:{json.dumps(payload, sort_keys=True)}:{time.time()}".encode()
        ).hexdigest()[:16]


class Node:
    """
    A blockchain node in the P2P network.

    Each node:
      - Maintains its own copy of the blockchain
      - Validates all blocks and transactions independently
      - Propagates new blocks and transactions to peers
      - Resolves forks using the longest-chain rule
    """

    def __init__(self, name: str, network: "Network"):
        self.name = name
        self.network = network
        self.blockchain = Blockchain()
        self.wallet = Wallet()
        self.peers: Set[str] = set()  # Names of connected peers
        self.seen_messages: Set[str] = set()  # Prevent re-broadcasting

        # Stats
        self.blocks_received = 0
        self.txs_received = 0
        self.forks_resolved = 0
        self.messages_sent = 0
        self.messages_received = 0

    def connect_peer(self, peer_name: str):
        """Connect to another node."""
        if peer_name != self.name:
            self.peers.add(peer_name)
            logger.debug("%s connected to %s", self.name, peer_name)

    def disconnect_peer(self, peer_name: str):
        """Disconnect from a peer."""
        self.peers.discard(peer_name)

    def broadcast(self, msg_type: str, payload: dict):
        """
        Broadcast a message to all connected peers.

        This is the "gossip protocol" — each node tells its neighbors,
        who tell their neighbors, and so on. Within a few hops,
        every node in the network receives the message.
        """
        msg = Message(msg_type, payload, self.name)
        self.seen_messages.add(msg.msg_id)
        self.messages_sent += 1

        for peer_name in self.peers:
            self.network.deliver(msg, peer_name)

    def receive(self, msg: Message):
        """
        Receive and process a message from a peer.

        Message types:
          - new_block: A peer found/received a new block
          - new_tx: A peer broadcast a new transaction
          - request_chain: A peer wants our blockchain
          - chain_response: Response to our chain request
        """
        # Don't process messages we've already seen (prevent loops)
        if msg.msg_id in self.seen_messages:
            return
        self.seen_messages.add(msg.msg_id)
        self.messages_received += 1

        if msg.msg_type == "new_block":
            self._handle_new_block(msg.payload, msg.sender)
        elif msg.msg_type == "new_tx":
            self._handle_new_tx(msg.payload)
        elif msg.msg_type == "request_chain":
            self._handle_chain_request(msg.sender)
        elif msg.msg_type == "chain_response":
            self._handle_chain_response(msg.payload)

        # Re-broadcast to other peers (gossip)
        for peer_name in self.peers:
            if peer_name != msg.sender:
                self.network.deliver(msg, peer_name)

    def _handle_new_block(self, block_data: dict, sender: str):
        """
        Handle a new block received from a peer.

        Steps:
          1. Deserialize the block
          2. Validate proof of work
          3. Check if it extends our chain
          4. If yes → append it
          5. If it's from a longer chain → sync with that peer
        """
        self.blocks_received += 1

        block = Block.from_dict(block_data)

        # Does it extend our chain?
        if block.previous_hash == self.blockchain.last_block.hash:
            if block.is_valid_proof() and block.index == self.blockchain.height:
                self.blockchain.chain.append(block)
                logger.info(
                    "%s accepted block #%d from %s",
                    self.name, block.index, sender,
                )
                return

        # If the block suggests a longer chain exists, request the full chain
        if block.index > self.blockchain.height:
            logger.info(
                "%s: peer %s has longer chain (%d vs %d), requesting sync",
                self.name, sender, block.index, self.blockchain.height,
            )
            self.broadcast("request_chain", {"requester": self.name})

    def _handle_new_tx(self, tx_data: dict):
        """Handle a new transaction from a peer."""
        self.txs_received += 1
        tx = Transaction.from_dict(tx_data)
        self.blockchain.add_transaction(tx)

    def _handle_chain_request(self, requester: str):
        """A peer wants our blockchain. Send it."""
        chain_data = {
            "chain": [b.to_dict() for b in self.blockchain.chain],
            "height": self.blockchain.height,
        }
        msg = Message("chain_response", chain_data, self.name)
        self.network.deliver(msg, requester)

    def _handle_chain_response(self, payload: dict):
        """
        Received a peer's blockchain. Resolve any fork.

        The LONGEST VALID CHAIN wins.
        This is the core of Nakamoto consensus:
          - More blocks = more work done = more secure
          - An attacker would need >50% hashpower to outpace the network
        """
        received_chain = [Block.from_dict(b) for b in payload["chain"]]

        # Is the received chain longer?
        if len(received_chain) <= len(self.blockchain.chain):
            return

        # Validate the entire received chain
        for i in range(1, len(received_chain)):
            current = received_chain[i]
            previous = received_chain[i - 1]

            if current.previous_hash != previous.hash:
                logger.warning("%s: received invalid chain (broken link at %d)", self.name, i)
                return
            if not current.hash.startswith("0" * current.difficulty):
                logger.warning("%s: received invalid chain (bad PoW at %d)", self.name, i)
                return

        # Valid and longer → adopt it
        self.blockchain.chain = received_chain
        self.forks_resolved += 1
        logger.info(
            "%s adopted longer chain (height: %d → %d)",
            self.name, len(self.blockchain.chain), len(received_chain),
        )

    def mine_block(self) -> Block:
        """Mine a block and broadcast it to the network."""
        block = self.blockchain.mine_block(self.wallet.address)

        # Broadcast to all peers
        self.broadcast("new_block", block.to_dict())

        return block

    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "address": self.wallet.address[:20] + "...",
            "chain_height": self.blockchain.height,
            "peers": len(self.peers),
            "balance": self.blockchain.get_balance(self.wallet.address),
            "blocks_received": self.blocks_received,
            "txs_received": self.txs_received,
            "forks_resolved": self.forks_resolved,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "chain_valid": self.blockchain.validate_chain(),
        }


class Network:
    """
    Simulated P2P network.

    In reality, nodes connect over TCP/IP using protocols like:
      - Bitcoin's P2P protocol (port 8333)
      - Ethereum's devp2p/libp2p
      - Custom protocols (Solana's Turbine)

    This simulation uses direct function calls instead of network I/O.
    """

    def __init__(self):
        self.nodes: Dict[str, Node] = {}

    def add_node(self, name: str) -> Node:
        """Add a node to the network."""
        node = Node(name, self)
        self.nodes[name] = node

        # Connect to all existing nodes (full mesh for simplicity)
        for existing_name, existing_node in self.nodes.items():
            if existing_name != name:
                node.connect_peer(existing_name)
                existing_node.connect_peer(name)

        logger.info("Node '%s' joined network (peers: %d)", name, len(node.peers))
        return node

    def remove_node(self, name: str):
        """Remove a node from the network."""
        if name not in self.nodes:
            return

        # Disconnect from all peers
        for peer_name in list(self.nodes[name].peers):
            if peer_name in self.nodes:
                self.nodes[peer_name].disconnect_peer(name)

        del self.nodes[name]
        logger.info("Node '%s' left network", name)

    def deliver(self, msg: Message, recipient: str):
        """Deliver a message to a specific node."""
        if recipient in self.nodes:
            self.nodes[recipient].receive(msg)

    def get_stats(self) -> dict:
        return {
            "total_nodes": len(self.nodes),
            "nodes": [n.get_stats() for n in self.nodes.values()],
        }

    def print_network(self):
        print(f"\n{'═' * 60}")
        print(f"P2P NETWORK — {len(self.nodes)} nodes")
        print(f"{'═' * 60}")

        for node in self.nodes.values():
            stats = node.get_stats()
            print(f"\n  {stats['name']}")
            print(f"  ├─ Chain height: {stats['chain_height']}")
            print(f"  ├─ Balance: {stats['balance']:.2f}")
            print(f"  ├─ Peers: {stats['peers']}")
            print(f"  ├─ Messages: sent={stats['messages_sent']} recv={stats['messages_received']}")
            print(f"  └─ Chain valid: {stats['chain_valid']}")


# ──────────────────────────────────────────────
# DEMO: Simulate a blockchain network
# ──────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("=" * 60)
    print("P2P NETWORK & CHAIN SYNCHRONIZATION DEMO")
    print("=" * 60)

    # Create a network with 3 nodes
    network = Network()
    node_a = network.add_node("Node-A")
    node_b = network.add_node("Node-B")
    node_c = network.add_node("Node-C")

    print(f"\nNodes created: {list(network.nodes.keys())}")

    # Node A mines some blocks
    print("\n--- Node A mines 3 blocks ---")
    for i in range(3):
        block = node_a.mine_block()
        print(f"  Block #{block.index} mined by Node-A")

    # Check: all nodes should have synced
    print("\n--- Chain heights after Node A mining ---")
    for name, node in network.nodes.items():
        print(f"  {name}: height={node.blockchain.height}, valid={node.blockchain.validate_chain()}")

    # Node B mines a block
    print("\n--- Node B mines 1 block ---")
    block = node_b.mine_block()
    print(f"  Block #{block.index} mined by Node-B")

    # Final state
    network.print_network()

    # Verify all chains are valid
    print("\n--- Validation ---")
    all_valid = all(n.blockchain.validate_chain() for n in network.nodes.values())
    print(f"All chains valid: {all_valid}")
