"""Blockchain API wrapper — Etherscan, Alchemy, Infura, etc."""

import requests
from core.config import SAFE_MODE


class BlockchainAPI:
    BASE_URLS = {
        "etherscan": "https://api.etherscan.io/api",
        "bscscan": "https://api.bscscan.com/api",
    }

    def __init__(self, api_key: str = "", chain: str = "etherscan"):
        self.api_key = api_key
        self.chain = chain
        self.base = self.BASE_URLS.get(chain, self.BASE_URLS["etherscan"])

    def get_balance(self, address: str) -> dict:
        if SAFE_MODE:
            return {"status": "safe_mode", "address": address, "balance": "N/A"}
        params = {
            "module": "account",
            "action": "balance",
            "address": address,
            "apikey": self.api_key,
        }
        resp = requests.get(self.base, params=params, timeout=10)
        return resp.json()

    def get_tx_list(self, address: str, start_block: int = 0) -> dict:
        if SAFE_MODE:
            return {"status": "safe_mode", "address": address, "txs": []}
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": start_block,
            "sort": "desc",
            "apikey": self.api_key,
        }
        resp = requests.get(self.base, params=params, timeout=10)
        return resp.json()

    def get_token_transfers(self, address: str) -> dict:
        if SAFE_MODE:
            return {"status": "safe_mode", "address": address, "transfers": []}
        params = {
            "module": "account",
            "action": "tokentx",
            "address": address,
            "sort": "desc",
            "apikey": self.api_key,
        }
        resp = requests.get(self.base, params=params, timeout=10)
        return resp.json()
