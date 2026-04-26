from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.software_update import (
    UPDATE_STATUS_AVAILABLE,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_PREPARED,
    UPDATE_STATUS_UPGRADING,
    architect_update_check,
    is_khaos_brain_ui_process,
    load_update_state,
    mark_update_status,
    save_update_state,
    set_update_request,
    startup_block_message,
    update_badge_label,
)


class SoftwareUpdateStateTests(unittest.TestCase):
    def _repo(self, root: Path, version: str = "0.2.2") -> Path:
        (root / "VERSION").write_text(version, encoding="utf-8")
        return root

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

    def test_architect_check_waits_when_ui_is_running(self) -> None:
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

            result = architect_update_check(
                repo_root,
                check_remote=False,
                ui_processes=[{"Name": "KhaosBrain.exe", "CommandLine": ""}],
            )

            self.assertFalse(result["apply_ready"])
            self.assertEqual(result["reason"], "ui-running")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_PREPARED)

    def test_architect_check_marks_upgrading_when_prepared_and_ui_closed(self) -> None:
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

            result = architect_update_check(repo_root, check_remote=False, ui_processes=[])

            self.assertTrue(result["apply_ready"])
            self.assertEqual(result["reason"], "prepared-and-ui-closed")
            self.assertEqual(result["skill"], "$khaos-brain-update")
            self.assertEqual(load_update_state(repo_root)["status"], UPDATE_STATUS_UPGRADING)

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


if __name__ == "__main__":
    unittest.main()
