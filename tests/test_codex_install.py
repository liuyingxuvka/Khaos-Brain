from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.install import build_installation_check, global_agents_path, install_codex_integration


def write_cmd(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"@echo off\r\n{body}\r\n", encoding="utf-8")


class CodexInstallTests(unittest.TestCase):
    def test_install_writes_global_skill_launcher_and_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            shell_bin_dir = Path(tmp_dir) / "shell-bin"
            git_real = Path(tmp_dir) / "tool-src" / "git-real.cmd"
            rg_source = Path(tmp_dir) / "tool-src" / "rg-source.exe"
            write_cmd(git_real, "echo git version test")
            rg_source.parent.mkdir(parents=True, exist_ok=True)
            rg_source.write_bytes(b"rg-binary")

            payload = install_codex_integration(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin_dir,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
            )

            self.assertTrue((codex_home / "skills" / "predictive-kb-preflight" / "SKILL.md").exists())
            self.assertTrue((codex_home / "skills" / "predictive-kb-preflight" / "kb_launch.py").exists())
            self.assertTrue((codex_home / "predictive-kb" / "install.json").exists())
            self.assertTrue((codex_home / "automations" / "kb-sleep" / "automation.toml").exists())
            self.assertTrue((codex_home / "automations" / "kb-dream" / "automation.toml").exists())
            self.assertTrue(global_agents_path(codex_home).exists())
            self.assertTrue((shell_bin_dir / "git.cmd").exists())
            self.assertTrue((shell_bin_dir / "rg.exe").exists())
            self.assertEqual(payload["repo_root"], str(repo_root))
            self.assertEqual(payload["automation_ids"], ["kb-sleep", "kb-dream"])
            self.assertEqual(payload["shell_tools"]["shell_bin_dir"], str(shell_bin_dir))
            self.assertTrue(payload["shell_tools"]["git_shim_installed"])
            self.assertTrue(payload["shell_tools"]["rg_installed"])
            self.assertFalse(payload["shell_tools"]["issues"])

            skill_text = (codex_home / "skills" / "predictive-kb-preflight" / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("--route-hint", skill_text)
            self.assertIn("search-style calls without the explicit `search` subcommand", skill_text)

            openai_text = (
                codex_home / "skills" / "predictive-kb-preflight" / "agents" / "openai.yaml"
            ).read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: true", openai_text)
            self.assertIn("record a KB follow-up observation", openai_text)
            self.assertIn("required default preflight", openai_text)

            global_agents_text = global_agents_path(codex_home).read_text(encoding="utf-8")
            self.assertIn("BEGIN MANAGED PREDICTIVE KB DEFAULTS", global_agents_text)
            self.assertIn("$predictive-kb-preflight", global_agents_text)
            self.assertIn("explicit KB postflight check", global_agents_text)

            sleep_toml = (codex_home / "automations" / "kb-sleep" / "automation.toml").read_text(encoding="utf-8")
            self.assertIn('kind = "cron"', sleep_toml)
            self.assertIn('rrule = "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=12;BYMINUTE=0"', sleep_toml)
            self.assertIn('model = "gpt-5.4"', sleep_toml)
            self.assertIn('reasoning_effort = "xhigh"', sleep_toml)
            self.assertIn(str(repo_root).replace("\\", "\\\\"), sleep_toml)

            dream_toml = (codex_home / "automations" / "kb-dream" / "automation.toml").read_text(encoding="utf-8")
            self.assertIn('kind = "cron"', dream_toml)
            self.assertIn('kb_dream.py', dream_toml)
            self.assertIn('rrule = "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=13;BYMINUTE=0"', dream_toml)
            self.assertIn('model = "gpt-5.4"', dream_toml)
            self.assertIn('reasoning_effort = "xhigh"', dream_toml)

            check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
            self.assertTrue(check["ok"], check["issues"])
            self.assertEqual([item["id"] for item in check["automation_checks"]], ["kb-sleep", "kb-dream"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertIn("codex_shell_tools", checklist)
            self.assertIn("strong_session_defaults", checklist)
            self.assertTrue(checklist["codex_shell_tools"]["ok"])
            self.assertTrue(checklist["strong_session_defaults"]["ok"])
            self.assertTrue(checklist["global_agents_block"]["ok"])
            self.assertTrue(checklist["global_skill_postflight"]["ok"])

    def test_install_preserves_existing_global_agents_content(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            shell_bin_dir = Path(tmp_dir) / "shell-bin"
            git_real = Path(tmp_dir) / "tool-src" / "git-real.cmd"
            rg_source = Path(tmp_dir) / "tool-src" / "rg-source.exe"
            write_cmd(git_real, "echo git version test")
            rg_source.parent.mkdir(parents=True, exist_ok=True)
            rg_source.write_bytes(b"rg-binary")
            agents_path = global_agents_path(codex_home)
            agents_path.parent.mkdir(parents=True, exist_ok=True)
            agents_path.write_text("## User Custom Defaults\n\n- Keep this line.\n", encoding="utf-8")

            install_codex_integration(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin_dir,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
            )

            global_agents_text = agents_path.read_text(encoding="utf-8")
            self.assertIn("## User Custom Defaults", global_agents_text)
            self.assertIn("- Keep this line.", global_agents_text)
            self.assertIn("BEGIN MANAGED PREDICTIVE KB DEFAULTS", global_agents_text)
            self.assertEqual(global_agents_text.count("BEGIN MANAGED PREDICTIVE KB DEFAULTS"), 1)

    def test_check_fails_when_shell_tool_artifacts_are_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            shell_bin_dir = Path(tmp_dir) / "shell-bin"
            git_real = Path(tmp_dir) / "tool-src" / "git-real.cmd"
            rg_source = Path(tmp_dir) / "tool-src" / "rg-source.exe"
            write_cmd(git_real, "echo git version test")
            rg_source.parent.mkdir(parents=True, exist_ok=True)
            rg_source.write_bytes(b"rg-binary")

            install_codex_integration(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin_dir,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
            )

            (shell_bin_dir / "rg.exe").unlink()

            check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
            self.assertFalse(check["ok"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertFalse(checklist["codex_shell_tools"]["ok"])
            self.assertTrue(
                any("Codex shell rg binary is missing" in issue for issue in check["issues"]),
                check["issues"],
            )

    def test_check_fails_when_managed_global_agents_block_is_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            shell_bin_dir = Path(tmp_dir) / "shell-bin"
            git_real = Path(tmp_dir) / "tool-src" / "git-real.cmd"
            rg_source = Path(tmp_dir) / "tool-src" / "rg-source.exe"
            write_cmd(git_real, "echo git version test")
            rg_source.parent.mkdir(parents=True, exist_ok=True)
            rg_source.write_bytes(b"rg-binary")

            install_codex_integration(
                repo_root=repo_root,
                codex_home=codex_home,
                shell_bin_dir=shell_bin_dir,
                git_executable=git_real,
                rg_source=rg_source,
                persist_user_shell_path=False,
            )

            agents_path = global_agents_path(codex_home)
            agents_path.write_text("## User Custom Defaults\n\n- Keep this line only.\n", encoding="utf-8")

            check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
            self.assertFalse(check["ok"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertFalse(checklist["global_agents_block"]["ok"])
            self.assertFalse(checklist["strong_session_defaults"]["ok"])


if __name__ == "__main__":
    unittest.main()
