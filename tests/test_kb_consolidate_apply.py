from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from local_kb.consolidate import consolidate_history


class ConsolidateApplyModeTests(unittest.TestCase):
    def test_apply_mode_creates_candidate_for_grouped_route_actions_only(self) -> None:
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
                        "route_hint": ["work", "communication", "email"],
                        "task_summary": "Need reusable email preference guidance",
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
                        "route_hint": ["work", "communication", "email"],
                        "task_summary": "Need default reply-language card for email work",
                    },
                    "rationale": "next=new-candidate",
                    "context": {"suggested_action": "new-candidate"},
                },
                {
                    "event_id": "obs-update-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T08:15:00+00:00",
                    "source": {"kind": "task", "agent": "worker-1"},
                    "target": {
                        "kind": "task-observation",
                        "entry_ids": ["example-entry-002"],
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Release notes card needs a confidence update",
                    },
                    "rationale": "next=update-card",
                    "context": {"suggested_action": "update-card", "hit_quality": "miss"},
                },
            ]
            with history_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")

            result = consolidate_history(
                repo_root=repo_root,
                run_id="apply-20260419",
                apply_mode="new-candidates",
            )

            self.assertEqual(result["candidate_action_count"], 2)
            self.assertEqual(result["apply_mode"], "new-candidates")
            self.assertEqual(result["apply_summary"]["created_candidate_count"], 1)
            self.assertEqual(result["apply_summary"]["skipped_action_count"], 1)
            self.assertIn("snapshot_path", result["artifact_paths"])
            self.assertIn("proposal_path", result["artifact_paths"])
            self.assertIn("apply_path", result["artifact_paths"])

            created_candidate = result["apply_summary"]["created_candidates"][0]
            candidate_path = repo_root / created_candidate["entry_path"]
            self.assertTrue(candidate_path.exists())

            candidate_payload = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
            self.assertEqual(candidate_payload["status"], "candidate")
            self.assertEqual(candidate_payload["scope"], "private")
            self.assertEqual(candidate_payload["domain_path"], ["work", "communication", "email"])
            self.assertEqual(candidate_payload["source"][0]["run_id"], "apply-20260419")
            self.assertIn("auto-created scaffold", candidate_payload["use"]["guidance"])

            apply_payload = json.loads(
                (repo_root / result["artifact_paths"]["apply_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(apply_payload["created_candidate_count"], 1)
            self.assertEqual(apply_payload["skipped_actions"][0]["action_type"], "review-entry-update")

            history_events = [
                json.loads(line)
                for line in history_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(len(history_events), 4)
            self.assertEqual(history_events[-1]["event_type"], "candidate-created")
            self.assertEqual(history_events[-1]["source"]["kind"], "consolidation-apply")
            self.assertEqual(
                history_events[-1]["context"]["action_key"],
                created_candidate["action_key"],
            )

    def test_apply_mode_skips_single_observation_route_group(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "event_id": "obs-new-cand-1",
                "event_type": "observation",
                "created_at": "2026-04-19T08:09:00+00:00",
                "source": {"kind": "task", "agent": "worker-1"},
                "target": {
                    "kind": "task-observation",
                    "route_hint": ["work", "reporting", "ppt"],
                    "task_summary": "Need a reusable slide-outline card",
                },
                "rationale": "next=new-candidate",
                "context": {"suggested_action": "new-candidate"},
            }
            history_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            result = consolidate_history(
                repo_root=repo_root,
                run_id="apply-single",
                apply_mode="new-candidates",
            )

            self.assertEqual(result["candidate_action_count"], 1)
            self.assertEqual(result["apply_summary"]["created_candidate_count"], 0)
            self.assertEqual(result["apply_summary"]["skipped_action_count"], 1)
            self.assertFalse((repo_root / "kb" / "candidates").exists())
            self.assertFalse(result["actions"][0]["apply_eligibility"]["eligible"])
            self.assertIn(
                "at least 2 grouped new-candidate observations",
                result["apply_summary"]["skipped_actions"][0]["reason"],
            )


if __name__ == "__main__":
    unittest.main()
