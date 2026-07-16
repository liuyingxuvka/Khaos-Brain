from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from local_kb.settings_migration import migrate_desktop_settings_to_current
from local_kb.settings import (
    CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION,
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

    def test_daily_reader_rejects_pre_schema_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"language": "zh-CN"}), encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "not current"):
                load_desktop_settings(root)

    def test_upgrade_directly_rewrites_pre_schema_settings_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(json.dumps({"language": "zh-CN"}), encoding="utf-8")

            migration = migrate_desktop_settings_to_current(root)
            settings = load_desktop_settings(root)
            repeated = migrate_desktop_settings_to_current(root)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertEqual(settings["schema_version"], CURRENT_DESKTOP_SETTINGS_SCHEMA_VERSION)
        self.assertEqual(settings["language"], "zh-CN")
        self.assertEqual(settings["mode"], PERSONAL_MODE)
        self.assertEqual(repeated["status"], "no_delta")
        self.assertEqual(repeated["receipt"]["status"], "committed")

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
                    },
                },
            )

            settings = load_desktop_settings(root)

        organization = settings["organization"]
        self.assertTrue(organization["organization_maintenance_validated"])
        self.assertEqual(organization["organization_maintenance_status"], "valid")
        self.assertEqual(organization["organization_maintenance_message"], "")
        self.assertFalse(any(key.startswith("maintainer_") for key in organization))

    def test_upgrade_migrates_maintainer_fields_and_daily_state_has_zero_old_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
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
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "not current"):
                load_desktop_settings(root)
            migration = migrate_desktop_settings_to_current(root)
            settings = load_desktop_settings(root)
            status = maintenance_participation_status_from_settings(settings)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertTrue(status["requested"])
        self.assertTrue(status["available"])
        self.assertFalse(any(key.startswith("maintainer_") for key in settings["organization"]))

    def test_upgrade_blocks_conflicting_old_and_current_settings_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            original = {
                "mode": ORGANIZATION_MODE,
                "organization": {
                    "organization_maintenance_requested": False,
                    "maintainer_mode_requested": True,
                },
            }
            settings_path.write_text(json.dumps(original), encoding="utf-8")

            migration = migrate_desktop_settings_to_current(root)
            after = json.loads(settings_path.read_text(encoding="utf-8"))

        self.assertFalse(migration["ok"], migration)
        self.assertEqual(migration["status"], "blocked")
        self.assertEqual(after, original)

    def test_upgrade_ai_resolution_selects_one_exact_value_and_records_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings_path = root / ".local" / "khaos_brain_desktop_settings.json"
            settings_path.parent.mkdir(parents=True)
            settings_path.write_text(
                json.dumps(
                    {
                        "mode": ORGANIZATION_MODE,
                        "organization": {
                            "validated": True,
                            "validation_status": "valid",
                            "organization_maintenance_requested": True,
                            "organization_maintenance_validated": True,
                            "maintainer_validated": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            migration = migrate_desktop_settings_to_current(
                root,
                conflict_resolution={"organization_maintenance_validated": True},
                resolution_reason="Current value matches the validated organization source.",
            )
            settings = load_desktop_settings(root)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertTrue(settings["organization"]["organization_maintenance_validated"])
        self.assertFalse(any(key.startswith("maintainer_") for key in settings["organization"]))
        resolution = migration["receipt"]["ai_conflict_resolution"]
        self.assertEqual(resolution["resolver"], "ai-upgrade-owner")
        self.assertTrue(
            resolution["fields"]["organization_maintenance_validated"]["selected_value"]
        )

    def test_save_rejects_obsolete_settings_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "upgrade-only input"):
                save_desktop_settings(
                    Path(tmp),
                    {"organization": {"maintainer_mode_requested": True}},
                )


if __name__ == "__main__":
    unittest.main()
