#!/usr/bin/env python3
"""Record an AI maintenance decision into the local KB history log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text
from local_kb.maintenance import build_maintenance_decision, record_maintenance_decision
from local_kb.store import history_events_path, resolve_repo_root


def parse_optional_float(value: str) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    return float(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument(
        "--decision-type",
        required=True,
        choices=["observation-ignored", "candidate-rejected", "confidence-reviewed", "split-reviewed"],
    )
    parser.add_argument("--action-key", required=True)
    parser.add_argument("--resolved-event-ids", default="")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--entry-id", default="")
    parser.add_argument("--route-ref", default="")
    parser.add_argument("--decision-summary", default="")
    parser.add_argument("--review-state", default="")
    parser.add_argument("--previous-confidence", default="")
    parser.add_argument("--new-confidence", default="")
    parser.add_argument("--source-kind", default="maintenance")
    parser.add_argument("--agent-name", default="kb-maintenance")
    parser.add_argument("--thread-ref", default="")
    parser.add_argument("--project-ref", default="")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = resolve_repo_root(args.repo_root)
    event = build_maintenance_decision(
        decision_type=args.decision_type,
        action_key=args.action_key,
        resolved_event_ids=args.resolved_event_ids,
        reason=args.reason,
        source_kind=args.source_kind,
        agent_name=args.agent_name,
        thread_ref=args.thread_ref,
        project_ref=args.project_ref,
        workspace_root=args.workspace_root,
        entry_id=args.entry_id,
        route_ref=args.route_ref,
        decision_summary=args.decision_summary,
        review_state=args.review_state,
        previous_confidence=parse_optional_float(args.previous_confidence),
        new_confidence=parse_optional_float(args.new_confidence),
    )
    record_maintenance_decision(repo_root, event)

    if args.json:
        print_json(
            {
                "event": event,
                "history_path": str(history_events_path(repo_root)),
            }
        )
        return

    print_text(f"Recorded maintenance decision {event['event_id']} in {history_events_path(repo_root)}")


if __name__ == "__main__":
    main()
