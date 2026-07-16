"""Compatibility CLI for the canonical FlowGuard skill-suite validator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from flowguard.skill_suite import validate_skill_suite


def verify_repository(root: Path) -> list[str]:
    """Return compatibility finding strings from the canonical report."""

    report = validate_skill_suite(root)
    return [
        f"{finding.code}: {finding.member_id or finding.file_path}: {finding.message}"
        for finding in report.findings
    ]


def verify_installed(root: Path, installed_root: Path) -> list[str]:
    """Validate the installed tree against the repository-owned inventory."""

    report = validate_skill_suite(
        root,
        skill_root=installed_root,
        check_private_inventories=False,
    )
    return [
        f"{finding.code}: {finding.member_id or finding.file_path}: {finding.message}"
        for finding in report.findings
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="validate the canonical FlowGuard skill suite")
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument("--installed-root", default=None, help="Optional installed Codex skills root")
    parser.add_argument("--json", action="store_true", help="Print canonical JSON output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    repository_report = validate_skill_suite(root)
    payload: dict[str, object] = repository_report.to_dict()
    if args.installed_root:
        installed_report = validate_skill_suite(
            root,
            skill_root=Path(args.installed_root).resolve(),
            check_private_inventories=False,
        )
        payload["installed"] = installed_report.to_dict()
        payload["ok"] = repository_report.ok and installed_report.ok
        payload["status"] = "pass" if payload["ok"] else "blocked"

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(repository_report.format_text())
        if args.installed_root:
            print("\n=== installed projection ===")
            print("status: pass" if payload["installed"]["ok"] else "status: blocked")  # type: ignore[index]

    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
