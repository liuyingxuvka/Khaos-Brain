#!/usr/bin/env python3
"""Inspect maintenance proposal stubs emitted for a consolidation run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.proposals import build_proposal_report, format_proposal_report
from local_kb.store import resolve_repo_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id", default="")
    group.add_argument("--run-dir", default="")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    report = build_proposal_report(
        repo_root,
        run_id=args.run_id or None,
        run_dir=args.run_dir or None,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(format_proposal_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
