from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.consolidate import consolidate_history


class ConsolidateActionStubTests(unittest.TestCase):
    def test_emit_files_writes_one_action_stub_per_grouped_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            events = [
                {
                    "event_id": "obs-update-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:05:00+00:00",
                    "source": {"kind": "task", "agent": "worker-1"},
                    "target": {
                        "kind": "task-observation",
                        "entry_ids": ["example-entry-002"],
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Release notes card missed a known remediation step",
                    },
                    "rationale": "retrieval=miss, next=update-card",
                    "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                },
                {
                    "event_id": "obs-new-cand-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:09:00+00:00",
                    "source": {"kind": "task", "agent": "worker-1"},
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
                run_id="stub-run",
                emit_files=True,
            )

            self.assertEqual(result["candidate_action_count"], 2)
            self.assertEqual(result["action_stub_count"], 2)
            self.assertEqual(
                result["action_stub_dir"],
                "kb/history/consolidation/stub-run/actions",
            )
            self.assertEqual(
                result["artifact_paths"]["action_stub_dir"],
                "kb/history/consolidation/stub-run/actions",
            )
            self.assertEqual(result["artifact_paths"]["action_stub_count"], 2)

            stub_dir = repo_root / result["action_stub_dir"]
            stub_paths = sorted(stub_dir.glob("*.json"))
            self.assertEqual(len(stub_paths), 2)

            stub_payload = json.loads(stub_paths[0].read_text(encoding="utf-8"))
            self.assertEqual(stub_payload["schema_version"], 1)
            self.assertEqual(stub_payload["kind"], "local-kb-consolidation-action-stub")
            self.assertEqual(stub_payload["run_id"], "stub-run")
            self.assertIn(stub_payload["action_type"], {"review-entry-update", "consider-new-candidate"})
            self.assertIn("priority_score", stub_payload)
            self.assertIn("event_ids", stub_payload)
            self.assertIn("routes", stub_payload)
            self.assertIn("task_summaries", stub_payload)
            self.assertIn("signals", stub_payload)
            self.assertIn("suggested_artifact_kind", stub_payload)
            self.assertIn("apply_eligibility", stub_payload)
            self.assertIn("recommended_next_step", stub_payload)
            self.assertTrue(stub_payload["ai_decision_required"])

    def test_apply_mode_also_emits_action_stub_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            events = [
                {
                    "event_id": "obs-new-cand-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:09:00+00:00",
                    "source": {"kind": "task", "agent": "worker-1"},
                    "target": {
                        "kind": "task-observation",
                        "route_hint": ["work", "reporting", "ppt"],
                        "task_summary": "Need a reusable reporting deck card",
                    },
                    "rationale": "next=new-candidate",
                    "context": {"suggested_action": "new-candidate"},
                },
                {
                    "event_id": "obs-new-cand-2",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:12:00+00:00",
                    "source": {"kind": "task", "agent": "worker-1"},
                    "target": {
                        "kind": "task-observation",
                        "route_hint": ["work", "reporting", "ppt"],
                        "task_summary": "Need a route-specific slide structure card",
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
                run_id="apply-stub-run",
                apply_mode="new-candidates",
            )

            self.assertEqual(result["apply_mode"], "new-candidates")
            self.assertEqual(result["action_stub_count"], 1)
            self.assertIn("apply_path", result["artifact_paths"])

            stub_paths = result["artifact_paths"]["action_stub_paths"]
            self.assertEqual(len(stub_paths), 1)
            stub_payload = json.loads((repo_root / stub_paths[0]).read_text(encoding="utf-8"))
            self.assertEqual(stub_payload["action_type"], "consider-new-candidate")
            self.assertEqual(stub_payload["target"]["ref"], "work/reporting/ppt")
            self.assertTrue(stub_payload["apply_eligibility"]["eligible"])
            self.assertEqual(
                stub_payload["suggested_artifact_kind"],
                "candidate-entry-proposal",
            )


if __name__ == "__main__":
    unittest.main()
