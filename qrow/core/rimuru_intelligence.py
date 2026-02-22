from __future__ import annotations

from datetime import datetime
from typing import Any


class Rimuru:
    """Dark-ninja analytical overseer — scores, interprets, and responds to events."""

    def __init__(self) -> None:
        self.persona = "Dark-ninja analytical overseer"
        self._event_history: list[dict[str, Any]] = []

    def analyze_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """Analyse a single event and return a structured response."""
        risk = self.score_risk(event)
        result = {
            "event": event,
            "risk": risk,
            "interpretation": self.interpret(event),
            "action": self.recommend_action(risk),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._event_history.append(result)
        return result

    def score_risk(self, event: dict[str, Any]) -> int:
        """Return a numeric risk score (0–10) based on event type."""
        event_type: str = event.get("type", "")
        scores: dict[str, int] = {
            "network": 2,
            "sandbox_violation": 4,
            "unauthorized_access": 6,
            "data_exfil": 8,
            "api_abuse": 5,
            "rate_limit": 3,
            "auth_failure": 5,
        }
        for key, score in scores.items():
            if key in event_type:
                return score
        return 0

    def interpret(self, event: dict[str, Any]) -> str:
        """Provide contextual interpretation per event type."""
        event_type: str = event.get("type", "unknown")
        context_map: dict[str, str] = {
            "network": "Unusual network activity detected — possible external probe.",
            "sandbox_violation": "Sandbox boundary breached — containment required immediately.",
            "unauthorized_access": "Unauthorised access attempt logged — credentials may be compromised.",
            "data_exfil": "Data exfiltration pattern detected — sensitive data may be leaving the system.",
            "api_abuse": "API endpoint is being abused — rate/auth controls should activate.",
            "rate_limit": "Rate limit threshold exceeded — throttling initiated.",
            "auth_failure": "Authentication failure detected — possible brute-force activity.",
        }
        for key, interpretation in context_map.items():
            if key in event_type:
                return interpretation
        return f"Rimuru interprets: {event_type} detected."

    def recommend_action(self, risk: int) -> str:
        """Return a graduated action level based on risk score."""
        if risk >= 8:
            return "emergency_shutdown"
        if risk >= 6:
            return "quarantine"
        if risk >= 4:
            return "freeze_sandbox"
        if risk >= 3:
            return "throttle"
        if risk >= 2:
            return "flag"
        return "allow"

    def analyze_batch(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Analyse a list of events and return all results."""
        return [self.analyze_event(event) for event in events]

    def get_event_history(self) -> list[dict[str, Any]]:
        """Return the full event history recorded by this instance."""
        return list(self._event_history)
