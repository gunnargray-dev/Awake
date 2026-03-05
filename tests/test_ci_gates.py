"""Tests for src.ci_gates.

These tests focus on the health gate behavior and ensure argument parsing
and exit codes remain stable for CI usage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src import ci_gates


def test_build_parser_has_health_command() -> None:
    parser = ci_gates.build_parser()
    # Ensure subcommand exists and parses expected defaults.
    args = parser.parse_args(["health"])
    assert args.command == "health"
    assert args.repo == "."
    assert args.min_score == 80.0


def test_main_health_passes_when_score_above_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyReport:
        overall_health_score = 90.0

    def fake_report(_repo: Path) -> DummyReport:
        return DummyReport()

    monkeypatch.setattr(ci_gates, "generate_health_report", fake_report)

    rc = ci_gates.main(["health", "--repo", str(tmp_path), "--min-score", "80"])
    assert rc == 0


def test_main_health_fails_when_score_below_threshold(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class DummyReport:
        overall_health_score = 70.0

    def fake_report(_repo: Path) -> DummyReport:
        return DummyReport()

    monkeypatch.setattr(ci_gates, "generate_health_report", fake_report)

    rc = ci_gates.main(["health", "--repo", str(tmp_path), "--min-score", "80"])
    assert rc == 1

    captured = capsys.readouterr()
    assert "Health score gate failed" in captured.err
