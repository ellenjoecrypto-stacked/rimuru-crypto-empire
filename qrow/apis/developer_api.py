"""Developer / on-chain developer activity API wrapper."""

from core.config import SAFE_MODE


class DeveloperAPI:
    """Tracks GitHub commits, smart-contract deployments, protocol updates."""

    def __init__(self):
        self.github_base = "https://api.github.com"

    def get_repo_activity(self, owner: str, repo: str) -> dict:
        if SAFE_MODE:
            return {
                "repo": f"{owner}/{repo}",
                "commits_30d": 0,
                "contributors": 0,
                "source": "safe_mode",
            }
        # TODO: real GitHub API call
        return {}

    def get_contract_deploys(self, chain: str = "ethereum") -> list:
        if SAFE_MODE:
            return []
        # TODO: scan for new verified contracts
        return []

    def get_protocol_updates(self) -> list:
        if SAFE_MODE:
            return []
        # TODO: aggregate governance proposals + protocol changelogs
        return []
