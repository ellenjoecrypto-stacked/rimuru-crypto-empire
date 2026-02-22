import logging

logger = logging.getLogger(__name__)


class Watchtower:
    def __init__(self, rimuru):
        self.rimuru = rimuru

    def log_event(self, event):
        analysis = self.rimuru.analyze_event(event)
        logger.info("[WATCHTOWER] %s", analysis)
        return analysis
