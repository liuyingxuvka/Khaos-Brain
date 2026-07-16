from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from local_kb.org_github_automation import install_github_automation_templates
from local_kb.store import write_yaml_file


class OrganizationGitHubAutomationTests(unittest.TestCase):
    def _write_org_repo(self, root: Path) -> None:
        write_yaml_file(
            root / "khaos_org_kb.yaml",
            {
                "kind": "khaos-organization-kb",
                "schema_version": 1,
                "organization_id": "sandbox",
                "kb": {
                    "main_path": "kb/main",
                    "imports_path": "kb/imports",
                },
                "skills": {
                    "registry_path": "skills/registry.yaml",
                    "candidates_path": "skills/candidates",
                },
            },
        )
        write_yaml_file(root / "kb" / "main" / "model.yaml", {"id": "model", "status": "trusted"})
        (root / "kb" / "imports").mkdir(parents=True)
        write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
        (root / "skills" / "candidates").mkdir(parents=True)

    def test_installs_github_workflow_templates_into_valid_org_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)

            result = install_github_automation_templates(root)
            checks = (root / ".github" / "workflows" / "org-kb-checks.yml").read_text(encoding="utf-8")
            auto_merge = (root / ".github" / "workflows" / "org-kb-auto-merge.yml").read_text(encoding="utf-8")
            script = (root / ".github" / "scripts" / "org_kb_check.py").read_text(encoding="utf-8")

        self.assertTrue(result["ok"], result)
        self.assertEqual(
            sorted(result["installed"]),
            [
                ".github/scripts/org_kb_check.py",
                ".github/workflows/org-kb-auto-merge.yml",
                ".github/workflows/org-kb-checks.yml",
            ],
        )
        self.assertIn(".github/scripts/org_kb_check.py", checks)
        self.assertIn("org-kb:auto-merge", auto_merge)
        self.assertIn("SKILL_REVIEW_STATES", script)

    def test_does_not_overwrite_existing_workflow_without_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            target = root / ".github" / "workflows" / "org-kb-checks.yml"
            target.parent.mkdir(parents=True)
            target.write_text("custom\n", encoding="utf-8")

            result = install_github_automation_templates(root)
            text = target.read_text(encoding="utf-8")

        self.assertTrue(result["ok"], result)
        self.assertIn(".github/workflows/org-kb-checks.yml", result["skipped"])
        self.assertEqual(text, "custom\n")

    def test_installed_checker_rejects_obsolete_organization_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_org_repo(root)
            install_github_automation_templates(root)
            write_yaml_file(
                root / "kb" / "trusted" / "obsolete.yaml",
                {"id": "obsolete", "status": "trusted"},
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / ".github" / "scripts" / "org_kb_check.py"),
                    "--org-root",
                    str(root),
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            payload = json.loads(completed.stdout)

        self.assertEqual(completed.returncode, 2)
        self.assertFalse(payload["ok"])
        self.assertTrue(
            any("obsolete organization roots" in item for item in payload["errors"]),
            payload,
        )


if __name__ == "__main__":
    unittest.main()
