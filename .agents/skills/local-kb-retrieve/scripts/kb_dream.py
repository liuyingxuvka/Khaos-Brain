#!/usr/bin/env python3
"""Run one bounded dream-maintenance pass for the local predictive KB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text
from local_kb.dream import run_dream_maintenance
from local_kb.store import resolve_repo_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-events", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    result = run_dream_maintenance(
        repo_root=repo_root,
        run_id=args.run_id or None,
        max_events=args.max_events or None,
    )

    if args.json:
        print_json(result, sort_keys=True)
        return

    print_text(
        f"Dream run {result['run_id']} finished with status={result['status']} "
        f"and {result.get('created_candidate_count', 0)} created candidates."
    )
    if result["status"] == "skipped":
        print_text(f"Reason: {result['reason']}")
    print_text(f"Run dir: {result['artifact_paths']['run_dir']}")
    if result.get("history_event_ids"):
        print_text(f"History events: {', '.join(result['history_event_ids'])}")


if __name__ == "__main__":
    main()
