from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.consolidate import consolidate_history


class ConsolidateHistoryTest(unittest.TestCase):
    def test_groups_actions_and_emits_snapshot_and_proposal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            events = [
                {
                    "event_id": "cand-2026-04-19-email-default",
                    "event_type": "candidate-created",
                    "created_at": "2026-04-19T08:00:00+00:00",
                    "source": {"kind": "kb-capture", "agent": "worker-2"},
                    "target": {
                        "kind": "candidate-entry",
                        "entry_id": "cand-2026-04-19-email-default",
                        "domain_path": ["work", "communication", "email"],
                    },
                    "rationale": "smoke candidate",
                    "context": {},
                },
                {
                    "event_id": "obs-update-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:05:00+00:00",
                    "source": {"kind": "task", "agent": "worker-2"},
                    "target": {
                        "kind": "task-observation",
                        "entry_ids": ["example-entry-002"],
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Missed release notes troubleshooting hint",
                    },
                    "rationale": "retrieval=miss, next=update-card",
                    "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                },
                {
                    "event_id": "obs-gap-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:07:00+00:00",
                    "source": {"kind": "task", "agent": "worker-2"},
                    "target": {
                        "kind": "task-observation",
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Weak retrieval for version-change task",
                    },
                    "rationale": "retrieval=weak, gap-exposed",
                    "context": {"hit_quality": "weak", "exposed_gap": True},
                },
                {
                    "event_id": "obs-new-cand-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:09:00+00:00",
                    "source": {"kind": "task", "agent": "worker-2"},
                    "target": {
                        "kind": "task-observation",
                        "route_hint": ["work", "communication", "email"],
                        "task_summary": "Need a reusable email preference card",
                    },
                    "rationale": "next=new-candidate",
                    "context": {"suggested_action": "new-candidate"},
                },
            ]
            with history_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")

            result = consolidate_history(
                repo_root=repo_root,
                run_id="20260419T090000Z",
                emit_files=True,
            )

            self.assertEqual(result["event_count"], 4)
            self.assertEqual(result["candidate_action_count"], 4)
            self.assertEqual(
                [action["action_type"] for action in result["actions"]],
                [
                    "review-entry-update",
                    "investigate-gap",
                    "consider-new-candidate",
                    "review-candidate",
                ],
            )
            self.assertEqual(
                result["actions"][0]["target"],
                {"kind": "entry", "ref": "example-entry-002"},
            )
            self.assertEqual(
                result["actions"][0]["suggested_artifact_kind"],
                "entry-update-proposal",
            )
            self.assertEqual(
                result["actions"][0]["task_summaries"],
                ["Missed release notes troubleshooting hint"],
            )
            self.assertEqual(
                result["artifact_paths"]["snapshot_path"],
                "kb/history/consolidation/20260419T090000Z/snapshot.json",
            )
            self.assertEqual(
                result["artifact_paths"]["proposal_path"],
                "kb/history/consolidation/20260419T090000Z/proposal.json",
            )

            snapshot_path = repo_root / result["artifact_paths"]["snapshot_path"]
            proposal_path = repo_root / result["artifact_paths"]["proposal_path"]
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
            proposal_payload = json.loads(proposal_path.read_text(encoding="utf-8"))

            self.assertEqual(snapshot_payload["run_id"], "20260419T090000Z")
            self.assertEqual(snapshot_payload["event_count"], 4)
            self.assertEqual(proposal_payload["candidate_action_count"], 4)
            self.assertTrue(proposal_payload["actions"][0]["ai_decision_required"])
            self.assertEqual(
                proposal_payload["actions"][2]["suggested_artifact_kind"],
                "candidate-entry-proposal",
            )


if __name__ == "__main__":
    unittest.main()
