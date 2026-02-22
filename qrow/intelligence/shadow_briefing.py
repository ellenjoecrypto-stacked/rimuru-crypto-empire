"""Shadow Briefing — generates daily / on-demand intelligence reports."""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ShadowBriefing:
    """Compiles intelligence from all engines into a single briefing."""

    def __init__(self, narrative_engine=None, sentiment_engine=None, clustering=None):
        self.narrative_engine = narrative_engine
        self.sentiment_engine = sentiment_engine
        self.clustering = clustering

    def generate(self) -> dict:
        briefing = {
            "timestamp": datetime.utcnow().isoformat(),
            "codename": "SHADOW BRIEFING",
            "sections": {},
        }

        if self.narrative_engine:
            briefing["sections"]["narratives"] = self.narrative_engine.get_narrative_report()

        if self.sentiment_engine:
            briefing["sections"]["sentiment"] = self.sentiment_engine.compute_sentiment()

        if self.clustering:
            briefing["sections"]["clusters"] = self.clustering.get_all_clusters()

        briefing["sections"]["recommendations"] = self._build_recommendations(briefing)
        return briefing

    def _build_recommendations(self, briefing: dict) -> list:
        recs = []
        sentiment = briefing["sections"].get("sentiment", {})
        if sentiment.get("label") == "bullish":
            recs.append("Consider increasing exposure to top-narrative tokens.")
        elif sentiment.get("label") == "bearish":
            recs.append("Reduce risk. Move to stables or hedge positions.")
        else:
            recs.append("Market neutral — focus on airdrop farming and data collection.")
        return recs

    def print_briefing(self):
        briefing = self.generate()
        logger.info("=" * 60)
        logger.info("       SHADOW BRIEFING — RIMURU INTELLIGENCE")
        logger.info("=" * 60)
        logger.info(json.dumps(briefing, indent=2))
        logger.info("=" * 60)

