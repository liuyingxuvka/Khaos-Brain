#!/usr/bin/env python3
"""Run or inspect the versioned Chaos Brain maintenance-debt migration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text  # noqa: E402
from local_kb.config import resolve_repo_root  # noqa: E402
from local_kb.maintenance_migration import (  # noqa: E402
    build_inventory,
    check_migration,
    run_maintenance_migration,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--fail-after-phase", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT)
    if args.check:
        payload = check_migration(repo_root)
    elif args.inventory_only:
        payload = build_inventory(repo_root)
        payload["ok"] = int(payload.get("unresolved_count") or 0) == 0
    else:
        payload = run_maintenance_migration(
            repo_root,
            fail_after_phase=str(args.fail_after_phase or ""),
        )
    if args.json:
        print_json(payload, sort_keys=True)
    else:
        print_text(f"KB maintenance migration: {payload.get('status') or ('ok' if payload.get('ok') else 'failed')}")
        if payload.get("error"):
            print_text(f"error: {payload['error']}")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
