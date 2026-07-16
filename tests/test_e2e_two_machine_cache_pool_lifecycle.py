from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.adoption import ADOPTION_KEY, adopt_organization_entry_by_source_info
from local_kb.org_outbox import build_organization_outbox
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.store import load_yaml_file
from local_kb.ui_data import build_search_payload
from tests.org_helpers import (
    ORGANIZATION_ID,
    connect_profile_to_org,
    init_git_repo,
    publish_accepted_outbox_to_org_main,
    write_local_skill_backed_card,
    write_valid_org_repo,
)


class TwoMachineCachePoolLifecycleE2ETests(unittest.TestCase):
    def test_machine_b_syncs_org_cache_adopts_skill_card_and_exports_diverged_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org_repo = root / "org-source"
            machine_a = root / "machine-a"
            machine_b = root / "machine-b"
            write_valid_org_repo(org_repo, include_sandbox_cards=True)
            init_git_repo(org_repo)

            connect_a, sources_a = connect_profile_to_org(machine_a, org_repo)
            connect_b_initial, sources_b_initial = connect_profile_to_org(machine_b, org_repo)
            initial_b_payload = build_search_payload(
                machine_b,
                "Skill backed organization contribution",
                organization_sources=sources_b_initial,
            )

            write_local_skill_backed_card(machine_a)
            outbox_a = build_organization_outbox(
                machine_a,
                organization_id=ORGANIZATION_ID,
                organization_sources=sources_a,
            )
            created_main_files = publish_accepted_outbox_to_org_main(
                org_repo,
                Path(outbox_a["outbox_dir"]),
            )

            connect_b_synced, sources_b_synced = connect_profile_to_org(machine_b, org_repo)
            synced_b_payload = build_search_payload(
                machine_b,
                "Skill backed organization contribution",
                organization_sources=sources_b_synced,
            )
            org_summary = next(
                item for item in synced_b_payload["results"] if item["source_info"]["kind"] == "organization"
            )
            adoption_b = adopt_organization_entry_by_source_info(
                machine_b,
                "skill-backed-card",
                sources_b_synced,
                source_info=org_summary["source_info"],
            )
            adopted_path = Path(adoption_b["path"])
            adopted = load_yaml_file(adopted_path)
            adopted["use"]["guidance"] = "Machine B added practical feedback after using the organization card."
            publication = publish_sleep_model_generation(
                machine_b,
                reason="test-machine-b-organization-feedback",
                card_upserts={adopted_path.relative_to(machine_b).as_posix(): adopted},
            )
            self.assertTrue(publication["ok"], publication)

            outbox_b = build_organization_outbox(
                machine_b,
                organization_id=ORGANIZATION_ID,
                organization_sources=sources_b_synced,
            )
            installed_skill_files = sorted((machine_b / ".local" / "organization_skills").rglob("SKILL.md"))
            adopted_after = load_yaml_file(adopted_path)

        self.assertTrue(connect_a["ok"], connect_a)
        self.assertTrue(connect_b_initial["ok"], connect_b_initial)
        self.assertNotIn("skill-backed-card", [item["id"] for item in initial_b_payload["results"]])
        self.assertTrue(outbox_a["ok"], outbox_a)
        self.assertEqual(outbox_a["created_count"], 1)
        self.assertIn("kb/main/skill-backed-card.yaml", created_main_files)
        self.assertTrue(connect_b_synced["ok"], connect_b_synced)
        self.assertNotEqual(
            connect_b_initial["settings"]["last_sync_commit"],
            connect_b_synced["settings"]["last_sync_commit"],
        )
        self.assertEqual(org_summary["id"], "skill-backed-card")
        self.assertEqual(org_summary["source_info"]["scope"], "candidate")
        self.assertTrue(adoption_b["ok"], adoption_b)
        self.assertTrue(adoption_b["created"])
        self.assertEqual(len(installed_skill_files), 1)
        self.assertEqual(adopted_after[ADOPTION_KEY]["organization_id"], ORGANIZATION_ID)
        self.assertEqual(outbox_b["created_count"], 1, outbox_b)
        self.assertEqual(outbox_b["created"][0]["proposal_kind"], "adopted-feedback")


if __name__ == "__main__":
    unittest.main()
