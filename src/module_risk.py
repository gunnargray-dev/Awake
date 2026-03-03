"""Module risk scoring: combine coupling + complexity + coverage into one signal.

This module computes a per-module "risk" score intended to highlight parts of
Awake that are hard to change safely.

The score combines three existing diagnostics:

- Coverage weakness (lower test coverage => higher risk)
- Cyclomatic complexity (higher complexity => higher risk)
- Coupling instability (higher instability and higher fan-out => higher risk)

The output is a deterministic JSON/Markdown report that can be consumed by the
brain, the status dashboard, or future alerting.

Design goals:
- stdlib only
- pure functions where possible
- robust to missing optional inputs (e.g. coverage file not generated yet)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ModuleRiskRow:
    """Risk metrics for a single module."""

    module: str
    risk_score: float
    coverage_pct: Optional[float]
    complexity: Optional[int]
    instability: Optional[float]
    afferent: Optional[int]
    efferent: Optional[int]

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "module": self.module,
            "risk_score": round(self.risk_score, 2),
            "coverage_pct": None if self.coverage_pct is None else round(self.coverage_pct, 2),
            "complexity": self.complexity,
            "instability": None if self.instability is None else round(self.instability, 4),
            "afferent": self.afferent,
            "efferent": self.efferent,
        }


@dataclass(frozen=True)
class ModuleRiskReport:
    """Full risk report across modules."""

    rows: list[ModuleRiskRow]
    generated_from: dict

    def to_dict(self) -> dict:
        """Serialize report."""
        return {
            "generated_from": dict(self.generated_from),
            "modules": [r.to_dict() for r in self.rows],
        }

    def to_markdown(self, limit: int = 25) -> str:
        """Render a Markdown table (highest-risk first)."""
        lines = [
            "# Module Risk Report",
            "",
            "This report combines coverage, complexity, and coupling into a single per-module risk score.",
            "",
            "| Module | Risk | Coverage | Complexity | Instability | Ce | Ca |",
            "|--------|------|----------|------------|-------------|----|----|",
        ]
        for r in self.rows[:limit]:
            cov = "—" if r.coverage_pct is None else f"{r.coverage_pct:.1f}%"
            comp = "—" if r.complexity is None else str(r.complexity)
            inst = "—" if r.instability is None else f"{r.instability:.2f}"
            ce = "—" if r.efferent is None else str(r.efferent)
            ca = "—" if r.afferent is None else str(r.afferent)
            lines.append(
                f"| `{r.module}` | **{r.risk_score:.1f}** | {cov} | {comp} | {inst} | {ce} | {ca} |"
            )
        lines.append("")
        lines.append("Scoring: 0 (low risk) to 100 (high risk). Missing inputs reduce confidence but still produce output.")
        return "\n".join(lines)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _scale_0_100(v: float, v_min: float, v_max: float) -> float:
    """Scale v to 0-100 given min/max, clamped."""
    if v_max <= v_min:
        return 0.0
    return 100.0 * _clamp((v - v_min) / (v_max - v_min), 0.0, 1.0)


def _load_coverage_percentages(coverage_json: Path) -> dict[str, float]:
    """Load per-file coverage percentages from pytest-cov JSON report."""
    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files = data.get("files", {})
    out: dict[str, float] = {}
    for filename, fdata in files.items():
        summary = fdata.get("summary", {})
        pct = summary.get("percent_covered")
        if isinstance(pct, (int, float)):
            out[filename] = float(pct)
    return out


def _normalize_module_path(repo_root: Path, module: str) -> str:
    """Map a module name/path into a canonical src/<name>.py key for joins."""
    # coupling/complexity modules generally report `src/foo.py`
    if module.endswith(".py") and module.startswith("src/"):
        return module
    if module.endswith(".py"):
        return f"src/{module.split('/')[-1]}"
    return f"src/{module}.py"


def generate_module_risk(
    repo_root: Path,
    coverage_json: Optional[Path] = None,
) -> ModuleRiskReport:
    """Generate a combined module risk report."""
    from src.coupling import analyze_coupling
    from src.complexity import analyze_complexity

    coupling = analyze_coupling(repo_root)
    complexity = analyze_complexity(repo_root)

    coverage_map: dict[str, float] = {}
    if coverage_json is not None and coverage_json.exists():
        coverage_map = _load_coverage_percentages(coverage_json)

    # Index coupling and complexity by canonical module path
    coupling_by: dict[str, dict] = {}
    for row in coupling.modules:
        coupling_by[_normalize_module_path(repo_root, row.file)] = {
            "instability": row.instability,
            "ca": row.ca,
            "ce": row.ce,
        }

    complexity_by: dict[str, int] = {}
    for r in complexity.results:
        # complexity report is per-function; aggregate by file
        complexity_by.setdefault(_normalize_module_path(repo_root, r.file), 0)
        complexity_by[_normalize_module_path(repo_root, r.file)] += int(r.complexity)

    # Universe: all src/*.py files
    modules = sorted(p.name for p in (repo_root / "src").glob("*.py"))

    # Collect raw values for scaling
    cov_vals = []
    comp_vals = []
    inst_vals = []
    ce_vals = []
    for mod in modules:
        key = f"src/{mod}"
        cov = coverage_map.get(str(repo_root / key)) or coverage_map.get(key)
        if isinstance(cov, (int, float)):
            cov_vals.append(float(cov))
        comp = complexity_by.get(key)
        if isinstance(comp, int):
            comp_vals.append(comp)
        c = coupling_by.get(key)
        if c:
            inst_vals.append(float(c["instability"]))
            ce_vals.append(int(c["ce"]))

    cov_min, cov_max = (min(cov_vals), max(cov_vals)) if cov_vals else (0.0, 100.0)
    comp_min, comp_max = (min(comp_vals), max(comp_vals)) if comp_vals else (0.0, 1.0)
    inst_min, inst_max = (min(inst_vals), max(inst_vals)) if inst_vals else (0.0, 1.0)
    ce_min, ce_max = (min(ce_vals), max(ce_vals)) if ce_vals else (0.0, 1.0)

    rows: list[ModuleRiskRow] = []
    for mod in modules:
        key = f"src/{mod}"
        cov = coverage_map.get(str(repo_root / key)) or coverage_map.get(key)
        cov_pct = float(cov) if isinstance(cov, (int, float)) else None
        comp = complexity_by.get(key)
        c = coupling_by.get(key)
        inst = None
        ca = None
        ce = None
        if c:
            inst = float(c["instability"]) if c.get("instability") is not None else None
            ca = int(c["ca"]) if c.get("ca") is not None else None
            ce = int(c["ce"]) if c.get("ce") is not None else None

        # Normalize components to 0-100 risk.
        # Coverage: lower coverage => higher risk
        cov_risk = 50.0
        if cov_pct is not None:
            cov_risk = 100.0 - _scale_0_100(cov_pct, cov_min, cov_max)

        comp_risk = 50.0
        if comp is not None:
            comp_risk = _scale_0_100(float(comp), float(comp_min), float(comp_max))

        inst_risk = 50.0
        if inst is not None:
            inst_risk = _scale_0_100(float(inst), float(inst_min), float(inst_max))

        ce_risk = 50.0
        if ce is not None:
            # log-scale fan-out so a few huge modules don't dominate
            ce_risk = _scale_0_100(math.log1p(ce), math.log1p(ce_min), math.log1p(ce_max))

        # Weighted blend: coverage 40%, complexity 30%, coupling 30% (instability + fan-out)
        risk = 0.4 * cov_risk + 0.3 * comp_risk + 0.2 * inst_risk + 0.1 * ce_risk

        rows.append(
            ModuleRiskRow(
                module=key,
                risk_score=risk,
                coverage_pct=cov_pct,
                complexity=comp,
                instability=inst,
                afferent=ca,
                efferent=ce,
            )
        )

    rows.sort(key=lambda r: r.risk_score, reverse=True)

    return ModuleRiskReport(
        rows=rows,
        generated_from={
            "repo_root": str(repo_root),
            "coverage_json": None if coverage_json is None else str(coverage_json),
        },
    )
