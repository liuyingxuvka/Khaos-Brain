from __future__ import annotations

import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.logicguard_models import (
    GroundedModelRelation,
    LogicGuardBinding,
    canonical_digest,
    commit_card_model,
    commit_scope_mesh,
)
from local_kb.model_projection import (
    ProjectionValidationError,
    active_index_binding_record,
    load_card_projection,
    project_card,
    projection_digest,
    validate_card_projection,
    write_card_projection_atomic,
)


def card(card_id: str, *, scope: str = "public") -> dict:
    return {
        "id": card_id,
        "title": f"Projection {card_id}",
        "type": "model",
        "scope": scope,
        "domain_path": ["system", "knowledge-library"],
        "cross_index": ["codex/workflow/retrieval"],
        "related_cards": ["legacy-unverified-neighbor"],
        "tags": ["projection"],
        "trigger_keywords": ["projection"],
        "if": {"notes": "When an exact model projection is required."},
        "action": {"description": "Read the deterministic projection."},
        "predict": {
            "expected_result": "The displayed card matches one exact model revision.",
            "alternatives": [
                {"when": "The projection is tampered", "result": "Validation fails visibly."}
            ],
        },
        "use": {"guidance": "Use the projection only after exact validation."},
        "confidence": 0.9,
        "source": [{"origin": "direct user instruction", "date": dt.date(2026, 7, 14)}],
        "status": "trusted",
        "updated_at": dt.date(2026, 7, 14),
        "then": {"guidance": "retired authority must not survive"},
    }


def grounding(label: str) -> dict:
    return {
        "origin_kind": "user_attestation",
        "source_id": f"projection:{label}",
        "content_hash": "sha256:" + canonical_digest(label),
        "actor": "test",
    }


def build_projection(root: Path, card_id: str = "card-a", *, scope: str = "public") -> tuple[dict, LogicGuardBinding]:
    committed = commit_card_model(
        root,
        card(card_id, scope=scope),
        authority_scope=scope,
        expected_revision=None,
        idempotency_key=f"model:{card_id}",
        actor="test",
        source_reference=f"kb/{scope}/{card_id}.yaml",
    )
    mesh = commit_scope_mesh(
        root,
        authority_scope=scope,
        model_bindings=(committed.binding,),
        expected_revision=None,
        idempotency_key=f"mesh:{scope}:{card_id}",
        actor="test",
    )
    binding = mesh.bindings[0]
    return project_card(root, binding, authority_generation_id="generation:test"), binding


class KhaosModelProjectionTests(unittest.TestCase):
    def test_projection_is_deterministic_and_exactly_validated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, binding = build_projection(root)
            self.assertEqual(
                projection,
                project_card(root, binding, authority_generation_id="generation:test"),
            )
            validation = validate_card_projection(root, projection)
            self.assertTrue(validation["ok"])
            self.assertEqual(validation["projection_digest"], projection["projection_digest"])
            self.assertEqual(projection["source"][0]["date"], "2026-07-14")
            self.assertEqual(projection["updated_at"], "2026-07-14")

    def test_human_fields_are_derived_and_retired_authority_does_not_survive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection, _binding = build_projection(Path(directory))
            self.assertEqual(projection["if"]["notes"], "When an exact model projection is required.")
            self.assertEqual(projection["action"]["description"], "Read the deterministic projection.")
            self.assertEqual(
                projection["predict"]["expected_result"],
                "The displayed card matches one exact model revision.",
            )
            self.assertEqual(projection["use"]["guidance"], "Use the projection only after exact validation.")
            self.assertEqual(projection["related_cards"], [])
            self.assertNotIn("then", projection)

    def test_grounded_mesh_relation_is_the_only_source_of_related_cards(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = commit_card_model(
                root,
                card("left"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="left",
                actor="test",
            )
            right = commit_card_model(
                root,
                card("right"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="right",
                actor="test",
            )
            mesh = commit_scope_mesh(
                root,
                authority_scope="public",
                model_bindings=(left.binding, right.binding),
                expected_revision=None,
                idempotency_key="mesh-related",
                actor="test",
                relations=(
                    GroundedModelRelation(
                        relation_id="edge-left-right",
                        source=left.binding,
                        target=right.binding,
                        edge_type="supports",
                        explanation="Explicitly grounded relation.",
                        provenance=(grounding("left-right"),),
                    ),
                ),
            )
            projections = {
                item.model_id: project_card(
                    root,
                    item,
                    authority_generation_id="generation:related",
                )
                for item in mesh.bindings
            }
            self.assertEqual(projections[left.binding.model_id]["related_cards"], ["right"])
            self.assertEqual(projections[right.binding.model_id]["related_cards"], ["left"])

    def test_digest_tampering_and_recomputed_semantic_tampering_both_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, _binding = build_projection(root)
            tampered = copy.deepcopy(projection)
            tampered["predict"]["expected_result"] = "Fabricated projection text."
            with self.assertRaisesRegex(ProjectionValidationError, "digest mismatch"):
                validate_card_projection(root, tampered)
            tampered["projection_digest"] = projection_digest(tampered)
            with self.assertRaisesRegex(ProjectionValidationError, "differs from"):
                validate_card_projection(root, tampered)

    def test_missing_model_node_block_or_mesh_revision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, _binding = build_projection(root)
            for field, value in (
                ("logicguard_revision_id", "rev-" + "0" * 64),
                ("logicguard_node_id", "missing-node"),
                ("logicguard_block_id", "missing-block"),
                ("logicguard_mesh_revision_id", "mesh-rev-" + "0" * 64),
            ):
                broken = copy.deepcopy(projection)
                broken[field] = value
                broken["projection_digest"] = projection_digest(broken)
                with self.assertRaises(ProjectionValidationError, msg=field):
                    validate_card_projection(root, broken)

    def test_atomic_write_roundtrip_and_failed_replace_preserves_prior_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            projection, _binding = build_projection(root)
            path = root / "kb" / "public" / "system" / "card-a.yaml"
            write_card_projection_atomic(root, path, projection)
            self.assertEqual(load_card_projection(root, path), projection)
            before = path.read_bytes()
            with patch("local_kb.model_projection.os.replace", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    write_card_projection_atomic(root, path, projection)
            self.assertEqual(path.read_bytes(), before)

    def test_projection_path_scope_blocks_public_private_crossing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_projection, _binding = build_projection(root, "private-card", scope="private")
            public_path = root / "kb" / "public" / "private-card.yaml"
            with self.assertRaisesRegex(ProjectionValidationError, "differs from authority scope"):
                write_card_projection_atomic(root, public_path, private_projection)

    def test_active_index_binding_record_contains_only_exact_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            projection, _binding = build_projection(Path(directory))
            record = active_index_binding_record(projection)
            self.assertEqual(record["authority_scope"], "public")
            self.assertEqual(record["projection_digest"], projection["projection_digest"])
            self.assertTrue(record["logicguard_revision_id"].startswith("rev-"))
            self.assertTrue(record["logicguard_mesh_revision_id"].startswith("mesh-rev-"))


if __name__ == "__main__":
    unittest.main()
