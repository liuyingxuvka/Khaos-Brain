#!/usr/bin/env python3
"""Append a task observation to the local KB history log."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
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
    parser.add_argument("--scenario", default="")
    parser.add_argument("--action-taken", default="")
    parser.add_argument("--observed-result", default="")
    parser.add_argument("--previous-action", default="")
    parser.add_argument("--previous-result", default="")
    parser.add_argument("--revised-action", default="")
    parser.add_argument("--revised-result", default="")
    parser.add_argument("--operational-use", default="")
    parser.add_argument("--reuse-judgment", default="")
    parser.add_argument(
        "--suggested-action",
        default="none",
        choices=["none", "update-card", "new-candidate", "taxonomy-change", "code-change"],
    )
    parser.add_argument("--exposed-gap", action="store_true")
    parser.add_argument("--source-kind", default="task")
    parser.add_argument("--agent-name", default="kb-recorder")
    parser.add_argument("--thread-ref", default="")
    parser.add_argument("--project-ref", default="")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--retrieval-request-id", default="")
    parser.add_argument("--used-entry-ids", default="")
    parser.add_argument("--evidence-kind", default="task")
    parser.add_argument("--evidence-ref", default="")
    parser.add_argument("--verified", action="store_true")
    parser.add_argument("--user-correction", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # Keep argparse help independent from the KB runtime.  Several of these
    # modules load the LogicGuard/lifecycle stack, which is required for a real
    # feedback write but must not turn ``feedback --help`` into a slow KB boot.
    from local_kb.cli_output import print_json, print_text
    from local_kb.common import csv_to_list
    from local_kb.feedback import build_observation, record_observation
    from local_kb.lifecycle import record_outcome_receipt
    from local_kb.store import history_events_path, resolve_repo_root

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
        scenario=args.scenario,
        action_taken=args.action_taken,
        observed_result=args.observed_result,
        previous_action=args.previous_action,
        previous_result=args.previous_result,
        revised_action=args.revised_action,
        revised_result=args.revised_result,
        operational_use=args.operational_use,
        reuse_judgment=args.reuse_judgment,
        source_kind=args.source_kind,
        agent_name=args.agent_name,
        thread_ref=args.thread_ref,
        project_ref=args.project_ref,
        workspace_root=args.workspace_root,
    )
    record_observation(repo_root, event)
    outcome_receipt = None
    if args.retrieval_request_id:
        used_entry_ids = csv_to_list(args.used_entry_ids or args.entry_ids)
        outcome_receipt = record_outcome_receipt(
            repo_root,
            request_id=args.retrieval_request_id,
            used_entry_ids=used_entry_ids,
            outcome=args.outcome or "unknown",
            evidence_kind=args.evidence_kind,
            evidence_ref=args.evidence_ref,
            verified=args.verified,
            user_correction=args.user_correction,
        )

    if args.json:
        print_json(
            {
                "event": event,
                "history_path": str(history_events_path(repo_root)),
                "outcome_receipt": outcome_receipt,
            }
        )
        return

    print_text(f"Recorded observation {event['event_id']} in {history_events_path(repo_root)}")


if __name__ == "__main__":
    main()
