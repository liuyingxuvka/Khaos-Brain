from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.adoption import ADOPTION_KEY, adopt_organization_entry_by_source_info
from local_kb.org_checks import check_organization_repository
from local_kb.org_contribution import prepare_organization_import_branch
from local_kb.org_outbox import build_organization_outbox, organization_outbox_dir
from local_kb.org_sources import _run_git, connect_organization_source
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.store import load_yaml_file, write_yaml_file
from local_kb.ui_data import build_search_payload
from tests.org_helpers import activate_current_kb_runtime


class OrganizationMultiMachineTests(unittest.TestCase):
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
            root / "kb" / "main" / "trusted" / "org-card.yaml",
            {
                "id": "org-card",
                "title": "Organization shared card",
                "type": "model",
                "scope": "public",
                "status": "trusted",
                "confidence": 0.9,
                "domain_path": ["shared"],
                "tags": ["shared", "organization"],
                "trigger_keywords": ["shared", "organization"],
                "if": {"notes": "Shared org scenario."},
                "action": {"description": "Use org card."},
                "predict": {"expected_result": "Org card is available."},
                "use": {"guidance": "Adopt before local maintenance."},
            },
        )
        (root / "kb" / "imports").mkdir(parents=True)
        (root / "kb" / "imports" / ".gitkeep").write_text("", encoding="utf-8")
        write_yaml_file(
            root / "skills" / "registry.yaml",
            {
                "skills": [
                    {
                        "id": "approved-skill",
                        "status": "approved",
                        "version": "1.0.0",
                        "content_hash": "sha256:" + "a" * 64,
                    }
                ]
            },
        )
        (root / "skills" / "candidates").mkdir(parents=True)
        (root / "skills" / "candidates" / ".gitkeep").write_text("", encoding="utf-8")

    def _init_git_repo(self, root: Path) -> None:
        self.assertEqual(0, _run_git(["init"], cwd=root).returncode)
        self.assertEqual(0, _run_git(["add", "."], cwd=root).returncode)
        self.assertEqual(
            0,
            _run_git(
                ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                cwd=root,
            ).returncode,
        )

    def _source(self, connect_result: dict) -> dict:
        settings = connect_result["settings"]
        return {
            "path": settings["local_mirror_path"],
            "organization_id": settings["organization_id"],
            "repo_url": "https://example.invalid/khaos-org-kb-sandbox.git",
            "source_commit": settings["last_sync_commit"],
        }

    def test_two_local_profiles_share_org_repo_but_keep_adoption_feedback_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org_source = root / "org-source"
            profile_a = root / "profile-a"
            profile_b = root / "profile-b"
            self._write_org_repo(org_source)
            self._init_git_repo(org_source)

            connect_a = connect_organization_source(profile_a, str(org_source))
            connect_b = connect_organization_source(profile_b, str(org_source))
            activate_current_kb_runtime(profile_a)
            activate_current_kb_runtime(profile_b)
            source_a = self._source(connect_a)
            source_b = self._source(connect_b)
            sources_a = [source_a]
            sources_b = [source_b]

            payload_a = build_search_payload(profile_a, "shared organization", organization_sources=sources_a)
            payload_b = build_search_payload(profile_b, "shared organization", organization_sources=sources_b)
            adoption_a = adopt_organization_entry_by_source_info(
                profile_a,
                "org-card",
                sources_a,
                source_info=payload_a["results"][0]["source_info"],
            )
            adoption_b = adopt_organization_entry_by_source_info(
                profile_b,
                "org-card",
                sources_b,
                source_info=payload_b["results"][0]["source_info"],
            )

            adopted_a = load_yaml_file(Path(adoption_a["path"]))
            adopted_a["use"]["guidance"] = "Profile A refined this for organization feedback."
            adopted_path = Path(adoption_a["path"])
            publication = publish_sleep_model_generation(
                profile_a,
                reason="test-organization-feedback-edit",
                card_upserts={adopted_path.relative_to(profile_a).as_posix(): adopted_a},
            )
            self.assertTrue(publication["ok"], publication)

            outbox_a = build_organization_outbox(profile_a, organization_id="sandbox")
            outbox_b = build_organization_outbox(profile_b, organization_id="sandbox")
            import_result = prepare_organization_import_branch(
                Path(source_a["path"]),
                organization_outbox_dir(profile_a, "sandbox"),
                contributor_id="profile-a",
                branch_name="contrib/profile-a/feedback",
            )
            check_result = check_organization_repository(
                Path(source_a["path"]),
                changed_files=import_result["created_files"],
                enforce_low_risk=True,
            )
            adoption_b_hit_count = load_yaml_file(Path(adoption_b["path"]))[ADOPTION_KEY]["hit_count"]

        self.assertTrue(connect_a["ok"], connect_a)
        self.assertTrue(connect_b["ok"], connect_b)
        self.assertNotEqual(source_a["path"], source_b["path"])
        self.assertNotEqual(adoption_a["path"], adoption_b["path"])
        self.assertEqual(adoption_b_hit_count, 1)
        self.assertEqual(outbox_a["created_count"], 1, outbox_a)
        self.assertEqual(outbox_a["created"][0]["proposal_kind"], "adopted-feedback")
        self.assertEqual(outbox_b["created_count"], 0, outbox_b)
        self.assertTrue(import_result["ok"], import_result)
        self.assertEqual(len(import_result["created_files"]), 1)
        self.assertRegex(
            import_result["created_files"][0],
            r"^kb/imports/profile-a/cand-\d{8}T\d{6}Z-inst[0-9a-f]{8}-[0-9a-f]{6}\.yaml$",
        )
        self.assertTrue(check_result["ok"], check_result)
        self.assertTrue(check_result["auto_merge_eligible"], check_result)


if __name__ == "__main__":
    unittest.main()
