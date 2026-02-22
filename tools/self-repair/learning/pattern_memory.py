"""
Rimuru Repair — Pattern Memory
================================
Tracks recurring issue patterns and identifies hot files.
"""

from collections import defaultdict
from datetime import UTC, datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PatternMemory:
    """
    Tracks issue patterns across scans to identify hot files and recurring problems.

    Maintains in-memory frequency maps that are persisted via the knowledge base.
    """

    def __init__(self) -> None:
        # file_path -> {issue_type -> count}
        self._file_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # issue_type -> total count
        self._type_counts: dict[str, int] = defaultdict(int)
        # file_path -> last seen timestamp (ISO)
        self._last_seen: dict[str, str] = {}

    def record_issues(self, issues: list) -> None:
        """
        Record a batch of issues from a scan run.

        Args:
            issues: List of Issue dataclass instances with .file and .issue_type attributes.
        """
        for issue in issues:
            self._file_counts[issue.file][issue.issue_type] += 1
            self._type_counts[issue.issue_type] += 1
            self._last_seen[issue.file] = datetime.now(UTC).isoformat()

    def get_hot_files(self, top_n: int = 10) -> list[tuple[str, int]]:
        """
        Return the top N files with the most issues, sorted descending.

        Args:
            top_n: Number of top files to return.

        Returns:
            List of (file_path, total_issue_count) tuples.
        """
        totals = {f: sum(counts.values()) for f, counts in self._file_counts.items()}
        return sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]

    def get_issue_frequency(self, issue_type: str) -> int:
        """
        Return how many times a given issue type has been seen.

        Args:
            issue_type: The issue type identifier.

        Returns:
            Total count of that issue type across all files.
        """
        return self._type_counts.get(issue_type, 0)

    def get_file_issue_count(self, file_path: str) -> int:
        """
        Return the total number of issues seen for a specific file.

        Args:
            file_path: Path string of the file.

        Returns:
            Total issue count for that file.
        """
        return sum(self._file_counts.get(file_path, {}).values())

    def prioritized_files(self, all_files: list[Path]) -> list[Path]:
        """
        Sort a list of file paths so hot files come first.

        Args:
            all_files: List of Path objects to sort.

        Returns:
            Sorted list with highest-issue files first.
        """
        return sorted(
            all_files,
            key=lambda p: self.get_file_issue_count(str(p)),
            reverse=True,
        )

    def to_dict(self) -> dict:
        """Serialize state to a plain dict for JSON persistence."""
        return {
            "file_counts": {k: dict(v) for k, v in self._file_counts.items()},
            "type_counts": dict(self._type_counts),
            "last_seen": self._last_seen,
        }

    def from_dict(self, data: dict) -> None:
        """
        Restore state from a serialized dict.

        Args:
            data: Previously serialized state from to_dict().
        """
        for file_path, counts in data.get("file_counts", {}).items():
            self._file_counts[file_path] = defaultdict(int, counts)
        self._type_counts = defaultdict(int, data.get("type_counts", {}))
        self._last_seen = data.get("last_seen", {})
