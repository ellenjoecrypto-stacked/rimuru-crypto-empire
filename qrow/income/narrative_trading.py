"""Narrative Trading — trade tokens aligned with top narratives."""

from datetime import datetime


class NarrativeTrading:
    """Generates trade signals based on narrative momentum."""

    def __init__(self, narrative_engine=None, sentiment_engine=None):
        self.narrative_engine = narrative_engine
        self.sentiment_engine = sentiment_engine
        self.positions = []
        self.trade_log = []

    def generate_signals(self) -> list:
        """Produce buy/sell signals from narrative + sentiment data."""
        signals = []
        if not self.narrative_engine:
            return signals

        top = self.narrative_engine.get_top_narratives(3)
        sentiment = {}
        if self.sentiment_engine:
            sentiment = self.sentiment_engine.compute_sentiment()

        for name, data in top:
            signal = {
                "narrative": name,
                "score": data["score"],
                "sentiment": sentiment.get("label", "unknown"),
                "action": "buy" if data["score"] > 5 and sentiment.get("label") != "bearish" else "watch",
                "timestamp": datetime.utcnow().isoformat(),
            }
            signals.append(signal)

        return signals

    def execute_trade(self, signal: dict) -> dict:
        """Simulate or execute a trade based on signal."""
        # TODO: connect to exchange_api for real execution
        trade = {
            "signal": signal,
            "status": "simulated",
            "executed_at": datetime.utcnow().isoformat(),
        }
        self.trade_log.append(trade)
        return trade

    def get_pnl_report(self) -> dict:
        return {
            "total_trades": len(self.trade_log),
            "positions": self.positions,
            "log": self.trade_log[-10:],  # last 10
        }
