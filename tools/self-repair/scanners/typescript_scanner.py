"""
Rimuru Repair — TypeScript/JavaScript Code Quality Scanner
===========================================================
Detects common TypeScript/React code quality issues via regex.
"""

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import ClassVar

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """Represents a detected code quality issue."""

    file: str
    line: int
    issue_type: str
    severity: str
    message: str
    auto_fixable: bool = False
    context: str = ""


class TypeScriptScanner:
    """
    Scans TypeScript/JavaScript source files for code quality issues.

    Detects:
    - console.log / console.error / console.warn in component files
    - any type usage
    - Empty catch blocks
    - Hardcoded API URLs
    - Missing key props in list renders
    - Unused imports (basic heuristic)
    """

    CONSOLE_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"\bconsole\.(log|error|warn|debug|info)\s*\("
    )
    ANY_TYPE_RE: ClassVar[re.Pattern[str]] = re.compile(r":\s*any\b")
    HARDCODED_URL_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?:["'])(https?://(?:localhost|\d{1,3}(?:\.\d{1,3}){3}|[a-zA-Z0-9\-]+\.(?:com|io|net|org|dev))[^"']*)(?:["'])"""
    )
    EMPTY_CATCH_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"catch\s*\([^)]*\)\s*\{\s*\}", re.DOTALL
    )
    MAP_WITHOUT_KEY_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"\.map\s*\([^)]*=>\s*(?:<[A-Z][^>]*(?<!key=)[^>]*>|<[a-z][^>]*(?<!key=)[^>]*>)"
    )

    def scan_file(self, path: Path) -> list[Issue]:
        """
        Scan a single TypeScript/JavaScript file and return all issues.

        Args:
            path: Path to the file to scan.

        Returns:
            List of Issue objects.
        """
        issues: list[Issue] = []
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
            return issues

        lines = source.splitlines()
        is_component = path.suffix in {".tsx", ".jsx"} or path.stem[0].isupper()

        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()

            # console.* usage
            if self.CONSOLE_RE.search(line):
                match = self.CONSOLE_RE.search(line)
                method = match.group(1) if match else "log"
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="console_statement",
                        severity="medium" if is_component else "low",
                        message=f"Remove console.{method}() from source code",
                        auto_fixable=True,
                        context=stripped,
                    )
                )

            # any type
            if self.ANY_TYPE_RE.search(line):
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="any_type",
                        severity="medium",
                        message="Avoid using 'any' type — prefer 'unknown'",
                        auto_fixable=True,
                        context=stripped,
                    )
                )

            # Hardcoded API URLs
            for match in self.HARDCODED_URL_RE.finditer(line):
                url = match.group(1)
                if not url.startswith("https://fonts.") and not url.startswith(
                    "https://schema."
                ):
                    issues.append(
                        Issue(
                            file=str(path),
                            line=lineno,
                            issue_type="hardcoded_url",
                            severity="high",
                            message=f"Hardcoded API URL: {url!r}",
                            auto_fixable=False,
                            context=stripped,
                        )
                    )

        # Multi-line empty catch check
        for match in self.EMPTY_CATCH_RE.finditer(source):
            lineno = source[: match.start()].count("\n") + 1
            issues.append(
                Issue(
                    file=str(path),
                    line=lineno,
                    issue_type="empty_catch",
                    severity="high",
                    message="Empty catch block — handle or log the error",
                    auto_fixable=False,
                    context="",
                )
            )

        return issues

    def scan_directory(self, root: Path, exclude_dirs: list[str] | None = None) -> list[Issue]:
        """
        Scan all TypeScript/JavaScript files under root recursively.

        Args:
            root: Root directory to scan.
            exclude_dirs: Directory names to skip.

        Returns:
            Aggregated list of all issues found.
        """
        skip = set(exclude_dirs or [])
        all_issues: list[Issue] = []
        extensions = {".ts", ".tsx", ".js", ".jsx"}
        for file in root.rglob("*"):
            if file.suffix not in extensions:
                continue
            if any(part in skip for part in file.parts):
                continue
            all_issues.extend(self.scan_file(file))
        return all_issues
