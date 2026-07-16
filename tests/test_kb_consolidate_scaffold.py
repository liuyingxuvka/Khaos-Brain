from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.current_runtime_helpers import consolidate_current_history as consolidate_history


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
                        "entry_ids": ["model-release-notes-first"],
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Missed release notes troubleshooting hint",
                    },
                    "rationale": "retrieval=miss, next=update-card",
                    "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                },
                {
                    "event_id": "obs-update-2",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:06:00+00:00",
                    "source": {"kind": "task", "agent": "worker-3"},
                    "target": {
                        "kind": "task-observation",
                        "entry_ids": ["model-release-notes-first"],
                        "route_hint": ["troubleshooting", "dependency", "regression"],
                        "task_summary": "Release notes card now also covers dependency regression triage",
                    },
                    "rationale": "retrieval=weak, next=update-card",
                    "context": {
                        "suggested_action": "update-card",
                        "hit_quality": "weak",
                        "predictive_observation": {
                            "scenario": "When a dependency regression needs fast triage after an upgrade.",
                            "action_taken": "Use the release notes card as the first troubleshooting step.",
                            "observed_result": "The same card appears in a distinct route context and may need route-specific refinement.",
                            "operational_use": "Review whether the card should narrow or split.",
                            "reuse_judgment": "This looks reusable because the same card is being reused outside its primary route.",
                        },
                    },
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

            self.assertEqual(result["event_count"], 5)
            self.assertEqual(result["candidate_action_count"], 8)
            action_types = [action["action_type"] for action in result["actions"]]
            self.assertEqual(action_types.count("review-confidence"), 1)
            self.assertEqual(action_types.count("review-cross-index"), 1)
            self.assertEqual(action_types.count("review-entry-update"), 1)
            self.assertEqual(action_types.count("investigate-gap"), 1)
            self.assertEqual(action_types.count("consider-new-candidate"), 1)
            self.assertEqual(action_types.count("review-observation-evidence"), 2)
            self.assertEqual(action_types.count("review-candidate"), 1)
            confidence_action = next(action for action in result["actions"] if action["action_type"] == "review-confidence")
            entry_update_action = next(action for action in result["actions"] if action["action_type"] == "review-entry-update")
            self.assertEqual(confidence_action["target"], {"kind": "entry", "ref": "model-release-notes-first"})
            self.assertEqual(confidence_action["suggested_artifact_kind"], "confidence-review-proposal")
            self.assertEqual(
                confidence_action["task_summaries"],
                [
                    "Missed release notes troubleshooting hint",
                    "Release notes card now also covers dependency regression triage",
                ],
            )
            self.assertEqual(confidence_action["suggested_confidence_change"]["review_state"], "revise-or-deprecate")
            self.assertEqual(confidence_action["provenance"]["agents"], ["worker-2", "worker-3"])
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["recommendation"],
                "consider-split-review",
            )
            self.assertEqual(
                entry_update_action["split_review_suggestion"]["distinct_route_count"],
                2,
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
            self.assertEqual(snapshot_payload["event_count"], 5)
            self.assertEqual(proposal_payload["candidate_action_count"], 8)
            self.assertTrue(proposal_payload["actions"][0]["ai_decision_required"])
            self.assertIn(
                "candidate-entry-proposal",
                [action["suggested_artifact_kind"] for action in proposal_payload["actions"]],
            )


if __name__ == "__main__":
    unittest.main()
