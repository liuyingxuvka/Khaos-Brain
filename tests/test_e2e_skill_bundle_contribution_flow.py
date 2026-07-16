from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_checks import check_organization_repository
from local_kb.org_contribution import prepare_organization_import_branch
from local_kb.org_outbox import build_organization_outbox
from local_kb.org_sources import _run_git
from local_kb.store import load_yaml_file, write_yaml_file
from tests.current_runtime_helpers import activate_current_kb_runtime


class SkillBundleContributionFlowE2ETests(unittest.TestCase):
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
        write_yaml_file(root / "kb" / "main" / "trusted" / "seed.yaml", {"id": "seed", "status": "trusted"})
        (root / "kb" / "imports").mkdir(parents=True, exist_ok=True)
        write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
        (root / "skills" / "candidates").mkdir(parents=True, exist_ok=True)

    def _write_skill_backed_local_card(self, repo: Path) -> None:
        skill_dir = repo / ".agents" / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo Skill for contribution e2e.\n---\n\nUse this Skill.",
            encoding="utf-8",
        )
        write_yaml_file(
            repo / "kb" / "public" / "skill-backed-card.yaml",
            {
                "id": "skill-backed-card",
                "title": "Skill backed organization contribution",
                "type": "model",
                "scope": "public",
                "status": "trusted",
                "confidence": 0.82,
                "domain_path": ["codex", "workflow", "skills"],
                "tags": ["skill", "organization"],
                "trigger_keywords": ["skill", "organization"],
                "required_skills": ["demo-skill"],
                "if": {"notes": "A reusable card depends on a local Skill."},
                "action": {"description": "Export the card and Skill bundle together."},
                "predict": {"expected_result": "Organization imports keep the nested Skill bundle."},
                "use": {
                    "guidance": "Review the card and its Skill as one proposal.",
                    "unavailable_skill_guidance": "Keep the card pending when the Skill bundle is unavailable.",
                },
            },
        )
        activate_current_kb_runtime(repo)

    def _commit_repo(self, root: Path) -> None:
        self.assertEqual(0, _run_git(["init"], cwd=root).returncode)
        self.assertEqual(0, _run_git(["add", "."], cwd=root).returncode)
        result = _run_git(
            ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
            cwd=root,
        )
        self.assertEqual(0, result.returncode, result.stderr or result.stdout)

    def test_outbox_contribution_preserves_nested_skill_bundle_and_passes_low_risk_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            machine = root / "machine-a"
            org = root / "org"
            self._write_org_repo(org)
            self._commit_repo(org)
            self._write_skill_backed_local_card(machine)

            outbox = build_organization_outbox(machine, organization_id="sandbox")
            proposal_path = Path(outbox["created"][0]["path"])
            proposal = load_yaml_file(proposal_path)
            dependency = proposal["organization_proposal"]["skill_dependencies"][0]
            outbox_skill_path = Path(outbox["outbox_dir"]) / dependency["bundle_path"] / "SKILL.md"
            outbox_metadata_path = Path(outbox["outbox_dir"]) / dependency["bundle_metadata_path"]

            branch = prepare_organization_import_branch(
                org,
                Path(outbox["outbox_dir"]),
                contributor_id="alice/main-laptop",
                branch_name="contrib/alice/skill-bundle",
            )
            imported_proposal_path = org / "kb" / "imports" / "alice-main-laptop" / proposal_path.name
            imported_proposal = load_yaml_file(imported_proposal_path)
            imported_dependency = imported_proposal["organization_proposal"]["skill_dependencies"][0]
            imported_skill_path = imported_proposal_path.parent / imported_dependency["bundle_path"] / "SKILL.md"
            imported_metadata_path = imported_proposal_path.parent / imported_dependency["bundle_metadata_path"]
            outbox_skill_exists = outbox_skill_path.exists()
            outbox_metadata_exists = outbox_metadata_path.exists()
            imported_skill_exists = imported_skill_path.exists()
            imported_metadata_exists = imported_metadata_path.exists()
            check = check_organization_repository(
                org,
                changed_files=branch["created_files"],
                enforce_low_risk=True,
            )

        self.assertTrue(outbox["ok"], outbox)
        self.assertEqual(outbox["created_count"], 1)
        self.assertEqual(dependency["sharing_mode"], "card-bound-bundle")
        self.assertTrue(outbox_skill_exists)
        self.assertTrue(outbox_metadata_exists)
        self.assertTrue(branch["ok"], branch)
        self.assertIn("kb/imports/alice-main-laptop/skill-backed-card.yaml", branch["created_files"])
        self.assertIn(imported_dependency["bundle_path"] + "/SKILL.md", "\n".join(branch["created_files"]))
        self.assertTrue(imported_skill_exists)
        self.assertTrue(imported_metadata_exists)
        self.assertTrue(check["ok"], check)
        self.assertTrue(check["auto_merge_eligible"], check)


if __name__ == "__main__":
    unittest.main()
