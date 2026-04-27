from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from local_kb.consolidate import consolidate_history
from local_kb.proposals import build_proposal_report, format_proposal_report


def write_yaml(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def write_history(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


class RelatedCardMaintenanceTests(unittest.TestCase):
    def test_consolidate_surfaces_related_card_suggestion_from_repeated_co_use(self) -> None:
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
            write_yaml(
                repo_root / "kb" / "public" / "engineering" / "debugging" / "version-change" / "model-b.yaml",
                {
                    "id": "model-b",
                    "title": "B",
                    "type": "heuristic",
                    "scope": "public",
                    "domain_path": ["engineering", "debugging", "version-change"],
                    "cross_index": [],
                    "tags": ["debugging"],
                    "trigger_keywords": ["upgrade"],
                    "if": {"notes": "B"},
                    "action": {"description": "B"},
                    "predict": {"expected_result": "B", "alternatives": []},
                    "use": {"guidance": "B"},
                    "confidence": 0.88,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )

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
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Used both entry A and entry B together",
                        },
                        "rationale": "used together",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T08:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["repository", "usage", "local-kb-retrieve"],
                            "task_summary": "Used A and B together again",
                        },
                        "rationale": "used together again",
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
                            "task_summary": "Used A by itself",
                        },
                        "rationale": "used A alone",
                        "context": {"hit_quality": "hit"},
                    },
                ],
            )

            result = consolidate_history(repo_root=repo_root, run_id="related-run", emit_files=True)

            related_actions = [action for action in result["actions"] if action["action_type"] == "review-related-cards"]
            self.assertEqual(len(related_actions), 2)
            action_a = next(action for action in related_actions if action["target"]["ref"] == "model-a")
            self.assertEqual(
                action_a["related_card_suggestion"]["suggested_related_cards"],
                ["model-b"],
            )
            self.assertEqual(action_a["related_card_suggestion"]["usage_count"], 3)
            self.assertEqual(
                action_a["related_card_suggestion"]["candidate_links"][0]["support_count"],
                2,
            )

            stub_payload = next(
                json.loads((repo_root / stub_path).read_text(encoding="utf-8"))
                for stub_path in result["artifact_paths"]["action_stub_paths"]
                if json.loads((repo_root / stub_path).read_text(encoding="utf-8"))["action_key"]
                == "review-related-cards::entry::model-a"
            )
            self.assertEqual(
                stub_payload["related_card_suggestion"]["suggested_related_cards"],
                ["model-b"],
            )

    def test_apply_mode_related_cards_updates_yaml_and_records_history(self) -> None:
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
                    "related_cards": ["model-c"],
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
            write_yaml(
                repo_root / "kb" / "public" / "engineering" / "debugging" / "version-change" / "model-b.yaml",
                {
                    "id": "model-b",
                    "title": "B",
                    "type": "heuristic",
                    "scope": "public",
                    "domain_path": ["engineering", "debugging", "version-change"],
                    "cross_index": [],
                    "tags": ["debugging"],
                    "trigger_keywords": ["upgrade"],
                    "if": {"notes": "B"},
                    "action": {"description": "B"},
                    "predict": {"expected_result": "B", "alternatives": []},
                    "use": {"guidance": "B"},
                    "confidence": 0.88,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )
            write_yaml(
                repo_root / "kb" / "public" / "work" / "communication" / "email" / "model-c.yaml",
                {
                    "id": "model-c",
                    "title": "C",
                    "type": "preference",
                    "scope": "private",
                    "domain_path": ["work", "communication", "email"],
                    "cross_index": [],
                    "tags": ["email"],
                    "trigger_keywords": ["email"],
                    "if": {"notes": "C"},
                    "action": {"description": "C"},
                    "predict": {"expected_result": "C", "alternatives": []},
                    "use": {"guidance": "C"},
                    "confidence": 0.85,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )

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
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Used A and B together",
                        },
                        "rationale": "used together",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["repository", "usage", "local-kb-retrieve"],
                            "task_summary": "Used A and B together again",
                        },
                        "rationale": "used together again",
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
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Used A alone once",
                        },
                        "rationale": "used A alone",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-4",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:12:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Used A alone twice",
                        },
                        "rationale": "used A alone again",
                        "context": {"hit_quality": "hit"},
                    },
                ],
            )

            result = consolidate_history(
                repo_root=repo_root,
                run_id="related-apply-run",
                apply_mode="related-cards",
            )

            self.assertEqual(result["apply_mode"], "related-cards")
            self.assertEqual(result["apply_summary"]["updated_entry_count"], 2)

            model_a = yaml.safe_load(
                (repo_root / "kb" / "public" / "system" / "knowledge-library" / "retrieval" / "model-a.yaml")
                .read_text(encoding="utf-8")
            )
            model_b = yaml.safe_load(
                (repo_root / "kb" / "public" / "engineering" / "debugging" / "version-change" / "model-b.yaml")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(model_a["related_cards"], ["model-b"])
            self.assertEqual(model_b["related_cards"], ["model-a"])

            history_events = [
                json.loads(line)
                for line in (repo_root / "kb" / "history" / "events.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(history_events[-1]["event_type"], "related-cards-updated")
            self.assertEqual(history_events[-2]["event_type"], "related-cards-updated")

    def test_selected_action_keys_apply_only_the_approved_related_card_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            model_a_path = repo_root / "kb" / "public" / "system" / "knowledge-library" / "retrieval" / "model-a.yaml"
            model_b_path = repo_root / "kb" / "public" / "engineering" / "debugging" / "version-change" / "model-b.yaml"
            write_yaml(
                model_a_path,
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
            write_yaml(
                model_b_path,
                {
                    "id": "model-b",
                    "title": "B",
                    "type": "heuristic",
                    "scope": "public",
                    "domain_path": ["engineering", "debugging", "version-change"],
                    "cross_index": [],
                    "tags": ["debugging"],
                    "trigger_keywords": ["upgrade"],
                    "if": {"notes": "B"},
                    "action": {"description": "B"},
                    "predict": {"expected_result": "B", "alternatives": []},
                    "use": {"guidance": "B"},
                    "confidence": 0.88,
                    "status": "trusted",
                    "updated_at": "2026-04-20",
                },
            )

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
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["system", "knowledge-library", "retrieval"],
                            "task_summary": "Used A and B together",
                        },
                        "rationale": "used together",
                        "context": {"hit_quality": "hit"},
                    },
                    {
                        "event_id": "obs-2",
                        "event_type": "observation",
                        "created_at": "2026-04-20T09:05:00+00:00",
                        "source": {"kind": "task", "agent": "worker-1"},
                        "target": {
                            "kind": "task-observation",
                            "entry_ids": ["model-a", "model-b"],
                            "route_hint": ["repository", "usage", "local-kb-retrieve"],
                            "task_summary": "Used A and B together again",
                        },
                        "rationale": "used together again",
                        "context": {"hit_quality": "hit"},
                    },
                ],
            )

            result = consolidate_history(
                repo_root=repo_root,
                run_id="related-selected-apply-run",
                apply_mode="related-cards",
                selected_action_keys=["review-related-cards::entry::model-a"],
            )

            self.assertEqual(result["apply_summary"]["updated_entry_count"], 1)
            self.assertEqual(result["apply_summary"]["action_selection"]["matched_action_count"], 1)
            self.assertEqual(
                result["apply_summary"]["action_selection"]["unselected_apply_eligible_action_count"],
                1,
            )
            model_a = yaml.safe_load(model_a_path.read_text(encoding="utf-8"))
            model_b = yaml.safe_load(model_b_path.read_text(encoding="utf-8"))
            self.assertEqual(model_a["related_cards"], ["model-b"])
            self.assertNotIn("related_cards", model_b)

    def test_proposal_report_human_output_includes_related_card_hint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            actions_dir = repo_root / "kb" / "history" / "consolidation" / "related-report" / "actions"
            actions_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": 1,
                "kind": "local-kb-consolidation-action-stub",
                "run_id": "related-report",
                "generated_at": "2026-04-20T10:00:00+00:00",
                "action_key": "review-related-cards::entry::model-a",
                "action_type": "review-related-cards",
                "target": {"kind": "entry", "ref": "model-a"},
                "priority_score": 6,
                "event_count": 3,
                "event_ids": ["obs-1", "obs-2", "obs-3"],
                "routes": ["system/knowledge-library/retrieval"],
                "task_summaries": ["Used A and B together"],
                "signals": {"partner_support": {"model-b": 2}},
                "suggested_artifact_kind": "related-card-update-proposal",
                "apply_eligibility": {"eligible": True, "supported_mode": "related-cards", "reason": "Repeated co-use suggests a stable direct related-card link set."},
                "recommended_next_step": "Inspect co-used entry evidence for model-a and decide whether its top direct related-card links should change.",
                "ai_decision_required": True,
                "related_card_suggestion": {
                    "entry_id": "model-a",
                    "suggested_related_cards": ["model-b"],
                    "recommendation": "update-related-cards",
                },
            }
            (actions_dir / "related.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            report = build_proposal_report(repo_root, run_id="related-report")
            human = format_proposal_report(report)

            self.assertEqual(report["stubs"][0]["related_card_suggestion"]["suggested_related_cards"], ["model-b"])
            self.assertIn("related_cards=model-b", human)


if __name__ == "__main__":
    unittest.main()
