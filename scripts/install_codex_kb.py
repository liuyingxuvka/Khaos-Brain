#!/usr/bin/env python3
"""Install or verify the cross-machine Codex integration for this predictive KB."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


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


def _bounded_text(value: object, *, limit: int = 2_000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _status_projection(
    value: object,
    *,
    extra_keys: tuple[str, ...] = (),
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    keys = (
        "ok",
        "status",
        "phase",
        "reason",
        "migration_id",
        "run_id",
        "transaction_id",
        "receipt",
        "receipt_path",
        "receipt_digest",
        "manifest_path",
        "manifest_digest",
        "evidence_root",
        "idempotent_no_delta",
        *extra_keys,
    )
    projected: dict[str, Any] = {}
    for key in keys:
        item = value.get(key)
        if item is None or isinstance(item, (Mapping, list, tuple, set)):
            continue
        projected[key] = _bounded_text(item) if isinstance(item, str) else item
    issues = value.get("issues")
    if isinstance(issues, list):
        projected["issue_count"] = len(issues)
    warnings = value.get("warnings")
    if isinstance(warnings, list):
        projected["warning_count"] = len(warnings)
    return projected


def _upgrade_attempt_projection(
    value: object,
    *,
    codex_home: Path,
) -> dict[str, Any]:
    del codex_home
    if not isinstance(value, Mapping):
        return {}
    projected = {
        key: value.get(key)
        for key in (
            "attempt_id",
            "sequence",
            "status",
            "phase",
            "started_at",
            "updated_at",
            "receipt_hash",
            "latest_event_hash",
            "current_path",
            "survivors_must_remain_paused",
            "post_install_check_ok",
        )
        if value.get(key) is not None
    }
    return {
        key: _bounded_text(item) if isinstance(item, str) else item
        for key, item in projected.items()
    }


def _bounded_messages(value: object, *, limit: int = 50) -> tuple[list[str], int]:
    if not isinstance(value, list):
        return [], 0
    return [_bounded_text(item) for item in value[:limit]], max(0, len(value) - limit)


def _checklist_projection(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    projected: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        projected.append(
            {
                key: (
                    _bounded_text(item.get(key))
                    if key in {"id", "label", "details"}
                    else bool(item.get(key))
                )
                for key in ("id", "label", "ok", "details")
                if item.get(key) is not None
            }
        )
    return projected


def _installation_check_result_projection(
    payload: Mapping[str, Any],
    *,
    codex_home: Path,
) -> dict[str, Any]:
    issues, omitted_issues = _bounded_messages(payload.get("issues"))
    warnings, omitted_warnings = _bounded_messages(payload.get("warnings"))
    shell_tools = payload.get("shell_tools")
    shell_projection = (
        {
            key: shell_tools.get(key)
            for key in ("shell_bin_dir", "git_shim_path", "rg_path", "required")
            if shell_tools.get(key) is not None
        }
        if isinstance(shell_tools, Mapping)
        else {}
    )
    return {
        "schema_version": "khaos-brain.install-check-result.v1",
        "ok": bool(payload.get("ok")),
        "status": "passed" if payload.get("ok") else "failed",
        "repo_root": str(payload.get("repo_root") or ""),
        "manifest_repo_root": str(payload.get("manifest_repo_root") or ""),
        "codex_home": str(payload.get("codex_home") or codex_home),
        "skill_path": str(payload.get("skill_path") or ""),
        "launcher_path": str(payload.get("launcher_path") or ""),
        "global_agents_path": str(payload.get("global_agents_path") or ""),
        "install_state_path": str(payload.get("install_state_path") or ""),
        "maintenance_skill_names": list(payload.get("maintenance_skill_names") or []),
        "shell_tools": shell_projection,
        "checklist": _checklist_projection(payload.get("checklist")),
        "automation_restore_deferred": bool(
            payload.get("automation_restore_deferred")
        ),
        "history_migration_required": bool(
            payload.get("history_migration_required")
        ),
        "history_migration_check": _status_projection(
            payload.get("history_migration_check")
        ),
        "obsolete_update_state_settled": bool(
            payload.get("obsolete_update_state_settled")
        ),
        "update_state_source_current": bool(
            payload.get("update_state_source_current")
        ),
        "upgrade_assurance_required": bool(
            payload.get("upgrade_assurance_required")
        ),
        "upgrade_assurance": _status_projection(payload.get("upgrade_assurance")),
        "upgrade_attempt": _upgrade_attempt_projection(
            payload.get("upgrade_attempt"),
            codex_home=codex_home,
        ),
        "upgrade_attempt_authority": _status_projection(
            payload.get("upgrade_attempt_authority"),
            extra_keys=("head_path", "current_path"),
        ),
        "install_transaction": _status_projection(
            payload.get("install_transaction")
        ),
        "retired_paths": [
            _bounded_text(item) for item in list(payload.get("retired_paths") or [])
        ],
        "issue_count": len(payload.get("issues") or []),
        "issues": issues,
        "issues_omitted": omitted_issues,
        "warning_count": len(payload.get("warnings") or []),
        "warnings": warnings,
        "warnings_omitted": omitted_warnings,
        "claim_boundary": (
            "This is a bounded terminal projection. Full installation and assurance "
            "evidence remains at install_state_path and the upgrade-attempt "
            "HEAD/current/event references; this projection is not an alternate "
            "evidence authority."
        ),
    }


def _install_result_projection(
    payload: Mapping[str, Any],
    *,
    codex_home: Path,
) -> dict[str, Any]:
    shell_tools = payload.get("shell_tools")
    shell_projection = (
        {
            key: shell_tools.get(key)
            for key in (
                "shell_bin_dir",
                "git_shim_path",
                "rg_path",
                "user_path_updated",
            )
            if shell_tools.get(key) is not None
        }
        if isinstance(shell_tools, Mapping)
        else {}
    )
    attempt = _upgrade_attempt_projection(
        payload.get("upgrade_attempt"),
        codex_home=codex_home,
    )
    post_install_check = payload.get("post_install_check")
    post_install_projection = (
        {
            "ok": bool(post_install_check.get("ok")),
            "issue_count": len(post_install_check.get("issues") or []),
            "warning_count": len(post_install_check.get("warnings") or []),
        }
        if isinstance(post_install_check, Mapping)
        else {}
    )
    assurance_projection = _status_projection(payload.get("upgrade_assurance"))
    return {
        "schema_version": "khaos-brain.install-result.v1",
        "ok": True,
        "status": "completed",
        "repo_root": str(payload.get("repo_root") or ""),
        "codex_home": str(payload.get("codex_home") or codex_home),
        "skill_path": str(payload.get("skill_path") or ""),
        "launcher_path": str(payload.get("launcher_path") or ""),
        "global_agents_path": str(payload.get("global_agents_path") or ""),
        "install_state_path": str(payload.get("install_state_path") or ""),
        "maintenance_skill_names": list(payload.get("maintenance_skill_names") or []),
        "shell_tools": shell_projection,
        "automation_ids": list(payload.get("automation_ids") or []),
        "installed_automation_statuses": dict(
            payload.get("installed_automation_statuses") or {}
        ),
        "automation_restore_deferred": bool(
            payload.get("automation_restore_deferred")
        ),
        "history_migration_required": bool(
            payload.get("history_migration_required")
        ),
        "history_migration": _status_projection(payload.get("history_migration")),
        "upgrade_assurance_required": bool(
            payload.get("upgrade_assurance_required")
        ),
        "upgrade_assurance": assurance_projection,
        "upgrade_attempt": attempt,
        "post_install_check": post_install_projection,
        "retired_skill_ids": list(payload.get("retired_skill_ids") or []),
        "retired_automation_ids": list(payload.get("retired_automation_ids") or []),
        "installed_at": str(payload.get("installed_at") or ""),
        "evidence_refs": {
            "install_state_path": str(payload.get("install_state_path") or ""),
            "upgrade_attempt_current_path": str(attempt.get("current_path") or ""),
            "assurance_manifest_path": str(
                assurance_projection.get("manifest_path") or ""
            ),
        },
        "claim_boundary": (
            "This is a bounded terminal projection. Full immutable assurance, migration, "
            "transaction, and install-check evidence remains behind evidence_refs; this "
            "projection is not an alternate evidence authority."
        ),
    }


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
            print_json(
                _installation_check_result_projection(
                    payload,
                    codex_home=codex_home,
                )
            )
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
        print_json(_install_result_projection(payload, codex_home=codex_home))
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
