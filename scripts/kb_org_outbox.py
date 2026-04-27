from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.org_automation import run_organization_contribution  # noqa: E402
from local_kb.org_outbox import build_organization_outbox  # noqa: E402
from local_kb.settings import load_desktop_settings, organization_sources_from_settings  # noqa: E402
from local_kb.store import resolve_repo_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build organization KB contribution outbox files.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--organization-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--automation",
        action="store_true",
        help="Run the settings-gated organization contribution automation entry point.",
    )
    parser.add_argument("--prepare-branch", dest="prepare_branch", action="store_true", default=True)
    parser.add_argument("--no-prepare-branch", dest="prepare_branch", action="store_false")
    parser.add_argument("--contributor-id", default="")
    parser.add_argument("--branch-name", default="")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--push", dest="push", action="store_true", default=True)
    parser.add_argument("--no-push", dest="push", action="store_false")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--no-postflight", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    if args.automation:
        result = run_organization_contribution(
            repo_root,
            dry_run=args.dry_run,
            prepare_branch=args.prepare_branch,
            contributor_id=args.contributor_id,
            branch_name=args.branch_name,
            commit=not args.no_commit,
            push=args.push,
            remote=args.remote,
            base_branch=args.base_branch,
            record_postflight=not args.no_postflight,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("ok"):
            raise SystemExit(2)
        return

    if not args.organization_id:
        parser.error("--organization-id is required unless --automation is used")

    organization_sources = organization_sources_from_settings(load_desktop_settings(repo_root))
    result = build_organization_outbox(
        repo_root,
        organization_id=args.organization_id,
        dry_run=args.dry_run,
        organization_sources=organization_sources,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
