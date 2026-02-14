"""
Rimuru Crypto Empire — Shared Configuration
Loaded from environment variables for Docker/K8s deployment.
"""

import os
from pathlib import Path


class ServiceConfig:
    """Base config loaded from environment variables"""

    # === Service Discovery ===
    DATA_INGEST_URL = os.getenv("DATA_INGEST_URL", "http://data-ingest:8000")
    INDICATORS_URL = os.getenv("INDICATORS_URL", "http://indicators:8001")
    STRATEGY_MA_URL = os.getenv("STRATEGY_MA_URL", "http://strategy-ma:8010")
    STRATEGY_RSI_URL = os.getenv("STRATEGY_RSI_URL", "http://strategy-rsi:8011")
    STRATEGY_BOLLINGER_URL = os.getenv("STRATEGY_BOLLINGER_URL", "http://strategy-bollinger:8012")
    STRATEGY_MOMENTUM_URL = os.getenv("STRATEGY_MOMENTUM_URL", "http://strategy-momentum:8013")
    STRATEGY_VOLUME_URL = os.getenv("STRATEGY_VOLUME_URL", "http://strategy-volume:8014")
    STRATEGY_LSTM_URL = os.getenv("STRATEGY_LSTM_URL", "http://strategy-lstm:8015")
    EXECUTOR_URL = os.getenv("EXECUTOR_URL", "http://executor:8020")
    ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8030")
    BACKTESTER_URL = os.getenv("BACKTESTER_URL", "http://backtester:8040")

    # === Kraken API ===
    KRAKEN_API_KEY = os.getenv("KRAKEN_API_KEY", "")
    KRAKEN_API_SECRET = os.getenv("KRAKEN_API_SECRET", "")
    KRAKEN_KEYS_FILE = os.getenv("KRAKEN_KEYS_FILE", "_SENSITIVE/kraken_keys.txt")

    # === Risk Defaults ===
    PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() in ("true", "1", "yes")
    MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.80"))
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.10"))
    MAX_DRAWDOWN_PCT = float(os.getenv("MAX_DRAWDOWN_PCT", "0.15"))
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
    MIN_TRADE_USD = float(os.getenv("MIN_TRADE_USD", "0.50"))
    MAX_TRADE_USD = float(os.getenv("MAX_TRADE_USD", "50.00"))
    RISK_PCT_PER_TRADE = float(os.getenv("RISK_PCT_PER_TRADE", "0.02"))
    DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "5.00"))

    # === Tradeable Pairs ===
    TRADEABLE_PAIRS = {
        "SOL": "SOLUSD",
        "PEPE": "PEPEUSD",
        "DOGE": "XDGUSD",
        "BTC": "XXBTZUSD",
        "ETH": "XETHZUSD",
    }

    MIN_ORDER = {
        "SOLUSD": 0.05,
        "PEPEUSD": 100000,
        "XDGUSD": 50,
        "XXBTZUSD": 0.00005,
        "XETHZUSD": 0.004,
    }

    ASSET_MAP = {
        "SOL": "SOL", "PEPE": "PEPE", "DOGE": "XXDG",
        "BTC": "XXBT", "ETH": "XETH",
    }

    # === Timing ===
    SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "60"))
    HEARTBEAT_SEC = int(os.getenv("HEARTBEAT_SEC", "300"))

    # === CoinGecko ===
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

    @classmethod
    def load_kraken_keys(cls):
        """Load Kraken keys from file if env vars not set"""
        if cls.KRAKEN_API_KEY and cls.KRAKEN_API_SECRET:
            return cls.KRAKEN_API_KEY, cls.KRAKEN_API_SECRET

        keys_file = Path(cls.KRAKEN_KEYS_FILE)
        if keys_file.exists():
            lines = keys_file.read_text().strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip().upper()
                    v = v.strip()
                    if "KEY" in k and "SECRET" not in k:
                        cls.KRAKEN_API_KEY = v
                    elif "SECRET" in k:
                        cls.KRAKEN_API_SECRET = v
            # Fallback: raw lines
            if not cls.KRAKEN_API_KEY:
                data_lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
                if len(data_lines) >= 2:
                    cls.KRAKEN_API_KEY = data_lines[-2]
                    cls.KRAKEN_API_SECRET = data_lines[-1]

        return cls.KRAKEN_API_KEY, cls.KRAKEN_API_SECRET
