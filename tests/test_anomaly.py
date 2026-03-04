"""
Tests for anomaly.py — Anomaly detection engine for Awake session metrics.

Covers:
- Log parsing (_parse_log, _parse_int, _SessionData)
- Statistical helpers (_iqr_bounds, _mean, _stdev, _z_score)
- Detector: test drops (_detect_test_drops)
- Detector: complexity spikes (_detect_complexity_spikes)
- Detector: velocity changes (_detect_velocity_changes)
- Detector: missing metrics (_detect_missing_metrics)
- Detector: PR anomalies (_detect_pr_anomalies)
- Public API (detect_anomalies)
- Report serialization (to_dict, to_json, to_markdown)
- Edge cases: empty log, single session, no anomalies, all anomalies
"""

from __future__ import annotations

import json
import math
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from anomaly import (
    Anomaly,
    AnomalyReport,
    _SessionData,
    _detect_complexity_spikes,
    _detect_missing_metrics,
    _detect_pr_anomalies,
    _detect_test_drops,
    _detect_velocity_changes,
    _iqr_bounds,
    _mean,
    _parse_int,
    _parse_log,
    _stdev,
    _z_score,
    detect_anomalies,
)


# ---------------------------------------------------------------------------
# Fixtures: synthetic AWAKE_LOG.md fragments
# ---------------------------------------------------------------------------

MINIMAL_LOG = """\
## Session 1 -- Stats + Tests (2026-02-27)

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
| Lines added | ~800 |
"""

MULTI_SESSION_LOG = """\
## Session 0 -- Repo Scaffold (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Created repo scaffold

### PRs
- PR #1 -- Session 0: Scaffold

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 3 |
| Tests | 10 |
| PRs opened | 1 |
| Lines added | ~200 |

## Session 1 -- Stats + Tests (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Built stats engine

### PRs
- PR #2 -- Stats engine
- PR #3 -- Test framework

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 8 |
| Tests | 50 |
| PRs opened | 2 |
| Lines added | ~800 |

## Session 2 -- Insights (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built insights

### PRs
- PR #4 -- Insights module

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 12 |
| Tests | 80 |
| PRs opened | 1 |
| Lines added | ~600 |

## Session 3 -- Timeline (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Built timeline

### PRs
- PR #5 -- Timeline

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 15 |
| Tests | 100 |
| PRs opened | 1 |
| Lines added | ~400 |

## Session 4 -- Final Polish (2026-02-28)

**Operator:** Computer

### Tasks Completed
- Done Polished code

### PRs
- PR #6 -- Polish

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 18 |
| Tests | 120 |
| PRs opened | 1 |
| Lines added | ~300 |
"""

TEST_DROP_LOG = """\
## Session 1 -- Build (2026-02-27)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 5 |
| Tests | 50 |
| PRs opened | 1 |

## Session 2 -- More (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 8 |
| Tests | 80 |
| PRs opened | 1 |

## Session 3 -- Regression (2026-03-01)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 10 |
| Tests | 60 |
| PRs opened | 1 |
"""

MISSING_STATS_LOG = """\
## Session 1 -- Scaffold (2026-02-27)

**Operator:** Computer

### Tasks Completed
- Done Created stuff

### PRs
- PR #1 -- Scaffold

## Session 2 -- Complete (2026-02-28)

### Stats
| Metric | Value |
|--------|-------|
| Source modules | 10 |
| Tests | 50 |
| PRs opened | 2 |
"""

VELOCITY_GAP_LOG = """\
## Session 1 -- Start (2026-01-01)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 10 |
| PRs opened | 1 |

## Session 2 -- Quick (2026-01-02)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 20 |
| PRs opened | 1 |

## Session 3 -- Quick2 (2026-01-03)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 30 |
| PRs opened | 1 |

## Session 4 -- Quick3 (2026-01-04)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 40 |
| PRs opened | 1 |

## Session 5 -- Quick4 (2026-01-05)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 50 |
| PRs opened | 1 |

## Session 6 -- Quick5 (2026-01-06)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 60 |
| PRs opened | 1 |

## Session 7 -- Long Gap (2026-03-15)

### Stats
| Metric | Value |
|--------|-------|
| Tests | 70 |
| PRs opened | 1 |
"""


# ---------------------------------------------------------------------------
# _parse_int
# ---------------------------------------------------------------------------


class TestParseInt:
    def test_plain_number(self):
        assert _parse_int("42") == 42

    def test_comma_separated(self):
        assert _parse_int("1,234") == 1234

    def test_tilde_prefix(self):
        assert _parse_int("~800") == 800

    def test_plus_suffix(self):
        assert _parse_int("100+") == 100

    def test_whitespace(self):
        assert _parse_int("  56  ") == 56

    def test_invalid_returns_zero(self):
        assert _parse_int("abc") == 0

    def test_empty_returns_zero(self):
        assert _parse_int("") == 0


# ---------------------------------------------------------------------------
# _parse_log
# ---------------------------------------------------------------------------


class TestParseLog:
    def test_empty_string(self):
        assert _parse_log("") == []

    def test_no_sessions(self):
        assert _parse_log("# Some header\n\nJust text.") == []

    def test_minimal_single_session(self):
        records = _parse_log(MINIMAL_LOG)
        assert len(records) == 1
        r = records[0]
        assert r.number == 1
        assert r.date == "2026-02-27"
        assert r.title == "Stats + Tests"
        assert r.prs == 2
        assert r.modules == 8
        assert r.tests == 50
        assert r.lines_added == 800
        assert r.has_modules_stat is True
        assert r.has_tests_stat is True
        assert r.has_prs_stat is True
        assert r.has_lines_stat is True

    def test_multi_session_count(self):
        records = _parse_log(MULTI_SESSION_LOG)
        assert len(records) == 5

    def test_sessions_sorted_by_number(self):
        records = _parse_log(MULTI_SESSION_LOG)
        numbers = [r.number for r in records]
        assert numbers == sorted(numbers)

    def test_pr_count_from_bullet_lines(self):
        """When PRs stat is missing, count PR bullet lines."""
        log = """\
## Session 1 -- Test (2026-02-27)

### PRs
- PR #1 -- First
- PR #2 -- Second
- PR #3 -- Third

### Stats
| Metric | Value |
|--------|-------|
| Tests | 10 |
"""
        records = _parse_log(log)
        assert records[0].prs == 3
        assert records[0].has_prs_stat is False

    def test_missing_stats_detected(self):
        records = _parse_log(MISSING_STATS_LOG)
        session1 = records[0]
        assert session1.has_modules_stat is False
        assert session1.has_tests_stat is False
        assert session1.has_prs_stat is False

    def test_tests_local_format(self):
        """Parser handles 'Tests (local) | N passed' format."""
        log = """\
## Session 1 -- Test (2026-02-27)

### Stats
| Metric | Value |
|--------|-------|
| Tests (local) | 120 passed, 0 skipped |
| PRs opened | 1 |
"""
        records = _parse_log(log)
        assert records[0].tests == 120
        assert records[0].has_tests_stat is True


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


class TestIqrBounds:
    def test_empty_list(self):
        lo, hi = _iqr_bounds([])
        assert (lo, hi) == (0.0, 0.0)

    def test_single_value(self):
        lo, hi = _iqr_bounds([5.0])
        assert lo == 5.0
        assert hi == 5.0

    def test_three_values_returns_min_max(self):
        lo, hi = _iqr_bounds([1.0, 5.0, 10.0])
        assert lo == 1.0
        assert hi == 10.0

    def test_four_or_more_uses_iqr(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        lo, hi = _iqr_bounds(values)
        # Q1 = values[2] = 3.0, Q3 = values[6] = 7.0, IQR = 4.0
        assert lo == 3.0 - 1.5 * 4.0  # -3.0
        assert hi == 7.0 + 1.5 * 4.0  # 13.0

    def test_custom_k(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        lo, hi = _iqr_bounds(values, k=3.0)
        assert lo == 3.0 - 3.0 * 4.0  # -9.0
        assert hi == 7.0 + 3.0 * 4.0  # 19.0


class TestMean:
    def test_empty(self):
        assert _mean([]) == 0.0

    def test_single(self):
        assert _mean([5.0]) == 5.0

    def test_multiple(self):
        assert _mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)


class TestStdev:
    def test_empty(self):
        assert _stdev([]) == 0.0

    def test_single(self):
        assert _stdev([5.0]) == 0.0

    def test_known_values(self):
        # Sample stdev of [2, 4, 4, 4, 5, 5, 7, 9]
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        expected = math.sqrt(sum((v - 5.0) ** 2 for v in values) / 7)
        assert _stdev(values) == pytest.approx(expected, abs=0.01)


class TestZScore:
    def test_zero_stdev(self):
        assert _z_score(5.0, 5.0, 0.0) == 0.0

    def test_positive(self):
        assert _z_score(10.0, 5.0, 2.5) == pytest.approx(2.0)

    def test_negative(self):
        assert _z_score(0.0, 5.0, 2.5) == pytest.approx(-2.0)


# ---------------------------------------------------------------------------
# Detector: _detect_test_drops
# ---------------------------------------------------------------------------


class TestDetectTestDrops:
    def test_no_drop(self):
        records = _parse_log(MULTI_SESSION_LOG)
        anomalies = _detect_test_drops(records)
        assert len(anomalies) == 0

    def test_drop_detected(self):
        records = _parse_log(TEST_DROP_LOG)
        anomalies = _detect_test_drops(records)
        assert len(anomalies) == 1
        a = anomalies[0]
        assert a.severity == "CRITICAL"
        assert a.session == 3
        assert a.kind == "test_count_drop"
        assert a.metric_value == 60.0

    def test_drop_with_zero_tests_ignored(self):
        """Sessions with tests=0 (not reported) should not trigger."""
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 5, 50, 0, True, True, True, False),
            _SessionData(2, "2026-01-02", "B", 1, 8, 0, 0, True, False, True, False),
            _SessionData(3, "2026-01-03", "C", 1, 10, 80, 0, True, True, True, False),
        ]
        anomalies = _detect_test_drops(records)
        assert len(anomalies) == 0


# ---------------------------------------------------------------------------
# Detector: _detect_complexity_spikes
# ---------------------------------------------------------------------------


class TestDetectComplexitySpikes:
    def test_no_spikes_normal_data(self):
        records = _parse_log(MULTI_SESSION_LOG)
        anomalies = _detect_complexity_spikes(records)
        # Normal multi-session log shouldn't have complexity spikes
        critical = [a for a in anomalies if a.severity == "CRITICAL"]
        assert len(critical) == 0

    def test_lots_of_lines_no_tests(self):
        """Lines > 100 with zero new tests is a WARNING."""
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 5, 50, 200, True, True, True, True),
            _SessionData(2, "2026-01-02", "B", 1, 8, 50, 500, True, True, True, True),
        ]
        anomalies = _detect_complexity_spikes(records)
        warnings = [a for a in anomalies if a.kind == "complexity_spike"]
        assert len(warnings) >= 1
        assert warnings[0].session == 2

    def test_extreme_ratio_detected(self):
        """Very high lines/tests ratio triggers warning with enough data points."""
        # Need enough normal points to make IQR tight, then one outlier
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 5, 10, 100, True, True, True, True),
            _SessionData(2, "2026-01-02", "B", 1, 8, 20, 100, True, True, True, True),
            _SessionData(3, "2026-01-03", "C", 1, 10, 30, 100, True, True, True, True),
            _SessionData(4, "2026-01-04", "D", 1, 12, 40, 100, True, True, True, True),
            _SessionData(5, "2026-01-05", "E", 1, 14, 50, 100, True, True, True, True),
            _SessionData(6, "2026-01-06", "F", 1, 16, 51, 5000, True, True, True, True),
        ]
        anomalies = _detect_complexity_spikes(records)
        # Session 6 adds 1 test for 5000 lines — ratio = 5000, way above IQR
        spikes = [a for a in anomalies if a.session == 6 and a.kind == "complexity_spike"]
        assert len(spikes) >= 1


# ---------------------------------------------------------------------------
# Detector: _detect_velocity_changes
# ---------------------------------------------------------------------------


class TestDetectVelocityChanges:
    def test_too_few_sessions(self):
        records = _parse_log(MINIMAL_LOG)
        anomalies = _detect_velocity_changes(records)
        assert len(anomalies) == 0

    def test_large_gap_detected(self):
        records = _parse_log(VELOCITY_GAP_LOG)
        anomalies = _detect_velocity_changes(records)
        gap_anomalies = [a for a in anomalies if a.kind == "velocity_gap"]
        assert len(gap_anomalies) >= 1
        assert gap_anomalies[0].session == 7

    def test_session_burst_detected(self):
        """4+ sessions on same day triggers burst anomaly."""
        log = "\n".join([
            f"## Session {i} -- Task{i} (2026-03-01)\n\n"
            f"### Stats\n| Metric | Value |\n|--------|-------|\n"
            f"| Tests | {10 + i * 5} |\n| PRs opened | 1 |\n"
            for i in range(5)
        ])
        records = _parse_log(log)
        anomalies = _detect_velocity_changes(records)
        burst = [a for a in anomalies if a.kind == "session_burst"]
        assert len(burst) >= 1
        assert burst[0].metric_value == 5.0

    def test_uniform_spacing_no_anomaly(self):
        """Uniformly spaced sessions shouldn't trigger velocity anomalies."""
        log = "\n".join([
            f"## Session {i} -- Task{i} (2026-01-{1 + i:02d})\n\n"
            f"### Stats\n| Metric | Value |\n|--------|-------|\n"
            f"| Tests | {10 + i * 5} |\n| PRs opened | 1 |\n"
            for i in range(6)
        ])
        records = _parse_log(log)
        anomalies = _detect_velocity_changes(records)
        gap_anomalies = [a for a in anomalies if a.kind == "velocity_gap"]
        assert len(gap_anomalies) == 0


# ---------------------------------------------------------------------------
# Detector: _detect_missing_metrics
# ---------------------------------------------------------------------------


class TestDetectMissingMetrics:
    def test_complete_sessions_no_warning(self):
        records = _parse_log(MULTI_SESSION_LOG)
        anomalies = _detect_missing_metrics(records)
        # All sessions have full stats
        warnings = [a for a in anomalies if a.severity == "WARNING"]
        assert len(warnings) == 0

    def test_two_missing_fields_is_warning(self):
        records = _parse_log(MISSING_STATS_LOG)
        anomalies = _detect_missing_metrics(records)
        # Session 1 is missing all stats
        warnings = [a for a in anomalies if a.severity == "WARNING"]
        assert len(warnings) >= 1
        assert warnings[0].session == 1

    def test_one_missing_field_is_info(self):
        """Single missing field is INFO severity."""
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 5, 50, 0, True, True, True, False),
        ]
        # Missing only lines_added — but that's not checked by the detector
        # Instead, let's make one that's missing Source modules only
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 0, 50, 0, False, True, True, False),
        ]
        anomalies = _detect_missing_metrics(records)
        info = [a for a in anomalies if a.severity == "INFO"]
        assert len(info) == 1
        assert "Source modules" in info[0].description


# ---------------------------------------------------------------------------
# Detector: _detect_pr_anomalies
# ---------------------------------------------------------------------------


class TestDetectPrAnomalies:
    def test_too_few_sessions(self):
        records = _parse_log(MINIMAL_LOG)
        anomalies = _detect_pr_anomalies(records)
        assert len(anomalies) == 0

    def test_normal_pr_counts_no_anomaly(self):
        records = _parse_log(MULTI_SESSION_LOG)
        anomalies = _detect_pr_anomalies(records)
        # PR counts are 1-2 across sessions — not anomalous
        assert len(anomalies) == 0

    def test_very_high_pr_count_detected(self):
        """Extremely high PR count triggers anomaly."""
        records = [
            _SessionData(1, "2026-01-01", "A", 1, 5, 10, 0, True, True, True, False),
            _SessionData(2, "2026-01-02", "B", 1, 8, 20, 0, True, True, True, False),
            _SessionData(3, "2026-01-03", "C", 2, 10, 30, 0, True, True, True, False),
            _SessionData(4, "2026-01-04", "D", 1, 12, 40, 0, True, True, True, False),
            _SessionData(5, "2026-01-05", "E", 1, 14, 50, 0, True, True, True, False),
            _SessionData(6, "2026-01-06", "F", 15, 16, 60, 0, True, True, True, False),
        ]
        anomalies = _detect_pr_anomalies(records)
        high = [a for a in anomalies if a.kind == "pr_count_high"]
        assert len(high) >= 1
        assert high[0].session == 6


# ---------------------------------------------------------------------------
# AnomalyReport serialization
# ---------------------------------------------------------------------------


class TestAnomalyReport:
    def _sample_report(self) -> AnomalyReport:
        return AnomalyReport(
            sessions_analyzed=5,
            total_anomalies=2,
            critical_count=1,
            warning_count=0,
            info_count=1,
            anomalies=[
                Anomaly(
                    severity="CRITICAL",
                    session=3,
                    kind="test_count_drop",
                    description="Tests dropped.",
                    metric_name="cumulative_tests",
                    metric_value=60.0,
                    expected_range=">= 80",
                    suggested_action="Investigate.",
                ),
                Anomaly(
                    severity="INFO",
                    session=5,
                    kind="velocity_gap",
                    description="Long gap.",
                    metric_name="days_since_previous",
                    metric_value=42.0,
                    expected_range="0.0 – 5.0 days",
                    suggested_action="Check for blockers.",
                ),
            ],
        )

    def test_to_dict_structure(self):
        report = self._sample_report()
        d = report.to_dict()
        assert d["sessions_analyzed"] == 5
        assert d["total_anomalies"] == 2
        assert d["critical_count"] == 1
        assert d["warning_count"] == 0
        assert d["info_count"] == 1
        assert len(d["anomalies"]) == 2
        assert d["anomalies"][0]["severity"] == "CRITICAL"
        assert d["anomalies"][1]["severity"] == "INFO"

    def test_to_json_valid(self):
        report = self._sample_report()
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["sessions_analyzed"] == 5
        assert len(parsed["anomalies"]) == 2

    def test_to_markdown_contains_header(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "# Awake: Anomaly Detection Report" in md

    def test_to_markdown_contains_summary_table(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "Sessions analyzed" in md
        assert "Total anomalies" in md

    def test_to_markdown_groups_by_severity(self):
        report = self._sample_report()
        md = report.to_markdown()
        assert "CRITICAL" in md
        assert "INFO" in md

    def test_empty_report_markdown(self):
        report = AnomalyReport(
            sessions_analyzed=0,
            total_anomalies=0,
            critical_count=0,
            warning_count=0,
            info_count=0,
            anomalies=[],
        )
        md = report.to_markdown()
        assert "No anomalies detected" in md


# ---------------------------------------------------------------------------
# Anomaly dataclass
# ---------------------------------------------------------------------------


class TestAnomaly:
    def test_to_dict(self):
        a = Anomaly(
            severity="WARNING",
            session=2,
            kind="complexity_spike",
            description="Too complex.",
            metric_name="lines_per_test",
            metric_value=200.0,
            expected_range="10 – 50",
            suggested_action="Review.",
        )
        d = a.to_dict()
        assert d["severity"] == "WARNING"
        assert d["session"] == 2
        assert d["metric_value"] == 200.0


# ---------------------------------------------------------------------------
# Public API: detect_anomalies
# ---------------------------------------------------------------------------


class TestDetectAnomalies:
    def test_with_real_log(self, tmp_path):
        """Run detection against the multi-session synthetic log."""
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(MULTI_SESSION_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        assert report.sessions_analyzed == 5
        assert isinstance(report.total_anomalies, int)
        assert report.total_anomalies >= 0
        assert report.critical_count + report.warning_count + report.info_count == report.total_anomalies

    def test_test_drop_log(self, tmp_path):
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(TEST_DROP_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        assert report.critical_count >= 1
        critical = [a for a in report.anomalies if a.severity == "CRITICAL"]
        assert any(a.kind == "test_count_drop" for a in critical)

    def test_empty_log(self, tmp_path):
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text("")
        report = detect_anomalies(repo_path=tmp_path)
        assert report.sessions_analyzed == 0
        assert report.total_anomalies == 0

    def test_missing_log_file(self, tmp_path):
        """No AWAKE_LOG.md at all should return empty report."""
        report = detect_anomalies(repo_path=tmp_path)
        assert report.sessions_analyzed == 0
        assert report.total_anomalies == 0

    def test_custom_log_path(self, tmp_path):
        custom = tmp_path / "custom_log.md"
        custom.write_text(MULTI_SESSION_LOG)
        report = detect_anomalies(repo_path=tmp_path, log_path=custom)
        assert report.sessions_analyzed == 5

    def test_anomalies_sorted_by_severity(self, tmp_path):
        """CRITICAL should come before WARNING, before INFO."""
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(TEST_DROP_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        if report.total_anomalies >= 2:
            severity_order = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
            for i in range(len(report.anomalies) - 1):
                a = report.anomalies[i]
                b = report.anomalies[i + 1]
                assert severity_order[a.severity] <= severity_order[b.severity]

    def test_velocity_gap_detected(self, tmp_path):
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(VELOCITY_GAP_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        gap_anomalies = [a for a in report.anomalies if a.kind == "velocity_gap"]
        assert len(gap_anomalies) >= 1

    def test_report_json_roundtrip(self, tmp_path):
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(MULTI_SESSION_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        j = report.to_json()
        parsed = json.loads(j)
        assert parsed["sessions_analyzed"] == report.sessions_analyzed

    def test_report_counts_consistent(self, tmp_path):
        log_file = tmp_path / "AWAKE_LOG.md"
        log_file.write_text(MULTI_SESSION_LOG)
        report = detect_anomalies(repo_path=tmp_path)
        crit = sum(1 for a in report.anomalies if a.severity == "CRITICAL")
        warn = sum(1 for a in report.anomalies if a.severity == "WARNING")
        info = sum(1 for a in report.anomalies if a.severity == "INFO")
        assert report.critical_count == crit
        assert report.warning_count == warn
        assert report.info_count == info
        assert report.total_anomalies == crit + warn + info


# ---------------------------------------------------------------------------
# Integration: against real AWAKE_LOG.md
# ---------------------------------------------------------------------------


class TestRealLog:
    """Run anomaly detection on the actual AWAKE_LOG.md if available."""

    @pytest.fixture
    def repo_root(self) -> Path:
        return Path(__file__).resolve().parent.parent

    def test_real_log_runs_without_error(self, repo_root):
        log_path = repo_root / "AWAKE_LOG.md"
        if not log_path.exists():
            pytest.skip("AWAKE_LOG.md not found")
        report = detect_anomalies(repo_path=repo_root)
        assert report.sessions_analyzed > 0
        assert isinstance(report.to_json(), str)
        assert isinstance(report.to_markdown(), str)

    def test_real_log_all_anomalies_have_required_fields(self, repo_root):
        log_path = repo_root / "AWAKE_LOG.md"
        if not log_path.exists():
            pytest.skip("AWAKE_LOG.md not found")
        report = detect_anomalies(repo_path=repo_root)
        for a in report.anomalies:
            assert a.severity in ("CRITICAL", "WARNING", "INFO")
            assert isinstance(a.session, int)
            assert isinstance(a.kind, str) and len(a.kind) > 0
            assert isinstance(a.description, str) and len(a.description) > 0
            assert isinstance(a.metric_name, str) and len(a.metric_name) > 0
            assert isinstance(a.expected_range, str) and len(a.expected_range) > 0
            assert isinstance(a.suggested_action, str) and len(a.suggested_action) > 0
