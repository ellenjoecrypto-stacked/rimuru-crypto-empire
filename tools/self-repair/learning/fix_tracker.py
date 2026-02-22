"""
Rimuru Repair — Fix Tracker
=============================
Tracks which fixes were applied and whether they stuck or were reverted.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FixRecord:
    """Record of a single fix application."""

    file: str
    line: int
    issue_type: str
    before: str
    after: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    verified: bool = False
    reverted: bool = False


class FixTracker:
    """
    Tracks fix applications and verifies whether fixes persist across scans.

    Calculates per-issue-type fix success rates. If a fix type is reverted
    too frequently, it is flagged for manual review instead of auto-applying.
    """

    def __init__(self, revert_threshold: float = 0.3, min_applications: int = 3) -> None:
        """
        Initialize the FixTracker.

        Args:
            revert_threshold: Fraction of reverts above which auto-fix is paused.
            min_applications: Minimum number of applications before revert rate
                              is considered reliable.
        """
        self._records: list[FixRecord] = []
        self.revert_threshold = revert_threshold
        self.min_applications = min_applications

    def record_fix(
        self,
        file: str,
        line: int,
        issue_type: str,
        before: str,
        after: str,
    ) -> None:
        """
        Record a fix that was applied.

        Args:
            file: File path where the fix was applied.
            line: Line number of the fix.
            issue_type: Type identifier of the issue that was fixed.
            before: Original code snippet.
            after: Fixed code snippet.
        """
        self._records.append(
            FixRecord(file=file, line=line, issue_type=issue_type, before=before, after=after)
        )

    def verify_fix(self, file: str, line: int, issue_type: str, current_content: str) -> bool:
        """
        Check if a previously applied fix is still in place.

        Marks the matching record as verified (or reverted) based on whether
        the current file content contains the fix.

        Args:
            file: File path to check.
            line: Line number of the original fix.
            issue_type: Issue type of the original fix.
            current_content: Current file content.

        Returns:
            True if the fix is still in place, False if it was reverted.
        """
        for record in reversed(self._records):
            if (
                record.file == file
                and record.line == line
                and record.issue_type == issue_type
                and not record.verified
                and not record.reverted
            ):
                still_applied = record.after.strip() in current_content
                record.verified = still_applied
                record.reverted = not still_applied
                return still_applied
        return True  # Unknown — assume OK

    def get_success_rate(self, issue_type: str) -> float | None:
        """
        Return the fix success rate for a given issue type.

        Args:
            issue_type: Issue type to check.

        Returns:
            Float between 0.0 and 1.0, or None if not enough data.
        """
        relevant = [r for r in self._records if r.issue_type == issue_type and
                    (r.verified or r.reverted)]
        if len(relevant) < self.min_applications:
            return None
        successes = sum(1 for r in relevant if r.verified)
        return successes / len(relevant)

    def should_auto_fix(self, issue_type: str) -> bool:
        """
        Decide whether auto-fixing should be applied for a given issue type.

        Args:
            issue_type: Issue type to evaluate.

        Returns:
            True if auto-fix should proceed, False if flagged for manual review.
        """
        rate = self.get_success_rate(issue_type)
        if rate is None:
            return True  # Not enough data — optimistically allow
        return rate >= (1.0 - self.revert_threshold)

    def get_stats(self) -> dict:
        """Return summary statistics for all tracked fixes."""
        total = len(self._records)
        verified = sum(1 for r in self._records if r.verified)
        reverted = sum(1 for r in self._records if r.reverted)
        return {
            "total_fixes": total,
            "verified": verified,
            "reverted": reverted,
            "success_rate": (verified / total) if total else 0.0,
            "flagged_types": [
                itype
                for itype in {r.issue_type for r in self._records}
                if not self.should_auto_fix(itype)
            ],
        }

    def to_dict(self) -> dict:
        """Serialize state to a plain dict for JSON persistence."""
        return {
            "records": [asdict(r) for r in self._records],
            "revert_threshold": self.revert_threshold,
            "min_applications": self.min_applications,
        }

    def from_dict(self, data: dict) -> None:
        """
        Restore state from a serialized dict.

        Args:
            data: Previously serialized state from to_dict().
        """
        self._records = [FixRecord(**r) for r in data.get("records", [])]
        self.revert_threshold = data.get("revert_threshold", self.revert_threshold)
        self.min_applications = data.get("min_applications", self.min_applications)
