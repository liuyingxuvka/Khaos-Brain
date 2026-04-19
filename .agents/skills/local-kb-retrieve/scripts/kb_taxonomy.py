#!/usr/bin/env python3
"""Inspect the explicit taxonomy layer of the local predictive knowledge base."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.store import resolve_repo_root
from local_kb.taxonomy import (
    build_taxonomy_gap_report,
    build_taxonomy_view,
    format_taxonomy_gap_report,
    format_taxonomy_view,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--route", default="")
    parser.add_argument("--gaps-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    if args.gaps_only:
        report = build_taxonomy_gap_report(repo_root)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return
        print(format_taxonomy_gap_report(report))
        return

    view = build_taxonomy_view(repo_root, route=args.route)
    if args.json:
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return
    print(format_taxonomy_view(view))


if __name__ == "__main__":
    main()
