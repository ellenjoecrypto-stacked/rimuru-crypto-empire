#!/usr/bin/env python3
"""
RIMURU CRYPTO EMPIRE - Wallet Balance Service
Standalone microservice for checking wallet balances across multiple chains.
Supports ETH, BTC, SOL, and ERC-20 tokens.
"""

import asyncio
import json
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

import aiohttp
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================
# Models
# ============================================

class WalletRequest(BaseModel):
    address: str
    chain: str = "eth"  # eth, btc, sol

class WalletBalance(BaseModel):
    address: str
    chain: str
    balance: float
    balance_usd: float
    token_symbol: str
    last_checked: str

class TokenBalance(BaseModel):
    contract_address: str
    symbol: str
    name: str
    balance: float
    decimals: int

class WalletPortfolio(BaseModel):
    address: str
    chain: str
    native_balance: WalletBalance
    tokens: List[TokenBalance]
    total_usd: float

# ============================================
# Multi-Chain Wallet Checker
# ============================================

class MultiChainWalletChecker:
    """Check wallet balances across ETH, BTC, SOL chains"""
    
    def __init__(self):
        self.etherscan_key = os.getenv("ETHERSCAN_API_KEY", "")
        self.db_path = os.getenv("WALLET_DB_PATH", "/data/wallets.db")
        self._init_db()
    
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                chain TEXT NOT NULL,
                balance REAL,
                balance_usd REAL,
                token_symbol TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, chain)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracked_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                chain TEXT NOT NULL,
                label TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(address, chain)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS token_balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                contract_address TEXT,
                symbol TEXT,
                name TEXT,
                balance REAL,
                decimals INTEGER,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    async def check_eth_balance(self, address: str) -> Dict:
        """Check ETH native balance via Etherscan"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.etherscan.io/api"
                params = {
                    "module": "account",
                    "action": "balance",
                    "address": address,
                    "tag": "latest"
                }
                if self.etherscan_key:
                    params["apikey"] = self.etherscan_key
                
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == "1":
                        wei = int(data["result"])
                        eth_balance = wei / 1e18
                        
                        # Get ETH price
                        eth_price = await self._get_eth_price()
                        usd_value = eth_balance * eth_price
                        
                        result = {
                            "address": address,
                            "chain": "eth",
                            "balance": eth_balance,
                            "balance_usd": usd_value,
                            "token_symbol": "ETH"
                        }
                        self._save_check(result)
                        return result
                    
                    return {"address": address, "chain": "eth", "balance": 0, "balance_usd": 0, "token_symbol": "ETH", "error": data.get("message")}
        except Exception as e:
            logger.error(f"ETH balance check failed for {address}: {e}")
            return {"address": address, "chain": "eth", "balance": 0, "balance_usd": 0, "token_symbol": "ETH", "error": str(e)}
    
    async def check_eth_tokens(self, address: str) -> List[Dict]:
        """Check ERC-20 token balances"""
        tokens = []
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.etherscan.io/api"
                params = {
                    "module": "account",
                    "action": "tokentx",
                    "address": address,
                    "sort": "desc",
                    "page": 1,
                    "offset": 100
                }
                if self.etherscan_key:
                    params["apikey"] = self.etherscan_key
                
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == "1":
                        seen = {}
                        for tx in data.get("result", []):
                            contract = tx.get("contractAddress", "")
                            if contract not in seen:
                                seen[contract] = {
                                    "contract_address": contract,
                                    "symbol": tx.get("tokenSymbol", "UNKNOWN"),
                                    "name": tx.get("tokenName", "Unknown"),
                                    "decimals": int(tx.get("tokenDecimal", 18))
                                }
                        
                        # Check balance for each unique token
                        for contract, info in seen.items():
                            balance = await self._check_token_balance(address, contract, info["decimals"])
                            info["balance"] = balance
                            tokens.append(info)
        
        except Exception as e:
            logger.error(f"Token check failed for {address}: {e}")
        
        return tokens
    
    async def _check_token_balance(self, address: str, contract: str, decimals: int) -> float:
        """Check specific ERC-20 token balance"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.etherscan.io/api"
                params = {
                    "module": "account",
                    "action": "tokenbalance",
                    "contractaddress": contract,
                    "address": address,
                    "tag": "latest"
                }
                if self.etherscan_key:
                    params["apikey"] = self.etherscan_key
                
                async with session.get(url, params=params) as resp:
                    data = await resp.json()
                    if data.get("status") == "1":
                        raw = int(data["result"])
                        return raw / (10 ** decimals)
        except Exception as e:
            logger.error(f"Token balance check failed: {e}")
        return 0.0
    
    async def check_btc_balance(self, address: str) -> Dict:
        """Check BTC balance via Blockchain.info"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://blockchain.info/q/addressbalance/{address}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        satoshis = int(await resp.text())
                        btc_balance = satoshis / 1e8
                        btc_price = await self._get_btc_price()
                        usd_value = btc_balance * btc_price
                        
                        result = {
                            "address": address,
                            "chain": "btc",
                            "balance": btc_balance,
                            "balance_usd": usd_value,
                            "token_symbol": "BTC"
                        }
                        self._save_check(result)
                        return result
                    
                    return {"address": address, "chain": "btc", "balance": 0, "balance_usd": 0, "token_symbol": "BTC", "error": f"HTTP {resp.status}"}
        except Exception as e:
            logger.error(f"BTC balance check failed for {address}: {e}")
            return {"address": address, "chain": "btc", "balance": 0, "balance_usd": 0, "token_symbol": "BTC", "error": str(e)}
    
    async def check_sol_balance(self, address: str) -> Dict:
        """Check SOL balance via public RPC"""
        try:
            async with aiohttp.ClientSession() as session:
                rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getBalance",
                    "params": [address]
                }
                async with session.post(rpc_url, json=payload) as resp:
                    data = await resp.json()
                    if "result" in data:
                        lamports = data["result"]["value"]
                        sol_balance = lamports / 1e9
                        sol_price = await self._get_sol_price()
                        usd_value = sol_balance * sol_price
                        
                        result = {
                            "address": address,
                            "chain": "sol",
                            "balance": sol_balance,
                            "balance_usd": usd_value,
                            "token_symbol": "SOL"
                        }
                        self._save_check(result)
                        return result
                    
                    return {"address": address, "chain": "sol", "balance": 0, "balance_usd": 0, "token_symbol": "SOL", "error": data.get("error", {}).get("message", "Unknown")}
        except Exception as e:
            logger.error(f"SOL balance check failed for {address}: {e}")
            return {"address": address, "chain": "sol", "balance": 0, "balance_usd": 0, "token_symbol": "SOL", "error": str(e)}
    
    async def check_wallet(self, address: str, chain: str = "eth") -> Dict:
        """Check wallet balance on any supported chain"""
        chain = chain.lower()
        if chain == "eth":
            return await self.check_eth_balance(address)
        elif chain == "btc":
            return await self.check_btc_balance(address)
        elif chain == "sol":
            return await self.check_sol_balance(address)
        else:
            return {"error": f"Unsupported chain: {chain}"}
    
    async def get_full_portfolio(self, address: str, chain: str = "eth") -> Dict:
        """Get full portfolio including tokens"""
        native = await self.check_wallet(address, chain)
        tokens = []
        total_usd = native.get("balance_usd", 0)
        
        if chain == "eth":
            tokens = await self.check_eth_tokens(address)
            # Token USD values would need price lookup
        
        return {
            "address": address,
            "chain": chain,
            "native_balance": native,
            "tokens": tokens,
            "total_usd": total_usd
        }
    
    async def batch_check(self, wallets: List[Dict]) -> List[Dict]:
        """Check multiple wallets in batch"""
        results = []
        for w in wallets:
            result = await self.check_wallet(w["address"], w.get("chain", "eth"))
            results.append(result)
            await asyncio.sleep(0.25)  # Rate limit
        return results
    
    def track_wallet(self, address: str, chain: str, label: str = ""):
        """Add wallet to tracked list"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT OR REPLACE INTO tracked_wallets (address, chain, label) VALUES (?, ?, ?)",
            (address, chain, label)
        )
        conn.commit()
        conn.close()
    
    def get_tracked_wallets(self) -> List[Dict]:
        """Get all tracked wallets"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT address, chain, label, added_at FROM tracked_wallets").fetchall()
        conn.close()
        return [{"address": r[0], "chain": r[1], "label": r[2], "added_at": r[3]} for r in rows]
    
    def get_check_history(self, address: str) -> List[Dict]:
        """Get check history for an address"""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT address, chain, balance, balance_usd, token_symbol, checked_at FROM wallet_checks WHERE address = ? ORDER BY checked_at DESC",
            (address,)
        ).fetchall()
        conn.close()
        return [{"address": r[0], "chain": r[1], "balance": r[2], "balance_usd": r[3], "symbol": r[4], "checked_at": r[5]} for r in rows]
    
    def _save_check(self, result: Dict):
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO wallet_checks (address, chain, balance, balance_usd, token_symbol) VALUES (?, ?, ?, ?, ?)",
                (result["address"], result["chain"], result.get("balance", 0), result.get("balance_usd", 0), result.get("token_symbol", ""))
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save check: {e}")
    
    async def _get_eth_price(self) -> float:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd") as resp:
                    data = await resp.json()
                    return data.get("ethereum", {}).get("usd", 0)
        except:
            return 0
    
    async def _get_btc_price(self) -> float:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd") as resp:
                    data = await resp.json()
                    return data.get("bitcoin", {}).get("usd", 0)
        except:
            return 0
    
    async def _get_sol_price(self) -> float:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd") as resp:
                    data = await resp.json()
                    return data.get("solana", {}).get("usd", 0)
        except:
            return 0


# ============================================
# FastAPI Wallet Service
# ============================================

app = FastAPI(
    title="Rimuru Wallet Service",
    description="Multi-chain wallet balance tracker - ETH, BTC, SOL + ERC-20 tokens",
    version="1.0.0"
)

checker = MultiChainWalletChecker()

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "wallet-service", "timestamp": datetime.now().isoformat()}

@app.get("/wallet/{chain}/{address}")
async def get_balance(chain: str, address: str):
    """Check wallet balance on specified chain"""
    result = await checker.check_wallet(address, chain)
    if "error" in result and not result.get("balance"):
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@app.get("/wallet/{address}/full")
async def get_full_portfolio(address: str, chain: str = "eth"):
    """Get full portfolio with token balances"""
    return await checker.get_full_portfolio(address, chain)

@app.post("/wallet/batch")
async def batch_check(wallets: List[WalletRequest]):
    """Check multiple wallets at once"""
    wallet_dicts = [{"address": w.address, "chain": w.chain} for w in wallets]
    return await checker.batch_check(wallet_dicts)

@app.post("/wallet/track")
async def track_wallet(address: str, chain: str = "eth", label: str = ""):
    """Add wallet to tracking list"""
    checker.track_wallet(address, chain, label)
    return {"status": "tracked", "address": address, "chain": chain}

@app.get("/wallet/tracked")
async def get_tracked():
    """Get all tracked wallets"""
    return checker.get_tracked_wallets()

@app.get("/wallet/history/{address}")
async def get_history(address: str):
    """Get check history for a wallet"""
    return checker.get_check_history(address)

@app.post("/wallet/tracked/refresh")
async def refresh_tracked():
    """Refresh balances for all tracked wallets"""
    tracked = checker.get_tracked_wallets()
    results = []
    for w in tracked:
        result = await checker.check_wallet(w["address"], w["chain"])
        result["label"] = w.get("label", "")
        results.append(result)
        await asyncio.sleep(0.3)
    return {"refreshed": len(results), "wallets": results}


if __name__ == "__main__":
    port = int(os.getenv("WALLET_SERVICE_PORT", "8200"))
    print(f"💰 Rimuru Wallet Service starting on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
