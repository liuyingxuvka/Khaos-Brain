#!/usr/bin/env python3
"""Install or verify the cross-machine Codex integration for this predictive KB."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path


SCRIPT_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_REPO_ROOT))

from local_kb.cli_output import print_json, print_text
from local_kb.config import default_codex_home, resolve_repo_root
from local_kb.install import (
    build_installation_check,
    install_codex_integration,
    latest_upgrade_attempt,
)


def _is_temporary_fixture_home(codex_home: Path) -> bool:
    temporary_root = Path(tempfile.gettempdir()).resolve()
    resolved_home = codex_home.resolve()
    try:
        resolved_home.relative_to(temporary_root)
    except ValueError:
        return False
    return resolved_home != default_codex_home().resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--defer-automation-restore", action="store_true")
    parser.add_argument("--allow-deferred-automation-restore", action="store_true")
    parser.add_argument("--automation-state-snapshot", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    codex_home = Path(args.codex_home).expanduser().resolve() if args.codex_home else default_codex_home()
    repo_root = resolve_repo_root(args.repo_root, cwd=SCRIPT_REPO_ROOT, codex_home=codex_home)

    if args.check:
        payload = build_installation_check(
            repo_root=repo_root,
            codex_home=codex_home,
            allow_deferred_automation_restore=args.allow_deferred_automation_restore,
        )
        if args.json:
            print_json(payload)
        else:
            status = "OK" if payload["ok"] else "FAILED"
            print_text(f"Predictive KB install check: {status}")
            print_text(f"repo_root: {payload['repo_root']}")
            print_text(f"codex_home: {payload['codex_home']}")
            print_text(f"skill_path: {payload['skill_path']}")
            print_text(f"launcher_path: {payload['launcher_path']}")
            print_text(f"global_agents_path: {payload['global_agents_path']}")
            print_text(f"install_state_path: {payload['install_state_path']}")
            print_text(f"maintenance_skills: {', '.join(payload.get('maintenance_skill_names', []))}")
            print_text("checklist:")
            for item in payload.get("checklist", []):
                marker = "[OK]" if item.get("ok") else "[MISSING]"
                print_text(f"- {marker} {item.get('label')}")
                details = str(item.get("details", "") or "").strip()
                if details:
                    print_text(f"  details: {details}")
            if payload["warnings"]:
                print_text("warnings:")
                for item in payload["warnings"]:
                    print_text(f"- {item}")
            if payload["issues"]:
                print_text("issues:")
                for item in payload["issues"]:
                    print_text(f"- {item}")
        return 0 if payload["ok"] else 1

    isolated_fixture = os.environ.get("KHAOS_BRAIN_ISOLATED_INSTALL_FIXTURE") == "1"
    assurance_child = os.environ.get("KHAOS_BRAIN_ASSURANCE_ACTIVE") == "1"
    # An environment marker alone can never weaken a real-machine install.
    # Lightweight gates are accepted only for an explicitly temporary Codex
    # home used by the aggregate regression or an isolated installer fixture.
    lightweight_fixture = (
        isolated_fixture or assurance_child
    ) and _is_temporary_fixture_home(codex_home)
    fixture_shell_bin = (
        (codex_home.parent / "codex-shell-bin").resolve()
        if lightweight_fixture
        else None
    )
    automation_state_snapshot = None
    try:
        if args.automation_state_snapshot:
            snapshot_path = Path(args.automation_state_snapshot).expanduser().resolve()
            try:
                loaded_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"automation state snapshot could not be read: {type(exc).__name__}"
                ) from exc
            if not isinstance(loaded_snapshot, dict):
                raise ValueError("automation state snapshot must be a JSON object")
            automation_state_snapshot = loaded_snapshot
        payload = install_codex_integration(
            repo_root=repo_root,
            codex_home=codex_home,
            shell_bin_dir=fixture_shell_bin,
            persist_user_shell_path=not lightweight_fixture,
            run_history_migration=not lightweight_fixture,
            run_upgrade_assurance=not lightweight_fixture,
            defer_automation_restore=args.defer_automation_restore,
            automation_state_snapshot=automation_state_snapshot,
        )
    except Exception as exc:
        attempt = latest_upgrade_attempt(codex_home)
        failure = {
            "schema_version": "khaos-brain.install-result.v1",
            "ok": False,
            "status": "failed",
            "checkpoint": str(attempt.get("phase") or "install_preflight"),
            "attempt_id": str(attempt.get("attempt_id") or ""),
            "attempt_receipt_path": str(attempt.get("current_path") or ""),
            "blockers": [f"{type(exc).__name__}: {str(exc)[-4000:]}"],
            "automations_safe_state": (
                "PAUSED" if not lightweight_fixture else "fixture-owned"
            ),
            "retry_action": (
                "Repair the reported hard gate and rerun the idempotent installer; "
                "do not manually resume automations first."
            ),
            "claim_boundary": (
                "This terminal proves only that installation failed closed at the named "
                "checkpoint; it does not claim a healthy install."
            ),
        }
        if args.json:
            print_json(failure)
        else:
            print_text(
                f"Predictive KB install failed safely at {failure['checkpoint']}."
            )
            for blocker in failure["blockers"]:
                print_text(f"- {blocker}")
        return 1
    if args.json:
        print_json(payload)
    else:
        print_text("Installed predictive KB Codex integration.")
        print_text(f"repo_root: {payload['repo_root']}")
        print_text(f"codex_home: {payload['codex_home']}")
        print_text(f"skill_path: {payload['skill_path']}")
        print_text(f"launcher_path: {payload['launcher_path']}")
        print_text(f"install_state_path: {payload['install_state_path']}")
        print_text(f"maintenance_skills: {', '.join(payload.get('maintenance_skill_names', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
