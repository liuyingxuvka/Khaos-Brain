from __future__ import annotations

import unittest
from unittest import mock

from local_kb.github_repo_config import (
    build_branch_protection_payload,
    configure_github_org_kb_repository,
    create_github_pull_request_for_branch,
    parse_github_owner_repo,
)


class GitHubRepoConfigTests(unittest.TestCase):
    def test_parse_github_owner_repo_supports_https_and_ssh(self) -> None:
        self.assertEqual(
            parse_github_owner_repo("https://github.com/example-org/khaos-org-kb-sandbox.git"),
            ("example-org", "khaos-org-kb-sandbox"),
        )
        self.assertEqual(
            parse_github_owner_repo("git@github.com:example-org/khaos-org-kb-sandbox.git"),
            ("example-org", "khaos-org-kb-sandbox"),
        )

    def test_branch_protection_payload_requires_expected_check_context(self) -> None:
        payload = build_branch_protection_payload(["organization-kb-checks"])

        self.assertEqual(payload["required_status_checks"]["contexts"], ["organization-kb-checks"])
        self.assertTrue(payload["required_status_checks"]["strict"])
        self.assertFalse(payload["allow_force_pushes"])
        self.assertFalse(payload["allow_deletions"])

    def test_configure_github_repo_dry_run_builds_expected_api_steps(self) -> None:
        result = configure_github_org_kb_repository(
            "https://github.com/example-org/khaos-org-kb-sandbox.git",
            token="",
            dry_run=True,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["owner"], "example-org")
        self.assertEqual(result["repo"], "khaos-org-kb-sandbox")
        self.assertEqual([step["name"] for step in result["steps"]], ["enable-auto-merge", "protect-default-branch"])

    def test_create_pull_request_dry_run_includes_auto_merge_label_step(self) -> None:
        result = create_github_pull_request_for_branch(
            "https://github.com/example-org/khaos-org-kb-sandbox.git",
            branch="contrib/test",
            base_branch="main",
            title="Add organization KB import proposals",
            labels=["org-kb:auto-merge"],
            dry_run=True,
        )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["owner"], "example-org")
        self.assertEqual([step["name"] for step in result["steps"]], ["create-pr", "add-labels"])
        self.assertEqual(result["steps"][1]["payload"]["labels"], ["org-kb:auto-merge"])

    def test_create_pull_request_posts_pr_then_labels(self) -> None:
        responses = [
            {"ok": True, "status": 201, "body": {"number": 7, "html_url": "https://github.com/example/pr/7"}},
            {"ok": True, "status": 200, "body": {}},
        ]

        with mock.patch("local_kb.github_repo_config._github_json_request", side_effect=responses) as request:
            result = create_github_pull_request_for_branch(
                "https://github.com/example-org/khaos-org-kb-sandbox.git",
                branch="maintenance/test",
                base_branch="main",
                title="Apply organization KB maintenance review",
                labels=["org-kb:auto-merge"],
                token="token",
            )

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["url"], "https://github.com/example/pr/7")
        self.assertEqual(request.call_count, 2)
        self.assertIn("/pulls", request.call_args_list[0].args[1])
        self.assertIn("/issues/7/labels", request.call_args_list[1].args[1])


if __name__ == "__main__":
    unittest.main()
