from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from local_kb.adoption import (
    ADOPTION_KEY,
    adopt_organization_entry_by_source_info,
    adoption_state,
    card_exchange_hash,
)
from local_kb.skill_sharing import skill_directory_content_hash
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.search import render_search_payload, search_multi_source_entries
from local_kb.store import load_yaml_file, write_yaml_file
from local_kb.ui_data import build_search_payload
from tests.current_runtime_helpers import activate_current_kb_runtime


class OrganizationAdoptionTests(unittest.TestCase):
    def _write_org_card(self, org: Path) -> None:
        write_yaml_file(
            org / "kb" / "main" / "org-card.yaml",
            {
                "id": "org-card",
                "title": "Organization shared card",
                "type": "model",
                "scope": "public",
                "status": "trusted",
                "confidence": 0.9,
                "updated_at": date(2026, 4, 24),
                "domain_path": ["shared"],
                "tags": ["shared", "organization"],
                "trigger_keywords": ["shared", "organization"],
                "if": {"notes": "Shared org scenario."},
                "action": {"description": "Use org card."},
                "predict": {"expected_result": "Org card is available."},
                "use": {"guidance": "Adopt before local maintenance."},
            },
        )

    def test_organization_card_copy_on_use_creates_local_clean_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox", "repo_url": "https://example.invalid/org.git"}]
            activate_current_kb_runtime(root)
            search_payload = build_search_payload(root, "shared organization", organization_sources=sources)

            result = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=search_payload["results"][0]["source_info"],
            )
            adopted = load_yaml_file(Path(result["path"]))

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["created"])
        self.assertRegex(adopted["id"], r"^cand-\d{8}T\d{6}Z-inst[0-9a-f]{8}-[0-9a-f]{6}$")
        self.assertNotEqual(adopted["id"], "org-card")
        self.assertEqual(adopted[ADOPTION_KEY]["organization_id"], "sandbox")
        self.assertEqual(adopted[ADOPTION_KEY]["source_entry_id"], "org-card")
        self.assertEqual(adopted[ADOPTION_KEY]["source_exchange_hash"], card_exchange_hash(adopted))
        self.assertEqual(adoption_state(adopted), "clean")

    def test_organization_card_use_reuses_existing_same_hash_local_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            local_payload = load_yaml_file(org / "kb" / "main" / "org-card.yaml")
            local_payload["id"] = "local-card"
            local_payload["i18n"] = {"zh-CN": {"title": "本地已有同内容卡"}}
            write_yaml_file(root / "kb" / "public" / "local.yaml", local_payload)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)

            result = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
            )
            search_after = render_search_payload(
                search_multi_source_entries(root, "shared organization", organization_sources=sources, top_k=5),
                root,
            )
            adopted_path_exists = (root / "kb" / "candidates" / "adopted" / "sandbox" / "org-card.yaml").exists()

        self.assertTrue(result["ok"], result)
        self.assertFalse(result["created"])
        self.assertTrue(result["matched_existing"])
        self.assertEqual(result["entry_id"], "local-card")
        self.assertFalse(adopted_path_exists)
        self.assertEqual([item["id"] for item in search_after], ["local-card"])

    def test_multi_source_search_hides_organization_card_after_local_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)
            adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )

            payload = render_search_payload(
                search_multi_source_entries(root, "shared organization", organization_sources=sources, top_k=5),
                root,
            )

        self.assertEqual([item["source_info"]["kind"] for item in payload], ["local"])
        self.assertRegex(payload[0]["id"], r"^cand-\d{8}T\d{6}Z-inst[0-9a-f]{8}-[0-9a-f]{6}$")
        self.assertEqual(payload[0]["source_info"]["scope"], "candidate")

    def test_downloaded_hash_ledger_prevents_same_organization_payload_from_reappearing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)
            result = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            adopted_path = Path(result["path"])
            publication = publish_sleep_model_generation(
                root,
                reason="test-organization-adoption-delete",
                card_deletes=(adopted_path.relative_to(root).as_posix(),),
            )
            self.assertTrue(publication["ok"], publication)

            payload = render_search_payload(
                search_multi_source_entries(root, "shared organization", organization_sources=sources, top_k=5),
                root,
            )

        self.assertEqual(payload, [])

    def test_adopting_organization_card_installs_card_bound_skill_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            skill_dir = org / "kb" / "main" / "skills" / "bundle-demo" / "skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Shared Skill.\n---\n\nUse shared Skill.",
                encoding="utf-8",
            )
            expected_hash = skill_directory_content_hash(skill_dir)
            card = load_yaml_file(org / "kb" / "main" / "org-card.yaml")
            card["organization_proposal"] = {
                "skill_dependencies": [
                    {
                        "id": "demo-skill",
                        "sharing_mode": "card-bound-bundle",
                        "bundle_id": "skill-bundle-demo",
                        "bundle_path": "skills/bundle-demo/skill",
                        "content_hash": expected_hash,
                        "version_time": "2026-04-24T12:00:00Z",
                        "original_author": "alice",
                        "readonly_when_imported": True,
                        "update_policy": "original_author_only",
                    }
                ]
            }
            write_yaml_file(org / "kb" / "main" / "org-card.yaml", card)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)

            result = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            installed = sorted((root / ".local" / "organization_skills" / "skill-bundle-demo").rglob("SKILL.md"))
            bundle_metadata = load_yaml_file(root / ".local" / "organization_skills" / "skill-bundle-demo" / "metadata.yaml")

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["installed_skill_bundles"]["ok"], result)
        self.assertEqual(len(installed), 1)
        self.assertEqual(bundle_metadata["latest_version"]["content_hash"], expected_hash)

    def test_same_id_organization_card_with_new_hash_surfaces_after_prior_adoption(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)
            adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            changed = load_yaml_file(org / "kb" / "main" / "org-card.yaml")
            changed["use"]["guidance"] = "Organization published a new content version."
            write_yaml_file(org / "kb" / "main" / "org-card.yaml", changed)

            payload = render_search_payload(
                search_multi_source_entries(root, "shared organization", organization_sources=sources, top_k=5),
                root,
            )

        self.assertEqual([item["source_info"]["kind"] for item in payload], ["local", "organization"])
        self.assertRegex(payload[0]["id"], r"^cand-\d{8}T\d{6}Z-inst[0-9a-f]{8}-[0-9a-f]{6}$")
        self.assertEqual(payload[1]["id"], "org-card")

    def test_reusing_organization_card_updates_existing_adoption_usage_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)
            first = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            second = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            adopted = load_yaml_file(Path(first["path"]))

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["path"], second["path"])
        self.assertEqual(adopted[ADOPTION_KEY]["hit_count"], 2)
        self.assertEqual(second["hit_count"], 2)
        self.assertEqual(adoption_state(adopted), "clean")

    def test_adoption_state_detects_local_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            self._write_org_card(org)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)
            initial = build_search_payload(root, "shared organization", organization_sources=sources)
            result = adopt_organization_entry_by_source_info(
                root,
                "org-card",
                sources,
                source_info=initial["results"][0]["source_info"],
            )
            adopted_path = Path(result["path"])
            adopted = load_yaml_file(adopted_path)
            adopted["use"]["guidance"] = "Local maintenance changed this card."
            write_yaml_file(adopted_path, adopted)
            changed = load_yaml_file(adopted_path)

        self.assertEqual(adoption_state(changed), "diverged")


if __name__ == "__main__":
    unittest.main()
