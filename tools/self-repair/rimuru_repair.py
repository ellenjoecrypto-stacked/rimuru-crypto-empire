"""
RIMURU CRYPTO EMPIRE — Rimuru Repair
======================================
Self-learning code repair engine.

Scan loop: scan → detect → fix → verify → learn → report

Usage:
    python tools/self-repair/rimuru_repair.py --scan --report
    python tools/self-repair/rimuru_repair.py --scan --fix
    python tools/self-repair/rimuru_repair.py --report
    python tools/self-repair/rimuru_repair.py --scan --path backend/
    python tools/self-repair/rimuru_repair.py --stats
"""

import argparse
from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
import pprint
import sys

# Ensure the tool directory is on sys.path for intra-package imports
# when run as a script (python tools/self-repair/rimuru_repair.py)
_TOOL_DIR = Path(__file__).resolve().parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))

from fixers.path_fixer import PathFixer  # noqa: E402
from fixers.python_fixer import PythonFixer  # noqa: E402
from fixers.typescript_fixer import TypeScriptFixer  # noqa: E402
from learning.fix_tracker import FixTracker  # noqa: E402
from learning.pattern_memory import PatternMemory  # noqa: E402
from reports.health_report import HealthReporter  # noqa: E402
from scanners.config_scanner import ConfigScanner  # noqa: E402
from scanners.python_scanner import PythonScanner  # noqa: E402
from scanners.typescript_scanner import TypeScriptScanner  # noqa: E402
import yaml  # noqa: E402  (after sys.path manipulation)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [RIMURU-REPAIR] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths (resolved relative to this file's location)
_KB_PATH = _TOOL_DIR / "learning" / "knowledge_base.json"
_CONFIG_PATH = _TOOL_DIR / "config.yaml"
_REPORTS_DIR = _TOOL_DIR / "reports"


def _load_config() -> dict:
    """Load tool configuration from config.yaml."""
    if _CONFIG_PATH.exists():
        with _CONFIG_PATH.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    return {}


def _load_kb() -> dict:
    """Load the persistent knowledge base from disk."""
    if _KB_PATH.exists():
        try:
            return json.loads(_KB_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Knowledge base corrupted — resetting.")
    return {
        "version": "1.0",
        "total_scans": 0,
        "total_issues_found": 0,
        "total_fixes_applied": 0,
        "fix_success_rate": 0.0,
        "issue_patterns": {},
        "hot_files": [],
        "lessons_learned": [],
        "last_scan": None,
        "last_score": None,
        "pattern_memory": {},
        "fix_tracker": {},
    }


def _save_kb(kb: dict) -> None:
    """Persist the knowledge base to disk."""
    _KB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _KB_PATH.write_text(json.dumps(kb, indent=2), encoding="utf-8")


class RimuruRepair:
    """
    Self-learning code repair engine modeled after RimuruAICore.

    Pipeline: scan → detect → fix → verify → learn → report

    Attributes:
        project_root: Root directory of the project to scan.
        config: Loaded configuration dict.
        kb: Persistent knowledge base dict.
        pattern_memory: PatternMemory instance for hot-file tracking.
        fix_tracker: FixTracker for fix success/revert tracking.
    """

    def __init__(self, project_root: Path | None = None) -> None:
        """
        Initialize the repair engine.

        Args:
            project_root: Override for the project root to scan.
                          Falls back to REPAIR_PROJECT_ROOT env var,
                          then config.yaml, then the repository root.
        """
        self.config = _load_config()
        self.kb = _load_kb()

        env_root = os.getenv("REPAIR_PROJECT_ROOT")
        if project_root:
            self.project_root = project_root.resolve()
        elif env_root:
            self.project_root = Path(env_root).resolve()
        else:
            cfg_root = self.config.get("project_root", ".")
            # Resolve relative to repo root (two levels up from tools/self-repair/)
            self.project_root = (_TOOL_DIR.parent.parent / cfg_root).resolve()

        # Sub-components
        self.pattern_memory = PatternMemory()
        if "pattern_memory" in self.kb:
            self.pattern_memory.from_dict(self.kb["pattern_memory"])

        self.fix_tracker = FixTracker(
            revert_threshold=self.config.get("revert_threshold", 0.3),
            min_applications=self.config.get("min_applications_for_revert_check", 3),
        )
        if "fix_tracker" in self.kb:
            self.fix_tracker.from_dict(self.kb["fix_tracker"])

        self.reporter = HealthReporter(output_dir=_REPORTS_DIR)

        # Scanners
        self._python_scanner = PythonScanner()
        self._ts_scanner = TypeScriptScanner()
        self._cfg_scanner = ConfigScanner()

        # Fixers
        self._python_fixer = PythonFixer()
        self._ts_fixer = TypeScriptFixer()
        self._path_fixer = PathFixer()

        # Results of last scan
        self._last_issues: list = []
        self._last_fix_counts: dict[str, int] = {}

        logger.info("🔧 Rimuru Repair initialized. Project root: %s", self.project_root)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan_project(self, path: Path | None = None) -> list:
        """
        Run a full scan of a project directory.

        Args:
            path: Directory to scan. Defaults to self.project_root.

        Returns:
            List of Issue objects found across all scanners.
        """
        root = (path or self.project_root).resolve()
        exclude = self.config.get("exclude_dirs", [])
        logger.info("🔍 Scanning %s ...", root)

        py_issues = self._python_scanner.scan_directory(root, exclude_dirs=exclude)
        ts_issues = self._ts_scanner.scan_directory(root, exclude_dirs=exclude)
        cfg_issues = self._cfg_scanner.scan_directory(root, exclude_dirs=exclude)

        all_issues = py_issues + ts_issues + cfg_issues
        self._last_issues = all_issues
        self.pattern_memory.record_issues(all_issues)

        logger.info(
            "Scan complete: %d Python, %d TS/JS, %d config issues",
            len(py_issues),
            len(ts_issues),
            len(cfg_issues),
        )
        return all_issues

    def auto_fix(self, issues: list | None = None) -> dict[str, int]:
        """
        Apply known auto-fixes to the detected issues.

        Only applies fixes for issue types that the FixTracker has not
        flagged as frequently reverted.

        Args:
            issues: List of Issue objects to fix. Defaults to last scan results.

        Returns:
            Aggregated fix counts by fix type.
        """
        issues = issues if issues is not None else self._last_issues
        if not issues:
            logger.info("No issues to fix.")
            return {}

        # Collect unique files by type
        py_files: set[Path] = set()
        ts_files: set[Path] = set()

        for issue in issues:
            if not issue.auto_fixable:
                continue
            if not self.fix_tracker.should_auto_fix(issue.issue_type):
                logger.debug("Skipping auto-fix for %s (flagged as frequently reverted)", issue.issue_type)
                continue
            file_path = Path(issue.file)
            if file_path.suffix == ".py":
                py_files.add(file_path)
            elif file_path.suffix in {".ts", ".tsx", ".js", ".jsx"}:
                ts_files.add(file_path)

        totals: dict[str, int] = {}

        for fp in py_files:
            counts = self._python_fixer.fix_file(fp)
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v
            # Also run path fixer on Python files
            path_counts = self._path_fixer.fix_file(fp)
            replaced = path_counts.get("paths_replaced", 0)
            if isinstance(replaced, int) and replaced > 0:
                totals["paths_replaced"] = totals.get("paths_replaced", 0) + replaced

        for fp in ts_files:
            counts = self._ts_fixer.fix_file(fp)
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v

        self._last_fix_counts = totals
        total_fixes = sum(totals.values())
        logger.info("✅ Applied %d fix(es): %s", total_fixes, totals)
        return totals

    def learn_from_result(
        self,
        issue: object,
        fix_applied: bool,
        fix_stuck: bool,
    ) -> None:
        """
        Update the learning state based on whether a fix was applied and stuck.

        Args:
            issue: The Issue object that was processed.
            fix_applied: Whether a fix was applied for this issue.
            fix_stuck: Whether the fix was still in place on next verification.
        """
        if fix_applied:
            file_path = Path(issue.file)  # type: ignore[attr-defined]
            try:
                content = file_path.read_text(encoding="utf-8")
            except OSError:
                content = ""
            self.fix_tracker.verify_fix(
                file=str(file_path),
                line=issue.line,  # type: ignore[attr-defined]
                issue_type=issue.issue_type,  # type: ignore[attr-defined]
                current_content=content,
            )
        if not fix_stuck:
            self.kb["lessons_learned"].append(
                {
                    "issue_type": issue.issue_type,  # type: ignore[attr-defined]
                    "file": issue.file,  # type: ignore[attr-defined]
                    "timestamp": datetime.now(UTC).isoformat(),
                    "lesson": "Fix was reverted — flagged for manual review",
                }
            )

    def get_health_score(self) -> int:
        """
        Calculate and return an overall health score (0-100).

        The score is derived from the number of issues found weighted
        by severity and the configured score weights per category.

        Returns:
            Integer health score from 0 to 100.
        """
        if not self._last_issues:
            return 100

        severity_weights = self.config.get(
            "severity_weights",
            {"critical": 5, "high": 3, "medium": 1, "low": 0},
        )
        total_deduction = sum(
            severity_weights.get(issue.severity, 1) for issue in self._last_issues
        )
        return max(0, 100 - total_deduction)

    def get_report(self) -> str:
        """
        Generate and return the full health report string.

        Returns:
            Formatted health report text.
        """
        score = self.get_health_score()
        previous_score = self.kb.get("last_score")
        project_name = self.project_root.name

        # Build per-category compliance stats
        category_map = {
            "logging": {"print_statement", "os_system"},
            "error_handling": {"bare_except", "generic_except"},
            "hardcoded_paths": {"hardcoded_path", "hardcoded_url"},
            "type_safety": {"any_type", "missing_type_hints"},
            "security": {"hardcoded_secret", "debug_code"},
            "dead_code": {"todo_comment", "star_import", "mutable_default"},
        }
        category_scores: dict[str, tuple[float, int]] = {}
        issue_type_counts: dict[str, int] = {}
        for issue in self._last_issues:
            issue_type_counts[issue.issue_type] = issue_type_counts.get(issue.issue_type, 0) + 1

        for cat, types in category_map.items():
            count = sum(issue_type_counts.get(t, 0) for t in types)
            # Simple compliance: 100% minus 5% per issue, floored at 0
            pct = max(0.0, 100.0 - count * 5)
            category_scores[cat] = (pct, count)

        hot_files = self.pattern_memory.get_hot_files(top_n=5)
        total_fixes = sum(self._last_fix_counts.values())

        return self.reporter.generate(
            project_name=project_name,
            score=score,
            category_scores=category_scores,
            hot_files=hot_files,
            previous_score=previous_score,
            total_issues=len(self._last_issues),
            total_fixes=total_fixes,
        )

    def run(
        self,
        scan: bool = True,
        fix: bool = False,
        report: bool = True,
        path: Path | None = None,
    ) -> str:
        """
        Execute the full pipeline: scan → fix → report → learn.

        Args:
            scan: Whether to run the scanner.
            fix: Whether to apply auto-fixes.
            report: Whether to generate and save the health report.
            path: Optional override for the directory to scan.

        Returns:
            Health report string (or empty string if report=False).
        """
        if scan:
            self.scan_project(path)

        if fix:
            self.auto_fix()

        report_text = ""
        if report:
            report_text = self.get_report()
            self.reporter.save(report_text)
            print(report_text)

        # Persist learning state
        self._persist()
        return report_text

    def get_stats(self) -> dict:
        """
        Return overall statistics from the knowledge base.

        Returns:
            Dictionary with scan and fix statistics.
        """
        return {
            "total_scans": self.kb.get("total_scans", 0),
            "total_issues_found": self.kb.get("total_issues_found", 0),
            "total_fixes_applied": self.kb.get("total_fixes_applied", 0),
            "fix_success_rate": self.kb.get("fix_success_rate", 0.0),
            "last_scan": self.kb.get("last_scan"),
            "last_score": self.kb.get("last_score"),
            "hot_files": self.kb.get("hot_files", []),
            "fix_tracker": self.fix_tracker.get_stats(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Update and save the knowledge base after a pipeline run."""
        total_fixes = sum(self._last_fix_counts.values())
        prev_fixes = self.kb.get("total_fixes_applied", 0)
        prev_issues = self.kb.get("total_issues_found", 0)
        prev_scans = self.kb.get("total_scans", 0)

        tracker_stats = self.fix_tracker.get_stats()

        self.kb.update(
            {
                "total_scans": prev_scans + 1,
                "total_issues_found": prev_issues + len(self._last_issues),
                "total_fixes_applied": prev_fixes + total_fixes,
                "fix_success_rate": tracker_stats.get("success_rate", 0.0),
                "hot_files": [f for f, _ in self.pattern_memory.get_hot_files(10)],
                "last_scan": datetime.now(UTC).isoformat(),
                "last_score": self.get_health_score(),
                "pattern_memory": self.pattern_memory.to_dict(),
                "fix_tracker": self.fix_tracker.to_dict(),
            }
        )
        _save_kb(self.kb)
        logger.info("📚 Knowledge base updated.")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Rimuru Repair — Self-learning code repair tool",
        prog="rimuru_repair",
    )
    parser.add_argument("--scan", action="store_true", help="Run a full project scan")
    parser.add_argument("--fix", action="store_true", help="Apply auto-fixes after scanning")
    parser.add_argument("--report", action="store_true", help="Generate health report")
    parser.add_argument("--stats", action="store_true", help="Show learning statistics")
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Scan a specific directory (default: project root from config)",
    )
    return parser.parse_args()


def main() -> None:
    """Main CLI entry point for Rimuru Repair."""
    args = _parse_args()
    repair = RimuruRepair()

    if args.stats:
        pprint.pprint(repair.get_stats())
        return

    if not args.scan and not args.report and not args.fix:
        args.scan = True
        args.report = True

    repair.run(
        scan=args.scan,
        fix=args.fix,
        report=args.report,
        path=args.path,
    )


if __name__ == "__main__":
    main()
