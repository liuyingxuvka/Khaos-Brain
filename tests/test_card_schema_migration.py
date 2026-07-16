from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.card_schema_migration import migrate_skill_guidance_fields_to_current
from local_kb.org_outbox import skill_dependency_evidence
from local_kb.store import load_yaml_file, write_yaml_file


class CardSchemaMigrationTests(unittest.TestCase):
    def test_upgrade_rewrites_old_skill_guidance_field_and_repeat_is_no_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "kb" / "candidates" / "card.yaml"
            write_yaml_file(
                card,
                {
                    "id": "card",
                    "status": "candidate",
                    "use": {"fallback": "Keep the dependency pending."},
                },
            )

            migration = migrate_skill_guidance_fields_to_current(root)
            current = load_yaml_file(card)
            repeated = migrate_skill_guidance_fields_to_current(root)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertEqual(current["use"]["unavailable_skill_guidance"], "Keep the dependency pending.")
        self.assertNotIn("fallback", current["use"])
        self.assertEqual(repeated["status"], "no_delta")

    def test_upgrade_blocks_conflicting_old_and_current_skill_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "kb" / "private" / "card.yaml"
            write_yaml_file(
                card,
                {
                    "id": "card",
                    "use": {
                        "fallback": "old",
                        "unavailable_skill_guidance": "current",
                    },
                },
            )

            migration = migrate_skill_guidance_fields_to_current(root)
            after = load_yaml_file(card)

        self.assertFalse(migration["ok"], migration)
        self.assertEqual(migration["status"], "blocked")
        self.assertEqual(after["use"]["fallback"], "old")

    def test_upgrade_restores_cards_when_current_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = root / "kb" / "public" / "card.yaml"
            write_yaml_file(card, {"id": "card", "use": {"without_skill": "manual"}})

            with patch(
                "local_kb.card_schema_migration.write_yaml_file",
                side_effect=RuntimeError("forced write failure"),
            ):
                migration = migrate_skill_guidance_fields_to_current(root)
            after = load_yaml_file(card)

        self.assertFalse(migration["ok"], migration)
        self.assertEqual(migration["status"], "rolled_back")
        self.assertEqual(after["use"]["without_skill"], "manual")

    def test_daily_dependency_reader_does_not_accept_old_field_aliases(self) -> None:
        evidence = skill_dependency_evidence(
            {
                "skills": [{"id": "skill.demo"}],
                "action": {"description": "Use the Skill."},
                "predict": {"expected_result": "The task completes."},
                "use": {"fallback": "old alias"},
            }
        )

        self.assertFalse(evidence["ok"])
        self.assertIn("unavailable-skill-guidance", evidence["missing_fields"])


if __name__ == "__main__":
    unittest.main()
