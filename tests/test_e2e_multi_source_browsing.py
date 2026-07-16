from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.settings import ORGANIZATION_MODE, load_desktop_settings, organization_sources_from_settings, save_desktop_settings
from local_kb.store import load_yaml_file, write_yaml_file
from local_kb.ui_data import build_card_detail_payload, build_search_payload, build_source_view_payload
from tests.current_runtime_helpers import activate_current_kb_runtime


class MultiSourceBrowsingE2ETests(unittest.TestCase):
    def _card(self, entry_id: str, title: str, guidance: str) -> dict:
        return {
            "id": entry_id,
            "title": title,
            "type": "model",
            "scope": "public",
            "status": "trusted",
            "confidence": 0.9,
            "domain_path": ["shared", "organization"],
            "tags": ["shared", "organization"],
            "trigger_keywords": ["shared", "organization"],
            "if": {"notes": "Shared browsing scenario."},
            "action": {"description": "Use the shared browsing card."},
            "predict": {"expected_result": "The expected source is visible."},
            "use": {"guidance": guidance},
        }

    def _save_organization_settings(self, repo: Path, org: Path) -> list[dict]:
        save_desktop_settings(
            repo,
            {
                "mode": ORGANIZATION_MODE,
                "organization": {
                    "repo_url": str(org),
                    "local_mirror_path": str(org),
                    "organization_id": "sandbox",
                    "validated": True,
                    "validation_status": "valid",
                    "validation_message": "ok",
                    "last_sync_commit": "abc1234",
                },
            },
        )
        return organization_sources_from_settings(load_desktop_settings(repo))

    def test_settings_sourced_browsing_hides_same_hash_and_surfaces_new_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "machine"
            org = root / "org"
            same_guidance = "Use the same durable organization guidance."
            write_yaml_file(repo / "kb" / "public" / "local.yaml", self._card("local-card", "Shared card", same_guidance))
            write_yaml_file(org / "kb" / "main" / "org.yaml", self._card("org-card", "Shared card", same_guidance))
            sources = self._save_organization_settings(repo, org)
            activate_current_kb_runtime(repo)

            initial_payload = build_search_payload(repo, "shared organization", organization_sources=sources)
            local_source_payload = build_source_view_payload(repo, "local", organization_sources=sources)
            organization_source_payload = build_source_view_payload(repo, "organization", organization_sources=sources)

            changed = load_yaml_file(org / "kb" / "main" / "org.yaml")
            changed["use"]["guidance"] = "Use the updated organization guidance."
            write_yaml_file(org / "kb" / "main" / "org.yaml", changed)
            changed_payload = build_search_payload(repo, "shared organization", organization_sources=sources)
            organization_summary = next(
                item for item in changed_payload["results"] if item["source_info"]["kind"] == "organization"
            )
            detail = build_card_detail_payload(
                repo,
                "org-card",
                organization_sources=sources,
                source_info=organization_summary["source_info"],
            )

        self.assertEqual([item["id"] for item in initial_payload["results"]], ["local-card"])
        self.assertEqual([item["id"] for item in local_source_payload["deck"]], ["local-card"])
        self.assertEqual(organization_source_payload["deck"], [])
        self.assertEqual([item["source_info"]["kind"] for item in changed_payload["results"]], ["local", "organization"])
        self.assertIsNotNone(detail)
        assert detail is not None
        self.assertEqual(detail["id"], "org-card")
        self.assertEqual(detail["source_info"]["kind"], "organization")
        self.assertTrue(detail["read_only"])


if __name__ == "__main__":
    unittest.main()
