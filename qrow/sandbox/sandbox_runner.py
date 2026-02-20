"""Sandbox runner — executes bots in isolated environments."""

import subprocess
import sys
import os

from core.config import SANDBOX_PATH, SAFE_MODE


class SandboxRunner:
    """Runs bot code inside a restricted environment (Docker or Firejail)."""

    def __init__(self, method: str = "subprocess"):
        self.method = method  # "subprocess", "docker", "firejail"

    def run(self, bot_module: str) -> dict:
        if SAFE_MODE:
            print(f"[SANDBOX] Safe-mode: simulating run of {bot_module}")
            return {"status": "simulated", "bot": bot_module}

        if self.method == "subprocess":
            return self._run_subprocess(bot_module)
        elif self.method == "docker":
            return self._run_docker(bot_module)
        elif self.method == "firejail":
            return self._run_firejail(bot_module)
        return {"error": "unknown sandbox method"}

    def _run_subprocess(self, bot_module: str) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", bot_module],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )
        return {
            "status": "completed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    def _run_docker(self, bot_module: str) -> dict:
        result = subprocess.run(
            ["docker", "run", "--rm", "--network=none", "qrow-sandbox", "python", "-m", bot_module],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "status": "completed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }

    def _run_firejail(self, bot_module: str) -> dict:
        profile = os.path.join(SANDBOX_PATH, "firejail.profile")
        result = subprocess.run(
            ["firejail", f"--profile={profile}", sys.executable, "-m", bot_module],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "status": "completed",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }


if __name__ == "__main__":
    runner = SandboxRunner()
    print(runner.run("bots.onchain_bot"))
