from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb import logicguard_models
from local_kb.active_index import load_active_entries, rebuild_active_index
from local_kb.logicguard_models import (
    ExactBindingError,
    GroundedModelRelation,
    build_authority_generation_payload,
    canonical_digest,
    commit_card_model,
    commit_scope_mesh,
    publish_authority_generation,
)
from local_kb.maintenance_standard import (
    CURRENT_HISTORY_SCHEMA_VERSION,
    CURRENT_MAINTENANCE_STANDARD_VERSION,
    write_maintenance_state,
)
from local_kb.model_projection import project_card, write_card_projection_atomic
from local_kb.search import (
    format_search_output,
    render_search_payload,
    search_loaded_entries,
    search_with_receipt,
)


def card(card_id: str, keyword: str) -> dict:
    return {
        "id": card_id,
        "title": f"{keyword} prediction",
        "type": "model",
        "scope": "public",
        "domain_path": ["system", keyword],
        "cross_index": [],
        "related_cards": ["legacy-name-that-must-not-drive-retrieval"],
        "tags": [keyword],
        "trigger_keywords": [keyword],
        "if": {"notes": f"When {keyword} is observed."},
        "action": {"description": f"Apply {keyword}."},
        "predict": {"expected_result": f"{keyword} remains explainable.", "alternatives": []},
        "use": {"guidance": f"Use the exact {keyword} model."},
        "confidence": 0.9,
        "source": [{"origin": "direct user instruction", "date": "2026-07-14"}],
        "status": "trusted",
        "updated_at": "2026-07-14",
    }


def grounding() -> dict:
    return {
        "origin_kind": "user_attestation",
        "source_id": "test:retrieval:left-right",
        "content_hash": "sha256:" + canonical_digest("left-right"),
        "source_reference": "tests/test_khaos_model_native_retrieval.py",
        "actor": "test",
    }


def activate_model_native_fixture(root: Path) -> None:
    models = {
        card_id: commit_card_model(
            root,
            card(card_id, keyword),
            authority_scope="public",
            expected_revision=None,
            idempotency_key=f"model:{card_id}",
            actor="test",
        )
        for card_id, keyword in (
            ("left-card", "leftsignal"),
            ("right-card", "rightsignal"),
            ("unrelated-card", "thirdsignal"),
        )
    }
    mesh = commit_scope_mesh(
        root,
        authority_scope="public",
        model_bindings=tuple(item.binding for item in models.values()),
        expected_revision=None,
        idempotency_key="mesh:retrieval",
        actor="test",
        relations=(
            GroundedModelRelation(
                relation_id="edge-left-right",
                source=models["left-card"].binding,
                target=models["right-card"].binding,
                edge_type="supports",
                explanation="The user attested this bounded relation.",
                provenance=(grounding(),),
            ),
        ),
    )
    generation_id = "generation-model-native-retrieval"
    manifest: list[dict] = []
    for binding in mesh.bindings:
        projection = project_card(root, binding, authority_generation_id=generation_id)
        path = root / "kb" / "public" / f"{projection['id']}.yaml"
        write_card_projection_atomic(root, path, projection)
        manifest.append(
            {
                "scope": "public",
                "path": path.relative_to(root).as_posix(),
                "card_id": projection["id"],
                "projection_digest": projection["projection_digest"],
                **binding.to_dict(),
            }
        )
    manifest.sort(key=lambda item: (item["scope"], item["path"], item["card_id"]))
    generation = build_authority_generation_payload(
        generation_id=generation_id,
        scope_meshes={
            "public": {
                "mesh_id": mesh.mesh_id,
                "mesh_revision_id": mesh.mesh_revision_id,
                "content_digest": mesh.content_digest,
            }
        },
        projection_manifest_digest="sha256:" + canonical_digest(manifest),
        projection_count=len(manifest),
        actor="test",
    )
    rebuild_active_index(root, reason="test:model-native-retrieval", authority_generation=generation)
    publish_authority_generation(root, generation, writer="local_kb.lifecycle.run_incremental_sleep")
    write_maintenance_state(
        root,
        {
            "maintenance_standard_version": CURRENT_MAINTENANCE_STANDARD_VERSION,
            "history_schema_version": CURRENT_HISTORY_SCHEMA_VERSION,
            "phase": "committed",
            "committed": True,
            "migration_id": "test-model-native-retrieval",
        },
    )


class KhaosModelNativeRetrievalTests(unittest.TestCase):
    def test_bound_read_session_rotates_with_authority_generation(self) -> None:
        logicguard_models._cached_bound_read_session.cache_clear()
        model_one = object()
        model_two = object()
        mesh_one = object()
        mesh_two = object()
        with patch(
            "local_kb.logicguard_models.open_pinned_model_read_store",
            side_effect=[(model_one, frozenset()), (model_two, frozenset())],
        ) as model_open, patch(
            "local_kb.logicguard_models.open_pinned_mesh_read_store",
            side_effect=[mesh_one, mesh_two],
        ) as mesh_open:
            first = logicguard_models._cached_bound_read_session(
                "fixture-root", "sha256:generation-one", "public"
            )
            repeated = logicguard_models._cached_bound_read_session(
                "fixture-root", "sha256:generation-one", "public"
            )
            rotated = logicguard_models._cached_bound_read_session(
                "fixture-root", "sha256:generation-two", "public"
            )

        self.assertIs(first, repeated)
        self.assertEqual(first, (model_one, mesh_one))
        self.assertEqual(rotated, (model_two, mesh_two))
        self.assertEqual(model_open.call_count, 2)
        self.assertEqual(mesh_open.call_count, 2)

    def test_repeated_exact_context_reads_reuse_only_immutable_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            logicguard_models._cached_bound_argument_context_json.cache_clear()
            logicguard_models._cached_bound_read_session.cache_clear()
            with patch(
                "local_kb.logicguard_models._build_bound_argument_context",
                wraps=logicguard_models._build_bound_argument_context,
            ) as builder, patch(
                "local_kb.logicguard_models.open_pinned_model_read_store",
                wraps=logicguard_models.open_pinned_model_read_store,
            ) as pinned_store:
                first, _ = search_with_receipt(
                    root,
                    query="id:left-card",
                    top_k=3,
                    record_receipt=False,
                )
                first_build_count = builder.call_count
                self.assertGreater(first_build_count, 0)
                first[0].source["logicguard"]["binding"][
                    "logicguard_model_id"
                ] = "mutated-by-caller"

                second, _ = search_with_receipt(
                    root,
                    query="id:left-card",
                    top_k=3,
                    record_receipt=False,
                )
                self.assertEqual(builder.call_count, first_build_count)
                self.assertEqual(pinned_store.call_count, 1)
                self.assertNotEqual(
                    second[0].source["logicguard"]["binding"][
                        "logicguard_model_id"
                    ],
                    "mutated-by-caller",
                )

    def test_retrieval_enters_exact_model_and_expands_only_grounded_neighborhood(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            results, receipt = search_with_receipt(root, query="id:left-card", top_k=3)
            self.assertEqual([item.data["id"] for item in results], ["left-card", "right-card"])
            self.assertEqual(
                results[1].source["logicguard_discovery"],
                "grounded-model-neighborhood",
            )
            self.assertNotIn("unrelated-card", [item.data["id"] for item in results])
            for entry in results:
                context = entry.source["logicguard"]
                self.assertTrue(context["binding"]["logicguard_revision_id"])
                self.assertTrue(context["binding"]["logicguard_mesh_revision_id"])
                self.assertTrue(context["neighborhood"]["materialization_fingerprint"])
                self.assertEqual(context["evaluation"]["authority"], "production")
            self.assertTrue(receipt["returned_entries"][0]["logicguard_binding"])
            self.assertTrue(
                receipt["returned_entries"][0]["materialization_fingerprint"]
            )
            self.assertEqual(
                results[0].source["logicguard_ranking"]["distance"],
                0,
            )
            self.assertEqual(
                results[0].source["logicguard_ranking"]["root_role"],
                "predicted_result",
            )
            self.assertEqual(
                results[1].source["logicguard_ranking"]["distance"],
                1,
            )
            self.assertEqual(
                results[1].source["logicguard_ranking"]["relation_types"],
                ["supports"],
            )
            self.assertTrue(
                receipt["returned_entries"][1]["logicguard_ranking"]
            )

            model_id = results[0].data["logicguard_model_id"]
            node_id = results[0].data["logicguard_node_id"]
            direct_model, _ = search_with_receipt(
                root,
                query=f"model:{model_id}",
                top_k=1,
                record_receipt=False,
            )
            self.assertEqual(direct_model[0].data["id"], "left-card")
            self.assertEqual(
                direct_model[0].source["logicguard_ranking"][
                    "direct_identifier_kind"
                ],
                "model",
            )
            direct_node, _ = search_with_receipt(
                root,
                query=f"node:{model_id}#{node_id}",
                top_k=1,
                record_receipt=False,
            )
            self.assertEqual(direct_node[0].data["id"], "left-card")
            self.assertEqual(
                direct_node[0].source["logicguard_ranking"][
                    "direct_identifier_kind"
                ],
                "qualified-node",
            )

            payload = render_search_payload(results, root)
            text = format_search_output(payload)
            self.assertIn("logicguard=khaos-card-left-card-", text)
            self.assertIn("model_neighbors=khaos-card-right-card-", text)

    def test_projection_related_cards_never_expand_the_lexical_ranker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            entries, _index = load_active_entries(root)
            ranked = search_loaded_entries(entries, query="id:left-card", top_k=3)
            self.assertEqual([item.data["id"] for item in ranked], ["left-card"])

    def test_missing_exact_model_context_fails_closed_without_projection_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            with patch(
                "local_kb.search.read_bound_argument_context",
                side_effect=ExactBindingError("exact revision unavailable"),
            ):
                with self.assertRaisesRegex(ExactBindingError, "exact revision unavailable"):
                    search_with_receipt(root, query="id:left-card", top_k=1)


if __name__ == "__main__":
    unittest.main()
