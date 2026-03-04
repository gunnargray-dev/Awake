"""Session planner -- AI plans its own next session.

Pulls signals from every Awake analysis module and auto-prioritises
what the next session should work on.  This is the final backlog item
on the Awake roadmap: the system that closes the autonomous loop.

Data sources
------------
- ``src/insights.py``      -- session velocity, streaks, growth trends
- ``src/anomaly.py``       -- active anomalies / alerts
- ``src/health.py``        -- files with low health scores
- ``src/coverage_map.py``  -- modules missing test coverage
- ``src/dead_code.py``     -- dead code that should be cleaned up
- ``src/todo_hunter.py``   -- stale TODOs that need addressing
- ``src/complexity.py``    -- high-complexity modules needing refactor
- ``src/doctor.py``        -- failing doctor checks

Scoring dimensions (each 0-100)
--------------------------------
- **Urgency**   -- Is this blocking or degrading quality?
- **Impact**    -- How much does this improve the repo?
- **Effort**    -- How much work? (inverted: simple = high score)
- **Freshness** -- When was this area last touched? (stale = high score)

Composite = weighted average (configurable).

Public API
----------
- ``PlannedTask``        -- a single recommended task
- ``SessionPlan``        -- ranked list of tasks + metadata
- ``generate_plan()``    -- main entry point
- ``DEFAULT_WEIGHTS``    -- default dimension weights

CLI
---
    awake plan [--top N] [--format {markdown,json}] [--write] [--repo PATH]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "urgency": 0.35,
    "impact": 0.30,
    "effort": 0.20,
    "freshness": 0.15,
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TaskScores:
    """Per-dimension scores for a planned task."""

    urgency: float = 0.0      # 0-100
    impact: float = 0.0       # 0-100
    effort: float = 0.0       # 0-100 (inverted: easy = high)
    freshness: float = 0.0    # 0-100 (stale = high)

    def composite(self, weights: Optional[dict] = None) -> float:
        """Weighted average across all dimensions."""
        w = weights or DEFAULT_WEIGHTS
        total = (
            self.urgency * w.get("urgency", 0.35)
            + self.impact * w.get("impact", 0.30)
            + self.effort * w.get("effort", 0.20)
            + self.freshness * w.get("freshness", 0.15)
        )
        return round(total, 1)

    def to_dict(self) -> dict:
        return {
            "urgency": self.urgency,
            "impact": self.impact,
            "effort": self.effort,
            "freshness": self.freshness,
        }


@dataclass
class PlannedTask:
    """A single recommended task for the next session."""

    title: str
    description: str
    source: str                # module that generated this task
    scores: TaskScores = field(default_factory=TaskScores)
    priority: float = 0.0     # composite score
    rationale: str = ""       # "why" explanation
    estimated_effort: str = "" # "small", "medium", "large"
    related_files: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "priority": self.priority,
            "scores": self.scores.to_dict(),
            "rationale": self.rationale,
            "estimated_effort": self.estimated_effort,
            "related_files": self.related_files,
        }


@dataclass
class SessionPlan:
    """The complete plan for the next session."""

    tasks: list[PlannedTask] = field(default_factory=list)
    generated_at: str = ""
    repo_path: str = ""
    signals_collected: int = 0
    modules_consulted: list[str] = field(default_factory=list)
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))

    @property
    def task_count(self) -> int:
        return len(self.tasks)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "repo_path": self.repo_path,
            "task_count": self.task_count,
            "signals_collected": self.signals_collected,
            "modules_consulted": self.modules_consulted,
            "weights": self.weights,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Session Plan",
            "",
            f"*Generated: {self.generated_at}*  ",
            f"*Repo: `{self.repo_path}`*  ",
            f"*Signals collected: {self.signals_collected} from {len(self.modules_consulted)} modules*",
            "",
            "## Recommended Tasks",
            "",
        ]

        for i, task in enumerate(self.tasks, 1):
            lines.append(f"### {i}. {task.title}")
            lines.append("")
            lines.append(f"**Priority:** {task.priority}/100  "
                         f"**Source:** {task.source}  "
                         f"**Effort:** {task.estimated_effort}")
            lines.append("")
            lines.append(task.description)
            lines.append("")
            lines.append(f"**Why:** {task.rationale}")
            lines.append("")
            lines.append(
                f"*Scores -- urgency: {task.scores.urgency:.0f}, "
                f"impact: {task.scores.impact:.0f}, "
                f"effort: {task.scores.effort:.0f}, "
                f"freshness: {task.scores.freshness:.0f}*"
            )
            if task.related_files:
                files = ", ".join(f"`{f}`" for f in task.related_files[:5])
                lines.append(f"*Files: {files}*")
            lines.append("")

        lines.append("---")
        lines.append("")
        lines.append(
            f"*Plan generated by `src/planner.py` — "
            f"weights: urgency={self.weights.get('urgency', 0.35)}, "
            f"impact={self.weights.get('impact', 0.30)}, "
            f"effort={self.weights.get('effort', 0.20)}, "
            f"freshness={self.weights.get('freshness', 0.15)}*"
        )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Signal collectors -- each returns a list of PlannedTask candidates
# ---------------------------------------------------------------------------


def _collect_anomalies(repo_path: Path) -> list[PlannedTask]:
    """Pull active anomalies from the anomaly detector."""
    try:
        from src.anomaly import detect_anomalies
        report = detect_anomalies(repo_path=repo_path)
    except Exception:
        return []

    tasks: list[PlannedTask] = []
    for anomaly in report.anomalies:
        severity_urgency = {"critical": 95, "warning": 70, "info": 40}.get(
            anomaly.severity, 50
        )
        tasks.append(PlannedTask(
            title=f"Fix anomaly: {anomaly.title}",
            description=anomaly.description,
            source="anomaly",
            scores=TaskScores(
                urgency=severity_urgency,
                impact=70,
                effort=60,
                freshness=80,
            ),
            rationale=f"Active {anomaly.severity} anomaly in {anomaly.metric}",
            estimated_effort="medium",
            related_files=[],
        ))
    return tasks


def _collect_health_issues(repo_path: Path) -> list[PlannedTask]:
    """Find files with low health scores."""
    try:
        from src.health import generate_health_report
        report = generate_health_report(repo_path=repo_path)
    except Exception:
        return []

    tasks: list[PlannedTask] = []
    for fh in report.files:
        if fh.health_score < 75:
            tasks.append(PlannedTask(
                title=f"Improve health of {fh.path}",
                description=(
                    f"Health score {fh.health_score}/100. "
                    f"Issues: {fh.long_lines} long lines, "
                    f"{fh.todo_count} TODOs, "
                    f"{fh.docstring_coverage:.0%} docstring coverage."
                ),
                source="health",
                scores=TaskScores(
                    urgency=max(0, 80 - fh.health_score),
                    impact=max(0, 90 - fh.health_score),
                    effort=80,  # health fixes are usually quick
                    freshness=50,
                ),
                rationale=f"File health is {fh.health_score}/100, below threshold of 75",
                estimated_effort="small",
                related_files=[fh.path],
            ))
    return tasks


def _collect_coverage_gaps(repo_path: Path) -> list[PlannedTask]:
    """Find modules with weak test coverage."""
    try:
        from src.coverage_map import build_coverage_map
        report = build_coverage_map(repo_path=repo_path)
    except Exception:
        return []

    tasks: list[PlannedTask] = []

    # Missing test files are highest priority
    for entry in report.modules_without_tests:
        tasks.append(PlannedTask(
            title=f"Add tests for {entry.module}",
            description=f"Module `{entry.src_file}` has {entry.public_symbols} public symbols but no test file.",
            source="coverage",
            scores=TaskScores(
                urgency=85,
                impact=90,
                effort=50,
                freshness=60,
            ),
            rationale=f"No test file exists for {entry.module} ({entry.public_symbols} public symbols)",
            estimated_effort="medium",
            related_files=[entry.src_file],
        ))

    # Weak coverage (has tests but low ratio)
    for entry in report.weakest:
        if entry.has_test_file and entry.coverage_score < 50:
            tasks.append(PlannedTask(
                title=f"Improve test coverage for {entry.module}",
                description=(
                    f"Coverage score {entry.coverage_score}/100 "
                    f"({entry.test_count} tests / {entry.public_symbols} symbols, "
                    f"ratio {entry.ratio:.2f})."
                ),
                source="coverage",
                scores=TaskScores(
                    urgency=60,
                    impact=80,
                    effort=55,
                    freshness=50,
                ),
                rationale=f"Test coverage ratio is {entry.ratio:.2f}, well below 1.0",
                estimated_effort="medium",
                related_files=[entry.src_file, entry.test_file],
            ))

    return tasks


def _collect_dead_code(repo_path: Path) -> list[PlannedTask]:
    """Find dead code candidates."""
    try:
        from src.dead_code import find_dead_code
        report = find_dead_code(repo_path=repo_path)
    except Exception:
        return []

    if not report.high_confidence:
        return []

    # Group by file for a single cleanup task
    files = sorted({item.file for item in report.high_confidence})
    items_desc = ", ".join(
        f"`{item.name}`" for item in report.high_confidence[:5]
    )
    extra = len(report.high_confidence) - 5
    if extra > 0:
        items_desc += f" and {extra} more"

    return [PlannedTask(
        title="Clean up dead code",
        description=(
            f"{len(report.high_confidence)} high-confidence dead code candidates: "
            f"{items_desc}."
        ),
        source="dead_code",
        scores=TaskScores(
            urgency=30,
            impact=50,
            effort=85,  # dead code removal is usually easy
            freshness=60,
        ),
        rationale=f"{len(report.high_confidence)} unused symbols found with high confidence",
        estimated_effort="small",
        related_files=files[:5],
    )]


def _collect_stale_todos(repo_path: Path) -> list[PlannedTask]:
    """Find stale TODO/FIXME annotations."""
    try:
        from src.todo_hunter import hunt
        src_path = repo_path / "src"
        if not src_path.exists():
            return []
        items = hunt(src_path=src_path, current_session=999, threshold=2)
    except Exception:
        return []

    stale = [i for i in items if i.is_stale]
    if not stale:
        return []

    fixmes = [i for i in stale if i.tag in ("FIXME", "HACK")]
    todos = [i for i in stale if i.tag == "TODO"]
    files = sorted({i.file for i in stale})

    tasks: list[PlannedTask] = []

    if fixmes:
        desc_items = ", ".join(f"`{i.file}:{i.line}`" for i in fixmes[:3])
        tasks.append(PlannedTask(
            title=f"Resolve {len(fixmes)} stale FIXME/HACK annotations",
            description=f"Stale FIXME/HACK items at: {desc_items}.",
            source="todo_hunter",
            scores=TaskScores(
                urgency=75,
                impact=60,
                effort=65,
                freshness=90,
            ),
            rationale=f"{len(fixmes)} FIXME/HACK annotations have been stale for 2+ sessions",
            estimated_effort="small",
            related_files=[i.file for i in fixmes[:5]],
        ))

    if todos:
        desc_items = ", ".join(f"`{i.file}:{i.line}`" for i in todos[:3])
        tasks.append(PlannedTask(
            title=f"Address {len(todos)} stale TODO items",
            description=f"Stale TODO items at: {desc_items}.",
            source="todo_hunter",
            scores=TaskScores(
                urgency=50,
                impact=45,
                effort=60,
                freshness=85,
            ),
            rationale=f"{len(todos)} TODO annotations have been sitting for 2+ sessions",
            estimated_effort="small",
            related_files=[i.file for i in todos[:5]],
        ))

    return tasks


def _collect_complexity_issues(repo_path: Path) -> list[PlannedTask]:
    """Find high-complexity functions that need refactoring."""
    try:
        from src.complexity import analyze_complexity
        report = analyze_complexity(repo_path=repo_path)
    except Exception:
        return []

    high = [r for r in report.results if r.rank == "HIGH"]
    if not high:
        return []

    items_desc = ", ".join(f"`{r.function}` ({r.complexity})" for r in high[:3])
    extra = len(high) - 3
    if extra > 0:
        items_desc += f" and {extra} more"
    files = sorted({r.file for r in high})

    return [PlannedTask(
        title=f"Refactor {len(high)} high-complexity functions",
        description=f"Functions with complexity >= 15: {items_desc}.",
        source="complexity",
        scores=TaskScores(
            urgency=45,
            impact=65,
            effort=40,  # refactoring is harder
            freshness=50,
        ),
        rationale=f"{len(high)} functions exceed complexity threshold of 15",
        estimated_effort="large",
        related_files=files[:5],
    )]


def _collect_doctor_issues(repo_path: Path) -> list[PlannedTask]:
    """Find failing doctor checks."""
    try:
        from src.doctor import diagnose, STATUS_FAIL, STATUS_WARN
        report = diagnose(repo_root=repo_path)
    except Exception:
        return []

    tasks: list[PlannedTask] = []

    failing = [c for c in report.checks if c.status == "FAIL"]
    if failing:
        descs = "; ".join(f"{c.name}: {c.message}" for c in failing[:3])
        tasks.append(PlannedTask(
            title=f"Fix {len(failing)} failing doctor checks",
            description=f"Failing checks: {descs}.",
            source="doctor",
            scores=TaskScores(
                urgency=90,
                impact=75,
                effort=70,
                freshness=70,
            ),
            rationale=f"{len(failing)} doctor checks are FAIL — repo grade is {report.grade}",
            estimated_effort="medium",
        ))

    warnings = [c for c in report.checks if c.status == "WARN"]
    if len(warnings) >= 3:
        descs = "; ".join(f"{c.name}" for c in warnings[:4])
        tasks.append(PlannedTask(
            title=f"Address {len(warnings)} doctor warnings",
            description=f"Warning checks: {descs}.",
            source="doctor",
            scores=TaskScores(
                urgency=40,
                impact=50,
                effort=75,
                freshness=60,
            ),
            rationale=f"{len(warnings)} doctor warnings contribute to grade {report.grade}",
            estimated_effort="small",
        ))

    return tasks


def _collect_insight_signals(repo_path: Path) -> list[PlannedTask]:
    """Pull growth and velocity signals from the insights engine."""
    try:
        from src.insights import generate_insights
        report = generate_insights(repo_path=repo_path)
    except Exception:
        return []

    tasks: list[PlannedTask] = []

    # Look for declining velocity or concerning insights
    for insight in report.insights:
        text_lower = insight.text.lower()
        if any(w in text_lower for w in ("declining", "drop", "decrease", "slowing")):
            tasks.append(PlannedTask(
                title=f"Address declining trend: {insight.category}",
                description=insight.text,
                source="insights",
                scores=TaskScores(
                    urgency=60,
                    impact=55,
                    effort=50,
                    freshness=70,
                ),
                rationale=f"Insights engine flagged a declining trend in {insight.category}",
                estimated_effort="medium",
            ))

    return tasks


# ---------------------------------------------------------------------------
# Collector registry
# ---------------------------------------------------------------------------

_COLLECTORS = [
    ("anomaly", _collect_anomalies),
    ("health", _collect_health_issues),
    ("coverage", _collect_coverage_gaps),
    ("dead_code", _collect_dead_code),
    ("todo_hunter", _collect_stale_todos),
    ("complexity", _collect_complexity_issues),
    ("doctor", _collect_doctor_issues),
    ("insights", _collect_insight_signals),
]


# ---------------------------------------------------------------------------
# Plan generation
# ---------------------------------------------------------------------------


def generate_plan(
    repo_path: Optional[Path] = None,
    top: int = 5,
    weights: Optional[dict] = None,
) -> SessionPlan:
    """Generate a prioritised session plan from all available signals.

    Args:
        repo_path: Root of the repo to analyse. Defaults to CWD.
        top: Maximum number of tasks to recommend.
        weights: Custom dimension weights (urgency, impact, effort, freshness).

    Returns:
        SessionPlan with ranked tasks and metadata.
    """
    repo = Path(repo_path) if repo_path else Path.cwd()
    w = weights or dict(DEFAULT_WEIGHTS)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    all_candidates: list[PlannedTask] = []
    modules_consulted: list[str] = []

    for module_name, collector_fn in _COLLECTORS:
        try:
            candidates = collector_fn(repo)
            if candidates:
                all_candidates.extend(candidates)
                modules_consulted.append(module_name)
        except Exception:
            # Graceful degradation: skip broken modules
            continue

    # Score all candidates
    for task in all_candidates:
        task.priority = task.scores.composite(w)

    # Sort by priority descending, take top N
    all_candidates.sort(key=lambda t: -t.priority)
    top_tasks = all_candidates[:top]

    return SessionPlan(
        tasks=top_tasks,
        generated_at=now,
        repo_path=str(repo),
        signals_collected=len(all_candidates),
        modules_consulted=modules_consulted,
        weights=w,
    )


def save_plan(plan: SessionPlan, output_path: Path) -> None:
    """Write the session plan as Markdown + JSON sidecar."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(plan.to_markdown(), encoding="utf-8")
    json_path = output_path.with_suffix(".json")
    json_path.write_text(plan.to_json(), encoding="utf-8")
