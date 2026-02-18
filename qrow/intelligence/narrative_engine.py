"""Narrative Engine — detects and scores emerging crypto narratives."""

from datetime import datetime


class NarrativeEngine:
    """Tracks narrative momentum across social, on-chain, and news signals."""

    def __init__(self):
        self.narratives = {}  # {name: {score, first_seen, signals}}

    def ingest_signal(self, narrative: str, source: str, weight: float = 1.0):
        if narrative not in self.narratives:
            self.narratives[narrative] = {
                "score": 0.0,
                "first_seen": datetime.utcnow().isoformat(),
                "signals": [],
            }
        entry = self.narratives[narrative]
        entry["score"] += weight
        entry["signals"].append({"source": source, "weight": weight, "ts": datetime.utcnow().isoformat()})

    def get_top_narratives(self, n: int = 5) -> list:
        ranked = sorted(self.narratives.items(), key=lambda x: x[1]["score"], reverse=True)
        return ranked[:n]

    def get_narrative_report(self) -> dict:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "active_count": len(self.narratives),
            "top_5": self.get_top_narratives(5),
        }
