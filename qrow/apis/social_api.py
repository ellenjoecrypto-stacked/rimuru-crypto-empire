"""Social media API wrapper — Twitter/X, Reddit, Telegram signals."""

from core.config import SAFE_MODE


class SocialAPI:
    """Collects social sentiment signals from crypto communities."""

    def __init__(self, platform: str = "twitter"):
        self.platform = platform

    def get_trending_topics(self) -> list:
        if SAFE_MODE:
            return [
                {"topic": "#BTC", "mentions": 0, "source": "safe_mode"},
                {"topic": "#ETH", "mentions": 0, "source": "safe_mode"},
            ]
        # TODO: integrate real Twitter/Reddit API
        return []

    def get_sentiment(self, keyword: str) -> dict:
        if SAFE_MODE:
            return {
                "keyword": keyword,
                "sentiment": "neutral",
                "confidence": 0.0,
                "source": "safe_mode",
            }
        # TODO: NLP sentiment pipeline
        return {}

    def get_influencer_signals(self) -> list:
        if SAFE_MODE:
            return []
        # TODO: track KOL wallets + posts
        return []
