"""
Rimuru Repair — TypeScript/JavaScript Auto-Fixer
=================================================
Applies automatic fixes for TypeScript/JavaScript code quality issues.
"""

import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class TypeScriptFixer:
    """
    Auto-fixes common TypeScript/JavaScript code quality issues.

    Supports:
    - Remove console.log/console.error/console.warn lines
    - Replace ': any' with ': unknown' where safe (non-cast contexts)
    """

    CONSOLE_LINE_RE = re.compile(r"^\s*console\.(log|error|warn|debug|info)\s*\(.*\);\s*$")
    ANY_TYPE_RE = re.compile(r"(:\s*)any\b")

    def fix_file(self, path: Path) -> dict[str, int]:
        """
        Apply all auto-fixes to a TypeScript/JavaScript file in-place.

        Args:
            path: Path to the file to fix.

        Returns:
            Dictionary of {fix_type: count} for fixes applied.
        """
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
            return {}

        lines = source.splitlines(keepends=True)
        counts: dict[str, int] = {}
        new_lines = []

        for line in lines:
            # Remove standalone console.* lines
            if self.CONSOLE_LINE_RE.match(line):
                counts["console_removed"] = counts.get("console_removed", 0) + 1
                continue

            # Replace : any → : unknown
            if self.ANY_TYPE_RE.search(line):
                fixed = self.ANY_TYPE_RE.sub(r"\1unknown", line)
                new_lines.append(fixed)
                counts["any_replaced"] = counts.get("any_replaced", 0) + 1
                continue

            new_lines.append(line)

        new_source = "".join(new_lines)
        if new_source != source:
            path.write_text(new_source, encoding="utf-8")
            logger.info("Fixed %s: %s", path, counts)

        return counts
