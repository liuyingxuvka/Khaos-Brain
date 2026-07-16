from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_checks import check_organization_repository
from local_kb.org_cleanup import apply_organization_cleanup_proposal, build_organization_cleanup_proposal
from local_kb.store import load_yaml_file, write_yaml_file
from local_kb.ui_data import build_search_payload
from tests.org_helpers import activate_current_kb_runtime, base_card, write_valid_org_repo


class OrganizationCleanupTests(unittest.TestCase):
    def _write_cleanup_repo(self, root: Path) -> None:
        write_valid_org_repo(root, include_sandbox_cards=False)
        trusted_low = base_card(
            "trusted-low",
            "Old trusted route",
            "This trusted card has weak evidence and should be scored down.",
            status="trusted",
            confidence=0.4,
        )
        duplicate_a = base_card(
            "duplicate-a",
            "Duplicate candidate",
            "Keep only one copy of this organization candidate.",
            status="candidate",
            confidence=0.7,
        )
        duplicate_b = dict(duplicate_a)
        duplicate_b["id"] = "duplicate-b"
        weak = base_card(
            "weak-card",
            "Random weak candidate",
            "Random unreviewed text without durable organization value.",
            status="candidate",
            confidence=0.2,
        )
        strong = base_card(
            "strong-card",
            "Strong candidate",
            "Strong evidence should produce a promotion proposal, not direct low-risk apply.",
            status="candidate",
            confidence=0.9,
        )
        stale = base_card(
            "stale-rejected",
            "Stale rejected card",
            "Already rejected and low value.",
            status="rejected",
            confidence=0.1,
        )
        similar = base_card(
            "similar-card",
            "Duplicate candidate",
            "A similar but not identical candidate should trigger merge review.",
            status="candidate",
            confidence=0.72,
        )
        smoke = base_card(
            "auto-merge-smoke",
            "Organization auto-merge smoke test candidate",
            "This fixture checks organization auto-merge behavior.",
            status="candidate",
            confidence=0.55,
        )
        incoming = base_card(
            "incoming-card",
            "Incoming import candidate",
            "Imported candidate should be reviewed into main, not used directly from imports.",
            status="candidate",
            confidence=0.7,
        )
        smoke["tags"] = ["organization-kb", "auto-merge", "smoke-test"]
        write_yaml_file(root / "kb" / "main" / "trusted" / "trusted-low.yaml", trusted_low)
        write_yaml_file(root / "kb" / "main" / "candidates" / "duplicate-a.yaml", duplicate_a)
        write_yaml_file(root / "kb" / "main" / "candidates" / "duplicate-b.yaml", duplicate_b)
        write_yaml_file(root / "kb" / "main" / "candidates" / "weak-card.yaml", weak)
        write_yaml_file(root / "kb" / "main" / "candidates" / "strong-card.yaml", strong)
        write_yaml_file(root / "kb" / "main" / "candidates" / "stale-rejected.yaml", stale)
        write_yaml_file(root / "kb" / "main" / "candidates" / "similar-card.yaml", similar)
        write_yaml_file(root / "kb" / "main" / "candidates" / "auto-merge-smoke.yaml", smoke)
        write_yaml_file(root / "kb" / "imports" / "alice" / "incoming-card.yaml", incoming)
        activate_current_kb_runtime(root)

    def test_cleanup_proposal_includes_duplicates_weak_cards_score_adjustments_and_review_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cleanup_repo(root)

            proposal = build_organization_cleanup_proposal(root)
            action_types = [item["action_type"] for item in proposal["actions"]]

        self.assertTrue(proposal["ok"], proposal)
        self.assertEqual(proposal["maintenance_model"]["role"], "organization-exchange-sleep")
        self.assertEqual(proposal["maintenance_model"]["incoming_lane"], "kb/imports")
        self.assertEqual(proposal["maintenance_model"]["exchange_surface"], "kb/main")
        self.assertEqual(proposal["maintenance_model"]["exchange_surface_content_maintenance"], "in-scope")
        self.assertEqual(proposal["maintenance_model"]["trusted_card_content_maintenance"], "in-scope")
        self.assertTrue(proposal["maintenance_model"]["local_final_adoption"])
        self.assertEqual(proposal["lane_policy"]["contribution_writes"], ["kb/imports"])
        self.assertEqual(proposal["lane_policy"]["maintenance_moves_reviewed_cards_to"], "kb/main")
        self.assertEqual(proposal["lane_policy"]["local_download_excluded_paths"], ["kb/imports"])
        self.assertIn("mark-duplicate", action_types)
        self.assertIn("status-adjust", action_types)
        self.assertIn("confidence-adjust", action_types)
        self.assertIn("delete-card", action_types)
        self.assertIn("merge-cards", action_types)
        self.assertIn("accept-import", action_types)
        promotion = next(item for item in proposal["actions"] if item.get("entry_id") == "strong-card")
        accepted_import = next(item for item in proposal["actions"] if item.get("entry_id") == "incoming-card")
        smoke = next(item for item in proposal["actions"] if item.get("entry_id") == "auto-merge-smoke")
        self.assertEqual(promotion["action_type"], "status-adjust")
        self.assertEqual(promotion["proposed_status"], "trusted")
        self.assertTrue(promotion["apply_supported"])
        self.assertTrue(promotion["target_path"].startswith("kb/main/"))
        self.assertEqual(accepted_import["action_type"], "accept-import")
        self.assertEqual(accepted_import["proposed_status"], "candidate")
        self.assertTrue(accepted_import["proposed_path"].startswith("kb/main/"))
        self.assertEqual(smoke["action_type"], "status-adjust")
        self.assertEqual(smoke["proposed_status"], "rejected")

    def test_cleanup_apply_updates_low_risk_actions_audits_and_keeps_checks_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cleanup_repo(root)
            proposal = build_organization_cleanup_proposal(root)

            result = apply_organization_cleanup_proposal(
                root,
                proposal,
                allow_actions={"confidence-adjust", "status-adjust", "mark-duplicate", "delete-card"},
                allow_trusted=True,
                allow_delete=True,
            )
            weak = load_yaml_file(root / "kb" / "main" / "candidates" / "weak-card.yaml")
            duplicate_b = load_yaml_file(root / "kb" / "main" / "candidates" / "duplicate-b.yaml")
            trusted_low = load_yaml_file(root / "kb" / "main" / "trusted" / "trusted-low.yaml")
            strong = load_yaml_file(root / "kb" / "main" / "candidates" / "strong-card.yaml")
            smoke = load_yaml_file(root / "kb" / "main" / "candidates" / "auto-merge-smoke.yaml")
            stale_exists = (root / "kb" / "main" / "candidates" / "stale-rejected.yaml").exists()
            check = check_organization_repository(root)
            rejected_search = build_search_payload(root, "Random weak candidate", organization_sources=[{"path": str(root), "organization_id": "sandbox"}])
            rejected_result_ids = [item["id"] for item in rejected_search["results"]]
            audit_exists = (root / "maintenance" / "cleanup_audit.jsonl").exists()

        self.assertTrue(result["ok"], result)
        self.assertGreaterEqual(result["applied_count"], 4)
        self.assertEqual(weak["status"], "rejected")
        self.assertEqual(duplicate_b["status"], "deprecated")
        self.assertEqual(duplicate_b["organization_cleanup"]["duplicate_of"], "kb/main/candidates/duplicate-a.yaml")
        self.assertLess(trusted_low["confidence"], 0.4)
        self.assertEqual(strong["status"], "trusted")
        self.assertEqual(smoke["status"], "rejected")
        self.assertFalse(stale_exists)
        self.assertTrue(check["ok"], check)
        self.assertNotIn("weak-card", rejected_result_ids)
        self.assertTrue(audit_exists)

    def test_cleanup_apply_upgrades_reviewed_main_candidate_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cleanup_repo(root)
            proposal = build_organization_cleanup_proposal(root)
            promotion = next(item for item in proposal["actions"] if item.get("entry_id") == "strong-card")

            result = apply_organization_cleanup_proposal(
                root,
                proposal,
                allow_actions={"status-adjust"},
                allow_action_ids={promotion["action_id"]},
                allow_trusted=True,
            )
            promoted_path = root / promotion["target_path"]
            promoted = load_yaml_file(promoted_path)
            check = check_organization_repository(root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["applied_count"], 1)
        self.assertEqual(promoted["status"], "trusted")
        self.assertEqual(promoted["organization_cleanup"]["last_action_type"], "status-adjust")
        self.assertTrue(check["ok"], check)

    def test_cleanup_apply_accepts_reviewed_import_to_main_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_cleanup_repo(root)
            proposal = build_organization_cleanup_proposal(root)
            incoming = next(item for item in proposal["actions"] if item.get("entry_id") == "incoming-card")

            result = apply_organization_cleanup_proposal(
                root,
                proposal,
                allow_actions={"accept-import"},
                allow_action_ids={incoming["action_id"]},
                allow_promote=True,
            )
            moved_path = root / incoming["proposed_path"]
            moved = load_yaml_file(moved_path)
            original_exists = (root / "kb" / "imports" / "alice" / "incoming-card.yaml").exists()
            check = check_organization_repository(root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["applied_count"], 1)
        self.assertFalse(original_exists)
        self.assertEqual(moved["status"], "candidate")
        self.assertEqual(moved["organization_cleanup"]["moved_to_main_from"], "kb/imports/alice/incoming-card.yaml")
        self.assertTrue(check["ok"], check)

    def test_maintenance_enforces_skill_author_hash_version_and_fork_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_valid_org_repo(root, include_sandbox_cards=False)
            older = base_card("older", "Older bundle card", "Use the original Skill lineage.", status="candidate")
            latest = base_card("latest", "Latest bundle card", "Use the newest original-author version.", status="candidate")
            newer = base_card("newer", "Newer bundle card", "A different author must fork.", status="candidate")
            for payload, author, version, digest in (
                (older, "author-a", "2026-01-01T00:00:00Z", "a" * 64),
                (latest, "author-a", "2026-03-01T00:00:00Z", "c" * 64),
                (newer, "author-b", "2026-04-01T00:00:00Z", "b" * 64),
            ):
                payload["organization_proposal"] = {
                    "skill_dependencies": [
                        {
                            "id": "demo-skill",
                            "sharing_mode": "card-bound-bundle",
                            "bundle_id": "shared-lineage",
                            "content_hash": f"sha256:{digest}",
                            "version_time": version,
                            "original_author": author,
                            "readonly_when_imported": True,
                            "update_policy": "original_author_only",
                            "bundle_path": "skills/shared-lineage/demo-skill",
                        }
                    ]
                }
            write_yaml_file(root / "kb" / "main" / "candidates" / "older.yaml", older)
            write_yaml_file(root / "kb" / "main" / "candidates" / "latest.yaml", latest)
            write_yaml_file(root / "kb" / "main" / "candidates" / "newer.yaml", newer)

            proposal = build_organization_cleanup_proposal(root)
            action_types = [str(item.get("action_type") or "") for item in proposal["actions"]]
            fork = next(item for item in proposal["actions"] if item.get("action_type") == "skill-bundle-fork-required")

        self.assertTrue(proposal["ok"], proposal)
        self.assertIn("skill-version-select", action_types)
        self.assertIn("skill-bundle-fork-required", action_types)
        self.assertEqual(fork["lineage_original_author"], "author-a")
        self.assertEqual(fork["conflicting_original_author"], "author-b")
        self.assertFalse(fork["apply_supported"])


if __name__ == "__main__":
    unittest.main()
