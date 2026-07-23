from __future__ import annotations

import hashlib
import re
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.install import (
    AUTOMATION_MODEL_ENV_VAR,
    AUTOMATION_REASONING_EFFORT_ENV_VAR,
    MAINTENANCE_SKILL_NAMES,
    REPO_AUTOMATION_SPECS,
    RETIRED_AUTOMATION_IDS,
    RETIRED_MAINTENANCE_SKILL_IDS,
    UPGRADE_ATTEMPT_CURRENT_MAX_BYTES,
    UPGRADE_ATTEMPT_HEAD_SCHEMA,
    automation_rrule_for_spec,
    build_installation_check,
    current_upgrade_attempt_authority,
    global_agents_path,
    install_codex_integration,
    latest_upgrade_attempt,
    _canonical_payload_hash,
    _record_upgrade_attempt,
    _automation_spec_payload,
    _freeze_flowguard_validation_toolchain,
    _freeze_researchguard_logic_validation_toolchain,
    _require_live_flowguard_matches_snapshot,
    _require_live_researchguard_logic_matches_snapshot,
    _restore_exact_file_snapshot,
    _run_pre_restore_upgrade_assurance,
)
from local_kb.config import INSTALL_STATE_SCHEMA, install_state_path, load_install_state
from local_kb.transactional_install import tree_manifest
from scripts.check_retired_kb_architect import build_report as build_architect_retirement_report


SURVIVING_SKILLS = {
    "kb-sleep-maintenance",
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
    "khaos-brain-update",
}
SURVIVING_AUTOMATIONS = {
    "kb-sleep",
    "kb-dream",
    "kb-org-contribute",
    "kb-org-maintenance",
}


def _write_fake_tools(root: Path) -> tuple[Path, Path, Path]:
    shell_bin = root / "shell-bin"
    git_real = root / "tools" / "git-real.cmd"
    rg_source = root / "tools" / "rg-source.exe"
    git_real.parent.mkdir(parents=True, exist_ok=True)
    git_real.write_text("@echo off\r\necho git version test\r\n", encoding="utf-8")
    rg_source.write_bytes(b"rg-binary")
    return shell_bin, git_real, rg_source


def _automation_status(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r'^status = "([A-Z]+)"$', text, re.MULTILINE)
    return match.group(1) if match else ""


class CodexInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self._automation_runtime = patch.dict(
            os.environ,
            {
                AUTOMATION_MODEL_ENV_VAR: "test-current-model",
                AUTOMATION_REASONING_EFFORT_ENV_VAR: "high",
            },
        )
        self._automation_runtime.start()
        self.addCleanup(self._automation_runtime.stop)
        self._update_state_migration = patch(
            "local_kb.software_update.migrate_obsolete_update_state",
            return_value={
                "ok": True,
                "status": "fixture_skipped",
                "legacy_state_found": False,
                "legacy_schema_found": False,
                "residual_retired_state_count": 0,
            },
        )
        self._update_state_migration.start()
        self.addCleanup(self._update_state_migration.stop)
        self._retired_standalone_logicguard = patch(
            "local_kb.logicguard_models.retired_standalone_logicguard_residuals",
            return_value={
                "schema_version": (
                    "khaos-brain.retired-standalone-logicguard-residuals.v1"
                ),
                "ok": True,
                "distribution": {"present": False},
                "import_resolution": {"present": False},
                "runtime_modules": [],
                "issues": [],
            },
        )
        self._retired_standalone_logicguard.start()
        self.addCleanup(self._retired_standalone_logicguard.stop)

    def test_upgrade_attempt_current_projection_is_bounded_and_event_backed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            attempt_id = "upgrade-bounded-projection"
            huge_journal = "J" * 2_000_000
            huge_checks = [{"check_id": "full", "stdout": "C" * 2_000_000}]
            first = _record_upgrade_attempt(
                codex_home,
                attempt_id,
                phase="affected_assurance_stable",
                status="in_progress",
                details={
                    "history_migration": {
                        "ok": True,
                        "status": "committed",
                        "migration_id": "migration-fixture",
                        "journal": huge_journal,
                    },
                    "upgrade_assurance": {
                        "schema_version": (
                            "khaos-brain.consumer-install-assurance.v2"
                        ),
                        "ok": True,
                        "status": "passed",
                        "owners": {
                            "flow_model": {
                                "status": "passed",
                                "payload": huge_checks,
                            }
                        },
                        "failed_checks": [],
                        "receipt_hash": "sha256:fixture",
                    },
                    "researchguard_logic_validation_toolchain": {
                        "ok": True,
                        "status": "frozen",
                        "snapshot_root": str(Path(tmp) / "researchguard"),
                        "manifest": {
                            "digest": "A" * 64,
                            "file_count": 2,
                            "files": [{"path": "large", "content": "M" * 2_000_000}],
                        },
                    },
                },
            )

            current_path = Path(first["current_path"])
            self.assertLess(current_path.stat().st_size, 100_000)
            self.assertEqual(
                first["projection_schema_version"],
                "khaos-brain.upgrade-attempt-projection.v2",
            )
            self.assertNotIn("journal", first["history_migration"])
            self.assertEqual(first["upgrade_assurance"]["owner_count"], 1)
            self.assertNotIn("owners", first["upgrade_assurance"])
            self.assertNotIn(
                "files",
                first["researchguard_logic_validation_toolchain"]["manifest"],
            )
            event_path = (
                current_path.parent
                / first["checkpoint_refs"][0]["relative_path"]
            )
            self.assertGreater(event_path.stat().st_size, 6_000_000)
            head_path = (
                codex_home / ".khaos-brain-install" / "attempts" / "HEAD.json"
            )
            self.assertTrue(head_path.is_file())
            self.assertLess(head_path.stat().st_size, 32_000)
            old_attempt = (
                codex_home
                / ".khaos-brain-install"
                / "attempts"
                / "unreferenced-old-attempt"
            )
            old_attempt.mkdir(parents=True)
            (old_attempt / "current.json").write_bytes(b"X" * 8_000_000)

            started = time.perf_counter()
            authority = current_upgrade_attempt_authority(codex_home)
            elapsed = time.perf_counter() - started
            self.assertTrue(authority["ok"], authority)
            self.assertLess(elapsed, 1.0)
            self.assertEqual(
                authority["read_budget"]["history_files_scanned"],
                0,
            )
            self.assertLess(
                authority["read_budget"]["observed_current_bytes"],
                authority["read_budget"]["current_max_bytes"],
            )
            self.assertEqual(
                latest_upgrade_attempt(codex_home)["receipt_hash"],
                first["receipt_hash"],
            )

    def test_upgrade_attempt_currentness_fails_fast_without_head(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            old_attempt = (
                codex_home
                / ".khaos-brain-install"
                / "attempts"
                / "old-only"
            )
            old_attempt.mkdir(parents=True)
            (old_attempt / "current.json").write_bytes(b"X" * 8_000_000)

            started = time.perf_counter()
            authority = current_upgrade_attempt_authority(codex_home)
            elapsed = time.perf_counter() - started

            self.assertFalse(authority["ok"])
            self.assertIn("upgrade-attempt-head-missing", authority["issues"])
            self.assertEqual(authority["read_budget"]["history_files_scanned"], 0)
            self.assertEqual(authority["read_budget"]["observed_current_bytes"], 0)
            self.assertLess(elapsed, 1.0)
            self.assertEqual(latest_upgrade_attempt(codex_home), {})

    def test_upgrade_attempt_currentness_reads_at_most_one_bounded_projection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            attempt_root = (
                codex_home / ".khaos-brain-install" / "attempts"
            )
            current_path = attempt_root / "oversized-current" / "current.json"
            current_path.parent.mkdir(parents=True)
            current_path.write_bytes(
                b"X" * (UPGRADE_ATTEMPT_CURRENT_MAX_BYTES + 10_000)
            )
            current_raw_hash = hashlib.sha256(
                current_path.read_bytes()
            ).hexdigest().upper()
            head_body = {
                "schema_version": UPGRADE_ATTEMPT_HEAD_SCHEMA,
                "attempt_id": "oversized-current",
                "sequence": 1,
                "updated_at": "2026-07-18T00:00:00+00:00",
                "current_receipt_hash": "A" * 64,
                "current_ref": {
                    "relative_path": (
                        "oversized-current/current.json"
                    ),
                    "sha256": current_raw_hash,
                },
            }
            head = {
                **head_body,
                "head_hash": _canonical_payload_hash(head_body),
            }
            (attempt_root / "HEAD.json").write_text(
                json.dumps(head, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            authority = current_upgrade_attempt_authority(codex_home)

            self.assertFalse(authority["ok"])
            self.assertIn(
                "upgrade-attempt-current-oversized",
                authority["issues"],
            )
            self.assertEqual(
                authority["read_budget"]["history_files_scanned"],
                0,
            )
            self.assertLessEqual(
                authority["read_budget"]["observed_current_bytes"],
                UPGRADE_ATTEMPT_CURRENT_MAX_BYTES + 1,
            )

    def test_update_state_rollback_restores_exact_bytes_or_prior_absence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".local" / "khaos_brain_update_state.json"
            original = b'{"status":"available","old_shape":true}\r\n'
            path.parent.mkdir(parents=True)
            path.write_bytes(original)

            path.write_bytes(b'{"schema_version":1,"status":"failed"}\n')
            _restore_exact_file_snapshot(path, existed=True, content=original)
            self.assertEqual(path.read_bytes(), original)

            _restore_exact_file_snapshot(path, existed=False, content=b"")
            self.assertFalse(path.exists())

    def test_automation_payload_restores_runtime_from_user_pause_intent(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        spec = next(item for item in REPO_AUTOMATION_SPECS if item["id"] == "kb-sleep")

        system_paused = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "PAUSED", "user_paused": False},
        )
        self.assertEqual("ACTIVE", system_paused["status"])
        self.assertFalse(system_paused["user_paused"])

        independently_marked = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "ACTIVE", "user_paused": True},
        )
        self.assertEqual("PAUSED", independently_marked["status"])
        self.assertTrue(independently_marked["user_paused"])

        legacy_paused = _automation_spec_payload(
            spec,
            repo_root,
            existing={"status": "PAUSED"},
        )
        self.assertEqual("PAUSED", legacy_paused["status"])
        self.assertTrue(legacy_paused["user_paused"])

    def test_real_upgrade_wrapper_keeps_pause_until_final_restore_transaction(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            sleep = codex_home / "automations/kb-sleep/automation.toml"
            dream = codex_home / "automations/kb-dream/automation.toml"
            architect = codex_home / "automations/kb-architect/automation.toml"
            for path, status in ((sleep, "ACTIVE"), (dream, "PAUSED"), (architect, "ACTIVE")):
                path.parent.mkdir(parents=True)
                path.write_text(f'status = "{status}"\n', encoding="utf-8")
            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value={"ok": True, "status": "committed", "migration_id": "fixture"},
            ), patch(
                "local_kb.install.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                payload = install_codex_integration(
                    repo_root,
                    codex_home,
                    shell_bin_dir=shell_bin,
                    git_executable=git_real,
                    rg_source=rg_source,
                    persist_user_shell_path=False,
                    run_upgrade_assurance=False,
                )

            self.assertTrue(payload["paused_install_transaction"]["ok"])
            self.assertNotEqual(
                payload["paused_install_transaction"]["transaction_id"],
                payload["install_transaction"]["transaction_id"],
            )
            self.assertEqual(_automation_status(sleep), "ACTIVE")
            self.assertEqual(_automation_status(dream), "PAUSED")
            self.assertFalse(architect.parent.exists())
            self.assertEqual(payload["upgrade_attempt"]["status"], "completed")
            persisted = load_install_state(codex_home)
            current_attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(
                persisted["upgrade_attempt"]["attempt_id"],
                current_attempt["attempt_id"],
            )
            self.assertEqual(
                persisted["upgrade_attempt"]["receipt_hash"],
                current_attempt["receipt_hash"],
            )
            phases = [
                row["phase"]
                for row in payload["upgrade_attempt"]["checkpoint_refs"]
            ]
            self.assertLess(
                phases.index("final_install_transaction_committed"),
                phases.index("final_consumer_projection_current"),
            )
            self.assertNotIn("skillguard_validation_toolchain", payload)
            self.assertNotIn("global_router_live_freshness", payload)
            self.assertIn(
                payload["flowguard_validation_toolchain"]["status"],
                {"frozen", "inherited_frozen"},
            )
            self.assertIn(
                payload["researchguard_logic_validation_toolchain"]["status"],
                {"frozen", "inherited_frozen"},
            )
            self.assertLess(
                phases.index("validation_toolchain_frozen"),
                phases.index("paused_install_transaction_committed"),
            )

    def test_real_upgrade_runs_one_affected_assurance_without_second_migration(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            initial = {
                "ok": True,
                "status": "committed",
                "migration_id": "fixture-initial",
            }
            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value=initial,
            ) as migration, patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                return_value={
                    "schema_version": "khaos-brain.consumer-install-assurance.v2",
                    "ok": True,
                    "status": "passed",
                    "failed_checks": [],
                    "receipt_hash": "sha256:fixture",
                    "execution_count": 1,
                },
            ), patch(
                "local_kb.install.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                payload = install_codex_integration(
                    repo_root,
                    codex_home,
                    shell_bin_dir=shell_bin,
                    git_executable=git_real,
                    rg_source=rg_source,
                    persist_user_shell_path=False,
                )

            self.assertEqual(migration.call_count, 1)
            self.assertEqual(payload["initial_history_migration"], initial)
            self.assertEqual(payload["history_migration"], initial)
            self.assertNotIn("post_assurance_history_migration", payload)
            self.assertNotIn("post_assurance_data_convergence", payload)
            phases = [
                row["phase"] for row in payload["upgrade_attempt"]["checkpoint_refs"]
            ]
            self.assertIn("affected_assurance_stable", phases)
            self.assertNotIn("post_assurance_history_current", phases)

    def test_migration_failure_persists_original_automation_intent_before_work(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            for automation_id in SURVIVING_AUTOMATIONS:
                path = codex_home / "automations" / automation_id / "automation.toml"
                path.parent.mkdir(parents=True)
                path.write_text(
                    'status = "ACTIVE"\nuser_paused = false\n',
                    encoding="utf-8",
                )

            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                side_effect=RuntimeError("fixture migration failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "fixture migration failed"):
                    install_codex_integration(
                        repo_root,
                        codex_home,
                        shell_bin_dir=shell_bin,
                        git_executable=git_real,
                        rg_source=rg_source,
                        persist_user_shell_path=False,
                        run_upgrade_assurance=False,
                    )

            attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(attempt["status"], "failed")
            self.assertEqual(attempt["phase"], "failed_paused_recoverable")
            self.assertEqual(
                set(attempt["automation_state_snapshot"]["states"].values()),
                {"ACTIVE"},
            )
            self.assertEqual(
                set(attempt["automation_state_snapshot"]["user_paused"].values()),
                {False},
            )
            phases = [row["phase"] for row in attempt["checkpoint_refs"]]
            self.assertEqual(phases[0], "automations_paused_migration_pending")
            for automation_id in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation_id / "automation.toml"
                    ),
                    "PAUSED",
                )

    def test_affected_assurance_failure_keeps_survivors_paused(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            initial = {
                "ok": True,
                "status": "committed",
                "migration_id": "fixture-initial",
            }
            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value=initial,
            ), patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                side_effect=RuntimeError(
                    "affected assurance stability limit reached"
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "affected assurance stability limit reached"
                ):
                    install_codex_integration(
                        repo_root,
                        codex_home,
                        shell_bin_dir=shell_bin,
                        git_executable=git_real,
                        rg_source=rg_source,
                        persist_user_shell_path=False,
                    )

            attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(attempt["status"], "failed")
            phases = [row["phase"] for row in attempt["checkpoint_refs"]]
            self.assertNotIn("affected_assurance_stable", phases)
            self.assertNotIn("final_install_transaction_committed", phases)
            for automation_id in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation_id / "automation.toml"
                    ),
                    "PAUSED",
                )

    def test_failed_post_commit_assurance_keeps_old_manifest_and_durable_attempt(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            old_manifest = {"sentinel": "last-known-good"}
            state_path = install_state_path(codex_home)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(old_manifest), encoding="utf-8")
            update_state = root / "obsolete-update-state.json"
            obsolete_update_bytes = (
                b'{"schema_version":1,"status":"failed",'
                b'"error":"SkillGuard installation identity is not current"}\r\n'
            )
            update_state.write_bytes(obsolete_update_bytes)
            migration_calls: list[dict[str, object]] = []

            def migrate_before_assurance(
                _repo_root: Path, *, install_receipt: dict[str, object]
            ) -> dict[str, object]:
                self.assertEqual(install_receipt.get("status"), "committed")
                migration_calls.append(dict(install_receipt))
                update_state.write_text(
                    '{"schema_version":1,"status":"current","error":""}\n',
                    encoding="utf-8",
                )
                return {
                    "ok": True,
                    "status": "committed",
                    "residual_retired_state_count": 0,
                }

            def fail_after_current_state(*_args: object, **_kwargs: object) -> dict:
                self.assertIn('"status":"current"', update_state.read_text(encoding="utf-8"))
                raise RuntimeError("fixture aggregate failure")
            with patch(
                "local_kb.maintenance_migration.run_maintenance_migration",
                return_value={
                    "ok": True,
                    "status": "committed",
                    "migration_id": "fixture",
                },
            ), patch(
                "local_kb.software_update.update_state_path",
                return_value=update_state,
            ), patch(
                "local_kb.software_update.migrate_obsolete_update_state",
                side_effect=migrate_before_assurance,
            ), patch(
                "local_kb.install._run_pre_restore_upgrade_assurance",
                side_effect=fail_after_current_state,
            ):
                with self.assertRaisesRegex(RuntimeError, "fixture aggregate failure"):
                    install_codex_integration(
                        repo_root,
                        codex_home,
                        shell_bin_dir=shell_bin,
                        git_executable=git_real,
                        rg_source=rg_source,
                        persist_user_shell_path=False,
                    )

            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")), old_manifest
            )
            self.assertEqual(len(migration_calls), 1)
            self.assertEqual(update_state.read_bytes(), obsolete_update_bytes)
            attempt = latest_upgrade_attempt(codex_home)
            self.assertEqual(attempt["status"], "failed")
            self.assertEqual(attempt["phase"], "failed_paused_recoverable")
            self.assertEqual(
                set(attempt["automation_state_snapshot"]["states"].values()),
                {"ACTIVE"},
            )
            self.assertEqual(
                set(
                    attempt["automation_state_snapshot"]["user_paused"].values()
                ),
                {False},
            )
            phases = [row["phase"] for row in attempt["checkpoint_refs"]]
            self.assertIn("paused_install_transaction_committed", phases)
            self.assertIn("pre_assurance_consumer_projection_current", phases)
            for automation_id in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation_id / "automation.toml"
                    ),
                    "PAUSED",
                )

    def test_sleep_and_dream_prompts_are_automatic_and_convergent(self) -> None:
        root = Path(__file__).resolve().parents[1]
        sleep = (root / ".agents/skills/local-kb-retrieve/MAINTENANCE_PROMPT.md").read_text(encoding="utf-8")
        dream = (root / ".agents/skills/local-kb-retrieve/DREAM_PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("kb_sleep.py", sleep)
        self.assertIn("exact open `batch_plan`", sleep)
        self.assertIn("`batch_head`", sleep)
        self.assertIn("`batch_checkpoint`", sleep)
        self.assertIn("`progress_saved`", sleep)
        self.assertIn("`previous_remaining`", sleep)
        self.assertIn("`closing_remaining`", sleep)
        self.assertIn("`downstream_stages` as `not_run`", sleep)
        self.assertIn("Do not ask a human", sleep)
        sleep_automation = next(
            item["prompt"] for item in REPO_AUTOMATION_SPECS if item["id"] == "kb-sleep"
        )
        self.assertIn("exact open frozen batch", sleep_automation)
        self.assertIn("progress_saved", sleep_automation)
        self.assertIn("downstream_stages as not_run", sleep_automation)
        self.assertIn("do not invoke kb_lane_status.py", sleep_automation)
        self.assertIn("no_delta_closed", dream)
        self.assertIn("typed idempotent Sleep handoff", dream)
        self.assertIn("Never directly modify cards", dream)

    def test_fixture_install_requires_isolated_shell_tools(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            with self.assertRaisesRegex(RuntimeError, "explicit shell_bin_dir"):
                install_codex_integration(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    persist_user_shell_path=False,
                    run_history_migration=False,
                )

    def test_flowguard_validation_toolchain_is_a_stable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live" / "flowguard"
            live.mkdir(parents=True)
            (live / "__init__.py").write_text(
                "SCHEMA_VERSION = 'test'\n", encoding="utf-8"
            )
            logic = live / "logic"
            logic.mkdir()
            (logic / "__init__.py").write_text(
                "SCHEMA_VERSION = 'researchguard.logic.model-store.v1'\n",
                encoding="utf-8",
            )
            (live / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            destination = root / "receipts" / "python" / "flowguard"
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_FLOWGUARD_VALIDATION_DIGEST": "",
                },
            ):
                receipt = _freeze_flowguard_validation_toolchain(
                    destination, source_root=live
                )
            self.assertEqual(receipt["status"], "frozen")
            self.assertEqual(
                receipt["manifest"]["digest"], tree_manifest(destination)["digest"]
            )
            shutil.rmtree(live)
            self.assertTrue((destination / "__init__.py").is_file())
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                _require_live_flowguard_matches_snapshot(receipt)

    def test_researchguard_logic_validation_toolchain_is_a_stable_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live = root / "live" / "researchguard"
            live.mkdir(parents=True)
            (live / "__init__.py").write_text(
                "SCHEMA_VERSION = 'test'\n", encoding="utf-8"
            )
            logic = live / "logic"
            logic.mkdir()
            (logic / "__init__.py").write_text(
                "SCHEMA_VERSION = 'researchguard.logic.model-store.v1'\n",
                encoding="utf-8",
            )
            (live / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            destination = root / "receipts" / "python" / "researchguard"
            with patch.dict(
                os.environ,
                {
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT": "",
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST": "",
                },
            ):
                receipt = _freeze_researchguard_logic_validation_toolchain(
                    destination, source_root=live
                )
            self.assertEqual(receipt["status"], "frozen")
            self.assertEqual(
                receipt["manifest"]["digest"], tree_manifest(destination)["digest"]
            )
            shutil.rmtree(live)
            self.assertTrue((destination / "__init__.py").is_file())
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                _require_live_researchguard_logic_matches_snapshot(receipt)

    def test_pre_restore_assurance_keeps_baseline_install_identity_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flowguard_root = root / "validation" / "python" / "flowguard"
            flowguard_root.mkdir(parents=True)
            researchguard_root = root / "validation" / "python" / "researchguard"
            researchguard_root.mkdir(parents=True)
            baseline_pythonpath = str(root / "baseline-pythonpath")
            injected_pythonpath = os.pathsep.join(
                (str(flowguard_root.parent), baseline_pythonpath)
            )
            captured: dict[str, object] = {}

            def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
                captured["environment"] = dict(kwargs["env"])
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "schema_version": (
                                "khaos-brain.consumer-install-assurance.v2"
                            ),
                            "ok": True,
                            "receipt_hash": "sha256:fixture",
                        }
                    ),
                    stderr="",
                )

            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": injected_pythonpath,
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_PRESENT": "1",
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE": baseline_pythonpath,
                },
            ), patch("local_kb.install.run_with_timeout_cleanup", side_effect=fake_run):
                result = _run_pre_restore_upgrade_assurance(
                    root,
                    root / ".codex",
                    flowguard_validation_toolchain={
                        "snapshot_root": str(flowguard_root),
                        "manifest": {"digest": "F" * 64},
                    },
                    researchguard_logic_validation_toolchain={
                        "snapshot_root": str(researchguard_root),
                        "manifest": {"digest": "L" * 64},
                    },
                )

            self.assertTrue(result["ok"])
            environment = captured["environment"]
            self.assertEqual(environment["PYTHONPATH"], injected_pythonpath)
            self.assertEqual(
                environment[
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_ROOT"
                ],
                str(researchguard_root),
            )
            self.assertEqual(
                environment[
                    "KHAOS_BRAIN_RESEARCHGUARD_LOGIC_VALIDATION_DIGEST"
                ],
                "L" * 64,
            )
            self.assertEqual(
                environment[
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHONPATH_VALUE"
                ],
                baseline_pythonpath,
            )
            self.assertEqual(
                environment[
                    "KHAOS_BRAIN_INSTALLATION_IDENTITY_PYTHON_EXECUTABLE"
                ],
                sys.executable,
            )

    def test_pre_restore_assurance_failure_reports_owner_terminal_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flowguard_root = root / "validation" / "python" / "flowguard"
            flowguard_root.mkdir(parents=True)
            researchguard_root = root / "validation" / "python" / "researchguard"
            researchguard_root.mkdir(parents=True)
            payload = {
                "schema_version": "khaos-brain.consumer-install-assurance.v2",
                "ok": False,
                "failed_checks": ["full_regression"],
                "owners": {
                    "full_regression": {
                        "terminal_status": "failed",
                        "exit_code": 1,
                        "timed_out": False,
                        "cleanup_confirmed": True,
                        "junit": {
                            "testcase_count": 2,
                            "passed_node_ids": ["tests/test_one.py::test_ok"],
                            "failed_node_ids": ["tests/test_two.py::test_failed"],
                            "errored_node_ids": [],
                            "skipped_node_ids": [],
                            "unparsed_cases": [
                                {"classname": "unexpected.module", "name": "test_unknown"}
                            ],
                            "parse_error": "",
                        },
                        "json_payload": {
                            "checks": [
                                {"id": "fixture-static-owner", "ok": False}
                            ],
                            "skills": {
                                "khaos-brain-update": {
                                    "executed_supervision": {
                                        "scheduled_production": {
                                            "ok": False,
                                            "exit_code": 1,
                                            "status": "blocked",
                                            "blockers": ["fixture-production-block"],
                                        }
                                    }
                                }
                            },
                        },
                        "stdout_tail": "one regression failed",
                        "stderr_tail": "assertion detail",
                    }
                },
            }
            completed = subprocess.CompletedProcess(
                args=["python"],
                returncode=1,
                stdout=json.dumps(payload),
                stderr="outer diagnostic",
            )

            with patch(
                "local_kb.install.run_with_timeout_cleanup",
                return_value=completed,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "unexpected.module",
                ) as raised:
                    _run_pre_restore_upgrade_assurance(
                        root,
                        root / ".codex",
                        flowguard_validation_toolchain={
                            "snapshot_root": str(flowguard_root),
                            "manifest": {"digest": "F" * 64},
                        },
                        researchguard_logic_validation_toolchain={
                            "snapshot_root": str(researchguard_root),
                            "manifest": {"digest": "L" * 64},
                        },
                    )

            message = str(raised.exception)
            self.assertIn('"terminal_status": "failed"', message)
            self.assertIn('"exit_code": 1', message)
            self.assertIn('"passed_count": 1', message)
            self.assertIn("tests/test_two.py::test_failed", message)
            self.assertIn("fixture-static-owner", message)
            self.assertIn("fixture-production-block", message)
            self.assertNotIn("one regression failed", message)

    def test_pre_restore_assurance_reports_model_alignment_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flowguard_root = root / "validation" / "python" / "flowguard"
            flowguard_root.mkdir(parents=True)
            researchguard_root = root / "validation" / "python" / "researchguard"
            researchguard_root.mkdir(parents=True)
            payload = {
                "schema_version": "khaos-brain.consumer-install-assurance.v2",
                "ok": False,
                "failed_checks": ["model_code_test_alignment"],
                "owners": {
                    "model_code_test_alignment": {
                        "terminal_status": "failed",
                        "exit_code": 1,
                        "timed_out": False,
                        "report": {
                            "ok": False,
                            "receipt_findings": ["source_changed_during_leaf_execution"],
                            "alignment": {
                                "decision": "model_test_alignment_blocked",
                                "summary": "one obligation lacks current evidence",
                                "findings": [{"code": "missing_test_evidence"}],
                                "binding_rows": [
                                    {
                                        "model_obligation_id": "req.fixture",
                                        "status": "blocked",
                                        "open_gap_codes": ["missing_test_evidence"],
                                    }
                                ],
                            },
                        },
                    }
                },
            }
            completed = subprocess.CompletedProcess(
                args=["python"],
                returncode=1,
                stdout=json.dumps(payload),
                stderr="",
            )

            with patch(
                "local_kb.install.run_with_timeout_cleanup",
                return_value=completed,
            ), self.assertRaisesRegex(
                RuntimeError,
                "source_changed_during_leaf_execution",
            ) as raised:
                _run_pre_restore_upgrade_assurance(
                    root,
                    root / ".codex",
                    flowguard_validation_toolchain={
                        "snapshot_root": str(flowguard_root),
                        "manifest": {"digest": "F" * 64},
                    },
                    researchguard_logic_validation_toolchain={
                        "snapshot_root": str(researchguard_root),
                        "manifest": {"digest": "L" * 64},
                    },
                )

            message = str(raised.exception)
            self.assertIn("req.fixture", message)
            self.assertIn("missing_test_evidence", message)

    def test_install_is_transactional_current_and_retires_exact_managed_surfaces(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)

            # Model a supported old machine, including exact retired ids and a
            # similarly named user surface that must remain untouched.
            (codex_home / "skills/kb-architect-pass").mkdir(parents=True)
            (codex_home / "skills/kb-architect-pass/SKILL.md").write_text("legacy", encoding="utf-8")
            (codex_home / "automations/kb-architect").mkdir(parents=True)
            (codex_home / "automations/kb-architect/automation.toml").write_text("id='legacy'", encoding="utf-8")
            (codex_home / "automations/khaos-brain-system-update").mkdir(parents=True)
            (codex_home / "automations/khaos-brain-system-update/automation.toml").write_text(
                "id='retired-update'", encoding="utf-8"
            )
            (codex_home / "skills/kb-architect-pass-personal").mkdir(parents=True)
            (codex_home / "skills/kb-architect-pass-personal/keep.txt").write_text("user", encoding="utf-8")
            (codex_home / "automations/khaos-brain-system-update-personal").mkdir(
                parents=True
            )
            (codex_home / "automations/khaos-brain-system-update-personal/keep.txt").write_text(
                "user", encoding="utf-8"
            )

            payload = install_codex_integration(
                repo_root,
                codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )

            self.assertNotIn("skillguard_validation_toolchain", payload)
            self.assertEqual(set(payload["maintenance_skill_names"]), SURVIVING_SKILLS)
            self.assertEqual(set(payload["automation_ids"]), SURVIVING_AUTOMATIONS)
            self.assertEqual(set(MAINTENANCE_SKILL_NAMES), SURVIVING_SKILLS)
            self.assertEqual({item["id"] for item in REPO_AUTOMATION_SPECS}, SURVIVING_AUTOMATIONS)
            self.assertEqual(tuple(payload["retired_skill_ids"]), RETIRED_MAINTENANCE_SKILL_IDS)
            self.assertEqual(tuple(payload["retired_automation_ids"]), RETIRED_AUTOMATION_IDS)
            self.assertFalse((codex_home / "skills/kb-architect-pass").exists())
            self.assertFalse((codex_home / "automations/kb-architect").exists())
            self.assertFalse(
                (codex_home / "automations/khaos-brain-system-update").exists()
            )
            self.assertTrue((codex_home / "skills/kb-architect-pass-personal/keep.txt").exists())
            self.assertTrue(
                (
                    codex_home
                    / "automations/khaos-brain-system-update-personal/keep.txt"
                ).exists()
            )
            for skill_id in SURVIVING_SKILLS:
                installed = codex_home / "skills" / skill_id
                self.assertFalse((installed / ".skillguard").exists())
                for path in installed.rglob("*"):
                    if path.is_file():
                        text = path.read_text(encoding="utf-8", errors="replace").lower()
                        self.assertNotIn("skillguard", text)
                        self.assertNotIn(".skillguard", text)
                        self.assertNotIn("skillguard.py", text)

            persisted = load_install_state(codex_home)
            self.assertEqual(persisted["schema_version"], INSTALL_STATE_SCHEMA)
            self.assertEqual(set(persisted["automation_ids"]), SURVIVING_AUTOMATIONS)
            for automation in persisted["automations"]:
                self.assertIn("user_paused", automation)
                self.assertIn("schedule_policy", automation)
                self.assertIn("model_policy", automation)
                self.assertIn("reasoning_effort_policy", automation)
            update_skill = next(
                item
                for item in persisted["maintenance_skills"]
                if item["name"] == "khaos-brain-update"
            )
            self.assertEqual(update_skill["automation_id"], "")
            self.assertNotIn("skillguard_validation_toolchain", persisted)
            self.assertNotIn("post_install_check", persisted)
            self.assertLess(install_state_path(codex_home).stat().st_size, 1_000_000)

            transaction = payload["install_transaction"]
            self.assertTrue(transaction["ok"])
            self.assertTrue(transaction["receipt_hash"])
            self.assertTrue(Path(transaction["journal_path"]).exists())
            self.assertTrue(Path(transaction["backup_root"]).exists())
            projection_receipts = transaction["consumer_projection_receipts"]
            self.assertTrue(SURVIVING_SKILLS.issubset(projection_receipts))
            for skill in SURVIVING_SKILLS:
                self.assertEqual(
                    projection_receipts[skill]["policy_id"],
                    "khaos-brain.clean-consumer-projection.v1",
                )
                self.assertFalse(projection_receipts[skill]["author_control_present"])
            for skill in SURVIVING_SKILLS:
                root_path = codex_home / "skills" / skill
                self.assertTrue((root_path / "SKILL.md").exists())
                self.assertFalse((root_path / ".skillguard").exists())
            for automation in SURVIVING_AUTOMATIONS:
                self.assertTrue((codex_home / "automations" / automation / "automation.toml").exists())
            self.assertTrue(global_agents_path(codex_home).exists())

            # Codex may normalize the live automation document to its
            # supported keys. Khaos-only metadata remains in the manifest.
            for automation_id in SURVIVING_AUTOMATIONS:
                automation_path = (
                    codex_home / "automations" / automation_id / "automation.toml"
                )
                normalized_lines = [
                    line
                    for line in automation_path.read_text(encoding="utf-8").splitlines()
                    if not line.startswith(
                        (
                            "user_paused = ",
                            "schedule_policy = ",
                            "schedule_window = ",
                            "model_policy = ",
                            "reasoning_effort_policy = ",
                        )
                    )
                ]
                automation_path.write_text(
                    "\n".join(normalized_lines) + "\n",
                    encoding="utf-8",
                )
            check = build_installation_check(repo_root, codex_home)
            self.assertTrue(check["ok"], check["issues"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertTrue(
                checklist["global_skill_postflight_timeout_ownership"]["ok"]
            )
            self.assertTrue(
                checklist["global_agents_postflight_timeout_ownership"]["ok"]
            )
            self.assertTrue(checklist["retired_managed_surfaces"]["ok"])
            self.assertTrue(
                checklist["retired_standalone_logicguard_absent"]["ok"]
            )
            self.assertTrue(checklist["transactional_install_receipt"]["ok"])
            self.assertTrue(checklist["repo_maintenance_skills"]["ok"])
            self.assertTrue(checklist["khaos_brain_system_update_retired"]["ok"])

            with patch(
                "local_kb.logicguard_models.retired_standalone_logicguard_residuals",
                return_value={
                    "schema_version": (
                        "khaos-brain.retired-standalone-logicguard-residuals.v1"
                    ),
                    "ok": False,
                    "distribution": {
                        "present": True,
                        "version": "0.18.0",
                    },
                    "import_resolution": {"present": True},
                    "runtime_modules": ["logicguard"],
                    "issues": [
                        "retired standalone LogicGuard distribution is installed",
                        "retired standalone LogicGuard import origin is resolvable",
                        "retired standalone LogicGuard modules are loaded",
                    ],
                },
            ):
                blocked = build_installation_check(repo_root, codex_home)
            self.assertFalse(blocked["ok"])
            blocked_checklist = {
                item["id"]: item for item in blocked["checklist"]
            }
            self.assertFalse(
                blocked_checklist[
                    "retired_standalone_logicguard_absent"
                ]["ok"]
            )

    def test_reinstall_preserves_pause_state_for_every_surviving_automation(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            kwargs = dict(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )
            install_codex_integration(**kwargs)
            for automation in SURVIVING_AUTOMATIONS:
                path = codex_home / "automations" / automation / "automation.toml"
                text = path.read_text(encoding="utf-8").replace('status = "ACTIVE"', 'status = "PAUSED"')
                text = text.replace("user_paused = false", "user_paused = true")
                path.write_text(text, encoding="utf-8")

            install_codex_integration(**kwargs)
            for automation in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation / "automation.toml"
                    ),
                    "PAUSED",
                )
            self.assertFalse(
                (codex_home / "automations/khaos-brain-system-update").exists()
            )

    def test_reinstall_recovers_system_pause_from_attempt_snapshot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            kwargs = dict(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )
            install_codex_integration(**kwargs)
            for automation in SURVIVING_AUTOMATIONS:
                path = codex_home / "automations" / automation / "automation.toml"
                text = path.read_text(encoding="utf-8").replace(
                    'status = "ACTIVE"',
                    'status = "PAUSED"',
                )
                path.write_text(text, encoding="utf-8")

            install_codex_integration(
                **kwargs,
                automation_state_snapshot={
                    "states": {
                        automation_id: "ACTIVE"
                        for automation_id in SURVIVING_AUTOMATIONS
                    },
                    "user_paused": {
                        automation_id: False
                        for automation_id in SURVIVING_AUTOMATIONS
                    },
                },
            )

            for automation in SURVIVING_AUTOMATIONS:
                self.assertEqual(
                    _automation_status(
                        codex_home / "automations" / automation / "automation.toml"
                    ),
                    "ACTIVE",
                )

    def test_complete_tree_drift_fails_install_check(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            codex_home = root / ".codex"
            shell_bin, git_real, rg_source = _write_fake_tools(root)
            install_codex_integration(
                repo_root,
                codex_home,
                shell_bin_dir=shell_bin,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
                run_history_migration=False,
            )
            target = codex_home / "skills/kb-dream-pass/SKILL.md"
            target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            check = build_installation_check(repo_root, codex_home)
            self.assertFalse(check["ok"])
            self.assertTrue(
                any(
                    "differs from repository source" in item
                    or "differs from the clean consumer projection" in item
                    for item in check["issues"]
                )
            )

    def test_explicit_operator_status_authority_overrides_old_install_snapshot(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            codex_home = Path(tmp) / ".codex"
            states = {automation_id: "ACTIVE" for automation_id in SURVIVING_AUTOMATIONS}
            for automation_id in SURVIVING_AUTOMATIONS:
                path = codex_home / "automations" / automation_id / "automation.toml"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    f'id = "{automation_id}"\nstatus = "ACTIVE"\n',
                    encoding="utf-8",
                )
            check = build_installation_check(
                repo_root,
                codex_home,
                manifest_override={
                    "repo_root": str(repo_root),
                    "installed_automation_statuses": {
                        automation_id: "PAUSED"
                        for automation_id in SURVIVING_AUTOMATIONS
                    },
                },
                automation_status_authority={
                    "ok": True,
                    "status": "test-current-operator-receipt",
                    "issues": [],
                    "states": states,
                },
            )
            status_issues = [
                issue
                for row in check["automation_checks"]
                for issue in row["issues"]
                if "should be status=" in issue
            ]
            self.assertEqual(status_issues, [])
            self.assertEqual(
                check["automation_status_authority"]["states"],
                states,
            )

    def test_organization_automation_times_are_stable_and_windowed(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        by_id = {item["id"]: item for item in REPO_AUTOMATION_SPECS}
        first = automation_rrule_for_spec(by_id["kb-org-contribute"], repo_root)
        second = automation_rrule_for_spec(by_id["kb-org-contribute"], repo_root)
        self.assertEqual(first, second)
        self.assertRegex(first, r"BYHOUR=\d+;BYMINUTE=\d+")


if __name__ == "__main__":
    unittest.main()
