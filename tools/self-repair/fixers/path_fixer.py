"""
Rimuru Repair — Path/Environment Variable Fixer
================================================
Detects and replaces hardcoded file paths with os.getenv() or Path() references.
"""

import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# Regex for hardcoded Windows and Unix paths in Python source
_WIN_PATH_RE = re.compile(
    r"""(["'])([A-Za-z]:[\\\/][^"']+)\1"""
)
_UNIX_PATH_RE = re.compile(
    r"""(["'])(\/(?:home|root|Users)\/[^"']+)\1"""
)


_MIN_PATH_PARTS = 2


def _path_to_env_var(raw_path: str) -> str:
    """Convert a raw path string into a suggested env var name."""
    parts = [p for p in re.split(r"[/\\]", raw_path) if p and p != ":"]
    if len(parts) >= _MIN_PATH_PARTS:
        name = "_".join(parts[-2:]).upper()
    elif parts:
        name = parts[-1].upper()
    else:
        name = "DATA_PATH"
    return re.sub(r"[^A-Z0-9_]", "_", name)


class PathFixer:
    """
    Detects and replaces hardcoded file paths in Python files.

    Replacements:
    - "C:\\Users\\..." → os.getenv('VAR_NAME', 'default')
    - "/home/user/..." → os.getenv('VAR_NAME', 'default')
    """

    def fix_file(self, path: Path) -> dict[str, int | list[str]]:
        """
        Replace hardcoded paths in a Python file with os.getenv() calls.

        Args:
            path: Path to the Python file to fix.

        Returns:
            Dictionary with counts and suggested env var names.
        """
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
            return {}

        counts: dict[str, int] = {"paths_replaced": 0}
        suggestions: list[str] = []

        def replace_path(match: re.Match) -> str:
            quote = match.group(1)
            raw = match.group(2)
            env_var = _path_to_env_var(raw)
            suggestions.append(f"{env_var}={raw}")
            counts["paths_replaced"] += 1
            return f"os.getenv({quote}{env_var}{quote}, {quote}{raw}{quote})"

        new_source = _WIN_PATH_RE.sub(replace_path, source)
        new_source = _UNIX_PATH_RE.sub(replace_path, new_source)

        if counts["paths_replaced"] > 0:
            # Ensure os is imported
            if "import os" not in new_source:
                new_source = "import os\n" + new_source
            path.write_text(new_source, encoding="utf-8")
            logger.info(
                "Fixed %d hardcoded path(s) in %s. Suggested env vars: %s",
                counts["paths_replaced"],
                path,
                suggestions,
            )

        return {**counts, "env_var_suggestions": suggestions}
