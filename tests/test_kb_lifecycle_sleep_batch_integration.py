from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from local_kb.active_index import active_index_path
from local_kb.feedback import build_observation, record_observation
from local_kb.lifecycle import run_incremental_sleep
from local_kb.sleep_batch import load_current_sleep_batch
from tests.current_runtime_helpers import activate_current_kb_runtime


def _record_history_only_observation(repo_root: Path, name: str) -> None:
    record_observation(
        repo_root,
        build_observation(
            task_summary=name,
            outcome="success",
            suggested_action="none",
        ),
    )


def test_soft_stop_preserves_generation_and_resumes_only_pending_frozen_items() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        activate_current_kb_runtime(repo_root)
        _record_history_only_observation(repo_root, "frozen item one")
        _record_history_only_observation(repo_root, "frozen item two")
        pointer_before = json.loads(
            active_index_path(repo_root).read_text(encoding="utf-8")
        )
        with patch(
            "local_kb.lifecycle.time.monotonic",
            side_effect=[100.0, 100.0, 101.0],
        ), patch(
            "local_kb.model_maintenance.publish_sleep_model_generation",
            side_effect=AssertionError("an open frozen batch must not publish"),
        ):
            progress = run_incremental_sleep(
                repo_root,
                run_id="sleep-progress-one",
                soft_deadline_seconds=0.05,
            )

        assert progress["final_run_state"] == "progress_saved"
        assert progress["completed_this_attempt"] == 1
        assert progress["blocked_this_attempt"] == 0
        assert progress["batch_checkpoint"]["pending_count"] == 1
        assert progress["input_watermark"] == progress["output_watermark"] == 0
        assert all(
            item == {"status": "not_run", "reason": "sleep-progress-saved"}
            for item in progress["downstream_stages"].values()
        )
        assert json.loads(active_index_path(repo_root).read_text(encoding="utf-8")) == pointer_before

        frozen_batch = load_current_sleep_batch(repo_root)
        assert frozen_batch is not None
        first_result = next(iter(frozen_batch["results"].values()))
        assert first_result["details"]["lifecycle_events"]
        assert "model_upserts" in first_result["details"]
        assert "deferred_history_events" in first_result["details"]
        assert "handoff_acknowledgement" in first_result["details"]
        assert "counters" in first_result["details"]

        completed = run_incremental_sleep(repo_root, run_id="sleep-resume-one")

        assert completed["final_run_state"] == "completed"
        assert completed["batch_id"] == progress["batch_id"]
        assert completed["completed_this_attempt"] == 1
        assert completed["batch_checkpoint"]["completed_count"] == 2
        assert completed["batch_checkpoint"]["pending_count"] == 0
        assert completed["output_watermark"] == 2


def test_later_arrival_does_not_expand_an_open_frozen_batch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        activate_current_kb_runtime(repo_root)
        _record_history_only_observation(repo_root, "first frozen observation")
        _record_history_only_observation(repo_root, "second frozen observation")

        progress = run_incremental_sleep(
            repo_root,
            run_id="sleep-freeze-zero",
            soft_deadline_seconds=0,
        )
        assert progress["final_run_state"] == "progress_saved"
        assert progress["target_batch_size"] == 2
        frozen_ids = list(progress["batch_plan"]["selected_item_ids"])

        _record_history_only_observation(repo_root, "arrived after freeze")
        resumed = run_incremental_sleep(repo_root, run_id="sleep-frozen-resume")

        assert resumed["final_run_state"] == "completed"
        assert resumed["batch_plan"]["selected_item_ids"] == frozen_ids
        assert resumed["target_batch_size"] == 2
        assert resumed["completed_this_attempt"] == 2
        assert resumed["output_watermark"] == 2

        next_cycle = run_incremental_sleep(repo_root, run_id="sleep-next-frozen-batch")
        assert next_cycle["final_run_state"] == "completed"
        assert next_cycle["batch_id"] != resumed["batch_id"]
        assert next_cycle["target_batch_size"] == 1
        assert next_cycle["output_watermark"] == 3


def test_blocked_item_does_not_prevent_completed_siblings_from_publishing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        activate_current_kb_runtime(repo_root)
        _record_history_only_observation(repo_root, "publishable sibling")
        history_path = repo_root / "kb" / "history" / "events.jsonl"
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write("{malformed-history}\n")

        receipt = run_incremental_sleep(repo_root, run_id="sleep-with-blocked-item")

        assert receipt["final_run_state"] == "completed_with_blocks"
        assert receipt["batch_checkpoint"]["state"] == "settled_with_blocks"
        assert receipt["completed_this_attempt"] == 1
        assert receipt["blocked_this_attempt"] == 1
        assert receipt["model_generation"]["ok"] is True
        assert receipt["output_watermark"] == 1
        assert receipt["blocked_items"] == [
            {
                "item_id": "history-error:1",
                "owner": "kb-history-maintainer",
                "reopen_condition": "Repair malformed history line 2 and reopen it.",
            }
        ]
        assert all(
            item == {
                "status": "not_run",
                "reason": "sleep-completed-with-blocks",
            }
            for item in receipt["downstream_stages"].values()
        )
