from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from local_kb.sleep_batch import (
    SLEEP_BATCH_CHECKPOINT_SCHEMA,
    SLEEP_BATCH_HEAD_SCHEMA,
    SLEEP_BATCH_ITEM_RESULT_SCHEMA,
    SLEEP_BATCH_PLAN_SCHEMA,
    SleepBatchError,
    calculate_sleep_batch_target,
    load_current_sleep_batch,
    record_sleep_batch_item_result,
    sleep_batch_checkpoint_path,
    sleep_batch_head_path,
    sleep_batch_plan_path,
    sleep_batch_result_dir,
    start_or_resume_sleep_batch,
)


class SleepBatchTests(unittest.TestCase):
    def test_target_is_twice_new_items_clamped_to_tested_bounds(self) -> None:
        self.assertEqual(calculate_sleep_batch_target(100, 10), 25)
        self.assertEqual(calculate_sleep_batch_target(100, 30), 60)
        self.assertEqual(calculate_sleep_batch_target(1000, 200), 250)
        self.assertEqual(calculate_sleep_batch_target(10, 200), 10)
        self.assertEqual(calculate_sleep_batch_target(100, 0), 25)
        self.assertEqual(calculate_sleep_batch_target(0, 0), 0)

    def test_plan_freezes_boundary_and_unsettled_batch_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            opened = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-freeze",
                eligible_item_ids=["a", "b", "c", "d", "e", "f", "g"],
                newly_eligible_item_ids=["a", "b"],
                prior_remaining_count=5,
                input_watermark={"history_line": 44},
                current_generation_id="generation-1",
                min_items=2,
                max_items=5,
                now="2026-07-22T10:00:00+00:00",
            )

            self.assertFalse(opened["resumed"])
            self.assertEqual(opened["head"]["schema_version"], SLEEP_BATCH_HEAD_SCHEMA)
            self.assertEqual(opened["plan"]["schema_version"], SLEEP_BATCH_PLAN_SCHEMA)
            self.assertEqual(
                opened["checkpoint"]["schema_version"],
                SLEEP_BATCH_CHECKPOINT_SCHEMA,
            )
            self.assertEqual(opened["plan"]["target_item_count"], 4)
            self.assertEqual(opened["plan"]["current_generation_id"], "generation-1")
            self.assertTrue(opened["plan"]["input_digest"])
            self.assertEqual(opened["plan"]["selected_item_ids"], ["a", "b", "c", "d"])
            self.assertEqual(opened["plan"]["deferred_item_ids"], ["e", "f", "g"])
            self.assertEqual(opened["checkpoint"]["closing_remaining_count"], 7)

            record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-freeze",
                item_id="a",
                status="completed",
                details={"receipt": "done-a"},
                recorded_at="2026-07-22T10:01:00+00:00",
            )
            resumed = start_or_resume_sleep_batch(
                repo_root,
                eligible_item_ids=["new-1", "new-2", "new-3", "new-4"],
                newly_eligible_item_ids=["new-1", "new-2", "new-3", "new-4"],
                min_items=2,
                max_items=5,
            )

            self.assertTrue(resumed["resumed"])
            self.assertEqual(resumed["plan"]["batch_id"], "sleep-freeze")
            self.assertEqual(resumed["plan"]["selected_item_ids"], ["a", "b", "c", "d"])
            self.assertNotIn("new-1", resumed["plan"]["eligible_item_ids"])
            self.assertEqual(resumed["checkpoint"]["completed_item_ids"], ["a"])
            self.assertEqual(resumed["checkpoint"]["pending_item_ids"], ["b", "c", "d"])

    def test_results_are_immutable_and_blocked_items_need_reopen_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            opened = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-results",
                eligible_item_ids=["a", "b", "c"],
                newly_eligible_item_ids=["a"],
                prior_remaining_count=2,
                min_items=2,
                max_items=2,
                now="2026-07-22T11:00:00+00:00",
            )
            self.assertEqual(opened["plan"]["selected_item_ids"], ["a", "b"])

            completed = record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-results",
                item_id="a",
                status="completed",
                details={"output": "staged-a"},
                recorded_at="2026-07-22T11:01:00+00:00",
            )
            revision = completed["checkpoint"]["revision"]
            replay = record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-results",
                item_id="a",
                status="completed",
                details={"output": "staged-a"},
                recorded_at="2099-01-01T00:00:00+00:00",
            )
            self.assertEqual(replay["checkpoint"]["revision"], revision)
            self.assertEqual(
                replay["item_result"]["recorded_at"],
                "2026-07-22T11:01:00+00:00",
            )

            with self.assertRaises(ValueError):
                record_sleep_batch_item_result(
                    repo_root,
                    batch_id="sleep-results",
                    item_id="b",
                    status="blocked",
                    owner="",
                    reopen_condition="",
                )
            blocked = record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-results",
                item_id="b",
                status="blocked",
                owner="sleep-model-owner",
                reopen_condition="Reopen after the missing source is admitted.",
                details={"reason": "missing-source"},
                recorded_at="2026-07-22T11:02:00+00:00",
            )

            self.assertEqual(
                blocked["item_result"]["schema_version"],
                SLEEP_BATCH_ITEM_RESULT_SCHEMA,
            )
            self.assertTrue(blocked["checkpoint"]["settled"])
            self.assertEqual(blocked["checkpoint"]["state"], "settled_with_blocks")
            self.assertEqual(blocked["checkpoint"]["completed_count"], 1)
            self.assertEqual(blocked["checkpoint"]["blocked_count"], 1)
            self.assertEqual(blocked["checkpoint"]["pending_count"], 0)
            self.assertEqual(blocked["checkpoint"]["closing_remaining_count"], 1)
            self.assertEqual(blocked["checkpoint"]["net_reduction"], 2)

            with self.assertRaises(SleepBatchError):
                record_sleep_batch_item_result(
                    repo_root,
                    batch_id="sleep-results",
                    item_id="a",
                    status="blocked",
                    owner="different-owner",
                    reopen_condition="Try a different result.",
                )

    def test_next_cycle_compares_closing_remainder_and_reports_growth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-cycle-1",
                eligible_item_ids=["old-a"],
                newly_eligible_item_ids=[],
                prior_remaining_count=2,
                min_items=1,
                max_items=2,
                now="2026-07-22T12:00:00+00:00",
            )
            first = record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-cycle-1",
                item_id="old-a",
                status="completed",
                recorded_at="2026-07-22T12:01:00+00:00",
            )
            self.assertEqual(first["checkpoint"]["closing_remaining_count"], 0)
            self.assertEqual(first["checkpoint"]["remainder_trend"], "shrinking")

            second = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-cycle-2",
                eligible_item_ids=["new-a", "new-b", "new-c"],
                newly_eligible_item_ids=["new-a", "new-b", "new-c"],
                min_items=1,
                max_items=2,
                now="2026-07-22T13:00:00+00:00",
            )
            self.assertEqual(second["plan"]["prior_remaining_count"], 0)
            self.assertEqual(second["plan"]["target_item_count"], 2)
            self.assertEqual(second["checkpoint"]["closing_remaining_count"], 3)
            self.assertFalse(second["checkpoint"]["backlog_growing"])
            self.assertEqual(second["checkpoint"]["remainder_trend"], "growing")

            for item_id in second["plan"]["selected_item_ids"]:
                second = record_sleep_batch_item_result(
                    repo_root,
                    batch_id="sleep-cycle-2",
                    item_id=item_id,
                    status="completed",
                )
            self.assertTrue(second["checkpoint"]["settled"])
            self.assertEqual(second["checkpoint"]["closing_remaining_count"], 1)
            self.assertFalse(second["checkpoint"]["backlog_growing"])
            self.assertEqual(second["checkpoint"]["remainder_delta_from_prior"], 1)

            third = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-cycle-3",
                eligible_item_ids=["later-a", "later-b"],
                newly_eligible_item_ids=["later-a", "later-b"],
                min_items=1,
                max_items=1,
                now="2026-07-22T14:00:00+00:00",
            )
            self.assertEqual(third["plan"]["prior_no_reduction_streak"], 1)
            self.assertTrue(third["checkpoint"]["backlog_growing"])

    def test_no_new_arrivals_still_processes_the_minimum_bounded_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            opened = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-existing-backlog",
                eligible_item_ids=[f"item-{index}" for index in range(8)],
                newly_eligible_item_ids=[],
                prior_remaining_count=8,
                min_items=3,
                max_items=5,
            )
            self.assertEqual(opened["plan"]["target_item_count"], 3)
            self.assertEqual(len(opened["plan"]["selected_item_ids"]), 3)

    def test_resume_recovers_result_written_before_checkpoint_and_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            opened = start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-crash-window",
                eligible_item_ids=["a", "b"],
                newly_eligible_item_ids=["a"],
                prior_remaining_count=1,
                min_items=2,
                max_items=2,
                now="2026-07-22T14:00:00+00:00",
            )
            stale_head = json.loads(
                sleep_batch_head_path(repo_root).read_text(encoding="utf-8")
            )
            stale_checkpoint = json.loads(
                sleep_batch_checkpoint_path(repo_root, "sleep-crash-window").read_text(
                    encoding="utf-8"
                )
            )
            record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-crash-window",
                item_id="a",
                status="completed",
                details={"durable": True},
            )
            sleep_batch_checkpoint_path(repo_root, "sleep-crash-window").write_text(
                json.dumps(stale_checkpoint),
                encoding="utf-8",
            )
            sleep_batch_head_path(repo_root).write_text(
                json.dumps(stale_head),
                encoding="utf-8",
            )

            recovered = load_current_sleep_batch(repo_root)

            self.assertIsNotNone(recovered)
            assert recovered is not None
            self.assertEqual(recovered["checkpoint"]["completed_item_ids"], ["a"])
            self.assertEqual(recovered["checkpoint"]["pending_item_ids"], ["b"])
            self.assertGreater(recovered["head"]["generation"], stale_head["generation"])
            self.assertEqual(
                recovered["head"]["checkpoint_revision"],
                recovered["checkpoint"]["revision"],
            )

    def test_plan_digest_detects_boundary_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-tamper",
                eligible_item_ids=["a"],
                newly_eligible_item_ids=["a"],
                prior_remaining_count=0,
                min_items=1,
                max_items=1,
            )
            plan_path = sleep_batch_plan_path(repo_root, "sleep-tamper")
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            plan["selected_item_ids"] = ["different-item"]
            plan_path.write_text(json.dumps(plan), encoding="utf-8")

            with self.assertRaises(SleepBatchError):
                load_current_sleep_batch(repo_root)

    def test_item_result_filename_is_content_addressed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            start_or_resume_sleep_batch(
                repo_root,
                batch_id="sleep-result-path",
                eligible_item_ids=["route/with:unsafe\\characters"],
                newly_eligible_item_ids=[],
                prior_remaining_count=1,
                min_items=1,
                max_items=1,
            )
            record_sleep_batch_item_result(
                repo_root,
                batch_id="sleep-result-path",
                item_id="route/with:unsafe\\characters",
                status="completed",
            )
            expected_name = (
                hashlib.sha256("route/with:unsafe\\characters".encode("utf-8")).hexdigest()
                + ".json"
            )
            result_paths = list(sleep_batch_result_dir(repo_root, "sleep-result-path").glob("*.json"))
            self.assertEqual([path.name for path in result_paths], [expected_name])


if __name__ == "__main__":
    unittest.main()
