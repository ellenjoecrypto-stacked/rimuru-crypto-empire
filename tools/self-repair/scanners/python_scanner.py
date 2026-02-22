"""
Rimuru Repair — Python Code Quality Scanner
============================================
Detects common Python code quality issues.
"""

import ast
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
    severity: str  # 'critical', 'high', 'medium', 'low'
    message: str
    auto_fixable: bool = False
    context: str = ""


class PythonScanner:
    """
    Scans Python source files for code quality issues.

    Detects:
    - Raw print() statements
    - Bare except blocks
    - Hardcoded file paths
    - Missing docstrings on public functions/classes
    - import * usage
    - Debug code (breakpoint, pdb, ipdb)
    - os.system() calls
    - Mutable default arguments
    - Generic exception handling
    - Missing type hints on public functions
    - TODO/FIXME/HACK comments
    """

    # Patterns for regex-based checks
    HARDCODED_PATH_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"""(?:["'])([A-Za-z]:[\\\/][^"']*|\/home\/[^"']+|\/Users\/[^"']+|\/root\/[^"']+)(?:["'])"""
    )
    TODO_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"#\s*(TODO|FIXME|HACK|XXX)\b.*", re.IGNORECASE
    )
    OS_SYSTEM_RE: ClassVar[re.Pattern[str]] = re.compile(r"\bos\.system\s*\(")
    PDB_RE: ClassVar[re.Pattern[str]] = re.compile(
        r"\b(breakpoint|pdb\.set_trace|ipdb\.set_trace)\s*\("
    )

    def scan_file(self, path: Path) -> list[Issue]:
        """
        Scan a single Python file and return all issues found.

        Args:
            path: Path to the Python file to scan.

        Returns:
            List of Issue objects detected in the file.
        """
        issues: list[Issue] = []
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning("Cannot read %s: %s", path, e)
            return issues

        # Line-based regex checks (fast pass)
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()

            # os.system() usage
            if self.OS_SYSTEM_RE.search(line):
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="os_system",
                        severity="high",
                        message="Use subprocess.run() instead of os.system()",
                        auto_fixable=True,
                        context=stripped,
                    )
                )

            # Debug code
            if self.PDB_RE.search(line):
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="debug_code",
                        severity="high",
                        message="Debug statement left in code",
                        auto_fixable=False,
                        context=stripped,
                    )
                )

            # Hardcoded paths
            issues.extend(
                Issue(
                    file=str(path),
                    line=lineno,
                    issue_type="hardcoded_path",
                    severity="medium",
                    message=f"Hardcoded path detected: {match.group(1)!r}",
                    auto_fixable=True,
                    context=stripped,
                )
                for match in self.HARDCODED_PATH_RE.finditer(line)
            )

            # TODO/FIXME/HACK comments
            if self.TODO_RE.search(line):
                m = self.TODO_RE.search(line)
                tag = m.group(1).upper() if m else "TODO"
                issues.append(
                    Issue(
                        file=str(path),
                        line=lineno,
                        issue_type="todo_comment",
                        severity="low",
                        message=f"{tag} comment — review and resolve",
                        auto_fixable=False,
                        context=stripped,
                    )
                )

        # AST-based checks
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            logger.debug("Syntax error in %s: %s", path, e)
            return issues

        issues.extend(self._check_ast(tree, source, str(path)))
        return issues

    def _check_ast(self, tree: ast.AST, source: str, filename: str) -> list[Issue]:
        """Run all AST-based checks on a parsed tree."""
        issues: list[Issue] = []
        lines = source.splitlines()

        for node in ast.walk(tree):
            # print() statements
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call = node.value
                if isinstance(call.func, ast.Name) and call.func.id == "print":
                    ctx = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    issues.append(
                        Issue(
                            file=filename,
                            line=node.lineno,
                            issue_type="print_statement",
                            severity="medium",
                            message="Use logging instead of print()",
                            auto_fixable=True,
                            context=ctx,
                        )
                    )

            # import *
            if isinstance(node, ast.ImportFrom) and node.names:
                for alias in node.names:
                    if alias.name == "*":
                        ctx = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        issues.append(
                            Issue(
                                file=filename,
                                line=node.lineno,
                                issue_type="star_import",
                                severity="medium",
                                message=f"Avoid wildcard import from {node.module!r}",
                                auto_fixable=False,
                                context=ctx,
                            )
                        )

            # Bare except / except Exception
            if isinstance(node, ast.ExceptHandler):
                ctx = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                if node.type is None:
                    issues.append(
                        Issue(
                            file=filename,
                            line=node.lineno,
                            issue_type="bare_except",
                            severity="high",
                            message="Bare except: clause — use except Exception as e:",
                            auto_fixable=True,
                            context=ctx,
                        )
                    )
                elif isinstance(node.type, ast.Name) and node.type.id == "Exception":
                    issues.append(
                        Issue(
                            file=filename,
                            line=node.lineno,
                            issue_type="generic_except",
                            severity="medium",
                            message="Generic except Exception — catch specific exceptions",
                            auto_fixable=False,
                            context=ctx,
                        )
                    )

            # Mutable default arguments
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        ctx = (
                            lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        )
                        issues.append(
                            Issue(
                                file=filename,
                                line=node.lineno,
                                issue_type="mutable_default",
                                severity="high",
                                message=f"Mutable default argument in {node.name!r}",
                                auto_fixable=False,
                                context=ctx,
                            )
                        )

                # Missing docstrings on public functions
                if not node.name.startswith("_") and not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    ctx = (
                        lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                    )
                    issues.append(
                        Issue(
                            file=filename,
                            line=node.lineno,
                            issue_type="missing_docstring",
                            severity="low",
                            message=f"Public function {node.name!r} is missing a docstring",
                            auto_fixable=False,
                            context=ctx,
                        )
                    )

                # Missing type hints on public functions
                if not node.name.startswith("_"):
                    all_args = node.args.args + node.args.posonlyargs + node.args.kwonlyargs
                    missing_hints = [
                        arg.arg
                        for arg in all_args
                        if arg.arg not in {"self", "cls"} and arg.annotation is None
                    ]
                    if missing_hints or node.returns is None:
                        ctx = (
                            lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                        )
                        issues.append(
                            Issue(
                                file=filename,
                                line=node.lineno,
                                issue_type="missing_type_hints",
                                severity="low",
                                message=(
                                    f"Public function {node.name!r} missing type hints"
                                    f" (args: {missing_hints},"
                                    f" return: {node.returns is None})"
                                ),
                                auto_fixable=False,
                                context=ctx,
                            )
                        )

            # Missing docstrings on public classes
            if (
                isinstance(node, ast.ClassDef)
                and not node.name.startswith("_")
                and not (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                )
            ):
                ctx = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
                issues.append(
                    Issue(
                        file=filename,
                        line=node.lineno,
                        issue_type="missing_docstring",
                        severity="low",
                        message=f"Public class {node.name!r} is missing a docstring",
                        auto_fixable=False,
                        context=ctx,
                    )
                )

        return issues

    def scan_directory(self, root: Path, exclude_dirs: list[str] | None = None) -> list[Issue]:
        """
        Scan all Python files under root recursively.

        Args:
            root: Root directory to scan.
            exclude_dirs: Directory names to skip.

        Returns:
            Aggregated list of all issues found.
        """
        skip = set(exclude_dirs or [])
        all_issues: list[Issue] = []
        for py_file in root.rglob("*.py"):
            if any(part in skip for part in py_file.parts):
                continue
            all_issues.extend(self.scan_file(py_file))
        return all_issues
