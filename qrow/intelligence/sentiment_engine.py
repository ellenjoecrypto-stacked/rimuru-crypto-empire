"""Sentiment Engine — aggregates and scores market sentiment."""


class SentimentEngine:
    """Produces a unified sentiment score from multiple data sources."""

    WEIGHTS = {
        "social": 0.3,
        "news": 0.25,
        "onchain": 0.25,
        "price_action": 0.2,
    }

    def __init__(self):
        self.signals = []

    def add_signal(self, source: str, score: float):
        """score in [-1.0, 1.0] range. source must be a valid category."""
        self.signals.append({"source": source, "score": score})

    def compute_sentiment(self) -> dict:
        if not self.signals:
            return {"sentiment": 0.0, "label": "neutral", "confidence": 0.0}

        weighted_sum = 0.0
        weight_total = 0.0
        for sig in self.signals:
            w = self.WEIGHTS.get(sig["source"], 0.1)
            weighted_sum += sig["score"] * w
            weight_total += w

        sentiment = weighted_sum / weight_total if weight_total else 0.0
        label = "bullish" if sentiment > 0.2 else "bearish" if sentiment < -0.2 else "neutral"
        return {
            "sentiment": round(sentiment, 4),
            "label": label,
            "confidence": round(min(len(self.signals) / 10, 1.0), 2),
        }

    def reset(self):
        self.signals = []
