#!/usr/bin/env python3
"""Run one native KB automation and close that exact run through SkillGuard."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from local_kb.automation_contracts import (  # noqa: E402
    AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS,
    AUTOMATION_COMPLETION_CONTRACTS,
    PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
    STANDARD_NATIVE_TIMEOUT_SECONDS,
    STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
    UPDATE_NATIVE_TIMEOUT_SECONDS,
    UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS,
)
from local_kb.automation_runtime import (  # noqa: E402
    RUNTIME_WRAPPER_SCHEMA,
    automation_run_root,
    build_update_activation_receipt,
    build_native_receipt,
    build_update_finalization_receipt,
    validate_update_activation_receipt,
    write_native_receipt,
)
from local_kb.cli_output import print_json  # noqa: E402
from local_kb.config import default_codex_home, resolve_repo_root  # noqa: E402
from local_kb.install import (  # noqa: E402
    apply_repo_automation_restoration_plan,
    build_installation_check,
    capture_repo_automation_state_snapshot,
    pause_repo_automations,
    plan_repo_automation_restoration,
)
from local_kb.process_control import run_with_timeout_cleanup  # noqa: E402
from local_kb.software_update import (  # noqa: E402
    UPDATE_STATUS_CURRENT,
    UPDATE_STATUS_FAILED,
    load_update_state,
    mark_update_status,
)
from scripts.check_kb_skillguard import (  # noqa: E402
    _build_current_scheduled_production_identity,
    _close_scheduled_supervision_session,
    _execute_supervision,
    _scheduled_supervision_snapshot,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id(skill_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"guarded-{skill_id}-{stamp}-{uuid4().hex[:8]}"


def native_command(
    skill_id: str,
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str,
) -> list[str]:
    commands = {
        "kb-sleep-maintenance": [
            sys.executable,
            ".agents/skills/local-kb-retrieve/scripts/kb_sleep.py",
            "--repo-root",
            str(repo_root),
            "--run-id",
            run_id,
            "--json",
        ],
        "kb-dream-pass": [
            sys.executable,
            ".agents/skills/local-kb-retrieve/scripts/kb_dream.py",
            "--repo-root",
            str(repo_root),
            "--run-id",
            run_id,
            "--json",
        ],
        "kb-organization-contribute": [
            sys.executable,
            "scripts/kb_org_outbox.py",
            "--repo-root",
            str(repo_root),
            "--automation",
            "--run-id",
            run_id,
        ],
        "kb-organization-maintenance": [
            sys.executable,
            "scripts/kb_org_maintainer.py",
            "--repo-root",
            str(repo_root),
            "--automation",
            "--run-id",
            run_id,
        ],
        "khaos-brain-update": [
            sys.executable,
            "scripts/run_khaos_brain_system_update.py",
            "--repo-root",
            str(repo_root),
            "--codex-home",
            str(codex_home),
            "--run-id",
            run_id,
            "--json",
        ],
    }
    return commands[skill_id]


def _parse_payload(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_guarded_result(run_root: Path, result: dict) -> dict:
    run_root.mkdir(parents=True, exist_ok=True)
    report_path = run_root / "guarded-result.json"
    scheduled_identity = result.get("scheduled_production_identity")
    if isinstance(scheduled_identity, dict):
        result.setdefault(
            "scheduled_supervision_snapshot",
            _scheduled_supervision_snapshot(scheduled_identity),
        )
    try:
        report_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        result["guarded_result_path"] = str(report_path)
        return result
    finally:
        _close_scheduled_supervision_session(
            scheduled_identity if isinstance(scheduled_identity, dict) else None
        )


def run_guarded_automation(
    skill_id: str,
    *,
    repo_root: Path,
    codex_home: Path,
    scheduler_or_trigger_id: str = "",
) -> dict:
    run_id = _run_id(skill_id)
    run_root = automation_run_root(repo_root, skill_id, run_id)
    installed_skill = codex_home / "skills" / skill_id
    preflight_result = {
        "schema_version": RUNTIME_WRAPPER_SCHEMA,
        "ok": False,
        "skill_id": skill_id,
        "automation_id": AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"],
        "run_id": run_id,
        "skillguard": {},
        "claim_boundary": (
            "Success requires the current installed SkillGuard identity, the target-owned native terminal, "
            "and the sole official current enforced closure for this exact scheduled execution."
        ),
    }
    if not installed_skill.is_dir():
        preflight_result["status"] = "skillguard-installed-skill-missing"
        preflight_result["issues"] = [str(installed_skill)]
        if skill_id == "khaos-brain-update":
            preflight_result["pause_after_skillguard_failure"] = pause_repo_automations(
                codex_home
            )
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="installed automation Skill is missing",
            )
        return _persist_guarded_result(run_root, preflight_result)
    trigger_id = (
        scheduler_or_trigger_id
        or str(AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"])
    )
    try:
        scheduled_identity = _build_current_scheduled_production_identity(
            codex_home,
            scheduler_or_trigger_id=trigger_id,
            scheduled_execution_id=run_id,
            scheduled_skill_root=installed_skill,
            repository_root=repo_root,
            session_root=run_root / "scheduled-supervision-session",
        )
    except Exception as exc:  # fail before the native owner can mutate state
        preflight_result["status"] = "scheduled-production-identity-blocked"
        preflight_result["issues"] = [f"{type(exc).__name__}: {exc}"]
        if skill_id == "khaos-brain-update":
            preflight_result["pause_after_skillguard_failure"] = pause_repo_automations(
                codex_home
            )
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="SkillGuard installation identity is not current",
            )
        return _persist_guarded_result(run_root, preflight_result)
    command = native_command(
        skill_id,
        repo_root=repo_root,
        codex_home=codex_home,
        run_id=run_id,
    )
    started_at = _utc_now()
    timeout = (
        UPDATE_NATIVE_TIMEOUT_SECONDS
        if skill_id == "khaos-brain-update"
        else STANDARD_NATIVE_TIMEOUT_SECONDS
    )
    timeout_cleanup: dict[str, object] = {}
    try:
        completed = run_with_timeout_cleanup(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        timeout_cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
    payload = _parse_payload(stdout)
    payload["_guarded_timeout_policy"] = {
        "native_timeout_seconds": timeout,
        "scheduled_timeout_seconds": (
            UPDATE_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
            if skill_id == "khaos-brain-update"
            else STANDARD_SCHEDULED_PRODUCTION_TIMEOUT_SECONDS
        ),
        "aggregate_timeout_seconds": AGGREGATE_SKILLGUARD_TIMEOUT_SECONDS,
        "installer_timeout_seconds": PRE_RESTORE_ASSURANCE_TIMEOUT_SECONDS,
        "timed_out": exit_code == 124,
        "cleanup_confirmed": (
            timeout_cleanup.get("cleanup_confirmed") is True
            if exit_code == 124
            else True
        ),
        "remaining_process_count": int(
            timeout_cleanup.get("remaining_process_count") or 0
        ),
    }
    receipt = build_native_receipt(
        skill_id,
        run_id=run_id,
        command=command,
        native_payload=payload,
        exit_code=exit_code,
        started_at=started_at,
        finished_at=_utc_now(),
    )
    receipt_path = write_native_receipt(run_root / "native-receipt.json", receipt)
    native_ok = receipt.get("terminal_status") in {"completed", "no-op"}
    result = {
        "schema_version": RUNTIME_WRAPPER_SCHEMA,
        "ok": False,
        "skill_id": skill_id,
        "automation_id": AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"],
        "run_id": run_id,
        "native_terminal_status": receipt.get("terminal_status"),
        "native_receipt_path": str(receipt_path),
        "native_receipt_hash": receipt.get("receipt_hash"),
        "native_exit_code": exit_code,
        "native_stderr_tail": stderr[-3000:],
        "native_timeout_seconds": timeout,
        "timeout_cleanup": timeout_cleanup,
        "scheduled_production_identity": scheduled_identity,
        "scheduled_supervision_snapshot": (
            _scheduled_supervision_snapshot(scheduled_identity)
        ),
        "skillguard": {},
        "claim_boundary": (
            "Success requires both the target-owned native terminal and an official current "
            "enforced SkillGuard closure for this exact immutable receipt."
        ),
    }
    if not native_ok:
        result["status"] = "native-failed"
        result["issues"] = receipt.get("evaluation_issues", [])
        return _persist_guarded_result(run_root, result)
    update_native_status = str(payload.get("status") or "")
    supervision_stage = "complete"
    native_terminal_branch_id = ""
    if skill_id == "khaos-brain-update":
        supervision_stage = (
            "no-op" if update_native_status == "no-op" else "authorization"
        )
        native_terminal_branch_id = (
            str(payload.get("reason") or "")
            if update_native_status == "no-op"
            else "prepared-update"
        )
    try:
        supervision = _execute_supervision(
            skill_id,
            installed_skill,
            codex_home,
            f"scheduled-{run_id}",
            native_receipt_path=receipt_path,
            expected_native_run_id=run_id,
            expected_native_receipt_hash=str(receipt.get("receipt_hash") or ""),
            expected_native_receipt_path=receipt_path,
            supervision_stage=supervision_stage,
            scheduler_or_trigger_id=scheduler_or_trigger_id,
            native_terminal_branch_id=native_terminal_branch_id,
            scheduled_production_identity=scheduled_identity,
        )
    except Exception as exc:  # fail closed at the external Guard boundary
        result["status"] = "skillguard-runtime-blocked"
        result["issues"] = [f"{type(exc).__name__}: {exc}"]
        if skill_id == "khaos-brain-update":
            result["pause_after_skillguard_failure"] = pause_repo_automations(
                codex_home
            )
            mark_update_status(
                repo_root,
                UPDATE_STATUS_FAILED,
                error="SkillGuard scheduled-production identity or supervision failed",
            )
        return _persist_guarded_result(run_root, result)
    result["skillguard"] = supervision
    supervision_ok = supervision.get("ok") is True
    if skill_id == "khaos-brain-update" and update_native_status == "no-op":
        result["ok"] = supervision_ok
        result["status"] = (
            "no-op-completed" if supervision_ok else "skillguard-blocked"
        )
    elif skill_id == "khaos-brain-update":
        result["ok"] = False
        result["status"] = (
            "update-authorization-closed"
            if supervision_ok
            else "skillguard-blocked"
        )
    else:
        result["ok"] = supervision_ok
        result["status"] = "completed" if result["ok"] else "skillguard-blocked"
    if skill_id == "khaos-brain-update" and payload.get("status") == "awaiting-skillguard":
        if supervision_ok:
            result["authorization_declared_check_receipt"] = supervision
            snapshot = payload.get("automation_state_snapshot") if isinstance(payload.get("automation_state_snapshot"), dict) else {}
            states = snapshot.get("states") if isinstance(snapshot.get("states"), dict) else {}
            user_paused_states = (
                snapshot.get("user_paused")
                if isinstance(snapshot.get("user_paused"), dict)
                else {}
            )
            live_before_finalization = capture_repo_automation_state_snapshot(codex_home)
            restoration_plan = plan_repo_automation_restoration(
                codex_home,
                states,
                user_paused_states=user_paused_states,
            )
            result["update_finalization"] = {
                "live_before_finalization": live_before_finalization,
                "restoration_plan": restoration_plan,
                "authorization_declared_checks_staged": True,
            }
            live_still_paused = bool(
                live_before_finalization.get("ok") is True
                and live_before_finalization.get("states")
                and all(
                    value == "PAUSED"
                    for value in live_before_finalization.get("states", {}).values()
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
            result["update_finalization"]["deferred_install_check"] = deferred_install_check
            if (
                live_still_paused
                and restoration_plan.get("ok") is True
                and deferred_install_check.get("ok") is True
            ):
                finalization_receipt = build_update_finalization_receipt(
                    run_id=run_id,
                    native_receipt_hash=str(receipt.get("receipt_hash") or ""),
                    authorization_declared_check_receipt=supervision,
                    snapshot=snapshot,
                    restoration_plan=restoration_plan,
                    deferred_install_check=deferred_install_check,
                    started_at=_utc_now(),
                )
                finalization_path = write_native_receipt(
                    run_root / "update-finalization-receipt.json",
                    finalization_receipt,
                )
                result["update_finalization"]["receipt_path"] = str(finalization_path)
                result["update_finalization"]["receipt_hash"] = finalization_receipt.get("receipt_hash")
                try:
                    final_supervision = _execute_supervision(
                        skill_id,
                        installed_skill,
                        codex_home,
                        f"scheduled-finalization-{run_id}",
                        native_receipt_path=receipt_path,
                        expected_native_run_id=run_id,
                        expected_native_receipt_hash=str(receipt.get("receipt_hash") or ""),
                        expected_native_receipt_path=receipt_path,
                        update_finalization_receipt_path=finalization_path,
                        expected_update_finalization_receipt_hash=str(
                            finalization_receipt.get("receipt_hash") or ""
                        ),
                        supervision_stage="finalization",
                        scheduler_or_trigger_id=scheduler_or_trigger_id,
                        native_terminal_branch_id="prepared-update",
                        scheduled_production_identity=scheduled_identity,
                    )
                except Exception as exc:  # fail closed and preserve PAUSED
                    result["ok"] = False
                    result["status"] = "update-final-skillguard-runtime-blocked"
                    result["update_finalization"]["issues"] = [
                        f"{type(exc).__name__}: {exc}"
                    ]
                    result["update_finalization"]["pause"] = pause_repo_automations(
                        codex_home
                    )
                    mark_update_status(
                        repo_root,
                        UPDATE_STATUS_FAILED,
                        error="final SkillGuard scheduled-production identity or supervision failed",
                    )
                    return _persist_guarded_result(run_root, result)
                result["update_finalization"]["skillguard"] = final_supervision
                result["skillguard"] = final_supervision
                if final_supervision.get("ok") is True:
                    restoration = apply_repo_automation_restoration_plan(
                        codex_home,
                        restoration_plan,
                    )
                    result["update_finalization"]["restoration"] = restoration
                    restoration_exact = bool(
                        restoration.get("ok") is True
                        and restoration.get("restored") == states
                        and restoration.get("restored_user_paused") == user_paused_states
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
                            "issues": ["authorized automation restoration did not read back exactly"],
                        }
                    )
                    result["update_finalization"]["final_install_check"] = final_install_check
                    if restoration_exact and final_install_check.get("ok") is True:
                        mark_update_status(repo_root, UPDATE_STATUS_CURRENT, error="")
                        current_state = load_update_state(repo_root)
                        activation_receipt = build_update_activation_receipt(
                            run_id=run_id,
                            native_receipt_hash=str(receipt.get("receipt_hash") or ""),
                            finalization_receipt_hash=str(
                                finalization_receipt.get("receipt_hash") or ""
                            ),
                            final_skillguard=final_supervision,
                            restoration_plan=restoration_plan,
                            restoration=restoration,
                            final_install_check=final_install_check,
                            update_state=current_state,
                            created_at=_utc_now(),
                        )
                        activation_path = write_native_receipt(
                            run_root / "update-activation-receipt.json",
                            activation_receipt,
                        )
                        result["update_finalization"]["activation_receipt_path"] = str(
                            activation_path
                        )
                        result["update_finalization"]["activation_receipt_hash"] = (
                            activation_receipt["receipt_hash"]
                        )
                        activation_validation = validate_update_activation_receipt(
                            activation_path,
                            expected_run_id=run_id,
                            expected_native_receipt_hash=str(
                                receipt.get("receipt_hash") or ""
                            ),
                            expected_finalization_receipt_hash=str(
                                finalization_receipt.get("receipt_hash") or ""
                            ),
                            expected_receipt_hash=str(
                                activation_receipt.get("receipt_hash") or ""
                            ),
                        )
                        result["update_finalization"]["activation_validation"] = (
                            activation_validation
                        )
                        if activation_validation.get("ok") is True:
                            snapshot_path = Path(str(snapshot.get("path") or ""))
                            try:
                                snapshot_path.resolve().relative_to(
                                    (repo_root / ".local").resolve()
                                )
                            except (OSError, ValueError):
                                snapshot_path = Path()
                            if snapshot_path.is_file():
                                snapshot_path.unlink()
                            result["update_finalization"]["status"] = (
                                "current-and-restored"
                            )
                            result["ok"] = True
                            result["status"] = "current-and-restored"
                        else:
                            result["ok"] = False
                            result["status"] = "update-activation-receipt-failed"
                            result["update_finalization"]["pause"] = (
                                pause_repo_automations(codex_home)
                            )
                            mark_update_status(
                                repo_root,
                                UPDATE_STATUS_FAILED,
                                error="final activation receipt validation failed",
                            )
                    else:
                        result["ok"] = False
                        result["status"] = "update-activation-failed"
                        result["update_finalization"]["pause"] = pause_repo_automations(
                            codex_home
                        )
                        mark_update_status(
                            repo_root,
                            UPDATE_STATUS_FAILED,
                            error="authorized automation restoration or final installed-state readback failed",
                        )
                else:
                    result["ok"] = False
                    result["status"] = "update-final-skillguard-blocked"
                    result["update_finalization"]["pause"] = pause_repo_automations(codex_home)
                    mark_update_status(
                        repo_root,
                        UPDATE_STATUS_FAILED,
                        error="staged restoration authorization SkillGuard closure failed",
                    )
            else:
                result["ok"] = False
                result["status"] = "update-finalization-failed"
                result["update_finalization"]["pause"] = pause_repo_automations(codex_home)
                mark_update_status(
                    repo_root,
                    UPDATE_STATUS_FAILED,
                    error="automation restoration plan or deferred installed-state validation failed",
                )
        else:
            result["pause_after_skillguard_failure"] = pause_repo_automations(codex_home)
            mark_update_status(repo_root, UPDATE_STATUS_FAILED, error="SkillGuard closure failed after native update")
    return _persist_guarded_result(run_root, result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", choices=tuple(AUTOMATION_COMPLETION_CONTRACTS), required=True)
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--scheduler-or-trigger-id", default="")
    args = parser.parse_args()
    codex_home = (
        Path(args.codex_home).expanduser().resolve()
        if args.codex_home
        else default_codex_home()
    )
    repo_root = resolve_repo_root(args.repo_root, cwd=REPO_ROOT, codex_home=codex_home)
    result = run_guarded_automation(
        args.skill,
        repo_root=repo_root,
        codex_home=codex_home,
        scheduler_or_trigger_id=args.scheduler_or_trigger_id,
    )
    print_json(result, sort_keys=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
