#!/usr/bin/env python3
"""Inspect or restore low-risk artifacts from a consolidation run directory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.snapshots import (
    MANIFEST_FILENAME,
    SUPPORTED_RESTORE_ARTIFACTS,
    build_rollback_manifest,
    resolve_run_dir,
    restore_artifact,
    write_rollback_manifest,
)
from local_kb.store import resolve_repo_root


def add_run_locator_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-id", default="")
    group.add_argument("--run-dir", default="")


def inspect_command(args: argparse.Namespace) -> int:
    repo_root = resolve_repo_root(args.repo_root)
    run_dir = resolve_run_dir(repo_root, run_id=args.run_id or None, run_dir=args.run_dir or None)
    manifest = build_rollback_manifest(repo_root, run_dir)

    if args.write_manifest:
        write_rollback_manifest(run_dir, manifest)
        manifest["manifest_path"] = str((run_dir / MANIFEST_FILENAME).relative_to(repo_root).as_posix())

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(
        f"Run {manifest['run_id']} contains {manifest['artifact_count']} artifacts; "
        f"{manifest['restorable_artifact_count']} can be restored safely."
    )
    for artifact in manifest["artifacts"]:
        status = "present" if artifact["exists"] else "missing"
        restorable = "restorable" if artifact["restorable"] else "inspect-only"
        print(f"- {artifact['artifact_id']}: {status}, {restorable}, path={artifact['path']}")
    if args.write_manifest:
        print(f"Manifest: {(run_dir / MANIFEST_FILENAME).relative_to(repo_root).as_posix()}")
    return 0


def restore_command(args: argparse.Namespace) -> int:
    repo_root = resolve_repo_root(args.repo_root)
    run_dir = resolve_run_dir(repo_root, run_id=args.run_id or None, run_dir=args.run_dir or None)
    manifest = build_rollback_manifest(repo_root, run_dir)
    result = restore_artifact(
        repo_root,
        manifest,
        args.artifact,
        dry_run=args.dry_run,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    verb = "Would restore" if args.dry_run else "Restored"
    print(
        f"{verb} {result['artifact_id']} to {result['target_path']} "
        f"from {result['source_path']} ({result['event_count']} events)."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect")
    add_run_locator_args(inspect_parser)
    inspect_parser.add_argument("--write-manifest", action="store_true")
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.set_defaults(handler=inspect_command)

    restore_parser = subparsers.add_parser("restore")
    add_run_locator_args(restore_parser)
    restore_parser.add_argument("--artifact", choices=SUPPORTED_RESTORE_ARTIFACTS, default="history-events")
    restore_parser.add_argument("--dry-run", action="store_true")
    restore_parser.add_argument("--json", action="store_true")
    restore_parser.set_defaults(handler=restore_command)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
