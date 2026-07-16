from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.install_desktop_shortcut import _target_and_arguments
from scripts.open_khaos_brain_ui import (
    CURRENT_RELEASE_EXECUTABLE,
    RELEASE_RUNTIME,
    SOURCE_RUNTIME,
    _launch_command,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class DesktopLauncherCurrentRuntimeTests(unittest.TestCase):
    def test_source_runtime_is_explicit_and_never_probes_release_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "scripts" / "kb_desktop.py"
            source.parent.mkdir(parents=True)
            source.write_text("print('ok')\n", encoding="utf-8")
            (root / CURRENT_RELEASE_EXECUTABLE).parent.mkdir(parents=True)
            (root / CURRENT_RELEASE_EXECUTABLE).write_bytes(b"not-used")

            mode, command = _launch_command(root, runtime=SOURCE_RUNTIME, language="zh-CN")

        self.assertEqual(mode, SOURCE_RUNTIME)
        self.assertEqual(Path(command[1]), source)
        self.assertNotIn(str(root / CURRENT_RELEASE_EXECUTABLE), command)

    def test_release_runtime_requires_the_one_current_executable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir(parents=True)
            (root / "scripts" / "kb_desktop.py").write_text("print('ok')\n", encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "Selected release runtime is unavailable"):
                _launch_command(root, runtime=RELEASE_RUNTIME, language="")

    def test_shortcut_target_uses_the_exact_selected_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            release = root / CURRENT_RELEASE_EXECUTABLE
            release.parent.mkdir(parents=True)
            release.write_bytes(b"exe")

            target, arguments = _target_and_arguments(root, runtime=RELEASE_RUNTIME, language="en")

        self.assertEqual(target, release)
        self.assertIn("--repo-root", arguments)
        self.assertIn("--language en", arguments)

    def test_retired_prefer_python_flag_is_rejected(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "open_khaos_brain_ui.py"),
                "--repo-root",
                str(REPO_ROOT),
                "--runtime",
                SOURCE_RUNTIME,
                "--prefer-python",
                "--json",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("--prefer-python", result.stderr)


if __name__ == "__main__":
    unittest.main()
