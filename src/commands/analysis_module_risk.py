from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.commands import _repo, _print_header


def cmd_module_risk(args: argparse.Namespace) -> int:
    """Compute per-module risk score from coupling/complexity/coverage."""
    from src.module_risk import generate_module_risk

    _print_header("Module Risk")
    repo = _repo(getattr(args, "repo", None))

    cov = getattr(args, "coverage", None)
    coverage_path = Path(cov) if cov else None

    report = generate_module_risk(repo_root=repo, coverage_json=coverage_path)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0

    md = report.to_markdown(limit=getattr(args, "limit", 25))
    if getattr(args, "write", False):
        out = repo / "docs" / "module_risk.md"
        out.write_text(md, encoding="utf-8")
        return 0

    print(md)
    return 0
