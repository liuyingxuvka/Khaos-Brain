from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.install import build_installation_check, global_agents_path, install_codex_integration


class CodexInstallTests(unittest.TestCase):
    def test_install_writes_global_skill_launcher_and_manifest(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            payload = install_codex_integration(repo_root=repo_root, codex_home=codex_home)

            self.assertTrue((codex_home / "skills" / "predictive-kb-preflight" / "SKILL.md").exists())
            self.assertTrue((codex_home / "skills" / "predictive-kb-preflight" / "kb_launch.py").exists())
            self.assertTrue((codex_home / "predictive-kb" / "install.json").exists())
            self.assertTrue((codex_home / "automations" / "kb-sleep" / "automation.toml").exists())
            self.assertTrue((codex_home / "automations" / "kb-dream" / "automation.toml").exists())
            self.assertTrue(global_agents_path(codex_home).exists())
            self.assertEqual(payload["repo_root"], str(repo_root))
            self.assertEqual(payload["automation_ids"], ["kb-sleep", "kb-dream"])

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
            self.assertIn(str(repo_root).replace("\\", "\\\\"), sleep_toml)

            dream_toml = (codex_home / "automations" / "kb-dream" / "automation.toml").read_text(encoding="utf-8")
            self.assertIn('kind = "cron"', dream_toml)
            self.assertIn('kb_dream.py', dream_toml)
            self.assertIn('rrule = "FREQ=WEEKLY;BYDAY=SU,MO,TU,WE,TH,FR,SA;BYHOUR=13;BYMINUTE=0"', dream_toml)

            check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
            self.assertTrue(check["ok"], check["issues"])
            self.assertEqual([item["id"] for item in check["automation_checks"]], ["kb-sleep", "kb-dream"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertIn("strong_session_defaults", checklist)
            self.assertTrue(checklist["strong_session_defaults"]["ok"])
            self.assertTrue(checklist["global_agents_block"]["ok"])
            self.assertTrue(checklist["global_skill_postflight"]["ok"])

    def test_install_preserves_existing_global_agents_content(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            agents_path = global_agents_path(codex_home)
            agents_path.parent.mkdir(parents=True, exist_ok=True)
            agents_path.write_text("## User Custom Defaults\n\n- Keep this line.\n", encoding="utf-8")

            install_codex_integration(repo_root=repo_root, codex_home=codex_home)

            global_agents_text = agents_path.read_text(encoding="utf-8")
            self.assertIn("## User Custom Defaults", global_agents_text)
            self.assertIn("- Keep this line.", global_agents_text)
            self.assertIn("BEGIN MANAGED PREDICTIVE KB DEFAULTS", global_agents_text)
            self.assertEqual(global_agents_text.count("BEGIN MANAGED PREDICTIVE KB DEFAULTS"), 1)

    def test_check_fails_when_managed_global_agents_block_is_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp_dir:
            codex_home = Path(tmp_dir) / ".codex"
            install_codex_integration(repo_root=repo_root, codex_home=codex_home)

            agents_path = global_agents_path(codex_home)
            agents_path.write_text("## User Custom Defaults\n\n- Keep this line only.\n", encoding="utf-8")

            check = build_installation_check(repo_root=repo_root, codex_home=codex_home)
            self.assertFalse(check["ok"])
            checklist = {item["id"]: item for item in check["checklist"]}
            self.assertFalse(checklist["global_agents_block"]["ok"])
            self.assertFalse(checklist["strong_session_defaults"]["ok"])


if __name__ == "__main__":
    unittest.main()
