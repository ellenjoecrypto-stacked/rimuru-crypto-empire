"""
Rimuru Repair — Python Auto-Fixer
===================================
Applies automatic fixes for common Python code quality issues.
"""

import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# Logger setup lines to inject when adding logging import
_LOGGER_SETUP = "import logging\n\nlogger = logging.getLogger(__name__)\n"
_LOGGING_IMPORT = "import logging"
_LOGGER_LINE = "logger = logging.getLogger(__name__)"


class PythonFixer:
    """
    Auto-fixes common Python code quality issues in source files.

    Supports:
    - print() → logger.info() / logger.debug()
    - bare except: → except Exception as e:
    - except: pass → except Exception as e: logger.debug(...)
    - os.system() → subprocess.run()
    - Inject missing logging setup
    """

    PRINT_RE = re.compile(r"^(\s*)print\s*\(")
    BARE_EXCEPT_RE = re.compile(r"^(\s*)except\s*:\s*$")
    EXCEPT_PASS_RE = re.compile(r"^(\s*)except\s*:\s*pass\s*$")
    OS_SYSTEM_RE = re.compile(r"\bos\.system\s*\(")

    def fix_file(self, path: Path) -> dict[str, int]:
        """
        Apply all auto-fixes to a Python source file in-place.

        Args:
            path: Path to the Python file to fix.

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
            # Fix bare except: pass  (must check before bare except:)
            m = self.EXCEPT_PASS_RE.match(line)
            if m:
                indent = m.group(1)
                new_lines.append(f"{indent}except Exception as e:\n")
                new_lines.append(f'{indent}    logger.debug("Skipped: %s", e)\n')
                counts["except_pass_fixed"] = counts.get("except_pass_fixed", 0) + 1
                continue

            # Fix bare except:
            m = self.BARE_EXCEPT_RE.match(line)
            if m:
                indent = m.group(1)
                new_lines.append(f"{indent}except Exception as e:\n")
                new_lines.append(f'{indent}    logger.error("Error: %s", e)\n')
                counts["bare_except_fixed"] = counts.get("bare_except_fixed", 0) + 1
                continue

            # Fix print() → logger.info()
            m = self.PRINT_RE.match(line)
            if m:
                indent = m.group(1)
                # Extract args by stripping the print( ... ) wrapper
                inner = line.strip()
                # Remove leading 'print(' and trailing ')'
                if inner.startswith("print(") and inner.rstrip().endswith(")"):
                    args = inner[6:].rstrip()
                    if args.endswith(")"):
                        args = args[:-1]
                    new_lines.append(f"{indent}logger.info({args})\n")
                else:
                    new_lines.append(line)
                counts["print_fixed"] = counts.get("print_fixed", 0) + 1
                continue

            # Fix os.system() → subprocess.run()
            if self.OS_SYSTEM_RE.search(line):
                fixed = self.OS_SYSTEM_RE.sub("subprocess.run(", line)
                new_lines.append(fixed)
                counts["os_system_fixed"] = counts.get("os_system_fixed", 0) + 1
                continue

            new_lines.append(line)

        new_source = "".join(new_lines)

        # Inject logging setup if fixes were applied and logging isn't already imported
        if counts:
            new_source = self._ensure_logging_setup(new_source, counts)
            # Ensure subprocess is imported if os.system was fixed
            if counts.get("os_system_fixed"):
                new_source = self._ensure_import(new_source, "subprocess")

        if new_source != source:
            path.write_text(new_source, encoding="utf-8")
            logger.info("Fixed %s: %s", path, counts)

        return counts

    def _ensure_logging_setup(self, source: str, counts: dict[str, int]) -> str:
        """Inject logging import and logger setup if not already present."""
        needs_logging = any(
            k in counts
            for k in ("print_fixed", "bare_except_fixed", "except_pass_fixed")
        )
        if not needs_logging:
            return source

        has_import = _LOGGING_IMPORT in source
        has_logger = _LOGGER_LINE in source

        if has_import and has_logger:
            return source

        lines = source.splitlines(keepends=True)
        new_lines = []
        injected = False

        for i, line in enumerate(lines):
            new_lines.append(line)
            # Inject after the last import block
            if (not injected and line.startswith("import ")) or line.startswith("from "):
                # Check if next line is not also an import
                peek = lines[i + 1] if i + 1 < len(lines) else ""
                if not (peek.startswith(("import ", "from "))):
                    if not has_import:
                        new_lines.append(_LOGGING_IMPORT + "\n")
                    if not has_logger:
                        new_lines.append(_LOGGER_LINE + "\n")
                    injected = True

        if not injected:
            # Prepend at the top
            prefix = []
            if not has_import:
                prefix.append(_LOGGING_IMPORT + "\n")
            if not has_logger:
                prefix.append(_LOGGER_LINE + "\n")
            new_lines = prefix + new_lines

        return "".join(new_lines)

    def _ensure_import(self, source: str, module: str) -> str:
        """Ensure an import statement is present in source."""
        import_line = f"import {module}"
        if import_line in source:
            return source
        # Insert after first import or at top
        lines = source.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.startswith(("import ", "from ")):
                lines.insert(i, import_line + "\n")
                return "".join(lines)
        return import_line + "\n" + source
