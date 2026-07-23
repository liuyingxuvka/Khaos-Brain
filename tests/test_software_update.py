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
    UPDATE_STATUS_DIVERGED,
    UPDATE_STATUS_FAILED,
    UPDATE_STATUS_LOCAL_AHEAD,
    UPDATE_STATUS_UNAVAILABLE,
    UPDATE_STATUS_UPGRADING,
    check_remote_update,
    is_khaos_brain_ui_process,
    load_update_state,
    manual_update_check,
    mark_update_status,
    migrate_obsolete_update_state,
    save_update_state,
    startup_block_message,
    update_badge_label,
)
from scripts.run_khaos_brain_manual_update import (
    _capture_or_load_snapshot,
    run_manual_update,
)


class SoftwareUpdateStateTests(unittest.TestCase):
    def _repo(self, root: Path, version: str = "0.2.2") -> Path:
        (root / "VERSION").write_text(version, encoding="utf-8")
        return root

    def _write_legacy_state(
        self,
        repo_root: Path,
        *,
        status: str,
        error: str = "",
        schema_version: int | None = 1,
        user_requested: bool = False,
    ) -> Path:
        path = repo_root / ".local" / "khaos_brain_update_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": status,
            "current_version": "0.2.2",
            "latest_version": "0.2.3",
            "current_revision": "old",
            "latest_revision": "new",
            "update_available": status in {"available", "prepared"},
            "user_requested": user_requested,
            "last_checked_at": "",
            "updated_at": "",
            "error": error,
        }
        if schema_version is not None:
            payload["schema_version"] = schema_version
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _write_automation_states(self, codex_home: Path) -> dict[str, str]:
        states = {
            "kb-sleep": "ACTIVE",
            "kb-dream": "PAUSED",
            "kb-org-contribute": "ACTIVE",
            "kb-org-maintenance": "PAUSED",
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
                "migration_id": (
                    "kb-maintenance-standard-v6-resumable-sleep-current-index"
                ),
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
            "retired_automation_ids": ["kb-architect", "khaos-brain-system-update"],
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

    def _run_successful_manual_native(self, repo_root: Path, codex_home: Path, states: dict[str, str]) -> tuple[dict, list[tuple[str, ...]]]:
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
            "scripts.run_khaos_brain_manual_update.manual_update_check",
            return_value={
                "ok": True,
                "apply_ready": True,
                "reason": "explicit-request-and-ui-closed",
                "state": {"latest_revision": "after"},
            },
        ), patch(
            "scripts.run_khaos_brain_manual_update._git",
            side_effect=fake_git,
        ), patch(
            "scripts.run_khaos_brain_manual_update._json_command",
            side_effect=[(0, install, ""), (0, check, "")],
        ), patch(
            "scripts.run_khaos_brain_manual_update.build_installation_check",
            side_effect=[
                {"ok": True, "issues": []},
                {"ok": True, "issues": []},
            ],
        ):
            result = run_manual_update(
                repo_root,
                codex_home,
                explicit_user_request=True,
            )
        return result, git_calls

    def test_update_state_has_no_persisted_authorization_or_prepared_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_AVAILABLE,
                    "latest_version": "0.2.3",
                    "upstream_ref": "origin/main",
                    "behind_count": 1,
                    "update_available": True,
                },
            )

            state = load_update_state(repo_root)
            raw = json.loads((repo_root / ".local" / "khaos_brain_update_state.json").read_text(encoding="utf-8"))

            self.assertEqual(state["status"], UPDATE_STATUS_AVAILABLE)
            self.assertNotIn("user_requested", raw)
            self.assertNotIn("prepared", set(raw.values()))
            self.assertEqual(update_badge_label(state, "zh-CN"), "main · 有新版本 v0.2.3")

    def test_manual_check_waits_when_ui_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_AVAILABLE,
                    "latest_version": "0.2.3",
                    "upstream_ref": "origin/main",
                    "behind_count": 1,
                    "update_available": True,
                },
            )

            result = manual_update_check(
                repo_root,
                explicit_user_request=True,
                check_remote=False,
                ui_processes=[{"Name": "KhaosBrain.exe", "CommandLine": ""}],
            )

            self.assertFalse(result["apply_ready"])
            self.assertEqual(result["reason"], "ui-running")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_AVAILABLE)

    def test_manual_check_marks_upgrading_only_with_explicit_request_and_closed_ui(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_AVAILABLE,
                    "latest_version": "0.2.3",
                    "upstream_ref": "origin/main",
                    "behind_count": 1,
                    "update_available": True,
                },
            )

            result = manual_update_check(
                repo_root,
                explicit_user_request=True,
                check_remote=False,
                ui_processes=[],
            )

            self.assertTrue(result["apply_ready"])
            self.assertEqual(result["reason"], "explicit-request-and-ui-closed")
            self.assertEqual(result["skill"], "$khaos-brain-update")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_UPGRADING)

    def test_manual_check_without_explicit_request_does_not_mutate_or_probe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            save_update_state(
                repo_root,
                {
                    "status": UPDATE_STATUS_AVAILABLE,
                    "latest_version": "0.2.3",
                    "upstream_ref": "origin/main",
                    "behind_count": 1,
                    "update_available": True,
                },
            )
            before = (repo_root / ".local" / "khaos_brain_update_state.json").read_bytes()

            with patch("local_kb.software_update.check_remote_update") as remote, patch(
                "local_kb.software_update.detect_khaos_brain_ui_processes"
            ) as processes:
                result = manual_update_check(
                    repo_root,
                    explicit_user_request=False,
                )

            self.assertFalse(result["apply_ready"])
            self.assertEqual(result["reason"], "explicit-user-request-required")
            self.assertEqual(result["skill"], "")
            remote.assert_not_called()
            processes.assert_not_called()
            self.assertEqual(
                before,
                (repo_root / ".local" / "khaos_brain_update_state.json").read_bytes(),
            )

    def test_native_update_runner_keeps_operational_blockers_unfinished(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir()
            repo_root = self._repo(repo_root)
            codex_home = root / ".codex"
            for reason in ("already-upgrading", "previous-update-failed"):
                with self.subTest(reason=reason), patch(
                    "scripts.run_khaos_brain_manual_update.manual_update_check",
                    return_value={
                        "ok": True,
                        "apply_ready": False,
                        "reason": reason,
                    },
                ), patch(
                    "scripts.run_khaos_brain_manual_update._git"
                ) as git_call:
                    result = run_manual_update(
                        repo_root,
                        codex_home,
                        explicit_user_request=True,
                        run_id=f"blocked-{reason}",
                    )

                self.assertFalse(result["ok"], result)
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["reason"], reason)
                self.assertIn("unfinished", result["error"])
                git_call.assert_not_called()

            with patch(
                "scripts.run_khaos_brain_manual_update.acquire_lane_lock",
                return_value={"ok": True, "acquired": False, "reason": "busy"},
            ):
                concurrent = run_manual_update(
                    repo_root,
                    codex_home,
                    explicit_user_request=True,
                    run_id="blocked-concurrent",
                )

            self.assertFalse(concurrent["ok"], concurrent)
            self.assertEqual(concurrent["status"], "blocked")
            self.assertEqual(concurrent["reason"], "concurrent-update")

    def test_remote_check_classifies_exact_git_topology(self) -> None:
        cases = (
            ((0, 0), UPDATE_STATUS_CURRENT, False),
            ((0, 2), UPDATE_STATUS_AVAILABLE, True),
            ((2, 0), UPDATE_STATUS_LOCAL_AHEAD, False),
            ((1, 3), UPDATE_STATUS_DIVERGED, False),
        )
        for topology, expected_status, expected_available in cases:
            with self.subTest(topology=topology), tempfile.TemporaryDirectory() as tmp:
                repo_root = self._repo(Path(tmp))

                def fake_git_stdout(_repo_root: Path, args: list[str]) -> str:
                    if args == ["rev-parse", "HEAD"]:
                        return "local"
                    if args == ["rev-parse", "origin/topic"]:
                        return "remote"
                    if args == ["show", "origin/topic:VERSION"]:
                        return "0.2.3"
                    return ""

                with patch(
                    "local_kb.software_update._upstream_ref",
                    return_value="origin/topic",
                ), patch(
                    "local_kb.software_update._git_stdout",
                    side_effect=fake_git_stdout,
                ), patch(
                    "local_kb.software_update._topology_counts",
                    return_value=topology,
                ):
                    state = check_remote_update(repo_root, fetch=False)

                self.assertEqual(state["status"], expected_status)
                self.assertEqual(state["update_available"], expected_available)
                self.assertEqual(state["ahead_count"], topology[0])
                self.assertEqual(state["behind_count"], topology[1])
                self.assertEqual(state["upstream_ref"], "origin/topic")

    def test_remote_check_does_not_guess_an_upstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            with patch(
                "local_kb.software_update._upstream_ref",
                return_value="",
            ), patch("local_kb.software_update._run_git") as git_call:
                state = check_remote_update(repo_root, fetch=True)

            self.assertEqual(state["status"], UPDATE_STATUS_UNAVAILABLE)
            self.assertEqual(state["upstream_ref"], "")
            self.assertIn("No configured Git upstream", state["error"])
            self.assertFalse(
                any(call.args[1:2] == ("fetch",) for call in git_call.call_args_list)
            )

    def test_exact_v1_prepared_state_migrates_without_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            path = repo_root / ".local" / "khaos_brain_update_state.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "status": "prepared",
                        "current_version": "0.2.2",
                        "latest_version": "0.2.3",
                        "current_revision": "local",
                        "latest_revision": "remote",
                        "update_available": True,
                        "user_requested": True,
                        "last_checked_at": "2026-07-16T00:00:00+00:00",
                        "updated_at": "2026-07-16T00:00:00+00:00",
                        "error": "",
                    }
                ),
                encoding="utf-8",
            )

            result = migrate_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "R" * 64},
            )
            raw = json.loads(path.read_text(encoding="utf-8"))

            self.assertTrue(result["ok"], result)
            self.assertEqual(raw["schema_version"], 2)
            self.assertEqual(raw["status"], UPDATE_STATUS_AVAILABLE)
            self.assertNotIn("user_requested", raw)
            self.assertEqual(raw["behind_count"], 1)

    def test_normal_reader_rejects_v1_without_compatibility_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = self._repo(Path(tmp))
            path = repo_root / ".local" / "khaos_brain_update_state.json"
            path.parent.mkdir(parents=True)
            path.write_text('{"schema_version": 1, "status": "current"}\n', encoding="utf-8")

            state = load_update_state(repo_root)

            self.assertEqual(state["status"], UPDATE_STATUS_UNAVAILABLE)
            self.assertIn("schema is not current", state["error"])

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
                result = manual_update_check(
                    repo_root,
                    explicit_user_request=True,
                    ui_processes=[],
                )

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

            self.assertEqual(state["status"], UPDATE_STATUS_UNAVAILABLE)
            self.assertEqual(state["current_version"], "0.3.0")
            self.assertEqual(update_badge_label(state), "Upstream · Status unavailable")

    def test_manual_update_refuses_dirty_tracked_work_and_keeps_survivors_paused(self) -> None:
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
                "scripts.run_khaos_brain_manual_update.manual_update_check",
                return_value={
                    "ok": True,
                    "apply_ready": True,
                    "reason": "explicit-request-and-ui-closed",
                    "state": {"latest_revision": "after"},
                },
            ), patch(
                "scripts.run_khaos_brain_manual_update._git",
                return_value=dirty,
            ) as git_call, patch(
                "scripts.run_khaos_brain_manual_update._json_command",
            ) as installer:
                result = run_manual_update(
                    repo_root,
                    codex_home,
                    explicit_user_request=True,
                )
            paused_states = self._automation_statuses(codex_home)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "failed")
        self.assertIn("dirty", result["error"])
        self.assertEqual(git_call.call_count, 1)
        self.assertFalse(installer.called)
        self.assertTrue(all(status == "PAUSED" for status in paused_states.values()))

    def test_manual_update_uses_ff_only_and_closes_natively(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)

            result, git_calls = self._run_successful_manual_native(repo_root, codex_home, states)
            evidence = evaluate_native_payload("khaos-brain-update", result, exit_code=0)
            paused_states = self._automation_statuses(codex_home)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "current-and-restored")
        self.assertTrue(evidence["ok"], evidence)
        self.assertIn(("merge", "--ff-only", "origin/main"), git_calls)
        self.assertFalse(any(call and call[0] in {"reset", "rebase", "checkout"} for call in git_calls))
        self.assertEqual(paused_states, states)
        self.assertEqual(result["update_state"]["status"], UPDATE_STATUS_CURRENT)
        self.assertTrue(result["snapshot_cleanup"]["ok"])

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

    def test_committed_upgrade_directly_settles_exact_retired_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            self._write_legacy_state(
                repo_root,
                status=UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )

            result = migrate_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "current-install"},
            )
            current_state = load_update_state(repo_root)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "committed")
        self.assertEqual(result["residual_retired_state_count"], 0)
        self.assertEqual(current_state["status"], UPDATE_STATUS_UNAVAILABLE)

    def test_obsolete_update_state_requires_a_committed_current_install_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            self._write_legacy_state(
                repo_root,
                status=UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )

            with self.assertRaisesRegex(RuntimeError, "committed current installation receipt"):
                migrate_obsolete_update_state(
                    repo_root,
                    install_receipt={"status": "failed", "receipt_hash": ""},
                )

            current_state = load_update_state(repo_root)

        self.assertEqual(current_state["status"], UPDATE_STATUS_UNAVAILABLE)
        self.assertIn("schema is not current", current_state["error"])

    def test_upgrade_does_not_reinterpret_an_unrelated_update_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="network verification failed",
            )

            result = migrate_obsolete_update_state(
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

        self.assertEqual(state["status"], UPDATE_STATUS_UNAVAILABLE)
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

            migration = migrate_obsolete_update_state(
                repo_root,
                install_receipt={"status": "committed", "receipt_hash": "current-install"},
            )
            state = load_update_state(repo_root)

        self.assertTrue(migration["ok"], migration)
        self.assertEqual(migration["status"], "committed")
        self.assertTrue(migration["legacy_schema_found"])
        self.assertEqual(state["schema_version"], 2)
        self.assertEqual(state["status"], UPDATE_STATUS_AVAILABLE)

    def test_manual_update_restores_status_and_user_pause_independently(self) -> None:
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
            result, _ = self._run_successful_manual_native(
                repo_root, codex_home, states
            )
            restored_statuses = self._automation_statuses(codex_home)
            restored_user_paused = self._automation_user_paused(codex_home)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "current-and-restored")
        self.assertEqual(restored_statuses, states)
        self.assertEqual(restored_user_paused, expected_user_paused)
        self.assertTrue(restored_user_paused["kb-sleep"])

    def test_consumer_assurance_failure_keeps_survivors_paused_and_marks_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo_root = root / "repo"
            repo_root.mkdir(parents=True)
            (repo_root / "VERSION").write_text("0.3.0", encoding="utf-8")
            codex_home = root / ".codex"
            states = self._write_automation_states(codex_home)
            install, _ = self._successful_install_payload(states)
            git_calls: list[tuple[str, ...]] = []

            def fake_git(
                _root: Path, *args: str, timeout: int = 180
            ) -> subprocess.CompletedProcess[str]:
                del timeout
                git_calls.append(tuple(args))
                if args[:2] == ("status", "--porcelain"):
                    return subprocess.CompletedProcess(args, 0, "", "")
                if args[:2] == ("rev-parse", "--abbrev-ref"):
                    return subprocess.CompletedProcess(args, 0, "origin/main\n", "")
                if args == ("rev-parse", "HEAD"):
                    revision = (
                        "after"
                        if any(call[:2] == ("merge", "--ff-only") for call in git_calls)
                        else "before"
                    )
                    return subprocess.CompletedProcess(args, 0, revision + "\n", "")
                if args[:2] == ("merge", "--ff-only"):
                    return subprocess.CompletedProcess(args, 0, "", "")
                return subprocess.CompletedProcess(args, 1, "", "unexpected command")

            with patch(
                "scripts.run_khaos_brain_manual_update.manual_update_check",
                return_value={
                    "ok": True,
                    "apply_ready": True,
                    "reason": "explicit-request-and-ui-closed",
                    "state": {"latest_revision": "after"},
                },
            ), patch(
                "scripts.run_khaos_brain_manual_update._git",
                side_effect=fake_git,
            ), patch(
                "scripts.run_khaos_brain_manual_update._json_command",
                side_effect=[
                    (0, install, ""),
                    (1, {"ok": False, "issues": ["consumer-assurance-failed"]}, ""),
                ],
            ):
                result = run_manual_update(
                    repo_root=repo_root,
                    codex_home=codex_home,
                    explicit_user_request=True,
                )
            paused = self._automation_statuses(codex_home)
            state = load_update_state(repo_root)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(all(status == "PAUSED" for status in paused.values()))
        self.assertEqual(state["status"], UPDATE_STATUS_FAILED)


if __name__ == "__main__":
    unittest.main()
