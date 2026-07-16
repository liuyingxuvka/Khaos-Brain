from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_checks import check_organization_repository
from local_kb.org_maintenance import build_organization_maintenance_report
from local_kb.skill_sharing import (
    consolidate_imported_skill_bundles,
    install_imported_skill_bundle_version,
    skill_directory_content_hash,
)
from local_kb.store import load_yaml_file, write_yaml_file


class OrganizationMaintenanceCleanupE2ETests(unittest.TestCase):
    def _write_org_repo(self, root: Path) -> None:
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
        write_yaml_file(
            root / "kb" / "main" / "trusted" / "canonical.yaml",
            self._card("canonical-card", status="trusted", title="Canonical organization card"),
        )
        write_yaml_file(
            root / "kb" / "main" / "candidates" / "weak-random.yaml",
            self._card(
                "weak-random",
                status="candidate",
                title="Random weak candidate",
                guidance="Random unreviewed text with no durable predictive value.",
                confidence=0.2,
            ),
        )
        (root / "kb" / "imports").mkdir(parents=True)
        write_yaml_file(
            root / "skills" / "registry.yaml",
            {
                "skills": [
                    {
                        "id": "approved-review-skill",
                        "status": "approved",
                        "version": "1.0.0",
                        "source_repo": "https://example.invalid/skills.git",
                        "content_hash": "sha256:" + "a" * 64,
                    }
                ]
            },
        )
        (root / "skills" / "candidates").mkdir(parents=True)

    def _card(
        self,
        entry_id: str,
        *,
        status: str = "candidate",
        title: str = "Shared candidate",
        guidance: str = "Keep one canonical copy.",
        confidence: float = 0.7,
    ) -> dict:
        return {
            "id": entry_id,
            "title": title,
            "type": "model",
            "scope": "public",
            "status": status,
            "confidence": confidence,
            "domain_path": ["shared", "maintenance"],
            "tags": ["shared", "maintenance"],
            "trigger_keywords": ["shared", "maintenance"],
            "if": {"notes": "A reusable organization maintenance scenario."},
            "action": {"description": "Use the card to guide organization KB maintenance."},
            "predict": {"expected_result": "Organization maintenance keeps the shared KB clean."},
            "use": {"guidance": guidance},
        }

    def test_cleanup_report_flags_duplicate_hashes_but_does_not_mutate_org_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            local_repo = root / "local"
            self._write_org_repo(org)
            duplicate_a = self._card("duplicate-a")
            duplicate_b = dict(duplicate_a)
            duplicate_b["id"] = "duplicate-b"
            write_yaml_file(org / "kb" / "imports" / "alice" / "duplicate-a.yaml", duplicate_a)
            write_yaml_file(org / "kb" / "imports" / "bob" / "duplicate-b.yaml", duplicate_b)
            before_a = load_yaml_file(org / "kb" / "imports" / "alice" / "duplicate-a.yaml")
            before_b = load_yaml_file(org / "kb" / "imports" / "bob" / "duplicate-b.yaml")

            check = check_organization_repository(
                org,
                changed_files=[
                    "kb/imports/alice/duplicate-a.yaml",
                    "kb/imports/bob/duplicate-b.yaml",
                ],
                enforce_low_risk=True,
            )
            report = build_organization_maintenance_report(org, repo_root=local_repo)
            after_a = load_yaml_file(org / "kb" / "imports" / "alice" / "duplicate-a.yaml")
            after_b = load_yaml_file(org / "kb" / "imports" / "bob" / "duplicate-b.yaml")
            weak_after = load_yaml_file(org / "kb" / "main" / "candidates" / "weak-random.yaml")

        self.assertFalse(check["ok"], check)
        self.assertIn("duplicate card content hashes require organization maintenance", check["errors"])
        self.assertEqual(report["cleanup"]["duplicate_content_hash_count"], 1)
        self.assertIn("review-duplicate-card-content-hashes", report["recommendations"])
        self.assertEqual(report["cleanup"]["weak_card_rejection_apply"], "planned")
        self.assertEqual(report["cleanup"]["similar_card_merge_apply"], "planned")
        self.assertEqual(before_a, after_a)
        self.assertEqual(before_b, after_b)
        self.assertEqual(weak_after["status"], "candidate")

    def test_imported_skill_bundle_cleanup_keeps_latest_version_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "local"
            older_skill = root / "older-skill"
            newer_skill = root / "newer-skill"
            older_skill.mkdir(parents=True)
            newer_skill.mkdir(parents=True)
            (older_skill / "SKILL.md").write_text(
                "---\nname: shared-skill\ndescription: Older shared Skill.\n---\n\nold",
                encoding="utf-8",
            )
            (newer_skill / "SKILL.md").write_text(
                "---\nname: shared-skill\ndescription: Newer shared Skill.\n---\n\nnew",
                encoding="utf-8",
            )
            bundle_id = "skill-bundle-shared"
            install_imported_skill_bundle_version(
                repo,
                {
                    "id": "shared-skill",
                    "bundle_id": bundle_id,
                    "content_hash": skill_directory_content_hash(older_skill),
                    "version_time": "2026-04-24T10:00:00Z",
                    "original_author": "alice",
                },
                older_skill,
                source_card_id="old-card",
            )
            install_imported_skill_bundle_version(
                repo,
                {
                    "id": "shared-skill",
                    "bundle_id": bundle_id,
                    "content_hash": skill_directory_content_hash(newer_skill),
                    "version_time": "2026-04-24T12:00:00Z",
                    "original_author": "alice",
                },
                newer_skill,
                source_card_id="new-card",
            )

            result = consolidate_imported_skill_bundles(repo)
            remaining_skill_files = sorted(
                (repo / ".local" / "organization_skills" / bundle_id / "versions").rglob("SKILL.md")
            )
            remaining_last_line = remaining_skill_files[0].read_text(encoding="utf-8").splitlines()[-1]
            metadata = load_yaml_file(repo / ".local" / "organization_skills" / bundle_id / "metadata.yaml")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["removed_count"], 1)
        self.assertEqual(len(remaining_skill_files), 1)
        self.assertEqual(remaining_last_line, "new")
        self.assertEqual(metadata["latest_version"]["version_time"], "2026-04-24T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
