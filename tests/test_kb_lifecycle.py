from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_kb.feedback import build_observation, record_observation
from local_kb.history import record_history_event
from local_kb.lifecycle import (
    admit_observation,
    build_observation_admission_event,
    build_observation_disposition_event,
    commit_lifecycle_events,
    _lifecycle_lock,
    evidence_items_for_observation,
    lifecycle_events_path,
    load_lifecycle_state,
    replay_lifecycle,
    run_incremental_sleep,
    transition_entry,
    validate_lifecycle,
)
from tests.current_runtime_helpers import activate_current_kb_runtime


def activate_standard(repo_root: Path) -> None:
    activate_current_kb_runtime(repo_root)


class KbLifecycleTests(unittest.TestCase):
    def test_lifecycle_writer_lock_recovers_interrupted_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            lock_dir = repo_root / "kb" / "history" / "lifecycle" / ".writer.lock"
            lock_dir.mkdir(parents=True)

            with _lifecycle_lock(
                repo_root,
                timeout_seconds=0.2,
                orphan_grace_seconds=0.0,
            ):
                owner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
                self.assertEqual(owner["pid"], os.getpid())
                self.assertEqual(owner["thread_id"], threading.get_ident())

            self.assertFalse(lock_dir.exists())

    def test_lifecycle_writer_lock_recovers_dead_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            lock_dir = repo_root / "kb" / "history" / "lifecycle" / ".writer.lock"
            lock_dir.mkdir(parents=True)
            (lock_dir / "owner.json").write_text(
                json.dumps(
                    {
                        "schema_version": "khaos-brain.lifecycle-writer-lock.v1",
                        "token": "dead-owner-token",
                        "pid": 2147483647,
                        "thread_id": 1,
                    }
                ),
                encoding="utf-8",
            )

            with _lifecycle_lock(repo_root, timeout_seconds=0.2):
                owner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
                self.assertEqual(owner["pid"], os.getpid())

            self.assertFalse(lock_dir.exists())

    def test_lifecycle_writer_lock_is_reentrant_only_for_the_active_owner_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            lock_dir = repo_root / "kb" / "history" / "lifecycle" / ".writer.lock"
            with _lifecycle_lock(repo_root, timeout_seconds=0.2):
                outer = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
                with _lifecycle_lock(repo_root, timeout_seconds=0.2):
                    inner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
                    self.assertEqual(inner["token"], outer["token"])
                self.assertTrue(lock_dir.exists())

            self.assertFalse(lock_dir.exists())

    def test_lifecycle_writer_lock_does_not_steal_a_live_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            lock_dir = repo_root / "kb" / "history" / "lifecycle" / ".writer.lock"
            lock_dir.mkdir(parents=True)
            owner_path = lock_dir / "owner.json"
            owner_path.write_text(
                json.dumps(
                    {
                        "schema_version": "khaos-brain.lifecycle-writer-lock.v1",
                        "token": "live-owner-token",
                        "pid": os.getpid(),
                        "thread_id": threading.get_ident() + 1,
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(TimeoutError, "live-owner-token"):
                with _lifecycle_lock(repo_root, timeout_seconds=0.1):
                    self.fail("a live owner must not be displaced")

            self.assertTrue(owner_path.exists())

    def test_lifecycle_writer_lock_release_failure_is_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            lock_dir = repo_root / "kb" / "history" / "lifecycle" / ".writer.lock"
            original_rmdir = Path.rmdir

            def fail_lock_release(path: Path) -> None:
                if path == lock_dir:
                    raise PermissionError("simulated Windows lock-directory contention")
                original_rmdir(path)

            with patch.object(Path, "rmdir", fail_lock_release):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "release failed without being hidden",
                ):
                    with _lifecycle_lock(
                        repo_root,
                        timeout_seconds=0.2,
                        release_timeout_seconds=0.1,
                    ):
                        self.assertTrue(lock_dir.exists())

            owner = json.loads((lock_dir / "owner.json").read_text(encoding="utf-8"))
            self.assertEqual(owner["pid"], os.getpid())

    def test_observation_is_admitted_and_disposed_by_next_sleep(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            observation = build_observation(
                task_summary="A recurring migration failed after a stale cache was reused.",
                route_hint="engineering/migration/cache",
                scenario="When a versioned migration resumes after interruption.",
                action_taken="Verify the checkpoint fingerprint before reuse.",
                observed_result="The migration resumed without duplicating side effects.",
                suggested_action="new-candidate",
                outcome="success",
            )
            record_observation(repo_root, observation)
            admitted = load_lifecycle_state(repo_root)["observations"][observation["event_id"]]
            self.assertEqual(admitted["state"], "new")

            receipt = run_incremental_sleep(repo_root, run_id="sleep-one")

            self.assertEqual(receipt["final_run_state"], "completed")
            self.assertEqual(receipt["output_watermark"], 1)
            current = load_lifecycle_state(repo_root)["observations"][observation["event_id"]]
            self.assertEqual(current["state"], "candidate")
            self.assertTrue(validate_lifecycle(repo_root)["ok"])

    def test_no_delta_sleep_reuses_one_model_publication_and_one_final_index_validation_owner(self) -> None:
        from local_kb import active_index, model_maintenance

        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            with patch(
                "local_kb.model_maintenance.publish_sleep_model_generation",
                wraps=model_maintenance.publish_sleep_model_generation,
            ) as publish, patch(
                "local_kb.model_maintenance.rebuild_active_index",
                wraps=model_maintenance.rebuild_active_index,
            ) as rebuild, patch(
                "local_kb.model_maintenance.validate_active_index",
                wraps=model_maintenance.validate_active_index,
            ) as model_validation, patch(
                "local_kb.active_index.validate_active_index",
                wraps=active_index.validate_active_index,
            ) as fallback_validation:
                receipt = run_incremental_sleep(
                    repo_root,
                    run_id="sleep-single-index-owner",
                )

            self.assertEqual(receipt["final_run_state"], "completed")
            self.assertEqual(receipt["model_generation"]["status"], "no_delta")
            self.assertEqual(receipt["post_review_index_refresh"]["status"], "reused_current")
            self.assertEqual(publish.call_count, 1)
            self.assertEqual(rebuild.call_count, 0)
            self.assertEqual(model_validation.call_count, 0)
            self.assertEqual(fallback_validation.call_count, 1)
            self.assertTrue(receipt["index_validation"]["ok"])

    def test_failed_history_parse_does_not_advance_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            history = repo_root / "kb" / "history" / "events.jsonl"
            history.parent.mkdir(parents=True, exist_ok=True)
            history.write_text("{not-json}\n", encoding="utf-8")

            receipt = run_incremental_sleep(repo_root, run_id="sleep-blocked")

            self.assertEqual(receipt["final_run_state"], "blocked")
            self.assertEqual(receipt["output_watermark"], 0)

    def test_sleep_recovers_zero_watermark_by_skipping_terminal_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            observation = build_observation(
                task_summary="An already settled observation remains before the watermark.",
                outcome="success",
            )
            record_observation(repo_root, observation)
            decision = {
                "disposition": "history_only",
                "reason": "The observation was already settled by an interrupted pass.",
                "target_id": "",
                "evidence_grade": "medium",
            }
            commit_lifecycle_events(
                repo_root,
                [
                    build_observation_disposition_event(
                        observation,
                        run_id="interrupted-sleep",
                        decision=decision,
                    )
                ],
            )

            with patch(
                "local_kb.lifecycle.admit_observation",
                side_effect=AssertionError("terminal history must not be readmitted"),
            ), patch(
                "local_kb.lifecycle.dispose_observation",
                side_effect=AssertionError("terminal history must not be redisposed"),
            ):
                receipt = run_incremental_sleep(
                    repo_root,
                    run_id="sleep-watermark-recovery",
                )

            self.assertEqual(receipt["final_run_state"], "completed")
            self.assertEqual(receipt["input_watermark"], 0)
            self.assertEqual(receipt["output_watermark"], 1)
            self.assertEqual(receipt["already_terminal_skipped"], 1)
            self.assertEqual(receipt["lifecycle_batch"]["requested_count"], 0)

    def test_sleep_batches_new_history_admission_and_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            for index in range(3):
                observation = build_observation(
                    task_summary=f"Unseen history observation {index}",
                    outcome="success",
                )
                record_history_event(repo_root, observation)

            with patch(
                "local_kb.lifecycle.commit_lifecycle_events",
                wraps=commit_lifecycle_events,
            ) as batch_commit, patch(
                "local_kb.lifecycle.admit_observation",
                side_effect=AssertionError("history should use the batch writer"),
            ), patch(
                "local_kb.lifecycle.dispose_observation",
                side_effect=AssertionError("history should use the batch writer"),
            ):
                receipt = run_incremental_sleep(
                    repo_root,
                    run_id="sleep-batch-history",
                )

            batch_commit.assert_called_once()
            self.assertEqual(receipt["final_run_state"], "completed")
            self.assertEqual(receipt["output_watermark"], 3)
            self.assertEqual(receipt["newly_admitted"], 3)
            self.assertEqual(receipt["processed_observations"], 3)
            self.assertEqual(receipt["lifecycle_batch"]["requested_count"], 6)
            self.assertEqual(receipt["lifecycle_batch"]["replay_pass_count"], 2)

    def test_candidate_review_reuses_one_calibration_evidence_index(self) -> None:
        from local_kb.candidate_lifecycle import review_entry_lifecycles

        entries = [
            SimpleNamespace(
                data={
                    "id": entry_id,
                    "status": "candidate",
                    "confidence": 0.5,
                }
            )
            for entry_id in ("candidate-1", "candidate-2", "candidate-3")
        ]
        lifecycle = {
            "entries": {
                entry.data["id"]: {
                    "status": "candidate",
                    "decision_deadline": "2999-01-01T00:00:00+00:00",
                }
                for entry in entries
            },
            "validation": {"ok": True, "issues": []},
        }
        evidence_index = {
            "sentinel": "one-shared-index",
            "outcomes_by_entry": {},
            "observations_by_entry": {},
        }
        calibration = {
            "downgrade_required": False,
            "promotion_ready": False,
            "support_by_grade": {"strong": 0, "medium": 0, "weak": 0},
        }
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "local_kb.model_maintenance.load_current_model_entries",
            return_value=(entries, {"generation_id": "fixture-current"}),
        ), patch(
            "local_kb.candidate_lifecycle.load_lifecycle_state",
            side_effect=(lifecycle, lifecycle),
        ), patch(
            "local_kb.calibration.build_calibration_evidence_index",
            return_value=evidence_index,
        ) as build_index, patch(
            "local_kb.calibration.calibrate_entry",
            return_value=calibration,
        ) as calibrate:
            report = review_entry_lifecycles(
                Path(tmp_dir),
                run_id="shared-calibration-index",
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["reviewed"], 3)
        build_index.assert_called_once()
        self.assertEqual(calibrate.call_count, 3)
        self.assertTrue(
            all(
                call.kwargs["evidence_index"] is evidence_index
                for call in calibrate.call_args_list
            )
        )

    def test_candidate_review_reuses_the_generation_catalog_and_skips_unchanged_parked_entries(self) -> None:
        from local_kb.candidate_lifecycle import review_entry_lifecycles

        entries = [
            SimpleNamespace(
                data={"id": "parked-1", "status": "parked", "confidence": 0.5}
            )
        ]
        lifecycle = {
            "entries": {
                "parked-1": {
                    "status": "parked",
                    "evidence_fingerprint": "same-evidence",
                }
            },
            "validation": {"ok": True, "issues": []},
        }
        calibration = {
            "evidence_digest": "same-evidence",
            "downgrade_required": False,
            "promotion_ready": False,
            "support_by_grade": {"strong": 0, "medium": 0, "weak": 0},
        }
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "local_kb.model_maintenance.load_current_model_entries",
            side_effect=AssertionError("the validated generation catalog must be reused"),
        ), patch(
            "local_kb.candidate_lifecycle.load_lifecycle_state",
            side_effect=(lifecycle, lifecycle),
        ), patch(
            "local_kb.calibration.build_calibration_evidence_index",
            return_value={
                "sentinel": "one-shared-index",
                "outcomes_by_entry": {"parked-1": [{"id": "outcome-1"}]},
                "observations_by_entry": {},
            },
        ), patch(
            "local_kb.calibration.calibrate_entry",
            return_value=calibration,
        ) as calibrate:
            report = review_entry_lifecycles(
                Path(tmp_dir),
                run_id="parked-no-delta",
                catalog_entries=entries,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["reviewed"], 0)
        self.assertEqual(report["unchanged_parked_skipped"], 1)
        calibrate.assert_called_once()

    def test_parked_calibration_snapshot_persists_the_delta_watermark_once(self) -> None:
        from local_kb.candidate_lifecycle import review_entry_lifecycles

        entries = [
            SimpleNamespace(
                data={"id": "parked-watermark", "status": "parked", "confidence": 0.5}
            )
        ]
        evidence_index = {
            "outcomes_by_entry": {
                "parked-watermark": [{"id": "outcome-1"}],
            },
            "observations_by_entry": {},
        }
        calibration = {
            "evidence_digest": "current-evidence",
            "downgrade_required": False,
            "promotion_ready": False,
            "support_by_grade": {"strong": 0, "medium": 0, "weak": 1},
            "qualifying_evidence_ids": ["outcome-1"],
            "evidence_references": ["source-1"],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            activate_standard(repo_root)
            transition_entry(
                repo_root,
                entry_id="parked-watermark",
                from_state="candidate",
                to_state="parked",
                reason="fixture parked state",
                actor="fixture",
                evidence_fingerprint="old-evidence",
            )
            with patch(
                "local_kb.calibration.build_calibration_evidence_index",
                return_value=evidence_index,
            ), patch(
                "local_kb.calibration.calibrate_entry",
                return_value=calibration,
            ) as calibrate:
                first = review_entry_lifecycles(
                    repo_root,
                    run_id="calibration-watermark-first",
                    catalog_entries=entries,
                )
                second = review_entry_lifecycles(
                    repo_root,
                    run_id="calibration-watermark-second",
                    catalog_entries=entries,
                )

        self.assertTrue(first["ok"])
        self.assertEqual(first["reviewed"], 1)
        self.assertEqual(first["calibration_snapshot_count"], 1)
        self.assertEqual(first["decision_count"], 0)
        self.assertTrue(second["ok"])
        self.assertEqual(second["reviewed"], 0)
        self.assertEqual(second["calibration_snapshot_count"], 0)
        self.assertEqual(second["unchanged_parked_skipped"], 1)
        self.assertEqual(calibrate.call_count, 2)

    def test_active_index_lifecycle_digest_ignores_calibration_only_fields(self) -> None:
        from local_kb.active_index import lifecycle_entry_digest

        baseline = {
            "entries": {
                "entry-1": {
                    "status": "parked",
                    "retrieval_eligible": False,
                    "evidence_fingerprint": "old",
                    "decision_receipt": {"evidence_digest": "old"},
                }
            }
        }
        recalibrated = {
            "entries": {
                "entry-1": {
                    "status": "parked",
                    "retrieval_eligible": False,
                    "evidence_fingerprint": "new",
                    "decision_receipt": {"evidence_digest": "new"},
                }
            }
        }
        reopened = {
            "entries": {
                "entry-1": {
                    "status": "candidate",
                    "retrieval_eligible": False,
                    "evidence_fingerprint": "new",
                }
            }
        }

        self.assertEqual(
            lifecycle_entry_digest(baseline),
            lifecycle_entry_digest(recalibrated),
        )
        self.assertNotEqual(
            lifecycle_entry_digest(baseline),
            lifecycle_entry_digest(reopened),
        )

    def test_parked_entry_without_any_linked_evidence_is_skipped_without_calibration(self) -> None:
        from local_kb.candidate_lifecycle import review_entry_lifecycles

        entries = [
            SimpleNamespace(
                data={"id": "parked-no-evidence", "status": "parked", "confidence": 0.5}
            )
        ]
        lifecycle = {
            "entries": {"parked-no-evidence": {"status": "parked"}},
            "validation": {"ok": True, "issues": []},
        }
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "local_kb.candidate_lifecycle.load_lifecycle_state",
            side_effect=(lifecycle, lifecycle),
        ), patch(
            "local_kb.calibration.build_calibration_evidence_index",
            return_value={"outcomes_by_entry": {}, "observations_by_entry": {}},
        ), patch(
            "local_kb.calibration.calibrate_entry",
            side_effect=AssertionError("no linked evidence cannot satisfy a reopen condition"),
        ):
            report = review_entry_lifecycles(
                Path(tmp_dir),
                run_id="parked-no-linked-evidence",
                catalog_entries=entries,
            )

        self.assertTrue(report["ok"])
        self.assertEqual(report["reviewed"], 0)
        self.assertEqual(report["unchanged_parked_skipped"], 1)

    def test_calibration_consumes_a_supplied_evidence_index_without_reloading(self) -> None:
        from local_kb.calibration import calibrate_entry

        evidence_index = {
            "outcomes_by_entry": {},
            "observations_by_entry": {},
            "lifecycle_event_digest": "shared-ledger-digest",
        }
        with tempfile.TemporaryDirectory() as tmp_dir, patch(
            "local_kb.calibration.build_calibration_evidence_index",
            side_effect=AssertionError("a supplied index must not reload shared evidence"),
        ):
            result = calibrate_entry(
                Path(tmp_dir),
                "candidate-1",
                evidence_index=evidence_index,
            )

        self.assertTrue(result["shared_evidence_index"])
        self.assertEqual(
            result["shared_lifecycle_event_digest"],
            "shared-ledger-digest",
        )

    def test_evidence_grading_keeps_ai_self_report_weak(self) -> None:
        observation = build_observation(
            task_summary="AI says a retrieved card helped.",
            entry_ids="model-1",
            hit_quality="hit",
            outcome="",
            source_kind="agent",
        )
        self.assertEqual(evidence_items_for_observation(observation)[0]["grade"], "weak")

        correction = build_observation(
            task_summary="User corrected the prior action.",
            previous_action="Used stale output.",
            previous_result="The result was wrong.",
            revised_action="Re-ran current validation.",
            revised_result="The result was correct.",
            source_kind="user-correction",
        )
        self.assertEqual(evidence_items_for_observation(correction)[0]["grade"], "strong")

    def test_candidate_terminal_transition_is_replayable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            first = transition_entry(
                repo_root,
                entry_id="cand-1",
                from_state="candidate",
                to_state="parked",
                reason="Independent evidence is missing.",
                actor="sleep",
                evidence_ids=["obs-1"],
                provenance_ids=["obs-1"],
                evidence_grade="weak",
                reopen_condition={"kind": "new-independent-evidence"},
                evidence_fingerprint="fp-1",
            )
            second = transition_entry(
                repo_root,
                entry_id="cand-1",
                from_state="candidate",
                to_state="parked",
                reason="Independent evidence is missing.",
                actor="sleep",
                evidence_ids=["obs-1"],
                provenance_ids=["obs-1"],
                evidence_grade="weak",
                reopen_condition={"kind": "new-independent-evidence"},
                evidence_fingerprint="fp-1",
            )

            self.assertTrue(first["created"])
            self.assertTrue(second["idempotent_reuse"])
            state = load_lifecycle_state(repo_root)
            self.assertEqual(state["entries"]["cand-1"]["status"], "parked")
            self.assertEqual(state["event_count"], 1)

    def test_large_lifecycle_batch_uses_two_replays_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            events = []
            for index in range(250):
                observation = build_observation(
                    task_summary=f"Historical observation {index}",
                    outcome="success",
                )
                decision = {
                    "disposition": "history_only",
                    "reason": "Scale fixture remains history only.",
                    "target_id": "",
                    "evidence_grade": "medium",
                }
                events.extend(
                    [
                        build_observation_admission_event(observation),
                        build_observation_disposition_event(
                            observation,
                            run_id="batch-migration",
                            decision=decision,
                        ),
                    ]
                )

            with patch("local_kb.lifecycle.replay_lifecycle", wraps=replay_lifecycle) as replay:
                first = commit_lifecycle_events(repo_root, events)
            self.assertEqual(replay.call_count, 2)
            self.assertEqual(first["created_count"], 500)
            self.assertEqual(first["replay_pass_count"], 2)
            self.assertEqual(first["state"]["event_count"], 500)
            self.assertTrue(validate_lifecycle(repo_root)["ok"])

            with patch("local_kb.lifecycle.replay_lifecycle", wraps=replay_lifecycle) as replay:
                repeated = commit_lifecycle_events(repo_root, events)
            self.assertEqual(replay.call_count, 2)
            self.assertEqual(repeated["created_count"], 0)
            self.assertEqual(repeated["reused_count"], 500)
            self.assertEqual(repeated["state"]["event_count"], 500)

    def test_replay_lifecycle_uses_a_linear_idempotency_index(self) -> None:
        def replay_duration(event_count: int) -> float:
            with tempfile.TemporaryDirectory() as tmp_dir:
                repo_root = Path(tmp_dir)
                path = lifecycle_events_path(repo_root)
                path.parent.mkdir(parents=True)
                with path.open("w", encoding="utf-8") as handle:
                    for sequence in range(1, event_count + 1):
                        handle.write(
                            json.dumps(
                                {
                                    "sequence": sequence,
                                    "idempotency_key": f"key-{sequence}",
                                    "event_type": "noop",
                                    "item_id": f"item-{sequence}",
                                },
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                started = time.perf_counter()
                state = replay_lifecycle(repo_root)
                duration = time.perf_counter() - started
                self.assertTrue(state["validation"]["ok"])
                self.assertEqual(state["event_count"], event_count)
                return duration

        small_duration = replay_duration(10_000)
        large_duration = replay_duration(20_000)
        self.assertLess(
            large_duration,
            max(0.1, small_duration) * 3.2,
            "doubling the event log must remain near-linear, not quadratic",
        )

    def test_legacy_mode_does_not_create_lifecycle_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            observation = build_observation(task_summary="Legacy observation before migration.")
            record_observation(repo_root, observation)
            self.assertFalse(lifecycle_events_path(repo_root).exists())


if __name__ == "__main__":
    unittest.main()
