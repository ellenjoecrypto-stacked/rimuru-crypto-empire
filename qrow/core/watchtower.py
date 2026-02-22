"""Watchtower — monitors bot events and routes them through Rimuru Intelligence."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Watchtower:
    """Observes all bot activity and delegates analysis to Rimuru."""

    def __init__(self, rimuru: Any) -> None:
        """Initialise with a Rimuru intelligence instance.

        Args:
            rimuru: A :class:`~core.rimuru_intelligence.Rimuru` instance.
        """
        self.rimuru = rimuru

    def log_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Analyse an event and log the result.

        Args:
            event: Event dict with at least a ``type`` key.

        Returns:
            The analysis dict returned by Rimuru.
        """
        analysis = self.rimuru.analyze_event(event)
        logger.info("[WATCHTOWER] %s", analysis)
        return analysis

