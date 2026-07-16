from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.automation_runtime import evaluate_native_payload
from local_kb.install import REPO_AUTOMATION_SPECS
from local_kb.software_update import (
    UPDATE_STATUS_AVAILABLE,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_FAILED,
    UPDATE_STATUS_PREPARED,
    UPDATE_STATUS_UPGRADING,
    canonicalize_obsolete_update_state,
    system_update_check,
    check_remote_update,
    is_khaos_brain_ui_process,
    load_update_state,
    mark_update_status,
    save_update_state,
    set_update_request,
    startup_block_message,
    update_badge_clickable,
    update_badge_label,
)
from scripts.run_kb_guarded_automation import run_guarded_automation
from scripts.check_kb_skillguard import _supervision_scope
from scripts.run_khaos_brain_system_update import (
    _capture_or_load_snapshot,
    run_prepared_update,
)


class SoftwareUpdateStateTests(unittest.TestCase):
    def setUp(self) -> None:
        def identity(_codex_home: Path, **kwargs: object) -> dict:
            return {
                "scheduler_or_trigger_id": str(
                    kwargs.get("scheduler_or_trigger_id") or "test-trigger"
                ),
                "scheduled_execution_id": str(
                    kwargs.get("scheduled_execution_id") or "test-run"
                ),
                "installation_receipt_id": "install-1",
                "installation_receipt_hash": "A" * 64,
                "installation_receipt_root_ref": {
                    "path_token": "active_skill_root",
                    "relative_path": ".sg-runtime/installation",
                },
                "installed_runtime_fingerprint": "B" * 64,
            }

        self._scheduled_identity_patch = patch(
            "scripts.run_kb_guarded_automation._build_current_scheduled_production_identity",
            side_effect=identity,
        )
        self._scheduled_identity_patch.start()
        self.addCleanup(self._scheduled_identity_patch.stop)

    def _repo(self, root: Path, version: str = "0.2.2") -> Path:
        (root / "VERSION").write_text(version, encoding="utf-8")
        return root

    def _write_automation_states(self, codex_home: Path) -> dict[str, str]:
        states = {
            "kb-sleep": "ACTIVE",
            "kb-dream": "PAUSED",
            "kb-org-contribute": "ACTIVE",
            "kb-org-maintenance": "PAUSED",
            "khaos-brain-system-update": "ACTIVE",
        }
        for automation_id, status in states.items():
            path = codex_home / "automations" / automation_id / "automation.toml"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                f'status = "{status}"\n'
                f"user_paused = {'true' if status == 'PAUSED' else 'false'}\n",
                encoding="utf-8",
            )
        return states

    def _automation_statuses(self, codex_home: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for spec in REPO_AUTOMATION_SPECS:
            automation_id = str(spec["id"])
            path = codex_home / "automations" / automation_id / "automation.toml"
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            result[automation_id] = "PAUSED" if 'status = "PAUSED"' in text else "ACTIVE" if 'status = "ACTIVE"' in text else ""
        return result

    def _automation_user_paused(self, codex_home: Path) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for spec in REPO_AUTOMATION_SPECS:
            automation_id = str(spec["id"])
            path = codex_home / "automations" / automation_id / "automation.toml"
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
            result[automation_id] = "user_paused = true" in text
        return result

    def _successful_install_payload(self, states: dict[str, str]) -> tuple[dict, dict]:
        install = {
            "paused_install_transaction": {
                "ok": True,
                "transaction_id": "pause-tx",
                "receipt_hash": "pause-hash",
            },
            "install_transaction": {
                "ok": True,
                "transaction_id": "restore-tx",
                "receipt_hash": "restore-hash",
            },
            "history_migration": {
                "ok": True,
                "status": "current",
                "migration_id": "kb-maintenance-standard-v4-logicguard-native",
                "validation": {
                    "ok": True,
                    "residual_managed_file_count": 0,
                    "logicguard_authority": {
                        "ok": True,
                        "generation_id": "generation-test-current",
                        "zero_legacy_projection_residuals": True,
                    },
                },
            },
            "upgrade_assurance": {"ok": True},
            "automation_restore_deferred": True,
            "retired_skill_ids": ["kb-architect-pass"],
            "retired_automation_ids": ["kb-architect"],
            "automations": [
                {"id": automation_id, "status": status}
                for automation_id, status in states.items()
            ],
        }
        check = {
            "ok": True,
            "automation_restore_deferred": True,
            "deferred_automation_restore_allowed": True,
            "install_transaction": {
                "status": "committed",
                "transaction_id": "restore-tx",
                "receipt_hash": "restore-hash",
            },
        }
        return install, check

    def _run_successful_prepared_native(self, repo_root: Path, codex_home: Path, states: dict[str, str]) -> tuple[dict, list[tuple[str, ...]]]:
        git_calls: list[tuple[str, ...]] = []

        def fake_git(_root: Path, *args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
            git_calls.append(tuple(args))
            if args[:2] == ("status", "--porcelain"):
                return subprocess.CompletedProcess(args, 0, "", "")
            if args[:2] == ("rev-parse", "--abbrev-ref"):
                return subprocess.CompletedProcess(args, 0, "origin/main\n", "")
            if args == ("rev-parse", "HEAD"):
                revision = "after" if any(call[:2] == ("merge", "--ff-only") for call in git_calls) else "before"
                return subprocess.CompletedProcess(args, 0, revision + "\n", "")
            if args[:2] == ("merge", "--ff-only"):
                return subprocess.CompletedProcess(args, 0, "", "")
            return subprocess.CompletedProcess(args, 1, "", "unexpected git command")

        install, check = self._successful_install_payload(states)
        with patch(
            "scripts.run_khaos_brain_system_update.system_update_check",
            return_value={
                "ok": True,
                "apply_ready": True,
                "reason": "prepared-and-ui-closed",
                "state": {"latest_revision": "after"},
            },
        ), patch(
            "scripts.run_khaos_brain_system_update._git",
            side_effect=fake_git,
        ), patch(
            "scripts.run_khaos_brain_system_update._json_command",
            side_effect=[(0, install, ""), (0, check, "")],
        ):
            result = run_prepared_update(repo_root, codex_home)
        return result, git_calls

    def test_update_request_toggles_available_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_AVAILABLE,
                    "latest_version": "0.2.3",
                    "update_available": True,
                },
            )

            prepared = set_update_request(repo_root, True)
            self.assertEqual(prepared["status"], UPDATE_STATUS_PREPARED)
            self.assertTrue(prepared["user_requested"])
            self.assertEqual(update_badge_label(prepared, "zh-CN"), "准备升级 v0.2.3")

            available = set_update_request(repo_root, False)
            self.assertEqual(available["status"], UPDATE_STATUS_AVAILABLE)
            self.assertFalse(available["user_requested"])
            self.assertEqual(update_badge_label(available, "zh-CN"), "可升级 v0.2.3")

    def test_system_check_waits_when_ui_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_PREPARED,
                    "latest_version": "0.2.3",
                    "update_available": True,
                    "user_requested": True,
                },
            )

            result = system_update_check(
                repo_root,
                check_remote=False,
                ui_processes=[{"Name": "KhaosBrain.exe", "CommandLine": ""}],
            )

            self.assertFalse(result["apply_ready"])
            self.assertEqual(result["reason"], "ui-running")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_PREPARED)

    def test_system_check_marks_upgrading_when_prepared_and_ui_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_PREPARED,
                    "latest_version": "0.2.3",
                    "update_available": True,
                    "user_requested": True,
                },
            )

            result = system_update_check(repo_root, check_remote=False, ui_processes=[])

            self.assertTrue(result["apply_ready"])
            self.assertEqual(result["reason"], "prepared-and-ui-closed")
            self.assertEqual(result["skill"], "$khaos-brain-update")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_UPGRADING)

    def test_failed_update_waits_for_user_before_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_FAILED,
                    "latest_version": "0.2.3",
                    "update_available": True,
                    "user_requested": True,
                    "error": "previous update failed",
                },
            )

            result = system_update_check(repo_root, check_remote=False, ui_processes=[])
            state = load_update_state(repo_root)

            self.assertFalse(result["apply_ready"])
            self.assertEqual(result["reason"], "failed-awaiting-user")
            self.assertEqual(result["skill"], "")
            self.assertEqual(state["status"], UPDATE_STATUS_FAILED)
            self.assertFalse(state["user_requested"])
            self.assertTrue(update_badge_clickable(state))

            prepared = set_update_request(repo_root, True)
            self.assertEqual(prepared["status"], UPDATE_STATUS_PREPARED)
            self.assertTrue(prepared["user_requested"])

    def test_native_update_runner_keeps_operational_blockers_unfinished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir()
            repo_root = self._repo(repo_root)
            codex_home = root / ".codex"
            for reason in ("already-upgrading", "failed-awaiting-user"):
                with self.subTest(reason=reason), patch(
                    "scripts.run_khaos_brain_system_update.system_update_check",
                    return_value={
                        "ok": True,
                        "apply_ready": False,
                        "reason": reason,
                    },
                ), patch(
                    "scripts.run_khaos_brain_system_update._git"
                ) as git_call:
                    result = run_prepared_update(
                        repo_root,
                        codex_home,
                        run_id=f"blocked-{reason}",
                    )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason"], reason)
                self.assertIn("unfinished", result["error"])
                git_call.assert_not_called()

            with patch(
                "scripts.run_khaos_brain_system_update.acquire_lane_lock",
                return_value={"ok": True, "acquired": False, "reason": "busy"},
            ):
                concurrent = run_prepared_update(
                    repo_root,
                    codex_home,
                    run_id="blocked-concurrent",
                )

            self.assertFalse(concurrent["ok"], concurrent)
            self.assertEqual(concurrent["status"], "blocked")
            self.assertEqual(concurrent["reason"], "concurrent-update")

    def test_remote_check_keeps_same_failed_target_failed_until_user_reprepares(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_FAILED,
                    "latest_version": "0.2.3",
                    "current_revision": "local",
                    "latest_revision": "remote",
                    "update_available": True,
                    "user_requested": True,
                    "error": "previous update failed",
                },
            )

            def fake_git_stdout(_repo_root: Path, args: list[str]) -> str:
                if args == ["rev-parse", "HEAD"]:
                    return "local"
                if args == ["rev-parse", "origin/main"]:
                    return "remote"
                if args == ["show", "origin/main:VERSION"]:
                    return "0.2.3"
                return ""

            with (
                patch("local_kb.software_update._upstream_ref", return_value="origin/main"),
                patch("local_kb.software_update._git_stdout", side_effect=fake_git_stdout),
            ):
                state = check_remote_update(repo_root, fetch=False)

            self.assertEqual(state["status"], UPDATE_STATUS_FAILED)
            self.assertFalse(state["user_requested"])
            self.assertEqual(state["error"], "previous update failed")

            prepared = set_update_request(repo_root, True)
            self.assertEqual(prepared["status"], UPDATE_STATUS_PREPARED)

    def test_remote_check_new_target_after_failed_update_requires_fresh_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_FAILED,
                    "latest_version": "0.2.3",
                    "current_revision": "local",
                    "latest_revision": "remote-old",
                    "update_available": True,
                    "user_requested": True,
                    "error": "previous update failed",
                },
            )

            def fake_git_stdout(_repo_root: Path, args: list[str]) -> str:
                if args == ["rev-parse", "HEAD"]:
                    return "local"
                if args == ["rev-parse", "origin/main"]:
                    return "remote-new"
                if args == ["show", "origin/main:VERSION"]:
                    return "0.2.4"
                return ""

            with (
                patch("local_kb.software_update._upstream_ref", return_value="origin/main"),
                patch("local_kb.software_update._git_stdout", side_effect=fake_git_stdout),
            ):
                state = check_remote_update(repo_root, fetch=False)

            self.assertEqual(state["status"], UPDATE_STATUS_AVAILABLE)
            self.assertFalse(state["user_requested"])
            self.assertEqual(state["latest_revision"], "remote-new")

    def test_remote_check_keeps_failed_when_local_already_equals_failed_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp), "0.2.3")
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_FAILED,
                    "latest_version": "0.2.3",
                    "current_revision": "same-revision",
                    "latest_revision": "same-revision",
                    "update_available": True,
                    "user_requested": True,
                    "error": "final SkillGuard closure failed",
                },
            )

            def fake_git_stdout(_repo_root: Path, args: list[str]) -> str:
                if args in (["rev-parse", "HEAD"], ["rev-parse", "origin/main"]):
                    return "same-revision"
                if args == ["show", "origin/main:VERSION"]:
                    return "0.2.3"
                return ""

            with patch(
                "local_kb.software_update._upstream_ref",
                return_value="origin/main",
            ), patch(
                "local_kb.software_update._git_stdout",
                side_effect=fake_git_stdout,
            ):
                state = check_remote_update(repo_root, fetch=False)

            self.assertEqual(state["status"], UPDATE_STATUS_FAILED)
            self.assertFalse(state["user_requested"])
            self.assertEqual(state["error"], "final SkillGuard closure failed")

    def test_prepared_revision_change_requires_fresh_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_PREPARED,
                    "latest_version": "0.2.3",
                    "current_revision": "local",
                    "latest_revision": "remote-a",
                    "update_available": True,
                    "user_requested": True,
                },
            )

            def fake_git_stdout(_repo_root: Path, args: list[str]) -> str:
                if args == ["rev-parse", "HEAD"]:
                    return "local"
                if args == ["rev-parse", "origin/main"]:
                    return "remote-b"
                if args == ["show", "origin/main:VERSION"]:
                    return "0.2.4"
                return ""

            with patch("local_kb.software_update._upstream_ref", return_value="origin/main"), patch(
                "local_kb.software_update._git_stdout",
                side_effect=fake_git_stdout,
            ):
                state = check_remote_update(repo_root, fetch=False)

        self.assertTrue(state["prepared_target_changed"], state)
        self.assertEqual(state["status"], UPDATE_STATUS_AVAILABLE)
        self.assertFalse(state["user_requested"])
        self.assertEqual(state["latest_revision"], "remote-b")

    def test_remote_fetch_failure_is_not_reported_as_no_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            failed_fetch = subprocess.CompletedProcess(
                args=["git", "fetch"],
                returncode=1,
                stdout="",
                stderr="network unavailable",
            )
            with patch("local_kb.software_update._upstream_ref", return_value="origin/main"), patch(
                "local_kb.software_update._run_git",
                return_value=failed_fetch,
            ), patch(
                "local_kb.software_update._git_stdout",
                return_value="",
            ):
                result = system_update_check(repo_root, ui_processes=[])

        self.assertFalse(result["ok"], result)
        self.assertFalse(result["apply_ready"])
        self.assertEqual(result["reason"], "remote-check-failed")

    def test_startup_block_message_only_when_upgrading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            self.assertEqual(startup_block_message(repo_root, language="zh-CN"), "")

            mark_update_status(repo_root, UPDATE_STATUS_UPGRADING)

            self.assertIn("正在升级", startup_block_message(repo_root, language="zh-CN"))
            self.assertIn("updating", startup_block_message(repo_root, language="en").lower())

    def test_process_detection_targets_only_desktop_ui(self) -> None:
        self.assertTrue(is_khaos_brain_ui_process({"Name": "KhaosBrain.exe"}))
        self.assertTrue(is_khaos_brain_ui_process({"CommandLine": "python scripts/kb_desktop.py --repo-root ."}))
        self.assertFalse(is_khaos_brain_ui_process({"CommandLine": "python scripts/khaos_brain_update.py --status"}))
        self.assertFalse(is_khaos_brain_ui_process({"Name": "python.exe", "CommandLine": "python other.py"}))

    def test_absent_state_defaults_to_current_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp), "0.3.0")

            state = load_update_state(repo_root)

            self.assertEqual(state["status"], UPDATE_STATUS_CURRENT)
            self.assertEqual(state["current_version"], "0.3.0")
            self.assertEqual(update_badge_label(state), "v0.3.0")

    def test_prepared_update_refuses_dirty_tracked_work_and_keeps_survivors_paused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            self._write_automation_states(codex_home)
            dirty = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout=" M user-work.py\n",
                stderr="",
            )
            with patch(
                "scripts.run_khaos_brain_system_update.system_update_check",
                return_value={
                    "ok": True,
                    "apply_ready": True,
                    "reason": "prepared-and-ui-closed",
                    "state": {"latest_revision": "after"},
                },
            ), patch(
                "scripts.run_khaos_brain_system_update._git",
                return_value=dirty,
            ) as git_call, patch(
                "scripts.run_khaos_brain_system_update._json_command",
            ) as installer:
                result = run_prepared_update(repo_root, codex_home)
            paused_states = self._automation_statuses(codex_home)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("dirty", result["error"])
        self.assertEqual(git_call.call_count, 1)
        self.assertFalse(installer.called)
        self.assertTrue(all(status == "PAUSED" for status in paused_states.values()))

    def test_prepared_update_uses_only_ff_only_and_waits_for_skillguard_before_current(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)

            result, git_calls = self._run_successful_prepared_native(repo_root, codex_home, states)
            evidence = evaluate_native_payload("khaos-brain-update", result, exit_code=0)
            paused_states = self._automation_statuses(codex_home)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "awaiting-skillguard")
        self.assertTrue(evidence["ok"], evidence)
        self.assertIn(("merge", "--ff-only", "origin/main"), git_calls)
        self.assertFalse(any(call and call[0] in {"reset", "rebase", "checkout"} for call in git_calls))
        self.assertTrue(all(status == "PAUSED" for status in paused_states.values()))

    def test_update_snapshot_is_not_reused_for_a_different_target_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            codex_home = root / ".codex"
            self._write_automation_states(codex_home)

            first = _capture_or_load_snapshot(
                repo_root,
                codex_home,
                target_revision="target-a",
                source_revision="source-a",
                run_id="run-a",
            )
            for spec in REPO_AUTOMATION_SPECS:
                path = (
                    codex_home
                    / "automations"
                    / str(spec["id"])
                    / "automation.toml"
                )
                path.write_text(
                    'status = "PAUSED"\nuser_paused = true\n',
                    encoding="utf-8",
                )
            second = _capture_or_load_snapshot(
                repo_root,
                codex_home,
                target_revision="target-b",
                source_revision="source-b",
                run_id="run-b",
            )

        self.assertFalse(first["reused"])
        self.assertFalse(second["reused"])
        self.assertEqual(second["target_revision"], "target-b")
        self.assertEqual(second["capture_run_id"], "run-b")
        self.assertTrue(all(value == "PAUSED" for value in second["states"].values()))
        self.assertNotEqual(first["snapshot_hash"], second["snapshot_hash"])

    def test_update_guarded_runner_restores_only_after_skillguard_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            native_payload, _ = self._run_successful_prepared_native(repo_root, codex_home, states)
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)
            mark_update_status(repo_root, UPDATE_STATUS_UPGRADING)
            def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                rebound = {**native_payload, "run_id": run_id}
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps(rebound),
                    stderr="",
                )
            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": True, "validation": {"depth_passed": True}},
            ), patch(
                "scripts.run_kb_guarded_automation.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            restored = self._automation_statuses(codex_home)
            state = load_update_state(repo_root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["update_finalization"]["status"], "current-and-restored")
        self.assertEqual(restored, states)
        self.assertEqual(state["status"], UPDATE_STATUS_CURRENT)

    def test_update_noop_requires_enforced_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            codex_home = root / ".codex"
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

            def completed_for(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                payload = {
                    "run_id": run_id,
                    "status": "no-op",
                    "reason": "no-update",
                    "system_check": {
                        "ok": True,
                        "apply_ready": False,
                        "reason": "no-update",
                    },
                    "terminal_gate": {
                        "gate_id": "system-update-check",
                        "evaluated": True,
                        "applicable": False,
                        "reason": "no-update",
                    },
                }
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps(payload),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": True, "profile": "enforced"},
            ) as supervise:
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "no-op-completed")
        self.assertEqual(supervise.call_count, 1)
        self.assertEqual(supervise.call_args.kwargs["supervision_stage"], "no-op")
        scope = _supervision_scope("khaos-brain-update", "no-op")
        self.assertEqual(scope["profile"], "enforced")
        self.assertEqual(scope["route_ids"], ["route:khaos-brain-update:authorize"])

    def test_scheduled_runtime_does_not_repair_retired_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            codex_home = root / ".codex"
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )

            def completed_for(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "run_id": run_id,
                            "status": "no-op",
                            "reason": "no-update",
                            "system_check": {
                                "ok": True,
                                "apply_ready": False,
                                "reason": "no-update",
                            },
                            "terminal_gate": {
                                "gate_id": "system-update-check",
                                "evaluated": True,
                                "applicable": False,
                                "reason": "no-update",
                            },
                        }
                    ),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation._build_current_scheduled_production_identity",
                return_value={
                    "installation_receipt_id": "install-current",
                    "installation_receipt_hash": "receipt-current",
                    "installed_runtime_fingerprint": "runtime-current",
                    "installation_receipt_root_ref": {
                        "path_token": "active_skill_root",
                        "relative_path": ".sg-runtime/installation",
                    },
                    "scheduler_or_trigger_id": "automation:khaos-brain-update",
                    "scheduled_execution_id": "placeholder",
                },
            ), patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": True, "profile": "enforced"},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            state_after = load_update_state(repo_root)

        self.assertTrue(result["ok"], result)
        self.assertNotIn("recovered_update_identity_failure", result)
        self.assertEqual(state_after["status"], UPDATE_STATUS_FAILED)
        self.assertEqual(
            state_after["error"],
            "SkillGuard installation identity is not current",
        )

    def test_committed_upgrade_directly_settles_exact_retired_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )

            result = canonicalize_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "current-install"},
            )
            current_state = load_update_state(repo_root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["residual_retired_state_count"], 0)
        self.assertEqual(current_state["status"], UPDATE_STATUS_CURRENT)

    def test_obsolete_update_state_requires_a_committed_current_install_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )

            with self.assertRaisesRegex(RuntimeError, "committed current installation receipt"):
                canonicalize_obsolete_update_state(
                    repo_root,
                    install_receipt={"status": "failed", "receipt_hash": ""},
                )

            current_state = load_update_state(repo_root)

        self.assertEqual(current_state["status"], UPDATE_STATUS_FAILED)
        self.assertEqual(current_state["error"], "SkillGuard installation identity is not current")

    def test_upgrade_does_not_reinterpret_an_unrelated_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="network verification failed",
            )

            result = canonicalize_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "current-install"},
            )
            current_state = load_update_state(repo_root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "no_delta")
        self.assertEqual(current_state["status"], UPDATE_STATUS_FAILED)
        self.assertEqual(current_state["error"], "network verification failed")

    def test_daily_update_reader_rejects_a_pre_schema_state_visibly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            path = repo_root / ".local" / "khaos_brain_update_state.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"status": UPDATE_STATUS_AVAILABLE, "update_available": True}),
                encoding="utf-8",
            )

            state = load_update_state(repo_root)

        self.assertEqual(state["status"], UPDATE_STATUS_FAILED)
        self.assertIn("Update state is not current", state["error"])

    def test_upgrade_directly_rewrites_a_pre_schema_update_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            path = repo_root / ".local" / "khaos_brain_update_state.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "status": UPDATE_STATUS_AVAILABLE,
                        "current_version": "0.1.0",
                        "latest_version": "0.2.0",
                        "current_revision": "old",
                        "latest_revision": "new",
                        "update_available": True,
                        "user_requested": False,
                        "last_checked_at": "",
                        "updated_at": "",
                        "error": "",
                    }
                ),
                encoding="utf-8",
            )

            migration = canonicalize_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "current-install"},
            )
            state = load_update_state(repo_root)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertTrue(migration["retired_schema_found"])
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["status"], UPDATE_STATUS_AVAILABLE)

    def test_update_noop_does_not_close_when_enforced_supervision_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            codex_home = root / ".codex"
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

            def completed_for(
                command: list[str], **_: object
            ) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps(
                        {
                            "run_id": run_id,
                            "status": "no-op",
                            "reason": "no-update",
                            "system_check": {
                                "ok": True,
                                "apply_ready": False,
                                "reason": "no-update",
                            },
                            "terminal_gate": {
                                "gate_id": "system-update-check",
                                "evaluated": True,
                                "applicable": False,
                                "reason": "no-update",
                            },
                        }
                    ),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": False, "profile": "enforced"},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "skillguard-blocked")

    def test_guarded_update_rejects_operational_blockers_before_skillguard(self) -> None:
        for reason in (
            "already-upgrading",
            "failed-awaiting-user",
            "concurrent-update",
        ):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo_root = root / "repo"
                repo_root.mkdir(parents=True)
                codex_home = root / ".codex"
                (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

                def completed_for(
                    command: list[str], **_: object
                ) -> subprocess.CompletedProcess[str]:
                    run_id = command[command.index("--run-id") + 1]
                    payload = {
                        "ok": False,
                        "run_id": run_id,
                        "status": "blocked",
                        "reason": reason,
                        "system_check": {
                            "ok": True,
                            "apply_ready": False,
                            "reason": reason,
                        },
                        "terminal_gate": {
                            "gate_id": "system-update-check",
                            "evaluated": True,
                            "applicable": False,
                            "reason": reason,
                        },
                    }
                    return subprocess.CompletedProcess(
                        args=command,
                        returncode=1,
                        stdout=json.dumps(payload),
                        stderr="",
                    )

                with patch(
                    "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                    side_effect=completed_for,
                ), patch(
                    "scripts.run_kb_guarded_automation._execute_supervision",
                ) as supervise:
                    result = run_guarded_automation(
                        "khaos-brain-update",
                        repo_root=repo_root,
                        codex_home=codex_home,
                    )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "native-failed")
                supervise.assert_not_called()

    def test_update_guarded_runner_preserves_status_and_user_pause_independently(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            sleep_path = codex_home / "automations" / "kb-sleep" / "automation.toml"
            sleep_path.write_text(
                'status = "ACTIVE"\nuser_paused = true\n',
                encoding="utf-8",
            )
            expected_user_paused = self._automation_user_paused(codex_home)
            native_payload, _ = self._run_successful_prepared_native(
                repo_root, codex_home, states
            )
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

            def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps({**native_payload, "run_id": run_id}),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": True, "validation": {"depth_passed": True}},
            ), patch(
                "scripts.run_kb_guarded_automation.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            restored_statuses = self._automation_statuses(codex_home)
            restored_user_paused = self._automation_user_paused(codex_home)

        self.assertTrue(result["ok"], result)
        self.assertEqual(restored_statuses, states)
        self.assertEqual(restored_user_paused, expected_user_paused)
        self.assertTrue(restored_user_paused["kb-sleep"])

    def test_update_final_skillguard_failure_repauses_every_survivor_and_marks_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            native_payload, _ = self._run_successful_prepared_native(
                repo_root, codex_home, states
            )
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

            def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps({**native_payload, "run_id": run_id}),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                side_effect=[
                    {"ok": True, "validation": {"depth_passed": True}},
                    {"ok": False, "validation": {"depth_passed": False}},
                ],
            ) as supervise, patch(
                "scripts.run_kb_guarded_automation.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            paused = self._automation_statuses(codex_home)
            state = load_update_state(repo_root)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "update-final-skillguard-blocked")
        self.assertEqual(supervise.call_count, 2)
        self.assertTrue(all(status == "PAUSED" for status in paused.values()))
        self.assertEqual(state["status"], UPDATE_STATUS_FAILED)

    def test_update_restoration_failure_stops_before_final_skillguard_and_repauses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            native_payload, _ = self._run_successful_prepared_native(
                repo_root, codex_home, states
            )
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)

            def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps({**native_payload, "run_id": run_id}),
                    stderr="",
                )

            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": True, "validation": {"depth_passed": True}},
            ) as supervise, patch(
                "scripts.run_kb_guarded_automation.apply_repo_automation_restoration_plan",
                return_value={
                    "ok": False,
                    "restored": {},
                    "restored_user_paused": {},
                    "issues": ["simulated restore failure"],
                },
            ), patch(
                "scripts.run_kb_guarded_automation.build_installation_check",
                return_value={"ok": True, "issues": []},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            paused = self._automation_statuses(codex_home)
            state = load_update_state(repo_root)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "update-activation-failed")
        self.assertEqual(supervise.call_count, 2)
        self.assertTrue(all(status == "PAUSED" for status in paused.values()))
        self.assertEqual(state["status"], UPDATE_STATUS_FAILED)

    def test_update_skillguard_failure_keeps_survivors_paused_and_marks_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            native_payload, _ = self._run_successful_prepared_native(repo_root, codex_home, states)
            (codex_home / "skills" / "khaos-brain-update").mkdir(parents=True)
            def completed_for(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
                run_id = command[command.index("--run-id") + 1]
                rebound = {**native_payload, "run_id": run_id}
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=0,
                    stdout=json.dumps(rebound),
                    stderr="",
                )
            with patch(
                "scripts.run_kb_guarded_automation.run_with_timeout_cleanup",
                side_effect=completed_for,
            ), patch(
                "scripts.run_kb_guarded_automation._execute_supervision",
                return_value={"ok": False, "validation": {"depth_passed": False}},
            ):
                result = run_guarded_automation(
                    "khaos-brain-update",
                    repo_root=repo_root,
                    codex_home=codex_home,
                )
            paused = self._automation_statuses(codex_home)
            state = load_update_state(repo_root)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "skillguard-blocked")
        self.assertTrue(all(status == "PAUSED" for status in paused.values()))
        self.assertEqual(state["status"], UPDATE_STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
