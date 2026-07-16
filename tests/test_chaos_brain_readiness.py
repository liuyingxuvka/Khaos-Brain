from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from scripts import check_chaos_brain_readiness as readiness


class ChaosBrainReadinessTests(unittest.TestCase):
    def test_run_resolves_windows_launcher_and_preserves_canonical_command(self) -> None:
        resolved = readiness.shutil.which("openspec")
        self.assertTrue(resolved)
        completed = subprocess.CompletedProcess(
            [resolved, "--version"],
            0,
            stdout="1.6.0\n",
            stderr="",
        )
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            readiness,
            "run_with_timeout_cleanup",
            return_value=completed,
        ) as runner:
            root = Path(temp_dir).resolve()
            name, receipt = readiness._run(
                ("openspec_probe", ["openspec", "--version"]),
                root,
                evidence_dir=root / "evidence",
                source_snapshot={"digest": "source"},
                verifier_fingerprint={"digest": "verifier"},
            )

        self.assertEqual(name, "openspec_probe")
        self.assertEqual(receipt["command"], ["openspec", "--version"])
        self.assertEqual(receipt["execution_command"][0], str(Path(resolved).resolve()))
        self.assertEqual(receipt["executable_identity"]["resolved_path"], str(Path(resolved).resolve()))
        self.assertTrue(receipt["ok"])
        self.assertEqual(runner.call_args.args[0][0], str(Path(resolved).resolve()))

    def test_flowguard_identity_is_bound_to_complete_frozen_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "flowguard"
            root.mkdir(parents=True)
            init = root / "__init__.py"
            init.write_text("SCHEMA_VERSION = 'test'\n", encoding="utf-8")
            (root / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            module = type("FlowGuardModule", (), {"__file__": str(init)})()
            # This test owns a synthetic FlowGuard tree.  A formal Chaos Brain
            # run intentionally exports a different frozen production root, so
            # clear that inherited authority for the synthetic preflight only.
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST": "",
                },
            ):
                first = readiness._flowguard_toolchain_identity(module)
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT": str(root),
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST": first["digest"],
                },
            ):
                self.assertEqual(
                    first["digest"],
                    readiness._flowguard_toolchain_identity(module)["digest"],
                )
                (root / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "digest"):
                    readiness._flowguard_toolchain_identity(module)

    def test_logicguard_identity_is_bound_to_complete_frozen_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "logicguard"
            root.mkdir(parents=True)
            init = root / "__init__.py"
            init.write_text("# synthetic LogicGuard package\n", encoding="utf-8")
            (root / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            module = type(
                "LogicGuardModule",
                (),
                {
                    "__file__": str(init),
                    "__version__": "test",
                    "SCHEMA_VERSION": "logicguard.model-store.v1",
                    "MESH_SCHEMA_VERSION": "logicguard.model-mesh.v1",
                    "FileModelStore": object(),
                    "FileModelMeshStore": object(),
                    "MeshNodeOverride": object(),
                    "simulate_mesh": object(),
                },
            )()
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST": "",
                },
            ):
                first = readiness._logicguard_toolchain_identity(module)
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_ROOT": str(root),
                    "KHAOS_BRAIN_LOGICGUARD_VALIDATION_DIGEST": first["digest"],
                },
            ):
                self.assertEqual(
                    first["digest"],
                    readiness._logicguard_toolchain_identity(module)["digest"],
                )
                (root / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "digest"):
                    readiness._logicguard_toolchain_identity(module)

    def _write_current_full_regression(
        self,
        root: Path,
        *,
        source_digest: str = "source",
        verifier_digest: str = "verifier",
    ) -> tuple[Path, Path, Path, list[str], str]:
        tests_root = root / "tests"
        tests_root.mkdir(parents=True, exist_ok=True)
        (tests_root / "test_sample.py").write_text("", encoding="utf-8")
        evidence_root = root / "evidence"
        owner_dir = evidence_root / "owner-run"
        owner_dir.mkdir(parents=True)
        junit_path = owner_dir / "full-regression.junit.xml"
        junit_path.write_text(
            '<?xml version="1.0"?><testsuites><testsuite>'
            '<testcase classname="tests.test_sample" name="test_ok" />'
            "</testsuite></testsuites>",
            encoding="utf-8",
        )
        command = [
            "python",
            "-m",
            "pytest",
            "tests",
            f"--junitxml={junit_path}",
        ]
        environment = readiness._environment_contract(root)
        identity = readiness._command_identity(
            command,
            source_digest=source_digest,
            verifier_digest=verifier_digest,
            environment_contract=environment,
        )
        receipt = {
            "schema_version": readiness.EVIDENCE_SCHEMA,
            "receipt_id": f"validation:full_regression:{identity}",
            "name": "full_regression",
            "execution": "executed",
            "identity_fingerprint": identity,
            "command": command,
            "semantic_argv": readiness._semantic_argv(command),
            "cwd": str(root.resolve()),
            "environment_contract": environment,
            "input_fingerprints": {
                "source": source_digest,
                "verifier": verifier_digest,
            },
            "inventory_revision": "owner-inventory",
            "terminal_status": "passed",
            "timed_out": False,
            "exit_code": 0,
            "ok": True,
            "junit": readiness._junit_summary(junit_path, root),
            "proof_artifact_ref": readiness._proof_ref(junit_path),
        }
        receipt_path = owner_dir / "full_regression.receipt.json"
        receipt_path.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipt_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        manifest = {
            "schema_version": readiness.EVIDENCE_SCHEMA,
            "entries": {
                "full_regression": {
                    **receipt,
                    "receipt_path": str(receipt_path.resolve()),
                    "receipt_sha256": receipt_hash,
                }
            },
        }
        current_path = evidence_root / "current.json"
        current_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return current_path, receipt_path, junit_path, command, identity

    def test_skillguard_consumers_receive_the_single_full_regression_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            junit = root / "evidence" / "full-regression.junit.xml"
            commands = readiness._commands(
                root,
                root / ".codex",
                pre_restore=True,
                junit_path=junit,
            )

        expected = str(junit.parent / "full_regression.receipt.json")
        for name in (
            "skillguard_source_install_parity",
            "skillguard_source_assurance",
        ):
            command = commands[name]
            index = command.index("--capability-receipt")
            self.assertEqual(expected, command[index + 1])

    def test_full_regression_has_an_exclusive_validation_lane(self) -> None:
        active: set[str] = set()
        completed: set[str] = set()
        lock = threading.Lock()
        full_regression_started_exclusively = False
        consumers_started_after_full = True
        logicguard_started_exclusively = False
        logicguard_started_after_other_children = False
        scheduled_production_started_exclusively = False
        scheduled_production_started_after_other_children = False

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            nonlocal full_regression_started_exclusively
            nonlocal consumers_started_after_full
            nonlocal logicguard_started_exclusively
            nonlocal logicguard_started_after_other_children
            nonlocal scheduled_production_started_exclusively
            nonlocal scheduled_production_started_after_other_children
            name, command = item
            with lock:
                if name == "full_regression":
                    full_regression_started_exclusively = not active and not completed
                else:
                    consumers_started_after_full = (
                        consumers_started_after_full
                        and "full_regression" in completed
                    )
                if name == "logicguard_runtime":
                    logicguard_started_exclusively = not active
                    logicguard_started_after_other_children = {
                        "full_regression",
                        "flowguard_models",
                        "skillguard_source_assurance",
                        "retired_architect_absence",
                        "retrieval_quality",
                    }.issubset(completed)
                if name == "skillguard_source_install_parity":
                    scheduled_production_started_exclusively = not active
                    scheduled_production_started_after_other_children = {
                        "full_regression",
                        "flowguard_models",
                        "logicguard_runtime",
                        "skillguard_source_assurance",
                        "retired_architect_absence",
                        "retrieval_quality",
                    }.issubset(completed)
                active.add(name)
            time.sleep(0.01)
            with lock:
                active.remove(name)
                completed.add(name)
            identity = name + "-identity"
            return name, {
                "receipt_id": f"validation:{name}:{identity}",
                "identity_fingerprint": identity,
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        commands = {
            "flowguard_models": ["python", "flowguard.py"],
            "logicguard_runtime": ["python", "logicguard.py"],
            "skillguard_source_install_parity": ["python", "skillguard.py"],
            "skillguard_source_assurance": ["python", "skillguard.py", "--source-only"],
            "retired_architect_absence": ["python", "architect.py"],
            "retrieval_quality": ["python", "retrieval.py"],
            "full_regression": ["python", "-m", "pytest", "tests"],
        }
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            readiness, "_run", side_effect=fake_run
        ):
            results, counts = readiness._execute_plan(
                commands,
                Path(temp_dir),
                evidence_dir=Path(temp_dir) / "evidence",
                source_snapshot={"digest": "source"},
                verifier_fingerprint={"digest": "verifier"},
            )

        self.assertTrue(all(item["ok"] for item in results.values()))
        self.assertTrue(full_regression_started_exclusively)
        self.assertTrue(consumers_started_after_full)
        self.assertTrue(logicguard_started_exclusively)
        self.assertTrue(logicguard_started_after_other_children)
        self.assertTrue(scheduled_production_started_exclusively)
        self.assertTrue(scheduled_production_started_after_other_children)
        self.assertTrue(all(count == 1 for count in counts.values()))

    def test_exact_duplicate_command_is_executed_once_and_reused(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            return name, {
                "receipt_id": f"validation:{name}:same",
                "identity_fingerprint": readiness._command_identity(
                    command,
                    source_digest="source",
                    verifier_digest="verifier",
                    environment_contract=readiness._environment_contract(Path(".")),
                ),
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        command = ["python", "check.py"]
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            readiness, "_run", side_effect=fake_run
        ):
            results, counts = readiness._execute_plan(
                {"owner": command, "consumer": list(command)},
                Path("."),
                evidence_dir=Path(temp_dir),
                source_snapshot={"digest": "source"},
                verifier_fingerprint={"digest": "verifier"},
            )

        self.assertEqual(calls, ["owner"])
        self.assertEqual(results["consumer"]["execution"], "reused")
        self.assertEqual(sum(counts.values()), 1)

    def test_current_full_regression_receipt_is_reused_across_aggregate_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            current, owner_receipt, _, command, identity = (
                self._write_current_full_regression(root)
            )
            next_dir = root / "evidence" / "next-run"
            next_command = [
                *command[:-1],
                f"--junitxml={next_dir / 'full-regression.junit.xml'}",
            ]
            with mock.patch.object(
                readiness,
                "_run",
                side_effect=AssertionError("full regression must not rerun"),
            ):
                results, counts = readiness._execute_plan(
                    {"full_regression": next_command},
                    root,
                    evidence_dir=next_dir,
                    source_snapshot={"digest": "source"},
                    verifier_fingerprint={"digest": "verifier"},
                    inventory_revision="consumer-inventory",
                    current_manifest_path=current,
                )

            row = results["full_regression"]
            alias = Path(row["receipt_path"])
            self.assertEqual(row["execution"], "reused")
            self.assertEqual(row["identity_fingerprint"], identity)
            self.assertEqual(row["inventory_revision"], "consumer-inventory")
            self.assertEqual(row["reuse_ticket"]["source_inventory_revision"], "owner-inventory")
            self.assertEqual(alias.read_bytes(), owner_receipt.read_bytes())
            self.assertEqual(json.loads(alias.read_text())["execution"], "executed")
            self.assertEqual(counts, {})

    def test_changed_full_regression_proof_forces_one_new_execution(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            identity = readiness._command_identity(
                command,
                source_digest="source",
                verifier_digest="verifier",
                environment_contract=readiness._environment_contract(root),
            )
            return name, {
                "receipt_id": f"validation:{name}:{identity}",
                "identity_fingerprint": identity,
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            current, _, junit, command, _ = self._write_current_full_regression(root)
            junit.write_text("tampered", encoding="utf-8")
            next_dir = root / "evidence" / "next-run"
            next_command = [
                *command[:-1],
                f"--junitxml={next_dir / 'full-regression.junit.xml'}",
            ]
            with mock.patch.object(readiness, "_run", side_effect=fake_run):
                results, counts = readiness._execute_plan(
                    {"full_regression": next_command},
                    root,
                    evidence_dir=next_dir,
                    source_snapshot={"digest": "source"},
                    verifier_fingerprint={"digest": "verifier"},
                    inventory_revision="consumer-inventory",
                    current_manifest_path=current,
                )

        self.assertEqual(calls, ["full_regression"])
        self.assertEqual(results["full_regression"]["execution"], "executed")
        self.assertEqual(sum(counts.values()), 1)

    def test_task_checkbox_bookkeeping_does_not_stale_source_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task_path = (
                root
                / "openspec"
                / "changes"
                / "converge-kb-learning-and-upgrade-migration"
                / "tasks.md"
            )
            task_path.parent.mkdir(parents=True)
            task_path.write_text("- [ ] Execute validation\n", encoding="utf-8")
            before = readiness._source_snapshot(root)
            task_path.write_text("- [x] Execute validation\n", encoding="utf-8")
            after_checkbox = readiness._source_snapshot(root)
            task_path.write_text("- [x] Execute different validation\n", encoding="utf-8")
            after_semantic_change = readiness._source_snapshot(root)

        self.assertEqual(before["digest"], after_checkbox["digest"])
        self.assertNotEqual(after_checkbox["digest"], after_semantic_change["digest"])

    def test_junit_summary_preserves_parameterized_node_ids_and_skips(self) -> None:
        xml = (
            '<?xml version="1.0"?><testsuites><testsuite>'
            '<testcase classname="tests.test_sample.TestSample" name="test_ok[value]" />'
            '<testcase classname="tests.test_sample" name="test_skip"><skipped /></testcase>'
            "</testsuite></testsuites>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "tests").mkdir()
            (root / "tests" / "test_sample.py").write_text("", encoding="utf-8")
            junit = root / "result.xml"
            junit.write_text(xml, encoding="utf-8")
            summary = readiness._junit_summary(junit, root)

        self.assertEqual(
            summary["passed_node_ids"],
            ["tests/test_sample.py::TestSample::test_ok[value]"],
        )
        self.assertEqual(
            summary["skipped_node_ids"],
            ["tests/test_sample.py::test_skip"],
        )

    def test_readiness_composes_alignment_without_launching_alignment_command(self) -> None:
        captured_commands: dict[str, list[str]] = {}

        def fake_execute(commands, repo_root, **kwargs):
            del repo_root, kwargs
            captured_commands.update(commands)
            rows = {
                name: {
                    "ok": True,
                    "receipt_id": f"validation:{name}:id",
                    "identity_fingerprint": f"identity:{name}",
                    "execution": "executed",
                }
                for name in commands
            }
            return rows, {f"identity:{name}": 1 for name in commands}

        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            readiness, "_execute_plan", side_effect=fake_execute
        ), mock.patch.object(
            readiness,
            "_verifier_fingerprint",
            return_value={"digest": "verifier"},
        ), mock.patch.object(
            readiness,
            "_alignment_from_manifest",
            return_value={"ok": True, "consumed_receipt_ids": []},
        ):
            root = Path(temp_dir)
            report = readiness.build_report(
                root,
                root / "codex-home",
                pre_restore=True,
                evidence_root=root / "evidence",
            )

        self.assertTrue(report["ok"])
        self.assertNotIn("model_code_test_alignment", captured_commands)
        self.assertEqual(
            sum(name == "full_regression" for name in captured_commands), 1
        )
        self.assertEqual(
            report["checks"]["model_code_test_alignment"]["execution"],
            "consumed",
        )

    def test_direct_script_context_resolves_the_repo_alignment_owner(self) -> None:
        script = readiness.REPO_ROOT / "scripts" / "check_chaos_brain_readiness.py"
        program = (
            "import runpy; "
            f"ns=runpy.run_path({str(script)!r}); "
            "report=ns['_alignment_from_manifest']({}); "
            "assert isinstance(report, dict) and report.get('check') == "
            "'kb-model-code-test-alignment'"
        )
        completed = subprocess.run(
            [sys.executable, "-P", "-c", program],
            cwd=readiness.REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )

        self.assertEqual(
            completed.returncode,
            0,
            msg=f"stdout={completed.stdout}\nstderr={completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
