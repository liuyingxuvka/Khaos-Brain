from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.org_github_automation import install_github_automation_templates  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install GitHub Actions automation templates into an organization KB repo.")
    parser.add_argument("--org-root", required=True, help="Organization KB repository root.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing workflow files.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = install_github_automation_templates(Path(args.org_root), overwrite=args.overwrite)
    print_json(result)
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
