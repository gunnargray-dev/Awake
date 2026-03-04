"""
Tests for src.digest — Nightly digest generator.

Covers:
- SessionDigest and DigestReport data structures
- Delta computation (_compute_deltas)
- Executive summary generation (_build_executive_summary)
- Time-based filtering (_filter_by_hours)
- Session-count filtering (_filter_by_session_count)
- Public API (generate_digest)
- All three output formats (markdown, json, text)
- CLI integration (cmd_digest)
- Edge cases: empty log, single session, no matching sessions
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.digest import (
    DigestReport,
    SessionDigest,
    _build_executive_summary,
    _compute_deltas,
    _filter_by_hours,
    _filter_by_session_count,
    generate_digest,
)
from src.insights import SessionRecord


# ---------------------------------------------------------------------------
# Fixtures: synthetic AWAKE_LOG.md fragments
# ---------------------------------------------------------------------------

SINGLE_SESSION_LOG = """\
## Session 5 -- Stats Engine (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built `src/stats.py`
- Done Wrote 50 tests

### PRs
- PR #2 -- Stats engine
- PR #3 -- Test framework

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 8 |
| Tests | 50 |
| PRs opened | 2 |
"""

MULTI_SESSION_LOG = """\
## Session 0 -- Scaffold (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Created repo scaffold

### PRs
- PR #1 -- Scaffold

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 3 |
| Tests | 0 |
| PRs opened | 1 |

## Session 1 -- Stats (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/stats.py`
- Done Wrote 50 tests

### PRs
- PR #2 -- Stats engine
- PR #3 -- Test framework

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 8 |
| Tests | 50 |
| PRs opened | 2 |

## Session 2 -- Health (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built `src/health.py`
- Done Added 80 tests

### PRs
- PR #4 -- Health module
- PR #5 -- Coverage tracker

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 12 |
| Tests | 130 |
| PRs opened | 2 |

## Session 3 -- Insights (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built insights engine

### PRs
- PR #6 -- Insights module

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 15 |
| Tests | 180 |
| PRs opened | 1 |
"""


# ---------------------------------------------------------------------------
# SessionDigest tests
# ---------------------------------------------------------------------------


class TestSessionDigest:
    def test_to_dict(self):
        d = SessionDigest(
            number=1, date="2026-02-27", title="Test",
            tasks=["task1"], pr_count=1, pr_titles=["PR #1 -- Test"],
            modules=8, tests=50, modules_added=5, tests_added=50,
        )
        result = d.to_dict()
        assert result["number"] == 1
        assert result["modules_added"] == 5
        assert result["tests_added"] == 50
        assert result["tasks"] == ["task1"]


# ---------------------------------------------------------------------------
# DigestReport serialization
# ---------------------------------------------------------------------------


class TestDigestReport:
    def _sample_report(self) -> DigestReport:
        return DigestReport(
            sessions=[
                SessionDigest(
                    number=1, date="2026-02-27", title="Stats",
                    tasks=["Built stats", "Wrote tests"],
                    pr_count=2, pr_titles=["Stats engine", "Test framework"],
                    modules=8, tests=50, modules_added=5, tests_added=50,
                ),
            ],
            session_count=1,
            date_range="2026-02-27",
            total_tasks=2,
            total_prs=2,
            total_modules_added=5,
            total_tests_added=50,
            current_modules=8,
            current_tests=50,
            executive_summary="Session 1 (Stats): completed 2 tasks, opened 2 PRs.",
        )

    def test_to_dict_structure(self):
        report = self._sample_report()
        d = report.to_dict()
        assert d["session_count"] == 1
        assert d["total_tasks"] == 2
        assert d["total_prs"] == 2
        assert len(d["sessions"]) == 1
        assert d["sessions"][0]["number"] == 1

    def test_to_json_valid(self):
        report = self._sample_report()
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["session_count"] == 1

    def test_to_markdown_has_header(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "# Awake: Nightly Digest" in md

    def test_to_markdown_has_tldr(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "## TL;DR" in md
        assert report.executive_summary in md

    def test_to_markdown_has_overview_table(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "| Sessions | 1 |" in md
        assert "| Tasks completed | 2 |" in md

    def test_to_markdown_has_session_details(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "### Session 1: Stats" in md
        assert "Built stats" in md

    def test_to_markdown_has_growth(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "+5 modules" in md
        assert "+50 tests" in md

    def test_to_text_format(self):
        report = self._sample_report()
        text = report.to_text()
        assert "AWAKE NIGHTLY DIGEST" in text
        assert "Sessions: 1" in text
        assert "Tasks: 2" in text

    def test_to_text_has_session_detail(self):
        report = self._sample_report()
        text = report.to_text()
        assert "Session 1: Stats" in text

    def test_empty_report_markdown(self):
        report = DigestReport(
            sessions=[], session_count=0, date_range="",
            total_tasks=0, total_prs=0, total_modules_added=0,
            total_tests_added=0, current_modules=0, current_tests=0,
            executive_summary="No sessions found.",
        )
        md = report.to_markdown()
        assert "No sessions found." in md


# ---------------------------------------------------------------------------
# _compute_deltas
# ---------------------------------------------------------------------------


class TestComputeDeltas:
    def test_single_session_delta(self):
        all_records = [
            SessionRecord(0, "2026-02-27", "Scaffold", 1, 3, 0, ["task"], []),
            SessionRecord(1, "2026-02-27", "Stats", 2, 8, 50, ["task"], []),
        ]
        digests = _compute_deltas([all_records[1]], all_records)
        assert len(digests) == 1
        assert digests[0].modules_added == 5
        assert digests[0].tests_added == 50

    def test_first_session_delta(self):
        records = [
            SessionRecord(0, "2026-02-27", "Scaffold", 1, 3, 10, [], []),
        ]
        digests = _compute_deltas(records, records)
        assert digests[0].modules_added == 3
        assert digests[0].tests_added == 10

    def test_multiple_sessions(self):
        all_records = [
            SessionRecord(0, "2026-02-27", "A", 1, 3, 0, [], []),
            SessionRecord(1, "2026-02-27", "B", 1, 8, 50, [], []),
            SessionRecord(2, "2026-02-28", "C", 1, 12, 130, [], []),
        ]
        digests = _compute_deltas(all_records[1:], all_records)
        assert digests[0].modules_added == 5   # 8 - 3
        assert digests[1].modules_added == 4   # 12 - 8
        assert digests[1].tests_added == 80    # 130 - 50

    def test_zero_modules_skipped(self):
        """If modules is 0 (not reported), modules_added should be 0."""
        all_records = [
            SessionRecord(0, "2026-02-27", "A", 1, 3, 10, [], []),
            SessionRecord(1, "2026-02-27", "B", 1, 0, 20, [], []),
        ]
        digests = _compute_deltas([all_records[1]], all_records)
        assert digests[0].modules_added == 0


# ---------------------------------------------------------------------------
# _build_executive_summary
# ---------------------------------------------------------------------------


class TestBuildExecutiveSummary:
    def test_empty_list(self):
        result = _build_executive_summary([])
        assert "No sessions" in result

    def test_single_session(self):
        d = SessionDigest(
            number=5, date="2026-02-28", title="Stats Engine",
            tasks=["Built stats", "Wrote tests"],
            pr_count=2, pr_titles=[], modules=8, tests=50,
            modules_added=5, tests_added=50,
        )
        result = _build_executive_summary([d])
        assert "Session 5" in result
        assert "Stats Engine" in result
        assert "2 tasks" in result
        assert "2 PRs" in result

    def test_multi_session(self):
        digests = [
            SessionDigest(1, "2026-02-27", "A", ["t1"], 1, [], 5, 10, 5, 10),
            SessionDigest(2, "2026-02-28", "B", ["t2", "t3"], 2, [], 10, 30, 5, 20),
            SessionDigest(3, "2026-02-28", "C", ["t4"], 1, [], 15, 50, 5, 20),
        ]
        result = _build_executive_summary(digests)
        assert "Sessions 1" in result
        assert "4 tasks" in result
        assert "4 PRs" in result

    def test_multi_session_highlights(self):
        digests = [
            SessionDigest(i, "2026-02-27", f"Task{i}", [f"t{i}"], 1, [], i * 3, i * 10, 3, 10)
            for i in range(1, 6)
        ]
        result = _build_executive_summary(digests)
        # First 3 titles mentioned, rest as "and N more"
        assert "Task1" in result
        assert "and 2 more" in result


# ---------------------------------------------------------------------------
# _filter_by_hours and _filter_by_session_count
# ---------------------------------------------------------------------------


class TestFilterBySessionCount:
    def test_returns_last_n(self):
        records = [
            SessionRecord(i, "2026-02-27", f"S{i}", 1, i * 3, i * 10, [], [])
            for i in range(5)
        ]
        result = _filter_by_session_count(records, 2)
        assert len(result) == 2
        assert result[0].number == 3
        assert result[1].number == 4

    def test_returns_all_if_count_exceeds(self):
        records = [
            SessionRecord(i, "2026-02-27", f"S{i}", 1, 0, 0, [], [])
            for i in range(3)
        ]
        result = _filter_by_session_count(records, 10)
        assert len(result) == 3


class TestFilterByHours:
    def test_filters_by_date(self):
        # Sessions with old dates should be filtered out
        records = [
            SessionRecord(0, "2020-01-01", "Old", 1, 0, 0, [], []),
            SessionRecord(1, "2026-03-04", "Recent", 1, 0, 0, [], []),
        ]
        result = _filter_by_hours(records, 24)
        # Only the recent one should remain
        assert all(r.date >= "2026-03-03" for r in result)


# ---------------------------------------------------------------------------
# Public API: generate_digest
# ---------------------------------------------------------------------------


class TestGenerateDigest:
    def test_single_session_log(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(SINGLE_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=1)
        assert report.session_count == 1
        assert report.sessions[0].number == 5
        assert report.total_prs == 2

    def test_multi_session_last_2(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=2)
        assert report.session_count == 2
        assert report.sessions[0].number == 2
        assert report.sessions[1].number == 3

    def test_multi_session_all(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=100)
        assert report.session_count == 4

    def test_empty_log(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text("")
        report = generate_digest(repo_path=tmp_path, sessions=1)
        assert report.session_count == 0
        assert report.total_prs == 0

    def test_missing_log_file(self, tmp_path):
        report = generate_digest(repo_path=tmp_path)
        assert report.session_count == 0

    def test_custom_log_path(self, tmp_path):
        custom = tmp_path / "custom.md"
        custom.write_text(SINGLE_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, log_path=custom, sessions=1)
        assert report.session_count == 1

    def test_date_range_single_day(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(SINGLE_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=1)
        assert report.date_range == "2026-02-28"

    def test_date_range_multi_day(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=4)
        assert "\u2013" in report.date_range  # en-dash

    def test_executive_summary_populated(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=2)
        assert len(report.executive_summary) > 0
        assert "Session" in report.executive_summary

    def test_json_roundtrip(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=2)
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["session_count"] == report.session_count

    def test_deltas_computed_correctly(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=4)
        # Session 0: 3 modules, 0 tests (first session)
        assert report.sessions[0].modules_added == 3
        assert report.sessions[0].tests_added == 0
        # Session 1: 8-3=5 modules, 50-0=50 tests
        assert report.sessions[1].modules_added == 5
        assert report.sessions[1].tests_added == 50

    def test_counts_consistent(self, tmp_path):
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        report = generate_digest(repo_path=tmp_path, sessions=4)
        computed_tasks = sum(len(s.tasks) for s in report.sessions)
        computed_prs = sum(s.pr_count for s in report.sessions)
        assert report.total_tasks == computed_tasks
        assert report.total_prs == computed_prs

    def test_fallback_to_last_session_when_no_recent(self, tmp_path):
        """If hours filter returns nothing, should fall back to last session."""
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        # These sessions are from 2026-02-27/28, so a 1-hour window now finds nothing
        report = generate_digest(repo_path=tmp_path, hours=1)
        # Should fall back to last session
        assert report.session_count >= 1


# ---------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------


class TestOutputFormats:
    @pytest.fixture
    def report(self, tmp_path) -> DigestReport:
        (tmp_path / "AWAKE_LOG.md").write_text(MULTI_SESSION_LOG)
        return generate_digest(repo_path=tmp_path, sessions=2)

    def test_markdown_sections(self, report):
        md = report.to_markdown()
        assert "# Awake: Nightly Digest" in md
        assert "## TL;DR" in md
        assert "## Overview" in md
        assert "## Session Details" in md
        assert "---" in md

    def test_json_all_fields(self, report):
        parsed = json.loads(report.to_json())
        assert "session_count" in parsed
        assert "date_range" in parsed
        assert "executive_summary" in parsed
        assert "sessions" in parsed
        assert len(parsed["sessions"]) == 2

    def test_text_compact(self, report):
        text = report.to_text()
        lines = text.strip().split("\n")
        assert lines[0] == "AWAKE NIGHTLY DIGEST"
        assert any("Sessions:" in line for line in lines)


# ---------------------------------------------------------------------------
# Integration: real AWAKE_LOG.md
# ---------------------------------------------------------------------------


class TestRealLog:
    @pytest.fixture
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def test_real_log_last_session(self, repo_root):
        log_path = repo_root / "AWAKE_LOG.md"
        if not log_path.exists():
            pytest.skip("AWAKE_LOG.md not found")
        report = generate_digest(repo_path=repo_root, sessions=1)
        assert report.session_count == 1
        assert len(report.executive_summary) > 0

    def test_real_log_last_3_sessions(self, repo_root):
        log_path = repo_root / "AWAKE_LOG.md"
        if not log_path.exists():
            pytest.skip("AWAKE_LOG.md not found")
        report = generate_digest(repo_path=repo_root, sessions=3)
        assert report.session_count == 3
        # All formats should work
        assert isinstance(report.to_markdown(), str)
        assert isinstance(report.to_json(), str)
        assert isinstance(report.to_text(), str)

    def test_real_log_json_valid(self, repo_root):
        log_path = repo_root / "AWAKE_LOG.md"
        if not log_path.exists():
            pytest.skip("AWAKE_LOG.md not found")
        report = generate_digest(repo_path=repo_root, sessions=1)
        parsed = json.loads(report.to_json())
        assert parsed["session_count"] == 1


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_digest_subcommand_exists(self):
        from src.cli import build_parser
        parser = build_parser()
        # Should not raise
        args = parser.parse_args(["digest", "--sessions", "1"])
        assert args.sessions == 1
        assert args.format == "markdown"

    def test_digest_json_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["digest", "--format", "json", "--sessions", "2"])
        assert args.format == "json"
        assert args.sessions == 2

    def test_digest_text_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["digest", "--format", "text"])
        assert args.format == "text"

    def test_digest_hours_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["digest", "--hours", "48"])
        assert args.hours == 48

    def test_digest_write_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["digest", "--write", "--sessions", "1"])
        assert args.write is True

    def test_digest_defaults(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["digest"])
        assert args.hours == 24
        assert args.sessions is None
        assert args.format == "markdown"
        assert args.write is False
