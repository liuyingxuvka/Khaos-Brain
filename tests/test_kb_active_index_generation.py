from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.active_index import (
    ACTIVE_INDEX_POINTER_SCHEMA_VERSION,
    active_index_corruption_path,
    active_index_path,
    apply_active_index_impact,
    current_active_record_identity,
    load_active_entries,
    mark_active_index_corruption,
    rebuild_active_index,
    validate_active_index,
    validate_active_index_fast,
)
from local_kb.store import load_yaml_file, write_yaml_file
from local_kb.maintenance_migration import classify_retired_active_index_authority
from tests.test_khaos_model_native_retrieval import activate_model_native_fixture


PUBLISHER = "local_kb.lifecycle.run_incremental_sleep"


class ActiveIndexGenerationTests(unittest.TestCase):
    def test_upgrade_classifies_retired_generic_marker_without_runtime_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "kb" / "indexes" / "active-invalidated.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                json.dumps({"reason": "legacy", "item_id": "new-candidate"}) + "\n",
                encoding="utf-8",
            )
            result = classify_retired_active_index_authority(root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["impact"], "additive_pending")
            self.assertEqual(
                result["disposition"],
                "replace-with-current-immutable-generation-and-pointer",
            )

    def test_foreground_reads_pointer_bound_immutable_artifact_not_mutable_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)

            pointer = json.loads(active_index_path(root).read_text(encoding="utf-8"))
            artifact_path = root / pointer["artifact_path"]
            artifact_before = artifact_path.read_bytes()
            source_path = root / "kb" / "public" / "left-card.yaml"
            changed = load_yaml_file(source_path)
            changed["status"] = "rejected"
            write_yaml_file(source_path, changed)

            self.assertEqual(pointer["schema_version"], ACTIVE_INDEX_POINTER_SCHEMA_VERSION)
            self.assertTrue(artifact_path.is_file())
            self.assertTrue(validate_active_index_fast(root)["ok"])
            entries, snapshot = load_active_entries(root)
            self.assertIn("left-card", [entry.data["id"] for entry in entries])
            self.assertEqual(snapshot["validation_mode"], "immutable-pointer")
            self.assertEqual(artifact_path.read_bytes(), artifact_before)
            self.assertFalse(validate_active_index(root)["ok"])

    def test_exact_generation_bound_deny_removes_only_matching_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            before = json.loads(active_index_path(root).read_text(encoding="utf-8"))
            identity = current_active_record_identity(root, "left-card")
            self.assertIsNotNone(identity)

            result = apply_active_index_impact(
                root,
                impact="entry_revoke",
                entry_id="left-card",
                expected_content_digest=identity["content_digest"],
                expected_pointer_digest=identity["pointer_digest"],
                reason="verified contradiction",
                event_type="candidate-transition",
                item_id="left-card",
            )

            after = json.loads(active_index_path(root).read_text(encoding="utf-8"))
            entries, snapshot = load_active_entries(root)
            ids = [entry.data["id"] for entry in entries]
            self.assertNotIn("left-card", ids)
            self.assertIn("right-card", ids)
            self.assertIn("unrelated-card", ids)
            self.assertEqual(after["artifact_digest"], before["artifact_digest"])
            self.assertNotEqual(after["deny_digest"], before["deny_digest"])
            self.assertEqual(snapshot["effective_record_count"], 2)
            self.assertEqual(result["denied_record_count"], 1)

            with self.assertRaisesRegex(ValueError, "Exact active-index record digest"):
                apply_active_index_impact(
                    root,
                    impact="entry_revoke",
                    entry_id="right-card",
                    expected_content_digest="sha256:" + "0" * 64,
                    expected_pointer_digest=after["pointer_digest"],
                    reason="wrong digest",
                )
            self.assertEqual(
                json.loads(active_index_path(root).read_text(encoding="utf-8"))["pointer_digest"],
                after["pointer_digest"],
            )

    def test_additive_work_stays_readable_and_only_exact_current_corruption_closes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            pointer = json.loads(active_index_path(root).read_text(encoding="utf-8"))

            receipt = apply_active_index_impact(
                root,
                impact="additive_pending",
                reason="new candidate waits for the next Sleep batch",
            )
            self.assertFalse(receipt["changed"])
            self.assertEqual(
                json.loads(active_index_path(root).read_text(encoding="utf-8"))["pointer_digest"],
                pointer["pointer_digest"],
            )
            self.assertTrue(validate_active_index_fast(root)["ok"])

            marker = mark_active_index_corruption(
                root,
                expected_pointer_digest=pointer["pointer_digest"],
                reason="artifact digest failed a verified read",
                evidence={"check": "test"},
            )
            with self.assertRaisesRegex(RuntimeError, "marked corrupt"):
                load_active_entries(root)

            rebuild_active_index(root, reason="replace-corrupt-generation", publisher_id=PUBLISHER)
            active_index_corruption_path(root).write_text(
                json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self.assertTrue(validate_active_index_fast(root)["ok"])
            entries, _snapshot = load_active_entries(root)
            self.assertEqual(len(entries), 3)


if __name__ == "__main__":
    unittest.main()
