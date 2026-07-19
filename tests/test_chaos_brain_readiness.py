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
    def _verifier_fingerprint(self) -> dict[str, object]:
        return {
            "evidence_policy_version": readiness.EVIDENCE_POLICY_VERSION,
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": "test-python",
            "platform": "test-platform",
            "pytest_version": "test-pytest",
            "flowguard_toolchain": {"digest": "flowguard", "file_count": 1},
            "researchguard_logic_toolchain": {
                "digest": "researchguard",
                "file_count": 1,
                "version": "test",
                "model_store_schema": "model-v1",
                "mesh_schema": "mesh-v1",
            },
        }

    def _owner_snapshot(
        self,
        owner: str,
        digest: str = "source",
    ) -> dict[str, object]:
        return {
            "owner": owner,
            "digest": digest,
            "components": [
                {
                    "component_id": f"component:{owner}",
                    "digest": digest,
                    "file_count": 1,
                }
            ],
        }

    def _owner_snapshots(
        self,
        commands: dict[str, list[str]],
        digest: str = "source",
    ) -> dict[str, dict[str, object]]:
        return {
            owner: self._owner_snapshot(owner, digest)
            for owner in commands
        }

    def test_run_resolves_windows_launcher_and_preserves_canonical_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            launcher = root / "openspec.cmd"
            launcher.write_text("@echo off\r\n", encoding="utf-8")
            resolved = str(launcher.resolve())
            completed = subprocess.CompletedProcess(
                [resolved, "--version"],
                0,
                stdout="1.6.0\n",
                stderr="",
            )
            readiness._resolved_executable_identity.cache_clear()
            try:
                with mock.patch.object(
                    readiness.shutil, "which", return_value=resolved
                ), mock.patch.object(
                    readiness,
                    "run_with_timeout_cleanup",
                    return_value=completed,
                ) as runner:
                    name, receipt = readiness._run(
                        ("openspec_probe", ["openspec", "--version"]),
                        root,
                        evidence_dir=root / "evidence",
                        owner_component_snapshot=self._owner_snapshot(
                            "openspec_probe"
                        ),
                        owner_verifier_fingerprint={"digest": "verifier"},
                    )
            finally:
                readiness._resolved_executable_identity.cache_clear()

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

    def test_researchguard_logic_identity_is_bound_to_complete_frozen_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "researchguard"
            root.mkdir(parents=True)
            init = root / "__init__.py"
            init.write_text("# synthetic ResearchGuard package\n", encoding="utf-8")
            (root / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            logic_root = root / "logic"
            logic_root.mkdir()
            logic_init = logic_root / "__init__.py"
            logic_init.write_text(
                "# synthetic ResearchGuard logic member\n",
                encoding="utf-8",
            )
            package_module = type(
                "ResearchGuardModule",
                (),
                {"__file__": str(init), "__version__": "test"},
            )()
            logic_module = type(
                "ResearchGuardLogicModule",
                (),
                {
                    "__file__": str(logic_init),
                    "__version__": "test",
                    "SCHEMA_VERSION": "researchguard.logic.model-store.v1",
                    "MESH_SCHEMA_VERSION": "researchguard.logic.model-mesh.v1",
                    "FileModelStore": object(),
                    "FileModelMeshStore": object(),
                    "MeshNodeOverride": object(),
                    "simulate_mesh": object(),
                },
            )()
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST": "",
                },
            ):
                first = readiness._researchguard_logic_toolchain_identity(
                    package_module,
                    logic_module,
                )
            with mock.patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT": str(root),
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST": first[
                        "digest"
                    ],
                },
            ):
                self.assertEqual(
                    first["digest"],
                    readiness._researchguard_logic_toolchain_identity(
                        package_module,
                        logic_module,
                    )["digest"],
                )
                (root / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
                with self.assertRaisesRegex(RuntimeError, "digest"):
                    readiness._researchguard_logic_toolchain_identity(
                        package_module,
                        logic_module,
                    )

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
        snapshot = self._owner_snapshot("full_regression", source_digest)
        owner_verifier = readiness._owner_verifier_fingerprint(
            "full_regression",
            self._verifier_fingerprint(),
        )
        identity = readiness._command_identity(
            command,
            owner_component_digest=source_digest,
            verifier_digest=str(owner_verifier["digest"]),
            environment_contract=environment,
        )
        receipt = {
            "schema_version": readiness.EVIDENCE_SCHEMA,
            "receipt_id": f"validation:full_regression:{identity}",
            "name": "full_regression",
            "execution": "executed",
            "identity_fingerprint": identity,
            "command": command,
            "executable_identity": readiness._executable_identity(command[0]),
            "semantic_argv": readiness._semantic_argv(command),
            "cwd": str(root.resolve()),
            "environment_contract": environment,
            "input_fingerprints": {
                "owner_components": source_digest,
                "verifier": owner_verifier["digest"],
            },
            "owner_components": snapshot["components"],
            "owner_verifier_fingerprint": owner_verifier,
            "inventory_revision": "owner-inventory",
            "terminal_status": "passed",
            "timed_out": False,
            "cleanup_confirmed": True,
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

    def _write_current_owner_receipts(
        self,
        root: Path,
        owners: dict[str, tuple[list[str], dict[str, object], int]],
    ) -> Path:
        evidence_root = root / "evidence"
        owner_dir = evidence_root / "owner-run"
        owner_dir.mkdir(parents=True, exist_ok=True)
        verifier = self._verifier_fingerprint()
        entries: dict[str, dict[str, object]] = {}
        for owner, (command, snapshot, exit_code) in owners.items():
            completed = subprocess.CompletedProcess(
                command,
                exit_code,
                stdout=json.dumps({"ok": exit_code == 0}),
                stderr="",
            )
            with mock.patch.object(
                readiness,
                "run_with_timeout_cleanup",
                return_value=completed,
            ):
                _, receipt = readiness._run(
                    (owner, command),
                    root,
                    evidence_dir=owner_dir,
                    owner_component_snapshot=dict(snapshot),
                    owner_verifier_fingerprint=readiness._owner_verifier_fingerprint(
                        owner,
                        verifier,
                    ),
                    inventory_revision="owner-inventory",
                )
            entries[owner] = receipt
        current = {
            "schema_version": readiness.EVIDENCE_SCHEMA,
            "entries": entries,
        }
        current_path = evidence_root / "current.json"
        current_path.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return current_path

    def test_author_contract_audit_does_not_consume_regression_or_installed_runtime(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            junit = root / "evidence" / "full-regression.junit.xml"
            commands = readiness._commands(
                root,
                root / ".codex",
                pre_restore=True,
                junit_path=junit,
            )

        command = commands["author_contract_assurance"]
        self.assertIn("--source-only", command)
        self.assertNotIn("--execute-checks", command)
        self.assertNotIn("--capability-receipt", command)
        self.assertNotIn("--codex-home", command)
        self.assertNotIn("--refresh-global-router-before-check", command)
        self.assertNotIn("skillguard_source_install_parity", commands)

    def test_full_regression_has_an_exclusive_validation_lane(self) -> None:
        active: set[str] = set()
        completed: set[str] = set()
        lock = threading.Lock()
        full_regression_started_exclusively = False
        consumers_started_after_full = True
        logicguard_started_exclusively = False
        logicguard_started_after_other_children = False

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            nonlocal full_regression_started_exclusively
            nonlocal consumers_started_after_full
            nonlocal logicguard_started_exclusively
            nonlocal logicguard_started_after_other_children
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
                        "author_contract_assurance",
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
            "author_contract_assurance": ["python", "author_contracts.py"],
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
                owner_component_snapshots=self._owner_snapshots(commands),
                verifier_fingerprint=self._verifier_fingerprint(),
            )

        self.assertTrue(all(item["ok"] for item in results.values()))
        self.assertTrue(full_regression_started_exclusively)
        self.assertTrue(consumers_started_after_full)
        self.assertTrue(logicguard_started_exclusively)
        self.assertTrue(logicguard_started_after_other_children)
        self.assertTrue(all(count == 1 for count in counts.values()))

    def test_exact_duplicate_command_with_two_owners_is_blocked(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            return name, {
                "receipt_id": f"validation:{name}:same",
                "identity_fingerprint": readiness._command_identity(
                    command,
                    owner_component_digest="source",
                    verifier_digest=str(
                        readiness._owner_verifier_fingerprint(
                            name,
                            self._verifier_fingerprint(),
                        )["digest"]
                    ),
                    environment_contract=readiness._environment_contract(Path(".")),
                ),
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        command = ["python", "check.py"]
        shared_snapshot = {
            "owner": "shared-command",
            "digest": "source",
            "components": [
                {
                    "component_id": "component:shared-command",
                    "digest": "source",
                    "file_count": 1,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir, mock.patch.object(
            readiness, "_run", side_effect=fake_run
        ), self.assertRaisesRegex(
            RuntimeError,
            "multiple owners",
        ):
            readiness._execute_plan(
                {"owner": command, "consumer": list(command)},
                Path("."),
                evidence_dir=Path(temp_dir),
                owner_component_snapshots={
                    "owner": shared_snapshot,
                    "consumer": shared_snapshot,
                },
                verifier_fingerprint=self._verifier_fingerprint(),
            )

        self.assertEqual(calls, [])

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
                    owner_component_snapshots={
                        "full_regression": self._owner_snapshot(
                            "full_regression"
                        )
                    },
                    verifier_fingerprint=self._verifier_fingerprint(),
                    inventory_revision="consumer-inventory",
                    current_manifest_path=current,
                )

            row = results["full_regression"]
            projection = Path(row["receipt_path"])
            self.assertEqual(row["execution"], "reused")
            self.assertEqual(row["identity_fingerprint"], identity)
            self.assertEqual(row["inventory_revision"], "consumer-inventory")
            self.assertEqual(row["reuse_ticket"]["source_inventory_revision"], "owner-inventory")
            stored = json.loads(projection.read_text(encoding="utf-8"))
            self.assertEqual(stored["execution"], "executed")
            self.assertEqual(
                stored["compacted_from"]["receipt_sha256"],
                hashlib.sha256(owner_receipt.read_bytes()).hexdigest(),
            )
            self.assertLess(
                projection.stat().st_size,
                owner_receipt.stat().st_size + 2_000,
            )
            self.assertEqual(
                json.loads(projection.read_text())["execution"],
                "executed",
            )
            self.assertEqual(counts, {})

    def test_changed_full_regression_proof_forces_one_new_execution(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            identity = readiness._command_identity(
                command,
                owner_component_digest="source",
                verifier_digest=str(
                    readiness._owner_verifier_fingerprint(
                        name,
                        self._verifier_fingerprint(),
                    )["digest"]
                ),
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
                    owner_component_snapshots={
                        "full_regression": self._owner_snapshot(
                            "full_regression"
                        )
                    },
                    verifier_fingerprint=self._verifier_fingerprint(),
                    inventory_revision="consumer-inventory",
                    current_manifest_path=current,
                )

        self.assertEqual(calls, ["full_regression"])
        self.assertEqual(results["full_regression"]["execution"], "executed")
        self.assertEqual(sum(counts.values()), 1)

    def test_exact_non_regression_owner_receipt_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            command = [sys.executable, "-c", "print('ok')"]
            snapshot = self._owner_snapshot("retrieval_quality")
            current = self._write_current_owner_receipts(
                root,
                {"retrieval_quality": (command, snapshot, 0)},
            )
            next_dir = root / "evidence" / "next-run"
            with mock.patch.object(
                readiness,
                "_run",
                side_effect=AssertionError("current owner must not rerun"),
            ):
                results, counts = readiness._execute_plan(
                    {"retrieval_quality": command},
                    root,
                    evidence_dir=next_dir,
                    owner_component_snapshots={"retrieval_quality": snapshot},
                    verifier_fingerprint=self._verifier_fingerprint(),
                    current_manifest_path=current,
                )

        self.assertEqual(results["retrieval_quality"]["execution"], "reused")
        self.assertEqual(counts, {})

    def test_failed_non_regression_owner_receipt_is_not_reused(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            return name, {
                "receipt_id": f"validation:{name}:new",
                "identity_fingerprint": f"new:{name}",
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            command = [sys.executable, "-c", "raise SystemExit(1)"]
            snapshot = self._owner_snapshot("retrieval_quality")
            current = self._write_current_owner_receipts(
                root,
                {"retrieval_quality": (command, snapshot, 1)},
            )
            with mock.patch.object(readiness, "_run", side_effect=fake_run):
                results, _ = readiness._execute_plan(
                    {"retrieval_quality": command},
                    root,
                    evidence_dir=root / "evidence" / "next-run",
                    owner_component_snapshots={"retrieval_quality": snapshot},
                    verifier_fingerprint=self._verifier_fingerprint(),
                    current_manifest_path=current,
                )

        self.assertEqual(calls, ["retrieval_quality"])
        self.assertEqual(results["retrieval_quality"]["execution"], "executed")

    def test_timeout_hash_mismatch_and_missing_proof_are_not_reused(self) -> None:
        for variant in ("timeout", "receipt-hash-mismatch", "missing-proof"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir).resolve()
                owner = "retrieval_quality"
                command = [sys.executable, "-c", "print('ok')"]
                snapshot = self._owner_snapshot(owner)
                verifier = readiness._owner_verifier_fingerprint(
                    owner,
                    self._verifier_fingerprint(),
                )
                current = self._write_current_owner_receipts(
                    root,
                    {owner: (command, snapshot, 0)},
                )
                manifest = json.loads(current.read_text(encoding="utf-8"))
                entry = manifest["entries"][owner]
                receipt_path = Path(entry["receipt_path"])
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if variant == "timeout":
                    receipt.update(
                        {
                            "terminal_status": "timeout",
                            "timed_out": True,
                            "cleanup_confirmed": False,
                            "exit_code": 124,
                            "ok": False,
                        }
                    )
                    receipt_path.write_text(
                        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    entry["receipt_sha256"] = hashlib.sha256(
                        receipt_path.read_bytes()
                    ).hexdigest()
                    current.write_text(
                        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                elif variant == "receipt-hash-mismatch":
                    receipt_path.write_text(
                        receipt_path.read_text(encoding="utf-8") + " ",
                        encoding="utf-8",
                    )
                else:
                    Path(receipt["proof_artifact_ref"]["path"]).unlink()

                reusable = readiness._current_owner_receipt(
                    current,
                    owner,
                    command,
                    root,
                    owner_component_snapshot=snapshot,
                    owner_verifier_fingerprint=verifier,
                )

            self.assertIsNone(reusable)

    def test_one_changed_owner_component_executes_only_that_owner(self) -> None:
        calls: list[str] = []

        def fake_run(item, repo_root, **kwargs):
            del repo_root, kwargs
            name, command = item
            calls.append(name)
            return name, {
                "receipt_id": f"validation:{name}:new",
                "identity_fingerprint": f"new:{name}",
                "execution": "executed",
                "command": command,
                "ok": True,
            }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            commands = {
                "retrieval_quality": [sys.executable, "-c", "print('retrieval')"],
                "current_runtime_only": [sys.executable, "-c", "print('runtime')"],
            }
            old_snapshots = self._owner_snapshots(commands)
            current = self._write_current_owner_receipts(
                root,
                {
                    name: (command, old_snapshots[name], 0)
                    for name, command in commands.items()
                },
            )
            new_snapshots = dict(old_snapshots)
            new_snapshots["retrieval_quality"] = self._owner_snapshot(
                "retrieval_quality",
                "changed",
            )
            with mock.patch.object(readiness, "_run", side_effect=fake_run):
                results, _ = readiness._execute_plan(
                    commands,
                    root,
                    evidence_dir=root / "evidence" / "next-run",
                    owner_component_snapshots=new_snapshots,
                    verifier_fingerprint=self._verifier_fingerprint(),
                    current_manifest_path=current,
                )

        self.assertEqual(calls, ["retrieval_quality"])
        self.assertEqual(results["retrieval_quality"]["execution"], "executed")
        self.assertEqual(results["current_runtime_only"]["execution"], "reused")

    def test_watched_source_classification_is_closed(self) -> None:
        rows = {
            path.relative_to(readiness.REPO_ROOT).as_posix(): (
                readiness._classify_watched_source(
                    path.relative_to(readiness.REPO_ROOT)
                )
            )
            for path in readiness._watched_files(readiness.REPO_ROOT)
        }
        self.assertTrue(rows)
        self.assertFalse(
            [path for path, component in rows.items() if component is None]
        )
        self.assertIsNone(
            readiness._classify_watched_source(Path("unexpected/new.py"))
        )

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

    def test_junit_summary_accepts_only_unique_platform_short_module_aliases(self) -> None:
        xml = (
            '<?xml version="1.0"?><testsuites><testsuite>'
            '<testcase classname="test_unique.TestUnique" name="test_ok" />'
            '<testcase classname="test_shared.TestShared" name="test_ambiguous" />'
            "</testsuite></testsuites>"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "tests" / "one").mkdir(parents=True)
            (root / "tests" / "two").mkdir(parents=True)
            (root / "tests" / "test_unique.py").write_text("", encoding="utf-8")
            (root / "tests" / "one" / "test_shared.py").write_text("", encoding="utf-8")
            (root / "tests" / "two" / "test_shared.py").write_text("", encoding="utf-8")
            junit = root / "result.xml"
            junit.write_text(xml, encoding="utf-8")
            summary = readiness._junit_summary(junit, root)

        self.assertEqual(
            summary["passed_node_ids"],
            ["tests/test_unique.py::TestUnique::test_ok"],
        )
        self.assertEqual(
            summary["unparsed_cases"],
            [{"classname": "test_shared.TestShared", "name": "test_ambiguous"}],
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
            "_build_component_inventory",
            return_value={"ok": True, "issues": [], "components": {}},
        ), mock.patch.object(
            readiness,
            "_owner_component_snapshots",
            side_effect=lambda commands, inventory: (
                self._owner_snapshots(dict(commands)),
                [],
            ),
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
