"""Clustering — groups tokens/projects by behaviour patterns."""

from collections import defaultdict


class TokenCluster:
    """Simple clustering of tokens by narrative, sector, or on-chain behaviour."""

    def __init__(self):
        self.clusters = defaultdict(list)  # {cluster_name: [tokens]}

    def assign(self, token: str, cluster: str):
        if token not in self.clusters[cluster]:
            self.clusters[cluster].append(token)

    def get_cluster(self, cluster: str) -> list:
        return self.clusters.get(cluster, [])

    def get_all_clusters(self) -> dict:
        return dict(self.clusters)

    def find_token_clusters(self, token: str) -> list:
        return [c for c, tokens in self.clusters.items() if token in tokens]
