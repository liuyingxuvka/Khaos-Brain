from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_outbox import build_organization_outbox
from local_kb.skill_sharing import (
    annotate_dependencies_with_registry_status,
    build_card_skill_dependency_manifest,
    consolidate_imported_skill_bundles,
    extract_skill_dependencies,
    install_imported_skill_bundle_version,
    install_approved_organization_skill,
    load_organization_skill_registry,
    select_latest_skill_bundle_versions,
    skill_auto_install_eligibility,
    skill_directory_content_hash,
)
from local_kb.store import load_yaml_file, write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


class SkillSharingTests(unittest.TestCase):
    def _card(self) -> dict:
        return {
            "id": "skill-backed-card",
            "title": "Skill backed card",
            "type": "model",
            "scope": "public",
            "status": "trusted",
            "confidence": 0.8,
            "domain_path": ["codex", "workflow", "skills"],
            "tags": ["skill"],
            "trigger_keywords": ["skill"],
            "required_skills": ["demo-skill"],
            "recommended_skills": [{"id": "missing-skill"}],
            "if": {"notes": "A card relies on a local Skill."},
            "action": {"description": "Declare the dependency as metadata."},
            "predict": {"expected_result": "Maintainers can review card and Skill together."},
            "use": {
                "guidance": "Do not auto-install the Skill.",
                "unavailable_skill_guidance": "Use the card without the Skill and keep the dependency unresolved.",
            },
        }

    def test_extract_skill_dependencies_supports_required_and_recommended_fields(self) -> None:
        dependencies = extract_skill_dependencies(self._card())

        self.assertEqual(
            dependencies,
            [
                {"id": "demo-skill", "requirement": "required"},
                {"id": "missing-skill", "requirement": "recommended"},
            ],
        )

    def test_dependency_manifest_builds_card_bound_skill_bundle_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".agents" / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo Skill for tests.\n---\n\nUse this skill.",
                encoding="utf-8",
            )

            manifest = build_card_skill_dependency_manifest(root, self._card(), codex_home=root / ".codex")

        self.assertEqual(manifest[0]["status"], "installed")
        self.assertEqual(manifest[0]["description"], "Demo Skill for tests.")
        self.assertEqual(manifest[0]["sharing_mode"], "card-bound-bundle")
        self.assertTrue(manifest[0]["bundle_id"].startswith("skill-bundle-"))
        self.assertTrue(manifest[0]["content_hash"].startswith("sha256:"))
        self.assertTrue(manifest[0]["readonly_when_imported"])
        self.assertEqual(manifest[0]["update_policy"], "original_author_only")
        self.assertEqual(manifest[1]["status"], "missing")
        self.assertEqual(manifest[1]["sharing_mode"], "missing")

    def test_outbox_proposal_includes_card_bound_skill_bundle_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / ".agents" / "skills" / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo Skill for tests.\n---\n\nUse this skill.",
                encoding="utf-8",
            )
            write_yaml_file(root / "kb" / "public" / "skill-backed-card.yaml", self._card())
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")
            proposal = load_yaml_file(Path(result["created"][0]["path"]))
            dependencies = proposal["organization_proposal"]["skill_dependencies"]
            copied_skill_exists = (Path(result["outbox_dir"]) / dependencies[0]["bundle_path"] / "SKILL.md").exists()
            copied_metadata_exists = (Path(result["outbox_dir"]) / dependencies[0]["bundle_metadata_path"]).exists()

        self.assertEqual([item["id"] for item in dependencies], ["demo-skill", "missing-skill"])
        self.assertEqual(dependencies[0]["sharing_mode"], "card-bound-bundle")
        self.assertEqual(dependencies[1]["sharing_mode"], "missing")
        self.assertTrue(dependencies[0]["bundle_id"].startswith("skill-bundle-"))
        self.assertTrue(dependencies[0]["bundle_path"])
        self.assertTrue(copied_skill_exists)
        self.assertTrue(copied_metadata_exists)

    def test_latest_skill_bundle_version_is_selected_by_version_time(self) -> None:
        latest = select_latest_skill_bundle_versions(
            [
                {
                    "bundle_id": "bundle-a",
                    "content_hash": "sha256:" + "1" * 64,
                    "version_time": "2026-04-24T10:00:00Z",
                },
                {
                    "bundle_id": "bundle-a",
                    "content_hash": "sha256:" + "2" * 64,
                    "version_time": "2026-04-24T12:00:00Z",
                },
            ]
        )

        self.assertEqual(latest["bundle-a"]["content_hash"], "sha256:" + "2" * 64)

    def test_imported_skill_bundle_consolidation_keeps_latest_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            older_skill = root / "older"
            newer_skill = root / "newer"
            older_skill.mkdir(parents=True)
            newer_skill.mkdir(parents=True)
            (older_skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Older Skill.\n---\n\nold",
                encoding="utf-8",
            )
            (newer_skill / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Newer Skill.\n---\n\nnew",
                encoding="utf-8",
            )
            bundle_id = "skill-bundle-demo"
            install_imported_skill_bundle_version(
                repo,
                {
                    "bundle_id": bundle_id,
                    "id": "demo-skill",
                    "version_time": "2026-04-24T10:00:00Z",
                    "content_hash": skill_directory_content_hash(older_skill),
                },
                older_skill,
                source_card_id="card-a",
            )
            install_imported_skill_bundle_version(
                repo,
                {
                    "bundle_id": bundle_id,
                    "id": "demo-skill",
                    "version_time": "2026-04-24T12:00:00Z",
                    "content_hash": skill_directory_content_hash(newer_skill),
                },
                newer_skill,
                source_card_id="card-b",
            )

            result = consolidate_imported_skill_bundles(repo)
            remaining = sorted((repo / ".local" / "organization_skills" / bundle_id / "versions").rglob("SKILL.md"))
            remaining_last_line = remaining[0].read_text(encoding="utf-8").splitlines()[-1]

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["bundle_count"], 1)
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining_last_line, "new")

    def test_skill_registry_loads_three_review_states_and_auto_install_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "skills" / "registry.yaml",
                {
                    "skills": [
                        {
                            "id": "approved-skill",
                            "status": "approved",
                            "version": "1.0.0",
                            "source_repo": "https://example.invalid/skills.git",
                            "content_hash": "sha256:" + "a" * 64,
                        },
                        {"id": "candidate-skill", "status": "candidate"},
                        {"id": "rejected-skill", "status": "rejected"},
                    ]
                },
            )

            registry = load_organization_skill_registry(root)
            approved = skill_auto_install_eligibility(
                registry["by_id"]["approved-skill"],
                local_policy_allows=True,
            )
            candidate = skill_auto_install_eligibility(
                registry["by_id"]["candidate-skill"],
                local_policy_allows=True,
            )

        self.assertTrue(registry["ok"], registry)
        self.assertTrue(approved["eligible"], approved)
        self.assertFalse(candidate["eligible"])
        self.assertIn("Skill is not approved", candidate["reasons"])

    def test_skill_registry_indexes_latest_bundle_version_even_when_ids_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "skills" / "registry.yaml",
                {
                    "skills": [
                        {
                            "id": "demo-skill",
                            "bundle_id": "bundle-a",
                            "status": "approved",
                            "version_time": "2026-04-24T10:00:00Z",
                            "source_repo": "https://example.invalid/skills.git",
                            "content_hash": "sha256:" + "1" * 64,
                        },
                        {
                            "id": "demo-skill",
                            "bundle_id": "bundle-a",
                            "status": "approved",
                            "version_time": "2026-04-24T12:00:00Z",
                            "source_repo": "https://example.invalid/skills.git",
                            "content_hash": "sha256:" + "2" * 64,
                        },
                    ]
                },
            )

            registry = load_organization_skill_registry(root)
            annotated = annotate_dependencies_with_registry_status(
                [{"id": "demo-skill", "bundle_id": "bundle-a", "requirement": "required"}],
                registry,
                local_policy_allows_auto_install=True,
            )

        self.assertTrue(registry["ok"], registry)
        self.assertEqual(registry["by_bundle_id"]["bundle-a"]["content_hash"], "sha256:" + "2" * 64)
        self.assertEqual(annotated[0]["registry_status"], "approved")
        self.assertEqual(annotated[0]["registry_version"], "2026-04-24T12:00:00Z")
        self.assertTrue(annotated[0]["auto_install"]["eligible"], annotated)

    def test_skill_registry_rejects_unknown_state_and_unpinned_approved_skill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "skills" / "registry.yaml",
                {
                    "skills": [
                        {"id": "bad-state", "status": "blocked"},
                        {"id": "bad-approved", "status": "approved"},
                    ]
                },
            )

            registry = load_organization_skill_registry(root)

        self.assertFalse(registry["ok"])
        self.assertIn("skill bad-state has invalid status: blocked", registry["errors"])
        self.assertIn("approved skill bad-approved must pin version", registry["errors"])
        self.assertIn("approved skill bad-approved must pin sha256 content_hash", registry["errors"])

    def test_dependencies_are_annotated_with_registry_status_and_install_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(
                root / "skills" / "registry.yaml",
                {
                    "skills": [
                        {
                            "id": "demo-skill",
                            "status": "approved",
                            "version": "1.0.0",
                            "source_repo": "https://example.invalid/skills.git",
                            "content_hash": "sha256:" + "a" * 64,
                        }
                    ]
                },
            )
            registry = load_organization_skill_registry(root)

            annotated = annotate_dependencies_with_registry_status(
                [{"id": "demo-skill", "requirement": "required"}, {"id": "missing-skill", "requirement": "recommended"}],
                registry,
                local_policy_allows_auto_install=True,
            )

        self.assertEqual(annotated[0]["registry_status"], "approved")
        self.assertTrue(annotated[0]["auto_install"]["eligible"])
        self.assertEqual(annotated[1]["registry_status"], "missing")
        self.assertFalse(annotated[1]["auto_install"]["eligible"])

    def test_install_approved_organization_skill_verifies_hash_and_existing_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "skill-source"
            skill_dir = source_root / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Approved demo Skill.\n---\n\nUse this Skill.",
                encoding="utf-8",
            )
            content_hash = skill_directory_content_hash(skill_dir)
            skill = {
                "id": "demo-skill",
                "bundle_id": "skill-bundle-demo",
                "status": "approved",
                "version": "1.0.0",
                "source_repo": str(source_root),
                "source_path": "demo-skill",
                "content_hash": content_hash,
            }
            codex_home = root / ".codex"

            installed = install_approved_organization_skill(
                skill,
                codex_home=codex_home,
                local_policy_allows=True,
            )
            bad_hash = install_approved_organization_skill(
                {**skill, "id": "bad-skill", "content_hash": "sha256:" + "b" * 64},
                codex_home=codex_home,
                local_policy_allows=True,
            )
            (codex_home / "skills" / "skill-bundle-demo" / "SKILL.md").write_text("different", encoding="utf-8")
            conflict = install_approved_organization_skill(
                skill,
                codex_home=codex_home,
                local_policy_allows=True,
            )
            installed_path_exists = (codex_home / "skills" / "skill-bundle-demo" / "SKILL.md").exists()

        self.assertTrue(installed["ok"], installed)
        self.assertEqual(installed["status"], "installed")
        self.assertTrue(installed_path_exists)
        self.assertFalse(bad_hash["ok"])
        self.assertEqual(bad_hash["status"], "hash_mismatch")
        self.assertFalse(conflict["ok"])
        self.assertEqual(conflict["status"], "existing_version_conflict")


if __name__ == "__main__":
    unittest.main()
