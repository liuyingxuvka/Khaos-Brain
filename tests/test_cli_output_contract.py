from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.cli_output import machine_json_text
from scripts.install_codex_kb import (
    _install_result_projection,
    _installation_check_result_projection,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliOutputContractTests(unittest.TestCase):
    def run_json(
        self,
        args: list[str],
        *,
        encoding: str,
        extra_env: dict[str, str] | None = None,
    ) -> object:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = encoding
        env["CODEX_PREDICTIVE_KB_ROOT"] = str(REPO_ROOT)
        env["CODEX_KB_AUTOMATION_MODEL"] = "test-current-model"
        env["CODEX_KB_AUTOMATION_REASONING_EFFORT"] = "high"
        env.update(extra_env or {})
        completed = subprocess.run(
            [sys.executable, *args],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"command failed under {encoding}: {args}\nstdout={completed.stdout}\nstderr={completed.stderr}",
        )
        return json.loads(completed.stdout)

    def test_machine_json_round_trips_unicode_as_ascii_text(self) -> None:
        text = machine_json_text({"title": "中文显示", "route": ["system", "knowledge-library"]})

        text.encode("ascii")
        self.assertEqual(json.loads(text)["title"], "中文显示")

    def test_search_json_is_safe_under_hostile_console_encodings(self) -> None:
        for encoding in ("ascii", "cp1252", "cp936"):
            payload = self.run_json(
                [
                    ".agents/skills/local-kb-retrieve/scripts/kb_search.py",
                    "--query",
                    "canonical interface install sync",
                    "--route-hint",
                    "system/knowledge-library/installation",
                    "--top-k",
                    "1",
                    "--json",
                ],
                encoding=encoding,
            )
            self.assertIsInstance(payload, list)

    def test_desktop_check_keeps_zh_cn_display_but_console_output_is_safe(self) -> None:
        payload = self.run_json(
            [
                "scripts/kb_desktop.py",
                "--check",
                "--language",
                "zh-CN",
                "--route",
                "system/knowledge-library/retrieval",
            ],
            encoding="cp1252",
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["language"], "zh-CN")
        self.assertIn("系统", payload["route"])

    def test_preflight_launcher_check_json_is_safe_under_cp1252(self) -> None:
        payload = self.run_json(
            ["templates/predictive-kb-preflight/kb_launch.py", "check", "--json"],
            encoding="cp1252",
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["resolved_repo_root"], str(REPO_ROOT))

    def test_installer_and_check_json_are_safe_under_cp1252(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            install_payload = self.run_json(
                ["scripts/install_codex_kb.py", "--codex-home", str(codex_home), "--json"],
                encoding="cp1252",
                extra_env={"KHAOS_BRAIN_ISOLATED_INSTALL_FIXTURE": "1"},
            )
            check_payload = self.run_json(
                ["scripts/install_codex_kb.py", "--codex-home", str(codex_home), "--check", "--json"],
                encoding="cp1252",
            )

            self.assertEqual(
                Path(install_payload["shell_tools"]["shell_bin_dir"]),
                (codex_home.parent / "codex-shell-bin").resolve(),
            )
            self.assertFalse(install_payload["shell_tools"]["user_path_updated"])
            self.assertEqual(
                install_payload["schema_version"],
                "khaos-brain.install-result.v1",
            )
            self.assertEqual(install_payload["status"], "completed")
            self.assertLess(len(json.dumps(install_payload)), 131_072)

        self.assertEqual(install_payload["codex_home"], str(codex_home))
        self.assertTrue(check_payload["ok"], check_payload["issues"])
        self.assertEqual(
            check_payload["schema_version"],
            "khaos-brain.install-check-result.v1",
        )
        self.assertLess(len(json.dumps(check_payload)), 131_072)
        checklist = {item["id"]: item for item in check_payload["checklist"]}
        self.assertTrue(checklist["canonical_machine_interfaces"]["ok"])

    def test_aggregate_assurance_child_cannot_recursively_run_upgrade_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            payload = self.run_json(
                ["scripts/install_codex_kb.py", "--codex-home", str(codex_home), "--json"],
                encoding="cp1252",
                extra_env={"KHAOS_BRAIN_ASSURANCE_ACTIVE": "1"},
            )

            self.assertEqual(
                Path(payload["shell_tools"]["shell_bin_dir"]),
                (codex_home.parent / "codex-shell-bin").resolve(),
            )
            self.assertFalse(payload["shell_tools"]["user_path_updated"])

        self.assertFalse(payload["history_migration_required"])
        self.assertFalse(payload["upgrade_assurance_required"])
        self.assertEqual(payload["history_migration"]["status"], "fixture_skipped")

    def test_installer_terminal_projections_never_embed_full_assurance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            giant = "x" * 10_000_000
            install_payload = {
                "repo_root": str(REPO_ROOT),
                "codex_home": str(codex_home),
                "install_state_path": str(codex_home / "install-state.json"),
                "upgrade_assurance": {
                    "ok": True,
                    "status": "passed",
                    "manifest_path": str(codex_home / "assurance.json"),
                    "full_evidence": giant,
                },
                "post_install_check": {
                    "ok": True,
                    "canonical_interface_checks": giant,
                },
                "upgrade_attempt": {
                    "attempt_id": "upgrade-test",
                    "status": "completed",
                    "phase": "post_install_check_passed",
                    "full_evidence": giant,
                },
            }
            check_payload = {
                "ok": True,
                "repo_root": str(REPO_ROOT),
                "codex_home": str(codex_home),
                "install_state_path": str(codex_home / "install-state.json"),
                "upgrade_assurance": {
                    "ok": True,
                    "status": "passed",
                    "full_evidence": giant,
                },
                "canonical_interface_checks": giant,
                "issues": [],
                "warnings": [],
            }

            projected_install = _install_result_projection(
                install_payload,
                codex_home=codex_home,
            )
            projected_check = _installation_check_result_projection(
                check_payload,
                codex_home=codex_home,
            )

        self.assertLess(len(json.dumps(projected_install)), 131_072)
        self.assertLess(len(json.dumps(projected_check)), 131_072)
        self.assertNotIn("full_evidence", json.dumps(projected_install))
        self.assertNotIn("full_evidence", json.dumps(projected_check))

    def test_installer_failure_is_one_parseable_json_terminal_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            missing_snapshot = Path(tmp_dir) / "missing-snapshot.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    "scripts/install_codex_kb.py",
                    "--codex-home",
                    str(codex_home),
                    "--automation-state-snapshot",
                    str(missing_snapshot),
                    "--json",
                ],
                cwd=REPO_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "failed")
        self.assertIn("checkpoint", payload)
        self.assertIn("blockers", payload)
        self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
