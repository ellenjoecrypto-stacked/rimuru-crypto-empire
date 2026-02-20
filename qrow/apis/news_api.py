"""News / RSS / announcement API wrapper."""

from core.config import SAFE_MODE


class NewsAPI:
    """Aggregates crypto news from multiple sources."""

    SOURCES = [
        "https://cointelegraph.com/rss",
        "https://decrypt.co/feed",
        "https://thedefiant.io/feed",
    ]

    def __init__(self):
        self.cache = []

    def get_latest_headlines(self, limit: int = 10) -> list:
        if SAFE_MODE:
            return [
                {"title": "Safe-mode placeholder headline", "source": "safe_mode"}
            ]
        # TODO: RSS parse + dedup
        return []

    def search_news(self, keyword: str) -> list:
        if SAFE_MODE:
            return []
        # TODO: keyword search across cached headlines
        return []

    def get_breaking_alerts(self) -> list:
        if SAFE_MODE:
            return []
        # TODO: real-time websocket / push alerts
        return []
