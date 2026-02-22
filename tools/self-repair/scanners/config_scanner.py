"""
Rimuru Repair — Config/Environment/Path Scanner
================================================
Detects hardcoded paths, secrets, and config issues across any file type.
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


class ConfigScanner:
    """
    Scans config, env, and general files for security/config issues.

    Detects:
    - Hardcoded paths in any file
    - Potential secrets/API keys in code (not env vars)
    - Missing .gitignore entries for sensitive files
    """

    HARDCODED_WIN_PATH_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?:["' ]|^)([A-Za-z]:[\\\/][^\s"'<>|]+)"""
    )
    HARDCODED_UNIX_PATH_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?:["' ]|^)(\/(?:home|root|Users)\/[^\s"'<>|]+)"""
    )
    # Matches patterns that look like API keys / secrets assigned to a variable
    SECRET_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?:api[_\-]?key|secret|token|password|passwd|auth[_\-]?token)\s*[=:]\s*["'][A-Za-z0-9+/=_\-]{16,}["']""",
        re.IGNORECASE,
    )
    ENV_VAR_REF_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"os\.getenv|os\.environ|process\.env"
    )

    # Extensions to scan for config issues
    SCAN_EXTENSIONS: ClassVar[set[str]] = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".sh",
        ".env",
    }

    def scan_file(self, path: Path) -> list[Issue]:
        """
        Scan a single file for config/secret issues.

        Args:
            path: Path to the file to scan.

        Returns:
            List of Issue objects.
        """
        issues: list[Issue] = []
        # Skip binary files and known-safe files
        if path.suffix not in self.SCAN_EXTENSIONS and path.suffix != "":
            return issues
        # Never flag .env.example files for secrets
        if path.name.endswith(".example"):
            return issues

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
            return issues

        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            # Skip comments
            if stripped.startswith(("#", "//")):
                # Still check for hardcoded paths in comments? No — too noisy.
                continue

            # Hardcoded Windows paths
            issues.extend(
                Issue(
                    file=str(path),
                    line=lineno,
                    issue_type="hardcoded_path",
                    severity="medium",
                    message=f"Hardcoded Windows path: {match.group(1)!r}",
                    auto_fixable=True,
                    context=stripped,
                )
                for match in self.HARDCODED_WIN_PATH_RE.finditer(line)
            )

            # Hardcoded Unix paths
            issues.extend(
                Issue(
                    file=str(path),
                    line=lineno,
                    issue_type="hardcoded_path",
                    severity="medium",
                    message=f"Hardcoded Unix path: {match.group(1)!r}",
                    auto_fixable=True,
                    context=stripped,
                )
                for match in self.HARDCODED_UNIX_PATH_RE.finditer(line)
            )

            # Potential hardcoded secrets
            if self.SECRET_RE.search(line) and not self.ENV_VAR_REF_RE.search(line):
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="hardcoded_secret",
                        severity="critical",
                        message="Potential hardcoded secret/API key detected",
                        auto_fixable=False,
                        context="[REDACTED]",
                    )
                )

        return issues

    def check_env_example(self, root: Path) -> list[Issue]:
        """
        Check that .env.example exists and .gitignore covers .env files.

        Args:
            root: Repository root path.

        Returns:
            List of Issue objects for missing files.
        """
        issues: list[Issue] = []
        env_example = root / ".env.example"
        if not env_example.exists():
            issues.append(
                Issue(
                    file=str(root / ".env.example"),
                    line=0,
                    issue_type="missing_env_example",
                    severity="medium",
                    message=".env.example is missing — document required env variables",
                    auto_fixable=False,
                )
            )

        gitignore = root / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text(encoding="utf-8")
            if ".env" not in content:
                issues.append(
                    Issue(
                        file=str(gitignore),
                        line=0,
                        issue_type="missing_gitignore_entry",
                        severity="high",
                        message=".gitignore does not include .env files",
                        auto_fixable=False,
                    )
                )
        return issues

    def scan_directory(self, root: Path, exclude_dirs: list[str] | None = None) -> list[Issue]:
        """
        Scan all relevant files under root for config/secret issues.

        Args:
            root: Root directory to scan.
            exclude_dirs: Directory names to skip.

        Returns:
            Aggregated list of all issues found.
        """
        skip = set(exclude_dirs or [])
        all_issues: list[Issue] = []
        for file in root.rglob("*"):
            if not file.is_file():
                continue
            if any(part in skip for part in file.parts):
                continue
            if file.suffix in self.SCAN_EXTENSIONS or file.name.startswith(".env"):
                all_issues.extend(self.scan_file(file))
        all_issues.extend(self.check_env_example(root))
        return all_issues
