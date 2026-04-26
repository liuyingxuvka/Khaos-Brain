#!/usr/bin/env python3
"""Inspect and maintain Khaos Brain software update state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    return repo_root


SCRIPT_REPO_ROOT = _bootstrap_repo_imports()

from local_kb.config import resolve_repo_root  # noqa: E402
from local_kb.software_update import (  # noqa: E402
    architect_update_check,
    check_remote_update,
    load_update_state,
    mark_update_status,
    set_update_request,
    update_state_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Khaos Brain software update state.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--status", action="store_true", help="Read the current update state.")
    parser.add_argument("--check-remote", action="store_true", help="Fetch and compare the configured upstream.")
    parser.add_argument(
        "--architect-check",
        action="store_true",
        help="Run the Architect gate: check remote state, verify whether UI is closed, and mark an approved update as upgrading.",
    )
    parser.add_argument("--request", choices=["prepare", "cancel"], help="Set or clear the user's prepared-update request.")
    parser.add_argument("--mark", choices=["upgrading", "current", "failed"], help="Mark update execution state.")
    parser.add_argument("--error", default="", help="Failure text when --mark failed is used.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT)

    if args.architect_check:
        payload = architect_update_check(repo_root)
    elif args.check_remote:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": check_remote_update(repo_root),
        }
    elif args.request:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": set_update_request(repo_root, args.request == "prepare"),
        }
    elif args.mark:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": mark_update_status(repo_root, args.mark, error=args.error),
        }
    else:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": load_update_state(repo_root),
        }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        state = payload.get("state", {}) if isinstance(payload.get("state"), dict) else payload
        print(f"Khaos Brain update status: {state.get('status', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
