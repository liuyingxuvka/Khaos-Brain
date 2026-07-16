from __future__ import annotations

import tempfile
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import check_khaos_logicguard_runtime as runtime_readiness
from scripts.check_khaos_logicguard_runtime import build_report
from tests.test_khaos_model_native_retrieval import activate_model_native_fixture


class KhaosModelRuntimeReadinessTests(unittest.TestCase):
    def test_catalog_latency_is_measured_without_memory_instrumentation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)
            tracing_states: list[bool] = []
            original = runtime_readiness.load_current_model_entries

            def observed_load(current_root: Path):
                tracing_states.append(tracemalloc.is_tracing())
                return original(current_root)

            with patch.object(
                runtime_readiness,
                "load_current_model_entries",
                side_effect=observed_load,
            ):
                report = runtime_readiness.build_report(root)

            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(tracing_states, [False, True])

    def test_current_exact_generation_passes_runtime_and_performance_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            activate_model_native_fixture(root)

            report = build_report(root)

            self.assertTrue(report["ok"], report["issues"])
            self.assertEqual(
                report["generation_id"],
                "generation-model-native-retrieval",
            )
            self.assertEqual(report["entry_count"], 3)
            self.assertEqual(report["sample_count"], 3)
            self.assertTrue(report["authority"]["zero_legacy_projection_residuals"])
            self.assertLessEqual(
                report["performance"]["exact_context_p95_seconds"],
                report["performance"]["budgets"]["exact_context_p95_max_seconds"],
            )


if __name__ == "__main__":
    unittest.main()
