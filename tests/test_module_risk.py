from __future__ import annotations

from pathlib import Path

import pytest

from src.module_risk import generate_module_risk


def test_generate_module_risk_smoke(tmp_path: Path) -> None:
    """Report generates without coverage input and includes src modules."""
    # minimal repo clone
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "src" / "b.py").write_text("def f():\n    return 1\n", encoding="utf-8")

    # Coupling/complexity analyzers expect to import from src.*, so put our test
    # repo on sys.path by changing cwd. Both analyzers operate via AST reads.
    report = generate_module_risk(repo_root=tmp_path, coverage_json=None)
    assert report.rows
    mods = {r.module for r in report.rows}
    assert "src/a.py" in mods
    assert "src/b.py" in mods


def test_generate_module_risk_with_coverage_json(tmp_path: Path) -> None:
    """Coverage JSON is joined when present."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    cov = {
        "files": {
            str(tmp_path / "src" / "a.py"): {"summary": {"percent_covered": 12.5}},
        }
    }
    cov_path = tmp_path / "coverage.json"
    cov_path.write_text(__import__("json").dumps(cov), encoding="utf-8")

    report = generate_module_risk(repo_root=tmp_path, coverage_json=cov_path)
    row = next(r for r in report.rows if r.module == "src/a.py")
    assert row.coverage_pct == pytest.approx(12.5)


def test_report_markdown_renders(tmp_path: Path) -> None:
    """Markdown output includes headers and table."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")

    report = generate_module_risk(repo_root=tmp_path, coverage_json=None)
    md = report.to_markdown(limit=10)
    assert "# Module Risk Report" in md
    assert "| Module | Risk |" in md
