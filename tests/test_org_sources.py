from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.org_sources import (
    _run_git,
    clone_or_fetch_organization_repo,
    connect_organization_source,
    default_org_mirror_path,
    guess_organization_source_id,
    validate_organization_repo,
)
from local_kb.org_migration import migrate_organization_repo_to_current
from local_kb.store import load_organization_entries, load_yaml_file, write_yaml_file


class OrganizationSourceTests(unittest.TestCase):
    def _write_valid_org_repo(self, root: Path) -> None:
        write_yaml_file(
            root / "khaos_org_kb.yaml",
            {
                "kind": "khaos-organization-kb",
                "schema_version": 1,
                "organization_id": "sandbox",
                "kb": {
                    "main_path": "kb/main",
                    "imports_path": "kb/imports",
                },
                "skills": {
                    "registry_path": "skills/registry.yaml",
                    "candidates_path": "skills/candidates",
                },
            },
        )
        write_yaml_file(root / "kb" / "main" / "model.yaml", {"id": "model", "status": "trusted"})
        write_yaml_file(root / "kb" / "main" / "candidate.yaml", {"id": "candidate", "status": "candidate"})
        (root / "kb" / "imports").mkdir(parents=True)
        (root / "kb" / "imports" / ".gitkeep").write_text("", encoding="utf-8")
        write_yaml_file(root / "skills" / "registry.yaml", {"skills": [{"id": "org.demo", "status": "approved"}]})
        (root / "skills" / "candidates").mkdir(parents=True)
        (root / "skills" / "candidates" / ".gitkeep").write_text("", encoding="utf-8")

    def test_validate_organization_repo_accepts_valid_manifest_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_valid_org_repo(root)

            result = validate_organization_repo(root)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["organization_id"], "sandbox")
        self.assertEqual(result["layout"], "main-imports")
        self.assertEqual(result["target_layout"], "main-imports")
        self.assertNotIn("legacy_compatibility", result)
        self.assertIn("sole current", result["layout_message"])
        self.assertEqual(result["incoming_lane_path"], "kb/imports")
        self.assertEqual(result["exchange_surface_path"], "kb/main")
        self.assertEqual(result["local_download_paths"], ["kb/main"])
        self.assertEqual(result["local_download_excluded_paths"], ["kb/imports"])
        self.assertEqual(result["trusted_count"], 1)
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["skill_count"], 1)

    def test_validate_organization_repo_accepts_main_imports_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "main_path": "kb/main",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "main" / "trusted.yaml", {"id": "model", "status": "trusted"})
            write_yaml_file(root / "kb" / "main" / "candidate.yaml", {"id": "candidate", "status": "candidate"})
            write_yaml_file(root / "kb" / "main" / "rejected.yaml", {"id": "rejected", "status": "rejected"})
            (root / "kb" / "imports").mkdir(parents=True)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            result = validate_organization_repo(root)

        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["layout"], "main-imports")
        self.assertEqual(result["target_layout"], "main-imports")
        self.assertNotIn("legacy_compatibility", result)
        self.assertEqual(result["incoming_lane_path"], "kb/imports")
        self.assertEqual(result["exchange_surface_path"], "kb/main")
        self.assertEqual(result["local_download_paths"], ["kb/main"])
        self.assertEqual(result["local_download_excluded_paths"], ["kb/imports"])
        self.assertEqual(result["main_count"], 3)
        self.assertEqual(result["main_active_count"], 2)
        self.assertEqual(result["imports_count"], 0)
        self.assertEqual(result["main_status_counts"]["trusted"], 1)
        self.assertEqual(result["main_status_counts"]["candidate"], 1)
        self.assertEqual(result["trusted_count"], 1)
        self.assertEqual(result["candidate_count"], 1)

    def test_local_organization_download_reads_main_not_imports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "main_path": "kb/main",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "main" / "main-card.yaml", {"id": "main-card", "status": "trusted"})
            write_yaml_file(root / "kb" / "imports" / "alice" / "import-card.yaml", {"id": "import-card", "status": "candidate"})
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            validation = validate_organization_repo(root)
            entries = load_organization_entries(root, "sandbox")
            entry_ids = [entry.data["id"] for entry in entries]

        self.assertTrue(validation["ok"], validation["errors"])
        self.assertEqual(validation["imports_count"], 1)
        self.assertEqual(entry_ids, ["main-card"])

    def test_validate_organization_repo_rejects_missing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = validate_organization_repo(Path(tmp))

        self.assertFalse(result["ok"])
        self.assertIn("missing organization KB manifest", result["errors"][0])

    def test_strict_runtime_rejects_retired_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "trusted_path": "kb/trusted",
                        "candidates_path": "kb/candidates",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "trusted" / "model.yaml", {"id": "model", "status": "trusted"})
            (root / "kb" / "candidates").mkdir(parents=True)
            (root / "kb" / "imports").mkdir(parents=True)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            result = validate_organization_repo(root)

        self.assertFalse(result["ok"])
        self.assertTrue(any("obsolete" in error for error in result["errors"]))

    def test_one_time_migration_rewrites_retired_layout_and_leaves_zero_residuals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "trusted_path": "kb/trusted",
                        "candidates_path": "kb/candidates",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "trusted" / "model.yaml", {"id": "model", "status": "trusted"})
            write_yaml_file(root / "kb" / "candidates" / "candidate.yaml", {"id": "candidate", "status": "candidate"})
            (root / "kb" / "imports").mkdir(parents=True)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            migration = migrate_organization_repo_to_current(root)
            validation = validate_organization_repo(root)

            self.assertTrue(migration["ok"], migration)
            self.assertEqual(migration["status"], "committed")
            self.assertTrue(validation["ok"], validation["errors"])
            self.assertFalse((root / "kb" / "trusted").exists())
            self.assertFalse((root / "kb" / "candidates").exists())
            self.assertTrue((root / "kb" / "main" / "trusted" / "model.yaml").exists())
            self.assertTrue((root / "kb" / "main" / "candidates" / "candidate.yaml").exists())

    def test_one_time_migration_blocks_a_conflicting_current_target_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "trusted_path": "kb/trusted",
                        "candidates_path": "kb/candidates",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "trusted" / "model.yaml", {"id": "old", "status": "trusted"})
            write_yaml_file(
                root / "kb" / "main" / "trusted" / "model.yaml",
                {"id": "different", "status": "trusted"},
            )
            (root / "kb" / "candidates").mkdir(parents=True)
            (root / "kb" / "imports").mkdir(parents=True)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            migration = migrate_organization_repo_to_current(root)

            self.assertFalse(migration["ok"], migration)
            self.assertEqual(migration["status"], "blocked")
            self.assertEqual(migration["collisions"], ["kb/main/trusted/model.yaml"])
            self.assertTrue((root / "kb" / "trusted" / "model.yaml").exists())
            self.assertEqual(
                load_yaml_file(root / "kb" / "main" / "trusted" / "model.yaml")["id"],
                "different",
            )

    def test_one_time_migration_restores_the_snapshot_when_current_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "khaos_org_kb.yaml",
                {
                    "kind": "khaos-organization-kb",
                    "schema_version": 1,
                    "organization_id": "sandbox",
                    "kb": {
                        "trusted_path": "kb/trusted",
                        "candidates_path": "kb/candidates",
                        "imports_path": "kb/imports",
                    },
                    "skills": {
                        "registry_path": "skills/registry.yaml",
                        "candidates_path": "skills/candidates",
                    },
                },
            )
            write_yaml_file(root / "kb" / "trusted" / "model.yaml", {"id": "model", "status": "trusted"})
            (root / "kb" / "candidates").mkdir(parents=True)
            (root / "kb" / "imports").mkdir(parents=True)
            write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
            (root / "skills" / "candidates").mkdir(parents=True)

            with patch(
                "local_kb.org_sources.validate_organization_repo",
                return_value={"ok": False, "errors": ["forced current validation failure"]},
            ):
                migration = migrate_organization_repo_to_current(root)

            restored_manifest = load_yaml_file(root / "khaos_org_kb.yaml")
            self.assertFalse(migration["ok"], migration)
            self.assertEqual(migration["status"], "rolled_back")
            self.assertTrue((root / "kb" / "trusted" / "model.yaml").exists())
            self.assertFalse((root / "kb" / "main").exists())
            self.assertEqual(restored_manifest["kb"]["trusted_path"], "kb/trusted")
            self.assertNotIn("main_path", restored_manifest["kb"])

    def test_default_org_mirror_path_sanitizes_organization_id(self) -> None:
        path = default_org_mirror_path(Path("repo"), "acme/org kb")

        self.assertEqual(path.as_posix(), "repo/.local/organization_sources/acme-org-kb")

    def test_guess_organization_source_id_uses_repo_name(self) -> None:
        self.assertEqual(
            guess_organization_source_id("https://github.com/acme/khaos-org-kb-sandbox.git"),
            "khaos-org-kb-sandbox",
        )

    def test_clone_or_fetch_supports_local_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            mirror = root / "mirror"
            self._write_valid_org_repo(source)
            self.assertEqual(0, _run_git(["init"], cwd=source).returncode)
            self.assertEqual(0, _run_git(["add", "."], cwd=source).returncode)
            self.assertEqual(
                0,
                _run_git(
                    ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                    cwd=source,
                ).returncode,
            )

            clone_result = clone_or_fetch_organization_repo(str(source), mirror)
            validation = validate_organization_repo(mirror)

        self.assertTrue(clone_result["ok"], clone_result["errors"])
        self.assertEqual(clone_result["action"], "clone")
        self.assertTrue(validation["ok"], validation["errors"])

    def test_connect_organization_source_clones_valid_repo_and_builds_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            repo_root = root / "repo"
            self._write_valid_org_repo(source)
            self.assertEqual(0, _run_git(["init"], cwd=source).returncode)
            self.assertEqual(0, _run_git(["add", "."], cwd=source).returncode)
            self.assertEqual(
                0,
                _run_git(
                    ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                    cwd=source,
                ).returncode,
            )

            result = connect_organization_source(repo_root, str(source))
            mirror_exists = Path(result["settings"]["local_mirror_path"]).exists()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["settings"]["validation_status"], "valid")
        self.assertEqual(result["settings"]["organization_id"], "sandbox")
        self.assertTrue(mirror_exists)


if __name__ == "__main__":
    unittest.main()
