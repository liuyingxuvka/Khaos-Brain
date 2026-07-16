from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.candidate_lifecycle import review_entry_lifecycles
from local_kb.feedback import build_observation, record_observation
from local_kb.lifecycle import (
    content_fingerprint,
    lifecycle_events_path,
    load_lifecycle_state,
    pending_dream_handoffs,
    record_dream_handoff,
    record_outcome_receipt,
    rollback_uncommitted_dream_handoff_acknowledgements,
    run_incremental_sleep,
    sleep_state_path,
    transition_entry,
)
from local_kb.maintenance_lanes import acquire_lane_lock, release_lane_lock
from local_kb.model_maintenance import publish_sleep_model_generation
from local_kb.search import search_with_receipt
from local_kb.store import history_events_path, write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


def activate_standard(repo_root: Path) -> None:
    activate_current_kb_runtime(repo_root)


class KbSleepConvergenceTests(unittest.TestCase):
    def test_sleep_holds_and_releases_shared_lane_for_exact_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            observation = build_observation(task_summary="Lock-bound Sleep observation")
            record_observation(repo_root, observation)

            receipt = run_incremental_sleep(repo_root, run_id="sleep-lock-bound")

            self.assertEqual(receipt["final_run_state"], "completed", receipt)
            self.assertEqual(receipt["lane_lock"]["group"], "local-maintenance")
            self.assertEqual(receipt["lane_lock"]["lane"], "kb-sleep")
            self.assertEqual(receipt["lane_lock"]["run_id"], "sleep-lock-bound")
            self.assertTrue(receipt["lane_lock"]["acquired"])
            self.assertTrue(receipt["lock_release"]["ok"])
            self.assertTrue(receipt["lock_release"]["released"])
            self.assertEqual(receipt["lock_release"]["run_id"], "sleep-lock-bound")
            self.assertEqual(receipt["lock_release"]["lock"]["run_id"], "sleep-lock-bound")

    def test_sleep_lane_contention_is_retryable_and_does_not_advance_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            held = acquire_lane_lock(
                repo_root,
                "kb-dream",
                run_id="dream-holds-local-maintenance",
                wait=False,
            )
            self.assertTrue(held["acquired"])
            try:
                receipt = run_incremental_sleep(
                    repo_root,
                    run_id="sleep-contended",
                )
            finally:
                release_lane_lock(
                    repo_root,
                    "kb-dream",
                    run_id="dream-holds-local-maintenance",
                )

            self.assertEqual(receipt["final_run_state"], "retryable", receipt)
            self.assertTrue(receipt["retryable"])
            self.assertEqual(receipt["reason"], "maintenance-lane-active")
            self.assertFalse(receipt["lane_lock"]["acquired"])
            self.assertEqual(receipt["input_watermark"], receipt["output_watermark"])
            self.assertFalse(sleep_state_path(repo_root).exists())

    def test_failed_sleep_does_not_advance_committed_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            observation = build_observation(task_summary="Committed before malformed input")
            record_observation(repo_root, observation)
            first = run_incremental_sleep(repo_root, run_id="sleep-before-failure")
            committed_before = json.loads(
                sleep_state_path(repo_root).read_text(encoding="utf-8")
            )["committed_watermark"]
            with history_events_path(repo_root).open("a", encoding="utf-8") as handle:
                handle.write("{malformed-json\n")

            failed = run_incremental_sleep(repo_root, run_id="sleep-malformed")
            committed_after = json.loads(
                sleep_state_path(repo_root).read_text(encoding="utf-8")
            )["committed_watermark"]

            self.assertEqual(first["output_watermark"], committed_before)
            self.assertEqual(failed["final_run_state"], "blocked", failed)
            self.assertEqual(failed["output_watermark"], committed_before)
            self.assertEqual(committed_after, committed_before)
            self.assertTrue(failed["lock_release"]["released"])

    def test_candidate_promotes_only_with_independent_support_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            entry_id = "candidate-promotion"
            candidate_payload = {
                    "id": entry_id,
                    "title": "Migration checkpoint candidate promotion",
                    "type": "model",
                    "scope": "public",
                    "domain_path": ["engineering", "migration", "checkpoint"],
                    "tags": ["migration", "checkpoint"],
                    "trigger_keywords": ["migration", "checkpoint"],
                    "if": {"notes": "A migration resumes from a durable checkpoint."},
                    "action": {"description": "Validate the checkpoint fingerprint before resuming."},
                    "predict": {"expected_result": "No migration side effect is duplicated."},
                    "use": {"guidance": "Use only for versioned resumable migrations."},
                    "source": [{"origin": "episode", "id": "episode-1"}],
                    "confidence": 0.5,
                    "status": "candidate",
                    "retrieval_eligible": True,
                }
            transition_entry(
                repo_root,
                entry_id=entry_id,
                from_state="candidate",
                to_state="candidate",
                reason="Candidate admitted for bounded validation.",
                actor="sleep",
                evidence_ids=["episode-1"],
                provenance_ids=["episode-1"],
                evidence_grade="medium",
                retrieval_eligible=True,
                decision_deadline="2099-01-01T00:00:00+00:00",
            )
            publication = publish_sleep_model_generation(
                repo_root,
                reason="test:candidate-promotion",
                card_upserts={f"kb/candidates/{entry_id}.yaml": candidate_payload},
            )
            self.assertTrue(publication["ok"], publication)
            _entries, retrieval = search_with_receipt(
                repo_root,
                query="migration checkpoint fingerprint",
            )
            record_outcome_receipt(
                repo_root,
                request_id=retrieval["request_id"],
                used_entry_ids=[entry_id],
                outcome="success",
                evidence_kind="test",
                evidence_ref="pytest:independent-support",
                verified=True,
            )
            before_validation = review_entry_lifecycles(repo_root, run_id="sleep-review-before-validation")
            self.assertEqual(before_validation["promoted"], 0)

            record_outcome_receipt(
                repo_root,
                request_id=retrieval["request_id"],
                used_entry_ids=[entry_id],
                outcome="success",
                evidence_kind="validation",
                evidence_ref="validator:semantic-current",
                verified=True,
            )
            after_validation = review_entry_lifecycles(repo_root, run_id="sleep-review-after-validation")

            self.assertEqual(after_validation["promoted"], 1)
            self.assertEqual(
                load_lifecycle_state(repo_root)["entries"][entry_id]["status"],
                "trusted",
            )

    def test_second_sleep_is_bounded_noop_without_duplicate_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            observation = build_observation(task_summary="One-off non-reusable observation")
            record_observation(repo_root, observation)
            first = run_incremental_sleep(repo_root, run_id="sleep-first")
            event_count = len(lifecycle_events_path(repo_root).read_text(encoding="utf-8").splitlines())

            second = run_incremental_sleep(repo_root, run_id="sleep-second")
            second_event_count = len(lifecycle_events_path(repo_root).read_text(encoding="utf-8").splitlines())

            self.assertEqual(first["output_watermark"], second["output_watermark"])
            self.assertEqual(event_count, second_event_count)
            self.assertEqual(second["newly_admitted"], 0)
            self.assertEqual(second["closing_actionable_backlog"], 0)

    def test_dream_handoff_is_acknowledged_once_by_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            handoff = record_dream_handoff(
                repo_root,
                run_id="dream-1",
                evidence_fingerprint=content_fingerprint(["route", "evidence"]),
                result_digest=content_fingerprint(["passed"]),
                route_ref="engineering/migration/checkpoint",
                hypothesis="A candidate may be useful.",
                classification="adjacent-support",
                result_summary="Adjacent evidence supports bounded review.",
                requested_disposition="candidate",
            )
            self.assertTrue(handoff["created"])
            first = run_incremental_sleep(repo_root, run_id="sleep-handoff")
            second = run_incremental_sleep(repo_root, run_id="sleep-handoff-repeat")

            self.assertEqual(len(first["handoff_acknowledgements"]), 1)
            self.assertEqual(second["handoff_acknowledgements"], [])
            self.assertEqual(pending_dream_handoffs(repo_root), [])

    def test_pending_dream_handoffs_share_one_atomic_lifecycle_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            for index in range(4):
                record_dream_handoff(
                    repo_root,
                    run_id="dream-batch",
                    evidence_fingerprint=content_fingerprint(["route", index]),
                    result_digest=content_fingerprint(["history-only", index]),
                    route_ref=f"engineering/migration/batch-{index}",
                    hypothesis=f"Dream handoff {index} remains historical evidence.",
                    classification="history-only",
                    result_summary="The result does not justify a reusable candidate.",
                    requested_disposition="history_only",
                )

            receipt = run_incremental_sleep(repo_root, run_id="sleep-handoff-batch")

            self.assertEqual(receipt["final_run_state"], "completed", receipt)
            self.assertEqual(receipt["processed_observations"], 4)
            self.assertEqual(receipt["lifecycle_batch"]["requested_count"], 8)
            self.assertEqual(receipt["lifecycle_batch"]["replay_pass_count"], 2)
            self.assertEqual(receipt["lifecycle_batch"]["atomic_batch_count"], 1)
            self.assertEqual(len(receipt["handoff_acknowledgements"]), 4)
            self.assertEqual(pending_dream_handoffs(repo_root), [])

    def test_dream_handoff_is_not_acknowledged_when_model_publication_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            handoff = record_dream_handoff(
                repo_root,
                run_id="dream-publication-failure",
                evidence_fingerprint=content_fingerprint(["route", "failed-publication"]),
                result_digest=content_fingerprint(["passed-experiment"]),
                route_ref="engineering/migration/publication-failure",
                hypothesis="A useful Dream result still requires committed model publication.",
                classification="passed",
                result_summary="The experiment passed, but publication is forced to fail.",
                requested_disposition="candidate",
            )
            with patch(
                "local_kb.model_maintenance.publish_sleep_model_generation",
                return_value={
                    "ok": False,
                    "status": "rolled_back",
                    "error": "forced model publication failure",
                },
            ):
                receipt = run_incremental_sleep(
                    repo_root,
                    run_id="sleep-publication-failure",
                )

            self.assertEqual(receipt["final_run_state"], "blocked")
            self.assertEqual(receipt["handoff_acknowledgements"], [])
            self.assertEqual(
                [item["handoff_id"] for item in pending_dream_handoffs(repo_root)],
                [handoff["handoff_id"]],
            )

    def test_dead_sleep_owner_reopens_acks_without_a_completed_receipt(self) -> None:
        from local_kb.lifecycle import acknowledge_dream_handoff

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            handoff = record_dream_handoff(
                repo_root,
                run_id="dream-interrupted-owner",
                evidence_fingerprint=content_fingerprint(["route", "interrupted-owner"]),
                result_digest=content_fingerprint(["passed"]),
                route_ref="engineering/migration/interrupted-owner",
                hypothesis="An interrupted owner must not consume its handoff.",
                classification="passed",
                result_summary="The owner terminated before model publication completed.",
                requested_disposition="candidate",
            )
            acknowledge_dream_handoff(
                repo_root,
                handoff_id=handoff["handoff_id"],
                disposition_id="disposition-before-publication",
                run_id="interrupted-sleep",
            )

            recovery = rollback_uncommitted_dream_handoff_acknowledgements(
                repo_root,
                run_id="interrupted-sleep",
            )

            self.assertEqual(recovery["removed_count"], 1)
            self.assertEqual(
                [item["handoff_id"] for item in pending_dream_handoffs(repo_root)],
                [handoff["handoff_id"]],
            )


if __name__ == "__main__":
    unittest.main()
