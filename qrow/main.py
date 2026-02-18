"""
Qrow + Rimuru + ACOP — Main Entry Point
========================================
Run this file to boot the full ecosystem:
  python main.py

All subsystems initialise in safe mode by default.
"""

from core.rimuru_intelligence import Rimuru
from core.watchtower import Watchtower
from core.sandbox_manager import SandboxManager
from core.qrow_orchestrator import Qrow

from bots.onchain_bot import OnChainBot
from bots.market_bot import MarketBot
from bots.airdrop_bot import AirdropBot
from bots.narrative_bot import NarrativeBot
from bots.data_miner_bot import DataMinerBot
from bots.automation_bot import AutomationBot

from intelligence.narrative_engine import NarrativeEngine
from intelligence.sentiment_engine import SentimentEngine
from intelligence.clustering import TokenCluster
from intelligence.shadow_briefing import ShadowBriefing

from income.airdrop_engine import AirdropEngine
from income.narrative_trading import NarrativeTrading
from income.data_products import DataProducts
from income.automation_services import AutomationServices


def main():
    print("= - main.py:34" * 60)
    print("QROW + RIMURU CRYPTO INTELLIGENCE ENGINE  BOOTING - main.py:35")
    print("= - main.py:36" * 60)

    # ── Core ────────────────────────────────────────────────
    rimuru = Rimuru()
    watchtower = Watchtower(rimuru)
    sandbox = SandboxManager()
    qrow = Qrow(sandbox, watchtower)

    # ── Intelligence ────────────────────────────────────────
    narrative_engine = NarrativeEngine()
    sentiment_engine = SentimentEngine()
    clustering = TokenCluster()
    briefing = ShadowBriefing(narrative_engine, sentiment_engine, clustering)

    # ── Income Engines ──────────────────────────────────────
    airdrop_engine = AirdropEngine()
    narrative_trading = NarrativeTrading(narrative_engine, sentiment_engine)
    data_products = DataProducts()
    automation = AutomationServices()

    # ── Register automation tasks ───────────────────────────
    automation.register_task("claim_rewards", interval_minutes=60, action="claim")
    automation.register_task("rebalance_portfolio", interval_minutes=360, action="rebalance")

    # ── Seed some test data ─────────────────────────────────
    narrative_engine.ingest_signal("AI Agents", source="twitter", weight=3.0)
    narrative_engine.ingest_signal("RWA Tokenization", source="news", weight=2.5)
    narrative_engine.ingest_signal("AI Agents", source="onchain", weight=2.0)
    narrative_engine.ingest_signal("Restaking", source="discord", weight=1.5)

    sentiment_engine.add_signal("social", 0.6)
    sentiment_engine.add_signal("news", 0.3)
    sentiment_engine.add_signal("onchain", 0.4)
    sentiment_engine.add_signal("price_action", 0.2)

    clustering.assign("TAO", "AI Agents")
    clustering.assign("RNDR", "AI Agents")
    clustering.assign("ONDO", "RWA Tokenization")
    clustering.assign("EIGEN", "Restaking")

    # ── Run all bots through Qrow orchestrator ──────────────
    bots = {
        "onchain_bot": OnChainBot(),
        "market_bot": MarketBot(),
        "airdrop_bot": AirdropBot(),
        "narrative_bot": NarrativeBot(),
        "data_miner_bot": DataMinerBot(),
        "automation_bot": AutomationBot(),
    }

    print("\n[QROW] Running all bots through sandboxed orchestrator...\n - main.py:86")
    for name, bot in bots.items():
        qrow.run_bot(bot, name)

    # ── Generate shadow briefing ────────────────────────────
    print()
    briefing.print_briefing()

    # ── Income engine reports ───────────────────────────────
    print("\n[AIRDROP ENGINE] - main.py:95", airdrop_engine.discover())
    print("[NARRATIVE TRADING] - main.py:96", narrative_trading.generate_signals())
    print("[AUTOMATION] - main.py:97", automation.run_due_tasks())

    print("\n - main.py:99" + "=" * 60)
    print("ALL SYSTEMS ONLINE  QROW + RIMURU OPERATIONAL - main.py:100")
    print("= - main.py:101" * 60)


if __name__ == "__main__":
    main()
