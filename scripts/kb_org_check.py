from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))


_bootstrap_repo_imports()

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.org_checks import check_organization_repository, normalize_changed_file  # noqa: E402


def _split_changed_files(values: list[str]) -> list[str]:
    files: list[str] = []
    for value in values:
        for item in str(value or "").replace("\r", "\n").split("\n"):
            for part in item.split(","):
                text = normalize_changed_file(part)
                if text:
                    files.append(text)
    return files


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run organization KB repository checks for GitHub automation.")
    parser.add_argument("--org-root", default=".", help="Organization KB repository root.")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path. May be repeated; comma-separated values are accepted.",
    )
    parser.add_argument(
        "--changed-files-file",
        default="",
        help="Text file containing changed paths, one per line.",
    )
    parser.add_argument(
        "--enforce-low-risk",
        action="store_true",
        help="Fail if the changed files are not eligible for low-risk automatic merge.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    changed_values = list(args.changed_file or [])
    if args.changed_files_file:
        changed_values.append(Path(args.changed_files_file).read_text(encoding="utf-8"))
    result = check_organization_repository(
        Path(args.org_root),
        changed_files=_split_changed_files(changed_values),
        enforce_low_risk=args.enforce_low_risk,
    )
    print_json(result)
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
