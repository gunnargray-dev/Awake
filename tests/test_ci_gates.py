from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from src import ci_gates


def test_build_parser_requires_subcommand() -> None:
    parser = ci_gates.build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args([])

    assert exc.value.code == 2


def test_build_parser_health_defaults() -> None:
    parser = ci_gates.build_parser()
    args = parser.parse_args(["health"])

    assert args.command == "health"
    assert Path(args.repo) == Path(".")
    assert args.min_score == 80.0


def test_build_parser_health_overrides() -> None:
    parser = ci_gates.build_parser()
    args = parser.parse_args(["health", "--repo", "somewhere", "--min-score", "72.5"])

    assert args.command == "health"
    assert Path(args.repo) == Path("somewhere")
    assert args.min_score == 72.5


def test_cmd_health_pass(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class _FakeReport:
        overall_health_score = 85.0

    def _fake_generate_health_report(_path: Path) -> _FakeReport:
        return _FakeReport()

    monkeypatch.setattr(ci_gates, "generate_health_report", _fake_generate_health_report)

    args = argparse.Namespace(repo=".", min_score=80.0)
    rc = ci_gates._cmd_health(args)

    assert rc == 0
    captured = capsys.readouterr()
    assert "passed" in captured.out


def test_cmd_health_fail(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    class _FakeReport:
        overall_health_score = 60.25

    def _fake_generate_health_report(_path: Path) -> _FakeReport:
        return _FakeReport()

    monkeypatch.setattr(ci_gates, "generate_health_report", _fake_generate_health_report)

    args = argparse.Namespace(repo=".", min_score=80.0)
    rc = ci_gates._cmd_health(args)

    assert rc == 1
    captured = capsys.readouterr()
    assert "failed" in captured.err


def test_main_health_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci_gates, "_cmd_health", lambda _args: 0)
    assert ci_gates.main(["health"]) == 0


def test_main_health_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ci_gates, "_cmd_health", lambda _args: 1)
    assert ci_gates.main(["health"]) == 1
