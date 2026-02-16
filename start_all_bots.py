#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║              RIMURU CRYPTO EMPIRE — MASTER BOT LAUNCHER             ║
║                     ALL BOTS RUNNING 24/7                           ║
║                                                                      ║
║  200+ Bot Configurations Across 5 Tiers:                            ║
║                                                                      ║
║  TIER 1: Core Infrastructure    (14 Docker services)                ║
║  TIER 2: Trading Team           (13 Docker microservices)           ║
║  TIER 3: Trade God Army         (5 Docker trader bots)              ║
║  TIER 4: Blockchain Empire      (mining + tracking + vault)         ║
║  TIER 5: Standalone Bots        (auto-trader + pool server)         ║
║                                                                      ║
║  Total: 35 services / 145 classes / 200+ active configurations     ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time
import json
import signal
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

# ─── Configuration ────────────────────────────────────────────────────
EMPIRE_ROOT = Path(__file__).parent.resolve()
BLOCKCHAIN_ROOT = EMPIRE_ROOT / "crypto-pool-blockchain"
LOGS_DIR = EMPIRE_ROOT / "logs" / "empire"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ─── Color output ─────────────────────────────────────────────────────
class C:
    R = "\033[91m"    # Red
    G = "\033[92m"    # Green
    Y = "\033[93m"    # Yellow
    B = "\033[94m"    # Blue
    M = "\033[95m"    # Magenta
    CY = "\033[96m"   # Cyan
    W = "\033[97m"    # White
    DIM = "\033[2m"
    BOLD = "\033[1m"
    END = "\033[0m"

def ts():
    return datetime.now().strftime("%H:%M:%S")

def banner(text, color=C.CY):
    w = 66
    print(f"\n{color}{'═' * w}")
    print(f"  {text}")
    print(f"{'═' * w}{C.END}")

def status(icon, name, detail="", color=C.G):
    print(f"  {icon} {color}{name:<40}{C.END} {C.DIM}{detail}{C.END}")

def error(name, detail=""):
    print(f"  ✗ {C.R}{name:<40}{C.END} {C.DIM}{detail}{C.END}")


# ═══════════════════════════════════════════════════════════════════════
# BOT REGISTRY — Every single bot/service in the empire
# ═══════════════════════════════════════════════════════════════════════

BOT_REGISTRY = {
    # ─── TIER 1: Core Infrastructure (docker-compose.yml) ──────────
    "tier1_core": {
        "name": "Core Infrastructure",
        "compose_file": "docker-compose.yml",
        "services": [
            # Databases & Cache
            {"name": "PostgreSQL",          "container": "rimuru-postgres",          "port": 5432, "type": "database"},
            {"name": "Redis Cache",         "container": "rimuru-redis",             "port": 6379, "type": "cache"},
            # API & Frontend
            {"name": "API Gateway",         "container": "rimuru-api",               "port": 5000, "type": "api"},
            {"name": "Dashboard",           "container": "rimuru-dashboard",         "port": 3000, "type": "frontend"},
            # Price & Wallet
            {"name": "Price Service",       "container": "rimuru-price-service",     "port": 8100, "type": "service"},
            {"name": "Wallet Service",      "container": "rimuru-wallet-service",    "port": 8200, "type": "service"},
            # AI & ML
            {"name": "AI Service",          "container": "rimuru-ai-service",        "port": 8300, "type": "service"},
            {"name": "Ollama LLM",          "container": "rimuru-ollama",            "port": 11434, "type": "ai"},
            # Bots & Pipeline
            {"name": "Bot Service",         "container": "rimuru-bot-service",       "port": 8400, "type": "service"},
            {"name": "Pipeline Service",    "container": "rimuru-pipeline-service",  "port": None, "type": "worker"},
            # Scanners
            {"name": "Opportunity Scanner", "container": "rimuru-scanner",           "port": None, "type": "scanner"},
            {"name": "Analyzer Engine",     "container": "rimuru-analyzer",          "port": None, "type": "scanner"},
            {"name": "Project Integrator",  "container": "rimuru-integrator",        "port": None, "type": "scanner"},
            {"name": "Asset Scanner",       "container": "rimuru-asset-scanner",     "port": None, "type": "scanner"},
        ],
    },

    # ─── TIER 2: Trading Microservices (docker-compose.team.yml) ───
    "tier2_team": {
        "name": "Trading Microservices",
        "compose_file": "docker-compose.team.yml",
        "services": [
            # Data Layer
            {"name": "Data Ingest (Kraken)", "container": "rimuru-data-ingest",       "port": 18000, "type": "data"},
            {"name": "Indicator Engine",     "container": "rimuru-indicators",        "port": 18001, "type": "data"},
            # 6 Strategy Bots
            {"name": "Strategy: MA Cross",   "container": "rimuru-strategy-ma",       "port": 8010, "type": "strategy"},
            {"name": "Strategy: RSI",        "container": "rimuru-strategy-rsi",      "port": 8011, "type": "strategy"},
            {"name": "Strategy: Bollinger",  "container": "rimuru-strategy-bollinger","port": 8012, "type": "strategy"},
            {"name": "Strategy: Momentum",   "container": "rimuru-strategy-momentum", "port": 8013, "type": "strategy"},
            {"name": "Strategy: Volume",     "container": "rimuru-strategy-volume",   "port": 8014, "type": "strategy"},
            {"name": "Strategy: LSTM/ML",    "container": "rimuru-strategy-lstm",     "port": 8015, "type": "strategy"},
            # Execution & Orchestration
            {"name": "Order Executor",       "container": "rimuru-executor",          "port": 8020, "type": "executor"},
            {"name": "Orchestrator (Brain)", "container": "rimuru-orchestrator",      "port": 8030, "type": "orchestrator"},
            {"name": "Backtester",           "container": "rimuru-backtester",        "port": 8040, "type": "backtester"},
            # Monitoring
            {"name": "Prometheus",           "container": "rimuru-prometheus",        "port": 9090, "type": "monitoring"},
            {"name": "Grafana",              "container": "rimuru-grafana",           "port": 3000, "type": "monitoring"},
        ],
    },

    # ─── TIER 3: Trade God Army (docker-compose.traders.yml) ───────
    "tier3_army": {
        "name": "Trade God Army",
        "compose_file": "docker-compose.traders.yml",
        "services": [
            {"name": "ALPHA — Full Trade God",    "container": "rimuru-alpha", "port": None, "type": "trader",
             "strategies": ["momentum","mean_rev","trend","fibonacci","golden_cross","stochastic","trade_god"],
             "pairs": ["SOL/USD","PEPE/USD","DOGE/USD","BTC/USD","ETH/USD"]},
            {"name": "BETA — Momentum Hunter",    "container": "rimuru-beta",  "port": None, "type": "trader",
             "strategies": ["momentum","trend"],
             "pairs": ["SOL/USD","PEPE/USD","DOGE/USD","BTC/USD","ETH/USD"]},
            {"name": "GAMMA — Reversal Expert",   "container": "rimuru-gamma", "port": None, "type": "trader",
             "strategies": ["mean_rev","stochastic"],
             "pairs": ["SOL/USD","PEPE/USD","DOGE/USD","BTC/USD","ETH/USD"]},
            {"name": "DELTA — Pattern Master",    "container": "rimuru-delta", "port": None, "type": "trader",
             "strategies": ["fibonacci","golden_cross"],
             "pairs": ["SOL/USD","PEPE/USD","DOGE/USD","BTC/USD","ETH/USD"]},
            {"name": "OMEGA — Aggressive God",    "container": "rimuru-omega", "port": None, "type": "trader",
             "strategies": ["momentum","mean_rev","trend","fibonacci","golden_cross","stochastic","trade_god"],
             "pairs": ["SOL/USD","PEPE/USD","DOGE/USD","BTC/USD","ETH/USD"]},
        ],
    },

    # ─── TIER 4: Blockchain Empire (Python processes) ──────────────
    "tier4_blockchain": {
        "name": "Blockchain Empire",
        "standalone": True,
        "services": [
            {"name": "Empire Runner (mine+track+vault)", "cmd": [sys.executable, "run_empire.py", "--continuous"],
             "cwd": str(BLOCKCHAIN_ROOT), "type": "blockchain"},
        ],
    },

    # ─── TIER 5: Standalone Bots (Python processes) ────────────────
    "tier5_standalone": {
        "name": "Standalone Bots",
        "standalone": True,
        "services": [
            {"name": "Rimuru Auto Trader (Trade God v2)", "cmd": [sys.executable, "rimuru_auto_trader.py", "--live"],
             "cwd": str(EMPIRE_ROOT), "type": "trader"},
            {"name": "Mining Pool Server",               "cmd": [sys.executable, "-m", "uvicorn", "pool_server:app", "--host", "0.0.0.0", "--port", "8050"],
             "cwd": str(BLOCKCHAIN_ROOT / "mining_pool"), "type": "miner"},
            {"name": "Pool Miner Worker",                "cmd": [sys.executable, "miner.py"],
             "cwd": str(BLOCKCHAIN_ROOT / "mining_pool"), "type": "miner"},
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════════
# BOT CONFIGURATION MATRIX — All 200+ active combinations
# ═══════════════════════════════════════════════════════════════════════

def count_bot_configurations():
    """Count every active bot configuration across the empire."""
    counts = {
        "docker_services": 0,
        "strategy_instances": 0,
        "trader_pair_combos": 0,
        "standalone_processes": 0,
        "bot_templates": 0,
        "pipeline_scanners": 0,
        "blockchain_agents": 0,
    }

    # Docker services (Tier 1 + 2 + 3)
    for tier_key in ["tier1_core", "tier2_team", "tier3_army"]:
        counts["docker_services"] += len(BOT_REGISTRY[tier_key]["services"])

    # Strategy × pair combinations (Trade God Army)
    for svc in BOT_REGISTRY["tier3_army"]["services"]:
        combos = len(svc.get("strategies", [])) * len(svc.get("pairs", []))
        counts["trader_pair_combos"] += combos

    # 6 microservice strategies × 5 pairs each
    counts["strategy_instances"] += 6 * 5  # MA, RSI, Bollinger, Momentum, Volume, LSTM × 5 pairs

    # Bot service templates (6 templates × 3 sub-strategies each)
    counts["bot_templates"] += 6 * 3  # spot_trader, farmer, collector, sniper, dca, arbitrage

    # Pipeline scanners (6 scanner types)
    counts["pipeline_scanners"] += 6  # Crypto, GiftCard, Loyalty, GoldAsset, APIKey, StoreCredit

    # Blockchain agents
    counts["blockchain_agents"] += 10  # AutoMiner, WhaleWatcher, AirdropHunter, FaucetCollector, etc.

    # Standalone processes
    counts["standalone_processes"] += len(BOT_REGISTRY["tier4_blockchain"]["services"])
    counts["standalone_processes"] += len(BOT_REGISTRY["tier5_standalone"]["services"])

    total = sum(counts.values())
    return counts, total


# ═══════════════════════════════════════════════════════════════════════
# LAUNCH ENGINE
# ═══════════════════════════════════════════════════════════════════════

class EmpireLauncher:
    """Master launcher for the entire Rimuru Empire."""

    def __init__(self):
        self.processes = []  # Standalone Python processes
        self.running = True
        self.start_time = datetime.now(timezone.utc)
        self.results = {"started": [], "failed": [], "skipped": []}
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        banner("SHUTTING DOWN EMPIRE", C.Y)
        self.running = False
        for proc_info in self.processes:
            try:
                proc_info["process"].terminate()
                status("⏹", f"Stopped {proc_info['name']}", color=C.Y)
            except Exception:
                pass
        print(f"\n{C.Y}  Stopping Docker services...{C.END}")
        for tier_key, tier in BOT_REGISTRY.items():
            if "compose_file" in tier:
                subprocess.run(
                    ["docker", "compose", "-f", tier["compose_file"], "stop"],
                    cwd=str(EMPIRE_ROOT), capture_output=True
                )
        print(f"\n{C.G}  Empire shutdown complete.{C.END}\n")
        sys.exit(0)

    def _run_compose(self, compose_file, tier_name):
        """Start all services in a docker-compose file."""
        banner(f"TIER: {tier_name}", C.B)
        print(f"  {C.DIM}compose: {compose_file}{C.END}\n")

        cmd = ["docker", "compose", "-f", compose_file, "up", "-d", "--remove-orphans"]
        result = subprocess.run(
            cmd, cwd=str(EMPIRE_ROOT),
            capture_output=True, text=True, timeout=300
        )

        if result.returncode != 0:
            error(f"docker compose -f {compose_file}", result.stderr[:200])
            return False
        return True

    def _check_container(self, container_name):
        """Check if a specific container is running."""
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True, text=True
        )
        return result.returncode == 0 and "running" in result.stdout.strip()

    def _start_standalone(self, svc):
        """Start a standalone Python process."""
        name = svc["name"]
        cmd = svc["cmd"]
        cwd = svc.get("cwd", str(EMPIRE_ROOT))
        log_file = LOGS_DIR / f"{name.lower().replace(' ', '_').replace('(', '').replace(')', '')}.log"

        try:
            log_fh = open(log_file, "a")
            proc = subprocess.Popen(
                cmd, cwd=cwd,
                stdout=log_fh, stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            self.processes.append({"name": name, "process": proc, "log": str(log_file)})
            status("🚀", name, f"PID {proc.pid} | log: {log_file.name}", C.G)
            self.results["started"].append(name)
            return True
        except Exception as e:
            error(name, str(e))
            self.results["failed"].append(name)
            return False

    def launch_tier_docker(self, tier_key):
        """Launch a Docker compose tier."""
        tier = BOT_REGISTRY[tier_key]
        compose_file = tier["compose_file"]
        tier_name = tier["name"]

        success = self._run_compose(compose_file, tier_name)
        time.sleep(3)  # Let containers initialize

        for svc in tier["services"]:
            container = svc["container"]
            if self._check_container(container):
                port_info = f":{svc['port']}" if svc.get("port") else ""
                status("✓", svc["name"], f"{container}{port_info}", C.G)
                self.results["started"].append(svc["name"])
            else:
                error(svc["name"], f"{container} not running")
                self.results["failed"].append(svc["name"])

    def launch_tier_standalone(self, tier_key):
        """Launch standalone Python bots."""
        tier = BOT_REGISTRY[tier_key]
        banner(f"TIER: {tier['name']}", C.M)
        print()

        for svc in tier["services"]:
            self._start_standalone(svc)
            time.sleep(1)

    def launch_all(self):
        """Launch the entire empire."""
        counts, total = count_bot_configurations()

        # ── Grand Banner ──
        print(f"\n{C.BOLD}{C.CY}")
        print("  ╔══════════════════════════════════════════════════════════════╗")
        print("  ║          RIMURU CRYPTO EMPIRE — FULL DEPLOYMENT             ║")
        print("  ║                   ALL BOTS GO LIVE 24/7                     ║")
        print("  ╚══════════════════════════════════════════════════════════════╝")
        print(f"{C.END}")

        print(f"  {C.W}Bot Configuration Matrix:{C.END}")
        print(f"    Docker Services:          {C.G}{counts['docker_services']:>4}{C.END}")
        print(f"    Strategy Microservices:    {C.G}{counts['strategy_instances']:>4}{C.END}  (6 strategies × 5 pairs)")
        print(f"    Trade God Army Combos:     {C.G}{counts['trader_pair_combos']:>4}{C.END}  (5 bots × strategies × pairs)")
        print(f"    Bot Service Templates:     {C.G}{counts['bot_templates']:>4}{C.END}  (6 templates × 3 variants)")
        print(f"    Pipeline Scanners:         {C.G}{counts['pipeline_scanners']:>4}{C.END}")
        print(f"    Blockchain Agents:         {C.G}{counts['blockchain_agents']:>4}{C.END}")
        print(f"    Standalone Processes:       {C.G}{counts['standalone_processes']:>4}{C.END}")
        print(f"    {'─' * 42}")
        print(f"    {C.BOLD}TOTAL CONFIGURATIONS:      {C.CY}{total:>4}{C.END}")
        print()

        # ── Tier 1: Core Infrastructure ──
        self.launch_tier_docker("tier1_core")

        # ── Tier 2: Trading Microservices ──
        self.launch_tier_docker("tier2_team")

        # ── Tier 3: Trade God Army ──
        self.launch_tier_docker("tier3_army")

        # ── Tier 4: Blockchain Empire ──
        self.launch_tier_standalone("tier4_blockchain")

        # ── Tier 5: Standalone Bots ──
        self.launch_tier_standalone("tier5_standalone")

        # ── Final Report ──
        self._print_report(counts, total)

        # ── Keep alive ──
        self._monitor_loop()

    def _print_report(self, counts, total):
        """Print the final deployment report."""
        started = len(self.results["started"])
        failed = len(self.results["failed"])

        banner("EMPIRE DEPLOYMENT COMPLETE", C.G if failed == 0 else C.Y)

        print(f"\n  {C.BOLD}Services Started:  {C.G}{started}{C.END}")
        if failed > 0:
            print(f"  {C.BOLD}Services Failed:   {C.R}{failed}{C.END}")
            for f in self.results["failed"]:
                print(f"    {C.R}✗ {f}{C.END}")

        print(f"\n  {C.BOLD}Active Bot Configurations: {C.CY}{total}{C.END}")
        print()

        # ── Port Map ──
        print(f"  {C.BOLD}Port Map:{C.END}")
        ports = {}
        for tier in BOT_REGISTRY.values():
            for svc in tier["services"]:
                if svc.get("port"):
                    ports[svc["port"]] = svc["name"]
        for port in sorted(ports.keys()):
            print(f"    :{port:<6} → {ports[port]}")

        print(f"\n  {C.BOLD}Standalone Processes:{C.END}")
        for p in self.processes:
            alive = p["process"].poll() is None
            icon = "●" if alive else "✗"
            color = C.G if alive else C.R
            print(f"    {color}{icon}{C.END} {p['name']} (PID {p['process'].pid})")

        print(f"\n  {C.BOLD}Monitoring:{C.END}")
        print(f"    Grafana:    http://localhost:3000")
        print(f"    Prometheus: http://localhost:9090")
        print(f"    Dashboard:  http://localhost:5000")
        print(f"    Logs:       {LOGS_DIR}")
        print()

        # Save deployment manifest
        manifest = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services_started": started,
            "services_failed": failed,
            "total_configurations": total,
            "breakdown": counts,
            "started": self.results["started"],
            "failed": self.results["failed"],
            "standalone_pids": {p["name"]: p["process"].pid for p in self.processes},
        }
        manifest_path = LOGS_DIR / "deployment_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        print(f"  {C.DIM}Manifest saved: {manifest_path}{C.END}")

    def _monitor_loop(self):
        """Keep running and monitor all processes."""
        banner("EMPIRE RUNNING 24/7 — Press Ctrl+C to stop", C.G)
        print(f"  {C.DIM}Monitoring all services...{C.END}\n")

        check_interval = 60  # seconds
        while self.running:
            try:
                time.sleep(check_interval)
                # Check standalone processes
                for p in self.processes:
                    if p["process"].poll() is not None:
                        print(f"  {C.Y}⚠ {p['name']} exited (code {p['process'].returncode}) — restarting...{C.END}")
                        # Auto-restart
                        svc = None
                        for tier in BOT_REGISTRY.values():
                            for s in tier["services"]:
                                if s.get("name") == p["name"]:
                                    svc = s
                                    break
                        if svc and "cmd" in svc:
                            self._start_standalone(svc)
                            self.processes.remove(p)
            except KeyboardInterrupt:
                self._shutdown(None, None)


# ═══════════════════════════════════════════════════════════════════════
# STATUS CHECK — Quick health check without launching
# ═══════════════════════════════════════════════════════════════════════

def check_status():
    """Check status of all services without launching."""
    banner("RIMURU EMPIRE — STATUS CHECK", C.CY)
    counts, total = count_bot_configurations()

    running = 0
    stopped = 0

    for tier_key, tier in BOT_REGISTRY.items():
        print(f"\n  {C.BOLD}{tier['name']}:{C.END}")
        for svc in tier["services"]:
            if svc.get("container"):
                result = subprocess.run(
                    ["docker", "inspect", "--format", "{{.State.Status}}", svc["container"]],
                    capture_output=True, text=True
                )
                is_running = result.returncode == 0 and "running" in result.stdout.strip()
                if is_running:
                    status("●", svc["name"], svc["container"], C.G)
                    running += 1
                else:
                    status("○", svc["name"], svc["container"], C.R)
                    stopped += 1
            elif svc.get("cmd"):
                status("?", svc["name"], "(standalone — check PIDs)", C.Y)

    print(f"\n  {C.BOLD}Running: {C.G}{running}{C.END}  |  {C.BOLD}Stopped: {C.R}{stopped}{C.END}  |  {C.BOLD}Total Configs: {C.CY}{total}{C.END}\n")


# ═══════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rimuru Empire — Master Bot Launcher")
    parser.add_argument("--status", action="store_true", help="Check status of all services")
    parser.add_argument("--no-standalone", action="store_true", help="Skip standalone Python bots")
    parser.add_argument("--tier", type=int, choices=[1,2,3,4,5], help="Launch only a specific tier")
    args = parser.parse_args()

    if args.status:
        check_status()
        sys.exit(0)

    launcher = EmpireLauncher()

    if args.tier:
        tier_map = {1: "tier1_core", 2: "tier2_team", 3: "tier3_army", 4: "tier4_blockchain", 5: "tier5_standalone"}
        tier_key = tier_map[args.tier]
        tier = BOT_REGISTRY[tier_key]
        if tier.get("standalone"):
            launcher.launch_tier_standalone(tier_key)
        else:
            launcher.launch_tier_docker(tier_key)
        launcher._monitor_loop()
    else:
        launcher.launch_all()
