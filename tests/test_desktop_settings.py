from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.settings import (
    ORGANIZATION_MODE,
    PERSONAL_MODE,
    load_desktop_settings,
    maintenance_participation_status_from_settings,
    organization_sources_from_settings,
    save_desktop_settings,
)


class DesktopSettingsTests(unittest.TestCase):
    def test_default_settings_are_personal_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = load_desktop_settings(Path(tmp))

        self.assertEqual(settings["mode"], PERSONAL_MODE)
        self.assertFalse(settings["organization"]["validated"])
        self.assertEqual(settings["organization"]["validation_status"], "not_configured")

    def test_legacy_language_only_settings_still_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"language": "zh-CN"}), encoding="utf-8")

            settings = load_desktop_settings(root)

        self.assertEqual(settings["language"], "zh-CN")
        self.assertEqual(settings["mode"], PERSONAL_MODE)

    def test_organization_mode_requires_validated_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_desktop_settings(
                root,
                {
                    "mode": ORGANIZATION_MODE,
                    "organization": {
                        "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                        "validation_status": "invalid",
                        "validated": False,
                    },
                },
            )

            settings = load_desktop_settings(root)

        self.assertEqual(settings["mode"], PERSONAL_MODE)
        self.assertEqual(settings["organization"]["repo_url"], "https://github.com/example/khaos-org-kb-sandbox.git")

    def test_valid_organization_settings_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_desktop_settings(
                root,
                {
                    "language": "en",
                    "mode": ORGANIZATION_MODE,
                    "organization": {
                        "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                        "local_mirror_path": "C:/Users/example/.khaos/org/sandbox",
                        "organization_id": "sandbox",
                        "validated": True,
                        "validation_status": "valid",
                        "validation_message": "ok",
                        "last_validated_at": "2026-04-24T15:00:00Z",
                        "last_sync_commit": "abc1234",
                        "last_sync_at": "2026-04-24T15:01:00Z",
                    },
                },
            )

            settings = load_desktop_settings(root)

        self.assertEqual(settings["mode"], ORGANIZATION_MODE)
        self.assertTrue(settings["organization"]["validated"])
        self.assertEqual(settings["organization"]["organization_id"], "sandbox")
        self.assertEqual(settings["organization"]["last_sync_commit"], "abc1234")

    def test_organization_sources_are_only_active_for_valid_organization_mode(self) -> None:
        settings = {
            "mode": ORGANIZATION_MODE,
            "organization": {
                "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                "local_mirror_path": "C:/mirror/sandbox",
                "organization_id": "sandbox",
                "validated": True,
                "validation_status": "valid",
                "last_sync_commit": "abc1234",
            },
        }

        sources = organization_sources_from_settings(settings)

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["path"], "C:/mirror/sandbox")
        self.assertEqual(sources[0]["organization_id"], "sandbox")
        settings["mode"] = PERSONAL_MODE
        self.assertEqual(organization_sources_from_settings(settings), [])

    def test_organization_maintenance_participation_requires_only_validated_organization(self) -> None:
        settings = {
            "mode": ORGANIZATION_MODE,
            "organization": {
                "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                "local_mirror_path": "C:/mirror/sandbox",
                "organization_id": "sandbox",
                "validated": True,
                "validation_status": "valid",
                "organization_maintenance_requested": True,
            },
        }

        status = maintenance_participation_status_from_settings(settings)

        self.assertTrue(status["requested"])
        self.assertTrue(status["available"])
        self.assertIn("enabled", status["reason"])

    def test_organization_maintenance_valid_state_clears_stale_permission_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_desktop_settings(
                root,
                {
                    "mode": ORGANIZATION_MODE,
                    "organization": {
                        "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                        "local_mirror_path": "C:/mirror/sandbox",
                        "organization_id": "sandbox",
                        "validated": True,
                        "validation_status": "valid",
                        "organization_maintenance_requested": True,
                        "organization_maintenance_status": "pending",
                        "organization_maintenance_message": "GitHub cloud checks have not validated a maintenance proposal yet",
                        "maintainer_validated": False,
                        "maintainer_validation_status": "not_configured",
                    },
                },
            )

            settings = load_desktop_settings(root)

        organization = settings["organization"]
        self.assertTrue(organization["organization_maintenance_validated"])
        self.assertEqual(organization["organization_maintenance_status"], "valid")
        self.assertEqual(organization["organization_maintenance_message"], "")
        self.assertFalse(organization["maintainer_validated"])
        self.assertEqual(organization["maintainer_validation_status"], "not_configured")

    def test_legacy_maintainer_mode_setting_maps_to_maintenance_participation(self) -> None:
        settings = {
            "mode": ORGANIZATION_MODE,
            "organization": {
                "repo_url": "https://github.com/example/khaos-org-kb-sandbox.git",
                "local_mirror_path": "C:/mirror/sandbox",
                "organization_id": "sandbox",
                "validated": True,
                "validation_status": "valid",
                "maintainer_mode_requested": True,
            },
        }

        status = maintenance_participation_status_from_settings(settings)

        self.assertTrue(status["requested"])
        self.assertTrue(status["available"])


if __name__ == "__main__":
    unittest.main()
