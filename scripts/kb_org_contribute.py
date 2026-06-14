from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.org_contribution import prepare_organization_import_branch  # noqa: E402
from local_kb.org_outbox import organization_outbox_dir  # noqa: E402
from local_kb.store import resolve_repo_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare a local organization KB import branch from outbox proposals.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--org-root", required=True)
    parser.add_argument("--organization-id", required=True)
    parser.add_argument("--contributor-id", required=True)
    parser.add_argument("--outbox-dir", default="")
    parser.add_argument("--branch-name", default="")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--push", action="store_true", help="Push the prepared branch to the configured remote.")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base-branch", default="main")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    outbox_dir = Path(args.outbox_dir) if args.outbox_dir else organization_outbox_dir(repo_root, args.organization_id)
    result = prepare_organization_import_branch(
        Path(args.org_root),
        outbox_dir,
        contributor_id=args.contributor_id,
        branch_name=args.branch_name,
        commit=not args.no_commit,
        push=args.push,
        remote=args.remote,
        base_branch=args.base_branch,
    )
    print_json(result)
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
