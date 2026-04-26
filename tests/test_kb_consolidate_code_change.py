from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.consolidate import consolidate_history


class ConsolidateCodeChangeTests(unittest.TestCase):
    def test_code_change_observation_becomes_review_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "event_id": "code-1",
                "event_type": "observation",
                "created_at": "2026-04-20T09:00:00+00:00",
                "source": {"kind": "task", "agent": "worker-9"},
                "target": {
                    "kind": "task-observation",
                    "route_hint": ["system", "knowledge-library", "maintenance"],
                    "task_summary": "Maintenance flow needs a code-level eligibility guard",
                },
                "rationale": "next=code-change",
                "context": {
                    "suggested_action": "code-change",
                    "predictive_observation": {
                        "scenario": "A maintenance workflow keeps surfacing broad eligible routes.",
                        "action_taken": "Add a narrower code-level eligibility rule.",
                        "observed_result": "The maintenance apply path becomes safer.",
                        "operational_use": "Use a code change proposal rather than a card update for maintenance logic fixes.",
                    },
                },
            }
            history_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            result = consolidate_history(repo_root=repo_root, run_id="code-change-run")

            self.assertEqual(result["candidate_action_count"], 1)
            action = result["actions"][0]
            self.assertEqual(action["action_type"], "review-code-change")
            self.assertEqual(action["target"], {"kind": "route", "ref": "system/knowledge-library/maintenance"})
            self.assertEqual(action["suggested_artifact_kind"], "code-change-proposal")
            self.assertEqual(
                action["recommended_next_step"],
                "Inspect route system/knowledge-library/maintenance and decide whether KB tooling, prompts, or maintenance code need a code change.",
            )

    def test_code_change_without_predictive_evidence_also_requests_evidence_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "event_id": "code-2",
                "event_type": "observation",
                "created_at": "2026-04-20T09:05:00+00:00",
                "source": {"kind": "task", "agent": "worker-9"},
                "target": {
                    "kind": "task-observation",
                    "task_summary": "Maintenance tool likely needs a code tweak",
                },
                "rationale": "next=code-change",
                "context": {
                    "suggested_action": "code-change",
                },
            }
            history_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            result = consolidate_history(repo_root=repo_root, run_id="code-change-missing-evidence")
            action_types = sorted(action["action_type"] for action in result["actions"])
            self.assertEqual(action_types, ["review-code-change", "review-observation-evidence"])
            code_action = next(action for action in result["actions"] if action["action_type"] == "review-code-change")
            self.assertEqual(code_action["target"]["kind"], "task")

    def test_skill_use_candidate_signal_also_requests_code_change_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            event = {
                "event_id": "skill-1",
                "event_type": "observation",
                "created_at": "2026-04-20T09:10:00+00:00",
                "source": {"kind": "task", "agent": "worker-9"},
                "target": {
                    "kind": "task-observation",
                    "route_hint": ["codex", "skill-use", "job-application-workflow"],
                    "task_summary": "Skill usage evidence shows the skill prompt should name a fallback earlier",
                },
                "rationale": "next=new-candidate",
                "context": {
                    "suggested_action": "new-candidate",
                    "predictive_observation": {
                        "scenario": "A task-critical Skill works only after a repeated fallback is discovered.",
                        "action_taken": "Record the skill-use lesson and surface it as a mechanism proposal.",
                        "observed_result": "The card lesson and Skill maintenance proposal stay on their existing paths.",
                        "operational_use": "Review the Skill prompt when repeated skill-use evidence shows a fallback should happen earlier.",
                        "reuse_judgment": "Reusable for Skill prompt maintenance.",
                    },
                },
            }
            history_path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            result = consolidate_history(repo_root=repo_root, run_id="skill-use-code-review")
            action_types = sorted(action["action_type"] for action in result["actions"])
            self.assertEqual(action_types, ["consider-new-candidate", "review-code-change"])
            code_action = next(action for action in result["actions"] if action["action_type"] == "review-code-change")
            self.assertEqual(code_action["target"], {"kind": "route", "ref": "codex/skill-use/job-application-workflow"})
            self.assertIn("skill-maintenance-signal", code_action["reasons"])


if __name__ == "__main__":
    unittest.main()
