from __future__ import annotations

from datetime import date
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import local_kb.active_index as active_index_module
from local_kb.active_index import (
    active_index_authority_path,
    active_index_invalidation_path,
    active_index_path,
    load_active_entries,
    rebuild_active_index,
    validate_active_index,
    validate_active_index_fast,
)
from local_kb.calibration import calibrate_entry
from local_kb.lifecycle import (
    commit_lifecycle_event,
    load_lifecycle_state,
    record_outcome_receipt,
    transition_entry,
)
from local_kb.maintenance_standard import (
    CURRENT_MAINTENANCE_STANDARD_VERSION,
    write_maintenance_state,
)
from local_kb.logicguard_models import authority_generation_pointer_path
from local_kb.maintenance_migration import migrate_legacy_card_generation
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.search import render_search_payload, search_with_receipt
from local_kb.store import load_yaml_file, write_yaml_file


def activate_standard(repo_root: Path) -> None:
    write_maintenance_state(
        repo_root,
        {
            "maintenance_standard_version": CURRENT_MAINTENANCE_STANDARD_VERSION,
            "history_schema_version": 1,
            "phase": "committed",
            "committed": True,
        },
    )


def publish_current_cards(repo_root: Path, *, reason: str) -> dict:
    if authority_generation_pointer_path(repo_root).exists():
        result = publish_sleep_model_generation(repo_root, reason=reason)
    elif any(
        root.exists() and any(root.rglob("*.yaml"))
        for root in [repo_root / "kb" / scope for scope in ("public", "private", "candidates")]
    ):
        result = migrate_legacy_card_generation(repo_root)
    else:
        result = publish_sleep_model_generation(repo_root, reason=reason)
    if not result.get("ok"):
        raise RuntimeError(result)
    return result.get("index_receipt") or result.get("receipt", {}).get("active_index") or {}


def card(
    entry_id: str,
    status: str,
    *,
    eligible: bool = False,
    related_cards: list[str] | None = None,
) -> dict:
    return {
        "id": entry_id,
        "title": f"{entry_id} migration checkpoint guidance",
        "type": "model",
        "scope": "public",
        "domain_path": ["engineering", "migration", "checkpoint"],
        "tags": ["migration", "checkpoint"],
        "trigger_keywords": ["migration", "resume", "checkpoint"],
        "related_cards": related_cards or [],
        "if": {"notes": "A migration resumes after interruption."},
        "action": {"description": "Verify the checkpoint before resuming."},
        "predict": {"expected_result": "No side effect is duplicated."},
        "use": {"guidance": "Use the latest verified checkpoint."},
        "confidence": 0.8,
        "status": status,
        "retrieval_eligible": eligible,
        "updated_at": date(2026, 7, 11),
    }


class KbRetrievalCalibrationTests(unittest.TestCase):
    def test_rebuild_requires_authorized_publisher(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            with self.assertRaisesRegex(
                PermissionError,
                "Unauthorized active-index publisher",
            ):
                rebuild_active_index(
                    repo_root,
                    reason="unauthorized-test",
                    publisher_id="local_kb.search.search_with_receipt",
                )
            self.assertFalse(active_index_path(repo_root).exists())
            self.assertFalse(active_index_authority_path(repo_root).exists())
            self.assertFalse(active_index_invalidation_path(repo_root).exists())

    def test_verified_contradiction_immediately_suspends_trusted_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            entry_id = "trusted-contradiction"
            write_yaml_file(
                repo_root / "kb" / "public" / "trusted.yaml",
                card(entry_id, "trusted"),
            )
            transition_entry(
                repo_root,
                entry_id=entry_id,
                from_state="candidate",
                to_state="trusted",
                reason="Previously validated evidence.",
                actor="sleep",
                evidence_ids=["validation-old"],
                provenance_ids=["episode-old"],
                evidence_grade="strong",
            )
            publish_current_cards(repo_root, reason="test")
            _entries, retrieval = search_with_receipt(
                repo_root,
                query="migration checkpoint guidance",
            )
            record_outcome_receipt(
                repo_root,
                request_id=retrieval["request_id"],
                used_entry_ids=[entry_id],
                outcome="misleading",
                evidence_kind="test",
                evidence_ref="pytest:verified-regression",
                verified=True,
            )

            with self.assertRaisesRegex(RuntimeError, "invalidated"):
                search_with_receipt(
                    repo_root,
                    query="migration checkpoint guidance",
                    record_receipt=False,
                )
            publish_current_cards(repo_root, reason="verified-contradiction")
            after, _receipt = search_with_receipt(
                repo_root,
                query="migration checkpoint guidance",
                record_receipt=False,
            )
            calibration = calibrate_entry(repo_root, entry_id)

            self.assertEqual(after, [])
            self.assertTrue(calibration["downgrade_required"])
            self.assertEqual(
                load_lifecycle_state(repo_root)["entries"][entry_id]["status"],
                "parked",
            )

    def test_direct_identifier_lookup_does_not_traverse_unverified_legacy_relations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            write_yaml_file(
                repo_root / "kb" / "public" / "primary.yaml",
                card("primary-card", "trusted", related_cards=["related-card", "rejected-card"]),
            )
            related = card("related-card", "trusted")
            related["title"] = "Orthogonal safeguard with no lexical overlap"
            related["tags"] = ["orthogonal"]
            related["trigger_keywords"] = ["orthogonal"]
            related["if"] = {"notes": "An orthogonal condition."}
            related["action"] = {"description": "Apply an orthogonal safeguard."}
            related["predict"] = {"expected_result": "The linked safeguard remains visible."}
            related["use"] = {"guidance": "Use only through a current related-card link."}
            write_yaml_file(repo_root / "kb" / "public" / "related.yaml", related)
            write_yaml_file(
                repo_root / "kb" / "candidates" / "rejected.yaml",
                card("rejected-card", "rejected", eligible=True),
            )
            publish_current_cards(repo_root, reason="test")

            direct, _receipt = search_with_receipt(
                repo_root,
                query="open id:primary-card",
                record_receipt=False,
            )
            linked, _receipt = search_with_receipt(
                repo_root,
                query="resume migration checkpoint",
                top_k=3,
                record_receipt=False,
            )

            self.assertEqual(direct[0].data["id"], "primary-card")
            linked_ids = [entry.data["id"] for entry in linked]
            self.assertNotIn("related-card", linked_ids)
            self.assertNotIn("rejected-card", linked_ids)

    def test_active_index_excludes_terminal_states_and_serializes_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            write_yaml_file(repo_root / "kb" / "public" / "trusted.yaml", card("trusted", "trusted"))
            write_yaml_file(repo_root / "kb" / "candidates" / "candidate.yaml", card("candidate", "candidate", eligible=True))
            write_yaml_file(repo_root / "kb" / "candidates" / "rejected.yaml", card("rejected", "rejected", eligible=True))
            write_yaml_file(repo_root / "kb" / "candidates" / "superseded.yaml", card("superseded", "superseded", eligible=True))

            publish_current_cards(repo_root, reason="test")
            self.assertTrue(validate_active_index(repo_root)["ok"])
            entries, receipt = search_with_receipt(
                repo_root,
                query="resume migration checkpoint",
                path_hint="engineering/migration/checkpoint",
            )
            payload = render_search_payload(entries, repo_root)

            self.assertEqual([item["id"] for item in payload], ["trusted", "candidate"])
            self.assertEqual(payload[1]["trust_label"], "untrusted-candidate")
            self.assertTrue(receipt["request_id"])

    def test_stale_index_is_a_visible_failure_without_scan_alternative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            write_yaml_file(repo_root / "kb" / "public" / "card.yaml", card("card-1", "trusted"))
            publish_current_cards(repo_root, reason="test")
            transition_entry(
                repo_root,
                entry_id="card-1",
                from_state="trusted",
                to_state="superseded",
                reason="A newer rule replaced it.",
                actor="sleep",
                evidence_ids=["outcome-1"],
                provenance_ids=["legacy-card"],
                evidence_grade="strong",
                target_id="card-2",
            )

            with self.assertRaisesRegex(RuntimeError, "stale"):
                search_with_receipt(repo_root, query="migration checkpoint")

    def test_fast_authority_avoids_full_replay_and_observation_only_events_do_not_stale_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            write_yaml_file(repo_root / "kb" / "public" / "card.yaml", card("card-1", "trusted"))
            built = publish_current_cards(repo_root, reason="test")
            commit_lifecycle_event(
                repo_root,
                {
                    "event_type": "observation-admitted",
                    "item_id": "observation-1",
                    "idempotency_key": "observation-1",
                    "source_event": {},
                    "source_fingerprint": "source-1",
                    "evidence": [],
                },
            )

            with (
                patch(
                    "local_kb.active_index._validate_indexed_sources_fast",
                    wraps=active_index_module._validate_indexed_sources_fast,
                ) as indexed_source_validator,
            ):
                with (
                    patch("local_kb.active_index.source_manifest", side_effect=AssertionError("full scan")),
                    patch("local_kb.active_index.load_lifecycle_state", side_effect=AssertionError("full replay")),
                ):
                    self.assertTrue(validate_active_index_fast(repo_root)["ok"])
                    entries, index = load_active_entries(repo_root)

                self.assertEqual([entry.data["id"] for entry in entries], ["card-1"])
                self.assertEqual(index["generation"], built["generation"])
                self.assertEqual(index["validation_mode"], "fast-authority")
                self.assertEqual(indexed_source_validator.call_count, 1)

                card_path = repo_root / "kb" / "public" / "card.yaml"
                original_projection = load_yaml_file(card_path)
                tampered_projection = dict(original_projection)
                tampered_projection["status"] = "rejected"
                write_yaml_file(card_path, tampered_projection)
                self.assertFalse(validate_active_index_fast(repo_root)["ok"])
                self.assertEqual(indexed_source_validator.call_count, 2)
                with self.assertRaisesRegex(RuntimeError, "stale"):
                    search_with_receipt(
                        repo_root,
                        query="migration checkpoint",
                        record_receipt=False,
                    )
                self.assertEqual(indexed_source_validator.call_count, 3)
                write_yaml_file(card_path, original_projection)
                changed = card("card-1", "rejected")
                publication = publish_sleep_model_generation(
                    repo_root,
                    reason="source-change",
                    card_upserts={"kb/public/card.yaml": changed},
                )
                self.assertTrue(publication["ok"], publication)
                post_publication_validation_count = indexed_source_validator.call_count
                self.assertGreater(post_publication_validation_count, 3)
                results, _receipt = search_with_receipt(
                    repo_root,
                    query="migration checkpoint",
                    record_receipt=False,
                )
                self.assertEqual(results, [])
                self.assertEqual(
                    indexed_source_validator.call_count,
                    post_publication_validation_count + 1,
                )

    def test_outcome_receipt_rejects_unreturned_card_and_requires_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            write_yaml_file(repo_root / "kb" / "public" / "card.yaml", card("card-1", "trusted"))
            publish_current_cards(repo_root, reason="test")
            _entries, retrieval = search_with_receipt(repo_root, query="migration checkpoint")

            with self.assertRaises(ValueError):
                record_outcome_receipt(
                    repo_root,
                    request_id=retrieval["request_id"],
                    used_entry_ids=["not-returned"],
                    outcome="success",
                    evidence_kind="test",
                    evidence_ref="test::1",
                    verified=True,
                )
            with self.assertRaises(ValueError):
                record_outcome_receipt(
                    repo_root,
                    request_id=retrieval["request_id"],
                    used_entry_ids=["card-1"],
                    outcome="success",
                    evidence_kind="test",
                    verified=True,
                )
            receipt = record_outcome_receipt(
                repo_root,
                request_id=retrieval["request_id"],
                used_entry_ids=["card-1"],
                outcome="success",
                evidence_kind="test",
                evidence_ref="pytest:test_case",
                verified=True,
            )
            self.assertEqual(receipt["evidence_grade"], "strong")

    def test_no_card_is_preserved_as_first_class_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            publish_current_cards(repo_root, reason="empty")
            entries, receipt = search_with_receipt(repo_root, query="uncovered quantum gardening task")
            self.assertEqual(entries, [])
            self.assertTrue(receipt["no_card"])
            self.assertTrue(receipt["abstention_reason"])


if __name__ == "__main__":
    unittest.main()
