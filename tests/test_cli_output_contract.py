from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.cli_output import machine_json_text


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliOutputContractTests(unittest.TestCase):
    def run_json(self, args: list[str], *, encoding: str) -> object:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = encoding
        env["CODEX_PREDICTIVE_KB_ROOT"] = str(REPO_ROOT)
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
            )
            check_payload = self.run_json(
                ["scripts/install_codex_kb.py", "--codex-home", str(codex_home), "--check", "--json"],
                encoding="cp1252",
            )

        self.assertEqual(install_payload["codex_home"], str(codex_home))
        self.assertTrue(check_payload["ok"], check_payload["issues"])
        checklist = {item["id"]: item for item in check_payload["checklist"]}
        self.assertTrue(checklist["canonical_machine_interfaces"]["ok"])


if __name__ == "__main__":
    unittest.main()
