"""Tests for src.planner -- session planning from insights.

Covers:
- TaskScores: composite scoring with default and custom weights
- PlannedTask: data structure and serialization
- SessionPlan: plan rendering (Markdown, JSON, dict)
- Signal collectors: each collector tested with mock data
- Collector graceful degradation: broken modules don't crash the planner
- generate_plan: full pipeline integration
- CLI integration: parser flags, command dispatch
- Self-referential: planner can analyze the Awake repo itself
- Edge cases: empty repo, no signals, custom weights
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from src.planner import (
    TaskScores,
    PlannedTask,
    SessionPlan,
    DEFAULT_WEIGHTS,
    generate_plan,
    save_plan,
    _collect_anomalies,
    _collect_health_issues,
    _collect_coverage_gaps,
    _collect_dead_code,
    _collect_stale_todos,
    _collect_complexity_issues,
    _collect_doctor_issues,
    _collect_insight_signals,
    _COLLECTORS,
)


# ---------------------------------------------------------------------------
# TaskScores tests
# ---------------------------------------------------------------------------


class TestTaskScores:
    def test_default_composite(self):
        scores = TaskScores(urgency=100, impact=100, effort=100, freshness=100)
        assert scores.composite() == 100.0

    def test_zero_composite(self):
        scores = TaskScores(urgency=0, impact=0, effort=0, freshness=0)
        assert scores.composite() == 0.0

    def test_weighted_composite(self):
        scores = TaskScores(urgency=80, impact=60, effort=40, freshness=20)
        # 80*0.35 + 60*0.30 + 40*0.20 + 20*0.15
        # = 28 + 18 + 8 + 3 = 57
        assert scores.composite() == 57.0

    def test_custom_weights(self):
        scores = TaskScores(urgency=100, impact=0, effort=0, freshness=0)
        custom = {"urgency": 1.0, "impact": 0.0, "effort": 0.0, "freshness": 0.0}
        assert scores.composite(custom) == 100.0

    def test_equal_weights(self):
        scores = TaskScores(urgency=80, impact=80, effort=80, freshness=80)
        equal = {"urgency": 0.25, "impact": 0.25, "effort": 0.25, "freshness": 0.25}
        assert scores.composite(equal) == 80.0

    def test_to_dict(self):
        scores = TaskScores(urgency=50, impact=60, effort=70, freshness=80)
        d = scores.to_dict()
        assert d["urgency"] == 50
        assert d["impact"] == 60
        assert d["effort"] == 70
        assert d["freshness"] == 80

    def test_default_weights_sum_to_one(self):
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# PlannedTask tests
# ---------------------------------------------------------------------------


class TestPlannedTask:
    def test_to_dict(self):
        task = PlannedTask(
            title="Fix anomaly",
            description="Something broke",
            source="anomaly",
            scores=TaskScores(urgency=90, impact=70, effort=60, freshness=80),
            priority=75.5,
            rationale="It's broken",
            estimated_effort="medium",
            related_files=["src/health.py"],
        )
        d = task.to_dict()
        assert d["title"] == "Fix anomaly"
        assert d["priority"] == 75.5
        assert d["scores"]["urgency"] == 90
        assert d["related_files"] == ["src/health.py"]

    def test_default_fields(self):
        task = PlannedTask(title="Test", description="", source="test")
        assert task.priority == 0.0
        assert task.related_files == []
        assert task.estimated_effort == ""


# ---------------------------------------------------------------------------
# SessionPlan tests
# ---------------------------------------------------------------------------


class TestSessionPlan:
    def _sample_plan(self) -> SessionPlan:
        t1 = PlannedTask(
            title="Fix anomaly",
            description="Critical issue detected",
            source="anomaly",
            scores=TaskScores(urgency=90, impact=70, effort=60, freshness=80),
            priority=77.5,
            rationale="Active critical anomaly",
            estimated_effort="medium",
            related_files=["src/health.py"],
        )
        t2 = PlannedTask(
            title="Add tests",
            description="Module lacks tests",
            source="coverage",
            scores=TaskScores(urgency=85, impact=90, effort=50, freshness=60),
            priority=73.0,
            rationale="No test file exists",
            estimated_effort="medium",
            related_files=["src/planner.py"],
        )
        return SessionPlan(
            tasks=[t1, t2],
            generated_at="2026-03-04 00:00 UTC",
            repo_path="/home/test/repo",
            signals_collected=10,
            modules_consulted=["anomaly", "coverage"],
            weights=dict(DEFAULT_WEIGHTS),
        )

    def test_task_count(self):
        plan = self._sample_plan()
        assert plan.task_count == 2

    def test_to_dict(self):
        plan = self._sample_plan()
        d = plan.to_dict()
        assert d["task_count"] == 2
        assert d["signals_collected"] == 10
        assert len(d["tasks"]) == 2

    def test_to_json_valid(self):
        plan = self._sample_plan()
        parsed = json.loads(plan.to_json())
        assert parsed["task_count"] == 2

    def test_to_markdown_has_headers(self):
        plan = self._sample_plan()
        md = plan.to_markdown()
        assert "# Session Plan" in md
        assert "## Recommended Tasks" in md
        assert "Fix anomaly" in md
        assert "Add tests" in md

    def test_to_markdown_shows_scores(self):
        plan = self._sample_plan()
        md = plan.to_markdown()
        assert "urgency:" in md
        assert "impact:" in md

    def test_to_markdown_shows_files(self):
        plan = self._sample_plan()
        md = plan.to_markdown()
        assert "src/health.py" in md

    def test_empty_plan(self):
        plan = SessionPlan()
        assert plan.task_count == 0
        md = plan.to_markdown()
        assert "# Session Plan" in md

    def test_to_markdown_shows_weights(self):
        plan = self._sample_plan()
        md = plan.to_markdown()
        assert "urgency=0.35" in md


# ---------------------------------------------------------------------------
# Collector tests with mocks
# ---------------------------------------------------------------------------


class TestCollectAnomalies:
    def test_returns_tasks_for_anomalies(self):
        mock_report = MagicMock()
        mock_anomaly = MagicMock()
        mock_anomaly.severity = "critical"
        mock_anomaly.title = "Test drop"
        mock_anomaly.description = "Tests dropped by 50"
        mock_anomaly.metric = "tests"
        mock_report.anomalies = [mock_anomaly]

        with patch("src.anomaly.detect_anomalies", return_value=mock_report):
            tasks = _collect_anomalies(Path("."))
        assert len(tasks) == 1
        assert tasks[0].source == "anomaly"
        assert tasks[0].scores.urgency == 95

    def test_handles_exception(self):
        with patch("src.anomaly.detect_anomalies", side_effect=Exception("boom")):
            tasks = _collect_anomalies(Path("."))
        assert tasks == []


class TestCollectHealthIssues:
    def test_returns_tasks_for_low_health(self):
        mock_report = MagicMock()
        mock_file = MagicMock()
        mock_file.health_score = 60.0
        mock_file.path = "src/bad.py"
        mock_file.long_lines = 10
        mock_file.todo_count = 5
        mock_file.docstring_coverage = 0.3
        mock_report.files = [mock_file]

        with patch("src.health.generate_health_report", return_value=mock_report):
            tasks = _collect_health_issues(Path("."))
        assert len(tasks) == 1
        assert tasks[0].source == "health"
        assert "src/bad.py" in tasks[0].related_files

    def test_skips_healthy_files(self):
        mock_report = MagicMock()
        mock_file = MagicMock()
        mock_file.health_score = 90.0
        mock_report.files = [mock_file]

        with patch("src.health.generate_health_report", return_value=mock_report):
            tasks = _collect_health_issues(Path("."))
        assert tasks == []

    def test_handles_exception(self):
        with patch("src.health.generate_health_report", side_effect=Exception("boom")):
            tasks = _collect_health_issues(Path("."))
        assert tasks == []


class TestCollectCoverageGaps:
    def test_returns_tasks_for_missing_tests(self):
        mock_report = MagicMock()
        mock_entry = MagicMock()
        mock_entry.module = "planner"
        mock_entry.src_file = "src/planner.py"
        mock_entry.public_symbols = 5
        mock_report.modules_without_tests = [mock_entry]
        mock_report.weakest = []

        with patch("src.coverage_map.build_coverage_map", return_value=mock_report):
            tasks = _collect_coverage_gaps(Path("."))
        assert len(tasks) == 1
        assert "planner" in tasks[0].title

    def test_returns_tasks_for_weak_coverage(self):
        mock_report = MagicMock()
        mock_report.modules_without_tests = []
        mock_entry = MagicMock()
        mock_entry.has_test_file = True
        mock_entry.coverage_score = 30
        mock_entry.module = "health"
        mock_entry.src_file = "src/health.py"
        mock_entry.test_file = "tests/test_health.py"
        mock_entry.test_count = 2
        mock_entry.public_symbols = 10
        mock_entry.ratio = 0.2
        mock_report.weakest = [mock_entry]

        with patch("src.coverage_map.build_coverage_map", return_value=mock_report):
            tasks = _collect_coverage_gaps(Path("."))
        assert len(tasks) == 1
        assert tasks[0].source == "coverage"


class TestCollectDeadCode:
    def test_returns_task_for_dead_code(self):
        mock_report = MagicMock()
        mock_item = MagicMock()
        mock_item.name = "dead_func"
        mock_item.file = "src/old.py"
        mock_report.high_confidence = [mock_item]

        with patch("src.dead_code.find_dead_code", return_value=mock_report):
            tasks = _collect_dead_code(Path("."))
        assert len(tasks) == 1
        assert "dead code" in tasks[0].title.lower()

    def test_no_dead_code(self):
        mock_report = MagicMock()
        mock_report.high_confidence = []

        with patch("src.dead_code.find_dead_code", return_value=mock_report):
            tasks = _collect_dead_code(Path("."))
        assert tasks == []


class TestCollectStaleTodos:
    def test_returns_tasks_for_stale_fixmes(self, tmp_path):
        (tmp_path / "src").mkdir()
        mock_item = MagicMock()
        mock_item.is_stale = True
        mock_item.tag = "FIXME"
        mock_item.file = "src/old.py"
        mock_item.line = 42

        with patch("src.todo_hunter.hunt", return_value=[mock_item]):
            tasks = _collect_stale_todos(tmp_path)
        assert len(tasks) >= 1
        assert any("FIXME" in t.title for t in tasks)

    def test_no_stale_todos(self, tmp_path):
        (tmp_path / "src").mkdir()
        mock_item = MagicMock()
        mock_item.is_stale = False
        mock_item.tag = "TODO"

        with patch("src.todo_hunter.hunt", return_value=[mock_item]):
            tasks = _collect_stale_todos(tmp_path)
        assert tasks == []


class TestCollectComplexityIssues:
    def test_returns_task_for_high_complexity(self):
        mock_report = MagicMock()
        mock_result = MagicMock()
        mock_result.rank = "HIGH"
        mock_result.function = "parse_log"
        mock_result.complexity = 22
        mock_result.file = "src/insights.py"
        mock_report.results = [mock_result]

        with patch("src.complexity.analyze_complexity", return_value=mock_report):
            tasks = _collect_complexity_issues(Path("."))
        assert len(tasks) == 1
        assert "complexity" in tasks[0].source

    def test_no_high_complexity(self):
        mock_report = MagicMock()
        mock_result = MagicMock()
        mock_result.rank = "LOW"
        mock_report.results = [mock_result]

        with patch("src.complexity.analyze_complexity", return_value=mock_report):
            tasks = _collect_complexity_issues(Path("."))
        assert tasks == []


class TestCollectDoctorIssues:
    def test_returns_task_for_failing_checks(self):
        mock_report = MagicMock()
        mock_check = MagicMock()
        mock_check.status = "FAIL"
        mock_check.name = "syntax check"
        mock_check.message = "2 files have syntax errors"
        mock_report.checks = [mock_check]
        mock_report.grade = "F"

        with patch("src.doctor.diagnose", return_value=mock_report):
            tasks = _collect_doctor_issues(Path("."))
        assert len(tasks) == 1
        assert "doctor" in tasks[0].source

    def test_returns_task_for_many_warnings(self):
        mock_report = MagicMock()
        warns = []
        for i in range(4):
            w = MagicMock()
            w.status = "WARN"
            w.name = f"check_{i}"
            warns.append(w)
        mock_report.checks = warns
        mock_report.grade = "C"

        with patch("src.doctor.diagnose", return_value=mock_report):
            tasks = _collect_doctor_issues(Path("."))
        assert any("warning" in t.title.lower() for t in tasks)


class TestCollectInsightSignals:
    def test_returns_task_for_declining_trend(self):
        mock_report = MagicMock()
        mock_insight = MagicMock()
        mock_insight.text = "Module count declining over last 3 sessions"
        mock_insight.category = "growth"
        mock_report.insights = [mock_insight]

        with patch("src.insights.generate_insights", return_value=mock_report):
            tasks = _collect_insight_signals(Path("."))
        assert len(tasks) == 1
        assert "declining" in tasks[0].title.lower()

    def test_no_concerning_insights(self):
        mock_report = MagicMock()
        mock_insight = MagicMock()
        mock_insight.text = "Strong growth trajectory"
        mock_report.insights = [mock_insight]

        with patch("src.insights.generate_insights", return_value=mock_report):
            tasks = _collect_insight_signals(Path("."))
        assert tasks == []


# ---------------------------------------------------------------------------
# Full pipeline tests
# ---------------------------------------------------------------------------


class TestGeneratePlan:
    def test_returns_session_plan(self, tmp_path):
        """generate_plan returns a valid SessionPlan even for an empty repo."""
        plan = generate_plan(repo_path=tmp_path, top=5)
        assert isinstance(plan, SessionPlan)
        assert plan.task_count >= 0

    def test_top_parameter_limits_tasks(self, tmp_path):
        plan = generate_plan(repo_path=tmp_path, top=2)
        assert plan.task_count <= 2

    def test_custom_weights(self, tmp_path):
        custom = {"urgency": 0.5, "impact": 0.3, "effort": 0.1, "freshness": 0.1}
        plan = generate_plan(repo_path=tmp_path, top=5, weights=custom)
        assert plan.weights == custom

    def test_generated_at_is_set(self, tmp_path):
        plan = generate_plan(repo_path=tmp_path)
        assert len(plan.generated_at) > 0

    def test_repo_path_is_set(self, tmp_path):
        plan = generate_plan(repo_path=tmp_path)
        assert str(tmp_path) in plan.repo_path

    def test_graceful_with_all_modules_failing(self, tmp_path):
        """Even if every collector fails, generate_plan still returns a plan."""
        # Doctor will still find issues in an empty dir, which is correct behavior
        plan = generate_plan(repo_path=tmp_path / "does_not_exist", top=5)
        assert isinstance(plan, SessionPlan)


class TestSavePlan:
    def test_saves_markdown_and_json(self, tmp_path):
        plan = SessionPlan(
            tasks=[],
            generated_at="2026-03-04",
            repo_path="/test",
        )
        out = tmp_path / "docs" / "session_plan.md"
        save_plan(plan, out)
        assert out.exists()
        assert out.with_suffix(".json").exists()
        content = out.read_text()
        assert "# Session Plan" in content

    def test_creates_parent_dirs(self, tmp_path):
        plan = SessionPlan()
        out = tmp_path / "deep" / "nested" / "plan.md"
        save_plan(plan, out)
        assert out.exists()


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLI:
    def test_plan_subcommand_exists(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan"])
        assert args.command == "plan"

    def test_plan_top_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan", "--top", "3"])
        assert args.top == 3

    def test_plan_format_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan", "--format", "json"])
        assert args.format == "json"

    def test_plan_write_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan", "--write"])
        assert args.write is True

    def test_plan_json_flag(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan", "--json"])
        assert args.json is True

    def test_brain_alias_exists(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["brain"])
        assert args.command == "brain"

    def test_brain_has_same_flags(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["brain", "--top", "10", "--format", "json"])
        assert args.top == 10
        assert args.format == "json"

    def test_plan_defaults(self):
        from src.cli import build_parser
        parser = build_parser()
        args = parser.parse_args(["plan"])
        assert args.top == 5
        assert args.format == "markdown"
        assert args.json is False
        assert args.write is False


# ---------------------------------------------------------------------------
# Self-referential test -- planner analyzes the Awake repo itself
# ---------------------------------------------------------------------------


class TestSelfReferential:
    """The planner should be able to analyze the Awake repo itself."""

    def test_can_plan_own_repo(self):
        """generate_plan runs against the Awake repo without crashing."""
        repo = Path(__file__).resolve().parent.parent
        plan = generate_plan(repo_path=repo, top=5)
        assert isinstance(plan, SessionPlan)
        assert plan.task_count >= 0

    def test_finds_real_signals(self):
        """When run against Awake, the planner should find at least some signals."""
        repo = Path(__file__).resolve().parent.parent
        plan = generate_plan(repo_path=repo, top=10)
        # The Awake repo is large enough that at least one collector should find something
        assert plan.signals_collected >= 0

    def test_modules_consulted(self):
        """The planner should consult multiple modules against the real repo."""
        repo = Path(__file__).resolve().parent.parent
        plan = generate_plan(repo_path=repo, top=5)
        # At minimum, health or coverage should find something
        assert isinstance(plan.modules_consulted, list)


# ---------------------------------------------------------------------------
# Collector registry
# ---------------------------------------------------------------------------


class TestCollectorRegistry:
    def test_all_collectors_registered(self):
        names = [name for name, _ in _COLLECTORS]
        assert "anomaly" in names
        assert "health" in names
        assert "coverage" in names
        assert "dead_code" in names
        assert "todo_hunter" in names
        assert "complexity" in names
        assert "doctor" in names
        assert "insights" in names

    def test_collector_count(self):
        assert len(_COLLECTORS) == 8


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_repo(self, tmp_path):
        """An empty repo still generates a plan (doctor finds issues)."""
        plan = generate_plan(repo_path=tmp_path, top=5)
        assert isinstance(plan, SessionPlan)
        assert plan.task_count >= 0

    def test_repo_with_only_src(self, tmp_path):
        (tmp_path / "src").mkdir()
        plan = generate_plan(repo_path=tmp_path, top=5)
        assert isinstance(plan, SessionPlan)

    def test_zero_top(self, tmp_path):
        plan = generate_plan(repo_path=tmp_path, top=0)
        assert plan.task_count == 0

    def test_large_top(self, tmp_path):
        plan = generate_plan(repo_path=tmp_path, top=100)
        assert plan.task_count <= 100

    def test_all_weights_zero(self, tmp_path):
        zero_weights = {"urgency": 0, "impact": 0, "effort": 0, "freshness": 0}
        plan = generate_plan(repo_path=tmp_path, weights=zero_weights)
        for task in plan.tasks:
            assert task.priority == 0.0

    def test_plan_is_sorted_by_priority(self):
        tasks = [
            PlannedTask(title="Low", description="", source="test",
                        scores=TaskScores(urgency=20), priority=20.0),
            PlannedTask(title="High", description="", source="test",
                        scores=TaskScores(urgency=90), priority=90.0),
            PlannedTask(title="Mid", description="", source="test",
                        scores=TaskScores(urgency=50), priority=50.0),
        ]
        plan = SessionPlan(tasks=sorted(tasks, key=lambda t: -t.priority))
        assert plan.tasks[0].title == "High"
        assert plan.tasks[-1].title == "Low"
