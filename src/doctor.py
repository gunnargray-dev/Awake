"""Awake Doctor — repo health diagnostic command.

Runs a comprehensive suite of checks on the repository and surfaces any
issues that need attention before the next session.  Think of it as a
pre-flight check list: CI readiness, module coverage, test suite health,
TODO debt, dependency sanity, and more.

The doctor produces a ``DiagnosticReport`` with colour-coded findings
(OK / WARN / FAIL) and an overall letter grade (A–F).

Usage::

    from src.doctor import diagnose, render_report, save_report
    report = diagnose(repo_root=Path("."))
    print(render_report(report))
    save_report(report, out_path=Path("docs/doctor_report.md"))

CLI::

    awake doctor
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"

STATUS_ICONS = {STATUS_OK: "OK", STATUS_WARN: "WARN", STATUS_FAIL: "FAIL"}
STATUS_WEIGHT = {STATUS_OK: 0, STATUS_WARN: 1, STATUS_FAIL: 2}


@dataclass
class Check:
    """A single doctor check result."""

    status: str        # OK | WARN | FAIL
    name: str
    message: str       # Human-readable finding
    detail: str = ""   # Optional extra context (multi-line OK)

    @property
    def icon(self) -> str:
        """Return the status icon for this check."""
        return STATUS_ICONS.get(self.status, "?")

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class DiagnosticReport:
    """Complete output of ``diagnose()``."""

    checks: list[Check]
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )

    @property
    def ok_count(self) -> int:
        """Number of passing checks."""
        return sum(1 for c in self.checks if c.status == STATUS_OK)

    @property
    def warn_count(self) -> int:
        """Number of warning checks."""
        return sum(1 for c in self.checks if c.status == STATUS_WARN)

    @property
    def fail_count(self) -> int:
        """Number of failing checks."""
        return sum(1 for c in self.checks if c.status == STATUS_FAIL)

    @property
    def grade(self) -> str:
        """Overall health grade A–F."""
        total = len(self.checks)
        if total == 0:
            return "N/A"
        fail_pct = self.fail_count / total
        warn_pct = self.warn_count / total
        if fail_pct == 0 and warn_pct == 0:
            return "A"
        if fail_pct == 0 and warn_pct <= 0.20:
            return "B"
        if fail_pct <= 0.10 and warn_pct <= 0.30:
            return "C"
        if fail_pct <= 0.20:
            return "D"
        return "F"

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "generated_at": self.generated_at,
            "grade": self.grade,
            "ok_count": self.ok_count,
            "warn_count": self.warn_count,
            "fail_count": self.fail_count,
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# Individual check implementations
# ---------------------------------------------------------------------------


def _check_src_exists(repo_root: Path) -> Check:
    src = repo_root / "src"
    if src.is_dir():
        py_count = len(list(src.glob("*.py")))
        return Check(STATUS_OK, "src/ directory", f"{py_count} Python module(s) found in src/")
    return Check(STATUS_FAIL, "src/ directory", "src/ directory is missing")


def _check_tests_exist(repo_root: Path) -> Check:
    tests = repo_root / "tests"
    if not tests.is_dir():
        return Check(STATUS_FAIL, "tests/ directory", "tests/ directory is missing")
    test_files = list(tests.glob("test_*.py"))
    if not test_files:
        return Check(STATUS_WARN, "tests/ directory", "No test_*.py files found in tests/")
    return Check(STATUS_OK, "tests/ directory", f"{len(test_files)} test file(s) found")


def _check_test_coverage(repo_root: Path) -> Check:
    """Check that every src/ module has a corresponding test file."""
    src = repo_root / "src"
    tests = repo_root / "tests"
    if not src.is_dir() or not tests.is_dir():
        return Check(STATUS_WARN, "test coverage (file)", "Cannot check — src/ or tests/ missing")

    src_modules = {p.stem for p in src.glob("*.py") if p.name != "__init__.py"}
    test_modules = {p.name[5:-3] for p in tests.glob("test_*.py")}  # strip "test_" and ".py"
    untested = src_modules - test_modules

    if not untested:
        return Check(STATUS_OK, "test coverage (file)", "Every src/ module has a test file")
    missing = ", ".join(sorted(untested))
    status = STATUS_FAIL if len(untested) > 2 else STATUS_WARN
    return Check(status, "test coverage (file)", f"{len(untested)} module(s) lack test files: {missing}")


def _check_syntax(repo_root: Path) -> Check:
    """Verify all src/ Python files parse without SyntaxError."""
    src = repo_root / "src"
    if not src.is_dir():
        return Check(STATUS_WARN, "syntax check", "src/ missing — skipped")

    bad: list[str] = []
    for py_file in sorted(src.glob("*.py")):
        try:
            ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as exc:
            bad.append(f"{py_file.name}:{exc.lineno}: {exc.msg}")

    if bad:
        return Check(
            STATUS_FAIL, "syntax check",
            f"{len(bad)} file(s) have syntax errors",
            detail="\n".join(bad),
        )
    py_count = len(list(src.glob("*.py")))
    return Check(STATUS_OK, "syntax check", f"All {py_count} src/ files are syntactically valid")


def _check_docstrings(repo_root: Path) -> Check:
    """Warn if any public module-level function is missing a docstring."""
    src = repo_root / "src"
    if not src.is_dir():
        return Check(STATUS_WARN, "docstrings", "src/ missing — skipped")

    missing: list[str] = []
    for py_file in sorted(src.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_") and not ast.get_docstring(node):
                    missing.append(f"{py_file.name}:{node.name}()")

    if len(missing) > 10:
        return Check(
            STATUS_WARN, "docstrings",
            f"{len(missing)} public functions missing docstrings",
            detail="\n".join(missing[:10]) + "\n...",
        )
    if missing:
        return Check(
            STATUS_WARN, "docstrings",
            f"{len(missing)} public function(s) missing docstrings",
            detail="\n".join(missing),
        )
    return Check(STATUS_OK, "docstrings", "All public functions have docstrings")


def _check_future_annotations(repo_root: Path) -> Check:
    """Ensure every src/ module has `from __future__ import annotations` for 3.10 compat."""
    src = repo_root / "src"
    if not src.is_dir():
        return Check(STATUS_WARN, "future annotations", "src/ missing — skipped")

    missing: list[str] = []
    for py_file in sorted(src.glob("*.py")):
        code = py_file.read_text(encoding="utf-8", errors="replace")
        if "from __future__ import annotations" not in code:
            missing.append(py_file.name)

    if missing:
        files = ", ".join(missing)
        return Check(
            STATUS_WARN, "future annotations",
            f"{len(missing)} module(s) missing 'from __future__ import annotations': {files}",
        )
    py_count = len(list(src.glob("*.py")))
    return Check(STATUS_OK, "future annotations", f"All {py_count} modules have future annotations")


def _check_ci_workflow(repo_root: Path) -> Check:
    """Check that CI workflow exists and covers Python 3.10."""
    ci = repo_root / ".github" / "workflows" / "ci.yml"
    if not ci.exists():
        return Check(STATUS_FAIL, "CI workflow", ".github/workflows/ci.yml not found")

    content = ci.read_text(encoding="utf-8")
    has_310 = "3.10" in content
    has_311 = "3.11" in content
    has_312 = "3.12" in content

    versions = []
    if has_310:
        versions.append("3.10")
    if has_311:
        versions.append("3.11")
    if has_312:
        versions.append("3.12")

    if has_310:
        return Check(STATUS_OK, "CI workflow", f"CI workflow present (Python {', '.join(versions)})")
    return Check(STATUS_WARN, "CI workflow", f"CI workflow present but missing Python 3.10 (found: {', '.join(versions)})")


# Remaining functions unchanged from repository version.
