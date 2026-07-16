from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from logicguard import MeshNodeOverride, MeshSimulationDelta, QualifiedNodeRef
from logicguard.model_store import TransactionConflictError

from local_kb.logicguard_models import (
    AuthorityScopeError,
    ExactBindingError,
    GroundedModelRelation,
    LogicGuardBinding,
    MIN_LOGICGUARD_VERSION,
    UngroundedRelationshipError,
    build_predictive_argument_model,
    canonical_digest,
    commit_card_model,
    commit_scope_mesh,
    logicguard_dependency_preflight,
    materialize_bound_neighborhood,
    model_id_for_card,
    model_store_root,
    open_model_store,
    read_exact_model,
    simulate_bound_mesh,
)


def card(card_id: str, *, scope: str = "public", evidence: object = None) -> dict:
    payload = {
        "id": card_id,
        "title": f"Prediction {card_id}",
        "type": "heuristic",
        "scope": scope,
        "domain_path": ["engineering", "testing"],
        "cross_index": ["codex/workflow/testing"],
        "tags": ["testing"],
        "trigger_keywords": ["test"],
        "if": {"notes": "When the current behavior is under test."},
        "action": {"description": "Use the model-first route."},
        "predict": {
            "expected_result": f"The {card_id} outcome remains explainable.",
            "alternatives": [
                {"when": "The model is bypassed", "result": "The outcome becomes less auditable."}
            ],
        },
        "use": {"guidance": "Inspect the exact model before acting."},
        "confidence": 0.8,
        "source": [{"origin": "direct user instruction", "date": "2026-07-14"}],
        "status": "trusted",
        "updated_at": "2026-07-14",
        "related_cards": ["legacy-neighbor"],
    }
    if evidence is not None:
        payload["evidence"] = evidence
    return payload


def grounding(label: str) -> dict:
    return {
        "origin_kind": "user_attestation",
        "source_id": f"test:{label}",
        "content_hash": "sha256:" + canonical_digest(label),
        "source_reference": "tests/test_khaos_logicguard_models.py",
        "actor": "test",
    }


class KhaosLogicGuardModelsTests(unittest.TestCase):
    def test_dependency_preflight_binds_real_current_logicguard(self) -> None:
        result = logicguard_dependency_preflight()
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(
            tuple(int(item) for item in result["version"].split(".")),
            tuple(int(item) for item in MIN_LOGICGUARD_VERSION.split(".")),
        )
        self.assertEqual(Path(result["origin"]).parts[-2:], ("logicguard", "__init__.py"))
        self.assertEqual(result["model_store_schema"], "logicguard.model-store.v1")
        self.assertEqual(result["mesh_schema"], "logicguard.model-mesh.v1")
        self.assertTrue(result["mesh_store_tool_fingerprint"].startswith("sha256:"))

    def test_argument_block_is_deterministic_and_missing_roles_are_explicit(self) -> None:
        source = card("model-a")
        first = build_predictive_argument_model(source, authority_scope="public")
        second = build_predictive_argument_model(source, authority_scope="public")
        self.assertEqual(first.canonical_dict(), second.canonical_dict())
        self.assertEqual(first.id, model_id_for_card("model-a"))
        self.assertEqual(first.root_claim, "claim-root")
        self.assertIn("card-argument", first.blocks)
        self.assertEqual(first.nodes["context"].type, "Context")
        self.assertEqual(first.nodes["action"].type, "Method")
        self.assertEqual(first.nodes["claim-root"].type, "Claim")
        self.assertNotIn("evidence-1", first.nodes)
        self.assertEqual(
            set(first.metadata["open_role_gaps"]),
            {"evidence", "warrant", "assumption", "opposition"},
        )
        self.assertEqual(first.metadata["legacy_related_card_candidates"], ["legacy-neighbor"])
        self.assertTrue(all(edge.id for edge in first.edges))

    def test_explicit_evidence_requires_and_preserves_typed_provenance(self) -> None:
        model = build_predictive_argument_model(
            card(
                "model-evidence",
                evidence={
                    "text": "A bounded test observed the expected result.",
                    "origin": "test result",
                    "source_id": "suite:model-evidence",
                },
            ),
            authority_scope="public",
        )
        evidence = model.nodes["evidence-1"]
        self.assertEqual(evidence.type, "Evidence")
        self.assertEqual(evidence.provenance[0].origin_kind.value, "test_result")
        self.assertNotIn("evidence", model.metadata["open_role_gaps"])

    def test_scoped_stores_are_physically_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertNotEqual(model_store_root(root, "public"), model_store_root(root, "private"))
            public = commit_card_model(
                root,
                card("same-id", scope="public"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="public-first",
                actor="test",
            )
            private = commit_card_model(
                root,
                card("same-id", scope="private"),
                authority_scope="private",
                expected_revision=None,
                idempotency_key="private-first",
                actor="test",
            )
            self.assertEqual(public.binding.model_id, private.binding.model_id)
            self.assertEqual(len(open_model_store(root, "public").list_models()), 1)
            self.assertEqual(len(open_model_store(root, "private").list_models()), 1)
            self.assertFalse(model_store_root(root, "candidates").exists())

    def test_model_commit_is_idempotent_and_stale_writer_loses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = card("model-cas")
            first = commit_card_model(
                root,
                payload,
                authority_scope="public",
                expected_revision=None,
                idempotency_key="same-operation",
                actor="test",
            )
            retry = commit_card_model(
                root,
                payload,
                authority_scope="public",
                expected_revision=None,
                idempotency_key="same-operation",
                actor="test",
            )
            self.assertEqual(first.receipt, retry.receipt)
            changed = copy.deepcopy(payload)
            changed["predict"]["expected_result"] = "A changed result wins once."
            winner = commit_card_model(
                root,
                changed,
                authority_scope="public",
                expected_revision=first.binding.revision_id,
                idempotency_key="winner",
                actor="test",
            )
            loser = copy.deepcopy(payload)
            loser["predict"]["expected_result"] = "A stale result must not publish."
            with self.assertRaises(TransactionConflictError):
                commit_card_model(
                    root,
                    loser,
                    authority_scope="public",
                    expected_revision=first.binding.revision_id,
                    idempotency_key="loser",
                    actor="test",
                )
            self.assertEqual(
                str(open_model_store(root, "public").head(first.binding.model_id)),
                winner.binding.revision_id,
            )

    def test_exact_read_never_substitutes_a_missing_revision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = commit_card_model(
                root,
                card("model-exact"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="exact",
                actor="test",
            )
            broken = LogicGuardBinding(
                **{
                    **result.binding.__dict__,
                    "revision_id": "rev-" + "0" * 64,
                }
            )
            with self.assertRaises(ExactBindingError):
                read_exact_model(root, broken)

    def test_mesh_pins_exact_models_and_materializes_grounded_relation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left = commit_card_model(
                root,
                card("model-left"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="left",
                actor="test",
            )
            right = commit_card_model(
                root,
                card("model-right"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="right",
                actor="test",
            )
            relation = GroundedModelRelation(
                relation_id="edge-left-supports-right",
                source=left.binding,
                target=right.binding,
                edge_type="supports",
                explanation="The user explicitly linked these bounded predictions.",
                provenance=(grounding("left-right"),),
            )
            mesh = commit_scope_mesh(
                root,
                authority_scope="public",
                model_bindings=(left.binding, right.binding),
                expected_revision=None,
                idempotency_key="mesh-first",
                actor="test",
                relations=(relation,),
            )
            neighborhood = materialize_bound_neighborhood(root, mesh.bindings[0])
            self.assertTrue(neighborhood.materialized["complete"])
            self.assertEqual(len(neighborhood.materialized["model_pins"]), 2)
            self.assertEqual(len(neighborhood.materialized["cross_edges"]), 1)
            self.assertEqual(neighborhood.evaluation["authority"], "production")

    def test_ai_only_relation_and_cross_scope_relation_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public = commit_card_model(
                root,
                card("public-card"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="public",
                actor="test",
            )
            other_public = commit_card_model(
                root,
                card("other-public-card"),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="other-public",
                actor="test",
            )
            private = commit_card_model(
                root,
                card("private-card", scope="private"),
                authority_scope="private",
                expected_revision=None,
                idempotency_key="private",
                actor="test",
            )
            ai_only = GroundedModelRelation(
                relation_id="edge-ai-only",
                source=public.binding,
                target=other_public.binding,
                edge_type="supports",
                explanation="AI guessed this relation.",
                provenance=(
                    {
                        "origin_kind": "ai_generated",
                        "source_id": "ai",
                        "content_hash": "sha256:" + canonical_digest("guess"),
                    },
                ),
            )
            with self.assertRaises(UngroundedRelationshipError):
                commit_scope_mesh(
                    root,
                    authority_scope="public",
                    model_bindings=(public.binding, other_public.binding),
                    expected_revision=None,
                    idempotency_key="ai-only",
                    actor="test",
                    relations=(ai_only,),
                )
            cross_scope = GroundedModelRelation(
                relation_id="edge-cross-scope",
                source=public.binding,
                target=private.binding,
                edge_type="supports",
                explanation="This must not cross stores.",
                provenance=(grounding("cross-scope"),),
            )
            with self.assertRaises(AuthorityScopeError):
                commit_scope_mesh(
                    root,
                    authority_scope="public",
                    model_bindings=(public.binding, private.binding),
                    expected_revision=None,
                    idempotency_key="cross-scope",
                    actor="test",
                    relations=(cross_scope,),
                )

    def test_dream_simulation_is_exact_and_does_not_advance_mesh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = commit_card_model(
                root,
                card(
                    "dream-card",
                    evidence={"text": "Observed support", "origin": "test result"},
                ),
                authority_scope="public",
                expected_revision=None,
                idempotency_key="dream-model",
                actor="test",
            )
            mesh = commit_scope_mesh(
                root,
                authority_scope="public",
                model_bindings=(model.binding,),
                expected_revision=None,
                idempotency_key="dream-mesh",
                actor="test",
            )
            binding = mesh.bindings[0]
            delta = MeshSimulationDelta(
                base_mesh_id=binding.mesh_id,
                base_mesh_revision=binding.mesh_revision_id,
                evidence_availability_changes=(
                    MeshNodeOverride(
                        QualifiedNodeRef(binding.model_id, binding.revision_id, "evidence-1"),
                        {"missing": True},
                    ),
                ),
            )
            before = open_model_store(root, "public").head(binding.model_id)
            result = simulate_bound_mesh(root, binding, delta)
            after = open_model_store(root, "public").head(binding.model_id)
            self.assertEqual(result.receipt.authority, "simulation-only")
            self.assertEqual(before, after)
            wrong = copy.deepcopy(binding)
            with self.assertRaises(ExactBindingError):
                simulate_bound_mesh(
                    root,
                    wrong,
                    MeshSimulationDelta(
                        base_mesh_id=binding.mesh_id,
                        base_mesh_revision="mesh-rev-" + "0" * 64,
                    ),
                )


if __name__ == "__main__":
    unittest.main()
