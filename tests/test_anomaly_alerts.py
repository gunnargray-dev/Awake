import json
from pathlib import Path

import pytest

from src.anomaly_alerts import detect_anomalies


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_detect_anomalies_returns_summary_and_list() -> None:
    summary, anomalies = detect_anomalies(repo_path=_repo_root())
    assert summary.sessions_analyzed > 0
    assert isinstance(anomalies, list)
    assert summary.anomalies_found == len(anomalies)


def test_missing_log_file_is_reported(tmp_path: Path) -> None:
    summary, anomalies = detect_anomalies(repo_path=tmp_path, log_path=tmp_path / "NOPE.md")
    assert summary.anomalies_found == 1
    assert anomalies[0].kind == "missing_log"


def test_parse_failure_is_reported(tmp_path: Path) -> None:
    log = tmp_path / "AWAKE_LOG.md"
    log.write_text("not a real log", encoding="utf-8")
    summary, anomalies = detect_anomalies(repo_path=tmp_path, log_path=log)
    assert summary.anomalies_found == 1
    assert anomalies[0].kind == "parse_failure"


def test_low_tests_for_modules_anomaly(tmp_path: Path) -> None:
    # Minimal synthetic log with cumulative module/test totals.
    log = tmp_path / "AWAKE_LOG.md"
    log.write_text(
        """
# Awake Log

---

## Session 0 -- Scaffold (2026-02-27)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 4 |
| Tests | 0 |
| PRs opened | 1 |

---

## Session 1 -- Something (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 6 |
| Tests | 1 |
| PRs opened | 1 |

---
""",
        encoding="utf-8",
    )
    summary, anomalies = detect_anomalies(
        repo_path=tmp_path,
        log_path=log,
        config={"low_test_delta_threshold": 5, "min_tests_per_module": 1.0},
    )
    kinds = {a.kind for a in anomalies}
    assert "low_tests_for_modules" in kinds
    assert summary.anomalies_found == len(anomalies)


def test_recent_zero_delta_detection(tmp_path: Path) -> None:
    # Create log where last 3 sessions have identical cumulative totals.
    log = tmp_path / "AWAKE_LOG.md"
    log.write_text(
        """
# Awake Log

---

## Session 0 -- A (2026-02-27)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 1 |
| Tests | 1 |
| PRs opened | 1 |

---

## Session 1 -- B (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 2 |
| Tests | 2 |
| PRs opened | 1 |

---

## Session 2 -- C (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 2 |
| Tests | 2 |
| PRs opened | 1 |

---

## Session 3 -- D (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 2 |
| Tests | 2 |
| PRs opened | 1 |

---

## Session 4 -- E (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 2 |
| Tests | 2 |
| PRs opened | 1 |

---
""",
        encoding="utf-8",
    )
    summary, anomalies = detect_anomalies(
        repo_path=tmp_path,
        log_path=log,
        config={"max_zero_delta_sessions": 3},
    )
    assert any(a.kind == "missing_cumulative_stats" and a.severity == "high" for a in anomalies)
    assert summary.anomalies_found == len(anomalies)
