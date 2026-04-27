from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from local_kb.org_contribution import github_compare_url, prepare_organization_import_branch
from local_kb.org_sources import _run_git
from local_kb.store import write_yaml_file


class OrganizationContributionTests(unittest.TestCase):
    def _write_org_repo(self, root: Path) -> None:
        write_yaml_file(
            root / "khaos_org_kb.yaml",
            {
                "kind": "khaos-organization-kb",
                "schema_version": 1,
                "organization_id": "sandbox",
                "kb": {
                    "trusted_path": "kb/trusted",
                    "candidates_path": "kb/candidates",
                    "imports_path": "kb/imports",
                },
                "skills": {
                    "registry_path": "skills/registry.yaml",
                    "candidates_path": "skills/candidates",
                },
            },
        )
        write_yaml_file(root / "kb" / "trusted" / "model.yaml", {"id": "trusted", "status": "trusted"})
        (root / "kb" / "candidates").mkdir(parents=True)
        (root / "kb" / "imports").mkdir(parents=True)
        write_yaml_file(root / "skills" / "registry.yaml", {"skills": []})
        (root / "skills" / "candidates").mkdir(parents=True)

    def test_prepare_organization_import_branch_copies_outbox_to_imports_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            outbox = root / "outbox"
            self._write_org_repo(org)
            write_yaml_file(outbox / "proposal.yaml", {"id": "proposal", "status": "candidate"})
            self.assertEqual(0, _run_git(["init"], cwd=org).returncode)
            self.assertEqual(0, _run_git(["add", "."], cwd=org).returncode)
            self.assertEqual(
                0,
                _run_git(
                    ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                    cwd=org,
                ).returncode,
            )

            result = prepare_organization_import_branch(
                org,
                outbox,
                contributor_id="alice/main-laptop",
                branch_name="contrib/test/imports",
            )
            imported = org / "kb" / "imports" / "alice-main-laptop" / "proposal.yaml"
            imported_exists = imported.exists()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["branch"], "contrib/test/imports")
        self.assertEqual(result["created_files"], ["kb/imports/alice-main-laptop/proposal.yaml"])
        self.assertTrue(result["committed"])
        self.assertTrue(result["commit"])
        self.assertTrue(imported_exists)

    def test_prepare_organization_import_branch_can_copy_selected_outbox_files_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            org = root / "org"
            outbox = root / "outbox"
            self._write_org_repo(org)
            write_yaml_file(outbox / "proposal.yaml", {"id": "proposal", "status": "candidate"})
            write_yaml_file(outbox / "stale.yaml", {"id": "stale", "status": "candidate"})
            self.assertEqual(0, _run_git(["init"], cwd=org).returncode)
            self.assertEqual(0, _run_git(["add", "."], cwd=org).returncode)
            self.assertEqual(
                0,
                _run_git(
                    ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                    cwd=org,
                ).returncode,
            )

            result = prepare_organization_import_branch(
                org,
                outbox,
                contributor_id="alice",
                branch_name="contrib/test/selected-imports",
                proposal_files=[outbox / "proposal.yaml"],
            )
            imported = org / "kb" / "imports" / "alice" / "proposal.yaml"
            stale = org / "kb" / "imports" / "alice" / "stale.yaml"
            imported_exists = imported.exists()
            stale_exists = stale.exists()

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["created_files"], ["kb/imports/alice/proposal.yaml"])
        self.assertTrue(imported_exists)
        self.assertFalse(stale_exists)

    def test_prepare_organization_import_branch_can_push_to_remote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote = root / "remote.git"
            org = root / "org"
            outbox = root / "outbox"
            self.assertEqual(0, _run_git(["init", "--bare", str(remote)]).returncode)
            self._write_org_repo(org)
            write_yaml_file(outbox / "proposal.yaml", {"id": "proposal", "status": "candidate"})
            self.assertEqual(0, _run_git(["init"], cwd=org).returncode)
            self.assertEqual(0, _run_git(["remote", "add", "origin", str(remote)], cwd=org).returncode)
            self.assertEqual(0, _run_git(["add", "."], cwd=org).returncode)
            self.assertEqual(
                0,
                _run_git(
                    ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "seed"],
                    cwd=org,
                ).returncode,
            )
            self.assertEqual(0, _run_git(["branch", "-M", "main"], cwd=org).returncode)
            self.assertEqual(0, _run_git(["push", "-u", "origin", "main"], cwd=org).returncode)

            result = prepare_organization_import_branch(
                org,
                outbox,
                contributor_id="alice",
                branch_name="contrib/alice/proposal",
                push=True,
            )
            branches = _run_git(["branch", "--list"], cwd=remote)

        self.assertTrue(result["ok"], result)
        self.assertTrue(result["push"]["pushed"], result)
        self.assertIn("contrib/alice/proposal", branches.stdout)

    def test_github_compare_url_supports_https_and_ssh_remotes(self) -> None:
        self.assertEqual(
            github_compare_url("https://github.com/example/org-kb.git", "contrib/alice/proposal"),
            "https://github.com/example/org-kb/compare/main...contrib/alice/proposal?expand=1",
        )
        self.assertEqual(
            github_compare_url("git@github.com:example/org-kb.git", "contrib/alice/proposal", base_branch="stable"),
            "https://github.com/example/org-kb/compare/stable...contrib/alice/proposal?expand=1",
        )


if __name__ == "__main__":
    unittest.main()
