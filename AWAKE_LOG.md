# Awake Log

This log is maintained autonomously by Computer. Every session appends a structured entry describing what was built and why.

---

## Session 0 -- Repo Scaffold (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Created repo scaffold with core files
- Done Set up directory structure (`src/`, `tests/`, `docs/`, `.github/`)
- Done Defined AWAKE rules and operating system

### PR
- PR #1 -- Session 0: Scaffold

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 4 |
| Tests | 0 |
| PRs opened | 1 |

---

## Session 1 -- Stats + Tests + CI (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/stats.py` to compute repo evolution stats
- Done Created `src/session_logger.py` to append structured session logs
- Done Wrote 50 tests (one per module)
- Done Set up GitHub Actions CI workflow
- Done Created PR template

### PRs
- PR #2 -- Stats engine
- PR #3 -- Session logger
- PR #4 -- Test framework
- PR #5 -- CI pipeline + PR template

### Decisions
1. Tests will cover every module even if minimal
2. CI runs on Python 3.10-3.12

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 8 |
| Tests | 50 |
| PRs opened | 4 |

---

## Session 2 -- Health + Changelog + Coverage (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/health.py` code health analyzer
- Done Built `src/changelog.py` changelog generator
- Done Built `src/coverage_tracker.py` test coverage runner and history tracker
- Done Wrote 129 new tests

### PRs
- PR #6 -- Health module
- PR #7 -- Changelog generator
- PR #8 -- Coverage tracker

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 11 |
| Tests | 179 |
| PRs opened | 3 |

---

## Session 3 -- README Automation + Diff Visualizer + PR Scoring (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/readme_updater.py` to auto-update README with live stats
- Done Built `src/diff_visualizer.py` to summarize session changes with heatmaps
- Done Built `src/pr_scorer.py` PR scoring system
- Done Wrote 219 new tests

### PRs
- PR #9 -- README automation
- PR #10 -- Diff visualizer
- PR #11 -- PR scoring

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 14 |
| Tests | 398 |
| PRs opened | 3 |

---

## Session 4 -- CLI + Refactor Engine + Architecture Docs (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/cli.py` unified CLI entry point
- Done Built `src/refactor.py` AST-based refactor analyzer + auto-fix
- Done Built `src/arch_generator.py` to generate architecture docs
- Done Wrote 281 new tests

### PRs
- PR #12 -- CLI entry point
- PR #13 -- Refactor engine
- PR #14 -- Architecture docs

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 17 |
| Tests | 679 |
| PRs opened | 3 |

---

## Session 5 -- Brain + Issues + Dashboard + Replay (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built `src/issue_triage.py` issue classification engine
- Done Built `src/brain.py` task prioritization engine
- Done Built `src/dashboard.py` terminal dashboard
- Done Built `src/session_replay.py` replay engine
- Done Built `docs/index.html` web dashboard
- Done Built `src/teach.py` tutorial generator
- Done Built `src/dna.py` repo fingerprint
- Done Built `src/maturity.py` maturity scoring
- Done Built `src/story.py` repo narrative generator
- Done Built `src/coverage_map.py` coverage heat map
- Done Built `src/security.py` security audit
- Done Built `src/dead_code.py` dead code detector
- Done Built `src/blame.py` blame attribution
- Done Added CONTRIBUTING.md

### PRs
- PR #15 through PR #28

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 26 |
| Tests | 1,260 |
| PRs opened | 14 |

---

## Session 10 -- Fixes + Doctor + Dependency Graph (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Fixed session_replay branch regex bug
- Done Built `src/dep_graph.py` dependency graph visualizer
- Done Built `src/todo_hunter.py` stale TODO hunter
- Done Built `src/doctor.py` full diagnostic module
- Done Expanded CLI with `depgraph`, `todos`, `doctor`

### PRs
- PR #29 through PR #32

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 30 |
| Tests | 1,622 |
| PRs opened | 4 |

---

## Session 11 -- Timeline + Complexity + Exporter (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built `src/timeline.py` session timeline visualizer
- Done Built `src/coupling.py` coupling analyzer
- Done Built `src/complexity.py` cyclomatic complexity tracker
- Done Built `src/exporter.py` export system

### PRs
- PR #33 through PR #36

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 34 |
| Tests | 1,816 |
| PRs opened | 4 |

---

## Session 12 -- Config + Compare + Terminal Dashboard (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built `src/config.py` awake.toml config system
- Done Built `src/compare.py` session diff engine
- Done Built `src/dashboard.py` terminal dashboard
- Done Built `src/deps_checker.py` dependency freshness checker

### PRs
- PR #37 through PR #40

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 38 |
| Tests | 1,934 |
| PRs opened | 4 |

---

## Session 13 -- Blame + Dead Code + Security (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built `src/blame.py` blame attribution engine
- Done Built `src/dead_code.py` dead code detector
- Done Built `src/security.py` security audit
- Done Built `src/coverage_map.py` coverage heat map

### PRs
- PR #41 through PR #44

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 42 |
| Tests | 2,030 |
| PRs opened | 4 |

---

## Sessions 19-28 -- See previous entries above

---

## Session 29 -- Anomaly Alerting (2026-03-04)

**Operator:** Computer
**Trigger:** Scheduled Awake autonomous dev session

### Tasks Completed
- Done **Anomaly detection engine** -- Built `src/anomaly.py`: IQR-based statistical anomaly detection across 5 dimensions. Parses AWAKE_LOG.md session entries, extracts metrics, and flags unusual patterns with CRITICAL/WARNING/INFO severity levels.
- Done **5 anomaly detectors**:
  1. **Test count drops** -- flags sessions where test count decreased (CRITICAL)
  2. **Complexity spikes** -- detects disproportionate lines-added vs tests ratio (WARNING)
  3. **Velocity changes** -- identifies dramatic shifts in session frequency (INFO)
  4. **Missing metrics** -- catches session entries missing expected stats fields (WARNING)
  5. **PR count anomalies** -- flags unusual PR counts using IQR outlier detection (INFO)
- Done **CLI integration** -- Added `awake anomalies` command with `--json` and `--repo` flags
- Done **Structured output** -- Both Markdown report and JSON serialization for machine consumption
- Done **Test suite** -- 63 new tests covering parsers, statistical helpers, all 5 detectors, serialization, and real-log integration

### PR
- PR #63 -- Session 29: Anomaly alerting

### Decisions
1. Used IQR (interquartile range) for outlier detection rather than z-scores -- more robust to non-normal distributions and small sample sizes typical in session data.
2. Built as standalone module rather than extending insights.py -- anomaly detection has different concerns (alerting, severity, actions) than insights (narrative, streaks, velocity).
3. Three severity levels (CRITICAL/WARNING/INFO) with suggested actions -- makes the output actionable, not just informational.
4. Test count drops are CRITICAL by default -- losing tests is always worth investigating.

### Stats
| Metric | Before | After |
|--------|--------|-------|
| Source modules | 69 | 70 |
| Tests | 2,467 | 2,530 |
| CLI subcommands | 55 | 56 |
| PRs merged | 62 | 63 |

---
