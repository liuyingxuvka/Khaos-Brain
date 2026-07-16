from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from local_kb.active_index import load_active_index, validate_active_index
from local_kb.logicguard_models import (
    ExactBindingError,
    load_authority_generation,
    open_mesh_store,
    read_exact_mesh,
)
from local_kb.maintenance_migration import (
    migrate_legacy_card_generation,
    plan_logicguard_native_migration,
    record_upgrade_ai_disposition,
    validate_logicguard_native_authority,
)
from local_kb.model_projection import binding_from_projection, validate_card_projection
from local_kb.store import load_yaml_file, write_yaml_file


def legacy_card(card_id: str, *, declared_scope: str = "public", context: str = "A bounded condition") -> dict:
    return {
        "id": card_id,
        "title": f"Legacy {card_id}",
        "type": "heuristic",
        "scope": declared_scope,
        "domain_path": ["system", "migration"],
        "cross_index": ["codex/workflow/migration"],
        "related_cards": ["unverified-legacy-neighbor"],
        "tags": ["migration"],
        "trigger_keywords": ["migrate"],
        "if": {"notes": context},
        "action": {"description": "Compile the card into an exact argument model."},
        "predict": {
            "expected_result": "The current projection binds one exact LogicGuard revision.",
            "alternatives": [],
        },
        "use": {"guidance": "Reject floating or legacy authority."},
        "confidence": 0.81,
        "source": [{"origin": "direct user instruction", "date": "2026-07-14"}],
        "status": "trusted" if declared_scope != "candidate" else "candidate",
        "updated_at": "2026-07-14",
        "then": {"guidance": "retired semantic authority"},
    }


def write_fixture(root: Path) -> None:
    write_yaml_file(root / "kb" / "public" / "public-a.yaml", legacy_card("public-a"))
    write_yaml_file(
        root / "kb" / "private" / "private-a.yaml",
        legacy_card("private-a", declared_scope="private"),
    )
    write_yaml_file(
        root / "kb" / "candidates" / "candidate-a.yaml",
        legacy_card("candidate-a", declared_scope="candidate", context=""),
    )


def tree_digest(root: Path, relative_roots: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative_root in relative_roots:
        base = root / relative_root
        if not base.exists():
            digest.update(f"ABSENT:{relative_root}\n".encode())
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            relative = path.relative_to(root).as_posix()
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\n")
    return digest.hexdigest()


class KhaosLogicGuardMigrationTests(unittest.TestCase):
    def test_fresh_clone_bootstraps_current_projection_into_stable_exact_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "fixture"
            write_yaml_file(
                fixture_root / "kb" / "public" / "public-a.yaml",
                legacy_card("public-a"),
            )
            fixture_result = migrate_legacy_card_generation(fixture_root)
            self.assertTrue(fixture_result["ok"], fixture_result)
            bootstrap_projection = load_yaml_file(
                fixture_root / "kb" / "public" / "public-a.yaml"
            )

            first_root = Path(directory) / "first-clean-clone"
            first_path = first_root / "kb" / "public" / "public-a.yaml"
            write_yaml_file(first_path, bootstrap_projection)
            plan = plan_logicguard_native_migration(first_root)
            self.assertTrue(plan["ok"], plan["issues"])
            self.assertEqual(1, plan["bootstrap_projection_count"])
            self.assertEqual(
                "direct-current-projection-bootstrap",
                plan["rows"][0]["disposition"],
            )
            self.assertEqual([], plan["rows"][0]["legacy_related_cards"])

            first = migrate_legacy_card_generation(first_root)
            self.assertTrue(first["ok"], first)
            self.assertEqual("committed", first["status"])
            first_projection = load_yaml_file(first_path)
            self.assertTrue(validate_card_projection(first_root, first_projection)["ok"])
            self.assertEqual([], first_projection["related_cards"])

            second = migrate_legacy_card_generation(first_root)
            self.assertTrue(second["ok"], second)
            self.assertEqual("no_delta", second["status"])
            self.assertEqual(first_projection, load_yaml_file(first_path))

            second_root = Path(directory) / "second-clean-clone"
            second_path = second_root / "kb" / "public" / "public-a.yaml"
            write_yaml_file(second_path, first_projection)
            rebuilt = migrate_legacy_card_generation(second_root)
            self.assertTrue(rebuilt["ok"], rebuilt)
            self.assertEqual(first_projection, load_yaml_file(second_path))
            self.assertEqual(
                load_authority_generation(first_root)["generation_id"],
                load_authority_generation(second_root)["generation_id"],
            )

    def test_fresh_clone_bootstrap_rejects_tampered_or_partial_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory) / "fixture"
            write_yaml_file(
                fixture_root / "kb" / "public" / "public-a.yaml",
                legacy_card("public-a"),
            )
            self.assertTrue(migrate_legacy_card_generation(fixture_root)["ok"])
            projection = load_yaml_file(
                fixture_root / "kb" / "public" / "public-a.yaml"
            )

            tampered_root = Path(directory) / "tampered"
            tampered = dict(projection)
            tampered["action"] = {"description": "Tampered without a new digest."}
            write_yaml_file(
                tampered_root / "kb" / "public" / "public-a.yaml",
                tampered,
            )
            tampered_plan = plan_logicguard_native_migration(tampered_root)
            self.assertFalse(tampered_plan["ok"])
            self.assertIn("projection digest mismatch", " ".join(tampered_plan["issues"]).lower())
            self.assertFalse(
                (tampered_root / ".local" / "khaos-brain" / "logicguard-authority").exists()
            )

            partial_root = Path(directory) / "partial"
            write_yaml_file(
                partial_root / "kb" / "public" / "public-a.yaml",
                projection,
            )
            partial = partial_root / ".local" / "khaos-brain" / "logicguard-authority" / "partial.json"
            partial.parent.mkdir(parents=True)
            partial.write_text("{}\n", encoding="utf-8")
            partial_plan = plan_logicguard_native_migration(partial_root)
            self.assertFalse(partial_plan["ok"])
            self.assertEqual(0, partial_plan["bootstrap_projection_count"])
            self.assertIn("current LogicGuard projections are invalid", " ".join(partial_plan["issues"]))

    def test_old_machine_mismatch_opens_upgrade_ai_work_item_without_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old_root = Path(directory) / "old-machine"
            write_yaml_file(
                old_root / "kb" / "public" / "public-a.yaml",
                legacy_card("public-a"),
            )
            write_yaml_file(
                old_root / "kb" / "public" / "public-b.yaml",
                legacy_card("public-b"),
            )
            self.assertTrue(migrate_legacy_card_generation(old_root)["ok"])
            old_generation = load_authority_generation(old_root)
            old_public_b = load_yaml_file(
                old_root / "kb" / "public" / "public-b.yaml"
            )

            package_root = Path(directory) / "new-package"
            write_yaml_file(
                package_root / "kb" / "public" / "public-a.yaml",
                legacy_card("public-a"),
            )
            self.assertTrue(migrate_legacy_card_generation(package_root)["ok"])
            package_projection = load_yaml_file(
                package_root / "kb" / "public" / "public-a.yaml"
            )
            self.assertNotEqual(
                package_projection["authority_generation_id"],
                old_generation["generation_id"],
            )

            # Simulate pulling a new repository projection onto a machine that
            # still owns a complete, different local authority generation.
            write_yaml_file(
                old_root / "kb" / "public" / "public-a.yaml",
                package_projection,
            )
            before_blocked_attempt = tree_digest(
                old_root,
                ("kb/public", ".local/khaos-brain/logicguard-authority"),
            )

            plan = plan_logicguard_native_migration(old_root)
            self.assertFalse(plan["ok"])
            self.assertEqual(1, plan["upgrade_ai_work_item_count"])
            work_item = plan["upgrade_ai_work_items"][0]
            self.assertEqual("open", work_item["status"])
            self.assertEqual(
                "incompatible-current-projection-authority",
                work_item["kind"],
            )
            self.assertIn("direct-to-current", work_item["required_action"])
            self.assertIn("automatic projection rebind", work_item["prohibited_actions"])
            self.assertIn("YAML or related_cards fallback", work_item["prohibited_actions"])
            self.assertEqual(
                old_generation["generation_id"],
                work_item["evidence"]["active_generation_id"],
            )

            blocked = migrate_legacy_card_generation(old_root)
            self.assertFalse(blocked["ok"])
            self.assertEqual("blocked", blocked["status"])
            self.assertEqual([work_item], blocked["upgrade_ai_work_items"])
            self.assertEqual(
                before_blocked_attempt,
                tree_digest(
                    old_root,
                    ("kb/public", ".local/khaos-brain/logicguard-authority"),
                ),
            )
            self.assertEqual(
                old_generation["generation_id"],
                load_authority_generation(old_root)["generation_id"],
            )

            resolution = record_upgrade_ai_disposition(
                old_root,
                work_item_id=work_item["work_item_id"],
                actor="Codex test upgrade AI",
                rationale=(
                    "The pulled public projection has a valid exact digest and a stable "
                    "public card id; rebuild only that card directly into the new current "
                    "model while reusing the old machine's other exact models."
                ),
            )
            self.assertTrue(resolution["ok"], resolution)
            self.assertEqual("recorded", resolution["status"])
            self.assertEqual([], resolution["remaining_work_item_ids"])
            self.assertEqual(
                before_blocked_attempt,
                tree_digest(
                    old_root,
                    ("kb/public", ".local/khaos-brain/logicguard-authority"),
                ),
            )

            resolved_plan = plan_logicguard_native_migration(old_root)
            self.assertTrue(resolved_plan["ok"], resolved_plan["issues"])
            self.assertEqual(0, resolved_plan["upgrade_ai_work_item_count"])
            self.assertEqual(1, resolved_plan["applied_upgrade_ai_disposition_count"])
            rebuilt_rows = [
                row
                for row in resolved_plan["rows"]
                if row["card_id"] == "public-a"
            ]
            self.assertEqual(
                ["direct-current-projection-to-logicguard-model"],
                [row["disposition"] for row in rebuilt_rows],
            )

            migrated = migrate_legacy_card_generation(old_root)
            self.assertTrue(migrated["ok"], migrated)
            self.assertEqual("committed", migrated["status"])
            current_generation = load_authority_generation(old_root)
            self.assertNotEqual(
                old_generation["generation_id"], current_generation["generation_id"]
            )
            public_a = load_yaml_file(
                old_root / "kb" / "public" / "public-a.yaml"
            )
            public_b = load_yaml_file(
                old_root / "kb" / "public" / "public-b.yaml"
            )
            self.assertEqual(
                package_projection["logicguard_model_id"],
                public_a["logicguard_model_id"],
            )
            self.assertEqual(
                old_public_b["logicguard_model_id"],
                public_b["logicguard_model_id"],
            )
            self.assertEqual(
                current_generation["generation_id"],
                public_a["authority_generation_id"],
            )
            self.assertEqual(
                current_generation["generation_id"],
                public_b["authority_generation_id"],
            )
            self.assertTrue(validate_logicguard_native_authority(old_root)["ok"])

    def test_direct_migration_publishes_scoped_exact_authority_and_zero_legacy_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            plan = plan_logicguard_native_migration(root)
            self.assertTrue(plan["ok"], plan["issues"])
            self.assertEqual(plan["legacy_card_count"], 3)

            result = migrate_legacy_card_generation(root)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["status"], "committed")
            generation = load_authority_generation(root)
            self.assertEqual(set(generation["scope_meshes"]), {"public", "private", "candidates"})

            for scope, filename in (
                ("public", "public-a.yaml"),
                ("private", "private-a.yaml"),
                ("candidates", "candidate-a.yaml"),
            ):
                projection = load_yaml_file(root / "kb" / scope / filename)
                self.assertNotIn("then", projection)
                self.assertEqual(projection["related_cards"], [])
                self.assertEqual(projection["authority_generation_id"], generation["generation_id"])
                validation = validate_card_projection(root, projection)
                self.assertTrue(validation["ok"])
                binding = binding_from_projection(projection)
                mesh = read_exact_mesh(root, binding)
                self.assertEqual(mesh.metadata["authority_scope"], scope)
                self.assertEqual(
                    mesh.metadata["unresolved_relationships"][0]["disposition"],
                    "unresolved-legacy-relation",
                )
                self.assertEqual(len(mesh.cross_model_edges), 0)

            candidate = load_yaml_file(root / "kb" / "candidates" / "candidate-a.yaml")
            self.assertIn("context", candidate["logicguard_open_role_gaps"])
            self.assertTrue(validate_logicguard_native_authority(root)["ok"])
            self.assertTrue(validate_active_index(root)["ok"])
            self.assertFalse(load_active_index(root)["stale"])

    def test_second_run_is_an_exact_no_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            first = migrate_legacy_card_generation(root)
            self.assertTrue(first["ok"], first)
            generation_before = load_authority_generation(root)
            index_before = load_active_index(root)
            heads_before = {
                scope: open_mesh_store(root, scope).head(binding["mesh_id"])
                for scope, binding in generation_before["scope_meshes"].items()
            }

            second = migrate_legacy_card_generation(root)
            self.assertTrue(second["ok"], second)
            self.assertEqual(second["status"], "no_delta")
            self.assertTrue(second["idempotent_no_delta"])
            self.assertEqual(load_authority_generation(root), generation_before)
            self.assertEqual(load_active_index(root)["generation"], index_before["generation"])
            self.assertEqual(
                {
                    scope: open_mesh_store(root, scope).head(binding["mesh_id"])
                    for scope, binding in generation_before["scope_meshes"].items()
                },
                heads_before,
            )

    def test_failures_after_each_publication_boundary_restore_the_pre_migration_surface(self) -> None:
        tracked = (
            "kb/public",
            "kb/private",
            "kb/candidates",
            "kb/indexes",
            ".local/khaos-brain/logicguard-authority",
        )
        for phase in ("models-meshes", "projections", "index", "pointer"):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_fixture(root)
                before = tree_digest(root, tracked)
                result = migrate_legacy_card_generation(root, fail_after_phase=phase)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "rolled_back")
                self.assertTrue(result["rollback"]["ok"])
                self.assertEqual(tree_digest(root, tracked), before)
                with self.assertRaises(ExactBindingError):
                    load_authority_generation(root)
                self.assertIn("then", load_yaml_file(root / "kb" / "public" / "public-a.yaml"))

    def test_malformed_legacy_card_blocks_before_any_authority_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_fixture(root)
            malformed = legacy_card("broken")
            malformed["predict"] = {"expected_result": ""}
            write_yaml_file(root / "kb" / "public" / "broken.yaml", malformed)
            result = migrate_legacy_card_generation(root)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "blocked")
            self.assertIn("action/prediction", " ".join(result["issues"]))
            self.assertFalse((root / ".local" / "khaos-brain" / "logicguard-authority").exists())


if __name__ == "__main__":
    unittest.main()
