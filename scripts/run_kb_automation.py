#!/usr/bin/env python3
"""Run one target-owned KB maintenance automation to a native terminal."""

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
    AUTOMATION_COMPLETION_CONTRACTS,
    STANDARD_OWNER_TIMEOUT_SECONDS,
    STANDARD_NATIVE_TIMEOUT_SECONDS,
)
from local_kb.automation_runtime import (  # noqa: E402
    RUNTIME_WRAPPER_SCHEMA,
    automation_run_root,
    build_native_receipt,
    validate_native_receipt,
    write_native_receipt,
)
from local_kb.cli_output import print_json  # noqa: E402
from local_kb.config import default_codex_home, resolve_repo_root  # noqa: E402
from local_kb.process_control import run_with_timeout_cleanup  # noqa: E402


SUPPORTED_SKILLS = (
    "kb-sleep-maintenance",
    "kb-dream-pass",
    "kb-organization-contribute",
    "kb-organization-maintenance",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run_id(skill_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"native-{skill_id}-{stamp}-{uuid4().hex[:8]}"


def native_command(skill_id: str, *, repo_root: Path, run_id: str) -> list[str]:
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
    }
    return commands[skill_id]


def _parse_payload(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def run_automation(
    skill_id: str,
    *,
    repo_root: Path,
    codex_home: Path,
    scheduler_or_trigger_id: str = "",
) -> dict:
    del codex_home
    run_id = _run_id(skill_id)
    run_root = automation_run_root(repo_root, skill_id, run_id)
    command = native_command(skill_id, repo_root=repo_root, run_id=run_id)
    started_at = _utc_now()
    cleanup: dict[str, object] = {}
    try:
        completed = run_with_timeout_cleanup(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=STANDARD_NATIVE_TIMEOUT_SECONDS,
        )
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = str(exc.stdout or "")
        stderr = str(exc.stderr or "")
        cleanup = dict(getattr(exc, "cleanup_receipt", {}) or {})
    payload = _parse_payload(stdout)
    payload["_owner_timeout_policy"] = {
        "native_timeout_seconds": STANDARD_NATIVE_TIMEOUT_SECONDS,
        "owner_timeout_seconds": STANDARD_OWNER_TIMEOUT_SECONDS,
        "aggregate_timeout_seconds": STANDARD_OWNER_TIMEOUT_SECONDS,
        "installer_timeout_seconds": 0,
        "timed_out": exit_code == 124,
        "cleanup_confirmed": (
            cleanup.get("cleanup_confirmed") is True if exit_code == 124 else True
        ),
        "remaining_process_count": int(cleanup.get("remaining_process_count") or 0),
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
    validation = validate_native_receipt(
        receipt_path,
        skill_id=skill_id,
        expected_run_id=run_id,
        expected_receipt_hash=str(receipt.get("receipt_hash") or ""),
    )
    terminal = str(receipt.get("terminal_status") or "failed")
    result = {
        "schema_version": RUNTIME_WRAPPER_SCHEMA,
        "ok": validation.get("ok") is True,
        "status": terminal if validation.get("ok") is True else "failed",
        "skill_id": skill_id,
        "automation_id": AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"],
        "execution_kind": AUTOMATION_COMPLETION_CONTRACTS[skill_id]["execution_kind"],
        "scheduler_or_trigger_id": (
            scheduler_or_trigger_id
            or str(AUTOMATION_COMPLETION_CONTRACTS[skill_id]["automation_id"])
        ),
        "run_id": run_id,
        "native_receipt_path": str(receipt_path),
        "native_receipt_hash": receipt.get("receipt_hash"),
        "native_receipt_validation": validation,
        "native_exit_code": exit_code,
        "native_stderr_tail": stderr[-3000:],
        "timeout_cleanup": cleanup,
        "issues": [
            *list(receipt.get("evaluation_issues", [])),
            *list(validation.get("issues", [])),
        ],
        "claim_boundary": (
            "This target-owned wrapper proves only the captured native terminal and "
            "the skill's own obligation evidence for this exact run."
        ),
    }
    run_root.mkdir(parents=True, exist_ok=True)
    report_path = run_root / "execution-result.json"
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result["execution_result_path"] = str(report_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True, choices=SUPPORTED_SKILLS)
    parser.add_argument("--repo-root", default="auto")
    parser.add_argument("--codex-home", default="")
    parser.add_argument("--scheduler-or-trigger-id", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    codex_home = (
        Path(args.codex_home).expanduser().resolve()
        if args.codex_home
        else default_codex_home()
    )
    repo_root = resolve_repo_root(args.repo_root, cwd=REPO_ROOT, codex_home=codex_home)
    result = run_automation(
        args.skill,
        repo_root=repo_root,
        codex_home=codex_home,
        scheduler_or_trigger_id=args.scheduler_or_trigger_id,
    )
    print_json(result, sort_keys=True)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
