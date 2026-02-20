class Watchtower:
    def __init__(self, rimuru):
        self.rimuru = rimuru

    def log_event(self, event):
        analysis = self.rimuru.analyze_event(event)
        print("[WATCHTOWER]", analysis)
        return analysis
