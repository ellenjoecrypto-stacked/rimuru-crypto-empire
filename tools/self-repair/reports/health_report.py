"""
Rimuru Repair — Health Report Generator
=========================================
Generates a formatted health report card for the scanned project.
"""

from datetime import UTC, datetime
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Grade thresholds
_GRADE_THRESHOLDS = [
    (97, "A+"),
    (93, "A"),
    (90, "A-"),
    (87, "B+"),
    (83, "B"),
    (80, "B-"),
    (77, "C+"),
    (73, "C"),
    (70, "C-"),
    (67, "D+"),
    (60, "D"),
    (0, "F"),
]


def _grade(score: int) -> str:
    """Convert a numeric score to a letter grade."""
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


_COMPLIANCE_GOOD = 90.0
_COMPLIANCE_OK = 70.0
_HOT_FILE_THRESHOLD = 10


def _compliance_icon(pct: float) -> str:
    """Return an emoji icon for a compliance percentage."""
    if pct >= _COMPLIANCE_GOOD:
        return "✅"
    if pct >= _COMPLIANCE_OK:
        return "⚠️"
    return "❌"


class HealthReporter:
    """
    Generates a human-readable health report card from scan results.

    The report includes:
    - Overall health score and grade
    - Per-category compliance percentages
    - Top issue files (hot files)
    - Trend compared to previous scan
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """
        Initialize the HealthReporter.

        Args:
            output_dir: Directory to write report files. Defaults to
                        tools/self-repair/reports/ relative to CWD.
        """
        self.output_dir = output_dir or (Path(__file__).parent)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        project_name: str,
        score: int,
        category_scores: dict[str, tuple[float, int]],
        hot_files: list[tuple[str, int]],
        previous_score: int | None = None,
        total_issues: int = 0,
        total_fixes: int = 0,
    ) -> str:
        """
        Build and return the formatted health report string.

        Args:
            project_name: Name of the scanned project.
            score: Overall health score (0-100).
            category_scores: Mapping of category name to (compliance_pct, issue_count).
            hot_files: List of (file_path, issue_count) sorted by issue count desc.
            previous_score: Score from the last scan run, or None if first run.
            total_issues: Total issues found in this scan.
            total_fixes: Total fixes applied in this scan.

        Returns:
            Formatted report string.
        """
        grade = _grade(score)
        now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        lines = [
            "═" * 55,
            "  RIMURU REPAIR — HEALTH REPORT",
            "═" * 55,
            f"  Project: {project_name}",
            f"  Score:   {score}/100",
            f"  Grade:   {grade}",
            f"  Scanned: {now}",
            f"  Issues:  {total_issues} found  |  {total_fixes} auto-fixed",
            "",
        ]

        # Category breakdown
        for category, (pct, count) in category_scores.items():
            icon = _compliance_icon(pct)
            label = category.replace("_", " ").title()
            lines.append(
                f"  {icon} {label:<22} {pct:>5.1f}% compliant  ({count} issues)"
            )

        # Trend
        if previous_score is not None:
            delta = score - previous_score
            if delta > 0:
                trend = f"↑ Improving (+{delta} from last scan)"
            elif delta < 0:
                trend = f"↓ Declining ({delta} from last scan)"
            else:
                trend = "→ No change from last scan"
            lines.append("")
            lines.append(f"  Trend: {trend}")

        # Top files
        if hot_files:
            lines.append("")
            lines.append("  Top Issue Files:")
            for i, (file_path, count) in enumerate(hot_files[:5], start=1):
                short = Path(file_path).name
                hot_tag = " 🔥" if i == 1 and count > _HOT_FILE_THRESHOLD else ""
                lines.append(f"  {i}. {short} — {count} issues{hot_tag}")

        lines.append("═" * 55)
        return "\n".join(lines)

    def save(self, report: str, filename: str = "health_report.txt") -> Path:
        """
        Save the report string to a file in the output directory.

        Args:
            report: Report text to save.
            filename: Output filename.

        Returns:
            Path to the saved file.
        """
        out_path = self.output_dir / filename
        out_path.write_text(report, encoding="utf-8")
        logger.info("Health report saved to %s", out_path)
        return out_path
