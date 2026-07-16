from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class KhaosLogicGuardAssuranceTests(unittest.TestCase):
    def test_all_logicguard_native_flowguard_contracts_reject_known_bad_shapes(self) -> None:
        paths = (
            ".flowguard/khaos_brain_logicguard_authority_cutover.py",
            ".flowguard/khaos_brain_logicguard_field_lifecycle.py",
            ".flowguard/khaos_brain_logicguard_model_mesh.py",
            ".flowguard/khaos_brain_logicguard_code_structure.py",
            ".flowguard/khaos_brain_logicguard_model_test_alignment.py",
            ".flowguard/khaos_brain_logicguard_test_mesh.py",
        )
        for relative in paths:
            with self.subTest(path=relative):
                completed = subprocess.run(
                    [sys.executable, relative],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=120,
                )
                self.assertEqual(
                    completed.returncode,
                    0,
                    f"{relative}\nstdout={completed.stdout}\nstderr={completed.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
