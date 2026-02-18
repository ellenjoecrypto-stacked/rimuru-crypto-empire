class OnChainBot:
    """Monitors on-chain activity: mempool, whale movements, contract deploys."""

    def run(self):
        return {
            "type": "network_request",
            "context": "bot attempted to read mempool",
            "data": {}
        }
