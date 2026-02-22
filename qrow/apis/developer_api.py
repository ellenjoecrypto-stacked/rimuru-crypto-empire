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
        raise NotImplementedError("Real GitHub API call not yet implemented")

    def get_contract_deploys(self, chain: str = "ethereum") -> list:
        if SAFE_MODE:
            return []
        raise NotImplementedError("Contract deploy scan not yet implemented")

    def get_protocol_updates(self) -> list:
        if SAFE_MODE:
            return []
        raise NotImplementedError("Protocol update aggregation not yet implemented")
