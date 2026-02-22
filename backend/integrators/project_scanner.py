"""
Project Data Integrator - Scans old projects for crypto configurations and data
Extracts wallets, API keys, strategies, and integrates with opportunity analyzer
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import re

logger = logging.getLogger(__name__)


@dataclass
class ProjectData:
    """Extracted data from an old project"""
    project_name: str
    project_path: str
    discovered_at: str
    crypto_assets: List[str]
    exchanges: List[str]
    api_keys_found: int
    wallet_addresses: List[str]
    trading_strategies: List[str]
    defi_protocols: List[str]
    networks_used: List[str]
    total_files_scanned: int
    findings: Dict[str, Any]


class ProjectScanner:
    """Scans projects for crypto-related data and configurations"""
    
    # File patterns to search
    SEARCH_PATTERNS = {
        'wallet_addresses': [
            r'0x[a-fA-F0-9]{40}',  # Ethereum addresses
            r'1[1-9A-HJ-NP-Z]{25,34}',  # Bitcoin addresses
            r'[13][a-km-zA-HJ-NP-Z1-9]{25,34}',  # Bitcoin legacy
        ],
        'api_keys': [
            r'[\'"]api[_-]?key[\'"]?\s*[:=]\s*[\'"]?[a-zA-Z0-9_-]{20,}[\'"]?',
            r'[\'"]secret[\'"]?\s*[:=]\s*[\'"]?[a-zA-Z0-9_-]{20,}[\'"]?',
            r'[\'"]token[\'"]?\s*[:=]\s*[\'"]?[a-zA-Z0-9_-]{20,}[\'"]?',
        ],
        'crypto_terms': [
            r'bitcoin|btc|ethereum|eth|solana|sol|cardano|ada',
            r'uniswap|aave|curve|compound|yearn|lido',
            r'private\s*key|seed\s*phrase|mnemonic',
        ]
    }
    
    # File types to analyze
    ANALYZABLE_EXTENSIONS = {
        '.py', '.js', '.ts', '.json', '.yaml', '.yml',
        '.env', '.txt', '.md', '.sh', '.sol'
    }
    
    # Directories to ignore
    IGNORE_DIRS = {
        'node_modules', '__pycache__', '.git', 'venv', 'env',
        '.vscode', '.idea', 'dist', 'build', '.next'
    }
    
    def __init__(self):
        self.projects: Dict[str, ProjectData] = {}
        self.total_wallets_found: List[str] = []
        self.total_apis_found: int = 0
    
    async def scan_project(self, project_path: str) -> Optional[ProjectData]:
        """Scan a project for crypto data"""
        
        project_name = os.path.basename(project_path)
        
        if not os.path.isdir(project_path):
            logger.error(f"Project path not found: {project_path}")
            return None
        
        logger.info(f"Scanning project: {project_name}")
        
        project_data = ProjectData(
            project_name=project_name,
            project_path=project_path,
            discovered_at=datetime.utcnow().isoformat() + "Z",
            crypto_assets=[],
            exchanges=[],
            api_keys_found=0,
            wallet_addresses=[],
            trading_strategies=[],
            defi_protocols=[],
            networks_used=[],
            total_files_scanned=0,
            findings={}
        )
        
        try:
            for root, dirs, files in os.walk(project_path):
                # Skip ignored directories
                dirs[:] = [d for d in dirs if d not in self.IGNORE_DIRS]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # Check file extension
                    if not any(file.endswith(ext) for ext in self.ANALYZABLE_EXTENSIONS):
                        continue
                    
                    project_data.total_files_scanned += 1
                    
                    try:
                        await self._analyze_file(file_path, project_data)
                    except Exception as e:
                        logger.debug(f"Error analyzing {file_path}: {e}")
            
            self.projects[project_name] = project_data
            self.total_wallets_found.extend(project_data.wallet_addresses)
            
            logger.info(f"Scan complete for {project_name}: "
                       f"{len(project_data.wallet_addresses)} wallets, "
                       f"{project_data.api_keys_found} API keys found")
            
            return project_data
            
        except Exception as e:
            logger.error(f"Error scanning project {project_name}: {e}")
            return None
    
    async def _analyze_file(self, file_path: str, project_data: ProjectData):
        """Analyze individual file for crypto data"""
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Check for crypto assets
            crypto_assets = self._extract_crypto_assets(content)
            project_data.crypto_assets.extend(crypto_assets)
            
            # Check for exchanges
            exchanges = self._extract_exchanges(content)
            if exchanges:
                project_data.exchanges.extend(exchanges)
                project_data.api_keys_found += len(re.findall(
                    r'[\'"]api[_-]?key', content, re.IGNORECASE
                ))
            
            # Check for wallet addresses
            wallets = self._extract_wallet_addresses(content)
            if wallets:
                project_data.wallet_addresses.extend(wallets)
            
            # Check for trading strategies
            strategies = self._extract_strategies(content)
            if strategies:
                project_data.trading_strategies.extend(strategies)
            
            # Check for DeFi protocols
            defi = self._extract_defi_protocols(content)
            if defi:
                project_data.defi_protocols.extend(defi)
            
            # Extract networks
            networks = self._extract_networks(content)
            if networks:
                project_data.networks_used.extend(networks)
            
            # Store file findings
            relative_path = os.path.relpath(file_path)
            if crypto_assets or wallets or exchanges:
                project_data.findings[relative_path] = {
                    'crypto_assets': crypto_assets,
                    'wallets': wallets,
                    'exchanges': exchanges,
                    'strategies': strategies,
                }
                
        except Exception as e:
            logger.debug(f"Error reading {file_path}: {e}")
    
    def _extract_crypto_assets(self, content: str) -> List[str]:
        """Extract cryptocurrency mentions"""
        assets = set()
        
        crypto_list = {
            'bitcoin': 'BTC', 'btc': 'BTC',
            'ethereum': 'ETH', 'eth': 'ETH',
            'solana': 'SOL', 'sol': 'SOL',
            'cardano': 'ADA', 'ada': 'ADA',
            'polkadot': 'DOT', 'dot': 'DOT',
            'ripple': 'XRP', 'xrp': 'XRP',
            'litecoin': 'LTC', 'ltc': 'LTC',
            'dogecoin': 'DOGE', 'doge': 'DOGE',
            'polygon': 'MATIC', 'matic': 'MATIC',
            'avalanche': 'AVAX', 'avax': 'AVAX',
            'chainlink': 'LINK', 'link': 'LINK',
            'uniswap': 'UNI', 'uni': 'UNI',
            'aave': 'AAVE',
            'curve': 'CRV', 'crv': 'CRV',
        }
        
        lower_content = content.lower()
        for crypto, symbol in crypto_list.items():
            if crypto in lower_content:
                assets.add(symbol)
        
        return list(assets)
    
    def _extract_exchanges(self, content: str) -> List[str]:
        """Extract exchange mentions"""
        exchanges = set()
        
        exchange_names = {
            'binance': 'Binance',
            'kraken': 'Kraken',
            'coinbase': 'Coinbase',
            'kucoin': 'KuCoin',
            'bybit': 'Bybit',
            'okx': 'OKX',
            'gateio': 'Gate.io',
            'huobi': 'Huobi',
            'ftx': 'FTX',
            'dydx': 'dYdX',
        }
        
        lower_content = content.lower()
        for exchange, name in exchange_names.items():
            if exchange in lower_content:
                exchanges.add(name)
        
        return list(exchanges)
    
    def _extract_wallet_addresses(self, content: str) -> List[str]:
        """Extract wallet addresses"""
        wallets = set()
        
        for pattern in self.SEARCH_PATTERNS['wallet_addresses']:
            matches = re.findall(pattern, content)
            wallets.update(matches)
        
        return list(wallets)
    
    def _extract_strategies(self, content: str) -> List[str]:
        """Extract trading strategy mentions"""
        strategies = set()
        
        strategy_patterns = {
            'moving.?average': 'Moving Average',
            'rsi': 'RSI',
            'macd': 'MACD',
            'bollinger': 'Bollinger Bands',
            'grid.?trading': 'Grid Trading',
            'dca': 'Dollar Cost Averaging',
            'arbitrage': 'Arbitrage',
            'trend.?following': 'Trend Following',
            'mean.?reversion': 'Mean Reversion',
        }
        
        lower_content = content.lower()
        for pattern, strategy in strategy_patterns.items():
            if re.search(pattern, lower_content):
                strategies.add(strategy)
        
        return list(strategies)
    
    def _extract_defi_protocols(self, content: str) -> List[str]:
        """Extract DeFi protocol mentions"""
        protocols = set()
        
        defi_list = {
            'uniswap': 'Uniswap',
            'aave': 'Aave',
            'curve': 'Curve',
            'compound': 'Compound',
            'lido': 'Lido',
            'yearn': 'Yearn',
            'dydx': 'dYdX',
            'synthetix': 'Synthetix',
            'makerdao': 'MakerDAO',
        }
        
        lower_content = content.lower()
        for protocol, name in defi_list.items():
            if protocol in lower_content:
                protocols.add(name)
        
        return list(protocols)
    
    def _extract_networks(self, content: str) -> List[str]:
        """Extract blockchain network mentions"""
        networks = set()
        
        network_list = {
            'ethereum': 'Ethereum',
            'polygon': 'Polygon',
            'arbitrum': 'Arbitrum',
            'optimism': 'Optimism',
            'solana': 'Solana',
            'near': 'NEAR',
            'avalanche': 'Avalanche',
            'fantom': 'Fantom',
            'bsc|binance.?chain': 'BSC',
            'xdc': 'XDC',
        }
        
        lower_content = content.lower()
        for network, name in network_list.items():
            if re.search(network, lower_content):
                networks.add(name)
        
        return list(networks)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all scanned projects"""
        
        total_wallets = len(set(self.total_wallets_found))
        total_crypto_assets = set()
        total_exchanges = set()
        all_strategies = set()
        all_defi = set()
        all_networks = set()
        
        for project in self.projects.values():
            total_crypto_assets.update(project.crypto_assets)
            total_exchanges.update(project.exchanges)
            all_strategies.update(project.trading_strategies)
            all_defi.update(project.defi_protocols)
            all_networks.update(project.networks_used)
        
        return {
            'timestamp': datetime.utcnow().isoformat() + "Z",
            'total_projects_scanned': len(self.projects),
            'total_wallets_found': total_wallets,
            'total_crypto_assets': list(total_crypto_assets),
            'total_exchanges': list(total_exchanges),
            'total_trading_strategies': list(all_strategies),
            'defi_protocols_used': list(all_defi),
            'networks_used': list(all_networks),
            'total_apis_found': self.total_apis_found,
            'projects': {
                name: {
                    'wallets': len(p.wallet_addresses),
                    'crypto_assets': p.crypto_assets,
                    'exchanges': p.exchanges,
                    'strategies': p.trading_strategies,
                    'api_keys_found': p.api_keys_found,
                    'files_scanned': p.total_files_scanned,
                }
                for name, p in self.projects.items()
            }
        }
    
    def export_findings(self, output_path: str):
        """Export all findings to JSON"""
        
        summary = self.get_summary()
        
        output = {
            'summary': summary,
            'projects': {
                name: asdict(project)
                for name, project in self.projects.items()
            },
            'all_wallets': list(set(self.total_wallets_found)),
        }
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        logger.info(f"Findings exported to {output_path}")


# CLI Usage
if __name__ == "__main__":
    import sys
    
    async def main():
        scanner = ProjectScanner()
        
        # Load project paths from environment (comma-separated) or use empty list
        scan_paths_env = os.getenv('RIMURU_SCAN_PATHS', '')
        project_paths = [p.strip() for p in scan_paths_env.split(',') if p.strip()]
        
        scanned = 0
        for project_path in project_paths:
            if os.path.exists(project_path):
                result = await scanner.scan_project(project_path)
                if result:
                    scanned += 1
        
        # Print summary
        summary = scanner.get_summary()
        print(f"\n=== PROJECT SCAN SUMMARY ({scanned} projects) ===")
        print(json.dumps(summary, indent=2))
        
        # Export findings
        output_dir = os.getenv('RIMURU_DATA_OUTPUT_DIR', 'data')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "project_findings.json")
        scanner.export_findings(output_path)
        print(f"\nExported to: {output_path}")
    
    asyncio.run(main())
