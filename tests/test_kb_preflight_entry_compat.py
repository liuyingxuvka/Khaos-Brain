from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class KbPreflightEntryCurrentGrammarTests(unittest.TestCase):
    def _launcher(self) -> tuple[Path, Path]:
        repo_root = Path(__file__).resolve().parents[1]
        return repo_root, repo_root / "templates" / "predictive-kb-preflight" / "kb_launch.py"

    def test_launcher_requires_an_explicit_current_subcommand(self) -> None:
        with tempfile.TemporaryDirectory():
            repo_root, launcher_path = self._launcher()
            env = os.environ.copy()
            env["CODEX_PREDICTIVE_KB_ROOT"] = str(repo_root)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(launcher_path),
                    "--query",
                    "knowledge library retrieval",
                ],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2)
            self.assertIn("invalid choice", completed.stderr)

    def test_launcher_current_check_subcommand_succeeds(self) -> None:
        with tempfile.TemporaryDirectory():
            repo_root, launcher_path = self._launcher()
            env = os.environ.copy()
            env["CODEX_PREDICTIVE_KB_ROOT"] = str(repo_root)
            completed = subprocess.run(
                [sys.executable, str(launcher_path), "check", "--json"],
                cwd=repo_root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue(json.loads(completed.stdout)["ok"])

    def test_local_search_exposes_only_route_hint(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / ".agents" / "skills" / "local-kb-retrieve" / "scripts" / "kb_search.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--help",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--route-hint", completed.stdout)
        self.assertNotIn("--path-hint", completed.stdout)

    def test_local_search_rejects_retired_path_hint(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / ".agents" / "skills" / "local-kb-retrieve" / "scripts" / "kb_search.py"
        completed = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--repo-root",
                str(repo_root),
                "--query",
                "knowledge library retrieval",
                "--path-hint",
                "system/knowledge-library/retrieval",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("unrecognized arguments: --path-hint", completed.stderr)

    def test_feedback_help_does_not_boot_the_kb_runtime(self) -> None:
        repo_root, launcher_path = self._launcher()
        env = os.environ.copy()
        env["CODEX_PREDICTIVE_KB_ROOT"] = str(repo_root)
        started = time.perf_counter()
        completed = subprocess.run(
            [sys.executable, str(launcher_path), "feedback", "--help"],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        elapsed = time.perf_counter() - started
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("--task-summary", completed.stdout)
        self.assertLess(elapsed, 5)


if __name__ == "__main__":
    unittest.main()
