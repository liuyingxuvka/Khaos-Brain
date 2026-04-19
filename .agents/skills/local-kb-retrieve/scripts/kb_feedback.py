#!/usr/bin/env python3
"""Append a task observation to the local KB history log."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.feedback import build_observation, record_observation
from local_kb.store import history_events_path, resolve_repo_root


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--task-summary", required=True)
    parser.add_argument("--route-hint", default="")
    parser.add_argument("--entry-ids", default="")
    parser.add_argument(
        "--hit-quality",
        default="none",
        choices=["hit", "weak", "miss", "misleading", "none"],
    )
    parser.add_argument("--outcome", default="")
    parser.add_argument("--comment", default="")
    parser.add_argument(
        "--suggested-action",
        default="none",
        choices=["none", "update-card", "new-candidate", "taxonomy-change", "code-change"],
    )
    parser.add_argument("--exposed-gap", action="store_true")
    parser.add_argument("--source-kind", default="task")
    parser.add_argument("--agent-name", default="kb-recorder")
    parser.add_argument("--thread-ref", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    event = build_observation(
        task_summary=args.task_summary,
        route_hint=args.route_hint,
        entry_ids=args.entry_ids,
        hit_quality=args.hit_quality,
        outcome=args.outcome,
        comment=args.comment,
        suggested_action=args.suggested_action,
        exposed_gap=args.exposed_gap,
        source_kind=args.source_kind,
        agent_name=args.agent_name,
        thread_ref=args.thread_ref,
    )
    record_observation(repo_root, event)

    if args.json:
        print(
            json.dumps(
                {
                    "event": event,
                    "history_path": str(history_events_path(repo_root)),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"Recorded observation {event['event_id']} in {history_events_path(repo_root)}")


if __name__ == "__main__":
    main()
