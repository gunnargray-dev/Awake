"""Unified CLI entry point for Awake.

Provides a single ``awake`` command that ties together all analysis
modules into a coherent developer experience.  Every subcommand corresponds
to one (or more) modules in ``src/``.

This file is a thin dispatcher -- all command implementations live in
``src/commands/``:

  src/commands/analysis.py  -- health, complexity, coupling, deadcode, security,
                               coveragemap, blame, maturity
  src/commands/meta.py      -- stats, changelog, story, reflect, evolve, status,
                               session_score, timeline, replay, compare, diff,
                               diff_sessions, insights
  src/commands/tools.py     -- doctor, todos, benchmark, gitstats, badges, audit,
                               predict, teach, dna, report, export, coverage,
                               score, test_quality, refactor, commits, semver,
                               modules, trends, plan (brain), triage, depgraph, arch
  src/commands/infra.py     -- dashboard, init, deps, config, plugins, openapi, run
  src/commands/tools_docstrings.py -- docstrings

Subcommands
-----------
awake health      -- Run code health analysis across src/
awake stats       -- Show repo stats (commits, PRs, lines changed)
awake diff        -- Visualise the last session's git changes
awake changelog   -- Render CHANGELOG.md from git history
awake coverage    -- Show test coverage trend
awake score       -- Score the most recent PR
awake arch        -- Generate / refresh docs/ARCHITECTURE.md
awake refactor    -- Identify refactor candidates in src/
awake run         -- Run the full end-of-session pipeline
awake depgraph    -- Visualise module dependency graph
awake todos       -- Hunt stale TODO/FIXME annotations
awake doctor      -- Run full repo health diagnostic
awake timeline    -- ASCII visual timeline of all sessions
awake coupling    -- Module coupling analyzer (Ca, Ce, instability)
awake complexity  -- Cyclomatic complexity tracker
awake export      -- Export any analysis to JSON/Markdown/HTML
awake config      -- Show or write awake.toml config
awake compare     -- Diff two sessions side-by-side
awake dashboard   -- Launch live React dashboard (web server)
awake deps        -- Check Python dependency freshness via PyPI
awake modules     -- Module interconnection visualizer (Mermaid/ASCII)
awake trends      -- Historical trend data for the React dashboard
awake commits     -- Smart commit message quality analyzer
awake diff-sessions -- Compare any two sessions with rich delta analysis
awake test-quality -- Grade tests by assertion density and edge coverage
awake report      -- Generate executive HTML report combining all analyses
awake openapi     -- Generate OpenAPI 3.1 spec from all API endpoints
awake plugins     -- Manage plugin/hook registry from awake.toml
awake changelog --release -- Generate polished GitHub Releases notes
awake blame       -- Human vs AI contribution attribution (git blame)
awake deadcode    -- Dead code detector: unused functions/imports
awake security    -- Security audit: common Python anti-patterns
awake coveragemap -- Test coverage heat map ranked by weakness
awake docstrings  -- Auto-generate missing docstrings for undocumented functions

Usage
-----
    python -m awake.cli <command> [options]
    # or after ``pip install -e .``
    awake <command> [options]
"""

from __future__ import annotations

import argparse
import sys

# ---------------------------------------------------------------------------
# Command imports -- pulled from domain-specific submodules
# ---------------------------------------------------------------------------

from src.commands import (
    _repo,
    _print_header,
    _print_ok,
    _print_warn,
    _print_info,
    REPO_ROOT,
    cmd_automerge,
)

from src.commands.tools_docstrings import cmd_docstrings

from src.commands.analysis import (
    cmd_health,
    cmd_complexity,
    cmd_coupling,
    cmd_deadcode,
    cmd_security,
    cmd_coveragemap,
    cmd_blame,
    cmd_maturity,
)
from src.commands.analysis_module_risk import cmd_module_risk
from src.commands.analysis_anomalies import cmd_anomalies

from src.commands.meta import (
    cmd_stats,
    cmd_changelog,
    cmd_story,
    cmd_reflect,
    cmd_evolve,
    cmd_status,
    cmd_session_score,
    cmd_timeline,
    cmd_replay,
    cmd_compare,
    cmd_diff,
    cmd_diff_sessions,
    cmd_insights,
)

from src.commands.tools import (
    cmd_doctor,
    cmd_todos,
    cmd_benchmark,
    cmd_gitstats,
    cmd_badges,
    cmd_audit,
    cmd_predict,
    cmd_teach,
    cmd_dna,
    cmd_report,
    cmd_export,
    cmd_coverage,
    cmd_score,
    cmd_test_quality,
    cmd_refactor,
    cmd_commits,
    cmd_semver,
    cmd_modules,
    cmd_trends,
    cmd_plan,
    cmd_triage,
    cmd_depgraph,
    cmd_arch,
)

from src.commands.infra import (
    cmd_dashboard,
    cmd_init,
    cmd_deps,
    cmd_config,
    cmd_plugins,
    cmd_openapi,
    cmd_run,
)

# Keep backwards-compatible re-exports so any code that imported these
# symbols from src.cli continues to work.
__all__ = [
    "cmd_health", "cmd_complexity", "cmd_coupling", "cmd_deadcode",
    "cmd_security", "cmd_coveragemap", "cmd_blame", "cmd_maturity",
    "cmd_stats", "cmd_changelog", "cmd_story", "cmd_reflect", "cmd_evolve",
    "cmd_status", "cmd_session_score", "cmd_timeline", "cmd_replay",
    "cmd_compare", "cmd_diff", "cmd_diff_sessions", "cmd_insights",
    "cmd_doctor", "cmd_todos", "cmd_benchmark", "cmd_gitstats", "cmd_badges",
    "cmd_audit", "cmd_predict", "cmd_teach", "cmd_dna", "cmd_report",
    "cmd_export", "cmd_coverage", "cmd_score", "cmd_test_quality",
    "cmd_refactor", "cmd_commits", "cmd_semver", "cmd_modules", "cmd_trends",
    "cmd_plan", "cmd_triage", "cmd_depgraph", "cmd_arch",
    "cmd_anomalies",
    "cmd_dashboard", "cmd_init", "cmd_deps", "cmd_config", "cmd_plugins",
    "cmd_openapi", "cmd_automerge", "cmd_docstrings", "cmd_run",
    "build_parser", "main",
]


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="awake",
        description="Awake -- autonomous repo intelligence",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Common flag helpers
    def _add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="Output raw JSON")

    def _add_repo(p: argparse.ArgumentParser) -> None:
        p.add_argument("--repo", default=None, help="Path to repo root")

    def _add_write(p: argparse.ArgumentParser) -> None:
        p.add_argument("--write", action="store_true", help="Write output to file")

    # ------------------------------------------------------------------
    # Analysis commands
    # ------------------------------------------------------------------

    # health
    p_health = sub.add_parser("health", help="Code health analysis")
    _add_json(p_health)
    _add_repo(p_health)
    p_health.set_defaults(func=cmd_health)

    # complexity
    p_complexity = sub.add_parser("complexity", help="Cyclomatic complexity")
    _add_write(p_complexity)
    _add_json(p_complexity)
    _add_repo(p_complexity)
    p_complexity.set_defaults(func=cmd_complexity)

    # coupling
    p_coupling = sub.add_parser("coupling", help="Module coupling analysis")
    _add_write(p_coupling)
    _add_json(p_coupling)
    _add_repo(p_coupling)
    p_coupling.set_defaults(func=cmd_coupling)

    # deadcode
    p_dc = sub.add_parser("deadcode", help="Dead code detector")
    _add_json(p_dc)
    _add_repo(p_dc)
    p_dc.set_defaults(func=cmd_deadcode)

    # security
    p_sec = sub.add_parser("security", help="Security audit")
    _add_json(p_sec)
    _add_repo(p_sec)
    p_sec.set_defaults(func=cmd_security)

    # coveragemap
    p_cmap = sub.add_parser("coveragemap", help="Coverage heat map")
    _add_json(p_cmap)
    _add_repo(p_cmap)
    p_cmap.set_defaults(func=cmd_coveragemap)

    # blame
    p_blame = sub.add_parser("blame", help="Human vs AI attribution")
    _add_json(p_blame)
    _add_repo(p_blame)
    p_blame.set_defaults(func=cmd_blame)

    # maturity
    p_mat = sub.add_parser("maturity", help="Module maturity scores")
    _add_write(p_mat)
    _add_json(p_mat)
    _add_repo(p_mat)
    p_mat.set_defaults(func=cmd_maturity)

    # ------------------------------------------------------------------
    # Meta commands
    # ------------------------------------------------------------------

    # stats
    p_stats = sub.add_parser("stats", help="Repository statistics")
    _add_json(p_stats)
    _add_repo(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    # changelog
    p_cl = sub.add_parser("changelog", help="Render CHANGELOG.md")
    p_cl.add_argument("--write", action="store_true", help="Write CHANGELOG.md")
    p_cl.add_argument("--release", action="store_true", help="Generate release notes")
    p_cl.add_argument("--since", default=None, help="Start tag/commit (default: auto)")
    p_cl.add_argument("--until", default=None, help="End tag/commit (default: HEAD)")
    p_cl.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_cl)
    p_cl.set_defaults(func=cmd_changelog)

    # story
    p_story = sub.add_parser("story", help="Repo story generator")
    _add_json(p_story)
    _add_repo(p_story)
    p_story.set_defaults(func=cmd_story)

    # reflect
    p_reflect = sub.add_parser("reflect", help="Self-analysis of past sessions")
    _add_write(p_reflect)
    _add_json(p_reflect)
    _add_repo(p_reflect)
    p_reflect.set_defaults(func=cmd_reflect)

    # evolve
    p_evolve = sub.add_parser("evolve", help="Gap analysis and next evolution plan")
    _add_write(p_evolve)
    _add_json(p_evolve)
    _add_repo(p_evolve)
    p_evolve.set_defaults(func=cmd_evolve)

    # status
    p_status = sub.add_parser("status", help="One-command repo health snapshot")
    _add_json(p_status)
    _add_repo(p_status)
    p_status.set_defaults(func=cmd_status)

    # session-score
    p_sess = sub.add_parser("session-score", help="Score a session")
    p_sess.add_argument("--session", type=int, default=1)
    _add_json(p_sess)
    _add_repo(p_sess)
    p_sess.set_defaults(func=cmd_session_score)

    # timeline
    p_tl = sub.add_parser("timeline", help="ASCII visual timeline of all sessions")
    _add_json(p_tl)
    _add_repo(p_tl)
    p_tl.set_defaults(func=cmd_timeline)

    # replay
    p_rep = sub.add_parser("replay", help="Reconstruct a past session")
    p_rep.add_argument("--session", type=int, required=True)
    _add_json(p_rep)
    _add_repo(p_rep)
    p_rep.set_defaults(func=cmd_replay)

    # compare
    p_cmp = sub.add_parser("compare", help="Compare two sessions")
    p_cmp.add_argument("--a", type=int, required=True)
    p_cmp.add_argument("--b", type=int, required=True)
    _add_json(p_cmp)
    _add_repo(p_cmp)
    p_cmp.set_defaults(func=cmd_compare)

    # diff
    p_diff = sub.add_parser("diff", help="Visualise the last session's git changes")
    p_diff.add_argument("--session", type=int, default=None)
    _add_repo(p_diff)
    p_diff.set_defaults(func=cmd_diff)

    # diff-sessions
    p_ds = sub.add_parser("diff-sessions", help="Compare any two sessions")
    p_ds.add_argument("--a", type=int, required=True)
    p_ds.add_argument("--b", type=int, required=True)
    _add_json(p_ds)
    _add_repo(p_ds)
    p_ds.set_defaults(func=cmd_diff_sessions)

    # insights
    p_ins = sub.add_parser("insights", help="Session insights")
    _add_write(p_ins)
    _add_json(p_ins)
    _add_repo(p_ins)
    p_ins.set_defaults(func=cmd_insights)

    # ------------------------------------------------------------------
    # Tools commands
    # ------------------------------------------------------------------

    # doctor
    p_doc = sub.add_parser("doctor", help="Repo diagnostic")
    _add_json(p_doc)
    _add_repo(p_doc)
    p_doc.set_defaults(func=cmd_doctor)

    # todos
    p_todos = sub.add_parser("todos", help="Stale TODO hunter")
    _add_json(p_todos)
    _add_repo(p_todos)
    p_todos.set_defaults(func=cmd_todos)

    # benchmark
    p_bench = sub.add_parser("benchmark", help="Benchmark analyzers")
    _add_repo(p_bench)
    p_bench.set_defaults(func=cmd_benchmark)

    # gitstats
    p_git = sub.add_parser("gitstats", help="Git history deep dive")
    _add_repo(p_git)
    p_git.set_defaults(func=cmd_gitstats)

    # badges
    p_badges = sub.add_parser("badges", help="README badge generator")
    _add_repo(p_badges)
    p_badges.set_defaults(func=cmd_badges)

    # audit
    p_audit = sub.add_parser("audit", help="Executive quality audit")
    _add_json(p_audit)
    _add_repo(p_audit)
    p_audit.set_defaults(func=cmd_audit)

    # predict
    p_pred = sub.add_parser("predict", help="Predict next improvements")
    _add_json(p_pred)
    _add_repo(p_pred)
    p_pred.set_defaults(func=cmd_predict)

    # teach
    p_teach = sub.add_parser("teach", help="Generate module tutorial")
    p_teach.add_argument("module")
    _add_write(p_teach)
    _add_json(p_teach)
    _add_repo(p_teach)
    p_teach.set_defaults(func=cmd_teach)

    # dna
    p_dna = sub.add_parser("dna", help="Repo DNA fingerprint")
    _add_json(p_dna)
    _add_repo(p_dna)
    p_dna.set_defaults(func=cmd_dna)

    # report
    p_report = sub.add_parser("report", help="Executive HTML report")
    p_report.add_argument("--write", action="store_true")
    _add_repo(p_report)
    p_report.set_defaults(func=cmd_report)

    # export
    p_export = sub.add_parser("export", help="Export analysis output")
    p_export.add_argument("analysis", choices=[
        "health", "complexity", "coupling", "deadcode", "security", "coveragemap",
        "maturity", "stats", "changelog", "story", "reflect", "evolve", "status",
        "session-score", "timeline", "replay", "compare", "diff", "diff-sessions",
        "insights", "doctor", "todos", "benchmark", "gitstats", "badges", "audit",
        "predict", "teach", "dna", "coverage", "score", "pr-score", "test-quality",
        "refactor", "commits", "semver", "modules", "trends", "module-risk"
    ])
    p_export.add_argument("--format", default="json", choices=["json", "markdown"])
    _add_repo(p_export)
    p_export.set_defaults(func=cmd_export)

    # coverage
    p_cov = sub.add_parser("coverage", help="Coverage trend")
    _add_json(p_cov)
    _add_repo(p_cov)
    p_cov.set_defaults(func=cmd_coverage)

    # score
    p_score = sub.add_parser("score", help="Score latest PR")
    _add_json(p_score)
    _add_repo(p_score)
    p_score.set_defaults(func=cmd_score)

    # pr-score
    p_prscore = sub.add_parser("pr-score", help="Score a PR by number")
    p_prscore.add_argument("--pr", type=int, required=True)
    p_prscore.add_argument("--write", action="store_true")
    _add_json(p_prscore)
    _add_repo(p_prscore)
    p_prscore.set_defaults(func=cmd_score)

    # test-quality
    p_tq = sub.add_parser("test-quality", help="Test quality scoring")
    _add_json(p_tq)
    _add_repo(p_tq)
    p_tq.set_defaults(func=cmd_test_quality)

    # refactor
    p_refac = sub.add_parser("refactor", help="Refactor candidate finder")
    _add_json(p_refac)
    _add_repo(p_refac)
    p_refac.set_defaults(func=cmd_refactor)

    # commits
    p_comm = sub.add_parser("commits", help="Commit message analyzer")
    _add_json(p_comm)
    _add_repo(p_comm)
    p_comm.set_defaults(func=cmd_commits)

    # semver
    p_semver = sub.add_parser("semver", help="Semver bump recommender")
    _add_json(p_semver)
    _add_repo(p_semver)
    p_semver.set_defaults(func=cmd_semver)

    # modules
    p_modules = sub.add_parser("modules", help="Module interconnection graph")
    p_modules.add_argument("--ascii", action="store_true", help="ASCII output instead of Mermaid")
    p_modules.add_argument("--write", action="store_true", help="Write to docs/MODULE_GRAPH.md")
    _add_json(p_modules)
    _add_repo(p_modules)
    p_modules.set_defaults(func=cmd_modules)

    # trends
    p_trends = sub.add_parser("trends", help="Historical trend data")
    p_trends.add_argument("--write", action="store_true", help="Write to docs/trend_data.json")
    _add_json(p_trends)
    _add_repo(p_trends)
    p_trends.set_defaults(func=cmd_trends)

    # anomalies
    p_anom = sub.add_parser("anomalies", help="Detect unusual patterns in session metrics")
    _add_write(p_anom)
    _add_json(p_anom)
    _add_repo(p_anom)
    p_anom.set_defaults(func=cmd_anomalies)

    # module-risk
    p_modrisk = sub.add_parser("module-risk", help="Combined module risk score (coverage + complexity + coupling)")
    p_modrisk.add_argument("--coverage", default=None, help="Optional coverage.json from pytest-cov")
    p_modrisk.add_argument("--limit", type=int, default=25, help="Max rows in markdown output")
    p_modrisk.add_argument("--write", action="store_true", help="Write to docs/module_risk.md")
    p_modrisk.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_modrisk)
    p_modrisk.set_defaults(func=cmd_module_risk)

    # plan / brain
    p_plan = sub.add_parser("plan", help="Session task planner")
    p_plan.add_argument("--session", type=int, default=1, help="Session number")
    p_plan.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_plan)
    p_plan.set_defaults(func=cmd_plan)

    p_brain = sub.add_parser("brain", help="Session task planner (alias for plan)")
    p_brain.add_argument("--session", type=int, default=1, help="Session number")
    p_brain.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_brain)
    p_brain.set_defaults(func=cmd_plan)

    # triage
    p_triage = sub.add_parser("triage", help="Issue triage")
    p_triage.add_argument("--issues", default=None, help="Path to issues JSON")
    p_triage.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_triage)
    p_triage.set_defaults(func=cmd_triage)

    # depgraph
    p_depgraph = sub.add_parser("depgraph", help="Module dependency graph")
    _add_write(p_depgraph)
    _add_json(p_depgraph)
    _add_repo(p_depgraph)
    p_depgraph.set_defaults(func=cmd_depgraph)

    # arch
    p_arch = sub.add_parser("arch", help="Architecture doc generator")
    p_arch.add_argument("--write", action="store_true")
    _add_repo(p_arch)
    p_arch.set_defaults(func=cmd_arch)

    # ------------------------------------------------------------------
    # Infrastructure commands
    # ------------------------------------------------------------------

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Launch React dashboard")
    p_dash.add_argument("--port", type=int, default=8710, help="Port (default: 8710)")
    _add_repo(p_dash)
    p_dash.set_defaults(func=cmd_dashboard)

    # init
    p_init = sub.add_parser("init", help="Initialize repo config")
    _add_repo(p_init)
    p_init.set_defaults(func=cmd_init)

    # deps
    p_deps = sub.add_parser("deps", help="Dependency freshness")
    _add_json(p_deps)
    _add_repo(p_deps)
    p_deps.set_defaults(func=cmd_deps)

    # config
    p_cfg = sub.add_parser("config", help="Config manager")
    p_cfg.add_argument("--write", action="store_true", help="Write default config")
    _add_json(p_cfg)
    _add_repo(p_cfg)
    p_cfg.set_defaults(func=cmd_config)

    # plugins
    p_pl = sub.add_parser("plugins", help="Plugin registry")
    _add_json(p_pl)
    _add_repo(p_pl)
    p_pl.set_defaults(func=cmd_plugins)

    # openapi
    p_oa = sub.add_parser("openapi", help="Generate OpenAPI spec")
    p_oa.add_argument("--write", action="store_true")
    _add_repo(p_oa)
    p_oa.set_defaults(func=cmd_openapi)

    # docstrings
    p_ds = sub.add_parser("docstrings", help="Auto-generate missing docstrings")
    p_ds.add_argument("--dry-run", action="store_true", help="Preview changes")
    p_ds.add_argument("--apply", action="store_true", help="Apply changes in-place")
    p_ds.add_argument("--json", action="store_true", help="Output raw JSON")
    _add_repo(p_ds)
    p_ds.set_defaults(func=cmd_docstrings)

    # automerge
    p_am = sub.add_parser("automerge", help="Auto-merge eligibility gate")
    p_am.add_argument("--pr", type=int, required=True)
    p_am.add_argument("--ci-passed", action="store_true")
    p_am.add_argument("--min-score", type=int, default=80)
    p_am.add_argument("--json", action="store_true")
    p_am.set_defaults(func=cmd_automerge)

    # run
    p_run = sub.add_parser("run", help="Run end-of-session pipeline")
    _add_repo(p_run)
    p_run.set_defaults(func=cmd_run)

    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for the awake CLI.

    Args:
        argv: Optional argv list (default: sys.argv[1:]).

    Returns:
        Exit code.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        _print_warn("Interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
