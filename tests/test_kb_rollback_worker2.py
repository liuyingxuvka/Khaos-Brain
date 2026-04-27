from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.consolidate import consolidate_history
from local_kb.store import load_yaml_file, write_yaml_file


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / ".agents"
    / "skills"
    / "local-kb-retrieve"
    / "scripts"
    / "kb_rollback.py"
)


class KbRollbackCliTests(unittest.TestCase):
    def test_inspect_writes_manifest_and_restore_recovers_history_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)

            events = [
                {
                    "event_id": "obs-1",
                    "event_type": "observation",
                    "created_at": "2026-04-19T09:00:00+00:00",
                    "source": {"kind": "task", "agent": "worker-2"},
                    "target": {
                        "kind": "task-observation",
                        "route_hint": ["engineering", "debugging", "version-change"],
                        "task_summary": "Release notes were skipped before debugging",
                    },
                    "rationale": "retrieval=miss, next=update-card",
                    "context": {"hit_quality": "miss", "suggested_action": "update-card"},
                },
                {
                    "event_id": "cand-1",
                    "event_type": "candidate-created",
                    "created_at": "2026-04-19T09:05:00+00:00",
                    "source": {"kind": "kb-capture", "agent": "worker-2"},
                    "target": {
                        "kind": "candidate-entry",
                        "entry_id": "cand-1",
                        "domain_path": ["work", "communication", "email"],
                    },
                    "rationale": "candidate-created",
                    "context": {},
                },
            ]
            with history_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")

            consolidate_history(
                repo_root=repo_root,
                run_id="20260419T090500Z",
                emit_files=True,
            )

            inspect_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "inspect",
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    "20260419T090500Z",
                    "--write-manifest",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            manifest = json.loads(inspect_result.stdout)

            self.assertEqual(manifest["kind"], "local-kb-rollback-manifest")
            self.assertEqual(manifest["run_id"], "20260419T090500Z")
            self.assertEqual(manifest["restorable_artifact_ids"], ["history-events"])
            self.assertEqual(manifest["artifact_count"], 3)

            manifest_path = (
                repo_root
                / "kb"
                / "history"
                / "consolidation"
                / "20260419T090500Z"
                / "rollback_manifest.json"
            )
            saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(saved_manifest["restorable_artifact_count"], 1)
            snapshot_path = manifest_path.with_name("snapshot.json")
            snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))

            history_path.write_text('{"corrupted": true}\n', encoding="utf-8")

            restore_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "restore",
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    "20260419T090500Z",
                    "--artifact",
                    "history-events",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            restore_payload = json.loads(restore_result.stdout)

            self.assertTrue(restore_payload["restored"])
            self.assertEqual(restore_payload["event_count"], 2)

            restored_lines = history_path.read_text(encoding="utf-8").strip().splitlines()
            restored_events = [json.loads(line) for line in restored_lines]
            self.assertEqual(restored_events, snapshot_payload["events"])

    def test_restore_related_card_entries_recovers_previous_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            history_path = repo_root / "kb" / "history" / "events.jsonl"
            history_path.parent.mkdir(parents=True, exist_ok=True)
            model_a_path = repo_root / "kb" / "public" / "system" / "knowledge-library" / "model-a.yaml"
            model_b_path = repo_root / "kb" / "public" / "system" / "knowledge-library" / "model-b.yaml"
            write_yaml_file(
                model_a_path,
                {
                    "id": "model-a",
                    "title": "A",
                    "type": "model",
                    "scope": "public",
                    "domain_path": ["system", "knowledge-library"],
                    "cross_index": [],
                    "related_cards": [],
                    "tags": ["kb"],
                    "trigger_keywords": ["kb"],
                    "if": {"notes": "A"},
                    "then": {"notes": "A"},
                    "else": {"notes": ""},
                },
            )
            write_yaml_file(
                model_b_path,
                {
                    "id": "model-b",
                    "title": "B",
                    "type": "model",
                    "scope": "public",
                    "domain_path": ["system", "knowledge-library"],
                    "cross_index": [],
                    "related_cards": [],
                    "tags": ["kb"],
                    "trigger_keywords": ["kb"],
                    "if": {"notes": "B"},
                    "then": {"notes": "B"},
                    "else": {"notes": ""},
                },
            )
            events = [
                {
                    "event_id": f"obs-{index}",
                    "event_type": "observation",
                    "created_at": f"2026-04-20T08:0{index}:00+00:00",
                    "source": {"kind": "task", "agent": "worker-2"},
                    "target": {
                        "kind": "task-observation",
                        "entry_ids": ["model-a", "model-b"],
                        "route_hint": ["system", "knowledge-library"],
                        "task_summary": "Used A and B together",
                    },
                    "rationale": "co-used entries",
                    "context": {"hit_quality": "hit"},
                }
                for index in range(3)
            ]
            with history_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event) + "\n")

            consolidate_history(
                repo_root=repo_root,
                run_id="related-rollback-run",
                apply_mode="related-cards",
            )
            self.assertEqual(load_yaml_file(model_a_path)["related_cards"], ["model-b"])

            inspect_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "inspect",
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    "related-rollback-run",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            manifest = json.loads(inspect_result.stdout)
            self.assertIn("related-card-entries", manifest["restorable_artifact_ids"])

            restore_result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "restore",
                    "--repo-root",
                    str(repo_root),
                    "--run-id",
                    "related-rollback-run",
                    "--artifact",
                    "related-card-entries",
                    "--json",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            restore_payload = json.loads(restore_result.stdout)

            self.assertTrue(restore_payload["restored"])
            self.assertEqual(restore_payload["entry_count"], 2)
            self.assertEqual(load_yaml_file(model_a_path)["related_cards"], [])
            self.assertEqual(load_yaml_file(model_b_path)["related_cards"], [])


if __name__ == "__main__":
    unittest.main()
