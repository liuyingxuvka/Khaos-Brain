from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.adoption import ADOPTION_KEY, adoption_content_hash, card_exchange_hash, record_exchange_hash
from local_kb.org_outbox import build_organization_outbox
from local_kb.store import load_yaml_file, write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


class OrganizationOutboxTests(unittest.TestCase):
    def _card(self, entry_id: str, card_type: str = "model", scope: str = "public") -> dict:
        return {
            "id": entry_id,
            "title": f"{entry_id} title",
            "type": card_type,
            "scope": scope,
            "status": "trusted",
            "confidence": 0.8,
            "domain_path": ["shared"],
            "tags": ["shared"],
            "trigger_keywords": ["shared"],
            "if": {"notes": "Shareable scenario."},
            "action": {"description": "Use card."},
            "predict": {"expected_result": "Card helps."},
            "use": {"guidance": "Share only when eligible."},
        }

    def _adopted_card(self, entry_id: str, *, diverged: bool = False) -> dict:
        payload = self._card(entry_id)
        source_hash = adoption_content_hash(payload)
        payload[ADOPTION_KEY] = {
            "organization_id": "sandbox",
            "source_entry_id": entry_id,
            "source_repo": "https://example.invalid/org.git",
            "source_commit": "abc123",
            "source_path": f"kb/trusted/{entry_id}.yaml",
            "adopted_at": "2026-04-24T00:00:00Z",
            "last_used_at": "2026-04-24T00:00:00Z",
            "source_content_hash": source_hash,
            "state": "clean",
        }
        if diverged:
            payload["use"]["guidance"] = "Local improvement should become organization feedback."
        return payload

    def test_outbox_only_exports_shareable_cards_and_diverged_adoptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(root / "kb" / "public" / "model.yaml", self._card("share-model"))
            duplicate = self._card("share-model-duplicate")
            duplicate["title"] = "share-model title"
            write_yaml_file(root / "kb" / "public" / "z-model-copy.yaml", duplicate)
            write_yaml_file(root / "kb" / "public" / "preference.yaml", self._card("skip-pref", card_type="preference"))
            write_yaml_file(root / "kb" / "private" / "private.yaml", self._card("skip-private", scope="private"))
            write_yaml_file(root / "kb" / "candidates" / "adopted" / "sandbox" / "clean.yaml", self._adopted_card("clean-adopted"))
            write_yaml_file(
                root / "kb" / "candidates" / "adopted" / "sandbox" / "diverged.yaml",
                self._adopted_card("diverged-adopted", diverged=True),
            )
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")
            created_ids = [item["entry_id"] for item in result["created"]]
            outbox_files = sorted((root / "kb" / "outbox" / "organization" / "sandbox").glob("*.yaml"))
            payloads = [load_yaml_file(path) for path in outbox_files]

        self.assertTrue(result["ok"])
        self.assertEqual(created_ids, ["share-model", "diverged-adopted"])
        self.assertEqual(len(payloads), 2)
        self.assertTrue(all(payload["status"] == "candidate" for payload in payloads))
        by_id = {payload["id"]: payload for payload in payloads}
        self.assertEqual(by_id["diverged-adopted"]["organization_proposal"]["proposal_kind"], "adopted-feedback")
        self.assertTrue(all(payload["organization_proposal"]["content_hash"] for payload in payloads))
        skipped = {item["entry_id"]: item["reasons"] for item in result["skipped"]}
        self.assertIn("duplicate content hash already exported", skipped["share-model-duplicate"])
        self.assertIn("card type is not shareable", skipped["skip-pref"])
        self.assertIn("card scope is not public", skipped["skip-private"])
        self.assertIn("clean adopted organization card does not need feedback", skipped["clean-adopted"])

    def test_outbox_dry_run_does_not_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_yaml_file(root / "kb" / "public" / "model.yaml", self._card("share-model"))
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox", dry_run=True)

            self.assertTrue(result["ok"])
            self.assertEqual(result["created_count"], 1)
            self.assertFalse((root / "kb" / "outbox").exists())

    def test_outbox_blocks_machine_specific_payloads_before_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secret = self._card("secret-card")
            secret["action"] = {
                "description": "Never publish this machine-bound payload.",
                "api_key": "sk-abcdefghijklmnopqrstuvwxyz123456",
                "workspace": r"C:\Users\alice\private-workspace",
                "machine_id": "machine-123",
            }
            write_yaml_file(root / "kb" / "public" / "secret.yaml", secret)
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["created_count"], 0)
        self.assertEqual(result["privacy_checkpoint"]["reviewed_count"], 1)
        self.assertEqual(result["privacy_checkpoint"]["blocked_sensitive_count"], 1)
        self.assertFalse((root / "kb" / "outbox").exists())
        reasons = result["skipped"][0]["reasons"]
        self.assertTrue(any("secret" in reason.lower() for reason in reasons), reasons)
        self.assertTrue(any("local machine path" in reason.lower() for reason in reasons), reasons)
        self.assertTrue(any("machine identifier" in reason.lower() for reason in reasons), reasons)

    def test_diverged_adoption_exports_feedback_without_local_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            adopted = self._adopted_card("diverged-local-source", diverged=True)
            adopted[ADOPTION_KEY]["source_repo"] = r"C:\Users\alice\org-clone"
            adopted[ADOPTION_KEY]["source_path"] = r"C:\Users\alice\org-clone\kb\main\card.yaml"
            write_yaml_file(
                root / "kb" / "candidates" / "adopted" / "sandbox" / "diverged.yaml",
                adopted,
            )
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")
            payload = load_yaml_file(
                root
                / "kb"
                / "outbox"
                / "organization"
                / "sandbox"
                / "diverged-local-source.yaml"
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["created_count"], 1, result)
        self.assertEqual(payload["organization_proposal"]["proposal_kind"], "adopted-feedback")
        self.assertEqual(payload["organization_proposal"]["source_repo"], "")
        self.assertNotIn(ADOPTION_KEY, payload)
        self.assertNotIn(r"C:\Users\alice", str(payload))

    def test_outbox_blocks_skill_dependency_without_usefulness_outcome_and_unavailable_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            card = self._card("incomplete-skill-card")
            card["required_skills"] = ["demo-skill"]
            card["use"] = {"guidance": "The Skill may help."}
            write_yaml_file(root / "kb" / "public" / "incomplete.yaml", card)
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["created_count"], 0)
        checkpoint = result["skill_bundle_checkpoint"]
        self.assertEqual(checkpoint["dependency_evidence_reviewed_count"], 1)
        self.assertEqual(checkpoint["dependency_evidence_blocked_count"], 1)
        reasons = result["skipped"][0]["reasons"]
        self.assertTrue(any("unavailable-skill-guidance" in reason for reason in reasons), reasons)

    def test_outbox_skips_hashes_already_exported_or_present_in_organization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            write_yaml_file(root / "kb" / "public" / "model.yaml", self._card("share-model"))
            write_yaml_file(org / "kb" / "main" / "existing.yaml", self._card("existing-org"))
            write_yaml_file(org / "kb" / "imports" / "alice" / "existing-import.yaml", self._card("existing-import"))
            local_duplicate = self._card("local-duplicate")
            local_duplicate["title"] = "existing-org title"
            write_yaml_file(root / "kb" / "public" / "local-duplicate.yaml", local_duplicate)
            import_duplicate = self._card("import-duplicate")
            import_duplicate["title"] = "existing-import title"
            write_yaml_file(root / "kb" / "public" / "import-duplicate.yaml", import_duplicate)
            sources = [{"path": str(org), "organization_id": "sandbox"}]
            activate_current_kb_runtime(root)

            first = build_organization_outbox(root, organization_id="sandbox", organization_sources=sources)
            record_exchange_hash(
                root,
                first["created"][0]["content_hash"],
                direction="uploaded",
                organization_id="sandbox",
                source_path=first["created"][0]["source_path"],
                entry_id=first["created"][0]["entry_id"],
            )
            second = build_organization_outbox(root, organization_id="sandbox", organization_sources=sources)

        self.assertEqual([item["entry_id"] for item in first["created"]], ["share-model"])
        first_skipped = {item["entry_id"]: item["reasons"] for item in first["skipped"]}
        self.assertIn("content hash already exists in organization repository", first_skipped["local-duplicate"])
        self.assertIn("content hash already exists in organization repository", first_skipped["import-duplicate"])
        self.assertEqual(second["created_count"], 0)
        second_skipped = {item["entry_id"]: item["reasons"] for item in second["skipped"]}
        self.assertIn("content hash was already exchanged with organization", second_skipped["share-model"])

    def test_outbox_skips_hashes_previously_downloaded_from_organization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            downloaded = self._card("previously-downloaded")
            write_yaml_file(root / "kb" / "public" / "downloaded.yaml", downloaded)
            record_exchange_hash(
                root,
                card_exchange_hash(downloaded),
                direction="downloaded",
                organization_id="sandbox",
                source_path="kb/trusted/previously-downloaded.yaml",
                entry_id="previously-downloaded",
            )
            activate_current_kb_runtime(root)

            result = build_organization_outbox(root, organization_id="sandbox")

        self.assertEqual(result["created_count"], 0)
        skipped = {item["entry_id"]: item["reasons"] for item in result["skipped"]}
        self.assertIn("content hash was already exchanged with organization", skipped["previously-downloaded"])


if __name__ == "__main__":
    unittest.main()
