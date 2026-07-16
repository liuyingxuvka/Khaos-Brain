from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_sources import _run_git, connect_organization_source
from local_kb.settings import (
    ORGANIZATION_MODE,
    PERSONAL_MODE,
    load_desktop_settings,
    organization_sources_from_settings,
    save_desktop_settings,
)
from local_kb.store import write_yaml_file
from local_kb.ui_data import build_search_payload
from tests.org_helpers import activate_current_kb_runtime


class OrganizationConnectionE2ETests(unittest.TestCase):
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
        write_yaml_file(
            root / "kb" / "main" / "trusted" / "org-card.yaml",
            {
                "id": "org-card",
                "title": "Organization shared card",
                "type": "model",
                "scope": "public",
                "status": "trusted",
                "confidence": 0.9,
                "domain_path": ["shared", "organization"],
                "tags": ["shared", "organization"],
                "trigger_keywords": ["shared", "organization"],
                "if": {"notes": "Shared organization connection scenario."},
                "action": {"description": "Use the connected organization card."},
                "predict": {"expected_result": "Organization search is active."},
                "use": {"guidance": "Only appears after validated organization settings are active."},
            },
        )
        (root / "kb" / "imports").mkdir(parents=True, exist_ok=True)
        (root / "kb" / "imports" / ".gitkeep").write_text("", encoding="utf-8")
        write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
        (root / "skills" / "candidates").mkdir(parents=True, exist_ok=True)
        (root / "skills" / "candidates" / ".gitkeep").write_text("", encoding="utf-8")

    def _commit_repo(self, root: Path) -> None:
        self.assertEqual(0, _run_git(["init"], cwd=root).returncode)
        self.assertEqual(0, _run_git(["add", "."], cwd=root).returncode)
        result = _run_git(
            ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
            cwd=root,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_valid_source_activates_organization_mode_and_personal_switch_hides_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            repo = root / "machine"
            self._write_valid_org_repo(source)
            self._commit_repo(source)

            connection = connect_organization_source(repo, str(source))
            save_desktop_settings(
                repo,
                {
                    "mode": ORGANIZATION_MODE,
                    "organization": connection["settings"],
                },
            )
            activate_current_kb_runtime(repo)
            organization_settings = load_desktop_settings(repo)
            organization_sources = organization_sources_from_settings(organization_settings)
            organization_payload = build_search_payload(
                repo,
                "shared organization",
                organization_sources=organization_sources,
            )

            save_desktop_settings(
                repo,
                {
                    "mode": PERSONAL_MODE,
                    "organization": organization_settings["organization"],
                },
            )
            personal_settings = load_desktop_settings(repo)
            personal_sources = organization_sources_from_settings(personal_settings)
            personal_payload = build_search_payload(
                repo,
                "shared organization",
                organization_sources=personal_sources,
            )

        self.assertTrue(connection["ok"], connection)
        self.assertEqual(organization_settings["mode"], ORGANIZATION_MODE)
        self.assertEqual(organization_settings["organization"]["organization_id"], "sandbox")
        self.assertEqual(len(organization_sources), 1)
        self.assertEqual([item["id"] for item in organization_payload["results"]], ["org-card"])
        self.assertEqual(organization_payload["results"][0]["source_info"]["kind"], "organization")
        self.assertEqual(personal_settings["mode"], PERSONAL_MODE)
        self.assertEqual(personal_sources, [])
        self.assertEqual(personal_payload["results"], [])

    def test_invalid_source_cannot_force_organization_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "invalid-source"
            repo = root / "machine"
            source.mkdir(parents=True)
            (source / "README.md").write_text("not an organization KB", encoding="utf-8")
            self._commit_repo(source)

            connection = connect_organization_source(repo, str(source))
            save_desktop_settings(
                repo,
                {
                    "mode": ORGANIZATION_MODE,
                    "organization": connection["settings"],
                },
            )
            settings = load_desktop_settings(repo)

        self.assertFalse(connection["ok"], connection)
        self.assertEqual(connection["settings"]["validation_status"], "invalid")
        self.assertEqual(settings["mode"], PERSONAL_MODE)
        self.assertFalse(settings["organization"]["validated"])
        self.assertEqual(organization_sources_from_settings(settings), [])


if __name__ == "__main__":
    unittest.main()
