class SandboxManager:
    def __init__(self):
        self.active_sandboxes = {}

    def create_sandbox(self, bot_name):
        self.active_sandboxes[bot_name] = "running"
        return f"Sandbox created for {bot_name}"

    def freeze(self, bot_name):
        self.active_sandboxes[bot_name] = "frozen"
        return f"Sandbox frozen for {bot_name}"
