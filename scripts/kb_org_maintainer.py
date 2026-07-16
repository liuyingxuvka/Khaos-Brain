from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.org_automation import run_organization_maintenance  # noqa: E402
from local_kb.org_maintenance import build_organization_maintenance_report  # noqa: E402
from local_kb.settings import load_desktop_settings, organization_sources_from_settings  # noqa: E402
from local_kb.store import resolve_repo_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect an organization KB mirror for maintainer review.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--org-root", default="", help="Organization KB mirror path. Omit to use validated desktop settings.")
    parser.add_argument(
        "--automation",
        action="store_true",
        help="Run the settings-gated organization maintenance automation entry point.",
    )
    parser.add_argument("--no-postflight", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root)
    if args.automation:
        result = run_organization_maintenance(
            repo_root,
            record_postflight=not args.no_postflight,
            run_id=args.run_id,
        )
        print_json(result)
        if not result.get("ok"):
            raise SystemExit(2)
        return

    organization_id = ""
    if args.org_root:
        org_root = Path(args.org_root)
    else:
        settings = load_desktop_settings(repo_root)
        sources = organization_sources_from_settings(settings)
        if not sources:
            print_json({"ok": False, "errors": ["No validated organization source in desktop settings."]})
            raise SystemExit(2)
        source = sources[0]
        org_root = Path(str(source["path"]))
        organization_id = str(source.get("organization_id") or "")

    report = build_organization_maintenance_report(org_root, repo_root=repo_root, organization_id=organization_id)
    print_json(report)
    if not report.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
