class Rimuru:
    def __init__(self):
        self.persona = "Dark-ninja analytical overseer"

    def analyze_event(self, event):
        # event = {type, context, data}
        risk = self.score_risk(event)
        return {
            "event": event,
            "risk": risk,
            "interpretation": self.interpret(event),
            "action": self.recommend_action(risk)
        }

    def score_risk(self, event):
        if "network" in event["type"]:
            return 2
        if "sandbox_violation" in event["type"]:
            return 4
        return 0

    def interpret(self, event):
        return f"Rimuru interprets: {event['type']} detected."

    def recommend_action(self, risk):
        if risk == 4:
            return "freeze_sandbox"
        if risk == 2:
            return "flag"
        return "allow"
