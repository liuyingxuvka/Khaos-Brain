from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.github_repo_config import configure_github_org_kb_repository, github_token_from_git_credential  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Configure GitHub auto-merge and branch protection for an organization KB repo.")
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--required-context", action="append", default=["organization-kb-checks"])
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--use-git-credential", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    token = os.environ.get(args.token_env, "").strip()
    if not token and args.use_git_credential:
        token = github_token_from_git_credential()
    result = configure_github_org_kb_repository(
        args.repo_url,
        token=token,
        branch=args.branch,
        required_contexts=args.required_context,
        dry_run=args.dry_run,
    )
    safe_result = dict(result)
    safe_result.pop("token", None)
    print_json(safe_result)
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
