"""anomaly_alerts.py — Detect unusual patterns in Awake session metrics.

This module is a thin alerting layer on top of the existing `insights` parsing
logic.

The goal is not to replace `awake insights` (which produces narrative insights),
but to provide deterministic, machine-readable anomaly detection suitable for:

- CI checks ("did tests drop unexpectedly?")
- notifications ("something weird happened last night")
- dashboards ("flag sessions worth reviewing")

Public API
----------
detect_anomalies(repo_path, log_path=None, config=None) -> list[Anomaly]
render_anomalies_markdown(anomalies, summary) -> str

Design notes
------------
- Uses only stdlib.
- Reuses the session parsing logic in `src.insights` to avoid double parsing.
- Focuses on *deltas* (tests added this session, modules added this session)
  rather than cumulative values.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from . import insights


@dataclass
class Anomaly:
    """A single detected anomaly."""

    kind: str
    severity: str  # "low" | "medium" | "high"
    session: int
    title: str
    details: str

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict representation."""
        return asdict(self)


@dataclass
class AnomalySummary:
    """High-level summary stats for an anomaly run."""

    sessions_analyzed: int
    anomalies_found: int

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict representation."""
        return asdict(self)


def detect_anomalies(
    repo_path: str | Path,
    log_path: Optional[str | Path] = None,
    config: Optional[dict] = None,
) -> tuple[AnomalySummary, list[Anomaly]]:
    """Detect anomalies in session-to-session metrics.

    Args:
        repo_path: Path to the repo root.
        log_path: Optional explicit path to AWAKE_LOG.md.
        config: Optional configuration dict.

    Returns:
        (summary, anomalies) tuple.

    Config keys:
        max_zero_delta_sessions: int
            If >= this many most-recent sessions have *both* tests_added=0 and
            modules_added=0, flag as a high-severity anomaly (likely missing stats
            logging).
        low_test_delta_threshold: int
            If a session adds fewer tests than this threshold while adding modules,
            flag as a medium anomaly.
        min_tests_per_module: float
            If tests_added/modules_added < this ratio, flag as medium.
    """
    cfg = {
        "max_zero_delta_sessions": 3,
        "low_test_delta_threshold": 5,
        "min_tests_per_module": 1.0,
    }
    if config:
        cfg.update(config)

    repo = Path(repo_path)
    log_file = Path(log_path) if log_path else (repo / "AWAKE_LOG.md")
    if not log_file.exists():
        return AnomalySummary(sessions_analyzed=0, anomalies_found=1), [
            Anomaly(
                kind="missing_log",
                severity="high",
                session=0,
                title="AWAKE_LOG.md not found",
                details=f"Expected log file at: {log_file}",
            )
        ]

    text = log_file.read_text(encoding="utf-8")
    records = insights._parse_sessions(text)
    if not records:
        return AnomalySummary(sessions_analyzed=0, anomalies_found=1), [
            Anomaly(
                kind="parse_failure",
                severity="high",
                session=0,
                title="Could not parse any session records from AWAKE_LOG.md",
                details="The log format may have changed or the file is empty.",
            )
        ]

    per_session_tests = insights._compute_per_session_tests(records)
    per_session_modules = insights._compute_per_session_modules(records)

    anomalies: list[Anomaly] = []

    # --- Anomaly 1: recent sessions with missing per-session stats deltas ---
    # A common failure mode is logging only small "New tests" rows rather than
    # updating cumulative totals; the insights module uses cumulative totals.
    sorted_sessions = sorted(set(per_session_tests.keys()) | set(per_session_modules.keys()))
    if sorted_sessions:
        recent = sorted_sessions[-cfg["max_zero_delta_sessions"]:]
        zero_delta = [s for s in recent if per_session_tests.get(s, 0) == 0 and per_session_modules.get(s, 0) == 0]
        if len(zero_delta) >= cfg["max_zero_delta_sessions"]:
            anomalies.append(Anomaly(
                kind="missing_cumulative_stats",
                severity="high",
                session=zero_delta[-1],
                title=(
                    f"Last {cfg['max_zero_delta_sessions']} sessions show 0 tests added and 0 modules added"
                ),
                details=(
                    "The insights parser computes per-session deltas from cumulative totals. "
                    "If recent sessions only log '+N' values (or omit cumulative totals), "
                    "the delta will appear as 0. Consider recording cumulative module/test totals "
                    "in each session's Stats table to keep trend analytics accurate."
                ),
            ))

    # --- Anomaly 2: modules added without corresponding tests ---
    for s in sorted_sessions:
        m = per_session_modules.get(s, 0)
        t = per_session_tests.get(s, 0)
        if m <= 0:
            continue
        if t < cfg["low_test_delta_threshold"]:
            anomalies.append(Anomaly(
                kind="low_tests_for_modules",
                severity="medium",
                session=s,
                title=f"Session {s} added {m} module(s) but only {t} test(s)",
                details=(
                    "This may be valid (docs-only modules, refactors), but it can also indicate "
                    "a slip in the 'tests-first' discipline."
                ),
            ))
        if m > 0:
            ratio = (t / m) if m else 0.0
            if ratio < cfg["min_tests_per_module"]:
                anomalies.append(Anomaly(
                    kind="low_test_ratio",
                    severity="low",
                    session=s,
                    title=f"Session {s} test/module delta ratio was {ratio:.2f}",
                    details=(
                        f"Tests added: {t}. Modules added: {m}. "
                        f"Threshold: {cfg['min_tests_per_module']:.2f}."
                    ),
                ))

    summary = AnomalySummary(sessions_analyzed=len(records), anomalies_found=len(anomalies))
    return summary, anomalies


def render_anomalies_markdown(summary: AnomalySummary, anomalies: list[Anomaly]) -> str:
    """Render anomalies as a short Markdown report."""
    lines: list[str] = []
    lines.append("# Awake: Anomaly Alerts")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Sessions analyzed | {summary.sessions_analyzed} |")
    lines.append(f"| Anomalies found | {summary.anomalies_found} |")
    lines.append("")

    if not anomalies:
        lines.append("No anomalies detected.")
        lines.append("")
        return "\n".join(lines)

    lines.append("## Anomalies")
    lines.append("")
    for a in anomalies:
        lines.append(f"### [{a.severity.upper()}] {a.title}")
        lines.append("")
        lines.append(f"- Kind: `{a.kind}`")
        lines.append(f"- Session: {a.session}")
        lines.append("")
        lines.append(a.details)
        lines.append("")

    return "\n".join(lines)
