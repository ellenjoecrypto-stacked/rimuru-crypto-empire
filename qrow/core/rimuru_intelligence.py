"""Rimuru Intelligence — event analysis, risk scoring, and action recommendation."""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Risk score mapping for known event types
_RISK_SCORES: dict[str, int] = {
    "network": 2,
    "sandbox_violation": 4,
    "unauthorized_access": 5,
    "data_exfil": 5,
    "api_abuse": 3,
    "rate_limit": 1,
    "auth_failure": 3,
}

# Graduated action levels by risk score
_ACTION_LEVELS: list[tuple[int, str]] = [
    (5, "emergency_shutdown"),
    (4, "freeze_sandbox"),
    (3, "quarantine"),
    (2, "throttle"),
    (1, "flag"),
    (0, "allow"),
]


class Rimuru:
    """Dark-ninja analytical overseer for the Qrow ecosystem."""

    def __init__(self) -> None:
        self.persona: str = "Dark-ninja analytical overseer"
        self.event_history: list[dict[str, Any]] = []

    def analyze_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Analyze a single event and return risk assessment with recommended action.

        Args:
            event: A dict with at least a ``type`` key, plus optional ``context``
                   and ``data`` keys.

        Returns:
            Analysis dict containing the original event, risk score,
            interpretation, and recommended action.
        """
        risk = self.score_risk(event)
        analysis = {
            "event": event,
            "risk": risk,
            "interpretation": self.interpret(event),
            "action": self.recommend_action(risk),
            "analyzed_at": datetime.utcnow().isoformat(),
        }
        self.event_history.append(analysis)
        logger.debug("Analyzed event type=%s risk=%d action=%s", event.get("type"), risk, analysis["action"])
        return analysis

    def score_risk(self, event: dict[str, Any]) -> int:
        """Return a numeric risk score for the given event.

        Args:
            event: Event dict with a ``type`` key.

        Returns:
            Integer risk score (0 = benign, 5 = critical).
        """
        event_type: str = event.get("type", "")
        for key, score in _RISK_SCORES.items():
            if key in event_type:
                return score
        return 0

    def interpret(self, event: dict[str, Any]) -> str:
        """Provide contextual analysis for the given event.

        Args:
            event: Event dict with a ``type`` key.

        Returns:
            Human-readable interpretation string.
        """
        event_type: str = event.get("type", "unknown")
        context: Any = event.get("context", {})

        interpretations: dict[str, str] = {
            "network": (
                f"Rimuru detects outbound network activity. "
                f"Context: {context}. Possible C2 or data leak vector."
            ),
            "sandbox_violation": (
                f"Sandbox boundary breached — event type '{event_type}'. "
                f"Immediate containment required."
            ),
            "unauthorized_access": (
                f"Unauthorized access attempt recorded. "
                f"Context: {context}. Credentials or ACL may be compromised."
            ),
            "data_exfil": (
                f"Potential data exfiltration detected. "
                f"Context: {context}. Investigate outbound data volume."
            ),
            "api_abuse": (
                f"API abuse pattern detected for type '{event_type}'. "
                f"Context: {context}. Rate-limit or revoke credentials."
            ),
            "rate_limit": (
                f"Rate-limit threshold approached for '{event_type}'. "
                f"Context: {context}. Throttling recommended."
            ),
            "auth_failure": (
                f"Authentication failure recorded. "
                f"Context: {context}. Possible brute-force in progress."
            ),
        }

        for key, message in interpretations.items():
            if key in event_type:
                return message

        return f"Rimuru interprets: '{event_type}' event detected. Context: {context}."

    def recommend_action(self, risk: int) -> str:
        """Return a graduated action recommendation based on the risk score.

        Action levels (ascending severity):
        allow → flag → throttle → quarantine → freeze_sandbox → emergency_shutdown

        Args:
            risk: Numeric risk score from :meth:`score_risk`.

        Returns:
            Action string.
        """
        for threshold, action in _ACTION_LEVELS:
            if risk >= threshold:
                return action
        return "allow"

    def analyze_batch(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process multiple events and return a list of analysis results.

        Args:
            events: List of event dicts.

        Returns:
            List of analysis dicts, one per event.
        """
        results = [self.analyze_event(event) for event in events]
        logger.info("Batch analysis complete: %d events processed.", len(results))
        return results

