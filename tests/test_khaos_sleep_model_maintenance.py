from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from local_kb import model_maintenance
from local_kb.active_index import load_active_index
from local_kb.logicguard_models import (
    GroundedModelRelation,
    canonical_digest,
    load_authority_generation,
    read_exact_mesh,
)
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.model_projection import ProjectionValidationError, binding_from_projection
from local_kb.store import load_yaml_file


def card(card_id: str, *, declared_scope: str = "public", result: str = "A bounded result") -> dict:
    return {
        "id": card_id,
        "title": f"Sleep model {card_id}",
        "type": "model",
        "scope": declared_scope,
        "domain_path": ["system", "sleep"],
        "cross_index": [],
        "related_cards": ["must-not-become-an-edge"],
        "tags": [card_id],
        "trigger_keywords": [card_id],
        "if": {"notes": "When Sleep reviews the model."},
        "action": {"description": "Commit one exact model revision."},
        "predict": {"expected_result": result, "alternatives": []},
        "use": {"guidance": "Read the exact model and its gaps."},
        "confidence": 0.8,
        "source": [{"origin": "direct user instruction", "date": "2026-07-14"}],
        "status": "candidate" if declared_scope == "private" else "trusted",
        "updated_at": "2026-07-14",
        "decision_deadline": "2026-07-21T00:00:00+00:00",
        "required_skills": ["logicguard"],
    }


def grounding() -> dict:
    return {
        "origin_kind": "user_attestation",
        "source_id": "test:sleep:left-right",
        "content_hash": "sha256:" + canonical_digest("sleep-left-right"),
        "actor": "test",
    }


class KhaosSleepModelMaintenanceTests(unittest.TestCase):
    def test_explicit_sleep_upsert_directly_replaces_one_raw_candidate_without_fallback_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = publish_sleep_model_generation(root, reason="test:baseline")
            self.assertTrue(baseline["ok"], baseline)
            raw_path = root / "kb" / "candidates" / "late.yaml"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw = card("late", declared_scope="private")
            raw_path.write_text(
                yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ProjectionValidationError,
                "schema is missing or unsupported",
            ):
                publish_sleep_model_generation(root, reason="test:unnamed-residual")

            repaired = publish_sleep_model_generation(
                root,
                reason="test:explicit-direct-to-current",
                card_upserts={"kb/candidates/late.yaml": raw},
            )

            self.assertTrue(repaired["ok"], repaired)
            projected = load_yaml_file(raw_path)
            self.assertEqual(
                projected["projection_schema_version"],
                "khaos-brain.card-projection.v1",
            )
            self.assertEqual(projected["authority_scope"], "candidates")

    def test_no_delta_generation_deep_validates_one_batch_not_one_mesh_per_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = publish_sleep_model_generation(
                root,
                reason="test:batch-baseline",
                card_upserts={
                    "kb/public/left.yaml": card("left"),
                    "kb/public/right.yaml": card("right"),
                    "kb/candidates/private.yaml": card(
                        "private",
                        declared_scope="private",
                    ),
                },
            )
            self.assertTrue(created["ok"], created)
            with patch(
                "local_kb.model_maintenance.validate_card_projections",
                wraps=model_maintenance.validate_card_projections,
            ) as batch_validator:
                result = publish_sleep_model_generation(
                    root,
                    reason="test:batch-no-delta",
                    refresh_index_on_no_delta=False,
                )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "no_delta")
            self.assertEqual(batch_validator.call_count, 1)
            self.assertEqual(len(batch_validator.call_args.args[1]), 3)

    def test_no_delta_generation_can_defer_index_validation_to_the_final_sleep_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = publish_sleep_model_generation(root, reason="test:baseline")
            self.assertTrue(baseline["ok"], baseline)
            with patch(
                "local_kb.model_maintenance.validate_active_index",
                side_effect=AssertionError("the final Sleep owner has not run yet"),
            ):
                deferred = publish_sleep_model_generation(
                    root,
                    reason="test:deferred-index-validation",
                    refresh_index_on_no_delta=False,
                    validate_index_on_no_delta=False,
                )
            self.assertTrue(deferred["ok"], deferred)
            self.assertTrue(deferred["index_validation"]["deferred"])

    def test_empty_library_publishes_a_valid_zero_model_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = publish_sleep_model_generation(root, reason="test:empty")
            self.assertTrue(result["ok"], result)
            generation = load_authority_generation(root)
            self.assertEqual(generation["projection_count"], 0)
            self.assertEqual(generation["scope_meshes"], {})
            self.assertEqual(load_active_index(root)["indexed_record_count"], 0)

    def test_sleep_upserts_models_and_preserves_projection_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = publish_sleep_model_generation(
                root,
                reason="test:create",
                card_upserts={
                    "kb/public/left.yaml": card("left"),
                    "kb/candidates/private.yaml": card("private", declared_scope="private"),
                },
            )
            self.assertTrue(result["ok"], result)
            public = load_yaml_file(root / "kb" / "public" / "left.yaml")
            private = load_yaml_file(root / "kb" / "candidates" / "private.yaml")
            self.assertEqual(public["required_skills"], ["logicguard"])
            self.assertEqual(private["decision_deadline"], "2026-07-21T00:00:00+00:00")
            self.assertEqual(public["related_cards"], [])
            self.assertEqual(private["authority_scope"], "candidates")
            self.assertIn("evidence", public["logicguard_open_role_gaps"])
            diagnostics = result["receipt"]["model_diagnostics"]
            self.assertTrue(diagnostics["all_gaps_dispositioned"])
            self.assertEqual(
                diagnostics["reviewed_gap_count"],
                len(diagnostics["gap_ledger"]),
            )
            evidence_gap = next(
                item
                for item in diagnostics["gap_ledger"]
                if item["card_id"] == "left" and item["gap_kind"] == "evidence"
            )
            self.assertEqual(
                evidence_gap["disposition"],
                "open-awaiting-grounded-input",
            )
            self.assertTrue(evidence_gap["revision_id"])
            self.assertEqual(
                evidence_gap["owner"],
                "local_kb.lifecycle.run_incremental_sleep",
            )

    def test_model_revision_moves_old_relation_to_revalidation_queue(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            created = publish_sleep_model_generation(
                root,
                reason="test:create-related",
                card_upserts={
                    "kb/public/left.yaml": card("left"),
                    "kb/public/right.yaml": card("right"),
                },
            )
            self.assertTrue(created["ok"], created)
            left = binding_from_projection(load_yaml_file(root / "kb" / "public" / "left.yaml"))
            right = binding_from_projection(load_yaml_file(root / "kb" / "public" / "right.yaml"))
            linked = publish_sleep_model_generation(
                root,
                reason="test:link",
                relations=(
                    GroundedModelRelation(
                        relation_id="edge-left-right",
                        source=left,
                        target=right,
                        edge_type="supports",
                        explanation="User-grounded relation.",
                        provenance=(grounding(),),
                    ),
                ),
            )
            self.assertTrue(linked["ok"], linked)
            linked_left = binding_from_projection(load_yaml_file(root / "kb" / "public" / "left.yaml"))
            self.assertEqual(len(read_exact_mesh(root, linked_left).cross_model_edges), 1)

            changed = card("left", result="A revised bounded result")
            updated = publish_sleep_model_generation(
                root,
                reason="test:update-left",
                card_upserts={"kb/public/left.yaml": changed},
            )
            self.assertTrue(updated["ok"], updated)
            current_left = binding_from_projection(load_yaml_file(root / "kb" / "public" / "left.yaml"))
            mesh = read_exact_mesh(root, current_left)
            self.assertEqual(len(mesh.cross_model_edges), 0)
            self.assertEqual(
                mesh.metadata["unresolved_relationships"][0]["disposition"],
                "revalidation-required-after-model-revision",
            )

    def test_failed_index_publication_restores_prior_generation_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = publish_sleep_model_generation(
                root,
                reason="test:baseline",
                card_upserts={"kb/public/left.yaml": card("left")},
            )
            self.assertTrue(first["ok"], first)
            pointer_before = load_authority_generation(root)
            projection_before = load_yaml_file(root / "kb" / "public" / "left.yaml")
            changed = copy.deepcopy(card("left"))
            changed["predict"]["expected_result"] = "A failed replacement must roll back."
            with patch(
                "local_kb.model_maintenance.rebuild_active_index",
                side_effect=RuntimeError("forced index failure"),
            ):
                failed = publish_sleep_model_generation(
                    root,
                    reason="test:forced-failure",
                    card_upserts={"kb/public/left.yaml": changed},
                )
            self.assertFalse(failed["ok"])
            self.assertEqual(failed["status"], "rolled_back")
            self.assertTrue(failed["rollback"]["ok"])
            self.assertEqual(load_authority_generation(root), pointer_before)
            self.assertEqual(load_yaml_file(root / "kb" / "public" / "left.yaml"), projection_before)


if __name__ == "__main__":
    unittest.main()
