from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from local_kb.install import build_installation_check
from local_kb.maintenance_migration import check_migration_current_authority
from scripts import check_consumer_install_assurance as assurance


REPO_ROOT = Path(__file__).resolve().parents[1]


def _snapshot(**changes: str) -> dict[str, object]:
    components = {
        component_id: f"sha256:{component_id}"
        for component_ids in assurance.OWNER_COMPONENTS.values()
        for component_id in component_ids
    }
    components.update(
        {
            component_id: f"sha256:{component_id}"
            for component_id in assurance.AUTHORITY_ONLY_COMPONENTS
        }
    )
    components.update(changes)
    return {
        "schema_version": "khaos-brain.consumer-assurance-components.v1",
        "components": components,
        "digest": assurance._canonical_hash(components),
    }


def _successful_owner(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {
        "ok": True,
        "exit_code": 0,
        "payload": {"ok": True},
        "stdout_tail": "",
        "stderr_tail": "",
        "timed_out": False,
        "cleanup_confirmed": True,
        "cleanup_receipt": {},
    }


class ConsumerInstallAssuranceTests(unittest.TestCase):
    def test_toolchain_component_identity_is_content_bound_not_path_bound(self) -> None:
        manifest = {
            "digest": "same-content",
            "file_count": 7,
        }
        first = SimpleNamespace(
            submodule_search_locations=["C:/frozen/toolchain/flowguard"],
            origin=None,
        )
        second = SimpleNamespace(
            submodule_search_locations=["C:/live/site-packages/flowguard"],
            origin=None,
        )
        with patch.object(
            assurance.importlib.util,
            "find_spec",
            side_effect=(first, second),
        ), patch.object(
            assurance,
            "tree_manifest",
            return_value=manifest,
        ):
            frozen = assurance._package_component("flowguard")
            live = assurance._package_component("flowguard")

        self.assertEqual(frozen, live)
        self.assertNotIn("root", frozen)

    def test_owner_receipt_keeps_bounded_summary_and_raw_output_identity(self) -> None:
        payload = {
            "schema_version": "example.v1",
            "ok": True,
            "status": "passed",
            "claim_boundary": "bounded evidence",
            "model_traces": [{"value": "x" * 1000}] * 1000,
        }
        receipt = assurance._receipt_from_execution(
            "flow_model",
            "sha256:identity",
            ["python", "check.py"],
            {"flow_model_source": "sha256:source"},
            {
                "ok": True,
                "exit_code": 0,
                "payload": payload,
                "stdout_sha256": "sha256:raw",
                "stdout_byte_count": 1000000,
                "stdout_tail": "",
                "stderr_tail": "",
                "timed_out": False,
                "cleanup_confirmed": True,
                "cleanup_receipt": {},
            },
        )

        self.assertEqual(receipt["payload"]["status"], "passed")
        self.assertNotIn("model_traces", receipt["payload"])
        self.assertEqual(receipt["stdout_sha256"], "sha256:raw")
        self.assertLess(len(str(receipt)), 10_000)

    def test_exact_receipts_reuse_and_retrieval_change_is_affected_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            evidence_root = root / "evidence"
            current = _snapshot()
            with patch.object(
                assurance,
                "build_component_snapshot",
                side_effect=lambda *_args, **_kwargs: current,
            ), patch.object(
                assurance,
                "_execute_owner",
                side_effect=_successful_owner,
            ) as execute:
                first = assurance.build_report(
                    REPO_ROOT,
                    codex_home,
                    evidence_root=evidence_root,
                )
                self.assertTrue(first["ok"])
                self.assertEqual(first["execution_count"], len(assurance.OWNER_ORDER))
                self.assertEqual(execute.call_count, len(assurance.OWNER_ORDER))

                execute.reset_mock()
                second = assurance.build_report(
                    REPO_ROOT,
                    codex_home,
                    evidence_root=evidence_root,
                )
                self.assertTrue(second["ok"])
                self.assertEqual(second["execution_count"], 0)
                self.assertEqual(execute.call_count, 0)

                current = _snapshot(planner_source="sha256:planner-changed")
                planner_only = assurance.build_report(
                    REPO_ROOT,
                    codex_home,
                    evidence_root=evidence_root,
                )
                self.assertTrue(planner_only["ok"])
                self.assertEqual(planner_only["execution_count"], 0)
                self.assertEqual(execute.call_count, 0)

                current = _snapshot(retrieval_source="sha256:retrieval-changed")
                third = assurance.build_report(
                    REPO_ROOT,
                    codex_home,
                    evidence_root=evidence_root,
                )
                self.assertTrue(third["ok"])
                self.assertEqual(third["execution_count"], 1)
                self.assertEqual(third["executed_owner_ids"], ["retrieval_quality"])
                self.assertEqual(execute.call_count, 1)

                execute.reset_mock()
                audit = assurance.audit_current_assurance(
                    REPO_ROOT,
                    codex_home,
                    evidence_root=evidence_root,
                    expected_receipt_hash=third["receipt_hash"],
                )
                self.assertTrue(audit["ok"], audit["issues"])
                self.assertEqual(audit["execution_count"], 0)
                self.assertEqual(execute.call_count, 0)

    def test_unknown_component_blocks_without_running_an_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshot = _snapshot(undeclared_component="sha256:unknown")
            with patch.object(
                assurance,
                "build_component_snapshot",
                return_value=snapshot,
            ), patch.object(
                assurance,
                "_execute_owner",
                side_effect=AssertionError("unknown input ran an owner"),
            ):
                report = assurance.build_report(
                    REPO_ROOT,
                    root / ".codex",
                    evidence_root=root / "evidence",
                )

        self.assertFalse(report["ok"])
        self.assertEqual(report["failed_checks"], ["component_map"])
        self.assertIn(
            "unknown-component:undeclared_component",
            report["issues"],
        )

    def test_late_input_change_replans_only_its_declared_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = _snapshot()
            new = _snapshot(retrieval_source="sha256:late-retrieval-change")
            snapshots = iter((old, new, new, new))
            executed: list[str] = []

            def execute(owner_id: str, *_args: object, **_kwargs: object):
                executed.append(owner_id)
                return _successful_owner()

            with patch.object(
                assurance,
                "build_component_snapshot",
                side_effect=lambda *_args, **_kwargs: next(snapshots),
            ), patch.object(
                assurance,
                "_execute_owner",
                side_effect=execute,
            ):
                report = assurance.build_report(
                    REPO_ROOT,
                    root / ".codex",
                    evidence_root=root / "evidence",
                )

            self.assertTrue(report["ok"])
            self.assertEqual(
                report["passes"][0]["affected_owner_ids"],
                ["retrieval_quality"],
            )
            self.assertEqual(
                report["passes"][1]["executed_owner_ids"],
                ["retrieval_quality"],
            )
            self.assertEqual(
                executed.count("retrieval_quality"),
                2,
            )
            for owner_id in set(assurance.OWNER_ORDER) - {"retrieval_quality"}:
                self.assertEqual(executed.count(owner_id), 1)

    def test_failed_or_cleanup_unconfirmed_owner_is_not_published(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            current = _snapshot()

            def execute(owner_id: str, *_args: object, **_kwargs: object):
                if owner_id == "reasoning_runtime":
                    return {
                        "ok": False,
                        "exit_code": None,
                        "payload": {},
                        "stdout_tail": "",
                        "stderr_tail": "timeout",
                        "timed_out": True,
                        "cleanup_confirmed": False,
                        "cleanup_receipt": {
                            "remaining_process_count": 1,
                            "cleanup_confirmed": False,
                        },
                    }
                return _successful_owner()

            evidence_root = root / "evidence"
            with patch.object(
                assurance,
                "build_component_snapshot",
                side_effect=lambda *_args, **_kwargs: current,
            ), patch.object(
                assurance,
                "_execute_owner",
                side_effect=execute,
            ):
                report = assurance.build_report(
                    REPO_ROOT,
                    root / ".codex",
                    evidence_root=evidence_root,
                )

            self.assertFalse(report["ok"])
            self.assertIn("reasoning_runtime", report["failed_checks"])
            self.assertFalse((evidence_root / "current.json").exists())

    def test_shallow_currentness_paths_launch_no_subprocess(self) -> None:
        with patch(
            "subprocess.Popen",
            side_effect=AssertionError("currentness launched a subprocess"),
        ), patch(
            "scripts.check_consumer_install_assurance.audit_current_assurance",
            return_value={
                "ok": False,
                "status": "stale",
                "execution_count": 0,
                "issues": ["fixture-stale"],
            },
        ):
            report = build_installation_check(
                REPO_ROOT,
                Path.home() / ".codex",
            )
        self.assertEqual(
            report["upgrade_assurance_currentness"]["execution_count"],
            0,
        )

    def test_migration_currentness_does_not_run_full_validation(self) -> None:
        with patch(
            "local_kb.maintenance_migration.validate_migration",
            side_effect=AssertionError("full migration validation executed"),
        ):
            report = check_migration_current_authority(REPO_ROOT)
        self.assertIn(report["status"], {"current", "stale"})
        self.assertIn(
            "Bounded read-only committed-authority check",
            report["claim_boundary"],
        )


if __name__ == "__main__":
    unittest.main()
