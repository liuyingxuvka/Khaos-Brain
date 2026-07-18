#!/usr/bin/env python3
"""Execute one explicitly user-requested Khaos Brain software update."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.cli_output import print_json  # noqa: E402
from local_kb.config import default_codex_home, resolve_repo_root  # noqa: E402
from local_kb.install import (  # noqa: E402
    apply_repo_automation_restoration_plan,
    build_installation_check,
    capture_repo_automation_state_snapshot,
    pause_repo_automations,
    plan_repo_automation_restoration,
)
from local_kb.maintenance_lanes import acquire_lane_lock, release_lane_lock  # noqa: E402
from local_kb.automation_contracts import (  # noqa: E402
    AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
    PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
    UPDATE_NATIVE_TIMEOUT_SECONDS,
    UPDATE_OWNER_TIMEOUT_SECONDS,
)
from local_kb.automation_runtime import (  # noqa: E402
    automation_run_root,
    build_native_receipt,
    validate_native_receipt,
    write_native_receipt,
)
from local_kb.software_update import (  # noqa: E402
    LEGAL_MANUAL_UPDATE_NOOP_REASONS,
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_FAILED,
    manual_update_check,
    mark_update_status,
)


def _git(repo_root: Path, *args: str, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("git") or "git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def _json_command(command: list[str], repo_root: Path, *, timeout: int) -> tuple[int, dict, str]:
    completed = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {}
    return completed.returncode, payload if isinstance(payload, dict) else {}, completed.stderr[-4000:]


def _snapshot_path(repo_root: Path) -> Path:
    return Path(repo_root) / ".local" / "khaos_brain_manual_update_snapshot.json"


def _snapshot_digest(payload: dict) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "snapshot_hash"}
    encoded = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def _capture_or_load_snapshot(
    repo_root: Path,
    codex_home: Path,
    *,
    target_revision: str,
    source_revision: str,
    run_id: str,
) -> dict:
    path = _snapshot_path(repo_root)
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}
        if isinstance(payload, dict) and payload.get("target_revision") == target_revision:
            if (
                payload.get("schema_version") != "khaos-brain.manual-update-snapshot.v3"
                or payload.get("snapshot_hash") != _snapshot_digest(payload)
                or not isinstance(payload.get("states"), dict)
                or not isinstance(payload.get("user_paused"), dict)
            ):
                raise RuntimeError("same-target automation snapshot is invalid or tampered")
            return {**payload, "path": str(path), "reused": True}
    capture = capture_repo_automation_state_snapshot(codex_home)
    payload = {
        "schema_version": "khaos-brain.manual-update-snapshot.v3",
        "target_revision": target_revision,
        "source_revision": source_revision,
        "capture_run_id": run_id,
        "states": capture["states"],
        "user_paused": capture["user_paused"],
        "state_sources": capture["sources"],
        "ambiguities": capture["ambiguities"],
        "ok": capture["ok"],
    }
    payload["snapshot_hash"] = _snapshot_digest(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return {**payload, "path": str(path), "reused": False}


def _fail(repo_root: Path, codex_home: Path, result: dict, message: str) -> dict:
    result["pause_after_failure"] = pause_repo_automations(codex_home)
    mark_update_status(repo_root, UPDATE_STATUS_FAILED, error=message)
    result.update({"ok": False, "status": "failed", "error": message})
    return result


def _mapping_ok(value: object) -> bool:
    return isinstance(value, dict) and value.get("ok") is True


def run_manual_update(
    repo_root: Path,
    codex_home: Path,
    *,
    explicit_user_request: bool,
    run_id: str = "",
) -> dict:
    resolved_run_id = str(run_id or f"manual-update-{uuid4().hex}")
    if not explicit_user_request:
        return {
            "ok": False,
            "status": "blocked",
            "run_id": resolved_run_id,
            "reason": "explicit-user-request-required",
            "error": "Manual update requires an explicit user request in the current invocation.",
            "terminal_gate": {
                "gate_id": "manual-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": "explicit-user-request-required",
            },
            "manual_check": {
                "ok": False,
                "apply_ready": False,
                "reason": "explicit-user-request-required",
            },
            "git_update": {"attempted": False, "mode": "ff-only"},
            "install": {},
            "install_check": {},
            "state_mutation_attempted": False,
        }
    lane_lock = acquire_lane_lock(
        repo_root,
        "khaos-brain-manual-update",
        run_id=resolved_run_id,
        wait=False,
    )
    if lane_lock.get("acquired") is not True:
        reason = "concurrent-update"
        return {
            "ok": False,
            "status": "blocked",
            "run_id": resolved_run_id,
            "reason": reason,
            "terminal_gate": {
                "gate_id": "manual-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": reason,
            },
            "manual_check": {"ok": True, "apply_ready": False, "reason": reason},
            "git_update": {"attempted": False, "mode": "ff-only"},
            "install": {},
            "install_check": {},
            "lane_lock": lane_lock,
        }
    gate = manual_update_check(repo_root, explicit_user_request=True)
    result: dict = {
        "ok": True,
        "status": "no-op",
        "reason": str(gate.get("reason") or "no-update"),
        "manual_check": gate,
        "git_update": {"attempted": False, "mode": "ff-only"},
        "install": {},
        "install_check": {},
        "claim_boundary": (
            "Only an explicit current user request may enter the fast-forward and transactional install route. "
            "A failed mutating update leaves the installer-owned four survivor automations paused."
        ),
        "run_id": resolved_run_id,
        "lane_lock": lane_lock,
    }
    try:
        if gate.get("ok") is not True:
            result.update(
                {
                    "ok": False,
                    "status": "blocked",
                    "error": str(gate.get("error") or gate.get("reason") or "manual update gate failed"),
                    "terminal_gate": {
                        "gate_id": "manual-update-check",
                        "evaluated": True,
                        "applicable": False,
                        "reason": str(gate.get("reason") or "manual-update-blocked"),
                    },
                }
            )
            return result
        if gate.get("apply_ready") is not True:
            result["terminal_gate"] = {
                "gate_id": "manual-update-check",
                "evaluated": True,
                "applicable": False,
                "reason": str(gate.get("reason") or result["reason"]),
            }
            if result["reason"] not in LEGAL_MANUAL_UPDATE_NOOP_REASONS:
                result.update(
                    {
                        "ok": False,
                        "status": "blocked",
                        "error": (
                            "manual update remains unfinished: "
                            f"{result['reason']}"
                        ),
                    }
                )
            return result

        dirty = _git(repo_root, "status", "--porcelain", "--untracked-files=no")
        if dirty.returncode != 0:
            return _fail(repo_root, codex_home, result, dirty.stderr.strip() or "git status failed")
        if dirty.stdout.strip():
            return _fail(
                repo_root,
                codex_home,
                result,
                "tracked user or peer work is dirty; manual update refused without overwriting it",
            )
        upstream_result = _git(
            repo_root,
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{u}",
        )
        upstream = upstream_result.stdout.strip()
        if upstream_result.returncode != 0 or not upstream:
            return _fail(repo_root, codex_home, result, upstream_result.stderr.strip() or "upstream is not configured")
        before = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
        gate_state = gate.get("state") if isinstance(gate.get("state"), dict) else {}
        target_revision = str(gate_state.get("latest_revision") or "").strip()
        if not before or not target_revision:
            return _fail(repo_root, codex_home, result, "update revision binding is missing")
        snapshot = _capture_or_load_snapshot(
            repo_root,
            codex_home,
            target_revision=target_revision,
            source_revision=before,
            run_id=resolved_run_id,
        )
        result["automation_state_snapshot"] = snapshot
        if snapshot.get("ok") is not True:
            return _fail(
                repo_root,
                codex_home,
                result,
                "; ".join(str(item) for item in snapshot.get("ambiguities") or []),
            )
        pause_receipt = pause_repo_automations(codex_home)
        result["pause_before_mutation"] = pause_receipt
        if pause_receipt.get("ok") is not True:
            return _fail(repo_root, codex_home, result, "failed to pause surviving automations before update")
        merge = _git(repo_root, "merge", "--ff-only", upstream, timeout=300)
        result["git_update"] = {
            "attempted": True,
            "ok": merge.returncode == 0,
            "mode": "ff-only",
            "upstream": upstream,
            "before_revision": before,
            "after_revision": _git(repo_root, "rev-parse", "HEAD").stdout.strip(),
            "stderr": merge.stderr[-2000:],
        }
        if merge.returncode != 0:
            return _fail(repo_root, codex_home, result, merge.stderr.strip() or "git fast-forward failed")

        install_command = [
            sys.executable,
            "scripts/install_codex_kb.py",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--defer-automation-restore",
            "--automation-state-snapshot",
            str(snapshot["path"]),
            "--json",
        ]
        install_code, install, install_error = _json_command(
            install_command,
            repo_root,
            timeout=10800,
        )
        result["install"] = install
        if install_code != 0 or not install or not _mapping_ok(install.get("install_transaction")):
            return _fail(repo_root, codex_home, result, install_error or "transactional installer failed")
        check_code, install_check, check_error = _json_command(
            [
                sys.executable,
                "scripts/install_codex_kb.py",
                "--repo-root",
                str(repo_root),
                "--codex-home",
                str(codex_home),
                "--check",
                "--allow-deferred-automation-restore",
                "--json",
            ],
            repo_root,
            timeout=3600,
        )
        result["install_check"] = install_check
        install_transaction = install.get("install_transaction") if isinstance(install.get("install_transaction"), dict) else {}
        checked_transaction = install_check.get("install_transaction") if isinstance(install_check.get("install_transaction"), dict) else {}
        transaction_matches = bool(
            install_transaction.get("transaction_id")
            and install_transaction.get("transaction_id") == checked_transaction.get("transaction_id")
            and install_transaction.get("receipt_hash") == checked_transaction.get("receipt_hash")
        )
        if check_code != 0 or install_check.get("ok") is not True or not transaction_matches:
            return _fail(repo_root, codex_home, result, check_error or "post-update install health failed or transaction mismatched")
        pause_after_native = pause_repo_automations(codex_home)
        result["pause_after_native"] = pause_after_native
        if pause_after_native.get("ok") is not True:
            return _fail(repo_root, codex_home, result, "failed to keep automations paused before native restoration")
        states = snapshot.get("states") if isinstance(snapshot.get("states"), dict) else {}
        user_paused = (
            snapshot.get("user_paused")
            if isinstance(snapshot.get("user_paused"), dict)
            else {}
        )
        live_before_restoration = capture_repo_automation_state_snapshot(codex_home)
        restoration_plan = plan_repo_automation_restoration(
            codex_home,
            states,
            user_paused_states=user_paused,
        )
        live_still_paused = bool(
            live_before_restoration.get("ok") is True
            and live_before_restoration.get("states")
            and all(
                value == "PAUSED"
                for value in live_before_restoration.get("states", {}).values()
            )
        )
        deferred_install_check = (
            build_installation_check(
                repo_root=repo_root,
                codex_home=codex_home,
                allow_deferred_automation_restore=True,
            )
            if live_still_paused and restoration_plan.get("ok") is True
            else {
                "ok": False,
                "issues": [
                    "live automations were not all paused or the exact restoration plan failed"
                ],
            }
        )
        result["update_finalization"] = {
            "live_before_restoration": live_before_restoration,
            "restoration_plan": restoration_plan,
            "deferred_install_check": deferred_install_check,
        }
        if deferred_install_check.get("ok") is not True:
            return _fail(
                repo_root,
                codex_home,
                result,
                "native deferred installed-state validation failed",
            )
        restoration = apply_repo_automation_restoration_plan(
            codex_home,
            restoration_plan,
        )
        result["update_finalization"]["restoration"] = restoration
        restoration_exact = bool(
            restoration.get("ok") is True
            and restoration.get("restored") == states
            and restoration.get("restored_user_paused") == user_paused
            and restoration.get("plan_hash") == restoration_plan.get("plan_hash")
        )
        final_install_check = (
            build_installation_check(
                repo_root=repo_root,
                codex_home=codex_home,
            )
            if restoration_exact
            else {
                "ok": False,
                "issues": ["automation restoration did not read back exactly"],
            }
        )
        result["update_finalization"]["final_install_check"] = final_install_check
        if final_install_check.get("ok") is not True:
            return _fail(
                repo_root,
                codex_home,
                result,
                "native automation restoration or final installed-state readback failed",
            )
        result["update_state"] = mark_update_status(
            repo_root, UPDATE_STATUS_CURRENT, error=""
        )
        snapshot_path = Path(str(snapshot.get("path") or ""))
        snapshot_path_safe = False
        try:
            snapshot_path.resolve().relative_to((repo_root / ".local").resolve())
            snapshot_path_safe = True
        except (OSError, ValueError):
            pass
        snapshot_deleted = False
        if snapshot_path_safe and snapshot_path.is_file():
            snapshot_path.unlink()
            snapshot_deleted = not snapshot_path.exists()
        result["snapshot_cleanup"] = {
            "ok": snapshot_path_safe and not snapshot_path.exists(),
            "path": str(snapshot_path),
            "deleted": snapshot_deleted,
        }
        result.update(
            {
                "ok": True,
                "status": "current-and-restored",
                "reason": "explicit-manual-update-completed",
            }
        )
        return result
    finally:
        result["lock_release"] = release_lane_lock(
            repo_root,
            "khaos-brain-manual-update",
            run_id=resolved_run_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--explicit-user-request",
        action="store_true",
        help="Confirm that the current user explicitly requested this manual update.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    codex_home = (
        Path(args.codex_home).expanduser().resolve()
        if args.codex_home
        else default_codex_home()
    )
    repo_root = resolve_repo_root(args.repo_root, cwd=REPO_ROOT, codex_home=codex_home)
    resolved_run_id = str(args.run_id or f"manual-update-{uuid4().hex}")
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        result = run_manual_update(
            repo_root,
            codex_home,
            explicit_user_request=args.explicit_user_request,
            run_id=resolved_run_id,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        result = _fail(
            repo_root,
            codex_home,
            {"manual_check": {}, "git_update": {}, "install": {}, "install_check": {}},
            f"{type(exc).__name__}: {exc}",
        )
    result["run_id"] = resolved_run_id
    result["_owner_timeout_policy"] = {
        "native_timeout_seconds": UPDATE_NATIVE_TIMEOUT_SECONDS,
        "owner_timeout_seconds": UPDATE_OWNER_TIMEOUT_SECONDS,
        "aggregate_timeout_seconds": AGGREGATE_ASSURANCE_TIMEOUT_SECONDS,
        "installer_timeout_seconds": PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
        "timed_out": False,
        "cleanup_confirmed": True,
        "remaining_process_count": 0,
    }
    command = [
        sys.executable,
        "scripts/run_khaos_brain_manual_update.py",
        "--repo-root",
        str(repo_root),
        "--codex-home",
        str(codex_home),
        "--run-id",
        resolved_run_id,
    ]
    if args.explicit_user_request:
        command.append("--explicit-user-request")
    command.append("--json")
    receipt = build_native_receipt(
        "khaos-brain-update",
        run_id=resolved_run_id,
        command=command,
        native_payload=result,
        exit_code=0 if result.get("ok") is True else 1,
        started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    receipt_path = write_native_receipt(
        automation_run_root(repo_root, "khaos-brain-update", resolved_run_id)
        / "native-receipt.json",
        receipt,
    )
    receipt_validation = validate_native_receipt(
        receipt_path,
        skill_id="khaos-brain-update",
        expected_run_id=resolved_run_id,
        expected_receipt_hash=str(receipt.get("receipt_hash") or ""),
    )
    result["native_receipt_path"] = str(receipt_path)
    result["native_receipt_hash"] = str(receipt.get("receipt_hash") or "")
    result["native_receipt_validation"] = receipt_validation
    result["ok"] = result.get("ok") is True and receipt_validation.get("ok") is True
    print_json(result, sort_keys=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
