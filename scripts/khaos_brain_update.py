#!/usr/bin/env python3
"""Inspect Khaos Brain's read-only configured-upstream update status."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_repo_imports() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root))
    return repo_root


SCRIPT_REPO_ROOT = _bootstrap_repo_imports()

from local_kb.cli_output import print_json, print_text  # noqa: E402
from local_kb.config import resolve_repo_root  # noqa: E402
from local_kb.software_update import (  # noqa: E402
    check_remote_update,
    load_update_state,
    update_state_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect Khaos Brain configured-upstream update status.")
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--status", action="store_true", help="Read the current update state.")
    parser.add_argument("--check-remote", action="store_true", help="Fetch and compare the configured upstream.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT)

    if args.check_remote:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": check_remote_update(repo_root),
        }
    else:
        payload = {
            "ok": True,
            "state_path": str(update_state_path(repo_root)),
            "state": load_update_state(repo_root),
        }

    if args.json:
        print_json(payload, sort_keys=True)
    else:
        state = payload.get("state", {}) if isinstance(payload.get("state"), dict) else payload
        print_text(f"Khaos Brain update status: {state.get('status', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
