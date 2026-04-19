#!/usr/bin/env python3
"""Build a deterministic consolidation proposal from local KB history."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.consolidate import consolidate_history
from local_kb.store import resolve_repo_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--max-events", type=int, default=0)
    parser.add_argument("--emit-files", action="store_true")
    parser.add_argument("--apply-mode", choices=["none", "new-candidates"], default="none")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    result = consolidate_history(
        repo_root=repo_root,
        run_id=args.run_id or None,
        emit_files=args.emit_files,
        max_events=args.max_events or None,
        apply_mode=args.apply_mode,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return

    print(
        "Consolidation scaffold analyzed "
        f"{result['event_count']} history events and grouped "
        f"{result['candidate_action_count']} candidate actions."
    )
    if result["apply_mode"] != "none":
        print(f"Apply mode: {result['apply_mode']}")
        print(f"Created candidates: {result['apply_summary']['created_candidate_count']}")
        print(f"Skipped actions: {result['apply_summary']['skipped_action_count']}")
    if result["artifact_paths"]:
        print(f"Snapshot: {result['artifact_paths']['snapshot_path']}")
        print(f"Proposal: {result['artifact_paths']['proposal_path']}")
        if result["artifact_paths"].get("apply_path"):
            print(f"Apply report: {result['artifact_paths']['apply_path']}")


if __name__ == "__main__":
    main()
