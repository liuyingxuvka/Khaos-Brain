from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local_kb.config import resolve_repo_root, save_install_state


def write_minimal_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "AGENTS.md").write_text("# test\n", encoding="utf-8")
    (root / "PROJECT_SPEC.md").write_text("# test\n", encoding="utf-8")
    (root / "kb").mkdir(parents=True, exist_ok=True)
    (root / "kb" / "taxonomy.yaml").write_text("nodes: []\n", encoding="utf-8")
    skill_dir = root / ".agents" / "skills" / "local-kb-retrieve"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("---\nname: local-kb-retrieve\n---\n", encoding="utf-8")


class RepoRootResolutionTests(unittest.TestCase):
    def test_resolve_repo_root_uses_env_var_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "kb-root"
            write_minimal_repo(repo_root)
            with patch.dict(os.environ, {"CODEX_PREDICTIVE_KB_ROOT": str(repo_root)}, clear=False):
                self.assertEqual(resolve_repo_root("auto"), repo_root.resolve())

    def test_resolve_repo_root_uses_install_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            repo_root = base / "kb-root"
            codex_home = base / ".codex"
            write_minimal_repo(repo_root)
            save_install_state({"repo_root": str(repo_root)}, codex_home)

            with patch.dict(os.environ, {"CODEX_PREDICTIVE_KB_ROOT": ""}, clear=False):
                self.assertEqual(resolve_repo_root("auto", cwd=base, codex_home=codex_home), repo_root.resolve())

    def test_resolve_repo_root_discovers_current_workspace_clone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir) / "kb-root"
            nested = repo_root / "tests" / "nested"
            write_minimal_repo(repo_root)
            nested.mkdir(parents=True, exist_ok=True)

            with patch.dict(os.environ, {"CODEX_PREDICTIVE_KB_ROOT": ""}, clear=False):
                self.assertEqual(resolve_repo_root("auto", cwd=nested), repo_root.resolve())


if __name__ == "__main__":
    unittest.main()
