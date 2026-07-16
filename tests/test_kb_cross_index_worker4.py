from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from local_kb.consolidate import consolidate_history
from local_kb.proposals import build_proposal_report, format_proposal_report
from tests.current_runtime_helpers import activate_current_kb_runtime


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_history(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class CrossIndexMaintenanceTests(unittest.TestCase):
    def test_consolidate_surfaces_cross_index_suggestion_from_repeated_route_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            write_yaml(
                repo_root / "kb" / "public" / "system" / "knowledge-library" / "retrieval" / "model-a.yaml",
                {
                    "id": "model-a",
                    "title": "A",
                    "type": "model",
                    "scope": "public",
                    "domain_path": ["system", "knowledge-library", "retrieval"],
                    "cross_index": [],
                    "tags": ["kb"],
                    "trigger_keywords": ["kb"],
                    "if": {"notes": "A"},
                    "action": {"description": "A"},
                    "predict": {"expected_result": "A", "alternatives": []},
                    "use": {"guidance": "A"},
                    "confidence": 0.9,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )
            activate_current_kb_runtime(repo_root)

            write_history(
                repo_root / "kb" / "history" / "events.jsonl",
                [
                    {
                        "event_id": "obs-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["prompting", "done-condition"],
                            "task_summary": "Prompting route used model A",
                        },
                        "rationale": "used through prompting route",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["prompting", "done-condition"],
                            "task_summary": "Prompting route used model A again",
                        },
                        "rationale": "used through prompting route again",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-3",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:10:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Primary route used model A",
                        },
                        "rationale": "used through primary route",
                        "context": {"hit_quality": "hit"},
                    },
                ],
            )

            result = consolidate_history(repo_root=repo_root, run_id="cross-index-run", emit_files=True)

            cross_actions = [action for action in result["actions"] if action["action_type"] == "review-cross-index"]
            self.assertEqual(len(cross_actions), 1)
            action = cross_actions[0]
            self.assertEqual(action["target"]["ref"], "model-a")
            self.assertEqual(
                action["cross_index_suggestion"]["suggested_cross_index"],
                ["prompting/done-condition"],
            )
            self.assertEqual(action["cross_index_suggestion"]["usage_count"], 3)
            self.assertEqual(
                action["cross_index_suggestion"]["candidate_routes"][0]["support_count"],
                2,
            )

            stub_path = next(
                repo_root / stub_path
                for stub_path in result["artifact_paths"]["action_stub_paths"]
                if "review-cross-index-entry-model-a" in stub_path
            )
            stub_payload = json.loads(stub_path.read_text(encoding="utf-8"))
            self.assertEqual(
                stub_payload["cross_index_suggestion"]["suggested_cross_index"],
                ["prompting/done-condition"],
            )

    def test_apply_mode_cross_index_updates_yaml_and_records_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            write_yaml(
                repo_root / "kb" / "public" / "system" / "knowledge-library" / "retrieval" / "model-a.yaml",
                {
                    "id": "model-a",
                    "title": "A",
                    "type": "model",
                    "scope": "public",
                    "domain_path": ["system", "knowledge-library", "retrieval"],
                    "cross_index": ["stale/route"],
                    "tags": ["kb"],
                    "trigger_keywords": ["kb"],
                    "if": {"notes": "A"},
                    "action": {"description": "A"},
                    "predict": {"expected_result": "A", "alternatives": []},
                    "use": {"guidance": "A"},
                    "confidence": 0.9,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )
            activate_current_kb_runtime(repo_root)

            write_history(
                repo_root / "kb" / "history" / "events.jsonl",
                [
                    {
                        "event_id": "obs-1",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:00:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["prompting", "done-condition"],
                            "task_summary": "Prompting route used model A",
                        },
                        "rationale": "prompting route",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["prompting", "done-condition"],
                            "task_summary": "Prompting route used model A again",
                        },
                        "rationale": "prompting route again",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-3",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:10:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["codex", "workflow", "postflight"],
                            "task_summary": "Workflow route used model A",
                        },
                        "rationale": "workflow route",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-4",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:15:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["codex", "workflow", "postflight"],
                            "task_summary": "Workflow route used model A again",
                        },
                        "rationale": "workflow route again",
                        "context": {"hit_quality": "hit"},
                    },
                ],
            )

            result = consolidate_history(
                repo_root=repo_root,
                run_id="cross-index-apply-run",
                apply_mode="cross-index",
            )

            self.assertEqual(result["apply_mode"], "cross-index")
            self.assertEqual(result["apply_summary"]["updated_entry_count"], 1)

            model_a = yaml.safe_load(
                (repo_root / "kb" / "public" / "system" / "knowledge-library" / "retrieval" / "model-a.yaml")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(
                model_a["cross_index"],
                ["stale/route", "codex/workflow/postflight", "prompting/done-condition"],
            )

            history_events = [
                json.loads(line)
                for line in (repo_root / "kb" / "history" / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(history_events[-1]["event_type"], "cross-index-updated")

    def test_proposal_report_human_output_includes_cross_index_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            actions_dir = repo_root / "kb" / "history" / "consolidation" / "cross-index-report" / "actions"
            actions_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 1,
                "kind": "local-kb-consolidation-action-stub",
                "run_id": "cross-index-report",
                "generated_at": "2026-04-20T10:00:00+00:00",
                "action_key": "review-cross-index::entry::model-a",
                "action_type": "review-cross-index",
                "target": {"kind": "entry", "ref": "model-a"},
                "priority_score": 6,
                "event_count": 4,
                "event_ids": ["obs-1", "obs-2", "obs-3", "obs-4"],
                "routes": ["prompting/done-condition", "codex/workflow/postflight"],
                "task_summaries": ["Used model A through two alternate routes"],
                "signals": {"observed_route_support": {"prompting/done-condition": 2}},
                "suggested_artifact_kind": "cross-index-update-proposal",
                "apply_eligibility": {
                    "eligible": True,
                    "supported_mode": "cross-index",
                    "reason": "Repeated route evidence suggests stable alternate retrieval paths for this entry.",
                },
                "recommended_next_step": "Inspect route evidence for model-a and decide whether its stable alternate cross-index routes should change.",
                "ai_decision_required": True,
                "cross_index_suggestion": {
                    "suggested_cross_index": [
                        "codex/workflow/postflight",
                        "prompting/done-condition",
                    ]
                },
            }
            (actions_dir / "001-review-cross-index-entry-model-a.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            report = build_proposal_report(repo_root, run_id="cross-index-report")
            text = format_proposal_report(report)

            self.assertIn("cross_index=codex/workflow/postflight,prompting/done-condition", text)


if __name__ == "__main__":
    unittest.main()
