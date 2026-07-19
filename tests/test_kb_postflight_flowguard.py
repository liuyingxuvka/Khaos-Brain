from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest

from flowguard import run_exact_sequence

MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / ".flowguard"
    / "kb_postflight_terminal_flow.py"
)
SPEC = importlib.util.spec_from_file_location(
    "kb_postflight_terminal_flow",
    MODEL_PATH,
)
assert SPEC is not None and SPEC.loader is not None
flow = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = flow
SPEC.loader.exec_module(flow)


class KbPostflightFlowGuardTests(unittest.TestCase):
    def result_for(self, input_obj):
        report = run_exact_sequence(
            workflow=flow.WORKFLOW,
            initial_state=flow.PostflightState(),
            external_input_sequence=(input_obj,),
            invariants=flow.INVARIANTS,
        )
        self.assertTrue(report.model_report.ok, report.to_json_text())
        return report.traces[0].steps[0].function_output

    def test_bounded_primary_path_is_the_only_success(self) -> None:
        output = self.result_for(flow.PostflightInput("bounded_success"))
        self.assertEqual("success", output.status)
        self.assertEqual("kb-sleep", output.deferred_owner)

        for input_obj in (
            flow.PostflightInput(
                "duplicate_event",
                durable_history_event_count=2,
            ),
            flow.PostflightInput(
                "synchronous_lifecycle_replay",
                lifecycle_replay_count=2,
            ),
            flow.PostflightInput(
                "synchronous_admission",
                synchronous_admission_count=1,
            ),
            flow.PostflightInput(
                "authority_changed",
                runtime_authority_unchanged=False,
            ),
            flow.PostflightInput(
                "lock_not_released",
                writer_lock_release_confirmed=False,
            ),
            flow.PostflightInput(
                "duplicate_writer",
                single_writer_owner=False,
            ),
            flow.PostflightInput(
                "terminal_budget_cannot_contain_lock",
                terminal_budget_ms=120_000.0,
            ),
            flow.PostflightInput(
                "launcher_timeout_cannot_contain_terminal",
                launcher_timeout_ms=150_000.0,
            ),
            flow.PostflightInput(
                "budget_exceeded",
                duration_ms=150_001.0,
            ),
        ):
            with self.subTest(input_obj.kind):
                self.assertEqual("failed", self.result_for(input_obj).status)

    def test_persisted_event_without_receipt_is_timeout_unknown(self) -> None:
        output = self.result_for(
            flow.PostflightInput(
                "event_without_receipt",
                terminal_receipt_present=False,
                terminal_receipt_matches=False,
                interrupted=True,
            )
        )
        self.assertEqual("timeout_unknown", output.status)


if __name__ == "__main__":
    unittest.main()
