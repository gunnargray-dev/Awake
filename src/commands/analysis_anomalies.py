"""analysis_anomalies.py — CLI command handler for anomaly alerts.

Implements `awake anomalies`.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..anomaly_alerts import detect_anomalies, render_anomalies_markdown


def cmd_anomalies(args) -> int:
    """Run anomaly detection and print results.

    Args:
        args: argparse Namespace.

    Returns:
        Exit code.
    """
    repo = Path(args.repo).resolve() if getattr(args, "repo", None) else Path.cwd().resolve()
    # If invoked from within the repo, cwd is fine; otherwise fall back to Awake's
    # default REPO_ROOT via the shared _repo() helper.
    try:
        from src.commands import _repo as _resolve_repo
        repo = _resolve_repo(str(repo))
    except Exception:
        pass
    summary, anomalies = detect_anomalies(repo_path=repo)

    if args.json:
        payload = {
            "summary": summary.to_dict(),
            "anomalies": [a.to_dict() for a in anomalies],
        }
        print(json.dumps(payload, indent=2))
        return 0

    md = render_anomalies_markdown(summary, anomalies)

    if args.write:
        out_dir = repo / "artifacts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "anomalies.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"Wrote {out_path}")
        return 0

    print(md)
    return 0
