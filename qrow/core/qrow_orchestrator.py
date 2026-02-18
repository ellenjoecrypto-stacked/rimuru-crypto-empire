class Qrow:
    def __init__(self, sandbox, watchtower):
        self.sandbox = sandbox
        self.watchtower = watchtower

    def run_bot(self, bot, name):
        self.sandbox.create_sandbox(name)
        event = bot.run()
        analysis = self.watchtower.log_event(event)

        if analysis["action"] == "freeze_sandbox":
            self.sandbox.freeze(name)
