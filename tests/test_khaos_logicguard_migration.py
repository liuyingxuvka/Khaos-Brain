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
